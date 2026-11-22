"""Launch one ECS Nitro pilot task and verify its attested synthetic result.

The task can only work on the already-queued fictional fixture.
Run after image, policy PCR17 and CONFIDENTIAL_SANDBOX task are registered.
Without --apply this is a no-op plan. It NEVER submits an external form.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# This operator CLI is also invoked as "python scripts/confidential_pilot_run.py".
# Python does not put the repository root on sys.path in that invocation.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from confidential.pilot_preflight import validate_preflight

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


_PCR17_LINE = re.compile(
    r'"kms:RecipientAttestation:PCR17"\s*:\s*"([0-9a-fA-F]{96})"'
)


def _pcr17_from_generator_output(text: str) -> str:
    match = _PCR17_LINE.search(text)
    if match is None or match.group(1).lower() == "0" * 96:
        raise RuntimeError("could not verify nonzero PCR17 from AWS generator")
    return match.group(1).lower()


def _verified_pcr17(profile: str, task_arn: str,
                    attestation_dir: str | None = None) -> str:
    """Use the official AWS policy generator, never guess PCR17.

    The generator (0.1.x) only supports --check on a local file, so the
    registered task definition is fetched first. When the operator machine
    cannot reach the image registry, ``attestation_dir`` may point at the
    output of the signature-verified generator run in the build pipeline
    (attestation-policy.b64 + pcrs.txt); the registered task definition must
    then carry exactly that policy envelope, which is what PCR17 measures.
    """
    described = aws(
        profile, ["ecs", "describe-task-definition", "--task-definition", task_arn]
    )
    registered = (
        described.get("taskDefinition", {})
        .get("trustedExecutionConfiguration", {})
        .get("attestationPolicy")
    )
    if not isinstance(registered, str) or not registered:
        raise RuntimeError("registered task definition has no attestation policy")
    if attestation_dir is not None:
        try:
            envelope = (Path(attestation_dir) / "attestation-policy.b64").read_text("ascii").strip()
            pcrs = (Path(attestation_dir) / "pcrs.txt").read_text("utf-8")
        except (OSError, UnicodeError) as exc:
            raise RuntimeError("official ECS attestation policy verification failed") from exc
        if not envelope or envelope != registered.strip():
            raise RuntimeError("registered attestation policy differs from generator output")
        return _pcr17_from_generator_output(pcrs)
    env = dict(os.environ, AWS_PROFILE=profile, AWS_DEFAULT_REGION=_REGION)
    with tempfile.TemporaryDirectory() as tmp:
        local = Path(tmp) / "registered-taskdef.json"
        local.write_text(json.dumps(described), "utf-8")
        for args in (
            ["ecs-nitro-sandbox-genpolicy", "--check", "--task-definition", str(local)],
            ["ecs-nitro-sandbox-genpolicy", "--task-definition", str(local),
             "--output", "pcrs"],
        ):
            try:
                result = subprocess.run(
                    args, env=env, capture_output=True, text=True,
                    check=True, timeout=180,
                )
            except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                raise RuntimeError("official ECS attestation policy verification failed") from exc
            if args[-1] == "pcrs":
                return _pcr17_from_generator_output(result.stdout)
    raise RuntimeError("attestation policy verification unavailable")


def run_pilot(*, profile: str, account: str, tenant: str, subnet: str,
              job_id: str, apply: bool = False,
              vpc: str | None = None, route_table: str | None = None,
              guest_sg: str | None = None, endpoint_sg: str | None = None,
              s3_prefix: str | None = None,
              dynamodb_prefix: str | None = None,
              shared_compute: bool = False,
              external_custody_key_arn: str | None = None,
              custody_profile: str | None = None,
              custody_release_file: str | None = None,
              custodian_public_key_file: str | None = None,
              custodian_public_key_sha256: str | None = None,
              attestation_dir: str | None = None) -> bool:
    if (not _ACCOUNT.fullmatch(account) or not _TENANT.fullmatch(tenant)
            or not _SUBNET.fullmatch(subnet) or not _JOB.fullmatch(job_id)):
        raise ValueError("invalid pilot configuration")
    external_arguments = (
        external_custody_key_arn, custody_profile, custody_release_file,
        custodian_public_key_file, custodian_public_key_sha256,
    )
    using_external_key = any(v is not None for v in external_arguments)
    if using_external_key and (
        not shared_compute or not all(
            isinstance(v, str) and bool(v) for v in external_arguments
        ) or custody_profile == profile
    ):
        raise RuntimeError("external custody requires shared compute and an independent signed release")
    if not apply:
        print("DRY RUN: one synthetic Nitro task would be launched; no resources changed.")
        return False
    if not all(isinstance(v, str) and v for v in (
        vpc, route_table, guest_sg, endpoint_sg,
        s3_prefix, dynamodb_prefix,
    )):
        raise RuntimeError("private network proof required before AWS task launch")
    # No broad base-stack SG may be used for the real test. Independently
    # inspect the VPC/subnet/route table and restrictive endpoints first.
    if type(shared_compute) is not bool:
        raise RuntimeError("invalid shared compute selector")
    if shared_compute:
        # Live read-only verification proves the single, tenant-neutral VPC
        # stack, AWS-owned gateway prefixes and required PrivateLink services.
        from scripts.verify_confidential_shared_fabric import verify as verify_shared
        verify_shared(profile=profile, account=account, check=True)
        fabric = outputs(profile, "notarai-confidential-shared-fabric")
        if (fabric.get("SharedVpcId") != vpc or
                fabric.get("SharedPrivateSubnetId") != subnet or
                fabric.get("SharedRouteTableId") != route_table or
                fabric.get("SharedRuntimeSecurityGroupId") != guest_sg or
                fabric.get("SharedEndpointSecurityGroupId") != endpoint_sg):
            raise RuntimeError("shared endpoint fabric does not match submitted network")
    else:
        from scripts.verify_confidential_private_network import verify
        verify(
            account=account, profile=profile, vpc=vpc, subnet=subnet,
            route_table=route_table, guest_sg=guest_sg,
            endpoint_sg=endpoint_sg, s3_prefix=s3_prefix,
            dynamodb_prefix=dynamodb_prefix, check=True,
        )
    if aws(profile, ["sts", "get-caller-identity"]).get("Account") != account:
        raise RuntimeError("AWS account mismatch")
    suffix = f"notarai-confidential-{tenant}"
    compute = "notarai-confidential-shared" if shared_compute else suffix
    base = outputs(
        profile,
        "notarai-confidential-shared-capacity" if shared_compute
        else "notarai-confidential-capacity-base",
    )
    stack = outputs(
        profile, f"notarai-confidential-task-{tenant}"
        if shared_compute else "notarai-confidential-task",
    )
    stage = outputs(
        profile, f"notarai-confidential-staging-{tenant}"
        if shared_compute else "notarai-confidential-staging",
    )
    expected_key = "SharedClusterName" if shared_compute else "ClusterName"
    if base.get(expected_key) != compute:
        raise RuntimeError("unexpected ECS cluster")
    task_def = stack.get("TaskDefinitionArn", "")
    if not task_def.startswith(
        f"arn:aws:ecs:{_REGION}:{account}:task-definition/{suffix}:"
    ):
        raise RuntimeError("task definition not validated")
    # Independent read-only checks run BEFORE any chargeable ECS task is launched.
    from confidential.pilot_preflight import PilotPreflightRejected
    if using_external_key:
        # The external key is NOT fetched from an operator-controlled stack.
        kms_arn = external_custody_key_arn
    else:
        key_stacks = outputs(
            profile, f"notarai-confidential-demo-kms-{tenant}"
            if shared_compute else "notarai-confidential-demo-kms",
        )
        kms_arn = key_stacks.get("KeyArn", "")
    guest_pcr17 = _verified_pcr17(profile, task_def, attestation_dir)
    task_response = aws(
        profile, ["ecs", "describe-task-definition", "--task-definition", task_def]
    )
    capacity_response = aws(
        profile, ["ecs", "describe-capacity-providers", "--capacity-providers", compute]
    )
    try:
        custody_approval = None
        if using_external_key:
            # This is a live cross-account KMS/ECS check plus an ECDSA
            # signature verified against the independent custodian's
            # out-of-band pinned public key. NO KMS decrypt occurs here.
            from scripts.verify_confidential_release import check_release
            with open(custody_release_file, encoding="utf-8") as file:
                receipt = json.load(file)
            trusted_public_key = Path(custodian_public_key_file).read_bytes()
            custody_approval = check_release(
                operator_profile=profile, custody_profile=custody_profile,
                tenant=tenant, task_definition_arn=task_def,
                kms_key_arn=kms_arn, pcr17=guest_pcr17,
                image_sha256=(
                    task_response["taskDefinition"]["containerDefinitions"][0][
                        "image"
                    ].rsplit("@sha256:", 1)[-1]
                ), receipt=receipt, trusted_public_key_pem=trusted_public_key,
                trusted_public_key_sha256=custodian_public_key_sha256,
                check=True,
            )
            key_policy = None
        else:
            policy_response = aws(
                profile, ["kms", "get-key-policy", "--key-id", kms_arn,
                          "--policy-name", "default"]
            )
            key_policy = json.loads(policy_response["Policy"])
        validate_preflight(
            task_response, capacity_response, key_policy,
            account=account, tenant=tenant, task_arn=task_def,
            kms_key_arn=kms_arn, bucket=stage["BucketName"],
            queue_url=stage["QueueUrl"], expected_pcr17=guest_pcr17,
            shared_pool=shared_compute, custody_approval=custody_approval,
        )
    except Exception:
        # No AWS/identity/receipt content in error text. No RunTask on failure.
        raise RuntimeError("confidential pilot preflight rejected launch") from None

    sg = guest_sg
    if not shared_compute and sg == base.get("InstanceSecurityGroupId"):
        raise RuntimeError("broad bootstrap security group cannot launch Nitro pilot")
    actual_groups = (
        capacity_response.get("capacityProviders", [{}])[0]
        .get("managedInstancesProvider", {})
        .get("instanceLaunchTemplate", {})
        .get("networkConfiguration", {})
        .get("securityGroups")
    )
    if actual_groups != [sg]:
        raise RuntimeError("capacity provider uses an unverified or broad SG")
    networking = {"awsvpcConfiguration": {
        "subnets": [subnet], "securityGroups": [sg],
        "assignPublicIp": "DISABLED",
    }}
    tasks = aws(profile, [
        "ecs", "run-task", "--cluster", compute,
        "--task-definition", task_def,
        "--capacity-provider-strategy", f"capacityProvider={compute},weight=1",
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
        ["aws", "ecs", "wait", "tasks-stopped", "--cluster", compute, "--tasks", arn,
         "--profile", profile, "--region", _REGION, "--no-cli-pager"],
        check=True, capture_output=True, text=True, timeout=900,
    )
    report = aws(profile, [
        "ecs", "describe-tasks", "--cluster", compute, "--tasks", arn
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
    p.add_argument("--vpc")
    p.add_argument("--route-table")
    p.add_argument("--guest-sg")
    p.add_argument("--endpoint-sg")
    p.add_argument("--s3-prefix")
    p.add_argument("--dynamodb-prefix")
    p.add_argument("--shared-compute", action="store_true",
                   help="Explicitly use tenant-neutral regional ECS shared fabric")
    p.add_argument("--external-custody-key-arn")
    p.add_argument("--custody-profile",
                   help="Independent KMS account READ-ONLY profile")
    p.add_argument("--custody-release-file",
                   help="Externally signed approval for this exact Nitro release")
    p.add_argument("--custodian-public-key-file",
                   help="Public ECDSA key delivered independently of NotarAI")
    p.add_argument("--custodian-public-key-sha256",
                   help="Pin obtained out-of-band from independent custodian")
    p.add_argument("--attestation-dir",
                   help="output of the signature-verified generator run in the build pipeline")
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()
    run_pilot(
        profile=args.profile, account=args.account, tenant=args.tenant,
        subnet=args.subnet, job_id=args.job_id, apply=args.apply,
        vpc=args.vpc, route_table=args.route_table,
        guest_sg=args.guest_sg, endpoint_sg=args.endpoint_sg,
        s3_prefix=args.s3_prefix, dynamodb_prefix=args.dynamodb_prefix,
        shared_compute=args.shared_compute,
        external_custody_key_arn=args.external_custody_key_arn,
        custody_profile=args.custody_profile,
        custody_release_file=args.custody_release_file,
        custodian_public_key_file=args.custodian_public_key_file,
        custodian_public_key_sha256=args.custodian_public_key_sha256,
        attestation_dir=args.attestation_dir,
    )


if __name__ == "__main__":
    main()
