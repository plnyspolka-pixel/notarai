"""SEC-10 independently verifiable, metadata-only retention evidence.

No private keys, key generation, AWS reads, deletion, or user-data processing.
Only an independently pinned Ed25519 key set is trusted. Signed evidence
permits an independent human review, NEVER actual deletion.

IMPORTANT: caller must obtain TrustAnchors AND ExpectedScope from protected
configuration/workflow, not from the incoming signed bundle or API request.
Replay prevention across the same scope requires a separate durable
single-use request ledger; this pure verifier does not provide one.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from confidential.retention_gate import (
    RetentionAssessment, RetentionEvidence, assess_retention,
)

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_TENANT = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_ACCOUNT = re.compile(r"^[0-9]{12}$")
_MAX_PAYLOAD = 8192
_DOMAIN = b"NOTARAI-SEC10-RETENTION-EVIDENCE-V1\x00"
_SCHEMA = "notarai.sec10.retention.v1"
_FLAG_FIELDS = frozenset({
    "s3_all_versions_listed", "s3_pagination_complete",
    "s3_delete_markers_included", "backups_verified_expired",
    "ddb_pitr_verified_expired",
    "cloud_audit_retention_exempted_with_legal_basis",
})
_TEXT_FIELDS = frozenset({
    "schema", "tenant_id", "aws_account", "request_sha256",
    "legal_policy_sha256", "inventory_sha256",
    "approved_retention_until", "observed_at", "legal_hold", "replicas",
})
_FIELDS = _FLAG_FIELDS | _TEXT_FIELDS
_ROLES = ("collector", "controller", "custodian")


class RejectedSignedEvidence(ValueError):
    """Constant-message fail-closed rejection; never echoes supplied metadata."""


@dataclass(frozen=True)
class SignedRetentionBundle:
    # Exact canonical UTF-8 JSON signed by all three independent parties.
    payload: bytes
    collector_signature: bytes
    controller_signature: bytes
    custodian_signature: bytes


@dataclass(frozen=True)
class TrustAnchors:
    """Three independent Ed25519 public keys from NON-user-controlled config."""
    collector_public_key: bytes
    controller_public_key: bytes
    custodian_public_key: bytes


@dataclass(frozen=True)
class ExpectedScope:
    """Expected values independently selected by the protected workflow."""
    tenant_id: str
    aws_account: str
    request_sha256: str
    legal_policy_sha256: str
    inventory_sha256: str


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise RejectedSignedEvidence("signed evidence rejected")
        result[key] = value
    return result


def _utc_timestamp(value: str) -> datetime:
    if not isinstance(value, str) or len(value) != 20:
        raise RejectedSignedEvidence("signed evidence rejected")
    try:
        dt = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        raise RejectedSignedEvidence("signed evidence rejected") from None
    if dt.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise RejectedSignedEvidence("signed evidence rejected")
    return dt.replace(tzinfo=timezone.utc)


def _validate_expected(expected: ExpectedScope, trust: TrustAnchors) -> None:
    if not isinstance(expected, ExpectedScope) or not isinstance(trust, TrustAnchors):
        raise RejectedSignedEvidence("signed evidence rejected")
    if (type(expected.tenant_id) is not str
            or not _TENANT.fullmatch(expected.tenant_id)
            or type(expected.aws_account) is not str
            or not _ACCOUNT.fullmatch(expected.aws_account)
            or any(type(x) is not str or not _DIGEST.fullmatch(x) for x in (
                expected.request_sha256, expected.legal_policy_sha256,
                expected.inventory_sha256,
            ))):
        raise RejectedSignedEvidence("signed evidence rejected")
    keys = (trust.collector_public_key, trust.controller_public_key,
            trust.custodian_public_key)
    if any(type(key) is not bytes or len(key) != 32 for key in keys):
        raise RejectedSignedEvidence("signed evidence rejected")
    if len(set(keys)) != 3:
        raise RejectedSignedEvidence("signed evidence rejected")


def assess_signed_retention(
    bundle: SignedRetentionBundle, *, trust: TrustAnchors,
    expected: ExpectedScope, now: datetime,
) -> RetentionAssessment:
    """Verify 3 distinct signatures, exact approved scope, then assess evidence.

    This does not create signatures, retain keys, call AWS, consume a nonce,
    or authorize deletion. No raw unverified "signature_verified" flag is
    accepted as an input to this entry point.
    """
    _validate_expected(expected, trust)
    if not isinstance(bundle, SignedRetentionBundle):
        raise RejectedSignedEvidence("signed evidence rejected")
    payload = bundle.payload
    if type(payload) is not bytes or not 1 <= len(payload) <= _MAX_PAYLOAD:
        raise RejectedSignedEvidence("signed evidence rejected")
    signatures = (
        bundle.collector_signature, bundle.controller_signature,
        bundle.custodian_signature,
    )
    if any(type(signature) is not bytes or len(signature) != 64
           for signature in signatures):
        raise RejectedSignedEvidence("signed evidence rejected")

    keys = (trust.collector_public_key, trust.controller_public_key,
            trust.custodian_public_key)
    for role, key, signature in zip(_ROLES, keys, signatures):
        # A signature valid for a different role cannot be substituted.
        signed = _DOMAIN + role.encode("ascii") + b"\x00" + payload
        try:
            Ed25519PublicKey.from_public_bytes(key).verify(signature, signed)
        except (InvalidSignature, ValueError, TypeError):
            raise RejectedSignedEvidence("signed evidence rejected") from None

    try:
        obj = json.loads(payload.decode("utf-8"),
                         object_pairs_hook=_unique_pairs)
        if type(obj) is not dict or obj.keys() != _FIELDS:
            raise RejectedSignedEvidence("signed evidence rejected")
        if any(type(obj[key]) is not str for key in _TEXT_FIELDS):
            raise RejectedSignedEvidence("signed evidence rejected")
        if any(type(obj[key]) is not bool for key in _FLAG_FIELDS):
            raise RejectedSignedEvidence("signed evidence rejected")
        canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=True, allow_nan=False).encode("utf-8")
        if canonical != payload:
            raise RejectedSignedEvidence("signed evidence rejected")
        if (obj["schema"] != _SCHEMA
                or obj["tenant_id"] != expected.tenant_id
                or obj["aws_account"] != expected.aws_account
                or obj["request_sha256"] != expected.request_sha256
                or obj["legal_policy_sha256"] != expected.legal_policy_sha256
                or obj["inventory_sha256"] != expected.inventory_sha256):
            raise RejectedSignedEvidence("signed evidence rejected")
        if not all(_DIGEST.fullmatch(obj[key]) for key in (
            "request_sha256", "legal_policy_sha256", "inventory_sha256",
        )):
            raise RejectedSignedEvidence("signed evidence rejected")
        e = RetentionEvidence(
            legal_policy_sha256=obj["legal_policy_sha256"],
            inventory_sha256=obj["inventory_sha256"],
            approved_retention_until=_utc_timestamp(
                obj["approved_retention_until"]
            ),
            observed_at=_utc_timestamp(obj["observed_at"]),
            legal_hold=obj["legal_hold"],
            s3_all_versions_listed=obj["s3_all_versions_listed"],
            s3_pagination_complete=obj["s3_pagination_complete"],
            s3_delete_markers_included=obj["s3_delete_markers_included"],
            replicas=obj["replicas"],
            backups_verified_expired=obj["backups_verified_expired"],
            ddb_pitr_verified_expired=obj["ddb_pitr_verified_expired"],
            cloud_audit_retention_exempted_with_legal_basis=(
                obj["cloud_audit_retention_exempted_with_legal_basis"]
            ),
            # These are set ONLY after verifying independently pinned
            # controller and custodian public-key signatures.
            controller_signed_authorization_verified=True,
            custodian_signed_authorization_verified=True,
        )
        return assess_retention(e, now=now)
    except (UnicodeError, ValueError, TypeError, KeyError, OverflowError):
        raise RejectedSignedEvidence("signed evidence rejected") from None
