"""Read-only audit of signed Confidential security claims (no AWS calls).

No arguments => prints four UNVERIFIED claims from the source-controlled
matrix. To check independently signed receipts, provide BOTH trust roots
and SHA256 fingerprints obtained out of band. Output is an *evidence syntax
audit*, not certification of a live Nitro/KMS system or marketing clearance.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from confidential.security_claims import ClaimsRejected, evaluate_claims

DEFAULT_POLICY = (
    Path(__file__).resolve().parents[1] /
    "docs/security-claims/policy.json"
)


def _root(pem: Path | None, fingerprint: str | None):
    if pem is None and fingerprint is None:
        return None
    if pem is None or fingerprint is None:
        raise ClaimsRejected("independent trust root requires PEM and fingerprint")
    return {
        "public_key_pem": pem.read_bytes(),
        "fingerprint_sha256": fingerprint,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy-file", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--tenant", choices=["pilot01", "pilot02"],
                        default="pilot01")
    parser.add_argument("--image-sha256", default="0" * 64,
                        help="Expected exact approved ECR image SHA256")
    parser.add_argument("--evidence-file", type=Path,
                        help="JSON array of independently signed evidence receipts")
    parser.add_argument("--custody-public-key", type=Path,
                        help="PEM supplied by independent custodian")
    parser.add_argument("--custody-public-key-sha256",
                        help="Independent out-of-band SHA256 pin of custody PEM SPKI")
    parser.add_argument("--auditor-public-key", type=Path,
                        help="PEM supplied by independent external auditor")
    parser.add_argument("--auditor-public-key-sha256",
                        help="Independent out-of-band SHA256 pin of auditor PEM SPKI")
    parser.add_argument("--require-all-pass", action="store_true",
                        help="Exit 2 unless all structural evidence gates pass")
    args = parser.parse_args()
    try:
        policy = json.loads(args.policy_file.read_text(encoding="utf-8"))
        evidence = (
            json.loads(args.evidence_file.read_text(encoding="utf-8"))
            if args.evidence_file is not None else None
        )
        roots = {}
        for name, pem, pin in (
            ("independent_custodian", args.custody_public_key,
             args.custody_public_key_sha256),
            ("independent_auditor", args.auditor_public_key,
             args.auditor_public_key_sha256),
        ):
            value = _root(pem, pin)
            if value is not None:
                roots[name] = value
        result = evaluate_claims(
            policy, evidence, trust_roots=roots, tenant=args.tenant,
            image_sha256=args.image_sha256,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        if args.require_all_pass and any(
            claim["status"] != "PASS"
            for claim in result["claims"].values()
        ):
            return 2
        return 0
    except (OSError, ValueError, KeyError, TypeError, ClaimsRejected):
        # No raw receipt content, key path or stacktrace to stdout/stderr.
        print("DENIED: independent security claim evidence could not be verified",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
