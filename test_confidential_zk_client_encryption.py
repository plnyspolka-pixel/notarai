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


def _pin_synthetic_recovery_root(monkeypatch, tmp_path, signer_a, signer_b, pin):
    import confidential.recovery_trust as trust
    import confidential.zk_migration as migration
    def raw(signer):
        return signer.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
    root = {
        "schema": "notarai.recovery-root.v1",
        "tenant_id": "pilot01", "old_key_arn": ARN, "old_key_pin": pin,
        "custodian_public_key_b64": base64.b64encode(raw(signer_a)).decode("ascii"),
        "trustee_public_key_b64": base64.b64encode(raw(signer_b)).decode("ascii"),
        "expires_at": 2000000000,
    }
    dest = tmp_path / "trusted-recovery-root.json"
    dest.write_text(json.dumps(root), encoding="ascii")
    monkeypatch.setattr(trust, "_ROOT_PATH", dest)
    monkeypatch.setattr(migration.time, "time", lambda: 1900000000)
    return dest


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
    def head_object(self, **kw):
        item = self.writes[kw["Key"]]
        return {"VersionId": "actualS3version01",
                "Metadata": item.get("Metadata", {}),
                "ContentLength": len(item["Body"])}
    def get_object(self, **kw):
        from io import BytesIO
        item = self.writes[kw["Key"]]
        return {"Body": BytesIO(item["Body"]), "VersionId": "actualS3version01"}

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


def test_recovery_with_two_external_signers_but_no_plaintext_export(keys):
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
        "schema": "notarai.recovery.v2", "action": "rotate",
        "tenant_id": "pilot01", "case_id": "case01", "object_id": "scan01",
        "target_tenant_id": "pilot01", "target_object_id": "scan02",
        "document_version": "a" * 32,
        "old_key_arn": ARN,
        "new_key_arn": ARN.replace("fictional", "successor"),
        "new_key_sha256": keys[1],
        "source_s3_version": "s3SyntheticVersion01",
        "source_ciphertext_sha256": "a" * 64,
        "source_key_pin": keys[1],
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
    keys, monkeypatch, tmp_path,
):
    import confidential.zk_migration as migration
    from confidential.zk_recovery import canonical_recovery_request, RecoveryDenied
    original_payload, _ = envelope(keys)
    original_wire = json.dumps(original_payload, separators=(",", ":")).encode("ascii")
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
        "schema": "notarai.recovery.v2", "action": "rotate",
        "tenant_id": "pilot01", "case_id": original.case_id,
        "object_id": original.object_id,
        "target_tenant_id": "pilot02", "target_object_id": "scan02",
        "document_version": original.document_version,
        "old_key_arn": ARN,
        "new_key_arn": ARN.replace("fictional", "successor"),
        "new_key_sha256": pin, "request_id": "c" * 32,
        "source_s3_version": "s3SyntheticVersion01",
        "source_ciphertext_sha256": hashlib.sha256(original_wire).hexdigest(),
        "source_key_pin": keys[1],
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
    monkeypatch.setattr(migration, "CustodyRecoveryNonceLedger", OneTimeLedger)
    _pin_synthetic_recovery_root(monkeypatch, tmp_path, signer_a, signer_b, keys[1])
    opts = dict(
        original=original, source_envelope_wire=original_wire,
        source_s3_version="s3SyntheticVersion01",
        unwrapper=GuestForTests(keys[0]),
        recovery_request=req,
        custodian_signature=signer_a.sign(signed),
        trustee_signature=signer_b.sign(signed),
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


def test_migration_denies_unsigned_recipient_and_wrong_approval(keys, monkeypatch, tmp_path):
    from confidential.zk_recovery import canonical_recovery_request, RecoveryDenied
    import confidential.zk_migration as migration
    old, _ = envelope(keys)
    original_wire = json.dumps(old, separators=(",", ":")).encode("ascii")
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
        "schema": "notarai.recovery.v2", "action": "rotate",
        "tenant_id": "pilot01", "case_id": original.case_id,
        "object_id": original.object_id, "document_version": original.document_version,
        "target_tenant_id": "pilot02", "target_object_id": "scan02",
        "old_key_arn": ARN, "new_key_arn": ARN.replace("fictional", "new"),
        "new_key_sha256": pin, "request_id": "d" * 32,
        "source_s3_version": "s3SyntheticVersion01",
        "source_ciphertext_sha256": hashlib.sha256(original_wire).hexdigest(),
        "source_key_pin": keys[1],
        "expires_at": 2000000000,
    }
    message = canonical_recovery_request(req)
    _pin_synthetic_recovery_root(monkeypatch, tmp_path, a, b, keys[1])
    calls = []
    class Ledger:
        def claim_once(self, token):
            calls.append(token)
            raise RuntimeError("no external authority")
    monkeypatch.setattr(migration, "CustodyRecoveryNonceLedger", Ledger)
    args = dict(
        original=original, source_envelope_wire=original_wire,
        source_s3_version="s3SyntheticVersion01",
        unwrapper=GuestForTests(keys[0]),
        recovery_request=req, custodian_signature=a.sign(message),
        trustee_signature=b.sign(message),
        replacement_kms_public_pem=pem,
        independent_one_time_ledger=Ledger(), now=1900000000,
    )
    monkeypatch.setattr(migration, "NitroKMSUnwrapper", GuestForTests)
    monkeypatch.setattr(migration.os.path, "exists", lambda path: path == "/dev/nsm")
    with pytest.raises(RecoveryDenied, match="unavailable"):
        migration.reencrypt_inside_attested_nitro(**args)
    assert len(calls) == 1
    # A signature must bind the exact source bytes and S3 VersionId.
    for changed in (
        {"source_envelope_wire": original_wire + b" "},
        {"source_s3_version": "differentS3version"},
        {"recovery_request": {**req, "source_ciphertext_sha256": "f" * 64}},
        {"recovery_request": {**req, "source_s3_version": "otherVersion"}},
        {"recovery_request": {**req, "source_key_pin": "A" * 43 + "="}},
        {"recovery_request": {**req, "target_object_id": "scan03"}},
    ):
        with pytest.raises(RecoveryDenied):
            migration.reencrypt_inside_attested_nitro(**{**args, **changed})
    assert len(calls) == 1, "unapproved recovery touched external one-time ledger"
    # An operator can manufacture two perfectly valid Ed25519 signatures
    # using its OWN keys. With a pinned independent release root, neither
    # can authorize a migration or consume the external nonce.
    rogue1 = ed25519.Ed25519PrivateKey.generate()
    rogue2 = ed25519.Ed25519PrivateKey.generate()
    for forged in (
        {"custodian_signature": rogue1.sign(message)},
        {"trustee_signature": rogue2.sign(message)},
        {"custodian_signature": rogue1.sign(message),
         "trustee_signature": rogue2.sign(message)},
    ):
        with pytest.raises(RecoveryDenied, match="independently authorized"):
            migration.reencrypt_inside_attested_nitro(**{**args, **forged})
    assert len(calls) == 1, "rogue recovery signatures reached the custody ledger"
    # Remove approved root: caller-created public keys and signatures MUST NOT
    # authorize a migration when the independent release root is missing.
    import confidential.recovery_trust as trust
    trusted_path = trust._ROOT_PATH
    monkeypatch.setattr(trust, "_ROOT_PATH", tmp_path / "missing-external-root.json")
    with pytest.raises(RecoveryDenied, match="not provisioned"):
        migration.reencrypt_inside_attested_nitro(**args)
    assert len(calls) == 1
    monkeypatch.setattr(trust, "_ROOT_PATH", trusted_path)
    # A forged clock cannot revive an expired signed approval.
    monkeypatch.setattr(migration.time, "time", lambda: 2000000001)
    with pytest.raises(RecoveryDenied, match="clock"):
        migration.reencrypt_inside_attested_nitro(**args)
    assert len(calls) == 1
    monkeypatch.setattr(migration.time, "time", lambda: 1900000000)
    with pytest.raises(RecoveryDenied):
        migration.reencrypt_inside_attested_nitro(**{**args,
            "replacement_kms_public_pem": keys[0].public_key().public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode("ascii")})


def test_readback_requires_durable_registry_digest_and_s3_version(keys, monkeypatch):
    s3 = S3ForTests()
    setup_backend(monkeypatch, s3, keys[1], "pilot01")
    payload, _ = envelope(keys)
    body = json.dumps(payload, separators=(",", ":")).encode("ascii")
    req = RequestForTests("pilot01", body)
    assert json.loads(asyncio.run(router.store(req, "case01", "scan01")).body)["stored"]
    from_repo = json.loads(router.retrieve(req, "case01", "scan01").body)
    assert from_repo["document_version"] == payload["document_version"]
    key = next(iter(s3.writes))
    original = s3.writes[key]["Body"]
    s3.writes[key]["Body"] = original + b" "
    with pytest.raises(HTTPException) as err:
        router.retrieve(req, "case01", "scan01")
    assert err.value.status_code == 409


def test_custody_recovery_nonce_is_single_use_and_fail_closed():
    from confidential.custody_nonce import (
        CustodyRecoveryNonceLedger, RecoveryNonceDenied,
    )
    table = FakeDocumentDdb()
    class Session:
        def __init__(self, account):
            self.account = account
            self.clients = []
        def client(self, name, **kwargs):
            self.clients.append(name)
            if name == "sts":
                session = self
                class STS:
                    def get_caller_identity(self):
                        return {"Account": session.account}
                return STS()
            if name == "dynamodb":
                assert kwargs["region_name"] == "eu-central-1"
                return table
            raise AssertionError("wrong AWS service")
    session = Session("111122223333")
    ledger = CustodyRecoveryNonceLedger(
        session, tenant="pilot01", custody_account="111122223333",
        workload_account="444455556666",
    )
    assert session.clients == ["sts", "dynamodb"]
    ledger.claim_once("a" * 32)
    assert len(table.rows) == 1
    with pytest.raises(RecoveryNonceDenied):
        ledger.claim_once("a" * 32)
    with pytest.raises(RecoveryNonceDenied):
        ledger.claim_once("bad-identifier")
    assert len(table.rows) == 1
    for account, workload in (
        ("444455556666", "444455556666"),  # same AWS account
        ("444455556666", "777788889999"),  # fake custody identity
    ):
        mismatched = Session(account)
        with pytest.raises(RecoveryNonceDenied):
            CustodyRecoveryNonceLedger(
                mismatched, tenant="pilot01", custody_account="111122223333",
                workload_account=workload,
            )
        assert "dynamodb" not in mismatched.clients
    with pytest.raises(RecoveryNonceDenied):
        CustodyRecoveryNonceLedger(
            session, tenant="../bad", custody_account="111122223333",
            workload_account="444455556666",
        )


def test_synthetic_operator_decrypt_probe_rejects_plaintext_and_bad_key_pin(keys):
    from scripts.verify_sec03_operator_denial import (
        OperatorProbeRejected, run_probe,
    )
    der = keys[0].public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    arn = "arn:aws:kms:eu-central-1:444455556666:key/fixture"
    class Sts:
        def __init__(self, account):
            self.account = account
        def get_caller_identity(self):
            return {"Account": self.account}
    class Custody:
        def get_public_key(self, **kwargs):
            assert kwargs == {"KeyId": arn}
            return {"KeyId": arn, "KeyUsage": "ENCRYPT_DECRYPT",
                    "KeySpec": "RSA_3072", "PublicKey": der}
    class Denied:
        def decrypt(self, **kwargs):
            class AwsDeny(Exception):
                response = {"Error": {"Code": "AccessDeniedException"}}
            raise AwsDeny()
    values = dict(
        operator_sts=Sts("111122223333"), operator_kms=Denied(),
        custody_sts=Sts("444455556666"), custody_kms=Custody(),
        expected_operator="111122223333",
        expected_custody="444455556666",
        key_arn=arn, trusted_public_key_pin=keys[1],
    )
    redacted = run_probe(**values)
    assert redacted["unenclaved_decrypt_denied_for_test_principal"]
    assert redacted["status"] == "BLOCKED"
    assert redacted["global_operator_denial_proven"] is False
    class Malicious:
        def decrypt(self, **kwargs):
            return {"Plaintext": b"synthetic-secret"}
    result = run_probe(**{**values, "operator_kms": Malicious()})
    assert result["status"] == "FAIL"
    assert "Plaintext" not in str(result)
    with pytest.raises(OperatorProbeRejected):
        run_probe(**{**values, "trusted_public_key_pin": "A" * 43 + "="})
    with pytest.raises(OperatorProbeRejected):
        run_probe(**{**values, "operator_sts": Sts("444455556666")})


def test_independent_document_origin_receipt_denies_operator_forgery(keys):
    from confidential.document_authenticity import (
        canonical_origin_receipt, verify_document_origin, UntrustedDocumentOrigin,
    )
    payload, _ = envelope(keys)
    wire = json.dumps(payload, separators=(",", ":")).encode("ascii")
    sha = hashlib.sha256(wire).hexdigest()
    signer = ed25519.Ed25519PrivateKey.generate()
    public = signer.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    fields = {
        "tenant_id": "pilot01", "case_id": "case01",
        "object_id": "scan01", "document_version": payload["document_version"],
        "s3_version": "actualS3version01", "ciphertext_sha256": sha,
        "kms_key_arn": ARN, "key_pin": keys[1],
        "issuer_id": "custody01",
    }
    receipt = {
        "schema": "notarai.document-origin.v1",
        **fields, "expires_at": 2000000000,
    }
    signature = signer.sign(canonical_origin_receipt(receipt))
    args = dict(
        receipt=receipt, signature=signature,
        independent_issuer_public_key=public,
        expected_tenant=fields["tenant_id"],
        expected_case=fields["case_id"],
        expected_object=fields["object_id"],
        expected_document_version=fields["document_version"],
        expected_s3_version=fields["s3_version"],
        expected_ciphertext_sha256=fields["ciphertext_sha256"],
        expected_key_arn=fields["kms_key_arn"],
        expected_key_pin=fields["key_pin"],
        expected_issuer_id=fields["issuer_id"],
        now=1900000000,
    )
    assert verify_document_origin(**args) is None
    for change in (
        {"expected_ciphertext_sha256": "0" * 64},
        {"expected_s3_version": "newS3version"},
        {"expected_tenant": "pilot02"},
        {"expected_issuer_id": "operator"},
        {"now": 2000000000},
        {"signature": b"0" * 64},
        {"independent_issuer_public_key":
            ed25519.Ed25519PrivateKey.generate().public_key().public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw,
            )},
    ):
        with pytest.raises(UntrustedDocumentOrigin):
            verify_document_origin(**{**args, **change})
    # An operator with the PUBLIC RSA key can forge a valid *new* envelope.
    # Without the custodian's private origin-signing key, its receipt fails.
    forged, _ = envelope(keys)
    forged_sha = hashlib.sha256(json.dumps(
        forged, separators=(",", ":")).encode("ascii")).hexdigest()
    assert forged_sha != sha
    with pytest.raises(UntrustedDocumentOrigin):
        verify_document_origin(**{**args,
            "expected_ciphertext_sha256": forged_sha})


def test_ciphertext_raw_bytes_preserved_and_duplicate_json_keys_rejected(keys, monkeypatch):
    s3 = S3ForTests()
    setup_backend(monkeypatch, s3, keys[1], "pilot01")
    payload, _ = envelope(keys)
    wire = json.dumps(payload, indent=2).encode("ascii") + b"\n"
    returned = asyncio.run(router.store(
        RequestForTests("pilot01", wire), "case01", "scan01",
    ))
    assert json.loads(returned.body)["ciphertext_sha256"] == hashlib.sha256(wire).hexdigest()
    assert next(iter(s3.writes.values()))["Body"] == wire
    returned_wire = router.retrieve(
        RequestForTests("pilot01", b""), "case01", "scan01"
    )
    assert returned_wire.body == wire
    assert returned_wire.headers["cache-control"] == "no-store"

    dupe = wire.replace(b'"version": 2,', b'"version": 2, "version": 2,', 1)
    # JSON parser ambiguity must be caught BEFORE S3/DDB reservation.
    s3_new = S3ForTests()
    setup_backend(monkeypatch, s3_new, keys[1], "pilot01")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(router.store(
            RequestForTests("pilot01", dupe), "case01", "scan01",
        ))
    assert exc.value.status_code == 400
    assert not s3_new.writes and not s3_new.ddb.rows


def test_signed_receipt_upload_matches_exact_encrypted_bytes(keys, monkeypatch):
    from confidential.document_authenticity import canonical_origin_receipt
    s3 = S3ForTests()
    setup_backend(monkeypatch, s3, keys[1], "pilot01")
    payload, _ = envelope(keys)
    wire = json.dumps(payload, separators=(",", ":")).encode("ascii")
    result = asyncio.run(router.store(
        RequestForTests("pilot01", wire), "case01", "scan01",
    ))
    stored = json.loads(result.body)
    signer = ed25519.Ed25519PrivateKey.generate()
    receipt = {
        "schema": "notarai.document-origin.v1",
        "tenant_id": "pilot01", "case_id": "case01",
        "object_id": "scan01",
        "document_version": payload["document_version"],
        "s3_version": stored["s3_version"],
        "ciphertext_sha256": stored["ciphertext_sha256"],
        "kms_key_arn": ARN, "key_pin": keys[1],
        "issuer_id": "synthetic_issuer", "expires_at": 2000000000,
    }
    bundle = {
        "schema": "notarai.signed-origin-receipt.v1", "receipt": receipt,
        "signature_b64": base64.b64encode(
            signer.sign(canonical_origin_receipt(receipt))
        ).decode("ascii"),
    }
    body = json.dumps(bundle, separators=(",", ":")).encode("ascii")
    accepted = asyncio.run(router.store_origin_receipt(
        RequestForTests("pilot01", body), "case01", "scan01",
    ))
    assert json.loads(accepted.body) == {
        "stored": True, "signature_verified": False,
    }
    assert any(k.endswith(".origin.json") for k in s3.writes)
    with pytest.raises(HTTPException) as err:
        asyncio.run(router.store_origin_receipt(
            RequestForTests("pilot01", body), "case01", "scan01",
        ))
    assert err.value.status_code == 409
    with pytest.raises(HTTPException) as err:
        asyncio.run(router.store_origin_receipt(
            RequestForTests("pilot01", json.dumps(
                {**bundle, "receipt": {
                    **receipt, "ciphertext_sha256": "0" * 64,
                }}
            ).encode("ascii")), "case01", "scan01",
        ))
    assert err.value.status_code == 409
