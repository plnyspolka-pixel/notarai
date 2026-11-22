#!/usr/bin/env python3
"""SEC-11 independent evidence archive verifier (opt-in, read-only AWS).

Obtain the public Ed25519 RAW key, its fingerprint, manifest HEAD digest,
and exact archive package SHA-256 from an OUT-OF-BAND custodian channel.
This script has no AWS write path and never outputs signed package contents.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from confidential.evidence_archive import ArchiveDenied, verify_archive_version


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--custody-account", required=True)
    p.add_argument("--bucket", required=True)
    p.add_argument("--tenant", required=True)
    p.add_argument("--sequence", required=True, type=int)
    p.add_argument("--version", required=True)
    p.add_argument("--expected-package-sha256", required=True)
    p.add_argument("--trusted-public-key", required=True, type=Path)
    p.add_argument("--pinned-fingerprint", required=True)
    p.add_argument("--trusted-manifest-head-sha256", required=True)
    p.add_argument("--custody-auditor-profile", required=True)
    p.add_argument("--run-read-only", action="store_true",
                   help="explicitly allow STS and S3 GET/HEAD API queries")
    args = p.parse_args(argv)
    if not args.run_read_only:
        print(json.dumps({
            "archive_integrity": "UNVERIFIED", "assurance_status": "BLOCKED",
            "zero_operator_access_proven": False,
        }, sort_keys=True))
        return 4
    try:
        import boto3
        raw_key = args.trusted_public_key.read_bytes()
        if len(raw_key) != 32:
            raise ArchiveDenied("independent key invalid")
        session = boto3.Session(
            profile_name=args.custody_auditor_profile, region_name="eu-central-1"
        )
        report = verify_archive_version(
            session=session, custody_account=args.custody_account,
            bucket=args.bucket, tenant=args.tenant, sequence=args.sequence,
            version_id=args.version,
            expected_package_sha256=args.expected_package_sha256,
            trusted_public_key_raw=raw_key,
            pinned_fingerprint=args.pinned_fingerprint,
            trusted_manifest_head_sha256=args.trusted_manifest_head_sha256,
        )
    except Exception:
        report = {
            "archive_integrity": "BLOCKED", "assurance_status": "BLOCKED",
            "zero_operator_access_proven": False,
        }
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    # A verified archived signature never means completed Zero Operator
    # or independent account/role trust attestation.
    return 2 if report["archive_integrity"] == "FAIL" else 4


if __name__ == "__main__":
    raise SystemExit(main())
