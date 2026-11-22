"""SEC-06: read-only audit of EVERY decrypt KMS key in signed custody history.

The current key alone is insufficient after ROTATE: a retired key may still
decrypt old ciphertext. This tool first replays the complete signed event
chain with externally pinned trust roots and final state SHA, then audits
each retired key with a deny-only policy and zero KMS grants, and finally
audits the current key against the custodian's approved lifecycle policy.

Nothing here deploys AWS, changes permissions, performs Decrypt or authorizes
UNFREEZE. A successful read-only snapshot is still BLOCKED pending independently
signed account ownership and live negative-decrypt/hardware evidence.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from confidential.custody_history import _json_object, _s, verify_history
from confidential.custody_ops import validate_state
from confidential.operator_boundary import BoundaryDenied, canonical_digest
from scripts.verify_confidential_custody_kms import inspect as inspect_kms


def audit_all_generations(
    *,
    tenant: str,
    event_items: list[dict],
    state_item: dict,
    trust_roots: dict[int, tuple[bytes, str]],
    pinned_final_state_sha256: str,
    custody_profile: str,
    check: bool = False,
    clock: datetime | None = None,
    session_factory=None,
) -> dict:
    """Validate signed chain before requesting any AWS KMS data."""
    history = verify_history(
        tenant=tenant, event_items=event_items, state_item=state_item,
        trust_roots=trust_roots,
        pinned_final_state_sha256=pinned_final_state_sha256, clock=clock)
    final = validate_state(_json_object(_s(state_item, "state_json")))
    if not isinstance(custody_profile, str) or not custody_profile.strip():
        raise BoundaryDenied("independent custody KMS audit profile required")
    retired = history["historical_decrypt_key_arns"]
    current_arn = history["current_decrypt_key_arn"]
    if (
        not isinstance(retired, list)
        or any(not isinstance(arn, str) for arn in retired)
        or len(set(retired)) != len(retired)
        or current_arn in retired
        or len(retired) != final["generation"] - 1
        or final["decrypt_key_arn"] != current_arn
    ):
        raise BoundaryDenied("historical KMS key inventory invalid")
    if not check:
        return {
            "schema": "notarai.confidential.all-generation-kms-audit.v1",
            "status": "BLOCKED",
            "mode": "dry-run",
            "tenant": tenant,
            "expected_key_count": len(retired) + 1,
            "retired_key_count": len(retired),
            "aws_calls": 0,
            "offline_chain_integrity_checked": True,
            "all_generations_read_only_snapshots_checked": False,
            "historical_keys_effectively_denied_verified": False,
            "independent_custody_verified": False,
            "kms_decrypt_performed": False,
        }

    snapshots = []
    for arn in retired:
        retired_state = {
            **final,
            "decrypt_key_arn": arn,
            "state": "FROZEN",
        }
        # FROZEN requires exactly the custodian-only/public-key-only policy,
        # no Decrypt principal and NO grants. The archived state is used
        # only to select the old physical key, not to restore old access.
        result = inspect_kms(
            state=retired_state, custody_profile=custody_profile, check=True,
            session_factory=session_factory)
        if (
            result.get("kms_policy_snapshot_checked") is not True
            or result.get("kms_grants_fully_enumerated") is not True
            or result.get("kms_grant_count") != 0
            or result.get("kms_decrypt_performed") is not False
            or result.get("independent_custody_verified") is not False
        ):
            raise BoundaryDenied("retired KMS snapshot did not meet deny-only baseline")
        snapshots.append({
            "key_arn": arn,
            "role": "retired",
            "policy_sha256": result["kms_policy_sha256"],
            "static_deny_only_snapshot_checked": True,
        })
    current_result = inspect_kms(
        state=final, custody_profile=custody_profile, check=True,
        session_factory=session_factory)
    if (
        current_result.get("kms_policy_snapshot_checked") is not True
        or current_result.get("kms_grants_fully_enumerated") is not True
        or current_result.get("kms_grant_count") != 0
        or current_result.get("kms_decrypt_performed") is not False
        or current_result.get("independent_custody_verified") is not False
    ):
        raise BoundaryDenied("current KMS snapshot did not match custody lifecycle")
    snapshots.append({
        "key_arn": current_arn,
        "role": "current",
        "policy_sha256": current_result["kms_policy_sha256"],
        "static_deny_only_snapshot_checked": final["state"] != "ACTIVE",
    })
    if len(snapshots) != final["generation"]:
        raise BoundaryDenied("KMS generation snapshot coverage incomplete")
    return {
        "schema": "notarai.confidential.all-generation-kms-audit.v1",
        "status": "BLOCKED_PENDING_EXTERNAL_CUSTODY_EVIDENCE",
        "mode": "read-only",
        "tenant": tenant,
        "final_state_sha256": canonical_digest(final),
        "final_generation": final["generation"],
        "final_lifecycle_state": final["state"],
        "retired_key_count": len(retired),
        "kms_key_snapshots_checked": len(snapshots),
        "kms_key_snapshots": snapshots,
        "offline_chain_integrity_checked": True,
        "all_generations_read_only_snapshots_checked": True,
        "historical_keys_effectively_denied_verified": False,
        "live_negative_decrypt_for_every_generation": False,
        "independent_custody_verified": False,
        "kms_decrypt_performed": False,
        "kms_write_performed": False,
        "aws_calls": "read-only",
        "warning": (
            "A snapshot is eventually consistent and does not prove that no "
            "other IAM identity, previous grant, or earlier event can decrypt. "
            "Every-generation negative tests and independent signed AWS "
            "audit evidence remain mandatory."
        ),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history-file", required=True)
    parser.add_argument("--tenant", required=True, choices=("pilot01", "pilot02"))
    parser.add_argument("--trust-roots-file", required=True)
    parser.add_argument("--pinned-final-sha256", required=True)
    parser.add_argument("--custody-profile", required=True)
    parser.add_argument("--check", action="store_true",
                        help="Explicit opt-in: read-only live KMS key and grant queries")
    parser.add_argument("--output", required=True,
                        help="Create-only JSON report, permissions 0600")
    args = parser.parse_args(argv)
    try:
        from confidential.custody_history import _json_object
        data = _json_object(Path(args.history_file).read_text("utf-8"))
        if set(data) != {"state_item", "event_items"}:
            raise BoundaryDenied("custody history export schema invalid")
        roots_manifest = _json_object(
            Path(args.trust_roots_file).read_text("utf-8"))
        roots = {}
        for index, item in roots_manifest.items():
            if (
                not isinstance(index, str)
                or not index.isdigit()
                or not isinstance(item, dict)
                or set(item) != {"pem_file", "sha256"}
            ):
                raise BoundaryDenied("custody generation trust manifest invalid")
            roots[int(index)] = (
                Path(item["pem_file"]).read_bytes(), item["sha256"])
        result = audit_all_generations(
            tenant=args.tenant,
            event_items=data["event_items"],
            state_item=data["state_item"],
            trust_roots=roots,
            pinned_final_state_sha256=args.pinned_final_sha256,
            custody_profile=args.custody_profile,
            check=args.check)
        fd = os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as report:
            json.dump(result, report, sort_keys=True, indent=2)
            report.write("\n")
    except (OSError, ValueError, TypeError, BoundaryDenied) as exc:
        reason = (str(exc) if isinstance(exc, BoundaryDenied)
                  else "custody KMS all-generation evidence unavailable")
        print(json.dumps({"status": "BLOCKED", "reason": reason,
                          "independent_custody_verified": False}))
        return 2
    print(json.dumps({
        "status": result["status"],
        "tenant": args.tenant,
        "checked_key_count": result.get("kms_key_snapshots_checked", 0),
        "aws_calls": result["aws_calls"],
        "independent_custody_verified": False,
    }))
    return 3 if args.check else 0


if __name__ == "__main__":
    raise SystemExit(main())
