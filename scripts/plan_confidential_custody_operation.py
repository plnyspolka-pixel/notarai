"""SEC-06: offline custody operation planner (NO AWS calls, NO approvals).

Generates an unsigned, tenant-bound action request and a non-executable KMS
policy change target for the independent custodian to review. Never updates
KMS, assumes an AWS role, signs, decrypts, or approves a release.

Example:
  python scripts/plan_confidential_custody_operation.py \
    --state /secure/pilot01-state.json --action FREEZE \
    --output /secure/pilot01-freeze-plan.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from confidential.custody_ops import (
    _EVENT_SCHEMA, _IDENTITY_FIELDS, _ROTATION_FIELDS,
    render_kms_policy_target, validate_state,
)
from confidential.operator_boundary import BoundaryDenied, canonical_digest
from scripts.custodian_sign_confidential_operation import _validate_intent

_TERMINAL = {"REVOKE", "MARK_LOST"}


def plan_operation(*, action: str, tenant: str,
                   state: dict | None = None, changes: dict | None = None,
                   clock: datetime | None = None, ttl_minutes: int = 15) -> dict:
    """Generate a request, not a grant/permission or completed transition.

    The external custodian must validate state revision atomically at signing
    time and after signature at independent policy-application time.
    """
    now = clock if clock is not None else datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise BoundaryDenied("timezone-aware planning clock required")
    now = now.astimezone(timezone.utc)
    if type(ttl_minutes) is not int or not 1 <= ttl_minutes <= 60:
        raise BoundaryDenied("custody operation TTL must be between 1 and 60 minutes")
    if state is not None:
        state = validate_state(state)
    supplied = {} if changes is None else changes
    if not isinstance(supplied, dict):
        raise BoundaryDenied("custody change set must be an object")
    if state is not None and tenant != state["tenant"]:
        raise BoundaryDenied("tenant does not match custody state")
    payload = {
        "schema": _EVENT_SCHEMA,
        "action": action,
        "tenant": tenant,
        "previous_sha256": (
            canonical_digest(state) if state is not None else "0" * 64),
        "revision": (state["revision"] + 1 if state is not None else 1),
        "issued_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": (now + timedelta(minutes=ttl_minutes)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "changes": supplied,
    }
    expected_signer = _validate_intent(payload, state, now)

    # Never call apply_signed_action here: unsigned intents cannot advance
    # custody. Only a signature plus an independently maintained CAS ledger
    # may do so.
    if action == "ENROLL":
        target = validate_state({
            **supplied, "schema": "notarai.confidential.custody-state.v1",
            "state": "ACTIVE", "generation": 1, "revision": 1,
        })
    elif action in {"FREEZE", "REVOKE", "MARK_LOST", "UNFREEZE"}:
        target = dict(state)
        target["revision"] += 1
        target["state"] = {
            "FREEZE": "FROZEN", "REVOKE": "REVOKED",
            "MARK_LOST": "LOST", "UNFREEZE": "ACTIVE",
        }[action]
    else:
        # Rotation requires a new decrypt and signer key. The target stays
        # frozen until the independent custodian executes a fresh UNFREEZE.
        target = dict(state)
        target.update(supplied)
        target["generation"] += 1
        target["revision"] += 1
    target = validate_state(target)
    suggested_policy = render_kms_policy_target(target)
    # KMS keys from *earlier* generations survive state rotation. An
    # independent custodian must deny Decrypt on the outgoing key AND audit
    # every historical key recorded in the authoritative custody ledger.
    # The new key stays deny-only throughout ROTATE. One future UNFREEZE
    # must not re-enable any old ciphertext recipient.
    policy_targets = []
    if action == "ROTATE":
        outgoing = render_kms_policy_target(state)
        policy_targets.append({
            "key_arn": state["decrypt_key_arn"],
            "intent": "RETAIN_DENY_ON_OUTGOING_KEY",
            "target_policy": outgoing["target_policy"],
            "target_policy_sha256": outgoing["target_policy_sha256"],
            "requires_no_grants": True,
        })
    policy_targets.append({
        "key_arn": target["decrypt_key_arn"],
        "intent": ("DENY_UNTIL_INDEPENDENT_UNFREEZE"
                   if action == "ROTATE" else
                   "SET_POLICY_FOR_APPROVED_LIFECYCLE_STATE"),
        "target_policy": suggested_policy["target_policy"],
        "target_policy_sha256": suggested_policy["target_policy_sha256"],
        "requires_no_grants": True,
    })
    return {
        "schema": "notarai.confidential.custody-plan.v1",
        "unsigned_event_payload": payload,
        "expected_pre_state_sha256": payload["previous_sha256"],
        "expected_post_state_sha256": canonical_digest(target),
        "expected_kms_policy_sha256": suggested_policy["target_policy_sha256"],
        "proposed_key_policy": suggested_policy["target_policy"],
        "required_kms_key_policy_targets": policy_targets,
        "historical_decrypt_key_inventory_complete": False,
        "historical_keys_effectively_denied_verified": False,
        "expected_signing_key_arn": expected_signer,
        "custodian_independent_signature_required": True,
        "custodian_ledger_compare_and_swap_required": True,
        "kms_policy_write_performed": False,
        "kms_grants_checked": False,
        "aws_calls": 0,
        "authorized_for_decrypt": False,
        "independent_custody_verified": False,
        "release_frozen_after_planning": False,
        "instructions": (
            "Unsigned proposal only. External custodian must verify current "
            "KMS policy, all grants and independent ledger revision, then "
            "sign, persist via CAS and apply new KMS controls. For a freeze "
            "or revocation, remove effective Decrypt/grants immediately and "
            "test denial. During ROTATE, verify BOTH outgoing and incoming "
            "keys, plus ALL historical decrypt keys from independent ledger; "
            "application state alone does not revoke KMS."
        ),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", help="Current approved custodian state JSON")
    parser.add_argument("--action", required=True,
                        choices=["ENROLL", "FREEZE", "UNFREEZE",
                                 "REVOKE", "ROTATE", "MARK_LOST"])
    parser.add_argument("--tenant", help="Required on ENROLL, otherwise must match state")
    parser.add_argument("--changes", help="JSON file with full bindings for ENROLL, rotation fields for ROTATE")
    parser.add_argument("--ttl-minutes", type=int, default=15)
    parser.add_argument("--output", required=True,
                        help="New local JSON file, created with permissions 0600")
    args = parser.parse_args(argv)
    try:
        current = (json.loads(Path(args.state).read_text(encoding="utf-8"))
                   if args.state else None)
        changes = (json.loads(Path(args.changes).read_text(encoding="utf-8"))
                   if args.changes else {})
        tenant = args.tenant or (current or {}).get("tenant", "")
        plan = plan_operation(
            action=args.action, tenant=tenant, state=current,
            changes=changes, ttl_minutes=args.ttl_minutes)
        fd = os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(plan, f, sort_keys=True, indent=2)
            f.write("\n")
    except (OSError, json.JSONDecodeError, BoundaryDenied) as exc:
        reason = str(exc) if isinstance(exc, BoundaryDenied) else "planning input/output unavailable"
        print(json.dumps({"status": "BLOCKED", "reason": reason, "aws_calls": 0}))
        return 2
    print(json.dumps({"status": "PLANNED_ONLY", "aws_calls": 0,
                      "requires_independent_approval": True,
                      "kms_policy_write_performed": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
