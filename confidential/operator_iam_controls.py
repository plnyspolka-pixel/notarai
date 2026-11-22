"""SEC-02 offline operator guardrail verifier. No AWS calls or approvals.

Structural checks are not live IAM authorization, Organizations ownership or
independent custody proof. Never grants privileges or emits secrets.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping

SCENARIOS = {
    "ecr_image_replacement": {"ecr:PutImage", "ecr:BatchDeleteImage"},
    "passrole_abuse": {"iam:PassRole"},
    "cloudformation_execution_role": {
        "cloudformation:CreateStack", "cloudformation:ExecuteChangeSet",
        "iam:PassRole"},
    "kms_policy_or_grant_mutation": {"kms:PutKeyPolicy", "kms:CreateGrant"},
    "oidc_trust_spoofing": {
        "iam:UpdateAssumeRolePolicy",
        "iam:UpdateOpenIDConnectProviderThumbprint",
        "sts:AssumeRoleWithWebIdentity"},
    "cross_account_custody_assumption": {
        "sts:AssumeRole", "organizations:*"},
}
READ_ACTIONS = {"ecs:ListTasks", "ecr:DescribeImages", "sqs:GetQueueAttributes"}


class GuardrailError(ValueError):
    """An unsafe configuration without disclosing AWS input data."""


def require(ok, reason):
    if not ok:
        raise GuardrailError(reason)


def actions(statement):
    a = statement.get("Action")
    require(isinstance(a, (str, list)), "invalid action")
    if isinstance(a, str):
        return {a}
    require(bool(a) and all(isinstance(x, str) for x in a) and
            len(set(a)) == len(a), "duplicate or invalid action")
    return set(a)


def statements(policy):
    require(isinstance(policy, dict) and
            policy.get("Version") == "2012-10-17" and
            isinstance(policy.get("Statement"), list),
            "invalid IAM document")
    for s in policy["Statement"]:
        require(isinstance(s, dict) and
                set(s) == {"Sid", "Effect", "Action", "Resource"},
                "unreviewed IAM statement fields")
        actions(s)
    return policy["Statement"]


def validate_observer_template(template: Mapping):
    require(isinstance(template, dict), "invalid template")
    require(template.get("Parameters", {}).get(
        "TenantId", {}).get("AllowedValues") == ["pilot01", "pilot02"],
        "invalid tenant allowlist")
    conditions = template.get("Conditions", {})
    require(set(conditions) == {"PilotEuRegion", "DifferentAccount",
                                "SafePilot"},
            "region and distinct-account conditions missing")
    require(conditions["PilotEuRegion"] ==
            {"Equals": [{"Ref": "AWS::Region"}, "eu-central-1"]} and
            conditions["DifferentAccount"] == {"Not": [{"Equals": [
                {"Ref": "AWS::AccountId"}, {"Ref": "CustodyAccountId"}]}]} and
            conditions["SafePilot"] == {"And": [
                {"Condition": "PilotEuRegion"},
                {"Condition": "DifferentAccount"}]},
            "pilot account/region gate can be bypassed")
    resources = template.get("Resources", {})
    require(set(resources) == {"OperatorGuardrail", "OperatorObserverRole"},
            "extra resources")
    boundary = resources["OperatorGuardrail"]
    role = resources["OperatorObserverRole"]
    require(boundary.get("Type") == "AWS::IAM::ManagedPolicy" and
            role.get("Type") == "AWS::IAM::Role" and
            boundary.get("Condition") == role.get("Condition") == "SafePilot",
            "IAM resources not conditional")
    p = role["Properties"]
    require(p.get("MaxSessionDuration") == 3600 and
            p.get("PermissionsBoundary") == {"Ref": "OperatorGuardrail"} and
            not p.get("ManagedPolicyArns"),
            "role can bypass boundary")
    trust = p.get("AssumeRolePolicyDocument", {})
    expected = [{
        "Sid": "OnlyPreexistingOperatorSource",
        "Effect": "Allow",
        "Principal": {"AWS": {"Sub":
            "arn:aws:iam::${AWS::AccountId}:role/${SourceRoleName}"}},
        "Action": "sts:AssumeRole",
    }]
    require(trust.get("Version") == "2012-10-17" and
            trust.get("Statement") == expected,
            "unreviewed observer role trust")
    rows = statements(boundary["Properties"]["PolicyDocument"])
    denies = [r for r in rows if r["Effect"] == "Deny"]
    allows = [r for r in rows if r["Effect"] == "Allow"]
    require(len(denies) == 1 and
            denies[0]["Sid"] == "ExplicitlyDenyEscalation" and
            denies[0]["Resource"] == "*", "explicit Deny missing")
    denied = actions(denies[0])
    require(all(a <= denied for a in SCENARIOS.values()) and
            {"kms:Decrypt", "ecs:RunTask", "ecs:ExecuteCommand",
             "iam:DeleteRolePermissionsBoundary",
             "cloudformation:UpdateStack", "sso:*",
             "identitystore:*"} <= denied, "critical Deny missing")
    require(len(allows) == 3, "extra observer policy permission")
    exact_resources = {
        "ecs:ListTasks":
            "arn:aws:ecs:eu-central-1:${AWS::AccountId}:cluster/notarai-confidential-shared",
        "ecr:DescribeImages":
            "arn:aws:ecr:eu-central-1:${AWS::AccountId}:repository/notarai-confidential-shared",
        "sqs:GetQueueAttributes":
            "arn:aws:sqs:eu-central-1:${AWS::AccountId}:notarai-confidential-${TenantId}.fifo",
    }
    observed = set()
    for s in allows:
        a = actions(s)
        require(len(a) == 1 and a <= READ_ACTIONS and
                s["Resource"] == {"Sub": exact_resources[next(iter(a))]},
                "unreviewed or wildcard observer Allow")
        observed.update(a)
    require(observed == READ_ACTIONS, "read-only allowlist drift")
    policies = p.get("Policies")
    require(isinstance(policies, list) and len(policies) == 1 and
            statements(policies[0]["PolicyDocument"]) == allows,
            "observer role/boundary mismatch")
    return {name: "DENIED_BY_STATIC_POLICY" for name in SCENARIOS}


def validate_image_oidc_template(template: Mapping):
    """Static token/principal/permission pin; not a live GitHub OIDC proof."""
    require(isinstance(template, Mapping) and
            set(template.get("Resources", {})) == {"GuestImagePushRole"},
            "unreviewed OIDC resources")
    role = template["Resources"]["GuestImagePushRole"]["Properties"]
    require(not role.get("ManagedPolicyArns") and
            role.get("MaxSessionDuration") == 3600,
            "unreviewed publisher privilege")
    trust_doc = role.get("AssumeRolePolicyDocument", {})
    trust = trust_doc.get("Statement", [])
    require(trust_doc.get("Version") == "2012-10-17" and
            len(trust) == 1 and
            trust[0] == {
                "Effect": "Allow",
                "Principal": {"Federated": {"Sub":
                    "arn:aws:iam::${AWS::AccountId}:oidc-provider/token.actions.githubusercontent.com"}},
                "Action": "sts:AssumeRoleWithWebIdentity",
                "Condition": {"StringEquals": {
                    "token.actions.githubusercontent.com:aud":
                        "sts.amazonaws.com",
                    "token.actions.githubusercontent.com:sub": {
                        "Sub": "repo:${Repository}:ref:refs/heads/${Branch}"}}},
            },
            "OIDC principal, audience or subject is not pinned")
    policy = role.get("Policies")
    require(isinstance(policy, list) and len(policy) == 1 and
            policy[0].get("PolicyName") == "push-guest-image",
            "unreviewed publisher IAM policies")
    rows = statements(policy[0]["PolicyDocument"])
    expected = {
        "EcrLogin": {"Action": "ecr:GetAuthorizationToken",
                     "Resource": "*"},
        "PushPilotGuestImageOnly": {
            "Action": [
                "ecr:BatchCheckLayerAvailability", "ecr:InitiateLayerUpload",
                "ecr:UploadLayerPart", "ecr:CompleteLayerUpload",
                "ecr:PutImage", "ecr:BatchGetImage", "ecr:DescribeImages",
            ],
            "Resource": {"Sub":
                "arn:aws:ecr:${AWS::Region}:${AWS::AccountId}:repository/notarai-confidential-${TenantId}"},
        },
    }
    require(len(rows) == 2 and
            {s["Sid"] for s in rows} == set(expected) and
            all(s["Effect"] == "Allow" and
                s["Resource"] == expected[s["Sid"]]["Resource"] and
                s["Action"] == expected[s["Sid"]]["Action"] for s in rows),
            "publisher ECR policy widened")
    return "STATIC_TRUST_ONLY"

def assess_custody_ownership(operator_id: str, custody_id: str,
                             observation: Mapping | None = None):
    """Reject shared ownership, never infer independence from unverified data."""
    require(all(isinstance(x, str) and len(x) == 12 and x.isascii()
                and x.isdigit() for x in (operator_id, custody_id)),
            "invalid account IDs")
    if operator_id == custody_id:
        return "FAIL"
    if not observation:
        return "BLOCKED"
    if observation.get("custody_management_account") == operator_id:
        return "FAIL"
    for field in ("organization_id", "identity_center_admin",
                  "root_recovery_controller"):
        left = observation.get("operator_" + field)
        right = observation.get("custody_" + field)
        if left and left == right:
            return "FAIL"
    return "BLOCKED"  # Only independent signed & live evidence can PASS.


def validate_break_glass_procedure(p: Mapping):
    """Pure documentation gate. Does not authenticate approvers or grant roles."""
    require(isinstance(p, dict) and
            p.get("scope") == "metadata-only-recovery" and
            p.get("plaintext_access") is False and
            p.get("kms_decrypt") is False and
            p.get("custody_key_policy_write") is False and
            isinstance(p.get("audit_log_ref"), str) and
            p["audit_log_ref"].startswith("external-audit:"),
            "emergency policy cannot access key or plaintext")
    approvals = p.get("approvals")
    require(isinstance(approvals, list) and len(approvals) == 2 and
            all(isinstance(x, dict) for x in approvals),
            "two reviewers required")
    require({x.get("role") for x in approvals} ==
            {"custody_owner", "independent_security_reviewer"} and
            len({x.get("approver_id") for x in approvals}) == 2 and
            all(isinstance(x.get("approver_id"), str) and
                bool(x["approver_id"]) and
                isinstance(x.get("evidence_ref"), str) and
                x["evidence_ref"].startswith("external-audit:")
                for x in approvals), "independent approvals missing")
    try:
        start = datetime.fromisoformat(p["starts_at"])
        end = datetime.fromisoformat(p["expires_at"])
    except (KeyError, TypeError, ValueError):
        raise GuardrailError("no expiry") from None
    require(start.tzinfo is not None and end.tzinfo is not None and
            0 < (end.astimezone(timezone.utc) -
                 start.astimezone(timezone.utc)).total_seconds() <= 900,
            "15 minute limit exceeded")
    return "DOCUMENT_VALIDATION_ONLY_NOT_AUTHORIZED"
