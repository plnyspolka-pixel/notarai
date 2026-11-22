"""SEC-11 independent audit of the COMPLETE S3 evidence version inventory.

Read-only ListObjectVersions with automatic pagination. Detects shadow
versions, delete markers, gaps and unexpected keys under tenant evidence
prefix. Must compare with version IDs independently archived by the custodian.
This does not replace per-version signature/retention validation.
"""
from __future__ import annotations

import re

_ACCOUNT = re.compile(r"^[0-9]{12}$")
_BUCKET = re.compile(r"^[a-z0-9][a-z0-9.-]{2,62}$")
_TENANT = re.compile(r"^[a-z0-9]{1,12}$")
_VERSION = re.compile(r"^[A-Za-z0-9._~+/=-]{1,1024}$")


class ArchiveHistoryDenied(ValueError):
    """Constant denial text with no original AWS fields or object keys."""


def audit_archive_history(*, session, custody_account: str, bucket: str,
                          tenant: str, expected_versions: tuple[tuple[int, str], ...]
                          ) -> dict:
    """Fail closed on missing, extra, overwritten or deleted evidence keys.

    expected_versions comes from an independently archived custody receipt,
    never from the current NotarAI database or an S3 latest listing.
    """
    if (not isinstance(custody_account, str) or not _ACCOUNT.fullmatch(custody_account)
            or not isinstance(bucket, str) or not _BUCKET.fullmatch(bucket)
            or not isinstance(tenant, str) or not _TENANT.fullmatch(tenant)
            or not isinstance(expected_versions, tuple)
            or not 1 <= len(expected_versions) <= 10000):
        raise ArchiveHistoryDenied("invalid independent archive scope")
    expected = {}
    for position, pair in enumerate(expected_versions, start=1):
        if (not isinstance(pair, tuple) or len(pair) != 2
                or type(pair[0]) is not int or pair[0] != position
                or not isinstance(pair[1], str)
                or pair[1] == "null" or not _VERSION.fullmatch(pair[1])):
            raise ArchiveHistoryDenied("invalid external version receipt")
        expected[f"sec11-evidence/{tenant}/{position:08d}.json"] = pair[1]
    checks = {
        "custodian_identity": False,
        "complete_chain_inventory": False,
        "no_shadow_versions": False,
        "no_delete_markers": False,
        "externally_pinned_versions": False,
    }
    try:
        identity = session.client("sts").get_caller_identity()
        if identity.get("Account") != custody_account:
            raise ArchiveHistoryDenied("wrong independent custodian account")
        checks["custodian_identity"] = True
        s3 = session.client("s3", region_name="eu-central-1")
        prefix = f"sec11-evidence/{tenant}/"
        paginator = s3.get_paginator("list_object_versions")
        seen = {}
        any_marker = False
        shadowed = False
        unexpected = False
        pages = paginator.paginate(Bucket=bucket, Prefix=prefix,
                                   ExpectedBucketOwner=custody_account)
        for page in pages:
            if not isinstance(page, dict):
                raise ArchiveHistoryDenied("invalid archive inventory page")
            if page.get("DeleteMarkers"):
                any_marker = True
            for record in page.get("Versions", []):
                if not isinstance(record, dict):
                    unexpected = True
                    continue
                key = record.get("Key")
                vid = record.get("VersionId")
                if (not isinstance(key, str) or not key.startswith(prefix)
                        or key not in expected or not isinstance(vid, str)
                        or not _VERSION.fullmatch(vid) or vid == "null"):
                    unexpected = True
                    continue
                if key in seen or record.get("IsLatest") is not True:
                    shadowed = True
                seen[key] = vid
                if len(seen) > len(expected):
                    unexpected = True
            if page.get("CommonPrefixes"):
                unexpected = True
        checks["complete_chain_inventory"] = (
            not unexpected and len(seen) == len(expected) and
            set(seen) == set(expected)
        )
        checks["no_shadow_versions"] = not shadowed and not unexpected
        checks["no_delete_markers"] = not any_marker
        checks["externally_pinned_versions"] = seen == expected
        passed = all(checks.values())
        return {
            "inventory_integrity": "PASS" if passed else "FAIL",
            "assurance_status": "BLOCKED",
            "checked_sequence_count": len(expected),
            "checks": checks,
            "zero_operator_access_proven": False,
        }
    except ArchiveHistoryDenied:
        return {
            "inventory_integrity": "FAIL",
            "assurance_status": "BLOCKED",
            "checks": checks, "zero_operator_access_proven": False,
        }
    except Exception:
        return {
            "inventory_integrity": "BLOCKED",
            "assurance_status": "BLOCKED",
            "checks": checks, "zero_operator_access_proven": False,
        }
