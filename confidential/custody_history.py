"""SEC-06 offline replay/audit of a synthetic custodian DynamoDB CAS ledger.

This verifier consumes an EXPORTED full set of DynamoDB AttributeValue maps.
It makes ZERO AWS calls. It does not establish that the export is exhaustive,
that the trust roots were independently obtained, or that any retired key is
actually denied by AWS KMS. Those remain mandatory out-of-band proofs.

Every signed event is re-verified with the public key pinned for the generation
that AUTHORIZED the transition; ROTATE uses the outgoing generation's signer.
The final state hash MUST be pinned outside the exported ledger.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from confidential.custody_ops import _utc, apply_signed_action, validate_state
from confidential.operator_boundary import BoundaryDenied, canonical_digest
from confidential.release_approval import public_key_fingerprint

_HEX = re.compile(r"[0-9a-f]{64}\Z")
_TENANT = re.compile(r"pilot0[12]\Z")
_STATE_ATTRS = frozenset({
    "tenant", "record", "state_json", "state_sha256", "revision", "generation",
})
_EVENT_ATTRS = frozenset({
    "tenant", "record", "event_json", "event_sha256", "previous_state_sha256",
    "new_state_sha256", "revision", "action", "retired_decrypt_key_arn",
})
_ACTIONS = frozenset({
    "ENROLL", "FREEZE", "UNFREEZE", "REVOKE", "ROTATE", "MARK_LOST",
})


def _deny(condition: bool, message: str) -> None:
    if not condition:
        raise BoundaryDenied(message)


def _no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        _deny(key not in result, "duplicate field in custody ledger JSON")
        result[key] = value
    return result


def _json_object(value: object) -> dict:
    _deny(isinstance(value, str) and len(value) <= 32768,
          "custody ledger JSON missing or oversized")
    try:
        parsed = json.loads(
            value, object_pairs_hook=_no_duplicate_keys,
            parse_constant=lambda v: (_ for _ in ()).throw(
                BoundaryDenied("invalid ledger JSON constant")))
    except BoundaryDenied:
        raise
    except (ValueError, TypeError, UnicodeError):
        raise BoundaryDenied("custody ledger JSON invalid") from None
    _deny(isinstance(parsed, dict), "custody ledger JSON must be an object")
    return parsed


def _s(item: dict, name: str) -> str:
    attr = item.get(name)
    _deny(isinstance(attr, dict) and set(attr) == {"S"} and
          isinstance(attr["S"], str), "invalid string DynamoDB attribute")
    return attr["S"]


def _n(item: dict, name: str) -> int:
    attr = item.get(name)
    _deny(isinstance(attr, dict) and set(attr) == {"N"} and
          isinstance(attr["N"], str) and
          re.fullmatch(r"(?:0|[1-9][0-9]*)", attr["N"]) is not None,
          "invalid numeric DynamoDB attribute")
    result = int(attr["N"])
    _deny(0 <= result <= 10_000_000, "custody revision outside review limit")
    return result


def verify_history(*, tenant: str, event_items: list[dict],
                   state_item: dict, trust_roots: dict[int, tuple[bytes, str]],
                   pinned_final_state_sha256: str,
                   clock: datetime | None = None) -> dict:
    """Reconstruct every revision, reject missing/reordered/forked/forged events.

    trust_roots must be provided independently: each generation has a
    (PEM public key bytes, externally pinned SHA256) tuple. Even when this
    returns chain_valid=True, the AWS authority/evidence status is BLOCKED.
    """
    _deny(isinstance(tenant, str) and _TENANT.fullmatch(tenant) is not None,
          "synthetic tenant required")
    _deny(isinstance(event_items, list) and 1 <= len(event_items) <= 10000,
          "complete custody history required")
    _deny(isinstance(state_item, dict) and set(state_item) == _STATE_ATTRS,
          "custody current-state ledger fields invalid")
    _deny(isinstance(pinned_final_state_sha256, str) and
          _HEX.fullmatch(pinned_final_state_sha256) is not None,
          "independently pinned final state hash required")
    _deny(isinstance(trust_roots, dict) and bool(trust_roots),
          "out-of-band generation trust roots required")
    now = clock if clock is not None else datetime.now(timezone.utc)
    _deny(isinstance(now, datetime) and now.tzinfo is not None,
          "timezone-aware replay clock required")
    now = now.astimezone(timezone.utc)

    partition = f"TENANT#{tenant}"
    _deny(_s(state_item, "tenant") == partition and
          _s(state_item, "record") == "STATE",
          "cross-tenant current-state ledger record")
    final = validate_state(_json_object(_s(state_item, "state_json")))
    final_sha = canonical_digest(final)
    _deny(final["tenant"] == tenant and
          _s(state_item, "state_sha256") == final_sha and
          final_sha == pinned_final_state_sha256 and
          _n(state_item, "revision") == final["revision"] and
          _n(state_item, "generation") == final["generation"],
          "current state does not match independently pinned anchor")

    current = None
    prior_issued = None
    retired = []
    generation_bindings = []
    observed_key_arns = set()

    for index, item in enumerate(event_items, 1):
        _deny(isinstance(item, dict) and set(item) == _EVENT_ATTRS,
              "custody event ledger fields invalid")
        _deny(_s(item, "tenant") == partition and
              _s(item, "record") == f"EVENT#{index:020d}" and
              _n(item, "revision") == index,
              "custody events missing, reordered or cross-tenant")
        envelope = _json_object(_s(item, "event_json"))
        _deny(set(envelope) == {"payload", "signature_b64"} and
              isinstance(envelope["payload"], dict),
              "custody event envelope invalid")
        payload = envelope["payload"]
        action = payload.get("action")
        _deny(isinstance(action, str) and action in _ACTIONS and
              _s(item, "action") == action and
              _s(item, "event_sha256") == canonical_digest(envelope),
              "custody event payload or digest changed")
        issued = _utc(payload.get("issued_at"))
        _deny(issued <= now and
              (prior_issued is None or issued >= prior_issued),
              "custody historical event time is not monotonic")
        prior_issued = issued
        generation = current["generation"] if current is not None else 1
        root = trust_roots.get(generation)
        _deny(isinstance(root, tuple) and len(root) == 2 and
              isinstance(root[0], bytes) and isinstance(root[1], str) and
              _HEX.fullmatch(root[1]) is not None and
              root[1] == public_key_fingerprint(root[0]),
              "missing or untrusted external generation signing pin")
        before_sha = canonical_digest(current) if current else "0" * 64
        _deny(_s(item, "previous_state_sha256") == before_sha,
              "custody historical state hash chain broken")
        next_state = apply_signed_action(
            current, envelope,
            trusted_public_key_pem=root[0],
            pinned_public_key_sha256=root[1], clock=issued)
        _deny(next_state["revision"] == index and
              _s(item, "new_state_sha256") == canonical_digest(next_state),
              "custody recorded transition hash incorrect")
        old_key = current["decrypt_key_arn"] if current else None
        retirement = item["retired_decrypt_key_arn"]
        if action == "ROTATE":
            _deny(retirement == {"S": old_key},
                  "rotated outgoing key omitted from custody inventory")
            _deny(next_state["generation"] == generation + 1,
                  "rotation generation invalid")
        else:
            _deny(retirement == {"NULL": True},
                  "unexpected historical key retirement marker")

        if current is None or action == "ROTATE":
            _deny(next_state["decrypt_key_arn"] not in observed_key_arns and
                  next_state["signing_key_arn"] not in observed_key_arns,
                  "old custody key reused in a later generation")
            observed_key_arns.add(next_state["decrypt_key_arn"])
            observed_key_arns.add(next_state["signing_key_arn"])
            generation_bindings.append({
                name: next_state[name] for name in (
                    "generation", "decrypt_key_arn", "signing_key_arn",
                    "pcr17", "task_definition_arn", "release_sha256",
                    "key_policy_sha256",
                )
            })
        if action == "ROTATE":
            retired.append(old_key)
        current = next_state

    _deny(current == final and current["revision"] == len(event_items),
          "custody historical replay differs from final state")
    expected_generations = set(range(1, current["generation"] + 1))
    _deny(set(trust_roots) == expected_generations,
          "custody rotated trust roots missing or extra")
    for generation, root in trust_roots.items():
        _deny(isinstance(root, tuple) and len(root) == 2 and
              isinstance(root[0], bytes) and isinstance(root[1], str) and
              _HEX.fullmatch(root[1]) is not None and
              root[1] == public_key_fingerprint(root[0]),
              "rotated trust root not independently pinned")
    _deny(len({root[1] for root in trust_roots.values()}) ==
          len(trust_roots), "signing trust root reused across generations")
    _deny(len(retired) == current["generation"] - 1,
          "historic decrypt-key generation inventory incomplete")

    return {
        "schema": "notarai.confidential.custody-history-check.v1",
        "tenant": tenant,
        "workload_account": final["workload_account"],
        "custody_account": final["custody_account"],
        "generation_bindings": generation_bindings,
        "final_revision": current["revision"],
        "final_generation": current["generation"],
        "final_state": current["state"],
        "final_state_sha256": final_sha,
        "events_replayed": len(event_items),
        "distinct_signing_trust_roots_checked": len(trust_roots),
        "historical_decrypt_key_arns": retired,
        "current_decrypt_key_arn": current["decrypt_key_arn"],
        "offline_chain_integrity_checked": True,
        "independent_ledger_export_completeness_verified": False,
        "independent_trust_root_provenance_verified": False,
        "historical_keys_effectively_denied_verified": False,
        "historical_event_commit_times_verified": False,
        "can_authorize_decrypt": False,
        "aws_calls": 0,
        "independent_custody_verified": False,
        "status": "BLOCKED_PENDING_INDEPENDENT_EVIDENCE",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history-file", required=True,
                        help="JSON export with state_item and event_items")
    parser.add_argument("--tenant", choices=("pilot01", "pilot02"),
                        required=True)
    parser.add_argument("--pinned-final-sha256", required=True,
                        help="Independent final-state SHA256, not from export")
    parser.add_argument("--trust-roots-file", required=True,
                        help="Independent JSON mapping generation to {pem_file, sha256}")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        data = _json_object(Path(args.history_file).read_text("utf-8"))
        if set(data) != {"state_item", "event_items"}:
            raise BoundaryDenied("history export schema invalid")
        roots_manifest = _json_object(Path(args.trust_roots_file).read_text("utf-8"))
        roots = {}
        for key, item in roots_manifest.items():
            if (not re.fullmatch(r"[1-9][0-9]*", key) or
                    not isinstance(item, dict) or
                    set(item) != {"pem_file", "sha256"}):
                raise BoundaryDenied("independent trust root manifest invalid")
            roots[int(key)] = (
                Path(item["pem_file"]).read_bytes(), item["sha256"])
        result = verify_history(
            tenant=args.tenant, state_item=data["state_item"],
            event_items=data["event_items"], trust_roots=roots,
            pinned_final_state_sha256=args.pinned_final_sha256)
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                     0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(result, f, sort_keys=True, indent=2)
            f.write("\n")
    except (OSError, TypeError, ValueError, BoundaryDenied) as exc:
        print(json.dumps({
            "status": "BLOCKED",
            "reason": str(exc) if isinstance(
                exc, BoundaryDenied) else "custody history input/output invalid",
            "aws_calls": 0,
        }))
        return 2
    print(json.dumps({
        "status": result["status"],
        "events_replayed": result["events_replayed"],
        "offline_chain_integrity_checked": True,
        "aws_calls": 0,
        "independent_custody_verified": False,
    }))
    return 3  # Even valid replay cannot release/activate customer data.


if __name__ == "__main__":
    raise SystemExit(main())
