"""Conservative read-only AWS Nitro Sandbox configuration gate for NotarAI 3xZERO.

No attestation forgery, no KMS key changes, no AWS calls in this module.
Passing a static configuration check is NOT evidence that 3xZERO or hardware
attestation was verified. The customer-owned key release cryptography resides
in customer_attested_release.py and must be run by an independently trusted client.
"""
from __future__ import annotations

import base64
import binascii
import re
from collections.abc import Mapping

_IMAGE = re.compile(
    r"^[0-9]{12}\.dkr\.ecr\.eu-central-1\.amazonaws\.com/"
    r"[A-Za-z0-9._/-]+@sha256:[0-9a-f]{64}$"
)


class ThreeZeroGateDenied(ValueError):
    """Fail-closed configuration rejection, without secret details."""


def _deny() -> None:
    raise ThreeZeroGateDenied("3xZERO configuration denied")


def validate_confidential_task_definition(payload: Mapping) -> dict:
    """Review an ECS DescribeTaskDefinition payload, not a user's arbitrary flag.

    The result establishes ONLY that the supplied description is structurally
    eligible for a confidential task. Callers must independently check live AWS
    account, role, key policies, attestation, release signer, and actual run.
    """
    if not isinstance(payload, Mapping):
        _deny()
    task = payload.get("taskDefinition", payload)
    if not isinstance(task, Mapping):
        _deny()
    trusted = task.get("trustedExecutionConfiguration")
    if not isinstance(trusted, Mapping) or trusted.get("isolationMode") != "CONFIDENTIAL_SANDBOX":
        _deny()
    encoded = trusted.get("attestationPolicy")
    if not isinstance(encoded, str) or len(encoded) < 16 or len(encoded) > 1024 * 1024:
        _deny()
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        _deny()
    if len(raw) < 8 or base64.b64encode(raw).decode("ascii") != encoded:
        _deny()
    if task.get("requiresCompatibilities") != ["MANAGED_INSTANCES"]:
        _deny()
    if task.get("networkMode") != "awsvpc":
        _deny()
    containers = task.get("containerDefinitions")
    if not isinstance(containers, list) or len(containers) != 1:
        _deny()
    c = containers[0]
    if not isinstance(c, Mapping) or c.get("essential") is not True:
        _deny()
    image = c.get("image")
    if not isinstance(image, str) or not _IMAGE.fullmatch(image):
        _deny()
    if c.get("readonlyRootFilesystem") is not True:
        _deny()
    if c.get("command") != ["python", "-m", "confidential.customer_v3_worker"]:
        _deny()
    if c.get("privileged") is True or c.get("user") in (None, "", "root", "0", "0:0"):
        _deny()
    if c.get("logConfiguration") or c.get("secrets") or c.get("secretOptions"):
        _deny()
    if task.get("volumes") or c.get("mountPoints") or c.get("portMappings"):
        _deny()
    env = c.get("environment")
    if not isinstance(env, list) or not env:
        _deny()
    values = {}
    for entry in env:
        if not isinstance(entry, Mapping) or set(entry) != {"name", "value"}:
            _deny()
        k, v = entry["name"], entry["value"]
        if not isinstance(k, str) or not isinstance(v, str) or k in values:
            _deny()
        if any(word in k.upper() for word in ("PASSWORD", "TOKEN", "SECRET", "PRIVATE_KEY", "ACCESS_KEY")):
            _deny()
        values[k] = v
    if values.get("NOTARAI_CONFIDENTIAL_REQUIRED") != "1":
        _deny()
    if values.get("NOTARAI_3ZERO_MODE") != "customer-v3":
        _deny()
    if "NOTARAI_CONFIDENTIAL_KMS_KEY_ARN" in values:
        _deny()
    if values.get("AWS_ACCOUNT_ID") != image.split(".", 1)[0]:
        _deny()
    if values.get("AWS_REGION") != "eu-central-1":
        _deny()
    tenant = values.get("NOTARAI_CONFIDENTIAL_TENANT", "")
    if not re.fullmatch(r"[a-z0-9]{1,12}", tenant):
        _deny()
    return {"isolation_mode": "CONFIDENTIAL_SANDBOX",
            "tenant": tenant, "image_digest": image.rsplit("@", 1)[-1],
            "static_config": "PASS", "hardware_verified": False,
            "operator_access_verified": False, "bedrock_verified": False}


def validate_bedrock_logging(payload: Mapping) -> dict:
    """Review AWS bedrock GetModelInvocationLoggingConfiguration response.

    Absence of a logging config is acceptable for *this check only*.
    It does not establish that account administrators cannot turn logging on,
    or whether the model provider retains data.
    """
    if not isinstance(payload, Mapping):
        _deny()
    logging = payload.get("loggingConfig")
    if logging is None:
        logging = {}
    if not isinstance(logging, Mapping):
        _deny()
    for name in ("textDataDeliveryEnabled", "imageDataDeliveryEnabled",
                 "embeddingDataDeliveryEnabled", "videoDataDeliveryEnabled",
                 "audioDataDeliveryEnabled"):
        if logging.get(name) is not False and name in logging:
            _deny()
    if logging.get("cloudWatchConfig") or logging.get("s3Config") or logging.get("largeDataDeliveryS3Config"):
        _deny()
    return {"bedrock_invocation_content_logging": "DISABLED",
            "provider_retention_verified": False,
            "admin_change_prevention_verified": False}


def validate_task_runtime(payload: Mapping) -> dict:
    """Review ECS DescribeTasks result; policy CONFIGURED is not proof of a PCR match."""
    if not isinstance(payload, Mapping):
        _deny()
    tasks = payload.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 1 or payload.get("failures"):
        _deny()
    task = tasks[0]
    if not isinstance(task, Mapping) or task.get("enableExecuteCommand") is True:
        _deny()
    trusted = task.get("trustedExecutionSummary")
    if not isinstance(trusted, Mapping):
        _deny()
    if trusted.get("isolationMode") != "CONFIDENTIAL_SANDBOX":
        _deny()
    if trusted.get("attestationPolicyStatus") != "CONFIGURED":
        _deny()
    return {"runtime_mode": "CONFIDENTIAL_SANDBOX",
            "attestation_policy": "CONFIGURED",
            "hardware_release_verified": False}
