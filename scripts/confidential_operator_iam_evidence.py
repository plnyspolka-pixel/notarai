"""SEC-02: authorized, read-only AWS IAM inventory and offline policy comparison.

Run ONLY when both AWS account owners have explicitly approved access:
  python -m scripts.confidential_operator_iam_evidence \
      --operator-profile ops --custody-profile custody \
      --tenant pilot01 --authorized-read-only

This script never creates resources or attempts real privilege escalation.
A successful IAM simulation is NOT an actual denial, root/SSO independence
proof or permission to advertise Zero Operator Access. Output excludes
raw policy documents, names of humans, account IDs, tokens and AWS errors.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path

import yaml

from confidential.operator_iam_controls import (
    GuardrailError, assess_custody_ownership, require,
    validate_observer_template,
)

_ACTIONS = {
    "ecr_image_replacement": "ecr:PutImage",
    "passrole_abuse": "iam:PassRole",
    "cloudformation_execution_role": "cloudformation:ExecuteChangeSet",
    "kms_policy_or_grant_mutation": "kms:PutKeyPolicy",
    "oidc_trust_spoofing": "iam:UpdateAssumeRolePolicy",
    "cross_account_custody_assumption": "sts:AssumeRole",
}
ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "infra" / "notarai-confidential-operator-iam.yaml"


def sha_json(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False).encode("utf-8")).hexdigest()


class _CloudFormationLoader(yaml.SafeLoader):
    pass


def _cloudformation_tag(loader, suffix, node):
    require(isinstance(node, yaml.ScalarNode), "unexpected IaC intrinsic")
    return {suffix: loader.construct_scalar(node)}


_CloudFormationLoader.add_multi_constructor("!", _cloudformation_tag)


def expected_policy(operator_account: str, tenant: str):
    """Render strictly the known ${AccountId}/${TenantId} symbols, fail closed."""
    require(tenant in ("pilot01", "pilot02") and
            isinstance(operator_account, str) and
            bool(re.fullmatch(r"[0-9]{12}", operator_account)),
            "invalid IAM account or tenant")
    template = yaml.load(TEMPLATE.read_text("utf-8"),
                         Loader=_CloudFormationLoader)
    # The template includes sequence-valued intrinsics; only the expected IAM
    # policy needs substitution, never evaluate Conditions as code.
    validate_observer_template(template)
    raw = template["Resources"]["OperatorGuardrail"][
        "Properties"]["PolicyDocument"]
    mapping = {
        "AWS::AccountId": operator_account,
        "TenantId": tenant,
    }

    def render(value):
        if isinstance(value, dict) and set(value) == {"Sub"}:
            require(isinstance(value["Sub"], str), "invalid Fn::Sub")
            tokens = re.findall(r"\${([^}]+)}", value["Sub"])
            require(set(tokens) <= set(mapping), "unexpected IaC symbol")
            return re.sub(r"\${([^}]+)}",
                          lambda m: mapping[m.group(1)], value["Sub"])
        if isinstance(value, dict):
            return {k: render(v) for k, v in value.items()}
        if isinstance(value, list):
            return [render(v) for v in value]
        return value
    return render(raw)


def _read_org(session):
    try:
        org = session.client("organizations").describe_organization()[
            "Organization"]
        return {
            "organization_id": org.get("Id"),
            "management_account": org.get(
                "ManagementAccountId", org.get("MasterAccountId")),
        }
    except Exception:
        return None


def _blocked(*, collected: bool = False, cause: str = "IAM_READ_BLOCKED"):
    return {
        "schema": "notarai.sec02.readonly.v2",
        "live_read_only_performed": collected,
        "policy_contract_matches_source": False,
        "policy_sha256": None,
        "actual_denial_verified": False,
        "ownership_status": "BLOCKED",
        "simulation_status": "BLOCKED",
        "reason": cause,
        "denial_by_scenario": {key: "BLOCKED" for key in _ACTIONS},
        "root_sso_independent_attestation": "BLOCKED",
        "zero_operator_access_proven": False,
    }


def inventory(*, operator_profile: str, custody_profile: str, tenant: str,
              authorized_read_only: bool = False, session_factory=None):
    require(authorized_read_only is True, "explicit authorization required")
    require(isinstance(operator_profile, str) and operator_profile.strip() and
            isinstance(custody_profile, str) and custody_profile.strip() and
            operator_profile != custody_profile,
            "distinct AWS profiles required")
    require(tenant in ("pilot01", "pilot02"), "only synthetic tenants")
    if session_factory is None:
        import boto3  # import only after explicit authorization gate
        session_factory = boto3.Session

    ops = session_factory(profile_name=operator_profile,
                          region_name="eu-central-1")
    cust = session_factory(profile_name=custody_profile,
                           region_name="eu-central-1")
    try:
        operator_id = ops.client("sts").get_caller_identity()["Account"]
        custody_id = cust.client("sts").get_caller_identity()["Account"]
    except Exception:
        return _blocked(cause="IDENTITY_READ_BLOCKED")
    if operator_id == custody_id:
        return _blocked(collected=True, cause="SAME_ACCOUNT")
    # No account ID included in output.
    require(all(re.fullmatch(r"[0-9]{12}", x)
                for x in (operator_id, custody_id)),
            "invalid caller identity")
    name = f"notarai-confidential-operator-observer-{tenant}"
    role_arn = f"arn:aws:iam::{operator_id}:role/{name}"
    boundary_arn = (f"arn:aws:iam::{operator_id}:policy/"
                    f"notarai-confidential-operator-boundary-{tenant}")
    try:
        iam = ops.client("iam")
        role = iam.get_role(RoleName=name)["Role"]
        require(role.get("Arn") == role_arn and
                role.get("PermissionsBoundary", {}).get(
                    "PermissionsBoundaryArn") == boundary_arn,
                "observer role or boundary mismatch")
        policy = iam.get_policy(PolicyArn=boundary_arn)["Policy"]
        require(policy.get("Arn") == boundary_arn,
                "IAM policy ARN mismatch")
        version_id = policy["DefaultVersionId"]
        require(isinstance(version_id, str) and version_id.startswith("v"),
                "unreviewed IAM policy version")
        document = iam.get_policy_version(
            PolicyArn=boundary_arn,
            VersionId=version_id,
        )["PolicyVersion"]["Document"]
        require(isinstance(document, Mapping), "invalid AWS policy document")
        expect = expected_policy(operator_id, tenant)
        source_match = document == expect
        if not source_match:
            # Return only a hash; do not simulate drifted permissions.
            return {
                **_blocked(collected=True, cause="POLICY_DRIFT"),
                "policy_sha256": sha_json(document),
            }
        # SimulatePrincipalPolicy is a READ-ONLY query; still no actual
        # resource-specific deny or SCP/Organizations assertion.
        response = iam.simulate_principal_policy(
            PolicySourceArn=role_arn,
            ActionNames=list(_ACTIONS.values()),
            ResourceArns=["*"],
        )
        results = response.get("EvaluationResults")
        require(isinstance(results, list) and not response.get("IsTruncated"),
                "incomplete IAM simulation")
        decisions = {}
        for item in results:
            require(isinstance(item, Mapping) and
                    item.get("EvalActionName") in _ACTIONS.values() and
                    item["EvalActionName"] not in decisions and
                    item.get("EvalDecision") in (
                        "explicitDeny", "implicitDeny", "allowed"),
                    "invalid or ambiguous simulation result")
            decisions[item["EvalActionName"]] = item["EvalDecision"]
        require(set(decisions) == set(_ACTIONS.values()),
                "missing IAM simulation actions")
    except Exception:
        return _blocked(collected=True)

    outcomes = {
        scenario: ("SIMULATED_DENY" if decisions[action] == "explicitDeny"
                   else "BLOCKED")
        for scenario, action in _ACTIONS.items()
    }
    operator_org = _read_org(ops)
    custody_org = _read_org(cust)
    observations = None
    if operator_org and custody_org:
        observations = {
            "operator_organization_id": operator_org["organization_id"],
            "custody_organization_id": custody_org["organization_id"],
            "custody_management_account": custody_org["management_account"],
        }
    return {
        "schema": "notarai.sec02.readonly.v2",
        "live_read_only_performed": True,
        "policy_sha256": sha_json(document),
        "policy_contract_matches_source": True,
        "actual_denial_verified": False,
        "ownership_status": assess_custody_ownership(
            operator_id, custody_id, observations),
        "simulation_status": (
            "SIMULATOR_DENIED_ALL_NOT_PROOF"
            if all(v == "SIMULATED_DENY" for v in outcomes.values())
            else "BLOCKED"),
        "denial_by_scenario": outcomes,
        "organization_visibility": (
            "READ_ONLY_PARTIAL" if observations else "BLOCKED"),
        "root_sso_independent_attestation": "BLOCKED",
        "zero_operator_access_proven": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator-profile", required=True)
    parser.add_argument("--custody-profile", required=True)
    parser.add_argument("--tenant", choices=("pilot01", "pilot02"),
                        required=True)
    parser.add_argument("--authorized-read-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = inventory(
            operator_profile=args.operator_profile,
            custody_profile=args.custody_profile,
            tenant=args.tenant,
            authorized_read_only=args.authorized_read_only,
        )
    except Exception:
        result = _blocked(cause="AUTHORIZATION_OR_READ_BLOCKED")
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("simulation_status") == (
        "SIMULATOR_DENIED_ALL_NOT_PROOF") else 2


if __name__ == "__main__":
    raise SystemExit(main())
