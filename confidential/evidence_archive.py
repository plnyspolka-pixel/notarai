"""SEC-11 read-only archive verification of an exact signed metadata version.

This verifier runs under the independent custodian's AWS identity. It reads
ONLY strict SEC-11 evidence package objects, never client documents.
A valid archived signature and WORM retention do not prove account isolation,
Nitro attestation, or Zero Operator Access.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone

from confidential.signed_evidence import verify_bundle

_ACCOUNT = re.compile(r"^[0-9]{12}$")
_BUCKET = re.compile(r"^[a-z0-9][a-z0-9.-]{2,62}$")
_TENANT = re.compile(r"^[a-z0-9]{1,12}$")
_VERSION = re.compile(r"^[A-Za-z0-9._~+/=-]{1,1024}$")
_HASH = re.compile(r"^[a-f0-9]{64}$")
_MAX_PACKAGE = 128 * 1024


class ArchiveDenied(ValueError):
    """Safe constant errors; never expose source records or AWS responses."""


def verify_archive_version(
    *, session, custody_account: str, bucket: str, tenant: str,
    sequence: int, version_id: str, expected_package_sha256: str,
    trusted_public_key_raw: bytes, pinned_fingerprint: str,
    trusted_manifest_head_sha256: str, clock: datetime | None = None,
) -> dict:
    """Validate independently pinned signature, exact S3 bytes and WORM lock.

    No PutObject, DeleteObject or AWS administrator calls; nothing is logged.
    """
    if (not isinstance(custody_account, str) or not _ACCOUNT.fullmatch(custody_account)
            or not isinstance(bucket, str) or not _BUCKET.fullmatch(bucket)
            or not isinstance(tenant, str) or not _TENANT.fullmatch(tenant)
            or type(sequence) is not int or not 1 <= sequence <= 10000000
            or not isinstance(version_id, str) or version_id == "null"
            or not _VERSION.fullmatch(version_id)
            or not isinstance(expected_package_sha256, str)
            or not _HASH.fullmatch(expected_package_sha256)
            or not isinstance(trusted_manifest_head_sha256, str)
            or not _HASH.fullmatch(trusted_manifest_head_sha256)):
        raise ArchiveDenied("invalid independent archive verification scope")
    now = clock or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ArchiveDenied("timezone-aware inspection required")
    key = f"sec11-evidence/{tenant}/{sequence:08d}.json"
    checks = {
        "custody_account_verified": False,
        "exact_version_integrity_verified": False,
        "compliance_retention_active": False,
        "independent_signature_verified": False,
    }
    try:
        identity = session.client("sts").get_caller_identity()
        if identity.get("Account") != custody_account:
            raise ArchiveDenied("wrong AWS evidence custody account")
        checks["custody_account_verified"] = True
        s3 = session.client("s3", region_name="eu-central-1")
        args = {
            "Bucket": bucket, "Key": key, "VersionId": version_id,
            "ExpectedBucketOwner": custody_account,
        }
        head = s3.head_object(**args)
        size = head.get("ContentLength")
        if type(size) is not int or not 1 <= size <= _MAX_PACKAGE:
            raise ArchiveDenied("invalid archive package size")
        retention = s3.get_object_retention(**args).get("Retention", {})
        until = retention.get("RetainUntilDate")
        checks["compliance_retention_active"] = (
            retention.get("Mode") == "COMPLIANCE"
            and isinstance(until, datetime) and until.tzinfo is not None
            and until.astimezone(timezone.utc) > now.astimezone(timezone.utc)
        )
        if not checks["compliance_retention_active"]:
            raise ArchiveDenied("archive version is not compliance locked")
        obj = s3.get_object(**args)
        stream = obj["Body"]
        try:
            raw = stream.read(_MAX_PACKAGE + 1)
        finally:
            stream.close()
        if len(raw) != size or hashlib.sha256(raw).hexdigest() != expected_package_sha256:
            raise ArchiveDenied("archived version digest mismatch")
        checks["exact_version_integrity_verified"] = True
        package = json.loads(raw)
        manifest = package.get("manifest") if isinstance(package, dict) else None
        if (not isinstance(manifest, dict) or manifest.get("tenant") != tenant
                or manifest.get("sequence") != sequence):
            raise ArchiveDenied("archive manifest does not match scope")
        verification = verify_bundle(
            bundle=package, trusted_public_key_raw=trusted_public_key_raw,
            pinned_fingerprint=pinned_fingerprint,
            trusted_head_sha256=trusted_manifest_head_sha256, clock=now,
        )
        checks["independent_signature_verified"] = verification.integrity_status == "PASS"
        if not checks["independent_signature_verified"]:
            raise ArchiveDenied("independent signature or head is invalid")
        return {
            "archive_integrity": "PASS",
            "assurance_status": "BLOCKED",
            "checks": checks,
            "zero_operator_access_proven": False,
        }
    except ArchiveDenied:
        return {
            "archive_integrity": "FAIL",
            "assurance_status": "BLOCKED",
            "checks": checks,
            "zero_operator_access_proven": False,
        }
    except Exception:
        return {
            "archive_integrity": "BLOCKED",
            "assurance_status": "BLOCKED",
            "checks": checks,
            "zero_operator_access_proven": False,
        }
