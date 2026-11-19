"""Launch one ECS Nitro pilot task and verify its attested synthetic result.

The task can only work on the already-queued fictional fixture.
Run after image, policy PCR17 and CONFIDENTIAL_SANDBOX task are registered.
Without --apply this is a no-op plan. It NEVER submits an external form.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess

_REGION = "eu-central-1"
_ACCOUNT = re.compile(r"\d{12}")
_TENANT = re.compile(r"[a-z0-9]{1,12}")
_SUBNET = re.compile(r"subnet-(?:[0-9a-f]{8}|[0-9a-f]{17})")
_JOB = re.compile(r"[0-9a-f]{32}")


def aws(profile: str, args: list[str], timeout: int = 90) -> dict:
    result = subprocess.run(
        ["aws", *args, "--profile", profile, "--region", _REGION,
         "--output", "json", "--no-cli-pager"],
        capture_output=True, text=True, check=True, timeout=timeout
    )
    return json.loads(result.stdout) if result.stdout.strip() else {}


def outputs(profile: str, stack: str) -> dict[str, str]:
    result = aws(profile, ["cloudformation", "describe-stacks", "--stack-name", stack])
    stacks = result.get("Stacks", [])
    if len(stacks) != 1:
        raise RuntimeError("missing isolated pilot stack")
    return {x["OutputKey"]: x["OutputValue"] for x in stacks[0].get("Outputs", [])}


def run_pilot(*, profile: str, account: str, tenant: str, subnet: str,
              job_id: str, apply: bool = False) -> bool:
    if (not _ACCOUNT.fullmatch(account) or not _TENANT.fullmatch(tenant)
            or not _SUBNET.fullmatch(subnet) or not _JOB.fullmatch(job_id)):
        raise ValueError("invalid pilot configuration")
    if not apply:
        print("DRY RUN: one synthetic Nitro task would be launched; no resources changed.")
        return False
    if aws(profile, ["sts", "get-caller-identity"]).get("Account") != account:
        raise RuntimeError("AWS account mismatch")
    suffix = f"notarai-confidential-{tenant}"
    base = outputs(profile, "notarai-confidential-capacity-base")
    stack = outputs(profile, "notarai-confidential-task")
    stage = outputs(profile, "notarai-confidential-staging")
    if base.get("ClusterName") != suffix:
        raise RuntimeError("unexpected ECS cluster")
    task_def = stack.get("TaskDefinitionArn", "")
    if not task_def.startswith(
        f"arn:aws:ecs:{_REGION}:{account}:task-definition/{suffix}:"
    ):
        raise RuntimeError("task definition not validated")
    sg = base["InstanceSecurityGroupId"]
    networking = {"awsvpcConfiguration": {
        "subnets": [subnet], "securityGroups": [sg],
        "assignPublicIp": "DISABLED",
    }}
    tasks = aws(profile, [
        "ecs", "run-task", "--cluster", suffix,
        "--task-definition", task_def,
        "--capacity-provider-strategy", f"capacityProvider={suffix},weight=1",
        "--network-configuration", json.dumps(networking),
        "--count", "1",
    ])
    if tasks.get("failures") or len(tasks.get("tasks", [])) != 1:
        raise RuntimeError("ECS did not start exactly one task")
    task = tasks["tasks"][0]
    arn = task["taskArn"]
    summary = task.get("trustedExecutionSummary", {})
    if summary.get("isolationMode") != "CONFIDENTIAL_SANDBOX" or (
        summary.get("attestationPolicyStatus") != "CONFIGURED"
    ):
        raise RuntimeError("task was not launched with required confidential attestation")
    # AWS waiter requires additional time; never busy-loop indefinitely.
    subprocess.run(
        ["aws", "ecs", "wait", "tasks-stopped", "--cluster", suffix, "--tasks", arn,
         "--profile", profile, "--region", _REGION, "--no-cli-pager"],
        check=True, capture_output=True, text=True, timeout=900,
    )
    report = aws(profile, [
        "ecs", "describe-tasks", "--cluster", suffix, "--tasks", arn
    ])
    current = report["tasks"][0]
    if current.get("trustedExecutionSummary", {}).get("isolationMode") != "CONFIDENTIAL_SANDBOX":
        raise RuntimeError("attestation status was lost")
    codes = [x.get("exitCode") for x in current.get("containers", [])]
    if codes != [0]:
        raise RuntimeError("confidential guest did not complete successfully")
    import boto3
    sess = boto3.Session(profile_name=profile, region_name=_REGION)
    bucket = stage["BucketName"]
    key = f"kancelarie/{tenant}/confidential-results/{job_id}.json"
    object_response = sess.client("s3").get_object(Bucket=bucket, Key=key)
    with object_response["Body"] as stream:
        data = json.loads(stream.read(2048))
    if data != {
        "version": 1, "job_id": job_id, "status": "preview_completed",
        "fields_filled": 2, "submitted": False,
    }:
        raise RuntimeError("guest result is missing or invalid")
    print("PASS: Nitro confidential task reached success with synthetic form.")
    print("Attestation mode: CONFIDENTIAL_SANDBOX; policy: CONFIGURED")
    print("No official form was submitted.")
    return True


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--profile", required=True)
    p.add_argument("--account", required=True)
    p.add_argument("--tenant", default="pilot01")
    p.add_argument("--subnet", required=True)
    p.add_argument("--job-id", required=True)
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()
    run_pilot(
        profile=args.profile, account=args.account, tenant=args.tenant,
        subnet=args.subnet, job_id=args.job_id, apply=args.apply,
    )


if __name__ == "__main__":
    main()
