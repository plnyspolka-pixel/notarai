#!/usr/bin/env python3
"""SEC-11 operator deny probe. NEVER run without prior custodian approval.

Two write attempts use only the dedicated synthetic fixture key/version.
The test does not clean up an unexpected success, because doing so could hide
a violation or bypass WORM retention. This script is NOT part of CI.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from confidential.custody_denial_probe import ProbeDenied, probe_operator_denials


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--operator-account", required=True)
    p.add_argument("--custody-account", required=True)
    p.add_argument("--bucket", required=True)
    p.add_argument("--fixture-key", required=True,
                   help="sec11-fixture/ followed by 8-64 lowercase digits/hyphens")
    p.add_argument("--fixture-version", required=True,
                   help="custodian-provided existing synthetic S3 VersionId")
    p.add_argument("--operator-profile", required=True,
                   help="separate AWS CLI profile belonging to NotarAI operator account")
    p.add_argument("--authorize-synthetic-write-probes", action="store_true",
                   help="confirm explicit prior written consent of the independent custodian")
    args = p.parse_args(argv)
    if not args.authorize_synthetic_write_probes:
        print(json.dumps({
            "status": "BLOCKED",
            "reason": "EXPLICIT_CUSTODIAN_AUTHORIZATION_REQUIRED",
            "zero_operator_access_proven": False,
        }, sort_keys=True))
        return 4
    try:
        import boto3
        session = boto3.Session(
            profile_name=args.operator_profile, region_name="eu-central-1"
        )
        result = probe_operator_denials(
            session=session, operator_account=args.operator_account,
            custody_account=args.custody_account, bucket=args.bucket,
            fixture_key=args.fixture_key, fixture_version=args.fixture_version,
            authorized=True,
        )
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        if result["permission_denials_verified"]:
            return 4  # still requires independent full audit for Zero Operator
        return 2
    except Exception:
        print(json.dumps({
            "status": "BLOCKED", "reason": "PROBE_NOT_VERIFIED",
            "zero_operator_access_proven": False,
        }, sort_keys=True))
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
