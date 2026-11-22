"""SEC-06 synthetic custodian-owned DynamoDB CAS transaction compiler tests."""
import copy

import pytest

from confidential.custody_cas import compile_signed_cas
from confidential.custody_ops import _IDENTITY_FIELDS, _ROTATION_FIELDS
from confidential.operator_boundary import BoundaryDenied, canonical_digest
from test_confidential_independent_custody_ops import (
    CUSTODY, NOW, WORKLOAD, apply, signer, signed_event, state,
)

TABLE = (f"arn:aws:dynamodb:eu-central-1:{CUSTODY}:table/"
         "notarai-confidential-custody-ledger-pilot")


def compile_plan(previous, event, public, pin, table=TABLE, expected=None):
    return compile_signed_cas(
        state=previous, envelope=event,
        trusted_public_key_pem=public,
        pinned_public_key_sha256=pin,
        independently_pinned_previous_state_sha256=(
            expected if expected is not None
            else canonical_digest(previous) if previous else "0" * 64),
        ledger_table_arn=table, clock=NOW,
    )


def test_k4_enroll_compiles_single_untamperable_atomic_transaction_frozen():
    private, public, pin = signer()
    binding = state()
    envelope = signed_event(
        private, action="ENROLL",
        changes={k: binding[k] for k in _IDENTITY_FIELDS})
    plan = compile_plan(None, envelope, public, pin)
    assert plan["status"] == "BLOCKED_PENDING_EXTERNAL_CUSTODY_EXECUTION"
    assert plan["aws_calls"] == 0
    assert plan["dynamodb_atomic_write_performed"] is False
    assert plan["independent_custody_verified"] is False
    assert plan["effective_revocation_verified"] is False
    assert plan["new_state_revision"] == 1
    tx = plan["proposed_transaction"]
    assert len(tx["ClientRequestToken"]) == 36
    assert len(tx["TransactItems"]) == 2
    current = tx["TransactItems"][0]["Put"]
    event = tx["TransactItems"][1]["Put"]
    assert current["TableName"] == TABLE
    assert current["ConditionExpression"] == "attribute_not_exists(#tenant)"
    assert current["Item"]["tenant"] == {"S": "TENANT#pilot01"}
    assert current["Item"]["record"] == {"S": "STATE"}
    assert '"state":"FROZEN"' in current["Item"]["state_json"]["S"]
    assert event["ConditionExpression"] == "attribute_not_exists(#tenant)"
    assert event["Item"]["record"] == {"S": "EVENT#00000000000000000001"}
    assert event["Item"]["retired_decrypt_key_arn"] == {"NULL": True}


def test_k4_frozen_ledger_cas_requires_exact_previous_sha_and_revision():
    private, public, pin = signer()
    s = state()
    envelope = signed_event(private, action="FREEZE", previous=s)
    plan = compile_plan(s, envelope, public, pin)
    put = plan["proposed_transaction"]["TransactItems"][0]["Put"]
    assert put["ExpressionAttributeValues"] == {
        ":previous": {"S": canonical_digest(s)},
        ":old_revision": {"N": "1"},
    }
    assert put["ConditionExpression"] == (
        "#sha = :previous AND #revision = :old_revision")
    assert plan["new_state_revision"] == 2
    assert not plan["dynamodb_atomic_write_performed"]
    assert compile_plan(s, envelope, public, pin)[
        "proposed_transaction"]["ClientRequestToken"] == plan[
        "proposed_transaction"]["ClientRequestToken"]
    with pytest.raises(BoundaryDenied):
        compile_plan(s, envelope, public, pin, expected="f" * 64)
    frozen = apply(s, envelope, public, pin)
    with pytest.raises(BoundaryDenied):
        compile_plan(frozen, envelope, public, pin)


def test_k5_rotation_cas_records_retired_old_key_while_new_one_is_frozen():
    private, public, pin = signer()
    s = state()
    frozen = apply(s, signed_event(
        private, action="FREEZE", previous=s), public, pin)
    fresh = state("pilot01", 2)
    rotation_fields = {k: fresh[k] for k in _ROTATION_FIELDS}
    event = signed_event(
        private, action="ROTATE", previous=frozen,
        changes=rotation_fields)
    plan = compile_plan(frozen, event, public, pin)
    assert plan["new_state_revision"] == 3
    assert plan["requires_historical_decrypt_key_audit"] is True
    tx = plan["proposed_transaction"]["TransactItems"]
    assert tx[1]["Put"]["Item"]["retired_decrypt_key_arn"] == {
        "S": frozen["decrypt_key_arn"]}
    assert '"state":"FROZEN"' in tx[0]["Put"]["Item"]["state_json"]["S"]
    assert fresh["decrypt_key_arn"] in tx[0]["Put"]["Item"]["state_json"]["S"]


def test_k4_k5_unfreeze_must_not_be_compiled_without_live_kms_release_proof():
    private, public, pin = signer()
    s = state()
    frozen = apply(s, signed_event(
        private, action="FREEZE", previous=s), public, pin)
    signed = signed_event(
        private, action="UNFREEZE", previous=frozen)
    with pytest.raises(BoundaryDenied, match="live KMS release proof"):
        compile_plan(frozen, signed, public, pin)


@pytest.mark.parametrize("bad_table", [
    "notarai-confidential-custody-ledger-pilot",
    f"arn:aws:dynamodb:us-east-1:{CUSTODY}:table/"
    "notarai-confidential-custody-ledger-pilot",
    f"arn:aws:dynamodb:eu-central-1:{WORKLOAD}:table/"
    "notarai-confidential-custody-ledger-pilot",
    f"arn:aws:dynamodb:eu-central-1:{CUSTODY}:table/"
    "notarai-production",
])
def test_k1_cas_cannot_target_operator_or_unapproved_table(bad_table):
    private, public, pin = signer()
    s = state()
    signed = signed_event(private, action="FREEZE", previous=s)
    with pytest.raises(BoundaryDenied):
        compile_plan(s, signed, public, pin, table=bad_table)


def test_k5_signed_cas_rejects_forgery_cross_tenant_and_wrong_pin():
    private, public, pin = signer()
    wrong, _, _ = signer()
    s = state()
    event = signed_event(private, action="REVOKE", previous=s)
    with pytest.raises(BoundaryDenied):
        compile_plan(s, event, public, "f" * 64)
    with pytest.raises(BoundaryDenied):
        compile_plan(s, signed_event(
            wrong, action="REVOKE", previous=s), public, pin)
    with pytest.raises(BoundaryDenied):
        compile_plan(s, signed_event(
            private, action="REVOKE", previous=s, tenant="pilot02"),
            public, pin)
    forged = copy.deepcopy(event)
    forged["payload"]["action"] = "MARK_LOST"
    with pytest.raises(BoundaryDenied):
        compile_plan(s, forged, public, pin)


@pytest.mark.parametrize("invalid", [
    {"payload": [], "signature_b64": "AA=="},
    {"payload": None, "signature_b64": ""},
    {"payload": {"changes": None}, "signature_b64": ""},
])
def test_k4_malformed_cas_envelope_fails_closed(invalid):
    _, public, pin = signer()
    with pytest.raises(BoundaryDenied):
        compile_plan(None, invalid, public, pin)


def test_k6_cas_plan_is_not_stored_does_not_sign_or_decrypt():
    private, public, pin = signer()
    s = state()
    event = signed_event(private, action="MARK_LOST", previous=s)
    plan = compile_plan(s, event, public, pin)
    assert plan["aws_calls"] == 0
    assert plan["dynamodb_atomic_write_performed"] is False
    assert plan["requires_live_kms_policy_and_grant_proof"] is True
    assert plan["requires_separate_custody_aws_identity_check"] is True
    assert "Decrypt" not in str(plan)
    assert "PutKeyPolicy" not in str(plan)



def test_k1_k4_custody_ledger_template_immutable_recovery_and_eu_only():
    from test_confidential_infra import template
    deployment = template("notarai-confidential-custody-ledger-pilot.yaml")
    assert "SafePilotBoundary" in deployment["Conditions"]
    assert "EUFrankfurtOnly" in deployment["Conditions"]
    assert "IndependentCustodyAccount" in deployment["Conditions"]
    resources = deployment["Resources"]
    assert len(resources) == 1
    ledger = resources["SyntheticCustodyLedger"]
    assert ledger["Condition"] == "SafePilotBoundary"
    assert ledger["DeletionPolicy"] == "Retain"
    assert ledger["UpdateReplacePolicy"] == "Retain"
    assert ledger["Type"] == "AWS::DynamoDB::Table"
    properties = ledger["Properties"]
    assert properties["TableName"] == "notarai-confidential-custody-ledger-pilot"
    assert properties["DeletionProtectionEnabled"] is True
    assert properties["PointInTimeRecoverySpecification"][
        "PointInTimeRecoveryEnabled"] is True
    assert properties["SSESpecification"]["SSEEnabled"] is True
    assert properties["SSESpecification"]["SSEType"] == "KMS"
    assert properties["SSESpecification"]["KMSMasterKeyId"] == "alias/aws/dynamodb"
    assert properties["BillingMode"] == "PAY_PER_REQUEST"
    assert properties["KeySchema"] == [
        {"AttributeName": "tenant", "KeyType": "HASH"},
        {"AttributeName": "record", "KeyType": "RANGE"},
    ]
    assert not any(item["Type"].startswith("AWS::IAM::")
                   for item in resources.values())
