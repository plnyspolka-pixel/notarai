"""SEC-03 end-to-end synthetic staged pilot; no AWS calls, no PII."""
import base64
import hashlib
import io
import json

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, ed25519

import scripts.confidential_pilot_origin_queue as stage2
from scripts.confidential_pilot_fixture import fixture_envelope
from scripts.sign_confidential_origin_receipt import sign_origin_receipt

ARN = "arn:aws:kms:eu-central-1:111122223333:key/fixture"
S3_VERSION = "v000001"
QUEUE = "https://sqs.eu-central-1.amazonaws.com/111122223333/notarai-confidential-pilot01.fifo"


@pytest.fixture
def synthetic_stage(tmp_path):
    kms = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    der = kms.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    envelope = fixture_envelope(
        tenant="pilot01", kms_arn=ARN, public_der=der,
    )
    blob = json.dumps(envelope, separators=(",", ":")).encode("ascii")
    assert b"FICTIONAL TEST PERSON" not in blob
    cipherfile = tmp_path / "synthetic.encrypted.json"
    cipherfile.write_bytes(blob)
    issuer = ed25519.Ed25519PrivateKey.generate()
    private = issuer.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    issuer_pem = issuer.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    issuer_der = issuer.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    signed = tmp_path / "synthetic.origin.json"
    sign_origin_receipt(
        ciphertext_file=cipherfile, output_file=signed,
        expected_sha256=hashlib.sha256(blob).hexdigest(),
        verified_s3_version=S3_VERSION,
        issuer_id="synthetic_issuer",
        expires_at=2000000000, issuer_private_key_pem=private,
        approved_tenant="pilot01", approved_kms_key_arn=ARN,
        approved_key_pin=envelope["public_key_sha256"],
    )
    return dict(
        ciphertext_file=cipherfile, origin_receipt_file=signed,
        trusted_issuer_public_key_pem=issuer_pem,
        trusted_issuer_id="synthetic_issuer",
        independent_issuer_spki_sha256=hashlib.sha256(issuer_der).hexdigest(),
        s3_version=S3_VERSION, kms_key_arn=ARN, tenant="pilot01",
        bucket="fictional-bucket", queue_url=QUEUE, now=1900000000,
        wire=blob,
    )


def test_only_signed_ciphertext_bytes_can_be_queued(monkeypatch, synthetic_stage):
    checks = []
    args = {k: v for k, v in synthetic_stage.items() if k != "wire"}
    class S3:
        def get_object(self, **kw):
            checks.append("s3-read")
            assert kw["VersionId"] == S3_VERSION
            return {"Body": io.BytesIO(synthetic_stage["wire"]),
                    "VersionId": S3_VERSION}
        def put_object(self, **kw):
            checks.append("origin-write")
            assert kw["IfNoneMatch"] == "*"
            assert kw["Key"].endswith(".origin.json")
            assert b"signature_b64" in kw["Body"]
    class SQS:
        def send_message(self, **kw):
            checks.append("queue")
            msg = json.loads(kw["MessageBody"])
            assert set(msg) == {
                "tenant_id", "case_id", "object_id", "job_id", "s3_version",
            }
            assert msg["s3_version"] == S3_VERSION
            assert kw["MessageGroupId"] == "pilot01"
    class Registry:
        def __init__(self, *a, **kw):
            pass
        def require_stored(self, **kw):
            checks.append("ledger-verify")
            assert kw["ciphertext_sha256"] == hashlib.sha256(
                synthetic_stage["wire"]
            ).hexdigest()
        def claim_preview(self, **kw):
            checks.append("ledger-claim")
    class Ledger:
        def __init__(self, *a, **kw):
            pass
        def create(self, **kw):
            checks.append("job-create")
        def mark_queue_uncertain(self, job_id):
            checks.append("queue-uncertain")
    monkeypatch.setattr(stage2, "DocumentVersionRegistry", Registry)
    monkeypatch.setattr(stage2, "PreviewJobLedger", Ledger)
    job = stage2.enqueue_signed_synthetic(
        **args, s3=S3(), sqs=SQS(), ddb=object(), new_job_id=lambda: "a"*32,
    )
    assert job == "a"*32
    assert checks == [
        "s3-read", "ledger-verify", "origin-write",
        "ledger-claim", "job-create", "queue",
    ]


def test_pilot_never_sends_queue_for_invalid_signature_or_s3_bytes(
    monkeypatch, synthetic_stage, tmp_path,
):
    counts = {"s3reads": 0, "writes": 0, "queue": 0}
    class S3:
        corrupt = False
        def get_object(self, **kw):
            counts["s3reads"] += 1
            content = synthetic_stage["wire"] + b"tamper" if self.corrupt else synthetic_stage["wire"]
            return {"Body": io.BytesIO(content), "VersionId": S3_VERSION}
        def put_object(self, **kw):
            counts["writes"] += 1
    class SQS:
        def send_message(self, **kw):
            counts["queue"] += 1
    args = {k: v for k, v in synthetic_stage.items() if k != "wire"}
    bad = json.loads(synthetic_stage["origin_receipt_file"].read_bytes())
    bad["signature_b64"] = base64.b64encode(b"z"*64).decode("ascii")
    path = tmp_path / "invalid.origin.json"
    path.write_text(json.dumps(bad))
    with pytest.raises(Exception):
        stage2.enqueue_signed_synthetic(
            **{**args, "origin_receipt_file": path},
            s3=S3(), ddb=object(), sqs=SQS(),
        )
    assert counts == {"s3reads": 0, "writes": 0, "queue": 0}
    corrupt_s3 = S3()
    corrupt_s3.corrupt = True
    with pytest.raises(ValueError, match="differ"):
        stage2.enqueue_signed_synthetic(
            **args, s3=corrupt_s3, ddb=object(), sqs=SQS(),
        )
    assert counts["s3reads"] == 1
    assert counts["writes"] == counts["queue"] == 0
    with pytest.raises(ValueError, match="not independently pinned"):
        stage2.enqueue_signed_synthetic(
            **{**args, "independent_issuer_spki_sha256": "f"*64},
            s3=S3(), ddb=object(), sqs=SQS(),
        )
    assert counts["writes"] == counts["queue"] == 0
