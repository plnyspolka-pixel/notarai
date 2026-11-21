"""Synthetic append-only confidential job journal tests, no real AWS."""
import copy
import json
import os
import tempfile
from pathlib import Path

import pytest

from confidential.event_journal import (
    DynamoJobJournal, JournalRejected, lambda_handler, transition,
)
from confidential.router import control_room_history
from fastapi import HTTPException
from test_confidential_auto import RequestFake, setup_tenant
from test_confidential_infra import template

TENANT = "pilot01"
JOB = "abc123"
SOURCE = (
    "arn:aws:dynamodb:eu-central-1:111122223333:"
    "table/notarai-confidential-jobs-pilot01/stream/2026-11-22T00:00:00.000"
)


def image(state="queued", attempts=0, tenant=TENANT):
    return {
        "tenant_id": {"S": tenant},
        "job_id": {"S": JOB},
        "state": {"S": state},
        "attempts": {"N": str(attempts)},
        "submitted": {"BOOL": False},
        "case_id": {"S": "sensitive-case-opaque"},
        "object_id": {"S": "sensitive-document-opaque"},
        "s3_version": {"S": "sensitive-object-version"},
    }


def record(name="INSERT", old=None, new=None, event_id="eventABC123"):
    record = {
        "eventSource": "aws:dynamodb",
        "eventSourceARN": SOURCE,
        "eventID": event_id,
        "eventName": name,
        "dynamodb": {
            "ApproximateCreationDateTime": 1800000000.5,
        }
    }
    if old is not None:
        record["dynamodb"]["OldImage"] = old
    if new is None and name == "INSERT":
        new = image()
    if new is not None:
        record["dynamodb"]["NewImage"] = new
    return record


class ConditionalError(Exception):
    response = {"Error": {"Code": "ConditionalCheckFailedException"}}


class Ddb:
    def __init__(self):
        self.rows = {}
        self.fail = False
        self.events = []
        self.last = False

    def put_item(self, **kwargs):
        if self.fail:
            raise RuntimeError("Private raw DynamoDB error")
        self.events.append(kwargs)
        row = kwargs["Item"]
        k = (row["pk"]["S"], row["sk"]["S"])
        assert kwargs["ConditionExpression"] == (
            "attribute_not_exists(pk) AND attribute_not_exists(sk)"
        )
        if k in self.rows:
            raise ConditionalError()
        self.rows[k] = copy.deepcopy(row)

    def get_item(self, **kwargs):
        if self.fail:
            raise RuntimeError("Synthetic DDB error")
        assert kwargs["ConsistentRead"] is True
        pk = kwargs["Key"]["pk"]["S"]
        sk = kwargs["Key"]["sk"]["S"]
        return {"Item": copy.deepcopy(self.rows.get((pk, sk), {}))}

    def query(self, **kwargs):
        assert kwargs["ScanIndexForward"] is False
        assert kwargs["ConsistentRead"] is True
        pk = kwargs["ExpressionAttributeValues"][":pk"]["S"]
        records = [
            copy.deepcopy(value)
            for (key, sk), value in sorted(self.rows.items(), reverse=True)
            if key == pk
        ]
        return {"Items": records[:kwargs["Limit"]]}


def test_transitions_strip_all_document_data():
    inserted = transition(record(), tenant=TENANT, source_arn=SOURCE)
    assert inserted["from"] is None
    assert inserted["to"] == "queued" and inserted["attempts"] == 0
    assert inserted["job_id"] == JOB
    serialized = json.dumps(inserted)
    assert "sensitive" not in serialized
    assert "version" not in serialized
    changed = transition(
        record("MODIFY", old=image(), new=image("running", 1)),
        tenant=TENANT, source_arn=SOURCE,
    )
    assert changed["from"] == "queued" and changed["to"] == "running"
    unchanged = transition(
        record("MODIFY", old=image(), new=image()),
        tenant=TENANT, source_arn=SOURCE,
    )
    assert unchanged is None
    deleted = transition(
        record("REMOVE", old=image("needs_review", 3)),
        tenant=TENANT, source_arn=SOURCE,
    )
    assert deleted["to"] == "deleted"


def test_duplicate_stream_event_is_idempotent_but_tampering_is_denied():
    ddb = Ddb()
    journal = DynamoJobJournal(ddb, tenant=TENANT)
    event = transition(record(), tenant=TENANT, source_arn=SOURCE)
    assert journal.append(event) is True
    assert journal.append(event) is False
    assert len(ddb.rows) == 1
    # Same hashed event id and timestamp but altered state must not be accepted.
    forged = dict(event, to="running")
    with pytest.raises(JournalRejected, match="integrity"):
        journal.append(forged)
    assert len(ddb.rows) == 1


def test_events_have_bounded_tenant_scoped_read_only_history():
    ddb = Ddb()
    journal = DynamoJobJournal(ddb, tenant=TENANT)
    for i, state in enumerate(("queued", "running", "preview_completed")):
        ev = transition(
            record("INSERT", new=image(state, i), event_id=f"event{i}"),
            tenant=TENANT, source_arn=SOURCE,
        )
        assert journal.append(ev)
    history = journal.for_job(JOB, limit=10)
    assert history["read_only"] is True
    assert history["job_id"] == JOB
    assert len(history["events"]) == 3
    assert set(history["events"][0]) == {
        "timestamp", "from", "to", "attempts", "event"
    }
    assert "sensitive" not in json.dumps(history)
    with pytest.raises(JournalRejected):
        DynamoJobJournal(ddb, tenant="another").for_job("../secret")


@pytest.mark.parametrize("mutate", [
    lambda x: x.update(eventSource="aws:s3"),
    lambda x: x.update(eventSourceARN=SOURCE.replace("pilot01", "other")),
    lambda x: x.update(eventName="SUBMIT"),
    lambda x: x.update(eventID="../bad"),
    lambda x: x["dynamodb"].update(NewImage=image(tenant="other")),
    lambda x: x["dynamodb"].update(NewImage={
        **image(), "submitted": {"BOOL": True},
    }),
    lambda x: x["dynamodb"].update(NewImage={
        **image(), "state": {"S": "submitted"},
    }),
    lambda x: x["dynamodb"].update(NewImage={
        **image(), "attempts": {"N": "99"},
    }),
])
def test_invalid_or_cross_tenant_stream_records_fail_closed(mutate):
    ev = record()
    mutate(ev)
    with pytest.raises(JournalRejected):
        transition(ev, tenant=TENANT, source_arn=SOURCE)


def test_lambda_batch_uses_tenant_pinned_journal(monkeypatch):
    ddb = Ddb()
    import boto3
    monkeypatch.setattr(boto3, "client", lambda name, **kw: ddb)
    monkeypatch.setenv("NOTARAI_AUDIT_TENANT", TENANT)
    monkeypatch.setenv("NOTARAI_JOB_STREAM_ARN", SOURCE)
    response = lambda_handler({
        "Records": [
            record("INSERT", event_id="one"),
            record("INSERT", event_id="two"),
        ]
    }, None)
    assert response == {"processed": 2}
    assert len(ddb.rows) == 2
    for item in ddb.rows.values():
        assert item["pk"]["S"] == f"JOB#{TENANT}#{JOB}"
        assert "s3_version" not in item
        assert "case_id" not in item
        assert "object_id" not in item


def test_stream_failed_write_raises_sanitized_error(monkeypatch):
    ddb = Ddb()
    ddb.fail = True
    journal = DynamoJobJournal(ddb, tenant=TENANT)
    with pytest.raises(JournalRejected) as exc:
        journal.append(transition(record(), tenant=TENANT, source_arn=SOURCE))
    assert "Private raw" not in str(exc.value)


def test_history_endpoint_authorization_and_no_submit(monkeypatch):
    setup_tenant(monkeypatch)
    import sys
    import boto3
    auth = sys.modules["autoryzacja"]
    auth._osoba_w_kancelarii = lambda tenant, email: {
        "rola": "wlasciciel",
    }
    ddb = Ddb()
    monkeypatch.setattr(boto3, "client", lambda name, **kwargs: ddb)
    ev = transition(record(), tenant=TENANT, source_arn=SOURCE)
    DynamoJobJournal(ddb, tenant=TENANT).append(ev)
    response = control_room_history(RequestFake(), JOB)
    payload = json.loads(response.body)
    assert response.headers["Cache-Control"] == "no-store"
    assert payload["read_only"] and payload["events"][0]["to"] == "queued"
    assert "submitted" not in json.dumps(payload)
    auth._osoba_w_kancelarii = lambda tenant, email: {
        "rola": "czlonek", "stanowisko": "sekretariat",
    }
    with pytest.raises(HTTPException) as denied:
        control_room_history(RequestFake(), JOB)
    assert denied.value.status_code == 403


def test_history_endpoint_denies_query_args_and_unknown_job_id(monkeypatch):
    setup_tenant(monkeypatch)
    import sys
    auth = sys.modules["autoryzacja"]
    auth._osoba_w_kancelarii = lambda tenant, email: {
        "rola": "wlasciciel",
    }
    with pytest.raises(HTTPException) as invalid:
        control_room_history(RequestFake("submit=true"), JOB)
    assert invalid.value.status_code == 400
    with pytest.raises(HTTPException):
        control_room_history(RequestFake(), "../other")


def test_cloudformation_append_only_audit_resources_are_disabled_by_default():
    ledger = template("notarai-confidential-job-ledger.yaml")
    props = ledger["Resources"]["PreviewJobs"]["Properties"]
    assert props["StreamSpecification"]["StreamViewType"] == "NEW_AND_OLD_IMAGES"
    audit = template("notarai-confidential-audit.yaml")
    resources = audit["Resources"]
    table = resources["AuditEvents"]
    assert table["DeletionPolicy"] == "Retain"
    assert table["Properties"]["PointInTimeRecoverySpecification"]["PointInTimeRecoveryEnabled"]
    trigger = resources["AuditSource"]["Properties"]
    assert trigger["StartingPosition"] == "TRIM_HORIZON"
    assert trigger["MaximumRetryAttempts"] == 3
    assert trigger["BisectBatchOnFunctionError"] is True
    assert trigger["Enabled"].get("If", [None])[0] == "EnableAudit"
    role = resources["AuditExecutionRole"]["Properties"]["Policies"][0][
        "PolicyDocument"]["Statement"
    ]
    append = next(x for x in role if x["Sid"] == "AppendAndDeduplicateOnly")
    assert set(append["Action"]) == {"dynamodb:PutItem", "dynamodb:GetItem"}
    assert not any(
        action in x.get("Action", [])
        for x in role for action in ("dynamodb:DeleteItem", "dynamodb:UpdateItem")
    )


def test_audit_zip_contains_only_allowlisted_python_sources(tmp_path):
    from scripts.package_confidential_audit import package
    import zipfile
    output = tmp_path / "audit.zip"
    digest = package(output)
    assert len(digest) == 64
    with zipfile.ZipFile(output) as zipped:
        assert set(zipped.namelist()) == {
            "confidential/__init__.py", "confidential/event_journal.py"
        }
    assert package(output) == digest
