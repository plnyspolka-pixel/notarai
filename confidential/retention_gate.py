"""SEC-10: metadata-only retention/erasure evidence gate. NEVER deletes data.

The caller is responsible for independently authenticating evidence. A READY
result is permission to seek human review, NOT an authorization to delete
objects, KMS keys or audit trails and NEVER proof that a copy is erased.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal
import re

_HEX = re.compile(r"^[0-9a-f]{64}$")
_HOLD = frozenset(("active", "cleared", "unknown"))
_REPLICATION = frozenset(("none-verified", "all-verified-purged", "unknown"))
_STATUS = frozenset(("ready_for_independent_review", "blocked"))


class InvalidRetentionEvidence(ValueError):
    """Constant-text rejection; never echo untrusted client metadata."""


@dataclass(frozen=True)
class RetentionEvidence:
    """Opaque, independently sourced metadata — no document IDs or contents.

    A missing fact means BLOCKED. Only a signed, vetted upstream evidence
    collector may populate these fields in a future integrated workflow.
    """
    legal_policy_sha256: str
    inventory_sha256: str
    approved_retention_until: datetime
    observed_at: datetime
    legal_hold: Literal["active", "cleared", "unknown"]
    s3_all_versions_listed: bool
    s3_pagination_complete: bool
    s3_delete_markers_included: bool
    replicas: Literal["none-verified", "all-verified-purged", "unknown"]
    backups_verified_expired: bool
    ddb_pitr_verified_expired: bool
    cloud_audit_retention_exempted_with_legal_basis: bool
    custodian_signed_authorization_verified: bool
    controller_signed_authorization_verified: bool


@dataclass(frozen=True)
class RetentionAssessment:
    status: Literal["blocked", "ready_for_independent_review"]
    blockers: tuple[str, ...]
    inventory_digest: str
    # Deliberately NO delete actions, object names, keys or ARNs.
    actual_deletion_verified: bool = False


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise InvalidRetentionEvidence("timezone-aware UTC timestamp required")
    try:
        offset = value.utcoffset()
    except (ValueError, OverflowError):
        raise InvalidRetentionEvidence("invalid evidence timestamp") from None
    if offset is None or offset != timedelta(0):
        raise InvalidRetentionEvidence("UTC timestamp required")
    return value.astimezone(timezone.utc)


def assess_retention(e: RetentionEvidence, *, now: datetime) -> RetentionAssessment:
    """Assess *eligibility for review* using trusted synthetic metadata.

    - No policy defaults: caller supplies an approved legal retention deadline.
    - No deletion can be issued by this function under any circumstances.
    - PITR, retained versions/replicas, backup and legal hold are separate gates.
    """
    current = _utc(now)
    until = _utc(e.approved_retention_until)
    observed = _utc(e.observed_at)
    if not (_HEX.fullmatch(e.legal_policy_sha256)
            and _HEX.fullmatch(e.inventory_sha256)):
        raise InvalidRetentionEvidence("approved evidence digests required")
    if e.legal_hold not in _HOLD or e.replicas not in _REPLICATION:
        raise InvalidRetentionEvidence("invalid retention evidence state")
    bool_fields = (
        e.s3_all_versions_listed, e.s3_pagination_complete,
        e.s3_delete_markers_included, e.backups_verified_expired,
        e.ddb_pitr_verified_expired,
        e.cloud_audit_retention_exempted_with_legal_basis,
        e.custodian_signed_authorization_verified,
        e.controller_signed_authorization_verified,
    )
    if any(type(value) is not bool for value in bool_fields):
        raise InvalidRetentionEvidence("invalid evidence type")
    if observed > current or current - observed > timedelta(hours=24):
        raise InvalidRetentionEvidence("stale or future evidence")
    reasons: list[str] = []
    if until > current:
        reasons.append("LEGAL_RETENTION_NOT_EXPIRED")
    if e.legal_hold != "cleared":
        reasons.append("LEGAL_HOLD_ACTIVE_OR_UNKNOWN")
    if not (e.s3_all_versions_listed and e.s3_pagination_complete
            and e.s3_delete_markers_included):
        reasons.append("S3_VERSION_INVENTORY_INCOMPLETE")
    if e.replicas not in ("none-verified", "all-verified-purged"):
        reasons.append("REPLICATION_UNKNOWN")
    if not e.backups_verified_expired:
        reasons.append("BACKUP_RECOVERY_WINDOW_UNVERIFIED")
    if not e.ddb_pitr_verified_expired:
        reasons.append("DDB_PITR_RECOVERY_WINDOW_UNVERIFIED")
    if not e.cloud_audit_retention_exempted_with_legal_basis:
        reasons.append("AUDIT_RETENTION_LEGAL_BASIS_UNVERIFIED")
    if not (e.controller_signed_authorization_verified
            and e.custodian_signed_authorization_verified):
        reasons.append("INDEPENDENT_AUTHORIZATION_MISSING")
    status = "blocked" if reasons else "ready_for_independent_review"
    if status not in _STATUS:
        raise AssertionError("invalid internal status")
    return RetentionAssessment(
        status=status, blockers=tuple(reasons),
        inventory_digest=e.inventory_sha256,
    )
