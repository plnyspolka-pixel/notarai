#!/usr/bin/env python3
"""SEC-09 read-only AWS inspection and *IAM simulations*, not live attack probes.

No IAM/S3/SQS/DynamoDB/ECS mutation is performed. IAM simulation cannot
prove runtime KMS attestation, S3 resource policies, session policies or
real AccessDenied responses. K2/K3/K4/K5/K6 remain BLOCKED until separately
authorized live negative and positive tests with two isolated pilot roles.

Usage:
  python scripts/verify_confidential_tenant_isolation.py
  python scripts/verify_confidential_tenant_isolation.py --check \
    --profile pilot-auditor --account 111122223333
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from confidential.tenant_isolation import TenantBoundary, validate_pair

_REGION = "eu-central-1"
_SHARED = "notarai-confidential-shared"


def _manifest(ecs, *, account: str, tenant: str) -> TenantBoundary:
    family = "notarai-confidential-" + tenant
    definition = ecs.describe_task_definition(taskDefinition=family)["taskDefinition"]
    containers = definition.get("containerDefinitions", [])
    if len(containers) != 1:
        raise ValueError("unexpected guest containers")
    guest = containers[0]
    environment = guest.get("environment", [])
    if not isinstance(environment, list) or len(environment) != 9:
        raise ValueError("guest environment has changed")
    values = {}
    for item in environment:
        if not isinstance(item, dict) or item.get("name") in values:
            raise ValueError("unexpected guest environment")
        values[item["name"]] = item.get("value")
    if values.get("NOTARAI_CONFIDENTIAL_REQUIRED") != "1" or (
        values.get("NOTARAI_CONFIDENTIAL_TENANT") != tenant
        or values.get("AWS_REGION") != _REGION
    ):
        raise ValueError("guest tenant is not pinned")
    image = guest.get("image", "")
    if not isinstance(image, str) or "@sha256:" not in image:
        raise ValueError("immutable guest image required")
    digest = image.rsplit("@sha256:", 1)[-1]
    if not image.startswith(
        f"{account}.dkr.ecr.{_REGION}.amazonaws.com/{_SHARED}@sha256:"
    ):
        raise ValueError("unapproved shared image registry")
    trust = definition.get("trustedExecutionConfiguration") or {}
    if (definition.get("status") != "ACTIVE" or
            definition.get("family") != family or
            definition.get("networkMode") != "awsvpc" or
            definition.get("requiresCompatibilities") != ["MANAGED_INSTANCES"] or
            definition.get("volumes") or
            trust.get("isolationMode") != "CONFIDENTIAL_SANDBOX" or
            not trust.get("attestationPolicy")):
        raise ValueError("unattested guest task definition")
    if (guest.get("name") != "confidential-browser" or
            guest.get("user") != "10001:10001" or
            guest.get("readonlyRootFilesystem") is not True or
            guest.get("privileged") is True or
            any(guest.get(field) for field in (
                "secrets", "environmentFiles", "mountPoints", "volumesFrom",
                "portMappings", "logConfiguration", "entryPoint", "command",
            ))):
        raise ValueError("unapproved confidential guest extensions")
    return TenantBoundary(
        tenant=tenant, account=account, session_tenant=tenant,
        cluster=_SHARED, capacity_provider=_SHARED,
        task_definition_arn=definition["taskDefinitionArn"],
        task_role_arn=definition["taskRoleArn"],
        execution_role_arn=definition["executionRoleArn"],
        image_digest=digest,
        kms_key_arn=values["NOTARAI_CONFIDENTIAL_KMS_KEY_ARN"],
        bucket=values["NOTARAI_CONFIDENTIAL_BUCKET"],
        queue_url=values["NOTARAI_CONFIDENTIAL_QUEUE_URL"],
        jobs_table=f"notarai-confidential-jobs-{tenant}",
        dispatch_table=f"notarai-confidential-dispatch-{tenant}",
        s3_namespace=f"kancelarie/{tenant}/confidential/",
    )


def _probe_spec(source: TenantBoundary, target: TenantBoundary) -> list[tuple]:
    # Hypothetical (nonexistent) object means IAM simulation must never
    # retrieve customer documents. ARN-only simulator requests are read-only.
    destination_account = target.account
    return [
        (source.task_role_arn, "kms:Decrypt", target.kms_key_arn, {}),
        (source.task_role_arn, "s3:GetObjectVersion",
         f"arn:aws:s3:::{target.bucket}/{target.s3_namespace}synthetic-only.json",
         {}),
        (source.task_role_arn, "sqs:ReceiveMessage",
         f"arn:aws:sqs:{_REGION}:{destination_account}:notarai-confidential-{target.tenant}.fifo", {}),
        (source.task_role_arn, "dynamodb:GetItem",
         f"arn:aws:dynamodb:{_REGION}:{destination_account}:table/{target.jobs_table}", {}),
        (source.task_role_arn, "dynamodb:UpdateItem",
         f"arn:aws:dynamodb:{_REGION}:{destination_account}:table/{target.jobs_table}", {}),
        (f"arn:aws:iam::{source.account}:role/notarai-confidential-dispatch-{source.tenant}",
         "ecs:RunTask", target.task_definition_arn,
         {"ContextKeyName": "ecs:cluster", "ContextKeyType": "string",
          "ContextKeyValues": [f"arn:aws:ecs:{_REGION}:{source.account}:cluster/{_SHARED}"]}),
        (f"arn:aws:iam::{source.account}:role/notarai-confidential-dispatch-{source.tenant}",
         "iam:PassRole", target.task_role_arn,
         {"ContextKeyName": "iam:PassedToService", "ContextKeyType": "string",
          "ContextKeyValues": ["ecs-tasks.amazonaws.com"]}),
    ]


def inspect(*, profile: str, account: str, session_factory=None) -> dict:
    if not re.fullmatch(r"[0-9]{12}", account):
        raise ValueError("explicit 12-digit account required")
    if session_factory is None:
        import boto3
        session_factory = boto3.Session
    session = session_factory(profile_name=profile, region_name=_REGION)
    if session.client("sts").get_caller_identity().get("Account") != account:
        raise ValueError("AWS account does not match the explicitly allowed account")
    ecs = session.client("ecs")
    one = _manifest(ecs, account=account, tenant="pilot01")
    two = _manifest(ecs, account=account, tenant="pilot02")
    validate_pair(one, two)
    provider = ecs.describe_capacity_providers(capacityProviders=[_SHARED]).get(
        "capacityProviders", []
    )
    if (len(provider) != 1 or provider[0].get("status") != "ACTIVE" or
            (provider[0].get("managedInstancesProvider") or {}).get(
                "instanceLaunchTemplate", {}).get("nitroEnclavesEnabled") is not True):
        raise ValueError("shared Nitro capacity provider not verified")
    config = {
        "tenants": sorted([one.tenant, two.tenant]),
        "account": account,
        "cluster": _SHARED,
        "image_digest": one.image_digest,
        "resource_hashes": {
            t.tenant: {
                name: hashlib.sha256(getattr(t, name).encode()).hexdigest()
                for name in ("task_role_arn", "execution_role_arn", "kms_key_arn",
                             "bucket", "queue_url", "jobs_table", "dispatch_table")
            } for t in (one, two)
        },
    }
    digest = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    iam = session.client("iam")
    simulations = []
    for source, destination in ((one, two), (two, one)):
        for principal, action, resource, context in _probe_spec(source, destination):
            args = {"PolicySourceArn": principal, "ActionNames": [action],
                    "ResourceArns": [resource]}
            if context:
                args["ContextEntries"] = [context]
            try:
                response = iam.simulate_principal_policy(**args)
                results = response.get("EvaluationResults", [])
                decision = results[0].get("EvalDecision") if len(results) == 1 else None
            except Exception:
                decision = None  # insufficient IAM simulation rights = BLOCKED
            simulations.append({
                "direction": source.tenant + " -> " + destination.tenant,
                "action": action,
                "simulator_decision": decision or "UNAVAILABLE",
                "actual_aws_call_performed": False,
            })
    # An IAM simulator denial is NOT a real AccessDenied. A simulator allow,
    # however, is a serious warning and fails the static inspection.
    unexpected_allow = any(
        r["simulator_decision"].lower() == "allowed" for r in simulations
    )
    report = {
        "workstream": "SEC-09",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "read-only-aws-and-iam-simulation",
        "configuration_sha256": digest,
        "pilot_count": 2,
        "actual_negative_probes": 0,
        "simulated_probes": len(simulations),
        "simulations": simulations,
        "criteria": {
            "K1": "BLOCKED",  # unverified independent sessions / VPC effective policy
            "K2": "FAIL" if unexpected_allow else "BLOCKED",
            "K3": "BLOCKED", "K4": "BLOCKED", "K5": "BLOCKED",
            "K6": "BLOCKED",
        },
        "completed": False,
        "scope": "synthetic pilot01/pilot02; no submit; production OFF",
        "warning": "Simulator results are not live KMS/S3/SQS/DDB/ECS denials.",
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="read-only AWS inspection + IAM simulations; never writes AWS")
    parser.add_argument("--profile", default=None)
    parser.add_argument("--account", default=None)
    parser.add_argument("--report", type=Path, default=None,
                        help="optional local sanitized JSON, never auto-upload")
    args = parser.parse_args()
    if not args.check:
        print("DRY RUN: zero AWS calls. --check requires --profile and --account.")
        return 0
    if not args.profile or not args.account:
        parser.error("--check requires --profile and --account")
    try:
        report = inspect(profile=args.profile, account=args.account)
    except Exception:
        print("BLOCKED: read-only AWS inspection failed; no credentials or identifiers displayed.")
        return 2
    payload = json.dumps(report, indent=2, sort_keys=True)
    if args.report is not None:
        args.report.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 2  # deliberately not green: no actual negative calls or live E2E


if __name__ == "__main__":
    raise SystemExit(main())
