"""Independent origin authentication for already uploaded ciphertext.

AES-GCM + public RSA encryption alone does NOT authenticate document origin:
an operator with the public RSA key could encrypt a different payload under
a new DEK. Only a receipt SIGNED by an independently identified notary or
a trusted external issuer binds the exact ciphertext and S3 version.
Receipt issuance/enrollment is an external dependency; this module is a
strict verifier, not a means to manufacture trust.
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

_DOMAIN = b"notarai:custodian-document-origin:v1\x00"
_KEYS = frozenset({
    "schema", "tenant_id", "case_id", "object_id", "document_version",
    "s3_version", "ciphertext_sha256", "kms_key_arn", "key_pin",
    "issuer_id", "expires_at",
})
_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
_TENANT = re.compile(r"^[a-z0-9]{1,12}$")
_LOGICAL = re.compile(r"^[a-f0-9]{32}$")
_SHA = re.compile(r"^[a-f0-9]{64}$")
_S3 = re.compile(r"^[A-Za-z0-9._~+/=-]{1,1024}$")
_KMS = re.compile(r"^arn:aws:kms:eu-central-1:[0-9]{12}:key/[A-Za-z0-9-]+$")
_PIN = re.compile(r"^[A-Za-z0-9+/]{43}=$")


class UntrustedDocumentOrigin(ValueError):
    pass


def canonical_origin_receipt(receipt: Mapping) -> bytes:
    if not isinstance(receipt, Mapping) or set(receipt) != _KEYS:
        raise UntrustedDocumentOrigin("invalid document origin receipt")
    if (receipt.get("schema") != "notarai.document-origin.v1"
            or not isinstance(receipt.get("tenant_id"), str)
            or not _TENANT.fullmatch(receipt["tenant_id"])
            or any(not isinstance(receipt.get(k), str) or not _ID.fullmatch(receipt[k])
                   for k in ("case_id", "object_id", "issuer_id"))
            or not isinstance(receipt.get("document_version"), str)
            or not _LOGICAL.fullmatch(receipt["document_version"])
            or not isinstance(receipt.get("s3_version"), str)
            or not _S3.fullmatch(receipt["s3_version"])
            or receipt["s3_version"] == "null"
            or not isinstance(receipt.get("ciphertext_sha256"), str)
            or not _SHA.fullmatch(receipt["ciphertext_sha256"])
            or not isinstance(receipt.get("kms_key_arn"), str)
            or not _KMS.fullmatch(receipt["kms_key_arn"])
            or not isinstance(receipt.get("key_pin"), str)
            or not _PIN.fullmatch(receipt["key_pin"])
            or type(receipt.get("expires_at")) is not int
            or not 0 < receipt["expires_at"] < 4102444800):
        raise UntrustedDocumentOrigin("invalid document origin receipt")
    return _DOMAIN + json.dumps(receipt, sort_keys=True,
                                separators=(",", ":"), ensure_ascii=True,
                                allow_nan=False).encode("ascii")


def verify_document_origin(
    *, receipt: Mapping, signature: bytes, independent_issuer_public_key: bytes,
    expected_tenant: str, expected_case: str, expected_object: str,
    expected_document_version: str, expected_s3_version: str,
    expected_ciphertext_sha256: str, expected_key_arn: str,
    expected_key_pin: str, expected_issuer_id: str, now: int,
) -> None:
    data = canonical_origin_receipt(receipt)
    expected = {
        "tenant_id": expected_tenant, "case_id": expected_case,
        "object_id": expected_object,
        "document_version": expected_document_version,
        "s3_version": expected_s3_version,
        "ciphertext_sha256": expected_ciphertext_sha256,
        "kms_key_arn": expected_key_arn, "key_pin": expected_key_pin,
        "issuer_id": expected_issuer_id,
    }
    if (type(now) is not int or now >= receipt["expires_at"]
            or any(receipt[key] != value for key, value in expected.items())
            or not isinstance(signature, bytes) or len(signature) != 64
            or not isinstance(independent_issuer_public_key, bytes)
            or len(independent_issuer_public_key) != 32):
        raise UntrustedDocumentOrigin("invalid independently signed document origin")
    try:
        Ed25519PublicKey.from_public_bytes(independent_issuer_public_key).verify(
            signature, data
        )
    except (ValueError, InvalidSignature):
        raise UntrustedDocumentOrigin("invalid independently signed document origin") from None
