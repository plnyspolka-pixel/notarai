"""SEC-10 KMS policy risk-screen regressions, strictly offline."""
from copy import deepcopy
import inspect

import pytest

from confidential.kms_policy_screen import (
    KmsPolicyNotAuditable, screen_kms_policy,
)


PCR17 = "a" * 96
ROLE = "arn:aws:iam::111122223333:role/notarai-confidential-pilot01"


def attested_statement():
    return {
        "Sid": "AllowOnlyAttestedTaskToDecrypt",
        "Effect": "Allow", "Principal": "*", "Action": ["kms:Decrypt"],
        "Resource": "*",
        "Condition": {
            "ArnEquals": {"aws:PrincipalArn": ROLE},
            "StringEqualsIgnoreCase": {
                "kms:RecipientAttestation:PCR17": PCR17,
                "kms:RecipientAttestation:PCR8:ServiceName":
                    "ecs.amazonaws.com",
            },
        },
    }


def policy():
    return {"Version": "2012-10-17", "Statement": [
        attested_statement()
    ]}


def assess(value=None):
    return screen_kms_policy(
        policy() if value is None else value,
        expected_pcr17=PCR17, expected_role_arn=ROLE,
    )


def test_attested_kms_decrypt_is_still_not_zero_operator_access_proof():
    result = assess()
    assert result.attestation_gated_decrypt_statement_count == 1
    assert result.unscoped_decrypt_allow_count == 0
    assert result.policy_mutation_allow_count == 0
    assert result.status == "BLOCKED_PENDING_INDEPENDENT_KMS_REVIEW"
    assert "INDEPENDENT_KMS_CUSTODY_UNVERIFIED" in result.findings
    assert result.zero_operator_access_verified is False


@pytest.mark.parametrize("action", [
    "kms:Decrypt", "kms:*", "kms:Dec*", "*",
])
def test_unattested_decrypt_actions_are_detected_even_with_valid_statement(
    action
):
    doc = policy()
    doc["Statement"].append({
        "Sid": "bad", "Effect": "Allow", "Principal": "*",
        "Action": action, "Resource": "*",
    })
    result = assess(doc)
    assert result.unscoped_decrypt_allow_count == 1
    assert "KMS_DECRYPT_ALLOW_OUTSIDE_ATTESTED_ROLE" in result.findings


@pytest.mark.parametrize("change", [
    {"kms:RecipientAttestation:PCR17": "f" * 96},
    {"kms:RecipientAttestation:PCR8:ServiceName": "eks.amazonaws.com"},
    {"kms:RecipientAttestation:PCR17": ["a" * 96]},
])
def test_wrong_or_multi_value_measurement_rejected_as_unscoped(change):
    doc = policy()
    checks = doc["Statement"][0]["Condition"]["StringEqualsIgnoreCase"]
    checks.update(change)
    result = assess(doc)
    assert result.attestation_gated_decrypt_statement_count == 0
    assert result.unscoped_decrypt_allow_count == 1


def test_missing_expected_role_or_arn_equals_causes_unscoped():
    doc = policy()
    doc["Statement"][0]["Condition"]["ArnEquals"] = {
        "aws:PrincipalArn":
            "arn:aws:iam::111122223333:role/notarai-confidential-pilot02"
    }
    assert assess(doc).unscoped_decrypt_allow_count == 1
    doc["Statement"][0]["Condition"].pop("ArnEquals")
    assert assess(doc).unscoped_decrypt_allow_count == 1


@pytest.mark.parametrize("action", [
    "kms:PutKeyPolicy", "kms:CreateGrant", "kms:Put*", "kms:*",
    "kms:ScheduleKeyDeletion",
])
def test_mutable_kms_policy_or_grant_path_requires_review(action):
    doc = policy()
    doc["Statement"].append({
        "Effect": "Allow", "Principal": {"AWS": "root"},
        "Action": [action], "Resource": "*",
    })
    result = assess(doc)
    assert result.policy_mutation_allow_count == 1
    assert "KMS_POLICY_OR_KEY_ADMIN_MUTATION_PATH" in result.findings


@pytest.mark.parametrize("name", ["NotAction", "NotPrincipal", "NotResource"])
def test_ambiguous_iam_constructs_block_positive_screen(name):
    doc = policy()
    doc["Statement"].append({
        "Effect": "Allow", "Principal": "*",
        "Action": ["kms:List*"], "Resource": "*",
        name: ["kms:Decrypt"],
    })
    result = assess(doc)
    assert result.unfamiliar_allow_statement_count == 1
    assert result.unscoped_decrypt_allow_count == 1
    assert result.policy_mutation_allow_count == 1


@pytest.mark.parametrize("variant", [
    {"Version": "2012-10-17", "Statement": []},
    {"Statement": [{"Effect": "Allow", "Principal": "*"}]},
    {"Statement": [{"Effect": "Unknown", "Action": "kms:Decrypt",
                    "Principal": "*"}]},
    {"Statement": [{"Effect": "Allow", "Action": "kms:Decrypt"}]},
    {"Statement": [{"Effect": "Allow", "Principal": "*", "Action": 123}]},
])
def test_unparseable_policy_fails_closed_with_constant_text(variant):
    with pytest.raises(KmsPolicyNotAuditable) as exc:
        assess(variant)
    assert str(exc.value) == "KMS policy cannot be screened"


def test_unscoped_allow_is_not_masked_by_deny():
    doc = policy()
    doc["Statement"].extend([
        {"Effect": "Allow", "Principal": "*",
         "Action": "kms:Decrypt", "Resource": "*"},
        {"Effect": "Deny", "Principal": "*",
         "Action": "kms:Decrypt", "Resource": "*"},
    ])
    assert assess(doc).unscoped_decrypt_allow_count == 1


def test_no_aws_or_deletion_or_private_material_in_screen():
    import confidential.kms_policy_screen as module
    source = inspect.getsource(module)
    for dangerous in (
        "boto3", "delete_object(", "get_key_policy(", "put_key_policy(",
        "kms.decrypt(", "Ed25519PrivateKey", "subprocess.",
    ):
        assert dangerous not in source
