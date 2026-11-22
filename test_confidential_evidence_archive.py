"""SEC-11 synthetic archive tests; never calls AWS or reads documents."""
import hashlib
import json
from datetime import timedelta

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from confidential.evidence_archive import ArchiveDenied, verify_archive_version
from confidential.signed_evidence import (
    manifest_sha256, public_fingerprint, sign_manifest,
)
from test_confidential_signed_evidence import NOW, fixture_manifest

ACCOUNT = "444455556666"
BUCKET = "notarai-sec11-custody-synthetic"
VERSION = "vTEST_ONLY_123"


class Body:
    def __init__(self, raw):
        self.raw = raw
        self.closed = False

    def read(self, count):
        assert count == 128 * 1024 + 1
        return self.raw[:count]

    def close(self):
        self.closed = True


class FakeS3:
    def __init__(self, raw):
        self.raw = raw
        self.calls = []
        self.lock = "COMPLIANCE"
        self.retained_until = NOW + timedelta(days=10)
        self.body = None

    def head_object(self, **kwargs):
        self.calls.append(("head_object", kwargs))
        return {"ContentLength": len(self.raw)}

    def get_object_retention(self, **kwargs):
        self.calls.append(("get_object_retention", kwargs))
        return {"Retention": {"Mode": self.lock, "RetainUntilDate": self.retained_until}}

    def get_object(self, **kwargs):
        self.calls.append(("get_object", kwargs))
        self.body = Body(self.raw)
        return {"Body": self.body}


class FakeSession:
    def __init__(self, raw, account=ACCOUNT):
        self.account = account
        self.s3 = FakeS3(raw)
        self.calls = []

    def client(self, service, **kwargs):
        self.calls.append((service, kwargs))
        if service == "sts":
            parent = self
            class STS:
                def get_caller_identity(self):
                    return {"Account": parent.account}
            return STS()
        assert service == "s3" and kwargs == {"region_name": "eu-central-1"}
        return self.s3


def make_fixture():
    key = Ed25519PrivateKey.generate()
    manifest = fixture_manifest()
    bundle = sign_manifest(manifest, key)
    raw = json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode("ascii")
    pub = key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )
    return FakeSession(raw), {
        "custody_account": ACCOUNT, "bucket": BUCKET,
        "tenant": "pilot01", "sequence": 1,
        "version_id": VERSION, "expected_package_sha256": hashlib.sha256(raw).hexdigest(),
        "trusted_public_key_raw": pub, "pinned_fingerprint": public_fingerprint(pub),
        "trusted_manifest_head_sha256": manifest_sha256(manifest),
        "clock": NOW,
    }


def test_exact_version_has_signed_integrity_and_active_retention():
    session, args = make_fixture()
    result = verify_archive_version(session=session, **args)
    assert result["archive_integrity"] == "PASS"
    assert result["assurance_status"] == "BLOCKED"
    assert all(result["checks"].values())
    assert result["zero_operator_access_proven"] is False
    assert [op for op, _ in session.s3.calls] == [
        "head_object", "get_object_retention", "get_object",
    ]
    assert all(kwargs["ExpectedBucketOwner"] == ACCOUNT
               and kwargs["VersionId"] == VERSION
               and kwargs["Key"] == "sec11-evidence/pilot01/00000001.json"
               for _, kwargs in session.s3.calls)
    assert session.s3.body.closed


@pytest.mark.parametrize("change", [
    "wrong_hash", "wrong_signature_pin", "wrong_head",
    "expired_lock", "governance_lock", "modified_body",
])
def test_archive_rejects_tampered_or_unlocked_records(change):
    session, args = make_fixture()
    if change == "wrong_hash":
        args["expected_package_sha256"] = "a" * 64
    elif change == "wrong_signature_pin":
        args["pinned_fingerprint"] = "a" * 64
    elif change == "wrong_head":
        args["trusted_manifest_head_sha256"] = "a" * 64
    elif change == "expired_lock":
        session.s3.retained_until = NOW - timedelta(seconds=1)
    elif change == "governance_lock":
        session.s3.lock = "GOVERNANCE"
    else:
        raw = bytearray(session.s3.raw)
        raw[-2] = ord("x")
        session.s3.raw = bytes(raw)
    result = verify_archive_version(session=session, **args)
    assert result["archive_integrity"] == "FAIL"
    assert result["zero_operator_access_proven"] is False


def test_wrong_custody_identity_prevents_any_s3_read():
    session, args = make_fixture()
    session.account = "111122223333"
    result = verify_archive_version(session=session, **args)
    assert result["archive_integrity"] == "FAIL"
    assert session.s3.calls == []
    assert session.calls == [("sts", {})]


@pytest.mark.parametrize("changes", [
    {"tenant": "../secret"}, {"sequence": 0}, {"version_id": "null"},
    {"version_id": "?"}, {"expected_package_sha256": "not-a-digest"},
    {"trusted_manifest_head_sha256": "not-a-digest"},
])
def test_invalid_scopes_rejected_before_aws(changes):
    class NoAws:
        def client(self, *args, **kwargs):
            raise AssertionError("AWS must not be called")
    _, args = make_fixture()
    args.update(changes)
    with pytest.raises(ArchiveDenied):
        verify_archive_version(session=NoAws(), **args)
