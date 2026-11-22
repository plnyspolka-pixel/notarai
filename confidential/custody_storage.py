"""SEC-11 read-only independent S3 WORM configuration audit.

This is NOT a substitute for a live operator overwrite/delete denial,
external custody signing, or Nitro hardware evidence. Use only the custodian
account's separate read-only audit identity; no AWS write APIs here.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

ACCOUNT = re.compile(r"^[0-9]{12}$")
BUCKET = re.compile(r"^[a-z0-9][a-z0-9.-]{2,62}$")


class StorageAuditRejected(ValueError):
    """No AWS error details, raw policy text or user identifiers in messages."""


def _deny_for_operator(policy: dict, *, operator: str, bucket: str) -> bool:
    """Require explicit all-action denial for the operator account.

    This is not an IAM/STS trust graph proof: an operator may have an
    assumed role in the custodian account. Such trust is audited separately.
    """
    statements = policy.get("Statement", [])
    if isinstance(statements, dict):
        statements = [statements]
    if not isinstance(statements, list):
        return False
    required_resources = {
        "arn:aws:s3:::" + bucket,
        "arn:aws:s3:::" + bucket + "/*",
    }
    for statement in statements:
        if not isinstance(statement, dict):
            continue
        if statement.get("Effect") != "Deny" or ("NotAction" in statement or "NotResource" in statement):
            continue
        actions = statement.get("Action")
        actions = [actions] if isinstance(actions, str) else actions
        if not isinstance(actions, list) or "s3:*" not in actions:
            continue
        resources = statement.get("Resource")
        resources = [resources] if isinstance(resources, str) else resources
        if not isinstance(resources, list) or not required_resources.issubset(set(
            item for item in resources if isinstance(item, str)
        )):
            continue
        principal = statement.get("Principal")
        if principal == "*":
            cond = statement.get("Condition", {})
            if (isinstance(cond, dict) and set(cond) == {"StringEquals"} and
                    isinstance(cond["StringEquals"], dict) and
                    cond["StringEquals"] == {"aws:PrincipalAccount": operator}):
                return True
        elif isinstance(principal, dict):
            # ARN root denotes all IAM identities of that account for
            # resource-policy delegation, but does not cover assumed roles
            # in the separate custody account (separate trust audit).
            arn = principal.get("AWS")
            arns = [arn] if isinstance(arn, str) else arn
            if (not statement.get("Condition") and isinstance(arns, list) and (
                "arn:aws:iam::" + operator + ":root"
            ) in arns):
                return True
    return False


@dataclass(frozen=True)
class StorageAudit:
    configuration_status: str
    assurance_status: str
    checks: dict[str, bool]
    policy_sha256: str | None

    def as_dict(self) -> dict:
        return {
            "configuration_status": self.configuration_status,
            "assurance_status": "BLOCKED",
            "checks": self.checks,
            "policy_sha256": self.policy_sha256,
            "zero_operator_access_proven": False,
        }


def assess_custody_storage(*, identity: dict, custody_account: str,
                           operator_account: str, bucket: str, data: dict,
                           required_retention_days: int = 30) -> StorageAudit:
    """Evaluate AWS API responses without exposing raw policies or user data."""
    if not all(isinstance(x, str) and ACCOUNT.fullmatch(x) for x in
               (custody_account, operator_account)):
        raise StorageAuditRejected("invalid account identifiers")
    if custody_account == operator_account:
        raise StorageAuditRejected("independent custody account required")
    if not isinstance(bucket, str) or not BUCKET.fullmatch(bucket):
        raise StorageAuditRejected("invalid evidence bucket identifier")
    if type(required_retention_days) is not int or not 30 <= required_retention_days <= 3650:
        raise StorageAuditRejected("invalid minimum retention")
    if not isinstance(data, dict):
        raise StorageAuditRejected("missing bucket inventory")
    expected_keys = {
        "versioning", "object_lock", "public_access", "encryption",
        "ownership", "policy", "region",
    }
    if set(data) != expected_keys:
        raise StorageAuditRejected("incomplete bucket inventory")
    try:
        lock = data["object_lock"]["ObjectLockConfiguration"]
        retention = lock["Rule"]["DefaultRetention"]
        access = data["public_access"]["PublicAccessBlockConfiguration"]
        enc_rules = data["encryption"]["ServerSideEncryptionConfiguration"]["Rules"]
        own_rules = data["ownership"]["OwnershipControls"]["Rules"]
        policy_text = data["policy"]["Policy"]
        if not isinstance(policy_text, str) or len(policy_text) > 256 * 1024:
            raise StorageAuditRejected("invalid bucket policy")
        policy = json.loads(policy_text)
    except (KeyError, TypeError, ValueError, IndexError):
        raise StorageAuditRejected("malformed bucket inventory") from None
    if not isinstance(policy, dict) or not all(isinstance(value, dict) for value in (
        identity, data["versioning"], lock, retention, access,
        data["region"], data["policy"],
    )):
        raise StorageAuditRejected("malformed bucket inventory")
    if not isinstance(enc_rules, list) or not isinstance(own_rules, list):
        raise StorageAuditRejected("malformed bucket inventory")
    days = retention.get("Days")
    years = retention.get("Years")
    if type(days) is not int:
        days = 0
    if type(years) is not int:
        years = 0
    checks = {
        "independent_aws_identity": identity.get("Account") == custody_account,
        "regional_scope": data["region"].get("LocationConstraint") == "eu-central-1",
        "versioning_enabled": data["versioning"].get("Status") == "Enabled",
        "compliance_object_lock": (
            lock.get("ObjectLockEnabled") == "Enabled" and
            retention.get("Mode") == "COMPLIANCE" and
            (days >= required_retention_days or years * 365 >= required_retention_days)
        ),
        "block_all_public_access": all(
            access.get(name) is True for name in (
                "BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy",
                "RestrictPublicBuckets",
            )
        ),
        "encryption_enabled": any(
            isinstance(rule, dict) and
            isinstance(rule.get("ApplyServerSideEncryptionByDefault"), dict) and
            rule["ApplyServerSideEncryptionByDefault"].get(
                "SSEAlgorithm"
            ) in ("AES256", "aws:kms")
            for rule in enc_rules
        ),
        "bucket_owner_enforced": any(
            isinstance(rule, dict) and
            rule.get("ObjectOwnership") == "BucketOwnerEnforced"
            for rule in own_rules
        ),
        "explicit_operator_account_deny": _deny_for_operator(
            policy, operator=operator_account, bucket=bucket
        ),
    }
    # Hash only, never publish raw AWS account policy.
    digest = hashlib.sha256(policy_text.encode("utf-8")).hexdigest()
    return StorageAudit(
        "PASS" if all(checks.values()) else "FAIL", "BLOCKED", checks, digest
    )


def read_only_inventory(session, *, bucket: str, custody_account: str) -> tuple[dict, dict]:
    """Read-only AWS calls; do not catch and print source exceptions."""
    try:
        identity = session.client("sts").get_caller_identity()
        if identity.get("Account") != custody_account:
            raise StorageAuditRejected("auditor session not on custody account")
        s3 = session.client("s3", region_name="eu-central-1")
        args = {"Bucket": bucket, "ExpectedBucketOwner": custody_account}
        s3.head_bucket(**args)
        data = {
            "versioning": s3.get_bucket_versioning(**args),
            "object_lock": s3.get_object_lock_configuration(**args),
            "public_access": s3.get_public_access_block(**args),
            "encryption": s3.get_bucket_encryption(**args),
            "ownership": s3.get_bucket_ownership_controls(**args),
            "policy": s3.get_bucket_policy(**args),
            "region": s3.get_bucket_location(**args),
        }
        return identity, data
    except StorageAuditRejected:
        raise
    except Exception:
        raise StorageAuditRejected("independent read-only AWS inventory unavailable") from None
