"""Synthetic no-AWS proof tests for independent NotarAI key custody."""
import copy
import json

import pytest
import yaml

from confidential.operator_boundary import (
    BoundaryDenied, inspect_operator_boundary, canonical_digest,
)
from scripts.verify_confidential_operator_boundary import inspect
from test_confidential_infra import ROOT, CloudFormationLoader
from test_confidential_dispatch import expected_task

OPERATOR = "111122223333"
CUSTODY = "444455556666"
TENANT = "pilot01"
PCR = "a" * 96
DIGEST = "b" * 64
TASK = f"arn:aws:ecs:eu-central-1:{OPERATOR}:task-definition/notarai-confidential-{TENANT}:12"
KEY = f"arn:aws:kms:eu-central-1:{CUSTODY}:key/11111111-2222-3333-4444-555555555555"
ADMIN = [
    "kms:DescribeKey", "kms:GetKeyPolicy", "kms:PutKeyPolicy",
    "kms:EnableKey", "kms:DisableKey", "kms:UpdateKeyDescription",
    "kms:ListResourceTags", "kms:TagResource", "kms:UntagResource",
    "kms:ScheduleKeyDeletion", "kms:CancelKeyDeletion",
]


def fixture():
    sample = expected_task()["taskDefinition"]
    sample["containerDefinitions"][0]["image"] = (
        f"{OPERATOR}.dkr.ecr.eu-central-1.amazonaws.com/"
        "notarai-confidential-shared@sha256:" + DIGEST
    )
    sample["containerDefinitions"][0]["environment"] = [
        {**item,
         "value": KEY if item["name"] == "NOTARAI_CONFIDENTIAL_KMS_KEY_ARN"
         else item["value"]}
        for item in sample["containerDefinitions"][0]["environment"]
    ]
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "CustodyAdministratorOnly", "Effect": "Allow",
                "Principal": {"AWS": f"arn:aws:iam::{CUSTODY}:root"},
                "Action": ADMIN, "Resource": "*",
            },
            {
                "Sid": "NotaraiPublicKeyOnly", "Effect": "Allow",
                "Principal": {"AWS": f"arn:aws:iam::{OPERATOR}:root"},
                "Action": ["kms:GetPublicKey", "kms:DescribeKey"],
                "Resource": "*",
            },
            {
                "Sid": "OnlyAttestedNitroTaskDecrypt", "Effect": "Allow",
                "Principal": {"AWS": f"arn:aws:iam::{OPERATOR}:role/notarai-confidential-{TENANT}"},
                "Action": "kms:Decrypt", "Resource": "*",
                "Condition": {"StringEqualsIgnoreCase": {
                    "kms:RecipientAttestation:PCR17": PCR,
                    "kms:RecipientAttestation:PCR8:ServiceName": "ecs.amazonaws.com",
                }},
            },
        ],
    }
    return {
        "operator_account": OPERATOR, "custody_account": CUSTODY,
        "tenant": TENANT, "key_arn": KEY, "pcr17": PCR,
        "image_sha256": DIGEST, "task_arn": TASK,
        "key_metadata": {
            "Arn": KEY, "AWSAccountId": CUSTODY, "KeyManager": "CUSTOMER",
            "Origin": "AWS_KMS", "KeySpec": "RSA_3072",
            "KeyUsage": "ENCRYPT_DECRYPT", "KeyState": "Enabled",
            "Enabled": True, "MultiRegion": False,
        },
        "key_policy": policy, "key_grants": [],
        "task_definition": sample,
    }


def test_structural_proof_is_appropriately_limited():
    result = inspect_operator_boundary(**fixture())
    assert result["static_configuration_verified"] is True
    assert result["live_nitro_attestation_verified"] is False
    assert result["independent_custody_verified"] is False
    assert result["zero_operator_access_proven"] is False
    assert result["key_policy_sha256"] == canonical_digest(fixture()["key_policy"])
    assert "FICTIONAL" not in str(result)


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(custody_account=OPERATOR),
    lambda d: d.update(pcr17="0" * 96),
    lambda d: d.update(image_sha256="f" * 63),
    lambda d: d.update(tenant="pilot02"),
    lambda d: d.update(key_arn=d["key_arn"].replace(CUSTODY, OPERATOR)),
    lambda d: d["key_metadata"].update(AWSAccountId=OPERATOR),
    lambda d: d["key_metadata"].update(KeySpec="SYMMETRIC_DEFAULT"),
    lambda d: d["key_metadata"].update(KeyState="Disabled"),
    lambda d: d["key_grants"].append({
        "GranteePrincipal": f"arn:aws:iam::{OPERATOR}:root",
        "Operations": ["Decrypt"],
    }),
    lambda d: d["key_policy"]["Statement"][0].update(
        Action=ADMIN + ["kms:Decrypt"]),
    lambda d: d["key_policy"]["Statement"][0].update(
        Principal={"AWS": f"arn:aws:iam::{OPERATOR}:root"}),
    lambda d: d["key_policy"]["Statement"][1].update(
        Action=["kms:GetPublicKey", "kms:DescribeKey", "kms:PutKeyPolicy"]),
    lambda d: d["key_policy"]["Statement"][1].update(
        Principal={"AWS": "*"}),
    lambda d: d["key_policy"]["Statement"][2].update(
        Action="kms:*"),
    lambda d: d["key_policy"]["Statement"][2].update(
        Principal={"AWS": "*"}),
    lambda d: d["key_policy"]["Statement"][2]["Condition"][
        "StringEqualsIgnoreCase"].pop("kms:RecipientAttestation:PCR17"),
    lambda d: d["key_policy"]["Statement"][2]["Condition"][
        "StringEqualsIgnoreCase"].pop(
            "kms:RecipientAttestation:PCR8:ServiceName"),
    lambda d: d["key_policy"]["Statement"][2]["Condition"][
        "StringEqualsIgnoreCase"].update(
            {"kms:RecipientAttestation:PCR17": "0" * 96}),
    lambda d: d["key_policy"]["Statement"].append({
        "Sid": "ExtraPermission", "Effect": "Allow",
        "Principal": {"AWS": "*"}, "Action": "kms:Decrypt",
        "Resource": "*",
    }),
    lambda d: d["key_policy"]["Statement"][1].update(
        NotAction="kms:DescribeKey"),
    lambda d: d["task_definition"]["containerDefinitions"][0].update(
        privileged=True),
    lambda d: d["task_definition"]["containerDefinitions"][0].update(
        logConfiguration={"logDriver": "awslogs"}),
    lambda d: d["task_definition"]["containerDefinitions"][0].update(
        image="untrusted:latest"),
    lambda d: d["task_definition"].update(
        taskRoleArn=f"arn:aws:iam::{OPERATOR}:role/admin"),
    lambda d: d["task_definition"]["containerDefinitions"][0][
        "environment"][3].update(value="not-tenant-scoped"),
    lambda d: d["task_definition"]["trustedExecutionConfiguration"].update(
        isolationMode="ISOLATED"),
])
def test_operator_privilege_escalation_is_rejected(mutate):
    data = copy.deepcopy(fixture())
    mutate(data)
    with pytest.raises(BoundaryDenied):
        inspect_operator_boundary(**data)


def test_external_custody_cloudformation_requires_independent_account_and_pcr():
    file = ROOT / "notarai-confidential-external-custody-kms.yaml"
    infra = yaml.load(file.read_text("utf-8"), Loader=CloudFormationLoader)
    params = infra["Parameters"]
    assert "WorkloadAccountId" in params
    assert "CustodyAcknowledgement" in params
    assert "TenantId" in params
    assert "(?!0{96}$)" in params["ExpectedPCR17"]["AllowedPattern"]
    key = infra["Resources"]["CustodianHeldKey"]
    assert key["Condition"] == "CustodyAccountDifferent"
    assert key["DeletionPolicy"] == "Retain"
    assert key["Properties"]["KeySpec"] == "RSA_3072"
    statements = key["Properties"]["KeyPolicy"]["Statement"]
    assert len(statements) == 3
    actions = {x["Sid"]: x["Action"] for x in statements}
    assert "kms:Decrypt" not in actions["CustodyAdministratorOnly"]
    assert "kms:PutKeyPolicy" not in actions["NotaraiPublicKeyOnly"]
    assert actions["OnlyAttestedNitroTaskDecrypt"] == "kms:Decrypt"
    assert "kms:CreateGrant" not in str(key)


def test_two_distinct_profiles_and_no_aws_call_by_default():
    assert inspect(
        operator_profile="ops", custody_profile="independent",
        tenant=TENANT, task_definition_arn=TASK,
        kms_key_arn=KEY, pcr17=PCR, image_sha256=DIGEST,
        session_factory=lambda **kw: 1,
    )["aws_calls"] == 0
    with pytest.raises(BoundaryDenied):
        inspect(
            operator_profile="same", custody_profile="same",
            tenant=TENANT, task_definition_arn=TASK,
            kms_key_arn=KEY, pcr17=PCR, image_sha256=DIGEST,
        )


class FakeSession:
    def __init__(self, profile_name, region_name):
        assert region_name == "eu-central-1"
        self.operator = profile_name == "ops"
        self.data = fixture()
    def client(self, name):
        session = self
        class C:
            def get_caller_identity(self):
                return {"Account": OPERATOR if session.operator else CUSTODY}
            def describe_key(self, **kwargs):
                assert kwargs["KeyId"] == KEY
                return {"KeyMetadata": session.data["key_metadata"]}
            def get_key_policy(self, **kwargs):
                assert kwargs["KeyId"] == KEY
                return {"Policy": json.dumps(session.data["key_policy"])}
            def list_grants(self, **kwargs):
                return {"Grants": []}
            def describe_task_definition(self, **kwargs):
                assert kwargs["taskDefinition"] == TASK
                return {"taskDefinition": session.data["task_definition"]}
        assert name in (("sts", "ecs") if self.operator else ("sts", "kms"))
        return C()


def test_dual_account_read_only_inspection_uses_no_decrypt_or_iam_calls():
    result = inspect(
        operator_profile="ops", custody_profile="independent",
        tenant=TENANT, task_definition_arn=TASK, kms_key_arn=KEY,
        pcr17=PCR, image_sha256=DIGEST, check=True,
        session_factory=FakeSession,
    )
    assert result["static_configuration_verified"]
    assert not result["zero_operator_access_proven"]


def test_same_account_refuses_before_kms_inspection():
    class Same(FakeSession):
        def client(self, name):
            client = super().client(name)
            if name == "sts":
                client.get_caller_identity = lambda: {"Account": OPERATOR}
            return client
    with pytest.raises(BoundaryDenied):
        inspect(
            operator_profile="ops", custody_profile="independent",
            tenant=TENANT, task_definition_arn=TASK, kms_key_arn=KEY,
            pcr17=PCR, image_sha256=DIGEST, check=True,
            session_factory=Same,
        )
