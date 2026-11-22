"""SEC-04 read-only AWS metadata audit for fictional pilot tenants.

No AWS call without --check; no decrypt, S3 objects, queue consumption, model
inference, user records or resource mutations. Reports only coarse statuses.
A PASS on infrastructure metadata never constitutes strict Zero Knowledge.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
from collections.abc import Callable

_REGION = "eu-central-1"
_KMS_ARN = re.compile(r"arn:aws:kms:eu-central-1:([0-9]{12}):key/[A-Za-z0-9-]+")
_QUEUE_URL = re.compile(
    r"https://sqs\.eu-central-1\.amazonaws\.com/([0-9]{12})/"
    r"notarai-confidential-(pilot01|pilot02)\.fifo"
)
_CHECKS = (
    "aws_account", "s3_region", "s3_versioning", "s3_public_access",
    "s3_bucket_encryption", "s3_no_replication", "kms_metadata",
    "kms_attested_policy", "kms_decrypt_grants", "sqs_fifo_encryption",
)


def _action_allows_decrypt(action: object) -> bool:
    actions = [action] if isinstance(action, str) else action
    return isinstance(actions, list) and any(
        isinstance(a, str) and fnmatch.fnmatchcase(
            "kms:decrypt", a.lower()
        ) for a in actions
    )


def validate_kms_attestation_policy(policy: object, *, account: str,
                                    tenant: str) -> bool:
    """Shape validation only; not proof that policy cannot later be changed."""
    if not isinstance(policy, dict) or not isinstance(policy.get("Statement"), list):
        return False
    # IAM NotAction is an implicit allow-list complement. Do not assert
    # protection if any Allow could include Decrypt through NotAction.
    if any(isinstance(s, dict) and s.get("Effect") == "Allow" and
           "NotAction" in s for s in policy["Statement"]):
        return False
    grants = [
        s for s in policy["Statement"]
        if isinstance(s, dict) and s.get("Effect") == "Allow"
        and _action_allows_decrypt(s.get("Action"))
    ]
    if len(grants) != 1:
        return False
    grant = grants[0]
    conditions = grant.get("Condition")
    if not isinstance(conditions, dict):
        return False
    arn = conditions.get("ArnEquals")
    exact = conditions.get("StringEqualsIgnoreCase")
    if not isinstance(arn, dict) or not isinstance(exact, dict):
        return False
    pcr = exact.get("kms:RecipientAttestation:PCR17")
    return (
        arn.get("aws:PrincipalArn") ==
        f"arn:aws:iam::{account}:role/notarai-confidential-{tenant}"
        and exact.get("kms:RecipientAttestation:PCR8:ServiceName") ==
        "ecs.amazonaws.com"
        and isinstance(pcr, str) and re.fullmatch(r"[a-fA-F0-9]{96}", pcr) is not None
    )


def _report(mode: str, checks: dict[str, str], *, aws_calls: int) -> dict:
    return {
        "schema": "sec04-live-readonly-v1",
        "mode": mode,
        "region": _REGION,
        "checks": checks,
        "aws_calls": aws_calls,
        "overall": "BLOCKED",
        "strict_zero_knowledge_verified": False,
        "hardware_attestation": "UNVERIFIED",
        "processor_retention": "UNVERIFIED",
    }


def audit(*, profile: str, account: str, tenant: str, bucket: str,
          kms_key_arn: str, queue_url: str, check: bool = False,
          session_factory=None) -> dict:
    if not re.fullmatch(r"[0-9]{12}", account):
        raise ValueError("invalid AWS account")
    if tenant not in {"pilot01", "pilot02"}:
        raise ValueError("only synthetic pilot tenants are allowed")
    if not isinstance(bucket, str) or not re.fullmatch(
        r"[a-z0-9][a-z0-9.-]{2,62}", bucket
    ) or tenant not in bucket:
        raise ValueError("invalid pilot storage scope")
    key_match = _KMS_ARN.fullmatch(kms_key_arn)
    queue_match = _QUEUE_URL.fullmatch(queue_url)
    if not key_match or key_match.group(1) != account:
        raise ValueError("invalid KMS account/region")
    if (not queue_match or queue_match.group(1) != account or
            queue_match.group(2) != tenant):
        raise ValueError("invalid queue account/region")
    if not isinstance(profile, str) or not profile:
        raise ValueError("AWS profile is required")

    checks = dict.fromkeys(_CHECKS, "BLOCKED")
    if not check:
        result = _report("dry_run", checks, aws_calls=0)
        print(json.dumps(result, sort_keys=True))
        return result

    if session_factory is None:
        import boto3
        session_factory = boto3.Session
    session = session_factory(profile_name=profile, region_name=_REGION)
    calls = 0

    def client(service: str):
        return session.client(service)

    def checked(name: str, operation: Callable[[], bool]):
        nonlocal calls
        calls += 1
        try:
            checks[name] = "PASS" if operation() is True else "FAIL"
        except Exception:
            # Never print raw SDK exception messages, names, values or IDs.
            checks[name] = "BLOCKED"

    def identity_ok() -> bool:
        return client("sts").get_caller_identity().get("Account") == account

    checked("aws_account", identity_ok)
    if checks["aws_account"] != "PASS":
        # No metadata access in an unexpected account.
        result = _report("read_only", checks, aws_calls=calls)
        print(json.dumps(result, sort_keys=True))
        return result

    def s3_location():
        return client("s3").get_bucket_location(
            Bucket=bucket, ExpectedBucketOwner=account
        ).get("LocationConstraint") == _REGION

    def s3_versioning():
        return client("s3").get_bucket_versioning(
            Bucket=bucket, ExpectedBucketOwner=account
        ).get("Status") == "Enabled"

    def s3_public():
        flags = client("s3").get_public_access_block(
            Bucket=bucket, ExpectedBucketOwner=account
        ).get("PublicAccessBlockConfiguration", {})
        return all(flags.get(k) is True for k in (
            "BlockPublicAcls", "IgnorePublicAcls",
            "BlockPublicPolicy", "RestrictPublicBuckets"
        ))

    def s3_encryption():
        rules = client("s3").get_bucket_encryption(
            Bucket=bucket, ExpectedBucketOwner=account
        ).get(
            "ServerSideEncryptionConfiguration", {}
        ).get("Rules", [])
        return len(rules) > 0 and all(
            isinstance(r, dict) and
            r.get("ApplyServerSideEncryptionByDefault", {}).get(
                "SSEAlgorithm"
            ) in {"AES256", "aws:kms"}
            for r in rules
        )

    def s3_no_replication():
        # A bucket can live in Frankfurt yet replicate ciphertext to
        # another region; reject any replication configuration, and deny
        # if AWS cannot prove the absence of rules.
        from botocore.exceptions import ClientError
        try:
            client("s3").get_bucket_replication(
                Bucket=bucket, ExpectedBucketOwner=account
            )
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code", "")
            if code == "ReplicationConfigurationNotFoundError":
                return True
            raise
        return False

    def kms_metadata():
        meta = client("kms").describe_key(KeyId=kms_key_arn).get("KeyMetadata", {})
        return (meta.get("Arn") == kms_key_arn and
                meta.get("KeyState") == "Enabled" and
                meta.get("KeyUsage") == "ENCRYPT_DECRYPT" and
                meta.get("KeySpec") == "RSA_3072" and
                meta.get("MultiRegion") is False)

    def kms_policy():
        policy_text = client("kms").get_key_policy(
            KeyId=kms_key_arn, PolicyName="default"
        ).get("Policy", "")
        # Only inspect policy structure; do not output its IAM principals.
        policy = json.loads(policy_text)
        return validate_kms_attestation_policy(
            policy, account=account, tenant=tenant
        )

    def kms_decrypt_grants():
        grants = client("kms").list_grants(
            KeyId=kms_key_arn, Limit=100
        )
        if grants.get("Truncated") or grants.get("NextMarker"):
            raise RuntimeError("incomplete KMS grant metadata")
        entries = grants.get("Grants")
        if not isinstance(entries, list):
            raise RuntimeError("missing KMS grant inventory")
        return all(
            isinstance(g, dict) and
            "Decrypt" not in g.get("Operations", [])
            for g in entries
        )

    def sqs_encryption():
        attrs = client("sqs").get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=["FifoQueue", "SqsManagedSseEnabled"]
        ).get("Attributes", {})
        return (attrs.get("FifoQueue") == "true" and
                attrs.get("SqsManagedSseEnabled") == "true")

    for name, operation in (
        ("s3_region", s3_location),
        ("s3_versioning", s3_versioning),
        ("s3_public_access", s3_public),
        ("s3_bucket_encryption", s3_encryption),
        ("s3_no_replication", s3_no_replication),
        ("kms_metadata", kms_metadata),
        ("kms_attested_policy", kms_policy),
        ("kms_decrypt_grants", kms_decrypt_grants),
        ("sqs_fifo_encryption", sqs_encryption),
    ):
        checked(name, operation)
    result = _report("read_only", checks, aws_calls=calls)
    print(json.dumps(result, sort_keys=True))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("profile", "account", "tenant", "bucket",
                  "kms-key-arn", "queue-url"):
        parser.add_argument("--" + field, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    audit(profile=args.profile, account=args.account, tenant=args.tenant,
          bucket=args.bucket, kms_key_arn=args.kms_key_arn,
          queue_url=args.queue_url, check=args.check)


if __name__ == "__main__":
    main()
