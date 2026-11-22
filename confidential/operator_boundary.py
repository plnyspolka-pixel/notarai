"""Fail-closed structural proof for a separately operated confidential key custodian.

This is NOT a Nitro hardware attestation verifier. It verifies a read-only
snapshot of AWS KMS key metadata and policy plus the signed ECS configuration.
Snapshots are not proof of the ownership of AWS Organizations or a malicious
cloud operator; a separate human/cryptographically authorized custodian is
required before any commercial Zero Operator Access claim.

Never emit ciphertext, plaintext, access tokens, subject data or raw AWS
exceptions. All errors are intentionally generic.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from collections.abc import Mapping

_REGION = "eu-central-1"
_ACCOUNT = re.compile(r"^[0-9]{12}$")
_TENANT = re.compile(r"^[a-z0-9]{1,12}$")
_PCR17 = re.compile(r"^[a-fA-F0-9]{96}$")
_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_UUID = re.compile(r"^[A-Za-z0-9-]+$")

_CUSTODY_ADMIN = frozenset({
    "kms:DescribeKey", "kms:GetKeyPolicy", "kms:PutKeyPolicy",
    "kms:EnableKey", "kms:DisableKey", "kms:UpdateKeyDescription",
    "kms:ListResourceTags", "kms:TagResource", "kms:UntagResource",
    "kms:ScheduleKeyDeletion", "kms:CancelKeyDeletion",
})
_PUBLIC_ONLY = frozenset({"kms:GetPublicKey", "kms:DescribeKey"})


class BoundaryDenied(ValueError):
    """Fail closed, without leaking AWS inputs."""


def require(condition: bool, label: str) -> None:
    if not condition:
        raise BoundaryDenied(label)


def canonical_digest(document: object) -> str:
    return hashlib.sha256(
        json.dumps(document, ensure_ascii=True, sort_keys=True,
                   separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _actions(statement: Mapping) -> frozenset[str]:
    actions = statement.get("Action")
    if isinstance(actions, str):
        actions = [actions]
    require(isinstance(actions, list) and bool(actions) and
            all(isinstance(x, str) for x in actions) and
            len(actions) == len(set(actions)),
            "unknown KMS policy action")
    return frozenset(actions)


def _statement_map(document: Mapping) -> dict[str, dict]:
    require(isinstance(document, Mapping) and
            document.get("Version") == "2012-10-17",
            "KMS policy document invalid")
    statements = document.get("Statement")
    require(isinstance(statements, list) and len(statements) == 3 and
            all(isinstance(x, dict) for x in statements),
            "KMS policy has unexpected statements")
    result = {s.get("Sid"): s for s in statements}
    require(len(result) == 3 and set(result) == {
        "CustodyAdministratorOnly",
        "NotaraiPublicKeyOnly",
        "OnlyAttestedNitroTaskDecrypt",
    }, "KMS policy has unreviewed grants")
    for statement in statements:
        require(statement.get("Effect") == "Allow" and
                statement.get("Resource") == "*" and
                "NotPrincipal" not in statement and
                "NotResource" not in statement and
                "NotAction" not in statement,
                "KMS wildcard or inverted policy forbidden")
    return result


def _check_policy(policy: Mapping, *, operator: str, custody: str,
                  tenant: str, pcr17: str) -> None:
    statements = _statement_map(policy)
    admin = statements["CustodyAdministratorOnly"]
    require(set(admin) == {"Sid", "Effect", "Principal", "Action", "Resource"} and
            admin.get("Principal") == {"AWS": f"arn:aws:iam::{custody}:root"} and
            _actions(admin) == _CUSTODY_ADMIN,
            "custody administration is not independently restricted")
    public = statements["NotaraiPublicKeyOnly"]
    require(set(public) == {"Sid", "Effect", "Principal", "Action", "Resource"} and
            public.get("Principal") == {"AWS": f"arn:aws:iam::{operator}:root"} and
            _actions(public) == _PUBLIC_ONLY,
            "operator must have public KMS read permissions only")
    decrypt = statements["OnlyAttestedNitroTaskDecrypt"]
    role = f"arn:aws:iam::{operator}:role/notarai-confidential-{tenant}"
    require(set(decrypt) == {"Sid", "Effect", "Principal", "Action", "Resource", "Condition"} and
            decrypt.get("Principal") == {"AWS": role} and
            _actions(decrypt) == {"kms:Decrypt"} and
            decrypt.get("Condition") == {
                "StringEqualsIgnoreCase": {
                    "kms:RecipientAttestation:PCR17": pcr17,
                    "kms:RecipientAttestation:PCR8:ServiceName": "ecs.amazonaws.com",
                },
            }, "attested decrypt has an unapproved principal or measurement")


def _check_task(task: Mapping, *, operator: str, custody_arn: str,
                tenant: str, task_arn: str,
                expected_digest: str) -> None:
    expected_family = f"notarai-confidential-{tenant}"
    require(isinstance(task, Mapping) and
            task.get("taskDefinitionArn") == task_arn and
            task.get("family") == expected_family and
            task.get("status") == "ACTIVE" and
            task.get("networkMode") == "awsvpc" and
            task.get("requiresCompatibilities") == ["MANAGED_INSTANCES"] and
            task.get("taskRoleArn") ==
            f"arn:aws:iam::{operator}:role/{expected_family}" and
            task.get("executionRoleArn") ==
            f"arn:aws:iam::{operator}:role/notarai-confidential-execution-{tenant}" and
            not task.get("volumes"),
            "confidential tenant task identity mismatch")
    trust = task.get("trustedExecutionConfiguration") or {}
    require(isinstance(trust, Mapping) and
            trust.get("isolationMode") == "CONFIDENTIAL_SANDBOX",
            "hardware Nitro mode is not required")
    policy = trust.get("attestationPolicy")
    require(isinstance(policy, str) and len(policy) >= 24,
            "attestation policy not supplied")
    try:
        encoded_policy = base64.b64decode(policy, validate=True)
    except (ValueError, binascii.Error):
        raise BoundaryDenied("invalid attestation policy envelope") from None
    require(len(encoded_policy) >= 16,
            "attestation policy placeholder rejected")
    image = (f"{operator}.dkr.ecr.{_REGION}.amazonaws.com/"
             f"notarai-confidential-shared@sha256:{expected_digest}")
    containers = task.get("containerDefinitions")
    require(isinstance(containers, list) and len(containers) == 1,
            "task contains unexpected containers")
    guest = containers[0]
    require(isinstance(guest, dict) and
            guest.get("name") == "confidential-browser" and
            guest.get("image") == image and
            guest.get("user") == "10001:10001" and
            guest.get("readonlyRootFilesystem") is True and
            guest.get("privileged") is not True,
            "guest image or privilege changed")
    for prohibited in ("logConfiguration", "secrets", "environmentFiles",
                       "mountPoints", "volumesFrom", "portMappings",
                       "entryPoint", "command"):
        require(not guest.get(prohibited), "guest control changed")
    env = guest.get("environment")
    require(isinstance(env, list) and
            all(isinstance(x, dict) and set(x) == {"name", "value"}
                for x in env),
            "task environment invalid")
    values = {x["name"]: x["value"] for x in env}
    require(len(values) == len(env) and
            values.get("NOTARAI_CONFIDENTIAL_TENANT") == tenant and
            values.get("NOTARAI_CONFIDENTIAL_REQUIRED") == "1" and
            values.get("NOTARAI_CONFIDENTIAL_KMS_KEY_ARN") == custody_arn and
            values.get("AWS_REGION") == _REGION,
            "guest configuration is not tenant-bound")
    queue = (f"https://sqs.{_REGION}.amazonaws.com/{operator}/"
             f"{expected_family}.fifo")
    require(values.get("NOTARAI_CONFIDENTIAL_QUEUE_URL") == queue,
            "guest queue is not tenant-bound")
    require(set(values) == {
        "NOTARAI_CONFIDENTIAL_TENANT",
        "NOTARAI_CONFIDENTIAL_REQUIRED",
        "NOTARAI_CONFIDENTIAL_KMS_KEY_ARN",
        "NOTARAI_CONFIDENTIAL_QUEUE_URL",
        "NOTARAI_CONFIDENTIAL_BUCKET",
        "AWS_REGION", "HOME", "XDG_CACHE_HOME", "TMPDIR",
    }, "unexpected guest environment field")
    require(values.get("HOME") == values.get("XDG_CACHE_HOME") ==
            values.get("TMPDIR") == "/tmp",
            "guest filesystem settings invalid")


def inspect_operator_boundary(
    *, operator_account: str, custody_account: str, tenant: str,
    key_arn: str, pcr17: str, image_sha256: str,
    task_arn: str, key_metadata: Mapping,
    key_policy: Mapping, key_grants: list,
    task_definition: Mapping,
) -> dict:
    """Return a redacted, reproducible CONFIGURATION snapshot, not a claim of hardware proof."""
    require(isinstance(operator_account, str) and
            isinstance(custody_account, str) and
            bool(_ACCOUNT.fullmatch(operator_account)) and
            bool(_ACCOUNT.fullmatch(custody_account)) and
            operator_account != custody_account,
            "key custody is not a distinct AWS account")
    require(isinstance(tenant, str) and bool(_TENANT.fullmatch(tenant)),
            "tenant identifier invalid")
    require(isinstance(pcr17, str) and bool(_PCR17.fullmatch(pcr17)) and
            pcr17.lower() != "0" * 96 and
            isinstance(image_sha256, str) and bool(_DIGEST.fullmatch(image_sha256)),
            "approved attestation or image digest missing")
    require(isinstance(key_arn, str) and
            key_arn.startswith(f"arn:aws:kms:{_REGION}:{custody_account}:key/") and
            bool(_UUID.fullmatch(key_arn.rsplit("/", 1)[-1])),
            "KMS key is not independently held")
    family = f"notarai-confidential-{tenant}"
    require(isinstance(task_arn, str) and
            re.fullmatch(
                rf"arn:aws:ecs:{_REGION}:{operator_account}:"
                rf"task-definition/{family}:[1-9][0-9]*", task_arn
            ) is not None, "invalid exact task revision")
    require(isinstance(key_metadata, Mapping) and
            key_metadata.get("Arn") == key_arn and
            key_metadata.get("AWSAccountId") == custody_account and
            key_metadata.get("KeyManager") == "CUSTOMER" and
            key_metadata.get("Origin") == "AWS_KMS" and
            key_metadata.get("KeySpec") == "RSA_3072" and
            key_metadata.get("KeyUsage") == "ENCRYPT_DECRYPT" and
            key_metadata.get("KeyState") == "Enabled" and
            key_metadata.get("Enabled") is True and
            key_metadata.get("MultiRegion") is False,
            "custodian-owned KMS key metadata mismatch")
    require(isinstance(key_grants, list) and key_grants == [],
            "unreviewed KMS grants permit key use")
    _check_policy(key_policy, operator=operator_account, custody=custody_account,
                  tenant=tenant, pcr17=pcr17)
    _check_task(task_definition, operator=operator_account,
                custody_arn=key_arn, tenant=tenant,
                task_arn=task_arn, expected_digest=image_sha256)
    return {
        "schema": "notarai.operator_boundary.configuration.v1",
        "operator_account": operator_account,
        "custody_account": custody_account,
        "tenant": tenant,
        "kms_key_arn": key_arn,
        "task_definition_arn": task_arn,
        "expected_pcr17": pcr17.lower(),
        "image_sha256": image_sha256,
        "key_policy_sha256": canonical_digest(key_policy),
        "task_definition_sha256": canonical_digest(task_definition),
        "static_configuration_verified": True,
        "live_nitro_attestation_verified": False,
        "independent_custody_verified": False,
        "zero_operator_access_proven": False,
    }
