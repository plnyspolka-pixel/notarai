"""Fail-closed independent document-origin gate for the Nitro guest.

A released guest contains an immutable trust-root file at a fixed image path;
its provenance must be checked as part of independently approved PCR/image
measurement. No environment variable, web session or operator API can replace
the trusted issuer key at runtime. The guest refuses to unwrap a DEK until
the separately signed origin receipt matches exact ciphertext and S3 version.
"""
from __future__ import annotations

import base64
import json
import re
import time
from pathlib import Path

from confidential.document_authenticity import verify_document_origin
from confidential.job_ledger import validate_version_id

_ROOT_PATH = Path(__file__).resolve().with_name("trusted-origin-root.json")
_ROOT_KEYS = frozenset({
    "schema", "tenant_id", "issuer_id", "issuer_public_key_b64",
    "kms_key_arn", "public_key_sha256", "expires_at",
})
_BUNDLE_KEYS = frozenset({"schema", "receipt", "signature_b64"})
_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
_TENANT = re.compile(r"^[a-z0-9]{1,12}$")
_KMS = re.compile(r"^arn:aws:kms:eu-central-1:[0-9]{12}:key/[A-Za-z0-9-]+$")
_PIN = re.compile(r"^[A-Za-z0-9+/]{43}=$")
_MAX_ROOT_BYTES = 2048
_MAX_RECEIPT_BYTES = 8192


class OriginAdmissionDenied(ValueError):
    """All failures must be generic; never print raw receipts or account IDs."""


def _no_duplicate_keys(pairs):
    data = {}
    for key, value in pairs:
        if key in data:
            raise OriginAdmissionDenied("duplicate document origin field")
        data[key] = value
    return data


def _strict_json(blob: bytes):
    try:
        return json.loads(blob.decode("ascii"), object_pairs_hook=_no_duplicate_keys)
    except (UnicodeError, ValueError, TypeError):
        raise OriginAdmissionDenied("invalid origin JSON") from None


def _decode_b64(value: object, expected_len: int) -> bytes:
    try:
        if not isinstance(value, str):
            raise ValueError("not a string")
        result = base64.b64decode(value, validate=True)
        if len(result) != expected_len:
            raise ValueError("wrong size")
        return result
    except (ValueError, TypeError):
        raise OriginAdmissionDenied("invalid origin signature or key") from None


def load_trusted_origin_root(*, tenant: str, key_arn: str,
                             now: int | None = None) -> dict:
    """No environment override. Missing embedded root means no decryption."""
    if not _TENANT.fullmatch(tenant) or not _KMS.fullmatch(key_arn):
        raise OriginAdmissionDenied("invalid trust root scope")
    now = int(time.time()) if now is None else now
    if type(now) is not int:
        raise OriginAdmissionDenied("invalid verification clock")
    try:
        with _ROOT_PATH.open("rb") as stream:
            blob = stream.read(_MAX_ROOT_BYTES + 1)
    except OSError:
        raise OriginAdmissionDenied("independent origin root not provisioned") from None
    if len(blob) > _MAX_ROOT_BYTES:
        raise OriginAdmissionDenied("oversized origin trust root")
    root = _strict_json(blob)
    if (not isinstance(root, dict) or set(root) != _ROOT_KEYS
            or root.get("schema") != "notarai.origin-root.v1"
            or root.get("tenant_id") != tenant
            or not isinstance(root.get("issuer_id"), str)
            or not _ID.fullmatch(root["issuer_id"])
            or root.get("kms_key_arn") != key_arn
            or not isinstance(root.get("public_key_sha256"), str)
            or not _PIN.fullmatch(root["public_key_sha256"])
            or type(root.get("expires_at")) is not int
            or not now < root["expires_at"] < 4102444800):
        raise OriginAdmissionDenied("untrusted origin root identity")
    root["issuer_public_key"] = _decode_b64(root["issuer_public_key_b64"], 32)
    return root


def require_origin_receipt(s3, *, bucket: str, tenant: str, case_id: str,
                           object_id: str, s3_version: str,
                           ciphertext_sha256: str, document_version: str,
                           key_arn: str, public_key_sha256: str,
                           now: int | None = None) -> None:
    """Check signature and exact source object before DEK reaches memory.

    The receipt is an untrusted S3 object: the signer key is supplied ONLY by
    the image-bundled custody root, not this receipt, task environment or S3.
    """
    root = load_trusted_origin_root(tenant=tenant, key_arn=key_arn, now=now)
    if root["public_key_sha256"] != public_key_sha256:
        raise OriginAdmissionDenied("public key pin drift")
    if not all(isinstance(v, str) and _ID.fullmatch(v)
               for v in (case_id, object_id)):
        raise OriginAdmissionDenied("untrusted object identity")
    validate_version_id(s3_version)
    key = (f"kancelarie/{tenant}/confidential/"
           f"{case_id}/{object_id}.origin.json")
    try:
        object_response = s3.get_object(Bucket=bucket, Key=key)
        with object_response["Body"] as body:
            blob = body.read(_MAX_RECEIPT_BYTES + 1)
    except Exception:
        raise OriginAdmissionDenied("independent origin receipt unavailable") from None
    if len(blob) > _MAX_RECEIPT_BYTES:
        raise OriginAdmissionDenied("oversized origin receipt")
    bundle = _strict_json(blob)
    if (not isinstance(bundle, dict) or set(bundle) != _BUNDLE_KEYS
            or bundle.get("schema") != "notarai.signed-origin-receipt.v1"):
        raise OriginAdmissionDenied("untrusted origin receipt envelope")
    signature = _decode_b64(bundle["signature_b64"], 64)
    try:
        verify_document_origin(
            receipt=bundle["receipt"], signature=signature,
            independent_issuer_public_key=root["issuer_public_key"],
            expected_tenant=tenant, expected_case=case_id,
            expected_object=object_id,
            expected_document_version=document_version,
            expected_s3_version=s3_version,
            expected_ciphertext_sha256=ciphertext_sha256,
            expected_key_arn=key_arn, expected_key_pin=public_key_sha256,
            expected_issuer_id=root["issuer_id"],
            now=int(time.time()) if now is None else now,
        )
    except Exception:
        raise OriginAdmissionDenied("origin receipt verification rejected") from None
