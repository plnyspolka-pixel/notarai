"""Standalone release verifier for an independently distributed client.

The verifier and pinned Ed25519 public key MUST arrive out of band, not from
the same NotarAI-controlled webpage that serves JavaScript. This module
checks signatures, hash and expiration but is NOT a deployed trust root.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

_REQUIRED = frozenset({
    "schema", "release_id", "tenant_id", "kms_key_arn",
    "public_key_sha256", "javascript_sha256", "expires_at",
})
_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_VERSION = re.compile(r"^[a-f0-9]{32}$")
_TENANT = re.compile(r"^[a-z0-9]{1,12}$")
_KMS = re.compile(r"^arn:aws:kms:eu-central-1:[0-9]{12}:key/[A-Za-z0-9-]+$")
_DOMAIN = b"notarai:independent-client-release:v1\x00"


class UntrustedClientRelease(ValueError):
    """Generic denial: never include tenant data, signature or trusted key."""


def canonical_release_bytes(manifest: Mapping) -> bytes:
    if not isinstance(manifest, Mapping) or set(manifest) != _REQUIRED:
        raise UntrustedClientRelease("invalid release manifest")
    if (
        manifest.get("schema") != "notarai.client-release.v1"
        or not isinstance(manifest.get("release_id"), str)
        or not _VERSION.fullmatch(manifest["release_id"])
        or not isinstance(manifest.get("tenant_id"), str)
        or not _TENANT.fullmatch(manifest["tenant_id"])
        or not isinstance(manifest.get("kms_key_arn"), str)
        or not _KMS.fullmatch(manifest["kms_key_arn"])
        or not isinstance(manifest.get("public_key_sha256"), str)
        or not re.fullmatch(r"[A-Za-z0-9+/]{43}=", manifest["public_key_sha256"])
        or not isinstance(manifest.get("javascript_sha256"), str)
        or not _DIGEST.fullmatch(manifest["javascript_sha256"])
        or type(manifest.get("expires_at")) is not int
        or not 0 < manifest["expires_at"] < 4102444800
    ):
        raise UntrustedClientRelease("invalid release manifest")
    return _DOMAIN + json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def verify_client_release(
    *, javascript: bytes, manifest: Mapping, signature: bytes,
    trusted_public_key: bytes, tenant_id: str, expected_kms_arn: str,
    expected_key_pin: str, now: int,
) -> str:
    """Return JS digest only after independent Ed25519 verification.

    Signature and manifest MAY be hosted by NotarAI, but the trusted public
    key + verifier executable MUST have an independently verified origin.
    """
    if (
        not isinstance(javascript, bytes) or not javascript
        or not isinstance(signature, bytes) or len(signature) != 64
        or not isinstance(trusted_public_key, bytes) or len(trusted_public_key) != 32
        or type(now) is not int
    ):
        raise UntrustedClientRelease("untrusted client release")
    raw = canonical_release_bytes(manifest)
    if (
        manifest["tenant_id"] != tenant_id
        or manifest["kms_key_arn"] != expected_kms_arn
        or manifest["public_key_sha256"] != expected_key_pin
        or now >= manifest["expires_at"]
        or hashlib.sha256(javascript).hexdigest() != manifest["javascript_sha256"]
    ):
        raise UntrustedClientRelease("untrusted client release")
    try:
        Ed25519PublicKey.from_public_bytes(trusted_public_key).verify(signature, raw)
    except (ValueError, InvalidSignature):
        raise UntrustedClientRelease("untrusted client release") from None
    return manifest["javascript_sha256"]
