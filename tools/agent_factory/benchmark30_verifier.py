"""Single-chain reference case runner. Execute ONLY in an isolated, unprivileged container.

This file imports untrusted solution.py. Never invoke this script on a host with
credentials, files, network, or production access. See benchmark30_docker.py.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
from pathlib import Path
import sys


FUNCTIONS = {"catalog": "normalize_catalog", "permissions": "decide", "slots": "slots", "deps": "affected", "ledger": "reduce_events", "scrub": "scrub"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chain", choices=sorted(FUNCTIONS), required=True)
    parser.add_argument("--upto", type=int, required=True)
    args = parser.parse_args(argv)
    if not 1 <= args.upto <= 5:
        return 2
    # Fixed paths supplied by independent Docker orchestration, read-only mounts.
    cases = json.loads(Path("/grader/cases.json").read_text(encoding="utf-8"))["tests"]
    selected = [r for r in cases if r["chain"] == args.chain and r["step"] <= args.upto]
    spec = importlib.util.spec_from_file_location("candidate_solution", "/workspace/solution.py")
    if spec is None or spec.loader is None:
        return 2
    module = importlib.util.module_from_spec(spec)
    passed, failed = [], []
    try:
        spec.loader.exec_module(module)
        func = getattr(module, FUNCTIONS[args.chain])
    except BaseException:
        print(json.dumps({"status": "failed", "passed_ids": [], "failed_ids": [r["id"] for r in selected], "total": len(selected)}))
        return 1
    for row in selected:
        try:
            result = func(*row["args"])
            # Strict JSON equality rejects bool==1, tuples vs lists, NaN, and non-JSON output.
            expected = json.dumps(row["expected"], sort_keys=True, separators=(",", ":"), allow_nan=False)
            actual = json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False)
            (passed if expected == actual else failed).append(row["id"])
        except BaseException:
            failed.append(row["id"])
    print(json.dumps({"status": "passed" if not failed else "failed", "passed_ids": passed,
                      "failed_ids": failed, "total": len(selected)}, sort_keys=True))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
