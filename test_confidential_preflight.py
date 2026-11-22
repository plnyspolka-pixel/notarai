"""Offline, synthetic fail-closed tests for the Nitro control-plane preflight."""
import copy
import json
import subprocess

import pytest

from confidential.pilot_preflight import (
    PilotPreflightRejected,
    validate_preflight,
)
from scripts import confidential_pilot_run as runner


ACCOUNT = "111122223333"
TENANT = "pilot01"
NAME = "notarai-confidential-pilot01"
TASK_ARN = f"arn:aws:ecs:eu-central-1:{ACCOUNT}:task-definition/{NAME}:7"
KEY_ARN = f"arn:aws:kms:eu-central-1:{ACCOUNT}:key/12345678-abcd"
ROLE = f"arn:aws:iam::{ACCOUNT}:role/{NAME}"
BUCKET = f"ntr-cf-{TENANT}-{ACCOUNT}-eu-central-1"
QUEUE = f"https://sqs.eu-central-1.amazonaws.com/{ACCOUNT}/{NAME}.fifo"
PCR = "a" * 96
IMAGE = f"{ACCOUNT}.dkr.ecr.eu-central-1.amazonaws.com/{NAME}@sha256:" + "b" * 64


def sample():
    env = {
        "NOTARAI_CONFIDENTIAL_REQUIRED": "1",
        "NOTARAI_CONFIDENTIAL_TENANT": TENANT,
        "NOTARAI_CONFIDENTIAL_BUCKET": BUCKET,
        "NOTARAI_CONFIDENTIAL_QUEUE_URL": QUEUE,
        "NOTARAI_CONFIDENTIAL_KMS_KEY_ARN": KEY_ARN,
        "AWS_REGION": "eu-central-1",
        "HOME": "/tmp", "XDG_CACHE_HOME": "/tmp", "TMPDIR": "/tmp",
    }
    task = {"taskDefinition": {
        "taskDefinitionArn": TASK_ARN, "family": NAME, "status": "ACTIVE",
        "requiresCompatibilities": ["MANAGED_INSTANCES"], "networkMode": "awsvpc",
        "taskRoleArn": ROLE,
        "executionRoleArn": f"arn:aws:iam::{ACCOUNT}:role/notarai-confidential-execution-{TENANT}",
        "trustedExecutionConfiguration": {
            "isolationMode": "CONFIDENTIAL_SANDBOX",
            "attestationPolicy": "dGVzdC1wb2xpY3ktZW52ZWxvcGUtYnl0ZXM=",
        },
        "containerDefinitions": [{
            "name": "confidential-browser", "image": IMAGE, "user": "10001:10001",
            "readonlyRootFilesystem": True, "privileged": False,
            "environment": [{"name": k, "value": v} for k, v in env.items()],
        }],
    }}
    capacity = {"capacityProviders": [{
        "name": NAME, "status": "ACTIVE",
        "managedInstancesProvider": {"instanceLaunchTemplate": {
            "nitroEnclavesEnabled": True,
        }},
    }]}
    policy = {"Version": "2012-10-17", "Statement": [
        {"Effect": "Allow", "Principal": {"AWS": f"arn:aws:iam::{ACCOUNT}:root"},
         "Action": ["kms:Describe*", "kms:Put*", "kms:Get*"]},
        {"Effect": "Allow", "Principal": "*", "Action": ["kms:Decrypt"],
         "Condition": {
             "ArnEquals": {"aws:PrincipalArn": ROLE},
             "StringEqualsIgnoreCase": {
                 "kms:RecipientAttestation:PCR17": PCR,
                 "kms:RecipientAttestation:PCR8:ServiceName": "ecs.amazonaws.com",
             },
         }},
    ]}
    return task, capacity, policy


def check(task, capacity, policy, pcr=PCR):
    return validate_preflight(
        task, capacity, policy, account=ACCOUNT, tenant=TENANT,
        task_arn=TASK_ARN, kms_key_arn=KEY_ARN, bucket=BUCKET,
        queue_url=QUEUE, expected_pcr17=pcr,
    )


def test_valid_synthetic_control_plane_is_accepted():
    check(*sample())


@pytest.mark.parametrize("tamper", [
    lambda t, c, k: t["taskDefinition"].update(status="INACTIVE"),
    lambda t, c, k: t["taskDefinition"].update(networkMode="host"),
    lambda t, c, k: t["taskDefinition"].update(requiresCompatibilities=["FARGATE"]),
    lambda t, c, k: t["taskDefinition"]["trustedExecutionConfiguration"].update(
        isolationMode="ISOLATED_SANDBOX"
    ),
    lambda t, c, k: t["taskDefinition"]["trustedExecutionConfiguration"].update(
        attestationPolicy=""
    ),
    lambda t, c, k: t["taskDefinition"]["containerDefinitions"][0].update(
        image=f"{ACCOUNT}.dkr.ecr.eu-central-1.amazonaws.com/{NAME}:latest"
    ),
    lambda t, c, k: t["taskDefinition"]["containerDefinitions"][0].update(
        readonlyRootFilesystem=False
    ),
    lambda t, c, k: t["taskDefinition"]["containerDefinitions"][0].update(
        secrets=[{"name": "TOKEN", "valueFrom": "example"}]
    ),
    lambda t, c, k: t["taskDefinition"]["containerDefinitions"][0]["environment"].append(
        {"name": "AWS_ACCESS_KEY_ID", "value": "synthetic"}
    ),
    lambda t, c, k: t["taskDefinition"].update(taskRoleArn="arn:aws:iam::111122223333:role/other"),
    lambda t, c, k: c["capacityProviders"][0]["managedInstancesProvider"][
        "instanceLaunchTemplate"
    ].update(nitroEnclavesEnabled=False),
    lambda t, c, k: k["Statement"][1]["Condition"]["StringEqualsIgnoreCase"].update(
        **{"kms:RecipientAttestation:PCR17": "c" * 96}
    ),
    lambda t, c, k: k["Statement"][1]["Condition"]["StringEqualsIgnoreCase"].update(
        **{"kms:RecipientAttestation:PCR8:ServiceName": "eks.amazonaws.com"}
    ),
    lambda t, c, k: k["Statement"].append({
        "Effect": "Allow", "Principal": "*", "Action": ["kms:*"]
    }),
    lambda t, c, k: k["Statement"].append({
        "Effect": "Allow", "Principal": "*", "Action": ["kms:De*"]
    }),
    lambda t, c, k: k["Statement"].append({
        "Effect": "Allow", "Principal": "*", "NotAction": ["kms:Encrypt"]
    }),
])
def test_rejects_drift_before_task_launch(tamper):
    task, capacity, key = copy.deepcopy(sample())
    tamper(task, capacity, key)
    with pytest.raises(PilotPreflightRejected):
        check(task, capacity, key)


def test_zero_pcr_is_deny_all():
    with pytest.raises(PilotPreflightRejected, match="PCR17 not pinned"):
        check(*sample(), pcr="0" * 96)


def _registered(policy="ZW52ZWxvcGU="):
    return {"taskDefinition": {"trustedExecutionConfiguration": {
        "isolationMode": "CONFIDENTIAL_SANDBOX", "attestationPolicy": policy,
    }}}


def test_official_generator_is_required_and_pcr_is_extracted(monkeypatch):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        # The released generator supports --check only on a local file.
        assert not argv[argv.index("--task-definition") + 1].startswith("arn:")
        if argv[-1] == "pcrs":
            return subprocess.CompletedProcess(
                argv, 0, stdout=json.dumps({
                    "Condition": {"StringEqualsIgnoreCase": {
                        "kms:RecipientAttestation:PCR17": PCR,
                    }},
                }),
            )
        return subprocess.CompletedProcess(argv, 0, stdout="Policy in sync")

    monkeypatch.setattr(runner, "aws", lambda profile, args, timeout=90: _registered())
    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    assert runner._verified_pcr17("demo-profile", TASK_ARN) == PCR
    assert len(calls) == 2
    assert calls[0][1] == "--check"


def test_missing_policy_generator_blocks_verification(monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError("no synthetic policy tool")
    monkeypatch.setattr(runner, "aws", lambda profile, args, timeout=90: _registered())
    monkeypatch.setattr(runner.subprocess, "run", missing)
    with pytest.raises(RuntimeError, match="verification failed"):
        runner._verified_pcr17("demo-profile", TASK_ARN)


def test_pipeline_generator_output_must_match_registered_policy(monkeypatch, tmp_path):
    (tmp_path / "attestation-policy.b64").write_text("ZW52ZWxvcGU=\n", "ascii")
    (tmp_path / "pcrs.txt").write_text(
        '--- KMS Key Policy Condition ---\n"Condition": {"StringEqualsIgnoreCase": {\n'
        f'"kms:RecipientAttestation:PCR17": "{PCR}",\n'
        '"kms:RecipientAttestation:PCR8:ServiceName": "ecs.amazonaws.com"}}\n', "utf-8")

    def no_generator(*args, **kwargs):
        raise AssertionError("local generator must not run when pipeline output is used")
    monkeypatch.setattr(runner.subprocess, "run", no_generator)
    monkeypatch.setattr(runner, "aws", lambda profile, args, timeout=90: _registered())
    assert runner._verified_pcr17("demo-profile", TASK_ARN, str(tmp_path)) == PCR
    monkeypatch.setattr(runner, "aws", lambda profile, args, timeout=90: _registered("b3RoZXI="))
    with pytest.raises(RuntimeError, match="differs from generator output"):
        runner._verified_pcr17("demo-profile", TASK_ARN, str(tmp_path))
    monkeypatch.setattr(runner, "aws", lambda profile, args, timeout=90: {"taskDefinition": {}})
    with pytest.raises(RuntimeError, match="no attestation policy"):
        runner._verified_pcr17("demo-profile", TASK_ARN, str(tmp_path))
