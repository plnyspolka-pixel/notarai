"""SEC-10: execute the real worker lifecycle with fake AWS and fake browser.

Purely synthetic markers, no actual AWS service calls and no real case data.
The os-level stdio suppression is separately checked in Linux CI smoke.
"""
from __future__ import annotations

import json

import pytest

from confidential.job_ledger import Claim
from confidential import worker


TENANT = "pilot01"
KEY = "arn:aws:kms:eu-central-1:111122223333:key/synthetic-key"
DOC_MARKER = "NOTARAI-P75-FAKE-DOCUMENT-ONLY"
KEY_MARKER = "NOTARAI-P75-FAKE-DEK-ONLY"


@pytest.mark.parametrize("scenario", [
    "success", "exception", "retry", "browser_crash", "network_error", "timeout",
])
def test_real_preview_worker_does_not_persist_plaintext_on_six_paths(
    monkeypatch, capfd, scenario
):
    events = []
    sqs_deletes = []
    s3_writes = []
    transitions = []
    message = {
        "tenant_id": TENANT, "case_id": "case01", "object_id": "object01",
        "job_id": "job01", "s3_version": "version01",
    }

    class FakeSQS:
        def receive_message(self, **kwargs):
            assert kwargs["MaxNumberOfMessages"] == 1
            events.append("sqs.receive")
            return {"Messages": [{
                "Body": json.dumps(message),
                "ReceiptHandle": "fake-receipt",
            }]}
        def delete_message(self, **kwargs):
            events.append("sqs.delete")
            sqs_deletes.append(kwargs)

    class FakeS3:
        def put_object(self, **kwargs):
            events.append("s3.put")
            s3_writes.append(kwargs)
            assert kwargs["ContentType"] == "application/json"
            assert kwargs["ServerSideEncryption"] == "AES256"

    class FakeLedger:
        def __init__(self, db, *, tenant):
            assert tenant == TENANT
        def claim(self, **kwargs):
            events.append("ledger.claim")
            assert kwargs["s3_version"] == "version01"
            return Claim("claimed", token="a" * 32, attempts=1)
        def complete(self, **kwargs):
            events.append("ledger.complete")
            transitions.append("complete")
        def fail(self, **kwargs):
            events.append("ledger.fail")
            transitions.append("fail")

    sqs, s3 = FakeSQS(), FakeS3()
    fake_kms = object()
    fake_ddb = object()

    class FakeSession:
        def client(self, name):
            assert name in ("sqs", "s3", "kms", "dynamodb")
            return {
                "sqs": sqs, "s3": s3, "kms": fake_kms, "dynamodb": fake_ddb,
            }[name]

    def suppress():
        events.append("stdio.suppressed")

    values_holder = []
    def decrypt(*args):
        assert events.index("stdio.suppressed") < len(events)
        events.append("kms.decrypt.synthetic")
        if scenario == "retry":
            raise ConnectionError("private " + DOC_MARKER + KEY_MARKER)
        values = {"name": DOC_MARKER, "reference": KEY_MARKER}
        values_holder.append(values)
        return values

    async def browser(job_id, values):
        events.append("browser.preview")
        assert job_id == "job01"
        assert values["name"] == DOC_MARKER
        failures = {
            "exception": RuntimeError,
            "browser_crash": BrokenPipeError,
            "network_error": OSError,
            "timeout": TimeoutError,
        }
        if scenario in failures:
            raise failures[scenario]("private " + DOC_MARKER + KEY_MARKER)

    monkeypatch.setattr(worker, "PreviewJobLedger", FakeLedger)
    monkeypatch.setattr(worker, "silence_guest_stdio", suppress)
    monkeypatch.setattr(worker, "_load_decrypted_form", decrypt)
    monkeypatch.setattr(worker, "_prepare_fictional_form", browser)

    if scenario == "success":
        assert worker._process_one(
            FakeSession(), TENANT, "synthetic-bucket", "synthetic-queue", KEY
        ) == 0
        assert transitions == ["complete"]
        assert len(sqs_deletes) == len(s3_writes) == 1
        body = json.loads(s3_writes[0]["Body"])
        assert body == {
            "version": 1, "job_id": "job01", "status": "preview_completed",
            "fields_filled": 2, "submitted": False,
        }
        assert events.index("s3.put") < events.index("ledger.complete")
        assert events.index("ledger.complete") < events.index("sqs.delete")
    else:
        with pytest.raises((ConnectionError, RuntimeError,
                            BrokenPipeError, OSError, TimeoutError)):
            worker._process_one(
                FakeSession(), TENANT, "synthetic-bucket", "synthetic-queue", KEY
            )
        assert transitions == ["fail"]
        assert not sqs_deletes and not s3_writes
    assert events.index("stdio.suppressed") < events.index("kms.decrypt.synthetic")
    assert all(not item for item in values_holder)
    stdout, stderr = capfd.readouterr()
    assert DOC_MARKER not in stdout + stderr
    assert KEY_MARKER not in stdout + stderr
    assert all(
        DOC_MARKER.encode() not in entry["Body"]
        and KEY_MARKER.encode() not in entry["Body"]
        for entry in s3_writes
    )


def test_worker_never_decrypts_when_untrusted_task_has_no_claim(monkeypatch):
    events = []
    class FakeSQS:
        def receive_message(self, **kwargs):
            return {"Messages": [{
                "Body": json.dumps({
                    "tenant_id": TENANT, "case_id": "c1", "object_id": "o1",
                    "job_id": "j1", "s3_version": "version01",
                }),
                "ReceiptHandle": "fake",
            }]}
        def delete_message(self, **kwargs):
            raise AssertionError("must not delete unowned job")

    class FakeLedger:
        def __init__(self, db, *, tenant):
            pass
        def claim(self, **kwargs):
            return Claim("needs_review")
    class Session:
        def client(self, service):
            if service == "sqs":
                return FakeSQS()
            if service == "dynamodb":
                return object()
            raise AssertionError("unclaimed task must not touch " + service)

    monkeypatch.setattr(worker, "PreviewJobLedger", FakeLedger)
    monkeypatch.setattr(worker, "silence_guest_stdio",
                        lambda: events.append("silence"))
    monkeypatch.setattr(worker, "_load_decrypted_form",
                        lambda *args: (_ for _ in ()).throw(AssertionError("decrypt")))
    assert worker._process_one(Session(), TENANT, "bucket", "queue", KEY) == 1
    assert events == []
