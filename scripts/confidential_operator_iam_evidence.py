"""SEC-02 opt-in READ-ONLY AWS inventory & IAM simulation.

Usage (only with written authorization):
  python -m scripts.confidential_operator_iam_evidence --operator-profile NAME \
      --custody-profile NAME --tenant pilot01 --authorized-read-only

Does not mutate resources, request KMS Decrypt, run tasks, or test actual API
denials. AWS policy SIMULATION is informational and is NOT live deny evidence.
Never writes PII, tokens, AWS policy text, account IDs or raw AWS errors.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping

from confidential.operator_iam_controls import (
    GuardrailError, assess_custody_ownership, require,
)

_ACTIONS = {
    "ecr_image_replacement": "ecr:PutImage",
    "passrole_abuse": "iam:PassRole",
    "cloudformation_execution_role": "cloudformation:ExecuteChangeSet",
    "kms_policy_or_grant_mutation": "kms:PutKeyPolicy",
    "oidc_trust_spoofing": "iam:UpdateAssumeRolePolicy",
    "cross_account_custody_assumption": "sts:AssumeRole",
}


def sha_json(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str,
        allow_nan=False).encode("utf-8")).hexdigest()


def _read_org(session):
    try:
        data = session.client("organizations").describe_organization()["Organization"]
        return {
            "organization_id": data.get("Id"),
            "management_account": data.get(
                "ManagementAccountId", data.get("MasterAccountId")),
        }
    except Exception:  # no log of access denied or service exceptions
        return None


def inventory(*, operator_profile: str, custody_profile: str, tenant: str,
              authorized_read_only: bool = False, session_factory=None):
    require(authorized_read_only is True, "explicit authorization needed")
    require(operator_profile and custody_profile and
            operator_profile != custody_profile,
            "two distinct profile names required")
    require(tenant in ("pilot01", "pilot02"), "only synthetic tenants")
    if session_factory is None:
        import boto3  # optional; no AWS interaction unless explicit invocation
        session_factory = boto3.Session

    ops = session_factory(profile_name=operator_profile, region_name="eu-central-1")
    custody = session_factory(profile_name=custody_profile, region_name="eu-central-1")
    operator_id = ops.client("sts").get_caller_identity()["Account"]
    custody_id = custody.client("sts").get_caller_identity()["Account"]
    require(operator_id != custody_id, "custody is not separate")
    name = "notarai-confidential-operator-observer-" + tenant
    try:
        iam = ops.client("iam")
        role = iam.get_role(RoleName=name)["Role"]
        boundary_arn = role["PermissionsBoundary"]["PermissionsBoundaryArn"]
        policy = iam.get_policy(PolicyArn=boundary_arn)["Policy"]
        version = iam.get_policy_version(
            PolicyArn=boundary_arn,
            VersionId=policy["DefaultVersionId"],
        )["PolicyVersion"]["Document"]
        # AWS STS/Org/IAM read-only API; SIMULATION is not an actual denial.
        simulation = iam.simulate_principal_policy(
            PolicySourceArn=role["Arn"],
            ActionNames=list(_ACTIONS.values()),
            ResourceArns=["*"],
        ).get("EvaluationResults", [])
    except Exception:
        return {
            "schema": "notarai.sec02.readonly.v1",
            "live_read_only_performed": True,
            "policy_verified": False,
            "actual_denial_verified": False,
            "ownership_status": "BLOCKED",
            "simulation_status": "BLOCKED",
            "denial_by_scenario": {k: "BLOCKED" for k in _ACTIONS},
        }

    decisions = {
        x.get("EvalActionName"): x.get("EvalDecision")
        for x in simulation if isinstance(x, Mapping)
    }
    outcomes = {
        name: ("SIMULATED_DENY" if decisions.get(action) ==
               "explicitDeny" else "BLOCKED")
        for name, action in _ACTIONS.items()
    }
    a = _read_org(ops)
    b = _read_org(custody)
    observations = None
    if a and b:
        observations = {
            "operator_organization_id": a["organization_id"],
            "custody_organization_id": b["organization_id"],
            "custody_management_account": b["management_account"],
        }
    return {
        "schema": "notarai.sec02.readonly.v1",
        "live_read_only_performed": True,
        "policy_sha256": sha_json(version),
        "policy_verified": True,
        "actual_denial_verified": False,
        "ownership_status": assess_custody_ownership(
            operator_id, custody_id, observations),
        "simulation_status": (
            "SIMULATOR_DENIED_ALL_NOT_PROOF"
            if set(outcomes.values()) == {"SIMULATED_DENY"} else "BLOCKED"),
        "denial_by_scenario": outcomes,
        "organization_visibility": "READ" if observations else "BLOCKED",
        "root_sso_independent_attestation": "BLOCKED",
        "zero_operator_access_proven": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator-profile", required=True)
    parser.add_argument("--custody-profile", required=True)
    parser.add_argument("--tenant", choices=("pilot01", "pilot02"), required=True)
    parser.add_argument("--authorized-read-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = inventory(
            operator_profile=args.operator_profile,
            custody_profile=args.custody_profile, tenant=args.tenant,
            authorized_read_only=args.authorized_read_only)
    except (GuardrailError, Exception):
        result = {
            "schema": "notarai.sec02.readonly.v1", "status": "BLOCKED",
            "reason": "authorization or safe AWS read failed",
            "actual_denial_verified": False,
            "zero_operator_access_proven": False,
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("simulation_status") == (
        "SIMULATOR_DENIED_ALL_NOT_PROOF") else 2


if __name__ == "__main__":
    raise SystemExit(main())
