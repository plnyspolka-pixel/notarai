#!/usr/bin/env python3
"""SEC-12 offline dry-run; --check must report BLOCKED until real hardware proof.

No AWS access, no production writes, no client data. Exit 2 is intentional
and means commercial release has NOT been authorized.
"""
from __future__ import annotations

import argparse
import json

from confidential.adversarial_gate import evaluate_gate, offline_matrix


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true",
                       help="fail closed on missing real signed AWS evidence (exit 2)")
    group.add_argument("--offline", action="store_true",
                       help="run synthetic attack matrix (does not authorize launch)")
    args = parser.parse_args()
    rows = offline_matrix()
    result = evaluate_gate(rows)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    if result["offline_matrix"] != "PASS":
        return 1
    return 2 if args.check else 0


if __name__ == "__main__":
    raise SystemExit(main())
