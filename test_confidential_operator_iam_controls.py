"""Six SEC-02 synthetic negative IAM probes: no AWS calls or credentials."""
import copy
from datetime import datetime, timedelta, timezone

import pytest
import yaml

from confidential.operator_iam_controls import (
    SCENARIOS, GuardrailError, assess_custody_ownership,
    validate_break_glass_procedure, validate_image_oidc_template,
    validate_observer_template,
)
from test_confidential_infra import CloudFormationLoader, ROOT


def template(filename):
    return yaml.load((ROOT / filename).read_text("utf-8"),
                     Loader=CloudFormationLoader)


def observer():
    return template("notarai-confidential-operator-iam.yaml")


def test_opt_in_observer_has_exact_scoped_read_only_permissions():
    t = observer()
    assert t["Conditions"]["PilotEuRegion"] == {
        "Equals": [{"Ref": "AWS::Region"}, "eu-central-1"]}
    assert t["Resources"]["OperatorObserverRole"]["Condition"] == "SafePilot"
    result = validate_observer_template(t)
    assert set(result) == set(SCENARIOS)
    assert set(result.values()) == {"DENIED_BY_STATIC_POLICY"}


@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
def test_six_operator_attack_paths_explicitly_denied(scenario):
    doc = observer()
    denied = set(doc["Resources"]["OperatorGuardrail"][
        "Properties"]["PolicyDocument"]["Statement"][0]["Action"])
    assert SCENARIOS[scenario] <= denied
    assert validate_observer_template(doc)[scenario] == "DENIED_BY_STATIC_POLICY"


@pytest.mark.parametrize("permission", [
    "ecr:PutImage", "iam:PassRole", "cloudformation:ExecuteChangeSet",
    "kms:CreateGrant", "iam:UpdateAssumeRolePolicy", "sts:AssumeRole",
    "kms:Decrypt", "ecs:RunTask", "iam:DeleteRolePermissionsBoundary",
])
def test_remove_critical_deny_is_rejected(permission):
    doc = observer()
    doc["Resources"]["OperatorGuardrail"]["Properties"][
        "PolicyDocument"]["Statement"][0]["Action"].remove(permission)
    with pytest.raises(GuardrailError):
        validate_observer_template(doc)


@pytest.mark.parametrize("mutation", [
    lambda x: x["Resources"]["OperatorObserverRole"][
        "Properties"].pop("PermissionsBoundary"),
    lambda x: x["Resources"]["OperatorObserverRole"]["Properties"][
        "Policies"][0]["PolicyDocument"]["Statement"][0].update(Action="iam:*"),
    lambda x: x["Resources"]["OperatorObserverRole"]["Properties"][
        "AssumeRolePolicyDocument"]["Statement"][0].update(
            Principal={"AWS": "*"}),
    lambda x: x["Resources"]["OperatorGuardrail"]["Properties"][
        "PolicyDocument"]["Statement"][1].update(Resource="*"),
    lambda x: x["Parameters"]["TenantId"].update(
        AllowedValues=["pilot01", "production"]),
    lambda x: x["Conditions"].pop("DifferentAccount"),
    lambda x: x["Resources"]["OperatorObserverRole"]["Properties"][
        "Policies"].append({"PolicyName": "admin", "PolicyDocument": {
            "Version": "2012-10-17", "Statement": []}}),
])
def test_identity_and_scope_mutations_are_rejected(mutation):
    doc = copy.deepcopy(observer())
    mutation(doc)
    with pytest.raises(GuardrailError):
        validate_observer_template(doc)


def test_oidc_publisher_has_no_wildcard_subject():
    doc = template("notarai-confidential-github.yaml")
    assert validate_image_oidc_template(doc) == "STATIC_TRUST_ONLY"
    doc["Resources"]["GuestImagePushRole"]["Properties"][
        "AssumeRolePolicyDocument"]["Statement"][0]["Condition"] = {
            "StringLike": {"token.actions.githubusercontent.com:sub": "repo:*"}
        }
    with pytest.raises(GuardrailError):
        validate_image_oidc_template(doc)


@pytest.mark.parametrize("obs,result", [
    (None, "BLOCKED"),
    ({"custody_management_account": "111122223333"}, "FAIL"),
    ({"operator_organization_id": "o-a",
      "custody_organization_id": "o-a"}, "FAIL"),
    ({"operator_identity_center_admin": "same",
      "custody_identity_center_admin": "same"}, "FAIL"),
    ({"operator_root_recovery_controller": "same",
      "custody_root_recovery_controller": "same"}, "FAIL"),
    ({"operator_organization_id": "o-a",
      "custody_organization_id": "o-b"}, "BLOCKED"),
])
def test_account_ids_never_prove_independence(obs, result):
    assert assess_custody_ownership(
        "111122223333", "444455556666", obs) == result


def test_same_aws_account_is_not_external_custody():
    assert assess_custody_ownership(
        "111122223333", "111122223333") == "FAIL"


def emergency():
    now = datetime(2026, 11, 22, tzinfo=timezone.utc)
    return {
        "scope": "metadata-only-recovery", "plaintext_access": False,
        "kms_decrypt": False, "custody_key_policy_write": False,
        "audit_log_ref": "external-audit:incident",
        "approvals": [
            {"role": "custody_owner", "approver_id": "reviewer-one",
             "evidence_ref": "external-audit:a"},
            {"role": "independent_security_reviewer",
             "approver_id": "reviewer-two", "evidence_ref": "external-audit:b"},
        ],
        "starts_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=15)).isoformat(),
    }


def test_break_glass_never_issues_authorization():
    assert validate_break_glass_procedure(emergency()) == (
        "DOCUMENT_VALIDATION_ONLY_NOT_AUTHORIZED")


@pytest.mark.parametrize("mutation", [
    lambda x: x["approvals"][1].update(approver_id="reviewer-one"),
    lambda x: x["approvals"].pop(),
    lambda x: x.update(plaintext_access=True),
    lambda x: x.update(kms_decrypt=True),
    lambda x: x.update(custody_key_policy_write=True),
    lambda x: x.update(audit_log_ref="mutable-local-log"),
    lambda x: x.update(expires_at="2026-11-22T00:16:00+00:00"),
    lambda x: x.update(scope="plaintext-recovery"),
])
def test_break_glass_negative_cases(mutation):
    record = emergency()
    mutation(record)
    with pytest.raises(GuardrailError):
        validate_break_glass_procedure(record)


def test_read_only_inventory_never_contacts_aws_without_opt_in():
    from scripts.confidential_operator_iam_evidence import inventory
    called = []
    def factory(**kwargs):
        called.append(kwargs)
        raise AssertionError("no AWS session should be created")
    with pytest.raises(GuardrailError):
        inventory(operator_profile="one", custody_profile="other",
                  tenant="pilot01", session_factory=factory)
    assert not called


class FakeAws:
    def __init__(self, profile_name, region_name):
        assert region_name == "eu-central-1"
        self.ops = profile_name == "operator"
    def client(self, name):
        source = self
        class C:
            def get_caller_identity(self):
                return {"Account": "111122223333" if source.ops
                        else "444455556666"}
            def get_role(self, **kw):
                assert kw["RoleName"] == (
                    "notarai-confidential-operator-observer-pilot01")
                return {"Role": {
                    "Arn": "arn:aws:iam::111122223333:role/operator-observer",
                    "PermissionsBoundary": {"PermissionsBoundaryArn":
                        "arn:aws:iam::111122223333:policy/boundary"},
                }}
            def get_policy(self, **kw):
                return {"Policy": {"DefaultVersionId": "v1"}}
            def get_policy_version(self, **kw):
                return {"PolicyVersion": {"Document": {
                    "Version": "2012-10-17", "Statement": [{"Effect": "Deny"}]}}}
            def simulate_principal_policy(self, **kw):
                assert len(kw["ActionNames"]) == 6
                return {"EvaluationResults": [
                    {"EvalActionName": a, "EvalDecision": "explicitDeny"}
                    for a in kw["ActionNames"]
                ]}
            def describe_organization(self):
                return {"Organization": {
                    "Id": "o-ops" if source.ops else "o-custody",
                    "ManagementAccountId": (
                        "111122223333" if source.ops else "444455556666")}}
        assert name in (("sts", "iam", "organizations") if self.ops
                        else ("sts", "organizations"))
        return C()


def test_read_only_inventory_records_simulation_not_real_denial():
    from scripts.confidential_operator_iam_evidence import inventory
    report = inventory(operator_profile="operator", custody_profile="custody",
                       tenant="pilot01", authorized_read_only=True,
                       session_factory=FakeAws)
    assert report["live_read_only_performed"] is True
    assert report["policy_verified"] is True
    assert len(report["policy_sha256"]) == 64
    assert report["simulation_status"] == "SIMULATOR_DENIED_ALL_NOT_PROOF"
    assert set(report["denial_by_scenario"].values()) == {"SIMULATED_DENY"}
    assert report["actual_denial_verified"] is False
    assert report["ownership_status"] == "BLOCKED"
    assert report["root_sso_independent_attestation"] == "BLOCKED"
    assert not report["zero_operator_access_proven"]
    assert "111122223333" not in str(report)
    assert "444455556666" not in str(report)


def test_missing_iam_read_or_simulator_is_blocked_not_pass():
    from scripts.confidential_operator_iam_evidence import inventory
    class Refused(FakeAws):
        def client(self, name):
            if name == "iam":
                raise PermissionError("not authorized")
            return super().client(name)
    report = inventory(operator_profile="operator", custody_profile="custody",
                       tenant="pilot01", authorized_read_only=True,
                       session_factory=Refused)
    assert report["simulation_status"] == "BLOCKED"
    assert report["actual_denial_verified"] is False
    assert set(report["denial_by_scenario"].values()) == {"BLOCKED"}


@pytest.mark.parametrize("tamper", [
    lambda doc: doc["Resources"]["GuestImagePushRole"]["Properties"][
        "AssumeRolePolicyDocument"]["Statement"][0].update(
            Principal={"AWS": "*"}),
    lambda doc: doc["Resources"]["GuestImagePushRole"]["Properties"][
        "AssumeRolePolicyDocument"]["Statement"][0].update(
            Principal={"Federated": {"Sub":
                "arn:aws:iam::${AWS::AccountId}:oidc-provider/attacker.example"}}),
    lambda doc: doc["Resources"]["GuestImagePushRole"]["Properties"][
        "Policies"][0]["PolicyDocument"]["Statement"][1]["Action"].append(
            "iam:PassRole"),
    lambda doc: doc["Resources"]["GuestImagePushRole"]["Properties"][
        "Policies"][0]["PolicyDocument"]["Statement"][1].update(
            Resource="*"),
    lambda doc: doc["Resources"]["GuestImagePushRole"]["Properties"][
        "Policies"].append({"PolicyName": "extra", "PolicyDocument": {
            "Version": "2012-10-17", "Statement": []}}),
])
def test_oidc_publisher_tampering_rejected(tamper):
    doc = template("notarai-confidential-github.yaml")
    tamper(doc)
    with pytest.raises(GuardrailError):
        validate_image_oidc_template(doc)
