"""Signed document-origin receipt for customer-owned (KMS-free) v3 documents.

Reuses the existing SEC-03 notary Ed25519 signing concept. A trusted public key
must be pinned inside a separately approved/attested guest image, NEVER
loaded from the document receipt, S3 or an operator-controlled environment.
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from confidential.customer_release import ReleaseDenied, envelope_sha256, parse_envelope

_ID = re.compile(r"[A-Za-z0-9_-]{1,80}\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_S3 = re.compile(r"[A-Za-z0-9._~+/=-]{1,1024}\Z")
_FIELDS = frozenset({
    "schema", "tenant_id", "case_id", "object_id", "document_version",
    "envelope_sha256", "s3_version", "owner_spki_sha256", "issuer_id",
    "operation", "expires_at",
})
_DOMAIN = b"notarai:customer-document-origin:v1\x00"


def canonical_customer_origin(receipt: Mapping) -> bytes:
    if not isinstance(receipt, Mapping) or set(receipt) != _FIELDS:
        raise ReleaseDenied("customer origin denied")
    if (receipt.get("schema") != "notarai.customer-origin.v1"
        or receipt.get("operation") != "preview-only"
        or any(not isinstance(receipt.get(k), str) or not _ID.fullmatch(receipt[k])
               for k in ("tenant_id", "case_id", "object_id", "issuer_id"))
        or not isinstance(receipt.get("document_version"), str)
        or not re.fullmatch(r"[a-f0-9]{32}", receipt["document_version"])
        or not isinstance(receipt.get("envelope_sha256"), str)
        or not _SHA.fullmatch(receipt["envelope_sha256"])
        or not isinstance(receipt.get("s3_version"), str)
        or not _S3.fullmatch(receipt["s3_version"])
        or receipt["s3_version"] == "null"
        or not isinstance(receipt.get("owner_spki_sha256"), str)
        or not re.fullmatch(r"[A-Za-z0-9+/]{43}=", receipt["owner_spki_sha256"])
        or type(receipt.get("expires_at")) is not int
        or not 0 < receipt["expires_at"] < 4102444800):
        raise ReleaseDenied("customer origin denied")
    return _DOMAIN + json.dumps(receipt, sort_keys=True, separators=(",", ":"),
                                ensure_ascii=True, allow_nan=False).encode("ascii")


def sign_customer_origin(envelope: Mapping, *, s3_version: str,
                         issuer_id: str, expires_at: int,
                         trusted_client_signing_private_pem: bytes) -> tuple[dict, bytes]:
    """Sign OUTSIDE NotarAI; separate trust anchor, same SEC-03 notary identity."""
    env = parse_envelope(envelope)
    receipt = {
        "schema": "notarai.customer-origin.v1",
        **{k: env[k] for k in ("tenant_id", "case_id", "object_id", "document_version")},
        "envelope_sha256": envelope_sha256(env), "s3_version": s3_version,
        "owner_spki_sha256": env["owner_spki_sha256"], "issuer_id": issuer_id,
        "operation": "preview-only", "expires_at": expires_at,
    }
    raw = canonical_customer_origin(receipt)
    try:
        private = serialization.load_pem_private_key(
            trusted_client_signing_private_pem, password=None)
        if not isinstance(private, Ed25519PrivateKey):
            raise ValueError("wrong key")
        return receipt, private.sign(raw)
    except (ValueError, TypeError):
        raise ReleaseDenied("customer origin denied") from None


def verify_customer_origin(envelope: Mapping, receipt: Mapping,
                           signature: bytes, *,
                           pinned_notary_signing_public_raw: bytes,
                           expected_issuer_id: str,
                           expected_s3_version: str, now: int) -> None:
    """Must be called inside guest BEFORE unwrapping any DEK.

    The caller must load the pinned public key from immutable approved guest
    build metadata. NEVER trust a key supplied by an operator-controlled API.
    """
    env = parse_envelope(envelope)
    raw = canonical_customer_origin(receipt)
    if (type(now) is not int or now >= receipt["expires_at"]
        or not isinstance(signature, bytes) or len(signature) != 64
        or not isinstance(pinned_notary_signing_public_raw, bytes)
        or len(pinned_notary_signing_public_raw) != 32
        or receipt["s3_version"] != expected_s3_version
        or receipt["issuer_id"] != expected_issuer_id
        or receipt["envelope_sha256"] != envelope_sha256(env)
        or receipt["owner_spki_sha256"] != env["owner_spki_sha256"]
        or any(receipt[k] != env[k] for k in (
            "tenant_id", "case_id", "object_id", "document_version"))):
        raise ReleaseDenied("customer origin denied")
    try:
        Ed25519PublicKey.from_public_bytes(pinned_notary_signing_public_raw).verify(
            signature, raw)
    except (InvalidSignature, ValueError):
        raise ReleaseDenied("customer origin denied") from None