"""SEC-02: deterministic source-only IAM privilege graph for independent review.

No credentials, AWS calls, resource mutations or deployment. Inputs restricted
to checked-in infrastructure templates. Output is redacted and explicitly
NOT proof of the actual IAM/Organizations/SSO/root permissions in AWS.

Usage:
  python -m scripts.confidential_operator_iam_source_inventory --summary
  python -m scripts.confidential_operator_iam_source_inventory --output /tmp/iam.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import yaml

from scripts.confidential_operator_iam_evidence import (
    _CloudFormationLoader,
)

ROOT = Path(__file__).resolve().parents[1]
INFRA = ROOT / "infra"
SELECTED_EXTRAS = ("notarai-github.yaml", "notarai-wdrozenie-iam.yaml")
IAM_TYPES = {
    "AWS::IAM::Role", "AWS::IAM::Policy",
    "AWS::IAM::ManagedPolicy",
}
_SENSITIVE = re.compile(r"(?<!\d)\d{12}(?!\d)")
_CONTROL_GAPS = (
    "AWS root and root credential recovery for each account",
    "AWS Organizations management account and delegated administrators",
    "IAM Identity Center administrator assignments and recovery",
    "CloudFormation execution roles and actual stack RoleARN inventory",
    "live IAM role attachments, policy default versions and resource policies",
    "GitHub OIDC actual token claims, repo control, branch protection",
    "independently governed custody account and signed release approval",
    "actual six IAM/STS/ECR/KMS/Cfn/OIDC deny attempts plus CloudTrail evidence",
)


def _clean(obj):
    """Scrub fixed-length AWS account IDs; never render secret-bearing values."""
    if obj is None:
        return "UNRESOLVED"
    if isinstance(obj, str):
        return _SENSITIVE.sub("[ACCOUNT_ID]", obj)
    if isinstance(obj, (list, tuple)):
        return [_clean(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in sorted(obj.items())}
    if isinstance(obj, (int, bool)):
        return obj
    return "UNRESOLVED"


def _actions(stmt):
    if "NotAction" in stmt:
        exception = stmt["NotAction"]
        if isinstance(exception, str):
            exception = [exception]
        if not isinstance(exception, list):
            return ["NOT_ACTION_UNRESOLVED"]
        return ["ALL_EXCEPT:" + str(action) for action in exception]
    value = stmt.get("Action")
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [a if isinstance(a, str) else "UNRESOLVED"
                for a in value]
    return ["UNRESOLVED"]


def _statements(policy):
    if not isinstance(policy, dict):
        return []
    value = policy.get("Statement", [])
    if isinstance(value, dict):
        return [value]
    return value if isinstance(value, list) else []


def _policy_sources(resource):
    typ = resource.get("Type")
    properties = resource.get("Properties", {})
    if not isinstance(properties, dict):
        return []
    docs = []
    if typ in ("AWS::IAM::ManagedPolicy", "AWS::IAM::Policy"):
        docs.append(("policy_document", properties.get("PolicyDocument", {})))
    if typ == "AWS::IAM::Role":
        for p in properties.get("Policies", []) or []:
            if isinstance(p, dict):
                docs.append(("inline:" + str(p.get("PolicyName", "UNNAMED")),
                             p.get("PolicyDocument", {})))
    if typ == "AWS::KMS::Key":
        docs.append(("kms_key_policy", properties.get("KeyPolicy", {})))
    return docs


def _account_zone(path: Path):
    if path.name in (
        "notarai-confidential-external-custody-kms.yaml",
        "notarai-confidential-custody-signing.yaml",
    ):
        return "custody"
    return "workload_or_unverified"


def build_manifest(root: Path = ROOT):
    infra = root / "infra"
    candidates = set(infra.glob("notarai-confidential-*.yaml"))
    candidates.update(infra / x for x in SELECTED_EXTRAS
                      if (infra / x).is_file())
    rows, roles, referenced = [], [], []
    for path in sorted(candidates):
        document = yaml.load(path.read_text(encoding="utf-8"),
                             Loader=_CloudFormationLoader)
        if not isinstance(document, dict):
            raise ValueError("malformed infrastructure source")
        resources = document.get("Resources", {})
        if not isinstance(resources, dict):
            raise ValueError("invalid CloudFormation resources")
        rel = str(path.relative_to(root))
        account = _account_zone(path)
        for logical_id, resource in sorted(resources.items()):
            if not isinstance(resource, dict):
                raise ValueError("malformed CloudFormation resource")
            typ = resource.get("Type")
            if typ not in IAM_TYPES and typ != "AWS::KMS::Key":
                continue
            props = resource.get("Properties", {})
            if not isinstance(props, dict):
                raise ValueError("malformed resource properties")
            if typ == "AWS::IAM::Role":
                roles.append({
                    "path": rel,
                    "logical_id": logical_id,
                    "role_name": _clean(props.get("RoleName")),
                    "account": account,
                    "trust_policy": "SOURCE_ONLY_NOT_EFFECTIVE_IAM",
                    "trust_principals": _clean([
                        x.get("Principal", "UNKNOWN")
                        for x in _statements(
                            props.get("AssumeRolePolicyDocument", {}))
                        if isinstance(x, dict)
                    ]),
                    "managed_policy_arns": _clean(
                        props.get("ManagedPolicyArns", [])),
                    "permissions_boundary": _clean(
                        props.get("PermissionsBoundary")),
                })
                if props.get("ManagedPolicyArns"):
                    referenced.append({
                        "path": rel,
                        "logical_id": logical_id,
                        "reason": "AWS_MANAGED_OR_EXTERNALLY_ATTACHED_POLICY",
                    })
            if typ == "AWS::IAM::Role":
                for trust in _statements(
                        props.get("AssumeRolePolicyDocument", {})):
                    if not isinstance(trust, dict):
                        raise ValueError("malformed IAM trust statement")
                    for action in _actions(trust):
                        rows.append({
                            "path": rel,
                            "logical_id": logical_id,
                            "principal": _clean(
                                trust.get("Principal", "UNRESOLVED")),
                            "policy": "assume_role_trust",
                            "sid": _clean(trust.get("Sid", "UNNAMED")),
                            "effect": _clean(trust.get("Effect")),
                            "action": _clean(action),
                            "resource": _clean(
                                props.get("RoleName") or logical_id),
                            "account": account,
                            "condition": _clean(
                                trust.get("Condition", "NONE")),
                            "scope": "SOURCE_ONLY",
                        })
            for policy_name, policy in _policy_sources(resource):
                statements = _statements(policy)
                if not statements:
                    referenced.append({
                        "path": rel,
                        "logical_id": logical_id,
                        "reason": "POLICY_NOT_EXPANDED_OR_EMPTY",
                    })
                for n, statement in enumerate(statements):
                    if not isinstance(statement, dict):
                        raise ValueError("malformed policy statement")
                    actions = _actions(statement)
                    for action in actions:
                        rows.append({
                            "path": rel,
                            "logical_id": logical_id,
                            "principal": _clean(
                                statement.get("Principal",
                                              props.get("RoleName") or
                                              props.get("Roles") or logical_id)),
                            "policy": policy_name,
                            "sid": _clean(statement.get("Sid", "UNNAMED")),
                            "effect": _clean(statement.get("Effect")),
                            "action": _clean(action),
                            "resource": _clean(
                                statement.get("Resource", {
                                    "NotResource": statement["NotResource"]
                                } if "NotResource" in statement else
                                "UNRESOLVED")),
                            "account": account,
                            "condition": _clean(
                                statement.get("Condition", "NONE")),
                            "scope": "SOURCE_ONLY",
                        })
    rows.sort(key=lambda x: (
        x["path"], x["logical_id"], x["policy"],
        x["sid"], str(x["action"])))
    roles.sort(key=lambda x: (x["path"], x["logical_id"]))
    referenced.sort(key=lambda x: (
        x["path"], x["logical_id"], x["reason"]))
    if not rows or not roles:
        raise ValueError("missing required confidential IAM sources")
    summary = {
        "schema": "notarai.sec02.source-inventory.v1",
        "verification": "STATIC_SOURCE_ONLY_NOT_DEPLOYED",
        "aws_calls": 0,
        "templates_inspected": len(candidates),
        "roles": roles,
        "principal_action_resource_account": rows,
        "unresolved_policy_sources": referenced,
        "live_evidence_gaps": list(_CONTROL_GAPS),
        "all_real_world_criteria_pass": False,
    }
    canonical = json.dumps(summary, ensure_ascii=True, sort_keys=True,
                           separators=(",", ":"), allow_nan=False)
    summary["sha256"] = hashlib.sha256(
        canonical.encode("utf-8")).hexdigest()
    return summary


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path)
    p.add_argument("--summary", action="store_true")
    args = p.parse_args(argv)
    manifest = build_manifest()
    if args.output:
        args.output.write_text(json.dumps(
            manifest, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
            encoding="utf-8")
    if args.summary:
        print(json.dumps({
            "verification": manifest["verification"],
            "templates": manifest["templates_inspected"],
            "roles": len(manifest["roles"]),
            "statements": len(manifest["principal_action_resource_account"]),
            "unexpanded_sources": len(manifest["unresolved_policy_sources"]),
            "sha256": manifest["sha256"],
            "live_criteria_pass": False,
        }, sort_keys=True))
    elif not args.output:
        print(json.dumps(manifest, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
