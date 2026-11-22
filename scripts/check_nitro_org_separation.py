"""SEC-07 read-only AWS Organizations separation check.

No write/decrypt/RunTask calls. Even different Organization IDs do not prove
absence of common beneficial owner, common account root, delegated admin or
other administrative access. Output deliberately remains BLOCKED.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from confidential.nitro_denial_matrix import validate_matrix
from confidential.nitro_organization_guard import (
    OrgBoundaryRejected, audit_organization_separation,
)


def blocked() -> dict:
    return {
        "status": "BLOCKED", "hardware_attestation_verified": False,
        "zero_operator_access_proven": False, "production_enabled": False,
        "reason": "AWS_organizations_and_real_administration_not_independently_proven",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true",
                      help="Offline; no AWS credentials or calls")
    mode.add_argument("--verify-live", action="store_true",
                      help="Read-only STS and Organizations calls")
    parser.add_argument("--matrix")
    parser.add_argument("--operator-profile")
    parser.add_argument("--custody-profile")
    args = parser.parse_args()
    try:
        if args.check:
            print(json.dumps(blocked(), sort_keys=True))
            return 2
        if not (args.matrix and args.operator_profile and args.custody_profile):
            raise OrgBoundaryRejected("live scope unavailable")
        with Path(args.matrix).open("rb") as file:
            source = file.read(32 * 1024 + 1)
        if not source or len(source) > 32 * 1024:
            raise OrgBoundaryRejected("matrix too large")
        matrix = validate_matrix(json.loads(source))
        result = audit_organization_separation(
            operator_profile=args.operator_profile,
            custody_profile=args.custody_profile,
            workload_account=matrix["workload_account"],
            custody_account=matrix["custody_account"],
        )
        report = {**result, **blocked()}
        report["distinct_organizations_observed"] = True
        print(json.dumps(report, sort_keys=True))
        return 2
    except Exception:
        print(json.dumps(blocked(), sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
