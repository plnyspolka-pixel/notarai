"""Fail-closed server-side custody release verification for the synthetic Nitro pilot.

This gate checks the *live* ECS/KMS configuration on every launch. The receipt
and KMS verification key are read with a custodian-controlled, read-only role.
A Lambda environment variable or caller payload is NOT an independent trust
root: external account ownership and all direct RunTask/KMS paths still
require separate hardware and organizational audits.

No Decrypt, Sign, PII, form submissions or AWS mutations are performed here.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from datetime import datetime, timezone
from collections.abc import Mapping

from confidential.operator_boundary import BoundaryDenied, inspect_operator_boundary

_REGION = "eu-central-1"
_DOMAIN = b"NotarAI:confidential:custody-release:v1\x00"
_HEX64 = re.compile(r"^[a-f0-9]{64}$")
_HEX96 = re.compile(r"^[a-f0-9]{96}$")
_RELEASE_ID = re.compile(r"^[a-f0-9]{32}$")
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_FIELDS = frozenset({
    "schema", "tenant", "operator_account", "custody_account",
    "kms_key_arn", "task_definition_arn", "expected_pcr17", "image_sha256",
    "key_policy_sha256", "task_definition_sha256", "release_id",
    "issued_at", "expires_at",
})
_BINDING = _FIELDS - {"schema", "release_id", "issued_at", "expires_at"}


def _require(predicate: bool) -> None:
    if not predicate:
        raise BoundaryDenied("independent release enforcement denied")


def _parse_time(text: object) -> datetime:
    _require(isinstance(text, str) and bool(_UTC.fullmatch(text)))
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        raise BoundaryDenied("independent release enforcement denied") from None


def verify_kms_signed_release(*, receipt: object, report: Mapping,
                              signing_key_arn: str, pinned_fingerprint: str,
                              kms, clock: datetime | None = None) -> None:
    """Validate the exact v1 signature with the external KMS Verify API.

    RAW matches the existing custodian_sign_confidential_release.py signer.
    This avoids depending on native crypto libraries in the Lambda ZIP.
    """
    _require(isinstance(receipt, dict) and set(receipt) ==
             {"payload", "signature_b64"})
    payload = receipt["payload"]
    _require(isinstance(payload, dict) and set(payload) == _FIELDS)
    _require(payload["schema"] == "notarai.confidential.custody-release.v1")
    _require(report.get("static_configuration_verified") is True)
    _require(all(type(payload[key]) is str and
                 payload[key] == report.get(key) for key in _BINDING))
    _require(isinstance(payload["release_id"], str) and
             bool(_RELEASE_ID.fullmatch(payload["release_id"])))
    issued, expires = _parse_time(payload["issued_at"]), _parse_time(payload["expires_at"])
    now = clock if clock is not None else datetime.now(timezone.utc)
    _require(isinstance(now, datetime) and now.tzinfo is not None)
    now = now.astimezone(timezone.utc)
    _require(issued <= now < expires and
             0 < (expires - issued).total_seconds() <= 48 * 3600)
    _require(isinstance(pinned_fingerprint, str) and
             bool(_HEX64.fullmatch(pinned_fingerprint)))
    custody = report["custody_account"]
    _require(isinstance(signing_key_arn, str) and
             signing_key_arn.startswith(f"arn:aws:kms:{_REGION}:{custody}:key/"))
    metadata = kms.describe_key(KeyId=signing_key_arn)["KeyMetadata"]
    _require(metadata.get("Arn") == signing_key_arn and
             metadata.get("AWSAccountId") == custody and
             metadata.get("KeyManager") == "CUSTOMER" and
             metadata.get("KeyUsage") == "SIGN_VERIFY" and
             metadata.get("KeySpec") == "ECC_NIST_P256" and
             metadata.get("KeyState") == "Enabled")
    public = kms.get_public_key(KeyId=signing_key_arn)
    _require("ECDSA_SHA_256" in public.get("SigningAlgorithms", []) and
             isinstance(public.get("PublicKey"), bytes) and
             hashlib.sha256(public["PublicKey"]).hexdigest() == pinned_fingerprint)
    try:
        signature = base64.b64decode(receipt["signature_b64"], validate=True)
        serialized = _DOMAIN + json.dumps(
            payload, sort_keys=True, ensure_ascii=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    except (ValueError, TypeError, binascii.Error, UnicodeError):
        raise BoundaryDenied("independent release enforcement denied") from None
    _require(bool(signature))
    verification = kms.verify(
        KeyId=signing_key_arn, Message=serialized, MessageType="RAW",
        Signature=signature, SigningAlgorithm="ECDSA_SHA_256",
    )
    _require(verification.get("SignatureValid") is True and
             verification.get("KeyId") == signing_key_arn and
             verification.get("SigningAlgorithm") == "ECDSA_SHA_256")


class LiveReleaseGate:
    """Callable gate. NO switches that allow a demo/same-account fallback."""

    def __init__(self, *, config, workload_sts, ecs, assume_custody,
                 custody_account: str, custody_audit_role_arn: str,
                 kms_key_arn: str, signing_key_arn: str,
                 approved_pcr17: str, approved_image_sha256: str,
                 pinned_signer_sha256: str, release_bucket: str,
                 release_key: str, release_version: str, clock=None):
        self.config = config
        self.workload_sts = workload_sts
        self.ecs = ecs
        self.assume_custody = assume_custody
        self.custody_account = custody_account
        self.custody_audit_role_arn = custody_audit_role_arn
        self.kms_key_arn = kms_key_arn
        self.signing_key_arn = signing_key_arn
        self.approved_pcr17 = approved_pcr17
        self.approved_image_sha256 = approved_image_sha256
        self.pinned_signer_sha256 = pinned_signer_sha256
        self.release_bucket = release_bucket
        self.release_key = release_key
        self.release_version = release_version
        self.clock = clock

    def __call__(self) -> None:
        cfg = self.config
        cfg.validate()
        _require(cfg.shared_pool is True and
                 cfg.external_custody_key_arn == self.kms_key_arn)
        _require(self.workload_sts.get_caller_identity().get("Account") == cfg.account)
        _require(self.custody_account != cfg.account and
                 bool(re.fullmatch(r"[0-9]{12}", self.custody_account or "")))
        _require(self.custody_audit_role_arn.startswith(
            f"arn:aws:iam::{self.custody_account}:role/"))
        _require(isinstance(self.approved_pcr17, str) and
                 bool(_HEX96.fullmatch(self.approved_pcr17)) and
                 self.approved_pcr17 != "0" * 96)
        _require(isinstance(self.approved_image_sha256, str) and
                 bool(_HEX64.fullmatch(self.approved_image_sha256)))
        _require(all(isinstance(v, str) and v for v in (
            self.release_bucket, self.release_key, self.release_version)))
        # Separate audit role is assumed for read-only custody state. The
        # custodian account MUST be independently administered (out-of-band).
        custodian = self.assume_custody(self.custody_audit_role_arn)
        _require(custodian.client("sts").get_caller_identity().get("Account")
                 == self.custody_account)
        kms = custodian.client("kms")
        key_metadata = kms.describe_key(KeyId=self.kms_key_arn)["KeyMetadata"]
        policy_text = kms.get_key_policy(
            KeyId=self.kms_key_arn, PolicyName="default")["Policy"]
        try:
            policy = json.loads(policy_text)
        except (ValueError, TypeError):
            raise BoundaryDenied("independent release enforcement denied") from None
        grants = kms.list_grants(KeyId=self.kms_key_arn, Limit=100)
        _require(not any(grants.get(marker) for marker in (
            "Truncated", "NextMarker", "Marker")))
        task = self.ecs.describe_task_definition(
            taskDefinition=cfg.task_definition_arn)["taskDefinition"]
        report = inspect_operator_boundary(
            operator_account=cfg.account,
            custody_account=self.custody_account,
            tenant=cfg.tenant, key_arn=self.kms_key_arn,
            pcr17=self.approved_pcr17,
            image_sha256=self.approved_image_sha256,
            task_arn=cfg.task_definition_arn, key_metadata=key_metadata,
            key_policy=policy, key_grants=grants.get("Grants"),
            task_definition=task,
        )
        # The receipt is immutable by S3 VersionId, in the custodian account,
        # not an operator-controlled payload or Lambda event attribute.
        response = custodian.client("s3").get_object(
            Bucket=self.release_bucket, Key=self.release_key,
            VersionId=self.release_version,
        )
        raw = response["Body"].read(16385)
        _require(len(raw) <= 16384)
        try:
            receipt = json.loads(raw)
        except (ValueError, UnicodeError, TypeError):
            raise BoundaryDenied("independent release enforcement denied") from None
        verify_kms_signed_release(
            receipt=receipt, report=report,
            signing_key_arn=self.signing_key_arn,
            pinned_fingerprint=self.pinned_signer_sha256, kms=kms,
            clock=self.clock() if self.clock is not None else None,
        )


def assume_custody_readonly(sts, role_arn: str):
    """Assume the externally granted READ-ONLY custody role; no admin/sign."""
    import boto3
    credential = sts.assume_role(
        RoleArn=role_arn, RoleSessionName="notarai-sec05-release-read",
        DurationSeconds=900,
    )["Credentials"]
    return boto3.Session(
        aws_access_key_id=credential["AccessKeyId"],
        aws_secret_access_key=credential["SecretAccessKey"],
        aws_session_token=credential["SessionToken"],
        region_name=_REGION,
    )
