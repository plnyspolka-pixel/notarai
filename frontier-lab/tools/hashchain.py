#!/usr/bin/env python3
"""SHA-256 hash-chain example, NOT signed or externally witnessed; not a secure audit service."""
import copy
import hashlib
import json
import sys

GENESIS = "0" * 64
ALLOWED_KINDS = {"policy_check", "sandbox_started", "audit_finished", "job_stopped"}


def canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def add_entry(chain: list[dict], event: dict) -> dict:
    if not isinstance(chain, list) or not isinstance(event, dict):
        raise ValueError("chain and event have invalid types")
    if set(event) != {"kind", "synthetic_task_id", "status"} or event["kind"] not in ALLOWED_KINDS:
        raise ValueError("invalid event structure")
    if not all(isinstance(event[key], str) and 0 < len(event[key]) <= 100 for key in ("kind", "synthetic_task_id", "status")):
        raise ValueError("invalid event values")
    if not event["synthetic_task_id"].startswith("demo-"):
        raise ValueError("only synthetic demo task ids are allowed")
    if not verify(chain):
        raise ValueError("refuse to append to a broken chain")
    prev = chain[-1]["hash"] if chain else GENESIS
    payload = {"sequence": len(chain), "previous_hash": prev, "event": copy.deepcopy(event)}
    payload["hash"] = hashlib.sha256(canonical(payload)).hexdigest()
    chain.append(payload)
    return copy.deepcopy(payload)


def verify(chain: list[dict]) -> bool:
    if not isinstance(chain, list):
        return False
    prev = GENESIS
    for seq, item in enumerate(chain):
        if not isinstance(item, dict) or set(item) != {"sequence", "previous_hash", "event", "hash"}:
            return False
        if type(item["sequence"]) is not int or item["sequence"] != seq or item["previous_hash"] != prev:
            return False
        try:
            check_hash = hashlib.sha256(canonical({k: v for k, v in item.items() if k != "hash"})).hexdigest()
        except (ValueError, TypeError):
            return False
        if not isinstance(item["hash"], str) or item["hash"] != check_hash:
            return False
        prev = item["hash"]
    return True


def demo() -> dict:
    chain = []
    add_entry(chain, {"kind": "policy_check", "synthetic_task_id": "demo-1", "status": "allowed"})
    add_entry(chain, {"kind": "audit_finished", "synthetic_task_id": "demo-1", "status": "ok"})
    tampered = copy.deepcopy(chain)
    tampered[0]["event"]["status"] = "blocked"
    return {
        "provenance": "synthetic_unsigned_demo",
        "valid_original": verify(chain),
        "valid_tampered": verify(tampered),
        "entry_count": len(chain),
        "head": chain[-1]["hash"],
        "limitation": "Attacker with log write access can rewrite entire chain and head. Use external signed witness for real audit integrity."
    }


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] != "demo":
        print("Usage: python hashchain.py demo", file=sys.stderr)
        raise SystemExit(2)
    print(json.dumps(demo(), indent=2))
