"""Fail-closed control-plane checks before a SYNTHETIC Nitro ECS pilot.

This verifies registration and policy drift. It is NOT a substitute for a real
KMS/Nitro attestation, external egress control or a production security review.
No AWS calls, customer records, or secrets are handled by this module.
"""
from __future__ import annotations

import base64
import binascii
import re
from collections.abc import Mapping

_ACCOUNT = re.compile(r"^[0-9]{12}$")
_TENANT = re.compile(r"^[a-z0-9]{1,12}$")
_PCR = re.compile(r"^[0-9a-fA-F]{96}$")
_REGION = "eu-central-1"


class PilotPreflightRejected(ValueError):
    """Intentional generic error, with no untrusted payload in the message."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise PilotPreflightRejected(reason)


def validate_preflight(
    task_response: Mapping,
    capacity_response: Mapping,
    key_policy: Mapping,
    *,
    account: str,
    tenant: str,
    task_arn: str,
    kms_key_arn: str,
    bucket: str,
    queue_url: str,
    expected_pcr17: str,
) -> None:
    """Reject mismatched task, unpinned images, broad KMS grants and no-Nitro capacity."""
    _require(bool(_ACCOUNT.fullmatch(account) and _TENANT.fullmatch(tenant)),
             "invalid account or tenant")
    _require(bool(_PCR.fullmatch(expected_pcr17)) and
             expected_pcr17.lower() != "0" * 96, "PCR17 not pinned")
    prefix = f"notarai-confidential-{tenant}"
    role = f"arn:aws:iam::{account}:role/{prefix}"
    expected_arn_start = (
        f"arn:aws:ecs:{_REGION}:{account}:task-definition/{prefix}:"
    )
    _require(task_arn.startswith(expected_arn_start) and
             task_arn[len(expected_arn_start):].isdigit(), "wrong ECS task ARN")
    _require(kms_key_arn.startswith(f"arn:aws:kms:{_REGION}:{account}:key/"),
             "wrong KMS key ARN")
    _require(bool(re.fullmatch(
        rf"https://sqs\\.{_REGION}\\.amazonaws\\.com/{account}/{prefix}\\.fifo",
        queue_url,
    )), "wrong SQS queue")
    _require(bool(re.fullmatch(r"[a-z0-9][a-z0-9.-]{2,62}", bucket)),
             "invalid bucket")

    definition = task_response.get("taskDefinition")
    _require(isinstance(definition, dict), "task definition unavailable")
    _require(definition.get("taskDefinitionArn") == task_arn and
             definition.get("status") == "ACTIVE", "task definition not active")
    _require(definition.get("family") == prefix and
             definition.get("networkMode") == "awsvpc" and
             definition.get("requiresCompatibilities") == ["MANAGED_INSTANCES"],
             "unsupported ECS runtime")
    _require(definition.get("taskRoleArn") == role and
             definition.get("executionRoleArn") ==
             f"arn:aws:iam::{account}:role/notarai-confidential-execution-{tenant}",
             "wrong IAM role")
    _require(not definition.get("volumes"), "shared task volumes forbidden")
    trust = definition.get("trustedExecutionConfiguration")
    _require(isinstance(trust, dict) and
             trust.get("isolationMode") == "CONFIDENTIAL_SANDBOX",
             "confidential isolation missing")
    envelope = trust.get("attestationPolicy")
    _require(isinstance(envelope, str) and len(envelope) > 16,
             "attestation policy missing")
    try:
        _require(len(base64.b64decode(envelope, validate=True)) >= 16,
                 "attestation policy invalid")
    except (ValueError, binascii.Error) as exc:
        raise PilotPreflightRejected("attestation policy invalid") from exc
    containers = definition.get("containerDefinitions")
    _require(isinstance(containers, list) and len(containers) == 1,
             "unexpected sidecar")
    container = containers[0]
    image = container.get("image", "")
    expected_image_start = (
        f"{account}.dkr.ecr.{_REGION}.amazonaws.com/{prefix}@sha256:"
    )
    _require(isinstance(image, str) and image.startswith(expected_image_start) and
             bool(re.fullmatch(r"[0-9a-f]{64}", image[len(expected_image_start):])),
             "guest image is not an approved immutable digest")
    _require(container.get("name") == "confidential-browser" and
             container.get("user") == "10001:10001" and
             container.get("readonlyRootFilesystem") is True and
             container.get("privileged") is not True,
             "guest container security posture changed")
    for field in ("secrets", "environmentFiles", "mountPoints", "volumesFrom",
                  "portMappings", "logConfiguration", "entryPoint", "command"):
        _require(not container.get(field), "unexpected guest extension")
    expected_env = {
        "NOTARAI_CONFIDENTIAL_REQUIRED": "1",
        "NOTARAI_CONFIDENTIAL_TENANT": tenant,
        "NOTARAI_CONFIDENTIAL_BUCKET": bucket,
        "NOTARAI_CONFIDENTIAL_QUEUE_URL": queue_url,
        "NOTARAI_CONFIDENTIAL_KMS_KEY_ARN": kms_key_arn,
        "AWS_REGION": _REGION,
        "HOME": "/tmp", "XDG_CACHE_HOME": "/tmp", "TMPDIR": "/tmp",
    }
    environment = container.get("environment")
    _require(isinstance(environment, list) and len(environment) == len(expected_env),
             "guest environment changed")
    observed_env = {
        item.get("name"): item.get("value")
        for item in environment if isinstance(item, dict)
    }
    _require(observed_env == expected_env, "guest environment not pinned")

    providers = capacity_response.get("capacityProviders")
    _require(isinstance(providers, list) and len(providers) == 1,
             "wrong capacity provider")
    provider = providers[0]
    _require(provider.get("name") == prefix and provider.get("status") == "ACTIVE",
             "Nitro capacity provider unavailable")
    launch = (provider.get("managedInstancesProvider") or {}).get(
        "instanceLaunchTemplate"
    ) or {}
    _require(launch.get("nitroEnclavesEnabled") is True,
             "hardware Nitro sandbox capacity is disabled")

    statements = key_policy.get("Statement")
    _require(isinstance(statements, list), "missing KMS key policy")
    decrypt_allow = []
    for statement in statements:
        if not isinstance(statement, dict) or statement.get("Effect") != "Allow":
            continue
        actions = statement.get("Action", [])
        if isinstance(actions, str):
            actions = [actions]
        if not isinstance(actions, list):
            raise PilotPreflightRejected("unrecognized KMS actions")
        if any(
            isinstance(action, str) and
            (action.lower() in {"kms:decrypt", "kms:*", "*"} or
             action.lower().startswith("kms:decry"))
            for action in actions
        ):
            decrypt_allow.append(statement)
    _require(len(decrypt_allow) == 1, "KMS decrypt grants must be unique")
    grant = decrypt_allow[0]
    condition = grant.get("Condition") or {}
    _require(grant.get("Principal") == "*" and
             (condition.get("ArnEquals") or {}).get("aws:PrincipalArn") == role,
             "KMS principal not pinned")
    equality = condition.get("StringEqualsIgnoreCase") or {}
    _require(equality.get("kms:RecipientAttestation:PCR17", "").lower() ==
             expected_pcr17.lower() and
             equality.get("kms:RecipientAttestation:PCR8:ServiceName") ==
             "ecs.amazonaws.com",
             "KMS attestation policy mismatch")
