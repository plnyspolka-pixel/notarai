"""SEC-03 synthetic-only offline acceptance tests; never use client documents."""
import asyncio
import base64
import copy
import hashlib
import json
import logging
import secrets
import sys
from types import SimpleNamespace

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa, ed25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException

from confidential.envelope import Envelope, InvalidEnvelope
from confidential.client_release import (
    UntrustedClientRelease, canonical_release_bytes, verify_client_release,
)
from confidential import router

ARN = "arn:aws:kms:eu-central-1:111122223333:key/fictional"
PLAINTEXT = b"FICTIONAL TEST DOCUMENT - NOT REAL NOTARIAL DATA"


@pytest.fixture
def keys():
    private = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    public = private.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    pin = base64.b64encode(hashlib.sha256(public).digest()).decode("ascii")
    return private, pin


def envelope(keys, *, tenant="pilot01", case="case01", object_id="scan01"):
    private, pin = keys
    dek, nonce = secrets.token_bytes(32), secrets.token_bytes(12)
    version = secrets.token_hex(16)
    aad = ("notarai-v2|" + tenant + "|" + case + "|" + object_id +
           "|" + version + "|" + ARN + "|" + pin).encode("ascii")
    wrapped = private.public_key().encrypt(
        dek, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),
                          algorithm=hashes.SHA256(), label=None),
    )
    payload = {
        "version": 2, "algorithm": "AES-256-GCM+RSA-OAEP-SHA256",
        "tenant_id": tenant, "case_id": case, "object_id": object_id,
        "document_version": version, "public_key_sha256": pin,
        "kms_key_arn": ARN,
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "wrapped_dek": base64.b64encode(wrapped).decode("ascii"),
        "ciphertext": base64.b64encode(
            AESGCM(dek).encrypt(nonce, PLAINTEXT, aad)
        ).decode("ascii"),
    }
    return payload, dek


class GuestForTests:
    """Local RSA fixture, NOT a genuine Nitro recipient."""
    def __init__(self, key):
        self.key = key
    def unwrap(self, wrapped, arn):
        # For tamper tests a changed KMS ARN must reach AEAD validation;
        # the real Nitro KMS unwrapper independently rejects the wrong ARN.
        return self.key.decrypt(wrapped, padding.OAEP(
            mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None
        ))


def test_v2_aead_and_unique_versions(keys):
    a, dek1 = envelope(keys)
    b, dek2 = envelope(keys)
    assert a["document_version"] != b["document_version"]
    assert a["nonce"] != b["nonce"]
    assert dek1 != dek2
    guest = GuestForTests(keys[0])
    assert Envelope.parse(a).open_inside_attested_task(guest) == PLAINTEXT
    assert Envelope.parse(b).open_inside_attested_task(guest) == PLAINTEXT
    assert Envelope.parse(a).associated_data().startswith(b"notarai-v2|pilot01|")


@pytest.mark.parametrize("field,replacement", [
    ("tenant_id", "pilot02"), ("object_id", "scan02"),
    ("case_id", "case02"), ("document_version", "a" * 32),
    ("public_key_sha256", "A" * 43 + "="),
    ("kms_key_arn", "arn:aws:kms:eu-central-1:111122223333:key/alternate"),
])
def test_wrong_aad_is_rejected(keys, field, replacement):
    payload, _ = envelope(keys)
    payload[field] = replacement
    with pytest.raises(InvalidEnvelope, match="authentication"):
        Envelope.parse(payload).open_inside_attested_task(GuestForTests(keys[0]))


def test_modified_tag_is_rejected(keys):
    payload, _ = envelope(keys)
    blob = bytearray(base64.b64decode(payload["ciphertext"]))
    blob[-1] ^= 0x01
    payload["ciphertext"] = base64.b64encode(blob).decode("ascii")
    with pytest.raises(InvalidEnvelope, match="authentication"):
        Envelope.parse(payload).open_inside_attested_task(GuestForTests(keys[0]))


def test_v2_rejects_invalid_or_downgraded_fields(keys):
    payload, _ = envelope(keys)
    for bad in (
        {**payload, "version": 1},
        {**payload, "version": True},
        {**payload, "document_version": "not-random"},
        {**payload, "extra": "hidden data"},
        {k: v for k, v in payload.items() if k != "public_key_sha256"},
    ):
        with pytest.raises(InvalidEnvelope):
            Envelope.parse(bad)


class FakeDocumentDdb:
    def __init__(self):
        self.rows = {}
    def put_item(self, **kw):
        item = kw["Item"]
        pk = item["pk"]["S"]
        if pk in self.rows or kw["ConditionExpression"] != "attribute_not_exists(pk)":
            raise RuntimeError("duplicate immutable document identity")
        self.rows[pk] = copy.deepcopy(item)
    def update_item(self, **kw):
        pk = kw["Key"]["pk"]["S"]
        item = self.rows[pk]
        values = kw["ExpressionAttributeValues"]
        if ":reserved" in values:
            if (item["state"]["S"] != "reserved" or "s3_version" in item
                    or item["sha256"] != values[":digest"]
                    or item["document_version"] != values[":logical"]):
                raise RuntimeError("invalid reservation")
            item["state"] = values[":stored"]
            item["s3_version"] = values[":version"]
        else:
            if (item["state"]["S"] != "stored"
                    or item["s3_version"] != values[":version"]
                    or item["document_version"] != values[":logical"]
                    or item["sha256"] != values[":digest"]
                    or item["key_pin"] != values[":pin"]):
                raise RuntimeError("preview replay or mismatch")
            item["state"] = values[":queued"]
    def get_item(self, **kw):
        return {"Item": copy.deepcopy(self.rows.get(kw["Key"]["pk"]["S"], {}))}


class S3ForTests:
    def __init__(self):
        self.writes = {}
        self.ddb = FakeDocumentDdb()
    def put_object(self, **kw):
        if kw["IfNoneMatch"] != "*":
            raise AssertionError("unsafe overwrite allowed")
        if kw["Key"] in self.writes:
            error = RuntimeError("conditional object collision")
            error.response = {"Error": {"Code": "PreconditionFailed"}}
            raise error
        self.writes[kw["Key"]] = kw
        return {"VersionId": "actualS3version01"}


class RequestForTests:
    def __init__(self, tenant, body):
        self.state = SimpleNamespace(email="notary@example.test", serwis=False,
                                     kancelaria=tenant)
        self.payload = body
    async def stream(self):
        yield self.payload


def setup_backend(monkeypatch, s3, pin, tenant):
    monkeypatch.setitem(sys.modules, "autoryzacja", SimpleNamespace(MULTI=True))
    monkeypatch.setitem(sys.modules, "magazyn", SimpleNamespace(
        TRYB="s3", _klient_s3=lambda: s3,
        _szyfrowanie=lambda: {"ServerSideEncryption": "AES256"},
    ))
    monkeypatch.setenv("PIECZAPP_CONFIDENTIAL_ALLOWED_TENANT", tenant)
    monkeypatch.setenv("PIECZAPP_CONFIDENTIAL_BUCKET", "fictional-cipher-bucket")
    monkeypatch.setenv("PIECZAPP_CONFIDENTIAL_KMS_KEY_ARN", ARN)
    monkeypatch.setenv("PIECZAPP_CONFIDENTIAL_PUBLIC_KEY_SHA256", pin)
    from confidential.document_registry import DocumentVersionRegistry
    monkeypatch.setattr(router, "_registry", lambda scoped_tenant:
                        DocumentVersionRegistry(s3.ddb, tenant=scoped_tenant))


def test_two_synthetic_uploads_never_store_plaintext_or_dek(keys, monkeypatch, caplog):
    s3 = S3ForTests()
    caplog.set_level(logging.DEBUG)
    for tenant in ("pilot01", "pilot02"):
        setup_backend(monkeypatch, s3, keys[1], tenant)
        for case in ("case01",):
            obj = "scan01" if tenant == "pilot01" else "scan02"
            payload, dek = envelope(keys, tenant=tenant, case=case, object_id=obj)
            body = json.dumps(payload, separators=(",", ":")).encode("ascii")
            response = asyncio.run(router.store(
                RequestForTests(tenant, body), case, obj
            ))
            assert json.loads(response.body)["stored"] is True
            assert PLAINTEXT not in body
            assert dek not in body
    assert len(s3.writes) == 2
    for obj in s3.writes.values():
        raw = obj["Body"]
        assert PLAINTEXT not in raw
        assert b"FICTIONAL" not in raw
        assert b"wrapped_dek" in raw
        assert obj["ContentType"] == "application/json"
        assert "ServerSideEncryption" in obj
    assert "FICTIONAL TEST DOCUMENT" not in caplog.text


def test_backend_denies_cross_tenant_wrong_pin_and_legacy(keys, monkeypatch):
    s3 = S3ForTests()
    setup_backend(monkeypatch, s3, keys[1], "pilot01")
    payload, _ = envelope(keys)
    for bad in (
        {**payload, "tenant_id": "pilot02"},
        {**payload, "public_key_sha256": "A" * 43 + "="},
        {k: v for k, v in payload.items()
         if k not in ("document_version", "public_key_sha256")} | {"version": 1},
    ):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(router.store(RequestForTests(
                "pilot01", json.dumps(bad).encode("ascii")
            ), "case01", "scan01"))
        assert exc.value.status_code in (400, 403)
    assert s3.writes == {}


def test_duplicate_object_replay_denied(keys, monkeypatch):
    s3 = S3ForTests()
    setup_backend(monkeypatch, s3, keys[1], "pilot01")
    payload, _ = envelope(keys)
    body = json.dumps(payload).encode("ascii")
    req = RequestForTests("pilot01", body)
    assert json.loads(asyncio.run(router.store(req, "case01", "scan01")).body)["stored"]
    with pytest.raises(HTTPException) as exc:
        asyncio.run(router.store(req, "case01", "scan01"))
    assert exc.value.status_code == 409
    assert len(s3.writes) == 1


def test_release_verification_requires_independent_public_key(keys):
    private = ed25519.Ed25519PrivateKey.generate()
    trusted = private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    javascript = b"// synthetic JS; no user data\n"
    manifest = {
        "schema": "notarai.client-release.v1",
        "release_id": "a" * 32,
        "tenant_id": "pilot01",
        "kms_key_arn": ARN,
        "public_key_sha256": keys[1],
        "javascript_sha256": hashlib.sha256(javascript).hexdigest(),
        "expires_at": 2000000000,
    }
    sig = private.sign(canonical_release_bytes(manifest))
    valid = dict(javascript=javascript, manifest=manifest, signature=sig,
                 trusted_public_key=trusted, tenant_id="pilot01",
                 expected_kms_arn=ARN, expected_key_pin=keys[1],
                 now=1900000000)
    assert verify_client_release(**valid) == manifest["javascript_sha256"]
    wrong = [
        {"javascript": b"// attacker-controlled update"},
        {"signature": b"x" * 64},
        {"tenant_id": "pilot02"},
        {"expected_kms_arn": ARN.replace("fictional", "wrong")},
        {"expected_key_pin": "A" * 43 + "="},
        {"now": 2000000000},
        {"trusted_public_key": ed25519.Ed25519PrivateKey.generate().public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)},
    ]
    for update in wrong:
        with pytest.raises(UntrustedClientRelease):
            verify_client_release(**{**valid, **update})


def test_no_support_admin_decryption_path():
    # No plaintext/DEK endpoint in the confidential web API.
    declared = {(route.path, method)
                for route in router.router.routes
                for method in route.methods}
    assert not any("decrypt" in path or "unwrap" in path or
                   "recover" in path for path, _ in declared)
    assert not any("submit" in path or "sign" in path for path, _ in declared)


def test_recovery_with_two_external_signers_but_no_plaintext_export():
    from confidential.zk_recovery import (
        RecoveryDenied, authorize_recovery, canonical_recovery_request,
    )
    signer_a = ed25519.Ed25519PrivateKey.generate()
    signer_b = ed25519.Ed25519PrivateKey.generate()
    outsider = ed25519.Ed25519PrivateKey.generate()
    def pub(signer):
        return signer.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
    req = {
        "schema": "notarai.recovery.v1", "action": "rotate",
        "tenant_id": "pilot01", "case_id": "case01", "object_id": "scan01",
        "target_tenant_id": "pilot01", "target_object_id": "scan02",
        "document_version": "a" * 32,
        "old_key_arn": ARN,
        "new_key_arn": ARN.replace("fictional", "successor"),
        "new_key_sha256": keys[1],
        "request_id": "b" * 32, "expires_at": 2000000000,
    }
    message = canonical_recovery_request(req)
    valid = dict(
        request=req, custodian_signature=signer_a.sign(message),
        trustee_signature=signer_b.sign(message),
        custodian_public_key=pub(signer_a),
        trustee_public_key=pub(signer_b),
        expected_tenant="pilot01", expected_old_key=ARN,
        now=1900000000,
    )
    # Lost client DEK can be approved for rewrap ONLY after two external
    # attestations. This function never releases a DEK or calls KMS.
    assert authorize_recovery(**valid) == "rotate"
    denied = (
        {"expected_tenant": "pilot02"},
        {"expected_old_key": ARN.replace("fictional", "other")},
        {"now": 2000000000},
        {"trustee_signature": outsider.sign(message)},
        {"custodian_signature": b""},
        {"custodian_public_key": pub(signer_b)},
        {"request": {**req, "tenant_id": "pilot02"}},
        {"request": {**req, "new_key_sha256": "B" * 43 + "="}},
    )
    for change in denied:
        with pytest.raises(RecoveryDenied):
            authorize_recovery(**{**valid, **change})
    revoke = {**req, "action": "revoke", "new_key_arn": "",
              "new_key_sha256": "", "target_tenant_id": "",
              "target_object_id": ""}
    revoke_message = canonical_recovery_request(revoke)
    assert authorize_recovery(**{**valid,
        "request": revoke,
        "custodian_signature": signer_a.sign(revoke_message),
        "trustee_signature": signer_b.sign(revoke_message),
    }) == "revoke"


def test_unknown_or_legacy_envelope_cannot_be_run_in_new_guest():
    from pathlib import Path
    code = (Path(__file__).parent / "confidential" / "worker.py").read_text()
    assert 'if env.version != 2:' in code
    assert 'legacy unversioned envelope' in code


def test_durable_registry_prevents_reupload_after_s3_delete_marker(keys, monkeypatch):
    s3 = S3ForTests()
    setup_backend(monkeypatch, s3, keys[1], "pilot01")
    payload, _ = envelope(keys)
    request = RequestForTests("pilot01", json.dumps(payload).encode("ascii"))
    assert json.loads(asyncio.run(router.store(request, "case01", "scan01")).body)["stored"]
    # Pretend S3 has a current delete marker and accepts another IfNoneMatch.
    s3.writes.clear()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(router.store(request, "case01", "scan01"))
    assert exc.value.status_code == 409
    assert s3.writes == {}


def test_registry_blocks_wrong_version_digest_and_duplicate_preview(keys):
    from confidential.document_registry import DocumentVersionRegistry, DocumentRegistryDenied
    ddb = FakeDocumentDdb()
    ledger = DocumentVersionRegistry(ddb, tenant="pilot01")
    payload, _ = envelope(keys)
    wire = json.dumps(payload, separators=(",", ":")).encode("ascii")
    digest = hashlib.sha256(wire).hexdigest()
    values = dict(case_id="case01", object_id="scan01",
                  document_version=payload["document_version"],
                  ciphertext_sha256=digest, key_pin=keys[1])
    ledger.reserve(**values)
    with pytest.raises(DocumentRegistryDenied):
        ledger.reserve(**values)
    ledger.finalize(case_id="case01", object_id="scan01",
                    document_version=payload["document_version"],
                    ciphertext_sha256=digest, s3_version="s3Version001")
    with pytest.raises(DocumentRegistryDenied):
        ledger.claim_preview(**{**values, "s3_version": "wrongS3version"})
    with pytest.raises(DocumentRegistryDenied):
        ledger.claim_preview(**{**values, "s3_version": "s3Version001",
                               "ciphertext_sha256": "0" * 64})
    ledger.claim_preview(**{**values, "s3_version": "s3Version001"})
    with pytest.raises(DocumentRegistryDenied):
        ledger.claim_preview(**{**values, "s3_version": "s3Version001"})
    with pytest.raises(DocumentRegistryDenied):
        ledger.require_guest(**{**values, "s3_version": "s3Version001",
                                "ciphertext_sha256": "0" * 64})
    ledger.require_guest(**{**values, "s3_version": "s3Version001"})
    with pytest.raises(DocumentRegistryDenied):
        DocumentVersionRegistry(ddb, tenant="pilot02").require_guest(
            **{**values, "s3_version": "s3Version001"})


def test_nitro_only_dual_signed_key_migration_with_new_immutable_identity(
    keys, monkeypatch,
):
    import confidential.zk_migration as migration
    from confidential.zk_recovery import canonical_recovery_request, RecoveryDenied
    original_payload, _ = envelope(keys)
    original = Envelope.parse(original_payload)
    replacement = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    pem = replacement.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    der = replacement.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    pin = base64.b64encode(hashlib.sha256(der).digest()).decode("ascii")
    signer_a = ed25519.Ed25519PrivateKey.generate()
    signer_b = ed25519.Ed25519PrivateKey.generate()
    def pub(signer):
        return signer.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw,
        )
    req = {
        "schema": "notarai.recovery.v1", "action": "rotate",
        "tenant_id": "pilot01", "case_id": original.case_id,
        "object_id": original.object_id,
        "target_tenant_id": "pilot02", "target_object_id": "scan02",
        "document_version": original.document_version,
        "old_key_arn": ARN,
        "new_key_arn": ARN.replace("fictional", "successor"),
        "new_key_sha256": pin, "request_id": "c" * 32,
        "expires_at": 2000000000,
    }
    signed = canonical_recovery_request(req)
    class OneTimeLedger:
        seen = set()
        def claim_once(self, token):
            if token in self.seen:
                raise RuntimeError("already used")
            self.seen.add(token)
    ledger = OneTimeLedger()
    opts = dict(
        original=original, unwrapper=GuestForTests(keys[0]),
        recovery_request=req,
        custodian_signature=signer_a.sign(signed),
        trustee_signature=signer_b.sign(signed),
        custodian_public_key=pub(signer_a), trustee_public_key=pub(signer_b),
        replacement_kms_public_pem=pem,
        independent_one_time_ledger=ledger,
        now=1900000000,
    )
    # The unit harness is NOT Nitro hardware evidence.
    monkeypatch.setattr(migration, "NitroKMSUnwrapper", GuestForTests)
    monkeypatch.setattr(migration.os.path, "exists", lambda path: path == "/dev/nsm")
    result = migration.reencrypt_inside_attested_nitro(**opts)
    assert result["tenant_id"] == "pilot02"
    assert result["object_id"] == "scan02"
    assert result["document_version"] != original.document_version
    assert PLAINTEXT not in json.dumps(result).encode("ascii")
    recovered = Envelope.parse(result).open_inside_attested_task(
        GuestForTests(replacement)
    )
    assert recovered == PLAINTEXT
    with pytest.raises(RecoveryDenied, match="consumed"):
        migration.reencrypt_inside_attested_nitro(**opts)
    # A missing hardware device rejects even signatures and a valid key.
    monkeypatch.setattr(migration.os.path, "exists", lambda path: False)
    with pytest.raises(RecoveryDenied, match="hardware"):
        migration.reencrypt_inside_attested_nitro(**opts)


def test_migration_denies_unsigned_recipient_and_wrong_approval(keys, monkeypatch):
    from confidential.zk_recovery import canonical_recovery_request, RecoveryDenied
    import confidential.zk_migration as migration
    old, _ = envelope(keys)
    original = Envelope.parse(old)
    new_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    pub_der = new_key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    pem = new_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    pin = base64.b64encode(hashlib.sha256(pub_der).digest()).decode("ascii")
    a, b = ed25519.Ed25519PrivateKey.generate(), ed25519.Ed25519PrivateKey.generate()
    pub = lambda k: k.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )
    req = {
        "schema": "notarai.recovery.v1", "action": "rotate",
        "tenant_id": "pilot01", "case_id": original.case_id,
        "object_id": original.object_id, "document_version": original.document_version,
        "target_tenant_id": "pilot02", "target_object_id": "scan02",
        "old_key_arn": ARN, "new_key_arn": ARN.replace("fictional", "new"),
        "new_key_sha256": pin, "request_id": "d" * 32,
        "expires_at": 2000000000,
    }
    message = canonical_recovery_request(req)
    class Ledger:
        def claim_once(self, token):
            raise RuntimeError("no external authority")
    args = dict(
        original=original, unwrapper=GuestForTests(keys[0]),
        recovery_request=req, custodian_signature=a.sign(message),
        trustee_signature=b.sign(message),
        custodian_public_key=pub(a), trustee_public_key=pub(b),
        replacement_kms_public_pem=pem,
        independent_one_time_ledger=Ledger(), now=1900000000,
    )
    monkeypatch.setattr(migration, "NitroKMSUnwrapper", GuestForTests)
    monkeypatch.setattr(migration.os.path, "exists", lambda path: path == "/dev/nsm")
    with pytest.raises(RecoveryDenied, match="unavailable"):
        migration.reencrypt_inside_attested_nitro(**args)
    with pytest.raises(RecoveryDenied):
        migration.reencrypt_inside_attested_nitro(**{**args,
            "recovery_request": {**req, "target_object_id": "scan03"}})
    with pytest.raises(RecoveryDenied):
        migration.reencrypt_inside_attested_nitro(**{**args,
            "replacement_kms_public_pem": keys[0].public_key().public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode("ascii")})
