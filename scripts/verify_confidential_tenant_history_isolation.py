"""SEC-06: verify lifetime two-tenant isolation across ALL signed generations.

Current-state comparison is insufficient: a KMS key retired by pilot01 may
be reused as pilot02's new key. Replay BOTH independently anchored histories,
then refuse cross-tenant reuse of ANY historical decrypt/signing key ARN,
PCR17, release hash, task definition or key policy binding. The external
custodian's trust-root fingerprints must also be different between tenants.

Offline-only. No AWS access, no key mutation, no data decrypt or release.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from confidential.custody_history import verify_history, _json_object
from confidential.operator_boundary import BoundaryDenied


def _hist(name: str, data: dict, clock: datetime | None) -> dict:
    if not isinstance(data, dict) or set(data) != {
        "event_items", "state_item", "trust_roots",
        "pinned_final_state_sha256",
    }:
        raise BoundaryDenied("two complete independently pinned histories required")
    return verify_history(
        tenant=name, event_items=data["event_items"],
        state_item=data["state_item"], trust_roots=data["trust_roots"],
        pinned_final_state_sha256=data["pinned_final_state_sha256"],
        clock=clock)


def verify_lifetime_isolation(*, pilot01: dict, pilot02: dict,
                              clock: datetime | None = None) -> dict:
    """Return a non-authoritative offline overlap audit for two pilots."""
    r1 = _hist("pilot01", pilot01, clock)
    r2 = _hist("pilot02", pilot02, clock)
    if (r1["workload_account"] != r2["workload_account"] or
            r1["custody_account"] != r2["custody_account"]):
        raise BoundaryDenied("custody pilot account ownership differs")
    groups = [r1["generation_bindings"], r2["generation_bindings"]]
    if not all(isinstance(x, list) and x for x in groups):
        raise BoundaryDenied("complete generation inventories required")
    for field in ("pcr17", "task_definition_arn", "release_sha256",
                  "key_policy_sha256"):
        values = [{record[field] for record in group} for group in groups]
        if values[0] & values[1]:
            raise BoundaryDenied("cross-tenant historical security binding reused")
    all_keys = [
        {arn for item in group for arn in (
            item["decrypt_key_arn"], item["signing_key_arn"])}
        for group in groups
    ]
    if all_keys[0] & all_keys[1]:
        raise BoundaryDenied("cross-tenant historical KMS decrypt/sign key reused")
    all_pins = []
    for data in (pilot01, pilot02):
        roots = data["trust_roots"]
        all_pins.append({root[1] for root in roots.values()})
    if all_pins[0] & all_pins[1]:
        raise BoundaryDenied("cross-tenant custodian P-256 trust root reused")
    return {
        "schema": "notarai.confidential.lifetime-isolation.v1",
        "tenant_count": 2,
        "history_event_counts": {
            "pilot01": r1["events_replayed"],
            "pilot02": r2["events_replayed"],
        },
        "generation_counts": {
            "pilot01": r1["final_generation"],
            "pilot02": r2["final_generation"],
        },
        "lifetime_cross_tenant_key_overlap": False,
        "lifetime_cross_tenant_signing_root_overlap": False,
        "lifetime_cross_tenant_pcr_release_overlap": False,
        "offline_signed_histories_checked": True,
        "aws_calls": 0,
        "independent_custody_verified": False,
        "all_live_kms_grants_audited": False,
        "live_cross_tenant_decrypt_denial_verified": False,
        "can_authorize_decrypt": False,
        "status": "BLOCKED_PENDING_INDEPENDENT_AWS_EVIDENCE",
    }


def _load_history(path: str, roots_path: str, final_sha: str) -> dict:
    parsed = _json_object(Path(path).read_text("utf-8"))
    if set(parsed) != {"state_item", "event_items"}:
        raise BoundaryDenied("custody export schema invalid")
    manifest = _json_object(Path(roots_path).read_text("utf-8"))
    roots = {}
    for key, value in manifest.items():
        if (not isinstance(key, str)
                or re.fullmatch(r"[1-9][0-9]*", key) is None
                or not isinstance(value, dict)
                or set(value) != {"pem_file", "sha256"}):
            raise BoundaryDenied("independent signing root manifest invalid")
        roots[int(key)] = (
            Path(value["pem_file"]).read_bytes(), value["sha256"])
    return {
        "event_items": parsed["event_items"],
        "state_item": parsed["state_item"],
        "trust_roots": roots,
        "pinned_final_state_sha256": final_sha,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for pilot in ("pilot01", "pilot02"):
        parser.add_argument(f"--{pilot}-history", required=True)
        parser.add_argument(f"--{pilot}-trust-roots", required=True)
        parser.add_argument(f"--{pilot}-final-sha256", required=True)
    parser.add_argument("--output", required=True,
                        help="Create-only JSON report, file mode 0600")
    args = parser.parse_args(argv)
    try:
        result = verify_lifetime_isolation(
            pilot01=_load_history(
                args.pilot01_history, args.pilot01_trust_roots,
                args.pilot01_final_sha256),
            pilot02=_load_history(
                args.pilot02_history, args.pilot02_trust_roots,
                args.pilot02_final_sha256))
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(result, f, sort_keys=True, indent=2)
            f.write("\n")
    except (OSError, ValueError, TypeError, BoundaryDenied) as exc:
        print(json.dumps({
            "status": "BLOCKED",
            "reason": str(exc) if isinstance(
                exc, BoundaryDenied) else "tenant history evidence unavailable",
            "aws_calls": 0,
        }))
        return 2
    print(json.dumps({
        "status": result["status"],
        "offline_signed_histories_checked": True,
        "aws_calls": 0, "independent_custody_verified": False,
    }))
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
