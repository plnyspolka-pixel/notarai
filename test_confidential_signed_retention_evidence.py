"""SEC-10 cryptographically signed metadata tests. Synthetic keys only."""
from __future__ import annotations

from dataclasses import replace, fields
from datetime import datetime, timedelta, timezone
import inspect
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from confidential.signed_retention_evidence import (
    SignedRetentionBundle, TrustAnchors, ExpectedScope,
    RejectedSignedEvidence, assess_signed_retention,
)


NOW = datetime(2026, 11, 22, 5, 0, tzinfo=timezone.utc)
DOMAIN = b"NOTARAI-SEC10-RETENTION-EVIDENCE-V1\x00"
ROLES = ("collector", "controller", "custodian")
DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
DIGEST_C = "c" * 64


@pytest.fixture
def keys():
    return tuple(Ed25519PrivateKey.generate() for _ in ROLES)


def trusted(keys):
    public = [
        k.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ) for k in keys
    ]
    return TrustAnchors(*public)


def scope():
    return ExpectedScope(
        tenant_id="pilot01", aws_account="111122223333",
        request_sha256=DIGEST_A, legal_policy_sha256=DIGEST_B,
        inventory_sha256=DIGEST_C,
    )


def evidence(**changes):
    d = {
        "schema": "notarai.sec10.retention.v1",
        "tenant_id": "pilot01", "aws_account": "111122223333",
        "request_sha256": DIGEST_A, "legal_policy_sha256": DIGEST_B,
        "inventory_sha256": DIGEST_C,
        "approved_retention_until": "2026-11-21T05:00:00Z",
        "observed_at": "2026-11-22T04:55:00Z",
        "legal_hold": "cleared",
        "s3_all_versions_listed": True,
        "s3_pagination_complete": True,
        "s3_delete_markers_included": True,
        "replicas": "none-verified",
        "backups_verified_expired": True,
        "ddb_pitr_verified_expired": True,
        "cloud_audit_retention_exempted_with_legal_basis": True,
    }
    d.update(changes)
    return d


def sign(keys, obj=None, *, raw=None):
    if raw is None:
        raw = json.dumps(
            evidence() if obj is None else obj, separators=(",", ":"),
            sort_keys=True, ensure_ascii=True,
        ).encode("utf-8")
    signatures = tuple(k.sign(DOMAIN + role.encode("ascii") + b"\x00" + raw)
                       for role, k in zip(ROLES, keys))
    return SignedRetentionBundle(raw, *signatures)


def verify(keys, bundle, *, expected=None, now=NOW, trust=None):
    return assess_signed_retention(
        bundle, trust=trusted(keys) if trust is None else trust,
        expected=scope() if expected is None else expected,
        now=now,
    )


def test_three_independent_signatures_only_authorize_review(keys):
    assessment = verify(keys, sign(keys))
    assert assessment.status == "ready_for_independent_review"
    assert assessment.blockers == ()
    assert assessment.actual_deletion_verified is False
    assert assessment.inventory_digest == DIGEST_C
    assert not {"delete", "key", "arn", "secret"}.intersection(
        f.name for f in fields(type(assessment))
    )


@pytest.mark.parametrize("field,value,blocker", [
    ("legal_hold", "active", "LEGAL_HOLD_ACTIVE_OR_UNKNOWN"),
    ("legal_hold", "unknown", "LEGAL_HOLD_ACTIVE_OR_UNKNOWN"),
    ("s3_all_versions_listed", False, "S3_VERSION_INVENTORY_INCOMPLETE"),
    ("s3_pagination_complete", False, "S3_VERSION_INVENTORY_INCOMPLETE"),
    ("s3_delete_markers_included", False, "S3_VERSION_INVENTORY_INCOMPLETE"),
    ("replicas", "unknown", "REPLICATION_UNKNOWN"),
    ("backups_verified_expired", False, "BACKUP_RECOVERY_WINDOW_UNVERIFIED"),
    ("ddb_pitr_verified_expired", False, "DDB_PITR_RECOVERY_WINDOW_UNVERIFIED"),
    ("cloud_audit_retention_exempted_with_legal_basis", False,
     "AUDIT_RETENTION_LEGAL_BASIS_UNVERIFIED"),
    ("approved_retention_until", "2026-12-01T00:00:00Z",
     "LEGAL_RETENTION_NOT_EXPIRED"),
])
def test_signed_but_legally_blocked_evidence_is_still_blocked(
    keys, field, value, blocker
):
    result = verify(keys, sign(keys, evidence(**{field: value})))
    assert result.status == "blocked"
    assert blocker in result.blockers
    assert result.actual_deletion_verified is False


@pytest.mark.parametrize("scope_field,new_value", [
    ("tenant_id", "pilot02"),
    ("aws_account", "999988887777"),
    ("request_sha256", "d" * 64),
    ("legal_policy_sha256", "e" * 64),
    ("inventory_sha256", "f" * 64),
])
def test_signed_evidence_cannot_be_replayed_for_another_scope(
    keys, scope_field, new_value
):
    with pytest.raises(RejectedSignedEvidence, match="signed evidence rejected"):
        verify(keys, sign(keys), expected=replace(scope(), **{scope_field: new_value}))


@pytest.mark.parametrize("field,new_value", [
    ("legal_hold", "active"),
    ("s3_all_versions_listed", False),
    ("approved_retention_until", "2026-12-01T00:00:00Z"),
    ("inventory_sha256", "d" * 64),
    ("tenant_id", "pilot02"),
])
def test_unsigned_mutations_are_rejected(keys, field, new_value):
    original = sign(keys)
    altered = evidence(**{field: new_value})
    raw = json.dumps(altered, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(RejectedSignedEvidence):
        verify(keys, replace(original, payload=raw))


def test_missing_or_swapped_signatures_and_keys_rejected(keys):
    good = sign(keys)
    wrong_order = replace(good,
                          collector_signature=good.controller_signature,
                          controller_signature=good.collector_signature)
    signatures = (
        replace(good, collector_signature=b""),
        replace(good, controller_signature=b"0" * 64),
        replace(good, custodian_signature=b"0" * 64),
        wrong_order,
    )
    for variant in signatures:
        with pytest.raises(RejectedSignedEvidence):
            verify(keys, variant)
    anchors = trusted(keys)
    with pytest.raises(RejectedSignedEvidence):
        verify(keys, good, trust=replace(
            anchors, custodian_public_key=anchors.controller_public_key
        ))
    with pytest.raises(RejectedSignedEvidence):
        verify(keys, good, trust=replace(
            anchors, controller_public_key=b"0" * 32
        ))


@pytest.mark.parametrize("change", [
    {"unknown_field": "not allowed"},
    {"schema": "notarai.sec10.retention.v0"},
    {"s3_pagination_complete": "true"},
    {"legal_hold": "not-a-state"},
    {"replicas": "auto"},
    {"inventory_sha256": "invalid"},
    {"observed_at": "2026-11-22T04:55:00+00:00"},
    {"approved_retention_until": "2026-11-21"},
    {"observed_at": "2026-11-22T04:55:00.123Z"},
])
def test_signed_invalid_schema_or_metadata_rejected(keys, change):
    with pytest.raises(RejectedSignedEvidence):
        verify(keys, sign(keys, evidence(**change)))


def test_missing_fields_cannot_be_signed_away(keys):
    data = evidence()
    del data["s3_delete_markers_included"]
    with pytest.raises(RejectedSignedEvidence):
        verify(keys, sign(keys, data))


def test_duplicate_json_keys_rejected_even_with_valid_signatures(keys):
    original = sign(keys)
    raw = original.payload.replace(
        b'"legal_hold":"cleared"',
        b'"legal_hold":"cleared","legal_hold":"active"',
    )
    assert raw != original.payload
    with pytest.raises(RejectedSignedEvidence):
        verify(keys, sign(keys, raw=raw))


def test_noncanonical_json_fails_closed_even_when_signed(keys):
    data = evidence()
    raw = json.dumps(data, indent=2, sort_keys=True).encode()
    with pytest.raises(RejectedSignedEvidence):
        verify(keys, sign(keys, raw=raw))


@pytest.mark.parametrize("observed", [
    "2026-11-21T03:00:00Z", "2026-11-22T05:00:01Z",
])
def test_signed_stale_or_future_evidence_rejected(keys, observed):
    with pytest.raises(RejectedSignedEvidence):
        verify(keys, sign(keys, evidence(observed_at=observed)))


def test_untrusted_caller_cannot_supply_its_own_trust_or_bad_scope(keys):
    good = sign(keys)
    wrong = tuple(Ed25519PrivateKey.generate() for _ in ROLES)
    with pytest.raises(RejectedSignedEvidence):
        verify(keys, good, trust=trusted(wrong))
    with pytest.raises(RejectedSignedEvidence):
        verify(keys, good, expected=replace(scope(), tenant_id="../pilot01"))
    with pytest.raises(RejectedSignedEvidence):
        verify(keys, good, expected=replace(scope(), aws_account="not-account"))


def test_no_private_key_or_deletion_primitive_in_verification_module():
    import confidential.signed_retention_evidence as mod
    source = inspect.getsource(mod)
    for dangerous in (
        "Ed25519PrivateKey", "delete_object(", "delete_item(",
        "boto3", "kms.decrypt(", "os.system(", "subprocess.",
    ):
        assert dangerous not in source


def test_signed_payload_has_a_strict_length_limit(keys):
    original = sign(keys)
    with pytest.raises(RejectedSignedEvidence):
        verify(keys, replace(original, payload=b"z" * 8193))
