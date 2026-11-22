"""No AWS access, no client data, no real browser session."""
import json

import pytest

from confidential.worker import _parse_message


def test_sqs_message_scoped_to_its_tenant():
    good = {"tenant_id": "demo_tenant", "case_id": "case1", "object_id": "scan1", "job_id": "job1", "s3_version": "v000001"}
    assert _parse_message(json.dumps(good), "demo_tenant") == ("case1", "scan1", "job1", "v000001")
    with pytest.raises(ValueError):
        _parse_message(json.dumps(good), "other_tenant")
    with pytest.raises(ValueError):
        _parse_message(json.dumps({**good, "case_id": "../secret"}), "demo_tenant")
    with pytest.raises(ValueError):
        _parse_message(json.dumps({**good, "submit": True}), "demo_tenant")
    with pytest.raises(ValueError):
        _parse_message(json.dumps({**good, "s3_version": "null"}), "demo_tenant")
    with pytest.raises(ValueError):
        _parse_message(json.dumps({k: v for k, v in good.items()
                                  if k != "s3_version"}), "demo_tenant")


def test_no_hardware_means_no_work(monkeypatch):
    from confidential.worker import _config
    monkeypatch.setenv("NOTARAI_CONFIDENTIAL_REQUIRED", "1")
    monkeypatch.setattr("confidential.worker.os.path.exists", lambda path: False)
    with pytest.raises(RuntimeError, match="hardware attestation required"):
        _config()


def test_decrypt_reads_only_exact_s3_version(monkeypatch):
    from confidential.worker import _load_decrypted_form
    import confidential.worker as worker
    import confidential.nitro_unwrapper as nitro

    seen = []
    class Body:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self, limit):
            return b'{"fictional":"ciphertext"}'
    class S3:
        def get_object(self, **kwargs):
            seen.append(kwargs)
            return {"Body": Body()}
    class FakeEnvelope:
        version = 2
        document_version = "a" * 32
        public_key_sha256 = "A" * 43 + "="
        tenant_id = "pilot01"
        case_id = "case01"
        object_id = "scan01"
        kms_key_arn = "arn:aws:kms:eu-central-1:111122223333:key/pilot"
        def open_inside_attested_task(self, unwrap):
            return b'{"form_id":"local-demo","fields":{"name":"FAKE","reference":"X"}}'

    monkeypatch.setattr(worker.Envelope, "parse", lambda contents: FakeEnvelope())
    checked = []
    class FakeRegistry:
        def require_guest(self, **kwargs):
            checked.append(kwargs)
    registry = FakeRegistry()
    origin_checks = []
    monkeypatch.setattr(worker, "require_origin_receipt",
                        lambda s3, **scope: origin_checks.append(scope))
    monkeypatch.setattr(nitro, "NitroKMSUnwrapper", lambda kms, key: object())
    fields = _load_decrypted_form(
        S3(), object(), "fixture-bucket", "pilot01",
        "case01", "scan01", FakeEnvelope.kms_key_arn,
        "versionABC123", registry,
    )
    assert checked[0]["s3_version"] == "versionABC123"
    assert len(origin_checks) == 1
    assert origin_checks[0]["s3_version"] == "versionABC123"
    assert origin_checks[0]["public_key_sha256"] == FakeEnvelope.public_key_sha256
    assert checked[0]["document_version"] == "a" * 32
    assert fields["name"] == "FAKE"
    assert seen == [{
        "Bucket": "fixture-bucket",
        "Key": "kancelarie/pilot01/confidential/case01/scan01.json",
        "VersionId": "versionABC123",
    }]
    seen.clear()
    with pytest.raises(ValueError):
        _load_decrypted_form(
            S3(), object(), "fixture-bucket", "pilot01", "case01",
            "scan01", FakeEnvelope.kms_key_arn, "null", registry,
        )
    assert seen == []
