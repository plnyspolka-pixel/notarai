"""External auditor verification of independently signed Nitro release receipt.

With --check queries BOTH live AWS accounts read-only and verifies signature
with an out-of-band pinned public key. No trust in NotarAI-controlled JWT,
GitHub CI check or report alone. No customer data or KMS decrypt operations.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from confidential.release_approval import verify_release
from scripts.verify_confidential_operator_boundary import inspect


def check_release(
    *, operator_profile: str, custody_profile: str, tenant: str,
    task_definition_arn: str, kms_key_arn: str,
    pcr17: str, image_sha256: str, receipt: dict,
    trusted_public_key_pem: bytes, trusted_public_key_sha256: str,
    check: bool = False, session_factory=None,
) -> dict:
    if not check:
        return {
            "state": "dry-run", "aws_calls": 0,
            "zero_operator_access_proven": False,
        }
    config = inspect(
        operator_profile=operator_profile,
        custody_profile=custody_profile,
        tenant=tenant,
        task_definition_arn=task_definition_arn,
        kms_key_arn=kms_key_arn,
        pcr17=pcr17, image_sha256=image_sha256,
        check=True, session_factory=session_factory,
    )
    return verify_release(
        envelope=receipt, config=config,
        trusted_public_key_pem=trusted_public_key_pem,
        pinned_public_key_sha256=trusted_public_key_sha256,
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in (
        "operator-profile", "custody-profile", "tenant",
        "task-definition-arn", "kms-key-arn", "pcr17", "image-sha256",
        "receipt-file", "trusted-custodian-public-key",
        "trusted-custodian-public-key-sha256",
    ):
        p.add_argument("--" + name, required=True)
    p.add_argument("--check", action="store_true",
                   help="Run live AWS structural audit + independent signature check")
    args = p.parse_args()
    try:
        if not args.check:
            print('{"state":"dry-run","aws_calls":0,"zero_operator_access_proven":false}')
            return
        # Independent auditor must obtain this public key and its SHA256
        # fingerprint through a channel outside the NotarAI operator's control.
        receipt = json.loads(Path(args.receipt_file).read_text(encoding="utf-8"))
        key_pem = Path(args.trusted_custodian_public_key).read_bytes()
        output = check_release(
            operator_profile=args.operator_profile,
            custody_profile=args.custody_profile,
            tenant=args.tenant,
            task_definition_arn=args.task_definition_arn,
            kms_key_arn=args.kms_key_arn,
            pcr17=args.pcr17, image_sha256=args.image_sha256,
            receipt=receipt, trusted_public_key_pem=key_pem,
            trusted_public_key_sha256=args.trusted_custodian_public_key_sha256,
            check=True,
        )
        print(json.dumps(output, sort_keys=True, indent=2))
    except Exception:
        raise SystemExit("DENIED: verified custody release not available") from None


if __name__ == "__main__":
    main()
