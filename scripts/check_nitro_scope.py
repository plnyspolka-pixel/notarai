"""SEC-07 offline positive/negative scope correlation; always BLOCKED.

The result is not hardware evidence and the command never contacts AWS.
Use it to reject mixing two different experiments before a live audit.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from confidential.nitro_scope_binding import bind_positive_negative_scope


def _json_file(path: str) -> dict:
    with Path(path).open("rb") as src:
        raw = src.read(32 * 1024 + 1)
    if not raw or len(raw) > 32 * 1024:
        raise ValueError("invalid evidence size")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("invalid evidence object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--positive-manifest", required=True)
    parser.add_argument("--negative-matrix", required=True)
    args = parser.parse_args()
    try:
        summary = bind_positive_negative_scope(
            positive=_json_file(args.positive_manifest),
            negative=_json_file(args.negative_matrix),
        )
        print(json.dumps(summary, sort_keys=True))
    except Exception:
        print(json.dumps({
            "status": "BLOCKED",
            "scope_consistent": False,
            "reason": "positive_negative_scope_unverified",
            "hardware_attestation_verified": False,
            "production_enabled": False,
        }, sort_keys=True))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
