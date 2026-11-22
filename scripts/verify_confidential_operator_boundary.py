"""Independently runnable read-only custody verifier for NotarAI Nitro.

Two genuinely independent AWS profiles are REQUIRED for --check:
one workload profile (ECS account), one custodian/auditor profile (KMS account).
Does not call Decrypt, change policies, access customer data or log raw AWS
responses. This verifies instantaneous configuration only, NOT hardware
attestation, AWS Organizations independence or absence of key admin collusion.

Usage:
 python scripts/verify_confidential_operator_boundary.py \
     --operator-profile notarai-audit-readonly \
     --custody-profile independent-custodian-readonly \
     --tenant pilot01 --task-definition-arn <EXACT_REVISION_ARN> \
     --kms-key-arn <EXTERNAL_ACCOUNT_KEY_ARN> \
     --pcr17 <96_HEX_CHARS> --image-sha256 <64_HEX_CHARS> --check
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from confidential.operator_boundary import (
    BoundaryDenied,
    inspect_operator_boundary,
)

_REGION = "eu-central-1"


def inspect(*, operator_profile: str, custody_profile: str, tenant: str,
            task_definition_arn: str, kms_key_arn: str,
            pcr17: str, image_sha256: str, check: bool = False,
            session_factory=None) -> dict:
    if operator_profile == custody_profile or not (
        operator_profile and custody_profile
    ):
        raise BoundaryDenied("two independent AWS identity profiles are mandatory")
    if not check:
        return {
            "status": "dry-run",
            "aws_calls": 0,
            "zero_operator_access_proven": False,
        }
    if session_factory is None:
        import boto3
        session_factory = boto3.Session

    workload = session_factory(profile_name=operator_profile,
                               region_name=_REGION)
    custodian = session_factory(profile_name=custody_profile,
                                region_name=_REGION)
    workload_id = workload.client("sts").get_caller_identity().get("Account")
    custody_id = custodian.client("sts").get_caller_identity().get("Account")
    # Abort before the KMS call if the accounts are not provably separate.
    if not (isinstance(workload_id, str) and
            isinstance(custody_id, str) and workload_id != custody_id):
        raise BoundaryDenied("custody is not an independent account")

    kms = custodian.client("kms")
    ecs = workload.client("ecs")
    meta = kms.describe_key(KeyId=kms_key_arn)["KeyMetadata"]
    policy_text = kms.get_key_policy(
        KeyId=kms_key_arn, PolicyName="default"
    )["Policy"]
    try:
        policy = json.loads(policy_text)
    except (ValueError, TypeError):
        raise BoundaryDenied("custodian KMS policy unavailable") from None
    grants_page = kms.list_grants(KeyId=kms_key_arn, Limit=100)
    if grants_page.get("Truncated") or grants_page.get("NextMarker") or (
        grants_page.get("Marker")
    ):
        raise BoundaryDenied("custody grants list incomplete")
    task = ecs.describe_task_definition(
        taskDefinition=task_definition_arn
    )["taskDefinition"]
    return inspect_operator_boundary(
        operator_account=workload_id,
        custody_account=custody_id,
        tenant=tenant,
        key_arn=kms_key_arn,
        pcr17=pcr17,
        image_sha256=image_sha256,
        task_arn=task_definition_arn,
        key_metadata=meta,
        key_policy=policy,
        key_grants=grants_page.get("Grants"),
        task_definition=task,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator-profile", required=True)
    parser.add_argument("--custody-profile", required=True)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--task-definition-arn", required=True)
    parser.add_argument("--kms-key-arn", required=True)
    parser.add_argument("--pcr17", required=True)
    parser.add_argument("--image-sha256", required=True)
    parser.add_argument("--check", action="store_true",
                        help="Real READ ONLY AWS queries from both profiles")
    parser.add_argument("--output", type=Path,
                        help="Optional redacted JSON report (outside repository)")
    args = parser.parse_args()
    try:
        report = inspect(
            operator_profile=args.operator_profile,
            custody_profile=args.custody_profile,
            tenant=args.tenant,
            task_definition_arn=args.task_definition_arn,
            kms_key_arn=args.kms_key_arn,
            pcr17=args.pcr17,
            image_sha256=args.image_sha256,
            check=args.check,
        )
        rendered = json.dumps(report, sort_keys=True, indent=2) + "\n"
        if args.output:
            # Do not overwrite existing evidence; avoid symlink/clobber issues.
            fd = os.open(str(args.output),
                         os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                output.write(rendered)
        else:
            print(rendered, end="")
    except Exception:
        # No raw botocore errors or potentially sensitive identifiers.
        raise SystemExit("DENIED: independent KMS / Nitro configuration unverified") from None


if __name__ == "__main__":
    main()
