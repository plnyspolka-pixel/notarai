"""SEC-04 metadata evidence collector: synthetic, offline, never AWS calls."""
import json

import pytest
from botocore.exceptions import ClientError

from scripts.audit_confidential_sec04_live import (
    audit, validate_kms_attestation_policy,
)

ACCOUNT = "111122223333"
TENANT = "pilot01"
BUCKET = "ntr-cf-pilot01-111122223333-eu-central-1"
KMS = "arn:aws:kms:eu-central-1:111122223333:key/pilot-test"
QUEUE = (
    "https://sqs.eu-central-1.amazonaws.com/111122223333/"
    "notarai-confidential-pilot01.fifo"
)


def params(**overrides):
    values = dict(profile="fake", account=ACCOUNT, tenant=TENANT,
                  bucket=BUCKET, kms_key_arn=KMS, queue_url=QUEUE)
    values.update(overrides)
    return values


def guarded_policy():
    return {
        "Statement": [{
            "Sid": "AllowAttested",
            "Effect": "Allow", "Action": ["kms:Decrypt"],
            "Condition": {
                "ArnEquals": {
                    "aws:PrincipalArn": (
                        "arn:aws:iam::111122223333:"
                        "role/notarai-confidential-pilot01"
                    )
                },
                "StringEqualsIgnoreCase": {
                    "kms:RecipientAttestation:PCR17": "a" * 96,
                    "kms:RecipientAttestation:PCR8:ServiceName": "ecs.amazonaws.com",
                },
            },
        }]
    }


class FakeAWS:
    def __init__(self, *, account=ACCOUNT, bucket_region="eu-central-1",
                 fail_region=False, policy=None, replication=False,
                 grants=None):
        self.account = account
        self.bucket_region = bucket_region
        self.fail_region = fail_region
        self.policy = guarded_policy() if policy is None else policy
        self.replication = replication
        self.grants = [] if grants is None else grants
        self.calls = []

    def client(self, name):
        assert name in {"sts", "s3", "kms", "sqs"}
        self.calls.append("client:" + name)
        return self

    def get_caller_identity(self):
        self.calls.append("sts:GetCallerIdentity")
        return {"Account": self.account}

    def get_bucket_location(self, *, Bucket, ExpectedBucketOwner):
        self.calls.append("s3:GetBucketLocation")
        assert Bucket == BUCKET and ExpectedBucketOwner == ACCOUNT
        if self.fail_region:
            raise RuntimeError("FICTIONAL-PERSONAL-DOCUMENT-CANARY")
        return {"LocationConstraint": self.bucket_region}

    def get_bucket_versioning(self, *, Bucket, ExpectedBucketOwner):
        self.calls.append("s3:GetBucketVersioning")
        assert Bucket == BUCKET and ExpectedBucketOwner == ACCOUNT
        return {"Status": "Enabled"}

    def get_public_access_block(self, *, Bucket, ExpectedBucketOwner):
        self.calls.append("s3:GetPublicAccessBlock")
        assert Bucket == BUCKET and ExpectedBucketOwner == ACCOUNT
        return {"PublicAccessBlockConfiguration": {
            "BlockPublicAcls": True, "IgnorePublicAcls": True,
            "BlockPublicPolicy": True, "RestrictPublicBuckets": True,
        }}

    def get_bucket_encryption(self, *, Bucket, ExpectedBucketOwner):
        self.calls.append("s3:GetBucketEncryption")
        assert Bucket == BUCKET and ExpectedBucketOwner == ACCOUNT
        return {"ServerSideEncryptionConfiguration": {
            "Rules": [{"ApplyServerSideEncryptionByDefault": {
                "SSEAlgorithm": "AES256"
            }}],
        }}

    def get_bucket_replication(self, *, Bucket, ExpectedBucketOwner):
        self.calls.append("s3:GetBucketReplication")
        assert Bucket == BUCKET and ExpectedBucketOwner == ACCOUNT
        if self.replication:
            return {"ReplicationConfiguration": {"Rules": [{"ID": "cross-region"}]}}
        raise ClientError({
            "Error": {"Code": "ReplicationConfigurationNotFoundError",
                      "Message": "no configuration"}
        }, "GetBucketReplication")

    def describe_key(self, *, KeyId):
        self.calls.append("kms:DescribeKey")
        assert KeyId == KMS
        return {"KeyMetadata": {
            "Arn": KMS, "KeyState": "Enabled",
            "KeyUsage": "ENCRYPT_DECRYPT", "KeySpec": "RSA_3072",
            "MultiRegion": False,
        }}

    def get_key_policy(self, *, KeyId, PolicyName):
        self.calls.append("kms:GetKeyPolicy")
        assert KeyId == KMS and PolicyName == "default"
        return {"Policy": json.dumps(self.policy)}

    def list_grants(self, *, KeyId, Limit):
        self.calls.append("kms:ListGrants")
        assert KeyId == KMS and Limit == 100
        return {"Grants": self.grants, "Truncated": False}

    def get_queue_attributes(self, *, QueueUrl, AttributeNames):
        self.calls.append("sqs:GetQueueAttributes")
        assert QueueUrl == QUEUE
        assert set(AttributeNames) == {"FifoQueue", "SqsManagedSseEnabled"}
        return {"Attributes": {
            "FifoQueue": "true", "SqsManagedSseEnabled": "true",
        }}


def test_sec04_dry_run_makes_zero_aws_calls_and_never_claims_zk(capsys):
    def forbidden(**kwargs):
        raise AssertionError("dry-run must not initialize AWS")
    result = audit(**params(), check=False, session_factory=forbidden)
    assert result["aws_calls"] == 0
    assert set(result["checks"].values()) == {"BLOCKED"}
    assert result["overall"] == "BLOCKED"
    assert result["strict_zero_knowledge_verified"] is False
    assert json.loads(capsys.readouterr().out) == result


def test_sec04_read_only_checks_metadata_only_and_never_attests_zk(capsys):
    aws = FakeAWS()
    def factory(**kwargs):
        assert kwargs == {"profile_name": "fake", "region_name": "eu-central-1"}
        return aws
    result = audit(**params(), check=True, session_factory=factory)
    assert all(v == "PASS" for v in result["checks"].values())
    assert result["overall"] == "BLOCKED"
    assert result["strict_zero_knowledge_verified"] is False
    assert result["hardware_attestation"] == "UNVERIFIED"
    assert result["processor_retention"] == "UNVERIFIED"
    assert all(not any(x in call.lower() for x in (
        "decrypt", "put", "delete", "receive", "send", "getobject", "invoke"
    )) for call in aws.calls)
    assert json.loads(capsys.readouterr().out) == result


def test_sec04_wrong_account_stops_without_listing_resources():
    aws = FakeAWS(account="444455556666")
    result = audit(**params(), check=True, session_factory=lambda **kw: aws)
    assert result["checks"]["aws_account"] == "FAIL"
    assert set(result["checks"].values()) == {"FAIL", "BLOCKED"}
    assert aws.calls == ["client:sts", "sts:GetCallerIdentity"]


def test_sec04_provider_error_cannot_enter_evidence_output(capsys):
    aws = FakeAWS(fail_region=True)
    result = audit(**params(), check=True, session_factory=lambda **kw: aws)
    assert result["checks"]["s3_region"] == "BLOCKED"
    output = capsys.readouterr().out
    assert "FICTIONAL-PERSONAL-DOCUMENT-CANARY" not in output
    assert result["overall"] == "BLOCKED"


def test_sec04_wrong_s3_region_is_fail_not_pass():
    aws = FakeAWS(bucket_region="eu-west-1")
    result = audit(**params(), check=True, session_factory=lambda **kw: aws)
    assert result["checks"]["s3_region"] == "FAIL"
    assert result["strict_zero_knowledge_verified"] is False


@pytest.mark.parametrize("mutation", [
    {"Statement": [{"Effect": "Allow", "Action": ["kms:*"], "Resource": "*"}]},
    {"Statement": [
        guarded_policy()["Statement"][0],
        {"Effect": "Allow", "NotAction": ["kms:Encrypt"], "Resource": "*"},
    ]},
    {"Statement": [{"Effect": "Allow", "Action": ["kms:Decrypt"], "Resource": "*"}]},
    {"Statement": []},
    None,
])
def test_sec04_kms_policy_rejects_broad_or_unattested_grants(mutation):
    assert not validate_kms_attestation_policy(
        mutation, account=ACCOUNT, tenant=TENANT
    )


def test_sec04_policy_deny_on_wrong_pcr17_or_principal():
    policy = guarded_policy()
    assert validate_kms_attestation_policy(policy, account=ACCOUNT, tenant=TENANT)
    policy["Statement"][0]["Condition"]["StringEqualsIgnoreCase"][
        "kms:RecipientAttestation:PCR17"
    ] = "a" * 95
    assert not validate_kms_attestation_policy(
        policy, account=ACCOUNT, tenant=TENANT
    )
    policy["Statement"][0]["Condition"]["StringEqualsIgnoreCase"][
        "kms:RecipientAttestation:PCR17"
    ] = "a" * 96
    assert not validate_kms_attestation_policy(
        policy, account="444455556666", tenant=TENANT
    )


@pytest.mark.parametrize("override", [
    {"tenant": "client_real"},
    {"kms_key_arn": KMS.replace("eu-central-1", "eu-west-1")},
    {"kms_key_arn": KMS.replace(ACCOUNT, "444455556666")},
    {"queue_url": QUEUE.replace("eu-central-1", "eu-west-1")},
    {"queue_url": QUEUE.replace("pilot01", "pilot02")},
    {"bucket": "data-unknown"},
])
def test_sec04_invalid_scopes_rejected_without_aws(override):
    with pytest.raises(ValueError):
        audit(**params(**override), check=True,
              session_factory=lambda **kw: pytest.fail("AWS reached"))


def test_sec04_active_decrypt_grant_does_not_pass_attestation_policy():
    aws = FakeAWS(grants=[{
        "Operations": ["Decrypt"], "GranteePrincipal": "FICTIONAL-OPERATOR"
    }])
    report = audit(**params(), check=True, session_factory=lambda **kw: aws)
    assert report["checks"]["kms_attested_policy"] == "PASS"
    assert report["checks"]["kms_decrypt_grants"] == "FAIL"
    assert report["strict_zero_knowledge_verified"] is False


def test_sec04_cross_region_replication_not_allowed():
    aws = FakeAWS(replication=True)
    report = audit(**params(), check=True, session_factory=lambda **kw: aws)
    assert report["checks"]["s3_region"] == "PASS"
    assert report["checks"]["s3_no_replication"] == "FAIL"
    assert report["strict_zero_knowledge_verified"] is False
