"""Offline admission guard for an independently approved key recovery/rotation.

Does NOT rewrap keys, perform KMS Decrypt or bypass Nitro. The real operation
must execute inside an attested enclave after independent key-release approval.
Approvers are two externally controlled signers (custodian + recovery trustee),
NEVER a NotarAI operator, support account or web session.
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

_FIELDS = frozenset({
    "schema", "action", "tenant_id", "case_id", "object_id",
    "document_version", "old_key_arn", "new_key_arn",
    "new_key_sha256", "request_id", "expires_at",
})
_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
_VERSION = re.compile(r"^[a-f0-9]{32}$")
_KMS = re.compile(r"^arn:aws:kms:eu-central-1:[0-9]{12}:key/[A-Za-z0-9-]+$")
_PIN = re.compile(r"^[A-Za-z0-9+/]{43}=$")
_DOMAIN = b"notarai:external-recovery-approval:v1\x00"


class RecoveryDenied(ValueError):
    """Generic failure; never disclose sensitive request or signer material."""


def canonical_recovery_request(request: Mapping) -> bytes:
    if not isinstance(request, Mapping) or set(request) != _FIELDS:
        raise RecoveryDenied("invalid recovery request")
    if (request.get("schema") != "notarai.recovery.v1"
            or request.get("action") not in ("rotate", "revoke")
            or any(not isinstance(request.get(key), str) or
                   not _ID.fullmatch(request[key])
                   for key in ("tenant_id", "case_id", "object_id"))
            or any(not isinstance(request.get(key), str) or
                   not _VERSION.fullmatch(request[key])
                   for key in ("document_version", "request_id"))
            or not isinstance(request.get("old_key_arn"), str)
            or not _KMS.fullmatch(request["old_key_arn"])
            or not isinstance(request.get("new_key_arn"), str)
            or not isinstance(request.get("new_key_sha256"), str)
            or (request["action"] == "rotate"
                and (not _KMS.fullmatch(request["new_key_arn"])
                     or request["old_key_arn"] == request["new_key_arn"]
                     or not _PIN.fullmatch(request["new_key_sha256"])))
            or (request["action"] == "revoke" and (
                request["new_key_arn"] != "" or request["new_key_sha256"] != ""))
            or type(request.get("expires_at")) is not int
            or not 0 < request["expires_at"] < 4102444800):
        raise RecoveryDenied("invalid recovery request")
    return _DOMAIN + json.dumps(
        request, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode("ascii")


def authorize_recovery(
    *, request: Mapping, custodian_signature: bytes,
    trustee_signature: bytes, custodian_public_key: bytes,
    trustee_public_key: bytes, expected_tenant: str, expected_old_key: str,
    now: int,
) -> str:
    """Require BOTH independent signatures. Return action only, not a DEK.

    External caller must enforce one-time request_id and independent approval
    at the actual KMS/release boundary; this offline check is not sufficient.
    """
    data = canonical_recovery_request(request)
    if (request["tenant_id"] != expected_tenant
            or request["old_key_arn"] != expected_old_key
            or type(now) is not int or now >= request["expires_at"]
            or not all(isinstance(x, bytes) for x in (
                custodian_signature, trustee_signature,
                custodian_public_key, trustee_public_key))
            or len(custodian_signature) != 64
            or len(trustee_signature) != 64
            or len(custodian_public_key) != 32
            or len(trustee_public_key) != 32
            or custodian_public_key == trustee_public_key):
        raise RecoveryDenied("recovery not independently authorized")
    try:
        Ed25519PublicKey.from_public_bytes(custodian_public_key).verify(
            custodian_signature, data)
        Ed25519PublicKey.from_public_bytes(trustee_public_key).verify(
            trustee_signature, data)
    except (InvalidSignature, ValueError):
        raise RecoveryDenied("recovery not independently authorized") from None
    return request["action"]
