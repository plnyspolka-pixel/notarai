"""SEC-11: independently signed, privacy-minimal security evidence bundles.

Signature/chain verification is OFFLINE and does not call AWS or NotarAI.
A valid signature attests to the signer's assertion, not to physical Nitro,
AWS WORM configuration, or Zero Operator Access. An externally pinned trust
root and independent storage verification are mandatory for such claims.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

SCHEMA = "notarai.confidential.evidence.v1"
DOMAIN = b"NotarAI:independent-evidence:v1\x00"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX96 = re.compile(r"^[0-9a-f]{96}$")
ACCOUNT = re.compile(r"^[0-9]{12}$")
TOKEN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
TASK = re.compile(r"^arn:aws:ecs:eu-central-1:[0-9]{12}:task/[A-Za-z0-9_/-]{1,160}$")
REQUIRED_CHECKS = frozenset({
    "sts_identity", "organizations_scope", "nitro_hardware",
    "kms_attested_decrypt", "kms_operator_deny", "image_release",
    "cloudtrail_kms", "operator_overwrite_deny", "operator_delete_deny",
    "cross_tenant_deny",
})
FIELDS = frozenset({
    "schema", "tenant", "region", "operator_account", "custody_account",
    "observed_at", "expires_at", "source_sha256", "image_sha256",
    "task_arn", "pcr17", "kms_policy_sha256", "release_id",
    "evidence_owner", "sequence", "previous_sha256", "checks",
})
CHECK_FIELDS = frozenset({"status", "provenance", "artifact_sha256", "owner"})
PACKAGE_FIELDS = frozenset({"manifest", "signature_b64"})
PROVENANCE = frozenset({"MOCK", "AWS_LIVE", "INDEPENDENT"})
STATUSES = frozenset({"PASS", "FAIL", "BLOCKED", "UNVERIFIED"})


class InvalidEvidence(ValueError):
    """Fixed messages only; never include untrusted manifest contents."""


def _utc(value: object) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value
    ):
        raise InvalidEvidence("invalid UTC timestamp")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        raise InvalidEvidence("invalid UTC timestamp") from None


def _token(value: object) -> bool:
    return isinstance(value, str) and TOKEN.fullmatch(value) is not None


def _hex(value: object, pattern=HEX64) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def canonical_manifest(manifest: Mapping) -> bytes:
    """Strict schema keeps personal data, logs, URLs and free text out of evidence."""
    if not isinstance(manifest, dict) or set(manifest) != FIELDS:
        raise InvalidEvidence("manifest fields invalid")
    if manifest["schema"] != SCHEMA or manifest["region"] != "eu-central-1":
        raise InvalidEvidence("manifest schema or region invalid")
    if not all(_token(manifest[k]) for k in
               ("tenant", "release_id", "evidence_owner")):
        raise InvalidEvidence("manifest identity invalid")
    if not all(_hex(manifest[k]) for k in
               ("source_sha256", "image_sha256", "kms_policy_sha256")):
        raise InvalidEvidence("manifest digest invalid")
    if not _hex(manifest["pcr17"], HEX96):
        raise InvalidEvidence("attestation measurement invalid")
    if not all(isinstance(manifest[k], str) and ACCOUNT.fullmatch(manifest[k])
               for k in ("operator_account", "custody_account")):
        raise InvalidEvidence("AWS account invalid")
    if manifest["operator_account"] == manifest["custody_account"]:
        raise InvalidEvidence("independent custody account required")
    if not isinstance(manifest["task_arn"], str) or not TASK.fullmatch(manifest["task_arn"]):
        raise InvalidEvidence("task identity invalid")
    if type(manifest["sequence"]) is not int or not 1 <= manifest["sequence"] <= 10000000:
        raise InvalidEvidence("sequence invalid")
    previous = manifest["previous_sha256"]
    if (manifest["sequence"] == 1 and previous is not None) or (
        manifest["sequence"] > 1 and not _hex(previous)
    ):
        raise InvalidEvidence("evidence chain link invalid")
    observed, expires = _utc(manifest["observed_at"]), _utc(manifest["expires_at"])
    if not observed < expires or expires - observed > timedelta(days=7):
        raise InvalidEvidence("evidence expiry window invalid")
    checks = manifest["checks"]
    if not isinstance(checks, dict) or set(checks) != REQUIRED_CHECKS:
        raise InvalidEvidence("required control evidence missing")
    for name, record in checks.items():
        if not isinstance(record, dict) or set(record) != CHECK_FIELDS:
            raise InvalidEvidence("control evidence schema invalid")
        if record["status"] not in STATUSES or record["provenance"] not in PROVENANCE:
            raise InvalidEvidence("control evidence status invalid")
        if not _token(record["owner"]):
            raise InvalidEvidence("control evidence owner invalid")
        if record["artifact_sha256"] is not None and not _hex(record["artifact_sha256"]):
            raise InvalidEvidence("control artifact digest invalid")
        if record["status"] == "PASS" and record["artifact_sha256"] is None:
            raise InvalidEvidence("PASS needs independently retrievable artifact")
    return DOMAIN + json.dumps(
        manifest, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")


def manifest_sha256(manifest: Mapping) -> str:
    return hashlib.sha256(canonical_manifest(manifest)).hexdigest()


def public_fingerprint(public_key_raw: bytes) -> str:
    if not isinstance(public_key_raw, bytes) or len(public_key_raw) != 32:
        raise InvalidEvidence("trusted Ed25519 public key invalid")
    # Domain separation prevents accidental interchange with other pin formats.
    return hashlib.sha256(b"NotarAI:SEC-11:Ed25519\x00" + public_key_raw).hexdigest()


def sign_manifest(manifest: dict, private_key: ed25519.Ed25519PrivateKey) -> dict:
    """Use only by the independent custodian; never store this key in NotarAI."""
    if not isinstance(private_key, ed25519.Ed25519PrivateKey):
        raise InvalidEvidence("independent signing key required")
    signed = canonical_manifest(manifest)
    return {
        "manifest": manifest,
        "signature_b64": base64.b64encode(private_key.sign(signed)).decode("ascii"),
    }


@dataclass(frozen=True)
class Verification:
    integrity_status: str  # PASS / FAIL / EXPIRED
    assurance_status: str  # BLOCKED until independent AWS/WORM evidence
    manifest_sha256: str | None
    check_status: dict[str, str]  # effective, independently confirmed only
    asserted_check_status: dict[str, str] = field(default_factory=dict)
    check_provenance: dict[str, str] = field(default_factory=dict)
    zero_operator_access_proven: bool = False

    def as_dict(self) -> dict:
        return {
            "integrity_status": self.integrity_status,
            "assurance_status": self.assurance_status,
            "manifest_sha256": self.manifest_sha256,
            "check_status": self.check_status,
            "asserted_check_status": self.asserted_check_status,
            "check_provenance": self.check_provenance,
            "zero_operator_access_proven": False,
        }


def verify_bundle(*, bundle: object, trusted_public_key_raw: bytes,
                  pinned_fingerprint: str, clock: datetime | None = None,
                  expected_previous_sha256: str | None = None,
                  trusted_head_sha256: str | None = None) -> Verification:
    """No network, no embedded trust root, no implicit trust in mock hardware.

    expected_previous_sha256 anchors link to independently held prior hash;
    trusted_head_sha256 prevents truncation/rollback of the chain head.
    Without both independent storage proof and physical checks, ZOA stays false.
    """
    try:
        if not _hex(pinned_fingerprint) or (
            public_fingerprint(trusted_public_key_raw) != pinned_fingerprint
        ):
            raise InvalidEvidence("trusted key fingerprint mismatch")
        if not isinstance(bundle, dict) or set(bundle) != PACKAGE_FIELDS:
            raise InvalidEvidence("signed package fields invalid")
        manifest = bundle["manifest"]
        signed = canonical_manifest(manifest)
        digest = hashlib.sha256(signed).hexdigest()
        sig = bundle["signature_b64"]
        if not isinstance(sig, str) or len(sig) > 128:
            raise InvalidEvidence("signature invalid")
        try:
            signature = base64.b64decode(sig, validate=True)
        except (binascii.Error, ValueError):
            raise InvalidEvidence("signature invalid") from None
        if len(signature) != 64:
            raise InvalidEvidence("signature invalid")
        ed25519.Ed25519PublicKey.from_public_bytes(
            trusted_public_key_raw
        ).verify(signature, signed)
        if expected_previous_sha256 is not None and (
            not _hex(expected_previous_sha256) or
            manifest["previous_sha256"] != expected_previous_sha256
        ):
            raise InvalidEvidence("evidence predecessor mismatch")
        if trusted_head_sha256 is not None and (
            not _hex(trusted_head_sha256) or digest != trusted_head_sha256
        ):
            raise InvalidEvidence("evidence head mismatch")
        now = clock or datetime.now(timezone.utc)
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise InvalidEvidence("UTC clock required")
        now = now.astimezone(timezone.utc)
        if now < _utc(manifest["observed_at"]):
            raise InvalidEvidence("evidence issued in the future")
        asserted = {name: record["status"] for name, record
                    in manifest["checks"].items()}
        provenance = {name: record["provenance"] for name, record
                      in manifest["checks"].items()}
        # A signed PASS is still just an assertion, not validated hardware.
        # Never display it as a verified PASS in the customer report.
        effective = {name: ("BLOCKED" if status == "PASS" else status)
                     for name, status in asserted.items()}
        if now >= _utc(manifest["expires_at"]):
            return Verification("EXPIRED", "BLOCKED", digest,
                                effective, asserted, provenance)
        return Verification("PASS", "BLOCKED", digest,
                            effective, asserted, provenance)
    except (InvalidSignature, InvalidEvidence, TypeError, ValueError, KeyError,
            AttributeError, UnicodeError):
        return Verification("FAIL", "BLOCKED", None, {})


def verify_chain(*, bundles: list[dict], trusted_public_key_raw: bytes,
                 pinned_fingerprint: str, trusted_head_sha256: str,
                 clock: datetime | None = None) -> Verification:
    """Reject reorder, gap, missing genesis, wrong link and truncated head."""
    if not bundles or not _hex(trusted_head_sha256):
        return Verification("FAIL", "BLOCKED", None, {})
    previous = None
    for position, bundle in enumerate(bundles, start=1):
        manifest = bundle.get("manifest") if isinstance(bundle, dict) else None
        if not isinstance(manifest, dict) or manifest.get("sequence") != position:
            return Verification("FAIL", "BLOCKED", None, {})
        result = verify_bundle(
            bundle=bundle, trusted_public_key_raw=trusted_public_key_raw,
            pinned_fingerprint=pinned_fingerprint, clock=clock,
            expected_previous_sha256=previous if position > 1 else None,
            trusted_head_sha256=trusted_head_sha256 if position == len(bundles) else None,
        )
        if result.integrity_status != "PASS":
            return result
        if position == 1 and manifest["previous_sha256"] is not None:
            return Verification("FAIL", "BLOCKED", None, {})
        previous = result.manifest_sha256
    return result
