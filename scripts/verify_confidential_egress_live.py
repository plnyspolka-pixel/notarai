"""SEC-08 real Nitro egress evidence gate.

A route-table inspection or offline Docker test is not proof of actual
blocking from an attested Nitro task. No deployment, no AWS calls, no PII.
"""
from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="check readiness for real evidence; always fail closed")
    args = parser.parse_args()
    if not args.check:
        parser.print_help()
        return 0
    print("BLOCKED SEC-08 K6: no independently witnessed AWS Nitro active probe.")
    print("Required: attested task identity + ENI, DNS/IPv6/HTTP/S3 active denial,")
    print("sanitized guest/parent flow logs, operator-side IAM and KMS audit.")
    print("Offline and EC2 Describe-only checks do not establish Zero Knowledge.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
