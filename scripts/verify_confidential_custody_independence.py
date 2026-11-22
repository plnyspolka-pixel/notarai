"""SEC-06 read-only AWS Organizations / IAM custody independence preflight.

This tool cannot attest legal account ownership, root custody, external
IdP/SSO administration or organizational control. A successful structural
check is never a Zero Operator Access claim. It NEVER changes AWS resources.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from confidential.operator_boundary import BoundaryDenied

_REGION = "eu-central-1"


def _account(session):
    ident = session.client("sts").get_caller_identity()
    value = ident.get("Account")
    if not isinstance(value, str) or len(value) != 12 or not value.isdigit():
        raise BoundaryDenied("AWS account identity unavailable")
    return value


def _organization(session):
    try:
        info = session.client("organizations").describe_organization()["Organization"]
    except Exception:
        # Standalone accounts legitimately return AWSOrganizationsNotInUseException.
        # We cannot distinguish that here without identifying the error, so fail
        # closed and request independent documentation.
        raise BoundaryDenied("Organizations evidence unavailable") from None
    org = info.get("Id")
    manager = info.get("ManagementAccountId") or info.get("MasterAccountId")
    if not isinstance(org, str) or not isinstance(manager, str):
        raise BoundaryDenied("Organizations management evidence incomplete")
    return org, manager


def _trust_principals(document):
    """Return typed trust principals and refuse unreviewed federation.

    A custody account role which trusts GitHub OIDC, SAML, another AWS
    account, or an arbitrary AWS service may be controlled by NotarAI even
    when neither role ARN contains the workload account number.
    """
    if not isinstance(document, dict) or "Statement" not in document:
        raise BoundaryDenied("IAM role trust document missing")
    statements = document["Statement"]
    if isinstance(statements, dict):
        statements = [statements]
    if not isinstance(statements, list) or not statements:
        raise BoundaryDenied("IAM trust statements invalid")
    principals = []
    for stmt in statements:
        if not isinstance(stmt, dict) or stmt.get("Effect") not in ("Allow", "Deny"):
            raise BoundaryDenied("IAM trust statement invalid")
        if stmt["Effect"] == "Deny":
            continue
        if ("NotPrincipal" in stmt or "NotAction" in stmt or
                "NotResource" in stmt):
            raise BoundaryDenied("inverted IAM trust requires independent review")
        actions = stmt.get("Action")
        if isinstance(actions, str):
            actions = [actions]
        if not isinstance(actions, list) or not actions or any(
            a != "sts:AssumeRole" for a in actions
        ):
            raise BoundaryDenied("unreviewed IAM role assumption method")
        principal = stmt.get("Principal")
        if not isinstance(principal, dict) or not principal:
            raise BoundaryDenied("IAM trust principal missing")
        for group, value in principal.items():
            if group not in {"AWS", "Service", "Federated"}:
                raise BoundaryDenied("unknown IAM trust principal type")
            values = [value] if isinstance(value, str) else value
            if not isinstance(values, list) or not values or not all(
                isinstance(v, str) and bool(v) for v in values
            ):
                raise BoundaryDenied("IAM trust principal format invalid")
            principals.extend((group, v) for v in values)
    return principals


def _scan_custody_role_trusts(session, operator_id: str,
                              custody_id: str) -> int:
    """Deny cross-account IAM trusts, OIDC/SAML and unreviewed service role use."""
    iam = session.client("iam")
    marker = None
    count = 0
    while True:
        args = {"MaxItems": 100}
        if marker:
            args["Marker"] = marker
        try:
            page = iam.list_roles(**args)
        except Exception:
            raise BoundaryDenied("complete IAM role inventory unavailable") from None
        roles = page.get("Roles")
        if not isinstance(roles, list):
            raise BoundaryDenied("IAM role inventory incomplete")
        for role in roles:
            if not isinstance(role, dict):
                raise BoundaryDenied("IAM role inventory invalid")
            count += 1
            arn = role.get("Arn", "")
            if (not isinstance(arn, str) or
                    not arn.startswith(f"arn:aws:iam::{custody_id}:role/")):
                raise BoundaryDenied("unexpected IAM role owner")
            path = role.get("Path", "/")
            if not isinstance(path, str):
                raise BoundaryDenied("IAM role path invalid")
            for group, principal in _trust_principals(
                role.get("AssumeRolePolicyDocument")
            ):
                if principal == "*" or operator_id in principal:
                    raise BoundaryDenied("operator may assume custody IAM role")
                if group == "Federated":
                    # Includes GitHub Actions OIDC and externally operated SAML.
                    raise BoundaryDenied("federated custody trust requires independent audit")
                if group == "Service":
                    # AWS-managed service-linked roles are not an operator
                    # OIDC channel; their use still needs human IAM review.
                    if (not path.startswith("/aws-service-role/") or
                            not principal.endswith(".amazonaws.com")):
                        raise BoundaryDenied("non-service-linked service trust requires audit")
                elif group == "AWS":
                    if principal != f"arn:aws:iam::{custody_id}:root" and (
                        not principal.startswith(
                            f"arn:aws:iam::{custody_id}:role/")
                    ):
                        raise BoundaryDenied("cross-account trust is unreviewed")
                else:
                    raise BoundaryDenied("unknown trust principal category")
        if not page.get("IsTruncated", False):
            break
        next_marker = page.get("Marker")
        if not isinstance(next_marker, str) or next_marker == marker:
            raise BoundaryDenied("IAM pagination incomplete")
        marker = next_marker
        if count > 10000:
            raise BoundaryDenied("IAM role inventory limit exceeded")
    return count


def inspect(*, operator_profile: str, custody_profile: str, check: bool = False,
            session_factory=None) -> dict:
    if not operator_profile or not custody_profile or (
        operator_profile == custody_profile
    ):
        raise BoundaryDenied("two separate audit identities required")
    if not check:
        return {
            "mode": "dry-run", "aws_calls": 0,
            "static_governance_screen_passed": False,
            "independent_custody_verified": False, "status": "BLOCKED",
        }
    if session_factory is None:
        import boto3
        session_factory = boto3.Session
    workload = session_factory(
        profile_name=operator_profile, region_name=_REGION)
    custody = session_factory(
        profile_name=custody_profile, region_name=_REGION)
    try:
        operator_id, custody_id = _account(workload), _account(custody)
        if operator_id == custody_id:
            raise BoundaryDenied("custodian and workload accounts match")
        operator_org, operator_manager = _organization(workload)
        custody_org, custody_manager = _organization(custody)
        if operator_org == custody_org or custody_manager == operator_id:
            raise BoundaryDenied("custody controlled by workload Organizations")
        roles_scanned = _scan_custody_role_trusts(custody, operator_id, custody_id)
    except BoundaryDenied:
        raise
    except Exception:
        raise BoundaryDenied("read-only AWS governance evidence unavailable") from None
    # Explicitly do not assert independence: root, IAM Identity Center, delegated
    # billing/Organizations management and CloudFormation execution roles still
    # require independent institutionally signed evidence.
    return {
        "region": _REGION,
        "workload_account": operator_id,
        "custody_account": custody_id,
        "separate_organizations": True,
        "custody_management_is_not_workload": True,
        "custody_iam_roles_scanned": roles_scanned,
        "operator_management_is_workload": operator_manager == operator_id,
        "static_governance_screen_passed": True,
        "root_sso_billing_cloudformation_external_audit": "BLOCKED",
        "independent_custody_verified": False,
        "status": "BLOCKED",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator-profile", required=True)
    parser.add_argument("--custody-profile", required=True)
    parser.add_argument("--check", action="store_true",
                        help="Explicit opt-in: read-only live AWS queries")
    parser.add_argument("--output", help="Create redacted report, mode 0600")
    args = parser.parse_args(argv)
    try:
        result = inspect(
            operator_profile=args.operator_profile,
            custody_profile=args.custody_profile, check=args.check)
    except BoundaryDenied as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc),
                          "independent_custody_verified": False}))
        return 2
    if args.output:
        path = Path(args.output)
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(result, file, sort_keys=True, indent=2)
            file.write("\n")
    print(json.dumps(result, sort_keys=True))
    # Structural check can succeed, but public release can never call it DONE.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
