"""SEC-11 independent custody WORM audit: synthetic read-only tests."""
import json

import pytest

from confidential.custody_storage import (
    StorageAuditRejected, assess_custody_storage, read_only_inventory,
    _deny_for_operator,
)

CUSTODY = "444455556666"
OPERATOR = "111122223333"
BUCKET = "notarai-sec11-custody-synthetic-fixture"
BASE_ARN = f"arn:aws:s3:::{BUCKET}"
DENY = {
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Deny",
        "Principal": {"AWS": f"arn:aws:iam::{OPERATOR}:root"},
        "Action": "s3:*",
        "Resource": [BASE_ARN, BASE_ARN + "/*"],
    }],
}


def fixture_inventory():
    return {
        "versioning": {"Status": "Enabled"},
        "object_lock": {"ObjectLockConfiguration": {
            "ObjectLockEnabled": "Enabled",
            "Rule": {"DefaultRetention": {"Mode": "COMPLIANCE", "Days": 365}},
        }},
        "public_access": {"PublicAccessBlockConfiguration": {
            "BlockPublicAcls": True, "IgnorePublicAcls": True,
            "BlockPublicPolicy": True, "RestrictPublicBuckets": True,
        }},
        "encryption": {"ServerSideEncryptionConfiguration": {"Rules": [{
            "ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}
        }]}},
        "ownership": {"OwnershipControls": {"Rules": [
            {"ObjectOwnership": "BucketOwnerEnforced"}]}},
        "policy": {"Policy": json.dumps(DENY, sort_keys=True)},
        "region": {"LocationConstraint": "eu-central-1"},
    }


def audit(data=None, custody=CUSTODY, operator=OPERATOR):
    return assess_custody_storage(
        identity={"Account": CUSTODY},
        custody_account=custody,
        operator_account=operator,
        bucket=BUCKET,
        data=fixture_inventory() if data is None else data,
        required_retention_days=30,
    )


def test_expected_synthetic_configuration_pass_still_not_zoa():
    result = audit()
    assert result.configuration_status == "PASS"
    assert result.assurance_status == "BLOCKED"
    assert len(result.policy_sha256) == 64
    assert all(result.checks.values())
    assert result.as_dict()["zero_operator_access_proven"] is False


@pytest.mark.parametrize("mutate,failed_check", [
    (lambda x: x["versioning"].update(Status="Suspended"), "versioning_enabled"),
    (lambda x: x["object_lock"]["ObjectLockConfiguration"]["Rule"][
        "DefaultRetention"].update(Mode="GOVERNANCE"), "compliance_object_lock"),
    (lambda x: x["object_lock"]["ObjectLockConfiguration"]["Rule"][
        "DefaultRetention"].update(Days=1), "compliance_object_lock"),
    (lambda x: x["object_lock"]["ObjectLockConfiguration"].update(
        ObjectLockEnabled="Disabled"), "compliance_object_lock"),
    (lambda x: x["public_access"]["PublicAccessBlockConfiguration"].update(
        BlockPublicPolicy=False), "block_all_public_access"),
    (lambda x: x["region"].update(LocationConstraint="us-east-1"), "regional_scope"),
    (lambda x: x["encryption"]["ServerSideEncryptionConfiguration"]["Rules"][
        0]["ApplyServerSideEncryptionByDefault"].update(SSEAlgorithm="INVALID"),
     "encryption_enabled"),
    (lambda x: x["ownership"]["OwnershipControls"]["Rules"][0].update(
        ObjectOwnership="ObjectWriter"), "bucket_owner_enforced"),
    (lambda x: x["policy"].update(Policy=json.dumps({"Statement": []})),
     "explicit_operator_account_deny"),
])
def test_each_unsafe_configuration_fails_without_claim(mutate, failed_check):
    data = fixture_inventory()
    mutate(data)
    result = audit(data)
    assert result.configuration_status == "FAIL"
    assert result.checks[failed_check] is False
    assert result.assurance_status == "BLOCKED"
    assert result.as_dict()["zero_operator_access_proven"] is False


def test_assumed_role_warning_and_policy_deny_condition_supported():
    conditional = {
        "Statement": [{
            "Effect": "Deny", "Principal": "*", "Action": "s3:*",
            "Resource": [BASE_ARN, BASE_ARN + "/*"],
            "Condition": {"StringEquals": {"aws:PrincipalAccount": OPERATOR}},
        }]
    }
    assert _deny_for_operator(conditional, operator=OPERATOR, bucket=BUCKET)
    assert not _deny_for_operator(
        {"Statement": [{
            "Effect": "Deny", "Principal": "*", "Action": "s3:GetObject",
            "Resource": [BASE_ARN + "/*"],
            "Condition": {"StringEquals": {"aws:PrincipalAccount": OPERATOR}},
        }]}, operator=OPERATOR, bucket=BUCKET
    )


def test_operator_and_custody_must_be_different():
    with pytest.raises(StorageAuditRejected, match="independent custody"):
        audit(custody=OPERATOR)


def test_unexpected_extra_or_missing_inventory_is_rejected():
    data = fixture_inventory()
    del data["policy"]
    with pytest.raises(StorageAuditRejected):
        audit(data)
    data = fixture_inventory()
    data["untrusted_customer"] = "not-a-field"
    with pytest.raises(StorageAuditRejected):
        audit(data)


def test_sts_account_mismatch_is_fail_closed():
    data = fixture_inventory()
    result = assess_custody_storage(
        identity={"Account": OPERATOR}, custody_account=CUSTODY,
        operator_account=OPERATOR, bucket=BUCKET, data=data,
    )
    assert result.configuration_status == "FAIL"
    assert not result.checks["independent_aws_identity"]


class StubSession:
    def __init__(self, custody_account=CUSTODY):
        self.calls = []
        self.custody_account = custody_account
        self.s3_data = fixture_inventory()

    def client(self, which, **kwargs):
        session = self

        class Client:
            def __getattr__(self, operation):
                def call(**args):
                    session.calls.append((which, operation, args))
                    if operation == "get_caller_identity":
                        return {"Account": session.custody_account}
                    if operation == "head_bucket":
                        return {}
                    lookup = {
                        "get_bucket_versioning": "versioning",
                        "get_object_lock_configuration": "object_lock",
                        "get_public_access_block": "public_access",
                        "get_bucket_encryption": "encryption",
                        "get_bucket_ownership_controls": "ownership",
                        "get_bucket_policy": "policy",
                        "get_bucket_location": "region",
                    }
                    return session.s3_data[lookup[operation]]
                return call
        return Client()


def test_inventory_is_read_only_and_owner_bound():
    s = StubSession()
    identity, data = read_only_inventory(s, bucket=BUCKET, custody_account=CUSTODY)
    assert identity["Account"] == CUSTODY
    assert data == s.s3_data
    assert all(operation.startswith("get_") or operation == "head_bucket"
               for _, operation, _ in s.calls)
    assert all(args["ExpectedBucketOwner"] == CUSTODY
               for service, operation, args in s.calls if service == "s3")
    assert all(service in ("sts", "s3") for service, _, _ in s.calls)


def test_inventory_wrong_identity_does_not_touch_storage():
    s = StubSession(custody_account=OPERATOR)
    with pytest.raises(StorageAuditRejected):
        read_only_inventory(s, bucket=BUCKET, custody_account=CUSTODY)
    assert s.calls == [("sts", "get_caller_identity", {})]


def test_iam_deny_with_hidden_condition_cannot_fake_control():
    sneaky = {
        "Statement": [{
            "Effect": "Deny",
            "Principal": {"AWS": f"arn:aws:iam::{OPERATOR}:root"},
            "Action": "s3:*",
            "Resource": [BASE_ARN, BASE_ARN + "/*"],
            "Condition": {"StringEquals": {"aws:SourceVpce": "vpce-deadbeef"}},
        }]
    }
    assert not _deny_for_operator(sneaky, operator=OPERATOR, bucket=BUCKET)
    wildcard = {
        "Statement": [{
            "Effect": "Deny",
            "Principal": "*",
            "Action": "s3:*",
            "Resource": [BASE_ARN, BASE_ARN + "/*"],
            "Condition": {
                "StringEquals": {"aws:PrincipalAccount": OPERATOR},
                "Bool": {"aws:SecureTransport": "false"},
            },
        }]
    }
    assert not _deny_for_operator(wildcard, operator=OPERATOR, bucket=BUCKET)


def test_incomplete_encryption_rule_fails_closed_without_exception():
    data = fixture_inventory()
    data["encryption"]["ServerSideEncryptionConfiguration"]["Rules"] = [
        {"ApplyServerSideEncryptionByDefault": None}
    ]
    outcome = audit(data)
    assert outcome.configuration_status == "FAIL"
    assert outcome.checks["encryption_enabled"] is False
