"""Synthetic negative tests for native AWS 3xZERO configuration checks.

These tests never contact AWS and never claim to verify live Nitro hardware.
"""
import base64
import copy

import pytest

from confidential.three_zero_gate import (
    ThreeZeroGateDenied, validate_bedrock_logging,
    validate_confidential_task_definition, validate_task_runtime,
)
from scripts.render_confidential_taskdef import make_task


def task():
    t = make_task(
        "111122223333", "pilot01",
        "111122223333.dkr.ecr.eu-central-1.amazonaws.com/notarai-confidential-pilot01@sha256:" + "a"*64,
        "arn:aws:kms:eu-central-1:111122223333:key/fake",
        "pilot-encrypted-bucket",
        "https://sqs.eu-central-1.amazonaws.com/111122223333/notarai-confidential-pilot01.fifo",
    )
    t["trustedExecutionConfiguration"] = {
        "isolationMode": "CONFIDENTIAL_SANDBOX",
        "attestationPolicy": base64.b64encode(b"synthetic-policy-not-a-signature").decode("ascii"),
    }
    return t


def test_pinned_sandbox_task_accepts_structural_check_only():
    result = validate_confidential_task_definition({"taskDefinition": task()})
    assert result == {
        "isolation_mode": "CONFIDENTIAL_SANDBOX",
        "tenant": "pilot01", "image_digest": "sha256:" + "a"*64,
        "static_config": "PASS", "hardware_verified": False,
        "operator_access_verified": False, "bedrock_verified": False,
    }


@pytest.mark.parametrize("mutator", [
    lambda t: t["trustedExecutionConfiguration"].update(isolationMode="ISOLATED_SANDBOX"),
    lambda t: t.pop("trustedExecutionConfiguration"),
    lambda t: t["trustedExecutionConfiguration"].update(attestationPolicy="attacker-policy"),
    lambda t: t["trustedExecutionConfiguration"].update(attestationPolicy=""),
    lambda t: t.update(requiresCompatibilities=["FARGATE"]),
    lambda t: t.update(networkMode="bridge"),
    lambda t: t["containerDefinitions"][0].update(image="ubuntu:latest"),
    lambda t: t["containerDefinitions"][0].update(image="111122223333.dkr.ecr.us-east-1.amazonaws.com/other@sha256:" + "a"*64),
    lambda t: t["containerDefinitions"][0].update(readonlyRootFilesystem=False),
    lambda t: t["containerDefinitions"][0].update(user="root"),
    lambda t: t["containerDefinitions"][0].update(privileged=True),
    lambda t: t["containerDefinitions"][0].update(logConfiguration={"logDriver":"awslogs"}),
    lambda t: t["containerDefinitions"][0].update(secrets=[{"name":"PASSWORD","valueFrom":"secret"}]),
    lambda t: t["containerDefinitions"][0].update(portMappings=[{"containerPort":443}]),
    lambda t: t.update(volumes=[{"name":"host"}]),
    lambda t: t["containerDefinitions"][0]["environment"].append({"name":"NOTARAI_CONFIDENTIAL_REQUIRED","value":"0"}),
    lambda t: t["containerDefinitions"][0]["environment"][0].update(value="0"),
    lambda t: t["containerDefinitions"][0]["environment"].append({"name":"AWS_SECRET_ACCESS_KEY","value":"fake"}),
    lambda t: t["containerDefinitions"].append(copy.deepcopy(t["containerDefinitions"][0])),
])
def test_sandbox_task_rejects_unsafe_changes(mutator):
    x = task()
    mutator(x)
    with pytest.raises(ThreeZeroGateDenied):
        validate_confidential_task_definition(x)


@pytest.mark.parametrize("logging", [
    {"textDataDeliveryEnabled": True},
    {"imageDataDeliveryEnabled": True},
    {"audioDataDeliveryEnabled": True},
    {"videoDataDeliveryEnabled": True},
    {"embeddingDataDeliveryEnabled": True},
    {"cloudWatchConfig": {"logGroupName":"danger"}},
    {"s3Config": {"bucketName":"danger"}},
    {"largeDataDeliveryS3Config": {"bucketName":"danger"}},
    {"textDataDeliveryEnabled":"false"},
])
def test_bedrock_content_logging_must_be_disabled(logging):
    with pytest.raises(ThreeZeroGateDenied):
        validate_bedrock_logging({"loggingConfig": logging})


def test_bedrock_no_content_logging_is_not_provider_attestation():
    assert validate_bedrock_logging({"loggingConfig": {"textDataDeliveryEnabled": False}}) == {
        "bedrock_invocation_content_logging": "DISABLED",
        "provider_retention_verified": False,
        "admin_change_prevention_verified": False,
    }


@pytest.mark.parametrize("bad", [
    {"tasks": []},
    {"tasks": [{"trustedExecutionSummary": {"isolationMode": "ISOLATED_SANDBOX", "attestationPolicyStatus":"CONFIGURED"}}]},
    {"tasks": [{"trustedExecutionSummary": {"isolationMode": "CONFIDENTIAL_SANDBOX", "attestationPolicyStatus":"MISSING"}}]},
    {"tasks": [{"enableExecuteCommand": True, "trustedExecutionSummary": {"isolationMode":"CONFIDENTIAL_SANDBOX", "attestationPolicyStatus":"CONFIGURED"}}]},
])
def test_task_runtime_negatives(bad):
    with pytest.raises(ThreeZeroGateDenied):
        validate_task_runtime(bad)


def test_task_runtime_structural_only():
    assert validate_task_runtime({"tasks":[{"enableExecuteCommand":False,"trustedExecutionSummary":{
        "isolationMode":"CONFIDENTIAL_SANDBOX","attestationPolicyStatus":"CONFIGURED"
    }}]})["hardware_release_verified"] is False
