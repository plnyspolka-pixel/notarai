"""Synthetic DynamoDB job-lifecycle tests: no AWS resources or real documents."""
import asyncio
import copy
import json

import pytest

from confidential.job_ledger import JobRejected, PreviewJobLedger
from confidential.worker import _process_one


class ConditionalError(Exception):
    response = {"Error": {"Code": "ConditionalCheckFailedException"}}


class FakeDdb:
    def __init__(self):
        self.rows = {}
        self.fail_next_write = False

    def _guard(self):
        if self.fail_next_write:
            self.fail_next_write = False
            raise RuntimeError("synthetic network failure")

    def put_item(self, **kwargs):
        self._guard()
        key = kwargs["Item"]["pk"]["S"]
        if key in self.rows:
            raise ConditionalError()
        assert kwargs["ConditionExpression"] == "attribute_not_exists(pk)"
        self.rows[key] = copy.deepcopy(kwargs["Item"])

    def get_item(self, **kwargs):
        assert kwargs["ConsistentRead"] is True
        return {"Item": copy.deepcopy(self.rows[kwargs["Key"]["pk"]["S"]])} \
            if kwargs["Key"]["pk"]["S"] in self.rows else {}

    def update_item(self, **kwargs):
        self._guard()
        key = kwargs["Key"]["pk"]["S"]
        row = self.rows.get(key)
        if row is None:
            raise ConditionalError()
        values = kwargs["ExpressionAttributeValues"]
        cmd = kwargs["UpdateExpression"]
        if "ADD attempts" in cmd:
            assert kwargs["ReturnValues"] == "ALL_NEW"
            state = row["state"]["S"]
            attempts = int(row["attempts"]["N"])
            ts = int(values[":now"]["N"])
            allowed = (
                row["tenant_id"]["S"] == values[":tenant"]["S"]
                and row["job_id"]["S"] == values[":job"]["S"]
                and row["case_id"]["S"] == values[":case"]["S"]
                and row["object_id"]["S"] == values[":object"]["S"]
                and row["submitted"]["BOOL"] is False
                and attempts < int(values[":limit"]["N"])
                and (state in ("queued", "retryable") or
                     (state == "running" and
                      int(row["lease_until"]["N"]) < ts))
            )
            if not allowed:
                raise ConditionalError()
            row["state"] = values[":running"]
            row["task_token"] = values[":token"]
            row["lease_until"] = values[":lease"]
            row["updated_at"] = values[":now"]
            row["attempts"] = {"N": str(attempts + 1)}
            return {"Attributes": copy.deepcopy(row)}
        if ":uncertain" in values:
            if row["state"]["S"] != "queued":
                raise ConditionalError()
            row["state"] = values[":uncertain"]
            return {}
        if ":next" in values:
            if row["state"]["S"] != "running" or (
                row.get("task_token") != values[":token"]
            ):
                raise ConditionalError()
            row["state"] = values[":next"]
            row.pop("task_token", None)
            return {}
        raise AssertionError("unexpected DynamoDB mutation")


def make():
    client = FakeDdb()
    ledger = PreviewJobLedger(client, tenant="pilot01")
    ledger.create(
        job_id="abc012", case_id="case01", object_id="object01", now=100
    )
    return client, ledger


def test_create_idempotency_and_tenant_scoping():
    client, ledger = make()
    status = ledger.status("abc012")
    assert status == {
        "job_id": "abc012", "status": "queued", "attempts": 0,
        "submitted": False, "mode": "auto", "can_submit": False,
    }
    with pytest.raises(JobRejected):
        ledger.create(job_id="abc012", case_id="case01",
                      object_id="object01", now=101)
    with pytest.raises(JobRejected):
        ledger.claim(job_id="abc012", case_id="wrong",
                     object_id="object01", now=101, token="a" * 32)
    other = PreviewJobLedger(client, tenant="other")
    with pytest.raises(JobRejected):
        other.status("abc012")


def test_claim_release_replay_and_completion_are_conditional():
    _, ledger = make()
    first = ledger.claim(
        job_id="abc012", case_id="case01", object_id="object01",
        now=101, token="a" * 32,
    )
    assert first.state == "claimed" and first.attempts == 1
    held = ledger.claim(
        job_id="abc012", case_id="case01", object_id="object01",
        now=102, token="b" * 32,
    )
    assert held.state == "busy"
    with pytest.raises(JobRejected):
        ledger.complete(job_id="abc012", token="b" * 32)
    ledger.complete(job_id="abc012", token=first.token)
    complete = ledger.claim(
        job_id="abc012", case_id="case01", object_id="object01",
        now=1500, token="c" * 32,
    )
    assert complete.state == "completed"
    assert ledger.status("abc012")["status"] == "preview_completed"


def test_expired_lease_can_retry_preview_only_not_a_submission():
    _, ledger = make()
    claim = ledger.claim(
        job_id="abc012", case_id="case01", object_id="object01",
        now=100, token="a" * 32,
    )
    pending = ledger.claim(
        job_id="abc012", case_id="case01", object_id="object01",
        now=1000, token="b" * 32,
    )
    assert pending.state == "busy"  # equality is not enough to steal a lease
    again = ledger.claim(
        job_id="abc012", case_id="case01", object_id="object01",
        now=1001, token="b" * 32,
    )
    assert again.state == "claimed" and again.attempts == 2
    with pytest.raises(JobRejected):
        ledger.complete(job_id="abc012", token=claim.token)
    ledger.fail(job_id="abc012", token=again.token, attempts=again.attempts)
    assert ledger.status("abc012")["status"] == "retryable"
    third = ledger.claim(
        job_id="abc012", case_id="case01", object_id="object01",
        now=1002, token="c" * 32,
    )
    assert third.state == "claimed" and third.attempts == 3
    ledger.fail(job_id="abc012", token=third.token, attempts=3)
    assert ledger.status("abc012")["status"] == "needs_review"
    assert ledger.claim(
        job_id="abc012", case_id="case01", object_id="object01",
        now=10000, token="d" * 32,
    ).state == "needs_review"


def test_uncertain_sqs_publish_fails_closed_with_no_worker_claim():
    client, ledger = make()
    ledger.mark_queue_uncertain("abc012")
    assert ledger.status("abc012")["status"] == "queue_uncertain"
    assert ledger.claim(
        job_id="abc012", case_id="case01", object_id="object01",
        now=101, token="a" * 32,
    ).state == "needs_review"
    ledger.mark_queue_uncertain("abc012")  # never reset back to queued
    assert ledger.status("abc012")["status"] == "queue_uncertain"
    client.fail_next_write = True
    with pytest.raises(JobRejected):
        ledger.create(job_id="another", case_id="case01",
                      object_id="object01", now=102)


class FakeQueue:
    def __init__(self, message):
        self.message = message
        self.deleted = False

    def receive_message(self, **kwargs):
        assert kwargs["VisibilityTimeout"] == 900
        return {"Messages": [self.message]}

    def delete_message(self, **kwargs):
        assert kwargs["ReceiptHandle"] == "fictional"
        self.deleted = True


class FakeS3:
    def __init__(self):
        self.markers = []

    def put_object(self, **kwargs):
        parsed = json.loads(kwargs["Body"])
        assert parsed["submitted"] is False
        assert parsed["status"] == "preview_completed"
        self.markers.append(kwargs)


class FakeSession:
    def __init__(self, ddb, queue, s3):
        self.clients = {
            "dynamodb": ddb, "sqs": queue, "s3": s3, "kms": object()
        }

    def client(self, which):
        return self.clients[which]


def test_worker_claims_before_decrypt_then_completes_and_deletes(monkeypatch):
    client, ledger = make()
    queue = FakeQueue({
        "Body": json.dumps({
            "tenant_id": "pilot01", "case_id": "case01",
            "object_id": "object01", "job_id": "abc012",
        }),
        "ReceiptHandle": "fictional",
    })
    session = FakeSession(client, queue, FakeS3())
    inspected = []

    def decrypt(*args):
        inspected.append(("decrypt", ledger.status("abc012")["status"]))
        return {"name": "FICTIONAL", "reference": "SIMULATED"}

    async def prepare(*args):
        inspected.append(("browser", ledger.status("abc012")["status"]))

    monkeypatch.setattr("confidential.worker._load_decrypted_form", decrypt)
    monkeypatch.setattr("confidential.worker._prepare_fictional_form", prepare)
    assert _process_one(
        session, "pilot01", "fictional-bucket", "queue-url", "kms-arn"
    ) == 0
    assert inspected == [("decrypt", "running"), ("browser", "running")]
    assert queue.deleted and len(session.clients["s3"].markers) == 1
    assert ledger.status("abc012")["status"] == "preview_completed"
    queue.deleted = False
    inspected.clear()
    # Duplicate SQS delivery: only acknowledge; do not decrypt again.
    assert _process_one(
        session, "pilot01", "fictional-bucket", "queue-url", "kms-arn"
    ) == 0
    assert queue.deleted and inspected == []
    assert len(session.clients["s3"].markers) == 1


def test_worker_fails_before_decryption_if_job_is_not_registered(monkeypatch):
    client = FakeDdb()
    queue = FakeQueue({
        "Body": json.dumps({
            "tenant_id": "pilot01", "case_id": "case01",
            "object_id": "object01", "job_id": "abc012",
        }), "ReceiptHandle": "fictional",
    })
    session = FakeSession(client, queue, FakeS3())
    calls = []
    monkeypatch.setattr(
        "confidential.worker._load_decrypted_form",
        lambda *args: calls.append("decrypt")
    )
    with pytest.raises(JobRejected):
        _process_one(session, "pilot01", "bucket", "queue", "key")
    assert not calls and not queue.deleted


def test_worker_failure_keeps_sqs_unacknowledged_for_bounded_retry(monkeypatch):
    client, ledger = make()
    queue = FakeQueue({
        "Body": json.dumps({
            "tenant_id": "pilot01", "case_id": "case01",
            "object_id": "object01", "job_id": "abc012",
        }), "ReceiptHandle": "fictional",
    })
    session = FakeSession(client, queue, FakeS3())
    def failing_decrypt(*args):
        raise RuntimeError("synthetic-only")
    monkeypatch.setattr("confidential.worker._load_decrypted_form", failing_decrypt)
    with pytest.raises(RuntimeError):
        _process_one(session, "pilot01", "bucket", "queue", "key")
    assert ledger.status("abc012")["status"] == "retryable"
    assert not queue.deleted
