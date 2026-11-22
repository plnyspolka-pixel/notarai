"""SEC-10 synthetic retention matrix; never touches AWS or actual cases."""
from dataclasses import replace, fields
from datetime import datetime, timedelta, timezone
import inspect

import pytest

from confidential.retention_gate import (
    RetentionEvidence, InvalidRetentionEvidence, assess_retention,
)


NOW = datetime(2026, 11, 22, 4, 30, tzinfo=timezone.utc)
HASH = "a" * 64


def cleared():
    return RetentionEvidence(
        legal_policy_sha256=HASH,
        inventory_sha256="b" * 64,
        approved_retention_until=NOW - timedelta(days=1),
        observed_at=NOW - timedelta(minutes=5),
        legal_hold="cleared",
        s3_all_versions_listed=True,
        s3_pagination_complete=True,
        s3_delete_markers_included=True,
        replicas="none-verified",
        backups_verified_expired=True,
        ddb_pitr_verified_expired=True,
        cloud_audit_retention_exempted_with_legal_basis=True,
        custodian_signed_authorization_verified=True,
        controller_signed_authorization_verified=True,
    )


def test_all_evidence_only_allows_independent_review_not_deletion():
    result = assess_retention(cleared(), now=NOW)
    assert result.status == "ready_for_independent_review"
    assert not result.blockers
    assert result.actual_deletion_verified is False
    assert not any(k in {f.name for f in fields(type(result))}
                   for k in ("delete", "s3_version_id", "kms_key", "plaintext"))


@pytest.mark.parametrize("change,blocker", [
    ({"approved_retention_until": NOW + timedelta(days=1)}, "LEGAL_RETENTION_NOT_EXPIRED"),
    ({"legal_hold": "active"}, "LEGAL_HOLD_ACTIVE_OR_UNKNOWN"),
    ({"legal_hold": "unknown"}, "LEGAL_HOLD_ACTIVE_OR_UNKNOWN"),
    ({"s3_all_versions_listed": False}, "S3_VERSION_INVENTORY_INCOMPLETE"),
    ({"s3_pagination_complete": False}, "S3_VERSION_INVENTORY_INCOMPLETE"),
    ({"s3_delete_markers_included": False}, "S3_VERSION_INVENTORY_INCOMPLETE"),
    ({"replicas": "unknown"}, "REPLICATION_UNKNOWN"),
    ({"backups_verified_expired": False}, "BACKUP_RECOVERY_WINDOW_UNVERIFIED"),
    ({"ddb_pitr_verified_expired": False}, "DDB_PITR_RECOVERY_WINDOW_UNVERIFIED"),
    ({"cloud_audit_retention_exempted_with_legal_basis": False},
     "AUDIT_RETENTION_LEGAL_BASIS_UNVERIFIED"),
    ({"controller_signed_authorization_verified": False},
     "INDEPENDENT_AUTHORIZATION_MISSING"),
    ({"custodian_signed_authorization_verified": False},
     "INDEPENDENT_AUTHORIZATION_MISSING"),
])
def test_every_required_evidence_blocks_when_missing(change, blocker):
    result = assess_retention(replace(cleared(), **change), now=NOW)
    assert result.status == "blocked"
    assert blocker in result.blockers
    assert result.actual_deletion_verified is False


def test_multiple_independent_missing_evidence_is_accumulated():
    result = assess_retention(
        replace(cleared(), legal_hold="unknown", s3_all_versions_listed=False,
                ddb_pitr_verified_expired=False,
                custodian_signed_authorization_verified=False), now=NOW
    )
    assert len(result.blockers) == 4
    assert all(isinstance(x, str) for x in result.blockers)
    assert HASH not in repr(result.blockers)


@pytest.mark.parametrize("field,value", [
    ("legal_policy_sha256", "not-a-digest"),
    ("inventory_sha256", "c" * 63),
    ("legal_hold", "auto-cleared"),
    ("replicas", "true"),
    ("s3_pagination_complete", "true"),
    ("ddb_pitr_verified_expired", 1),
])
def test_inconsistent_input_fails_closed_without_echo(field, value):
    with pytest.raises(InvalidRetentionEvidence) as err:
        assess_retention(replace(cleared(), **{field: value}), now=NOW)
    assert str(value) not in str(err.value)


def test_stale_future_and_naive_timestamps_fail_closed():
    for change in (
        {"observed_at": NOW - timedelta(hours=25)},
        {"observed_at": NOW + timedelta(seconds=1)},
        {"observed_at": NOW.replace(tzinfo=None)},
        {"approved_retention_until": NOW.replace(tzinfo=None)},
    ):
        with pytest.raises(InvalidRetentionEvidence):
            assess_retention(replace(cleared(), **change), now=NOW)


def test_no_live_io_or_deletion_primitives_in_gate():
    source = inspect.getsource(assess_retention)
    for forbidden in ("boto3", "delete_object", "delete_item",
                      "kms.decrypt(", "subprocess", "os.system", "requests."):
        assert forbidden not in source
