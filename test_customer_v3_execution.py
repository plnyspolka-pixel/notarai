"""Real crypto, synthetic NSM and fake AWS: customer v3 guest end-to-end.

No claim of real AWS hardware attestation, no Bedrock, no external forms.
"""
import asyncio
import io
import json
import copy

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa

from confidential.customer_origin import sign_customer_origin
from confidential.customer_release import seal_document, issue_job_release
from confidential.customer_guest_v3 import CustomerGuestSession
from confidential.customer_v3_execution import process_preview_once, CustomerPreviewDenied
from confidential.customer_v3_transport import CustomerCiphertextTransport
from test_customer_v3_transport import FakeS3, FakeSqs, FakeDdb as DocumentDdb
from test_customer_release_ledger import MemoryDdb


class HybridDdb(MemoryDdb):
    def _guard(self):
        pass

    def update_item(self, **kw):
        pk = kw["Key"]["pk"]["S"]
        if pk.startswith("DOC#"):
            return DocumentDdb.update_item(self, **kw)
        return super().update_item(**kw)


class VersionedS3(FakeS3):
    def get_object(self, **kw):
        row = self.items[kw["Key"]]
        if "VersionId" in kw and kw["VersionId"] != row["version"]:
            raise ValueError("synthetic wrong version")
        return {"Body": io.BytesIO(row["bytes"])}

    def put_object(self, **kw):
        if "/confidential-results/" in kw["Key"]:
            assert "IfNoneMatch" not in kw
            assert kw["ServerSideEncryption"] == "AES256"
            self.items[kw["Key"]] = {"version":"vresult", "bytes":kw["Body"]}
            return {"VersionId":"vresult"}
        return super().put_object(**kw)


def create_case(monkeypatch, *, wrong_form=False):
    # Synthetic NSM returns a placeholder only: actual COSE/X509 verification
    # is independently covered by test_customer_attestation.py.
    monkeypatch.setattr("confidential.customer_guest_v3.os.path.exists", lambda _: True)
    monkeypatch.setattr("confidential.nsm_recipient._request_attestation",
                        lambda public_key, **_: b"SYNTHETIC-NSM-NOT-A-REAL-ATTESTATION")
    owner = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    owner_private = owner.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption())
    owner_public = owner.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    issuer = ed25519.Ed25519PrivateKey.generate()
    issuer_private = issuer.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption())
    issuer_public = issuer.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    payload = {"form_id":"unknown-form" if wrong_form else "local-demo",
               "fields":{"name":"FAKE-SECRET-CANARY","reference":"abc01"}}
    env = seal_document(json.dumps(payload).encode(), owner_public,
                        tenant_id="pilot01", case_id="case01",
                        object_id="object01", document_version="a"*32)
    ddb, s3, sqs = HybridDdb(), VersionedS3(), FakeSqs()
    t = CustomerCiphertextTransport(
        s3=s3, sqs=sqs, ddb=ddb, tenant="pilot01",
        bucket="synthetic-three-zero",
        queue_url="https://sqs.eu-central-1.amazonaws.com/111122223333/notarai-confidential-pilot01.fifo",
        account="111122223333")
    stored = t.admit_ciphertext(env)
    receipt, signature = sign_customer_origin(
        env, s3_version=stored["s3_version"], issuer_id="notary01",
        expires_at=2000, trusted_client_signing_private_pem=issuer_private)
    t.enqueue_signed_preview(
        env, s3_version=stored["s3_version"], job_id="job01",
        ciphertext_sha256=stored["ciphertext_sha256"],
        origin_receipt=receipt, origin_signature=signature,
        pinned_notary_signing_public_raw=issuer_public,
        expected_issuer_id="notary01", now=1000)
    guest = CustomerGuestSession()
    guest.attest(env, job_id="job01", nonce=b"N"*32)
    guest_public = guest._private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    grant = issue_job_release(
        env, owner_private, guest_public,
        job_id="job01", issued_at=1000, expires_at=1800)
    args = {
        "s3":s3, "ddb":ddb, "guest":guest, "tenant":"pilot01",
        "bucket":"synthetic-three-zero", "case_id":"case01",
        "object_id":"object01", "job_id":"job01",
        "s3_version":stored["s3_version"], "grant":grant,
        "expected_issuer_id":"notary01",
        "pinned_notary_signing_public_raw":issuer_public, "now":1001,
    }
    return args, ddb, s3, sqs


def test_guest_crypto_preview_once_then_durable_replay_denied(monkeypatch):
    args, ddb, s3, sqs = create_case(monkeypatch)
    seen = []
    async def local_preview(job, values):
        seen.append((job, dict(values)))
    monkeypatch.setattr("confidential.worker._prepare_fictional_form", local_preview)
    result = asyncio.run(process_preview_once(**args))
    assert result["submitted"] is False
    assert result["status"] == "preview_completed"
    assert seen == [("job01", {"name":"FAKE-SECRET-CANARY", "reference":"abc01"})]
    assert "release_consumed_sha256" in ddb.rows["JOB#pilot01#job01"]
    assert ddb.rows["JOB#pilot01#job01"]["state"]["S"] == "preview_completed"
    with pytest.raises(CustomerPreviewDenied):
        asyncio.run(process_preview_once(**args))
    assert len(seen) == 1
    for row in s3.items.values():
        assert b"FAKE-SECRET-CANARY" not in row["bytes"]
    assert len(sqs.messages) == 1


def test_tampered_origin_denies_after_burn_and_marks_needs_review(monkeypatch):
    args, ddb, s3, _ = create_case(monkeypatch)
    key = "kancelarie/pilot01/confidential/case01/object01.json.origin.v3.json"
    b = json.loads(s3.items[key]["bytes"])
    b["receipt"]["issuer_id"] = "attacker"
    s3.items[key]["bytes"] = json.dumps(b).encode()
    with pytest.raises(CustomerPreviewDenied):
        asyncio.run(process_preview_once(**args))
    job = ddb.rows["JOB#pilot01#job01"]
    assert job["state"]["S"] == "needs_review"
    assert "release_consumed_sha256" in job
    with pytest.raises(CustomerPreviewDenied):
        asyncio.run(process_preview_once(**args))


def test_wrong_s3_version_never_releases_key(monkeypatch):
    args, ddb, s3, _ = create_case(monkeypatch)
    args["s3_version"] = "wrong-version"
    with pytest.raises(Exception):
        asyncio.run(process_preview_once(**args))
    assert "release_consumed_sha256" not in ddb.rows["JOB#pilot01#job01"]


def test_invalid_form_after_decrypt_marks_needs_review(monkeypatch):
    args, ddb, s3, _ = create_case(monkeypatch, wrong_form=True)
    with pytest.raises(CustomerPreviewDenied):
        asyncio.run(process_preview_once(**args))
    job = ddb.rows["JOB#pilot01#job01"]
    assert job["state"]["S"] == "needs_review"
    assert "release_consumed_sha256" in job
