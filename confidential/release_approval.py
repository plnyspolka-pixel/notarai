"""Independent custodian-signed release authorization (ECDSA P-256/SHA-256).

A release is not trusted merely because GitHub CI succeeds or an AWS account
administrator publishes a PCR. An independent custodian must sign the exact
tenant, task revision, image digest, key policy hash and PCR17, using a signing
key whose *public fingerprint* is pinned outside the NotarAI operator's control.

The signature proves custody authorization of the release, NOT the physical
Nitro hardware state or absence of leaks. No private keys or customer data.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from collections.abc import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from confidential.operator_boundary import BoundaryDenied

_SCHEMA = "notarai.confidential.custody-release.v1"
_DOMAIN = b"NotarAI:confidential:custody-release:v1\x00"
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_FIELDS = frozenset({
    "schema", "tenant", "operator_account", "custody_account",
    "kms_key_arn", "task_definition_arn", "expected_pcr17", "image_sha256",
    "key_policy_sha256", "task_definition_sha256", "release_id",
    "issued_at", "expires_at",
})
_BINDING = frozenset({
    "tenant", "operator_account", "custody_account",
    "kms_key_arn", "task_definition_arn", "expected_pcr17", "image_sha256",
    "key_policy_sha256", "task_definition_sha256",
})


def canonical_bytes(payload: Mapping) -> bytes:
    if not isinstance(payload, dict) or set(payload) != _FIELDS:
        raise BoundaryDenied("custodian release fields invalid")
    if payload.get("schema") != _SCHEMA:
        raise BoundaryDenied("custodian release schema invalid")
    try:
        return _DOMAIN + json.dumps(
            payload, sort_keys=True, ensure_ascii=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise BoundaryDenied("custodian release not serializable") from None


def _parse_utc(value: object) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value
    ):
        raise BoundaryDenied("custodian release UTC time invalid")
    try:
        instant = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        raise BoundaryDenied("custodian release timestamp invalid") from None
    return instant


def _utc_string(t: datetime) -> str:
    if not isinstance(t, datetime) or t.tzinfo is None:
        raise BoundaryDenied("UTC clock required")
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_release_payload(config: Mapping, *, clock: datetime | None = None,
                         release_id: str | None = None,
                         lifetime_hours: int = 24) -> dict:
    if config.get("static_configuration_verified") is not True:
        raise BoundaryDenied("cross-account configuration not verified")
    if type(lifetime_hours) is not int or not (1 <= lifetime_hours <= 48):
        raise BoundaryDenied("custodian release lifetime too long")
    now = clock or datetime.now(timezone.utc)
    rid = release_id or uuid.uuid4().hex
    if not isinstance(rid, str) or not re.fullmatch(r"[a-f0-9]{32}", rid):
        raise BoundaryDenied("custodian release ID invalid")
    payload = {name: config[name] for name in _BINDING}
    payload.update({
        "schema": _SCHEMA,
        "release_id": rid,
        "issued_at": _utc_string(now),
        "expires_at": _utc_string(now + timedelta(hours=lifetime_hours)),
    })
    canonical_bytes(payload)
    return payload


def public_key_fingerprint(pem: bytes) -> str:
    try:
        public_candidate = serialization.load_pem_public_key(pem)
    except (ValueError, TypeError):
        raise BoundaryDenied("external public key invalid") from None
    if not isinstance(public_candidate, ec.EllipticCurvePublicKey) or not isinstance(
        public_candidate.curve, ec.SECP256R1
    ):
        raise BoundaryDenied("external key must be ECDSA P-256")
    der = public_candidate.public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return hashlib.sha256(der).hexdigest()


def verify_release(
    *, envelope: Mapping, config: Mapping, trusted_public_key_pem: bytes,
    pinned_public_key_sha256: str, clock: datetime | None = None,
) -> dict:
    if config.get("static_configuration_verified") is not True:
        raise BoundaryDenied("external custody configuration has not passed audit")
    if (not isinstance(pinned_public_key_sha256, str) or
            _SHA256.fullmatch(pinned_public_key_sha256) is None):
        raise BoundaryDenied("custodian trusted fingerprint missing")
    if not isinstance(envelope, dict) or set(envelope) != {
        "payload", "signature_b64",
    }:
        raise BoundaryDenied("signed release envelope invalid")
    payload = envelope["payload"]
    signed = canonical_bytes(payload)
    for field in _BINDING:
        if payload[field] != config.get(field):
            raise BoundaryDenied("custodian release does not match live configuration")
    issued, expires = _parse_utc(payload["issued_at"]), _parse_utc(payload["expires_at"])
    now = clock or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise BoundaryDenied("UTC clock required")
    now = now.astimezone(timezone.utc)
    if (not isinstance(payload["release_id"], str) or
            re.fullmatch(r"[a-f0-9]{32}", payload["release_id"]) is None or
            issued > now or now >= expires or
            expires - issued > timedelta(hours=48) or
            expires <= issued):
        raise BoundaryDenied("custodian release expired or not yet active")
    try:
        fingerprint = public_key_fingerprint(trusted_public_key_pem)
    except (ValueError, TypeError):
        raise BoundaryDenied("invalid independent public key") from None
    if fingerprint != pinned_public_key_sha256:
        raise BoundaryDenied("custodian public key differs from independently pinned trust root")
    signature_text = envelope.get("signature_b64")
    if not isinstance(signature_text, str):
        raise BoundaryDenied("custodian signature missing")
    try:
        signature = base64.b64decode(signature_text, validate=True)
    except (ValueError, binascii.Error):
        raise BoundaryDenied("custodian signature encoding invalid") from None
    if not signature:
        raise BoundaryDenied("custodian signature empty")
    approved_public = serialization.load_pem_public_key(trusted_public_key_pem)
    try:
        approved_public.verify(signature, signed, ec.ECDSA(hashes.SHA256()))
    except (InvalidSignature, TypeError, ValueError):
        raise BoundaryDenied("independent custodian release signature invalid") from None
    return {
        "schema": "notarai.confidential.custody-signoff.v1",
        "tenant": config["tenant"],
        "operator_account": config["operator_account"],
        "custody_account": config["custody_account"],
        "kms_key_arn": config["kms_key_arn"],
        "task_definition_arn": config["task_definition_arn"],
        "expected_pcr17": config["expected_pcr17"],
        "image_sha256": config["image_sha256"],
        "key_policy_sha256": config["key_policy_sha256"],
        "task_definition_sha256": config["task_definition_sha256"],
        "release_id": payload["release_id"],
        "release_expires_at": payload["expires_at"],
        "custody_public_key_sha256": fingerprint,
        "static_configuration_verified": True,
        "independent_release_signature_verified": True,
        "hardware_nitro_attestation_verified": False,
        "zero_operator_access_proven": False,
    }
