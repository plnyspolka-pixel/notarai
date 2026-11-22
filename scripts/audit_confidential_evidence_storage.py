#!/usr/bin/env python3
"""SEC-11 read-only AWS WORM audit, exclusively for independent custodian.

No AWS write APIs. Does not attempt overwrite/delete denial, and hence never
reports verified Zero Operator Access even when the configuration looks safe.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from confidential.custody_storage import (
    StorageAuditRejected, assess_custody_storage, read_only_inventory,
    read_only_fixture_retention,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--custody-account", required=True, help="12-digit independent AWS account")
    parser.add_argument("--operator-account", required=True, help="12-digit NotarAI AWS account")
    parser.add_argument("--bucket", required=True, help="independent evidence bucket")
    parser.add_argument("--profile", help="optional AWS CLI SSO profile of independent custodian")
    parser.add_argument("--min-retention-days", type=int, default=30)
    parser.add_argument("--fixture-key", help="optional synthetic fixture key for retention check")
    parser.add_argument("--fixture-version", help="optional existing fixture S3 VersionId")
    parser.add_argument("--run-read-only", action="store_true",
                        help="explicitly enable STS/S3 read-only queries")
    args = parser.parse_args(argv)
    if bool(args.fixture_key) != bool(args.fixture_version):
        parser.error("fixture key and version must be supplied together")
    if not args.run_read_only:
        print(json.dumps({
            "configuration_status": "UNVERIFIED", "assurance_status": "BLOCKED",
            "zero_operator_access_proven": False, "reason": "AWS_READ_NOT_RUN",
        }, sort_keys=True))
        return 4
    try:
        import boto3
        session = boto3.Session(
            profile_name=args.profile, region_name="eu-central-1"
        ) if args.profile else boto3.Session(region_name="eu-central-1")
        identity, data = read_only_inventory(
            session, bucket=args.bucket, custody_account=args.custody_account
        )
        report = assess_custody_storage(
            identity=identity, custody_account=args.custody_account,
            operator_account=args.operator_account, bucket=args.bucket,
            data=data, required_retention_days=args.min_retention_days,
        )
        result = report.as_dict()
        if args.fixture_key and report.configuration_status == "PASS":
            fixture = read_only_fixture_retention(
                session, bucket=args.bucket, custody_account=args.custody_account,
                fixture_key=args.fixture_key, fixture_version=args.fixture_version,
            )
            result["fixture_checks"] = fixture
            if not all(fixture.values()):
                result["configuration_status"] = "FAIL"
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 4 if result["configuration_status"] == "PASS" else 2
    except (StorageAuditRejected, Exception):
        # Never echo AWS exceptions (may include identifiers or policy snippets).
        print(json.dumps({
            "configuration_status": "FAIL", "assurance_status": "BLOCKED",
            "zero_operator_access_proven": False, "reason": "READ_ONLY_AUDIT_FAILED",
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
