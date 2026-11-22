"""SEC-06 contract for AWS-documented ECS confidential KMS attestation gates.

AWS KMS explicitly supports RecipientAttestation:PCR17 and
RecipientAttestation:PCR8:ServiceName=ecs.amazonaws.com. Verify that
both the custodian-only CloudFormation key and lifecycle-generated
policy include BOTH for the single attested Decrypt permission.

Official AWS documentation:
https://docs.aws.amazon.com/kms/latest/developerguide/conditions-nitro-enclave.html
https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ict-confidential-policy-configuration.html
"""
from confidential.custody_ops import render_kms_policy_target
from test_confidential_independent_custody_ops import WORKLOAD, CUSTODY, state
from test_confidential_infra import template


def test_k2_external_key_cloudformation_requires_both_aws_attestation_claims():
    data = template("notarai-confidential-external-custody-kms.yaml")
    statement = data["Resources"]["CustodianHeldKey"][
        "Properties"]["KeyPolicy"]["Statement"]
    assert len(statement) == 3
    decrypt = [s for s in statement if s["Sid"] ==
               "OnlyAttestedNitroTaskDecrypt"]
    assert len(decrypt) == 1
    rule = decrypt[0]
    assert rule["Action"] == "kms:Decrypt"
    assert rule["Effect"] == "Allow"
    assert rule["Principal"] == {
        "AWS": {"Sub": "arn:aws:iam::${WorkloadAccountId}:role/"
               "notarai-confidential-${TenantId}"}
    }
    gate = rule["Condition"]
    assert gate == {"StringEqualsIgnoreCase": {
        "kms:RecipientAttestation:PCR17": {"Ref": "ExpectedPCR17"},
        "kms:RecipientAttestation:PCR8:ServiceName": "ecs.amazonaws.com",
    }}
    assert all(
        "kms:Decrypt" not in str(item["Action"])
        for item in statement if item["Sid"] != "OnlyAttestedNitroTaskDecrypt"
    )
    assert "kms:CreateGrant" not in str(statement)


def test_k2_lifecycle_active_policy_requires_both_pinned_ecs_attestations():
    for tenant, number in (("pilot01", 1), ("pilot02", 2)):
        s = state(tenant, number)
        policy = render_kms_policy_target(s)["target_policy"]
        assert len(policy["Statement"]) == 3
        attested = policy["Statement"][2]
        assert attested["Principal"] == {
            "AWS": f"arn:aws:iam::{WORKLOAD}:"
                   f"role/notarai-confidential-{tenant}"}
        assert attested["Action"] == "kms:Decrypt"
        assert attested["Condition"] == {
            "StringEqualsIgnoreCase": {
                "kms:RecipientAttestation:PCR17": s["pcr17"],
                "kms:RecipientAttestation:PCR8:ServiceName":
                    "ecs.amazonaws.com",
            }}
        assert "kms:CreateGrant" not in str(policy)


def test_k4_frozen_revoked_lost_have_no_attested_or_unattested_decrypt():
    for lifecycle in ("FROZEN", "REVOKED", "LOST"):
        for tenant, number in (("pilot01", 1), ("pilot02", 2)):
            s = state(tenant, number)
            s["state"] = lifecycle
            policy = render_kms_policy_target(s)["target_policy"]
            assert len(policy["Statement"]) == 2
            assert "kms:Decrypt" not in str(policy)
            assert "kms:CreateGrant" not in str(policy)
            assert policy["Statement"][0]["Principal"] == {
                "AWS": f"arn:aws:iam::{CUSTODY}:root"}
            assert policy["Statement"][1]["Principal"] == {
                "AWS": f"arn:aws:iam::{WORKLOAD}:root"}
            assert policy["Statement"][1]["Action"] == [
                "kms:GetPublicKey", "kms:DescribeKey"]
