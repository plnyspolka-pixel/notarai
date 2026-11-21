"""Idempotent-ish AWS pilot bootstrap; cannot touch existing NotarAI production.

Run with explicit AWS profile, expected account, VPC and 1-3 subnet IDs.
Default: READ-ONLY PLAN (calls STS and CloudFormation ValidateTemplate).
--apply: Creates ONLY uniquely named pilot stacks and a dedicated capacity
provider, but does not schedule tasks or release plaintext keys.

Deprecated --apply path: pilot capacity must use a private-only SG from\ninfra/notarai-confidential-private-egress.yaml. This script intentionally\nrefuses provisioning until it is refactored to accept independently verified\nprivate network outputs. Use docs/claude-aws-confidential-handoff.md.\n\nRequires AWS CLI v2 whose ECS model supports nitroEnclavesEnabled.
Usage:
 python scripts/confidential_pilot_bootstrap.py --account 123456789012 \
   --profile notarai-admin --vpc vpc-0123456789abcdef0 \
   --subnet subnet-0123456789abcdef0 --instance-sg SKIP --tenant pilot01
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.render_confidential_capacity import render_capacity_provider

REGION = "eu-central-1"
BASE = Path(__file__).resolve().parents[1]
ACCOUNT_PATTERN = re.compile(r"\d{12}")
ID_PATTERN = re.compile(r"vpc-(?:[0-9a-f]{8}|[0-9a-f]{17})")
TENANT_PATTERN = re.compile(r"[a-z0-9]{1,12}")


def cli(args: list[str], profile: str, *, capture: bool = True) -> str:
    full = ["aws", *args, "--profile", profile, "--region", REGION, "--no-cli-pager"]
    result = subprocess.run(
        full, check=True, capture_output=capture, text=True, timeout=3600
    )
    return result.stdout.strip() if capture else ""


def stack_outputs(name: str, profile: str) -> dict[str, str]:
    response = json.loads(cli(
        ["cloudformation", "describe-stacks", "--stack-name", name, "--output", "json"],
        profile
    ))
    stacks = response.get("Stacks", [])
    if len(stacks) != 1 or not stacks[0].get("StackStatus", "").endswith("_COMPLETE"):
        raise RuntimeError("pilot CloudFormation stack is not complete")
    return {o["OutputKey"]: o["OutputValue"] for o in stacks[0].get("Outputs", [])}


def bootstrap(*, profile: str, account: str, tenant: str, vpc: str,
              subnets: list[str], apply: bool = False) -> None:
    if not ACCOUNT_PATTERN.fullmatch(account) or not TENANT_PATTERN.fullmatch(tenant):
        raise ValueError("invalid expected AWS account or fictional tenant")
    if not ID_PATTERN.fullmatch(vpc):
        raise ValueError("invalid VPC ID")
    # Validate user-provided subnets and test SG with same restrictions as the
    # capacity provider renderer, before any AWS writes.
    sample_sg = "sg-0123456789abcdef0"
    render_capacity_provider(
        tenant=tenant, account=account, subnets=subnets, instance_sg=sample_sg
    )
    actual = cli(["sts", "get-caller-identity", "--query", "Account", "--output", "text"], profile)
    if actual != account:
        raise RuntimeError("AWS account mismatch; refusing all operations")
    templates = {
        "notarai-confidential-staging": "notarai-confidential-staging.yaml",
        "notarai-confidential-ecr": "notarai-confidential-ecr.yaml",
        "notarai-confidential-demo-kms": "notarai-confidential-demo-kms.yaml",
        "notarai-confidential-capacity-base": "notarai-confidential-capacity-base.yaml",
    }
    for name, template in templates.items():
        file = BASE / "infra" / template
        cli(["cloudformation", "validate-template",
             "--template-body", f"file://{file}", "--output", "json"], profile)
        print(f"VALIDATED: {name}")

    if not apply:
        print("DRY RUN: all pilot templates validated in AWS; no resources created.")
        print("Provision via docs/claude-aws-confidential-handoff.md; broad SG bootstrap is disabled.")
        return

    # Historical bootstrap bound the ECS capacity provider to a test SG with
    # outbound HTTPS 0.0.0.0/0. Do not provision that path even on fictional
    # data: the new isolated pilot MUST use a validated private-only SG.
    raise RuntimeError(
        "insecure broad-egress bootstrap --apply disabled; use private-only AWS runbook"
    )

    for name, filename in templates.items():
        argv = [
            "cloudformation", "deploy", "--stack-name", name,
            "--template-file", str(BASE / "infra" / filename),
            "--parameter-overrides", f"TenantId={tenant}",
            "--no-fail-on-empty-changeset", "--tags", "project=notarai",
            "scope=confidential-pilot",
        ]
        if name.endswith("capacity-base"):
            argv.extend(["--parameter-overrides", f"TenantId={tenant}", f"VpcId={vpc}"])
            # Remove preceding parameter override, supplied in second occurrence.
            ix = argv.index("--parameter-overrides")
            del argv[ix:ix+2]
            argv.extend(["--capabilities", "CAPABILITY_NAMED_IAM"])
        cli(argv, profile)
        print(f"PROVISIONED: {name}")

    suffix = f"notarai-confidential-{tenant}"
    stacks = {
        name: stack_outputs(name, profile)
        for name in templates
    }
    base = stacks["notarai-confidential-capacity-base"]
    if base.get("ClusterName") != suffix:
        raise RuntimeError("pilot cluster mismatch")
    if base.get("InfrastructureRoleArn") != f"arn:aws:iam::{account}:role/notarai-confidential-infra-{tenant}":
        raise RuntimeError("pilot infrastructure role mismatch")
    sg = base["InstanceSecurityGroupId"]
    provider = render_capacity_provider(
        tenant=tenant, account=account, subnets=subnets, instance_sg=sg
    )
    # Validate derived role names and refuse drift.
    if provider["managedInstancesProvider"]["instanceLaunchTemplate"]["ec2InstanceProfileArn"] != base["InstanceProfileArn"]:
        raise RuntimeError("instance profile ARN mismatch")
    info = json.loads(cli([
        "ecs", "describe-capacity-providers", "--capacity-providers", suffix,
        "--output", "json",
    ], profile))
    providers = info.get("capacityProviders", [])
    if providers:
        current = providers[0]
        if current.get("cluster") not in (suffix, f"arn:aws:ecs:{REGION}:{account}:cluster/{suffix}"):
            raise RuntimeError("capacity provider belongs to unexpected cluster")
        launch = current.get("managedInstancesProvider", {}).get("instanceLaunchTemplate", {})
        if launch.get("nitroEnclavesEnabled") is not True or launch.get("networkConfiguration", {}).get("securityGroups") != [sg]:
            raise RuntimeError("existing capacity provider is not the approved pilot configuration")
        print("EXISTS: approved Nitro provider")
    else:
        with tempfile.TemporaryDirectory(prefix="notarai-nitro-") as d:
            path = Path(d) / "provider.json"
            path.write_text(json.dumps(provider), encoding="utf-8")
            cli(["ecs", "create-capacity-provider", "--cli-input-json",
                 f"file://{path}", "--output", "json"], profile)
        print("CREATED: Nitro-enabled capacity provider")

    cli(["ecs", "put-cluster-capacity-providers",
         "--cluster", suffix, "--capacity-providers", suffix,
         "--default-capacity-provider-strategy", f"capacityProvider={suffix},weight=1",
         "--output", "json"], profile)
    print("BOOTSTRAPPED: isolated pilot cluster with Nitro capacity provider.")
    print("No task has been started, and no confidential data was decrypted.")
    print("Staging S3 bucket:", stacks["notarai-confidential-staging"]["BucketName"])
    print("ECR repo:", stacks["notarai-confidential-ecr"]["RepositoryUri"])
    print("KMS key ARN:", stacks["notarai-confidential-demo-kms"]["KeyArn"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--vpc", required=True)
    parser.add_argument("--subnet", action="append", required=True)
    parser.add_argument("--tenant", default="pilot01")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    bootstrap(
        profile=args.profile, account=args.account, tenant=args.tenant,
        vpc=args.vpc, subnets=args.subnet, apply=args.apply
    )


if __name__ == "__main__":
    main()
