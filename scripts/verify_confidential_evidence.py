#!/usr/bin/env python3
"""Standalone offline verification of SEC-11 custodian evidence.

No network, AWS credentials or NotarAI server. Trust key and fingerprint MUST
come from an independent channel, never from the signed bundle. This tool only
checks signature integrity / hash anchors; full AWS/WORM assurance is BLOCKED.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Direct invocation from repository root or by absolute path.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from confidential.signed_evidence import verify_bundle, verify_chain


def _load_json(path: Path):
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("evidence file exceeds offline size limit")
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--bundle", type=Path, help="single signed JSON bundle")
    group.add_argument("--chain", type=Path, help="JSON list of signed bundles, in sequence")
    parser.add_argument("--trusted-public-key", type=Path, required=True,
                        help="independently obtained RAW Ed25519 public key (32 bytes)")
    parser.add_argument("--pinned-fingerprint", required=True,
                        help="SHA-256 pin received OUTSIDE the NotarAI operator")
    parser.add_argument("--trusted-head-sha256", required=True,
                        help="independently archived latest chain/head SHA-256 (required even for one bundle)")
    args = parser.parse_args(argv)
    try:
        public_key = args.trusted_public_key.read_bytes()
        if len(public_key) != 32:
            raise ValueError("invalid public key length")
        if args.chain:
            if not args.trusted_head_sha256:
                raise ValueError("external chain head anchor required")
            result = verify_chain(
                bundles=_load_json(args.chain), trusted_public_key_raw=public_key,
                pinned_fingerprint=args.pinned_fingerprint,
                trusted_head_sha256=args.trusted_head_sha256,
            )
        else:
            result = verify_bundle(
                bundle=_load_json(args.bundle), trusted_public_key_raw=public_key,
                pinned_fingerprint=args.pinned_fingerprint,
                trusted_head_sha256=args.trusted_head_sha256,
            )
    except (OSError, ValueError, UnicodeError, TypeError):
        print(json.dumps({
            "integrity_status": "FAIL", "assurance_status": "BLOCKED",
            "zero_operator_access_proven": False, "manifest_sha256": None,
            "check_status": {},
        }, sort_keys=True))
        return 2
    print(json.dumps(result.as_dict(), sort_keys=True, separators=(",", ":")))
    # NEVER make a signature-only PASS into production readiness by exit code.
    if result.integrity_status == "FAIL" or result.assurance_status == "FAIL":
        return 2
    if result.integrity_status == "EXPIRED":
        return 3
    return 4  # independent hardware + append-only custody evidence still BLOCKED


if __name__ == "__main__":
    raise SystemExit(main())
