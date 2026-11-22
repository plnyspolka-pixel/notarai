"""Read-only configuration audit for existing AWS ECS Nitro Sandbox + Bedrock.

Defaults to NO AWS calls and NO_GO. Does not decrypt, dispatch, log prompts,
mutate IAM/KMS, create ECS tasks, or claim real hardware attestation.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from confidential.three_zero_gate import (
    ThreeZeroGateDenied, validate_bedrock_logging,
    validate_confidential_task_definition, validate_task_runtime,
)

ACCOUNT = re.compile(r"^[0-9]{12}$")
TASK = re.compile(r"^[a-zA-Z0-9_./:-]{1,250}$")
REGION = "eu-central-1"


def audit_offline(task_definition=None, bedrock_logging=None, task_runtime=None):
    result = {
        "schema": "notarai.aws-three-zero-audit.v1",
        "aws_region": REGION,
        "read_only": True,
        "decision": "NO_GO",
        "checks": {},
        "requires_live_evidence": [
            "aws_nitro_hardware_attestation_and_negative_release",
            "customer_controlled_owner_key_and_signed_client",
            "kms_iam_operator_mutation_boundary",
            "bedrock_model_region_retention_and_supplier_contract",
            "tenant_isolation_and_egress",
            "end_to_end_integration_and_external_review",
        ],
    }
    candidates = (
        ("ecs_task_definition", task_definition, validate_confidential_task_definition),
        ("bedrock_content_logging", bedrock_logging, validate_bedrock_logging),
        ("ecs_task_runtime", task_runtime, validate_task_runtime),
    )
    for name, value, checker in candidates:
        if value is None:
            result["checks"][name] = {"status": "NOT_CHECKED"}
            continue
        try:
            data = checker(value)
            result["checks"][name] = {"status": "PASS_STATIC", **data}
        except (ThreeZeroGateDenied, KeyError, ValueError, TypeError):
            result["checks"][name] = {"status": "FAIL"}
    # Intentionally NO code path promotes to GO. Evidence must be generated
    # independently by the actual Nitro/customer/Bedrock integration tests.
    return result


def audit_live_readonly(*, profile: str, account: str, task_definition: str,
                        cluster: str | None = None, task_arn: str | None = None):
    """Fetch narrowly selected AWS metadata only, never underlying documents."""
    if not ACCOUNT.fullmatch(account) or not TASK.fullmatch(task_definition):
        raise ValueError("invalid audit scope")
    if bool(cluster) != bool(task_arn):
        raise ValueError("cluster and task arn must be supplied together")
    if cluster and (not TASK.fullmatch(cluster) or not TASK.fullmatch(task_arn)):
        raise ValueError("invalid runtime scope")
    import boto3

    session = boto3.Session(profile_name=profile, region_name=REGION)
    observed = session.client("sts").get_caller_identity().get("Account")
    if observed != account:
        raise RuntimeError("AWS account mismatch")
    ecs = session.client("ecs")
    task = ecs.describe_task_definition(taskDefinition=task_definition)
    bedrock = session.client("bedrock")
    logging = bedrock.get_model_invocation_logging_configuration()
    runtime = None
    if task_arn:
        runtime = ecs.describe_tasks(cluster=cluster, tasks=[task_arn])
    return audit_offline(task, logging, runtime)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--task-json", type=Path)
    p.add_argument("--bedrock-json", type=Path)
    p.add_argument("--runtime-json", type=Path)
    p.add_argument("--check-aws", action="store_true",
                   help="Explicit read-only AWS STS/ECS/Bedrock calls")
    p.add_argument("--profile")
    p.add_argument("--account")
    p.add_argument("--task-definition")
    p.add_argument("--cluster")
    p.add_argument("--task-arn")
    args = p.parse_args(argv)
    try:
        if args.check_aws:
            if any((args.task_json, args.bedrock_json, args.runtime_json)):
                p.error("--check-aws is incompatible with local fixture inputs")
            if not all((args.profile, args.account, args.task_definition)):
                p.error("--check-aws requires --profile --account --task-definition")
            report = audit_live_readonly(
                profile=args.profile, account=args.account,
                task_definition=args.task_definition,
                cluster=args.cluster, task_arn=args.task_arn)
        else:
            if any((args.profile, args.account, args.task_definition, args.cluster, args.task_arn)):
                p.error("AWS settings require explicit --check-aws")
            inputs = []
            for path in (args.task_json, args.bedrock_json, args.runtime_json):
                if path is None:
                    inputs.append(None)
                else:
                    if path.stat().st_size > 1024 * 1024:
                        raise ValueError("oversized evidence fixture")
                    inputs.append(json.loads(path.read_text(encoding="utf-8")))
            report = audit_offline(*inputs)
    except (ValueError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        # Redact SDK exceptions: they can contain resource names or sensitive paths.
        print(json.dumps({"schema": "notarai.aws-three-zero-audit.v1",
                          "decision": "NO_GO", "error": type(exc).__name__}))
        return 2
    except Exception:
        print(json.dumps({"schema": "notarai.aws-three-zero-audit.v1",
                          "decision": "NO_GO", "error": "AWS_READ_FAILED"}))
        return 2
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0 if all(x["status"] == "PASS_STATIC" for x in report["checks"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
