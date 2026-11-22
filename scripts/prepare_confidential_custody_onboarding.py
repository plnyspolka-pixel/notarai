"""SEC-06: synthetic two-tenant onboarding plan, never provisions AWS.

Read two independently reviewed JSON binding objects; output an unsigned
approval package for pilot01 and pilot02. Does not assume that different AWS
accounts imply independent custody. It does NOT sign a release or issue grants.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from confidential.custody_ops import (
    _IDENTITY_FIELDS, _SCHEMA, validate_pilot_inventory, validate_state,
)
from confidential.operator_boundary import BoundaryDenied
from scripts.plan_confidential_custody_operation import plan_operation


def prepare_two_tenant_onboarding(*, bindings: list[dict],
                                  clock: datetime | None = None) -> dict:
    if not isinstance(bindings, list) or len(bindings) != 2:
        raise BoundaryDenied("exactly two approved synthetic tenant bindings required")
    states = []
    for binding in bindings:
        if not isinstance(binding, dict) or set(binding) != _IDENTITY_FIELDS:
            raise BoundaryDenied("tenant binding schema invalid")
        states.append(validate_state({
            **binding, "schema": _SCHEMA, "state": "FROZEN",
            "generation": 1, "revision": 1,
        }))
    checked = validate_pilot_inventory(states)
    # No KMS provisioning or KMS grant: these are independent review packages.
    plans = [
        plan_operation(
            action="ENROLL", tenant=s["tenant"],
            changes={name: s[name] for name in _IDENTITY_FIELDS},
            clock=clock,
        )
        for s in sorted(states, key=lambda x: x["tenant"])
    ]
    return {
        "schema": "notarai.confidential.two-tenant-onboarding.v1",
        "tenant_count": checked["tenant_count"],
        "review_packages": plans,
        "separate_approval_for_each_tenant": True,
        "cross_tenant_key_reuse_denied": True,
        "aws_calls": 0,
        "kms_resources_created": False,
        "signing_performed": False,
        "independent_custody_verified": False,
        "actual_onboarding_complete": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot01-binding", required=True)
    parser.add_argument("--pilot02-binding", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        bindings = [
            json.loads(Path(file).read_text("utf-8"))
            for file in (args.pilot01_binding, args.pilot02_binding)
        ]
        result = prepare_two_tenant_onboarding(bindings=bindings)
        fd = os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(result, f, sort_keys=True, indent=2)
            f.write("\n")
    except (BoundaryDenied, OSError, json.JSONDecodeError) as exc:
        reason = str(exc) if isinstance(exc, BoundaryDenied) else "input/output unavailable"
        print(json.dumps({"status": "BLOCKED", "reason": reason, "aws_calls": 0}))
        return 2
    print(json.dumps({
        "status": "UNSIGNED_PLANS_ONLY", "tenant_count": 2,
        "aws_calls": 0, "kms_resources_created": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
