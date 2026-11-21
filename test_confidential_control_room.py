"""Read-only AUTO Control Room tests, entirely synthetic and offline."""
import copy
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from confidential.control_room import (
    ControlRoom, ControlRoomRejected, authorized_notary,
)
from confidential.router import control_room_jobs
from test_confidential_auto import RequestFake, setup_tenant
from test_confidential_infra import template

TENANT = "pilot01"
JOB = "0123456789abcdef0123456789abcdef"


def entry(
    *, job=JOB, tenant=TENANT, state="queued", created=1000,
    attempts=0, submitted=False, lease=None,
):
    item = {
        "job_id": {"S": job},
        "tenant_id": {"S": tenant},
        "state": {"S": state},
        "attempts": {"N": str(attempts)},
        "created_at": {"N": str(created)},
        "submitted": {"BOOL": submitted},
        # We deliberately test that an AWS projection violation is
        # ignored by the public response and never transmitted.
        "s3_version": {"S": "top-secret-opaque-version-id"},
        "case_id": {"S": "private-case"},
        "object_id": {"S": "private-document"},
    }
    if lease is not None:
        item["lease_until"] = {"N": str(lease)}
    return item


class Ddb:
    def __init__(self, items=None, *, last=False):
        self.items = items if items is not None else [entry()]
        self.last = last
        self.calls = []
        self.fail = False

    def query(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("Synthetic error with private detail")
        return {
            "Items": copy.deepcopy(self.items),
            **({"LastEvaluatedKey": {"pk": {"S": "secret"}}} if self.last else {}),
        }


def test_owner_and_notary_allowed_secretariat_and_unassigned_denied():
    assert authorized_notary({"rola": "wlasciciel", "stanowisko": "sekretariat"})
    assert authorized_notary({"rola": "czlonek", "stanowisko": "notariusz"})
    for value in (None, {}, {"stanowisko": "sekretariat"},
                  {"rola": "czlonek", "stanowisko": "aplikant"},
                  "notary", {"role": "notary"}):
        assert not authorized_notary(value)


def test_read_only_query_returns_only_safe_fields_and_page_counts():
    client = Ddb([
        entry(job="abc", state="queued", created=2990),
        entry(job="def", state="preview_completed", created=2980, attempts=1),
        entry(job="ghi", state="needs_review", created=2700, attempts=3),
    ])
    result = ControlRoom(client, TENANT).recent(limit=5, now=3000)
    assert result["read_only"] is True
    assert result["mode"] == "auto" and result["can_submit"] is False
    assert result["attention_on_page"] == 1
    assert result["status_counts_on_page"] == {
        "queued": 1, "preview_completed": 1, "needs_review": 1
    }
    assert result["more_available"] is False
    assert result["jobs"][2]["attention_reason"] == "needs_review"
    assert result["jobs"][0]["attention_required"] is False
    assert set(result["jobs"][0]) == {
        "job_id", "status", "attempts", "created_at",
        "attention_required", "attention_reason", "submitted",
    }
    text = json.dumps(result)
    assert "private-case" not in text
    assert "private-document" not in text
    assert "top-secret" not in text
    assert result["snapshot_at"] == 3000
    kwargs = client.calls[0]
    assert kwargs["TableName"] == "notarai-confidential-jobs-pilot01"
    assert kwargs["IndexName"] == "TenantCreatedAtIndex"
    assert kwargs["ExpressionAttributeValues"] == {
        ":tenant": {"S": TENANT}
    }
    assert kwargs["ScanIndexForward"] is False
    assert kwargs["Limit"] == 6
    assert kwargs["ConsistentRead"] is False
    assert "Scan" not in kwargs


@pytest.mark.parametrize(("state", "created", "lease", "reason"), [
    ("queued", 100, None, "long_wait"),
    ("retryable", 100, None, "long_wait"),
    ("queue_uncertain", 2900, None, "queue_uncertain"),
    ("needs_review", 2900, None, "needs_review"),
    ("running", 2950, 2999, "expired_lease"),
    ("running", 2950, 3000, None),
    ("preview_completed", 100, None, None),
])
def test_stale_and_manual_intervention_flags(state, created, lease, reason):
    row = entry(state=state, created=created, lease=lease)
    output = ControlRoom(Ddb([row]), TENANT).recent(limit=10, now=3000)
    result = output["jobs"][0]
    assert result["attention_reason"] == reason
    assert result["attention_required"] is (reason is not None)


@pytest.mark.parametrize("changes", [
    {"tenant": "another"},
    {"state": "submitted"},
    {"state": "signed"},
    {"attempts": 4},
    {"created": 3100},
    {"submitted": True},
    {"job": "../another"},
    {"lease": 99, "state": "running"},
])
def test_invalid_rows_fail_closed(changes):
    with pytest.raises(ControlRoomRejected):
        ControlRoom(Ddb([entry(**changes)]), TENANT).recent(limit=10, now=3000)


def test_query_failure_or_wrong_page_size_denied_without_data():
    client = Ddb()
    client.fail = True
    with pytest.raises(ControlRoomRejected, match="unavailable"):
        ControlRoom(client, TENANT).recent(now=3000)
    for size in (1, 50, True, 10.0, "10"):
        with pytest.raises(ControlRoomRejected):
            ControlRoom(Ddb(), TENANT).recent(limit=size, now=3000)
    with pytest.raises(ControlRoomRejected):
        ControlRoom(Ddb(), "pilot../other").recent(now=3000)


def test_limited_recent_page_does_not_claim_global_totals():
    data = [entry(job=f"job{i}", state="queued") for i in range(11)]
    client = Ddb(data, last=True)
    result = ControlRoom(client, TENANT).recent(limit=10, now=3000)
    assert result["page_size"] == 10
    assert result["more_available"] is True
    assert result["attention_on_page"] == 10
    assert len(result["jobs"]) == 10


def configure(monkeypatch, *, principal):
    setup_tenant(monkeypatch)
    import sys
    autoryzacja = sys.modules["autoryzacja"]
    autoryzacja._osoba_w_kancelarii = lambda tenant, email: principal
    ddb = Ddb([entry(state="preview_completed", created=2000)])
    import boto3
    calls = []
    def client(service, **kwargs):
        calls.append(service)
        assert service == "dynamodb" and kwargs["region_name"] == "eu-central-1"
        return ddb
    monkeypatch.setattr(boto3, "client", client)
    return ddb, calls


def test_endpoint_notary_only_and_no_store(monkeypatch):
    client, calls = configure(monkeypatch, principal={"rola": "czlonek", "stanowisko": "notariusz"})
    response = control_room_jobs(RequestFake("limit=5"))
    assert response.headers["Cache-Control"] == "no-store"
    payload = json.loads(response.body)
    assert payload["can_submit"] is False and payload["read_only"] is True
    assert payload["jobs"][0]["submitted"] is False
    assert calls == ["dynamodb"]
    assert client.calls[0]["Limit"] == 6


@pytest.mark.parametrize("principal", [
    None, {"rola": "czlonek", "stanowisko": "aplikant"},
    {"rola": "czlonek", "stanowisko": "sekretariat"},
])
def test_endpoint_denies_non_notaries_before_aws(monkeypatch, principal):
    _, calls = configure(monkeypatch, principal=principal)
    with pytest.raises(HTTPException) as exc:
        control_room_jobs(RequestFake())
    assert exc.value.status_code == 403
    assert calls == []


@pytest.mark.parametrize("args", [
    "limit=1", "limit=21", "limit=10&limit=10",
    "tenant=another", "role=notary", "submit=true", "cursor=secret",
])
def test_endpoint_rejects_unknown_params_before_aws(monkeypatch, args):
    _, calls = configure(monkeypatch, principal={"rola": "wlasciciel"})
    with pytest.raises(HTTPException) as exc:
        control_room_jobs(RequestFake(args))
    assert exc.value.status_code == 400
    assert calls == []


def test_endpoint_rejects_other_tenant_even_for_owner(monkeypatch):
    _, calls = configure(monkeypatch, principal={"rola": "wlasciciel"})
    import os
    monkeypatch.setenv("PIECZAPP_CONFIDENTIAL_ALLOWED_TENANT", "somebodyelse")
    with pytest.raises(HTTPException) as exc:
        control_room_jobs(RequestFake())
    assert exc.value.status_code == 403
    assert calls == []


def test_endpoint_sanitizes_aws_failure(monkeypatch):
    ddb, calls = configure(monkeypatch, principal={"rola": "wlasciciel"})
    ddb.fail = True
    with pytest.raises(HTTPException) as exc:
        control_room_jobs(RequestFake())
    assert exc.value.status_code == 503
    assert "private detail" not in str(exc.value.detail)


def test_cfn_index_is_tenant_scoped_projected_and_no_global_list():
    t = template("notarai-confidential-job-ledger.yaml")
    table = t["Resources"]["PreviewJobs"]["Properties"]
    idx = table["GlobalSecondaryIndexes"]
    assert len(idx) == 1
    assert idx[0]["IndexName"] == "TenantCreatedAtIndex"
    assert idx[0]["KeySchema"] == [
        {"AttributeName": "tenant_id", "KeyType": "HASH"},
        {"AttributeName": "created_at", "KeyType": "RANGE"},
    ]
    assert idx[0]["Projection"]["ProjectionType"] == "INCLUDE"
    assert "s3_version" not in idx[0]["Projection"]["NonKeyAttributes"]
    assert "case_id" not in idx[0]["Projection"]["NonKeyAttributes"]
    assert "object_id" not in idx[0]["Projection"]["NonKeyAttributes"]
    assert table["PointInTimeRecoverySpecification"]["PointInTimeRecoveryEnabled"]
