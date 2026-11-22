"""SEC-07: dual independent signatures over the exact synthetic denial matrix.

Signatures are additional provenance controls; neither a cryptographic
signature nor successful CI proves real AWS hardware execution, custody
independence, or the absence of a control-plane bypass.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from collections.abc import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from confidential.nitro_denial_matrix import (
    CASES, KMS_CASES, DenialEvidenceRejected, utc, validate_matrix,
)
from confidential.release_approval import public_key_fingerprint

_SCHEMA = "notarai.confidential.nitro-denial-witness.v1"
_DOMAIN = b"NotarAI:SEC-07:independent-witness:v1\x00"
_SHA = re.compile(r"[a-f0-9]{64}\Z")


def canonical_witness(payload: Mapping) -> bytes:
    if not isinstance(payload, dict):
        raise DenialEvidenceRejected("witness payload must be an object")
    return _DOMAIN + json.dumps(payload, sort_keys=True,
                                separators=(",", ":"), ensure_ascii=True,
                                allow_nan=False).encode("utf-8")


def _matrix_hash(matrix: Mapping) -> str:
    return hashlib.sha256(json.dumps(
        matrix, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode("utf-8")).hexdigest()


def validate_witness_payload(payload: Mapping, matrix: Mapping,
                             *, now: datetime | None = None) -> bytes:
    """Bind both external signatures to one exact trial configuration."""
    validate_matrix(matrix, now=now)
    if not isinstance(payload, dict) or set(payload) != {
        "schema", "tenant", "job_id", "matrix_sha256", "observed_at",
        "expires_at", "denied_event_ids", "trial_receipt_sha256",
        "result", "submitted", "signed",
    }:
        raise DenialEvidenceRejected("witness fields invalid")
    if (payload["schema"] != _SCHEMA or
            payload["tenant"] != matrix["tenant"] or
            payload["job_id"] != matrix["job_id"] or
            payload["matrix_sha256"] != _matrix_hash(matrix) or
            payload["result"] != "SIX_DENIALS_WITNESSED" or
            payload["submitted"] is not False or
            payload["signed"] is not False):
        raise DenialEvidenceRejected("witness trial scope or result incorrect")
    receipt_hashes = payload["trial_receipt_sha256"]
    event_ids = payload["denied_event_ids"]
    if (not isinstance(receipt_hashes, dict) or
            set(receipt_hashes) != set(CASES) or
            any(receipt_hashes[name] !=
                matrix["trials"][name]["receipt_sha256"] for name in CASES) or
            not isinstance(event_ids, dict) or
            set(event_ids) != set(KMS_CASES) or
            any(event_ids[name] != matrix["trials"][name]["event_id"]
                for name in KMS_CASES)):
        raise DenialEvidenceRejected("witness event or receipt binding mismatch")
    observed = utc(payload["observed_at"])
    expires = utc(payload["expires_at"])
    current = now or datetime.now(timezone.utc)
    if (current.tzinfo is None or
            not utc(matrix["started_at"]) <= observed or
            observed < utc(matrix["ended_at"]) or
            observed > current or
            not observed < expires or
            expires - observed > timedelta(hours=24) or
            current >= expires):
        raise DenialEvidenceRejected("witness proof expired or outside run window")
    return canonical_witness(payload)


def _verify_signature(*, signature_b64: object, pem: bytes,
                      pin: str, signed: bytes) -> str:
    if not isinstance(pin, str) or _SHA.fullmatch(pin) is None:
        raise DenialEvidenceRejected("out-of-band witness public key pin invalid")
    try:
        fingerprint = public_key_fingerprint(pem)
        if fingerprint != pin:
            raise DenialEvidenceRejected("witness trust root mismatch")
        key = serialization.load_pem_public_key(pem)
        if (not isinstance(key, ec.EllipticCurvePublicKey) or
                not isinstance(key.curve, ec.SECP256R1)):
            raise DenialEvidenceRejected("witness key not P-256")
        if not isinstance(signature_b64, str):
            raise DenialEvidenceRejected("witness signature missing")
        signature = base64.b64decode(signature_b64, validate=True)
        if not signature:
            raise DenialEvidenceRejected("empty witness signature")
        key.verify(signature, signed, ec.ECDSA(hashes.SHA256()))
        return fingerprint
    except (InvalidSignature, ValueError, TypeError, binascii.Error):
        raise DenialEvidenceRejected("witness signature or key invalid") from None


def verify_independent_witnesses(
    *, payload: dict, matrix: dict, custodian_signature_b64: str,
    custodian_public_key_pem: bytes, custodian_public_key_sha256: str,
    auditor_signature_b64: str, auditor_public_key_pem: bytes,
    auditor_public_key_sha256: str, now: datetime | None = None,
) -> dict:
    """Require TWO independently pinned, distinct keys for identical bytes."""
    data = validate_witness_payload(payload, matrix, now=now)
    if (custodian_public_key_sha256 == auditor_public_key_sha256 or
            custodian_public_key_pem == auditor_public_key_pem):
        raise DenialEvidenceRejected("custodian and auditor signing identities must differ")
    custodian = _verify_signature(
        signature_b64=custodian_signature_b64,
        pem=custodian_public_key_pem, pin=custodian_public_key_sha256,
        signed=data,
    )
    auditor = _verify_signature(
        signature_b64=auditor_signature_b64,
        pem=auditor_public_key_pem, pin=auditor_public_key_sha256,
        signed=data,
    )
    return {
        "witness_signatures_verified": True,
        "custodian_public_key_sha256": custodian,
        "auditor_public_key_sha256": auditor,
        "witness_sha256": hashlib.sha256(data).hexdigest(),
        "hardware_attestation_verified": False,
        "production_enabled": False,
        "status": "BLOCKED",
        "reason": "signatures_only_do_not_prove_AWS_execution_or_independence",
    }
