"""Customer-only key release: authentic Nitro attestation BEFORE RSA DEK rewrap.

No operator-selected recipient key, PCR policy, or simulated attestation is
accepted by this entrypoint. Actual guest execution is a separate deployment
and evidence gate: this adapter alone is not a Zero Operator Access proof.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Mapping

from confidential.customer_release import (
    ReleaseDenied, envelope_sha256, issue_job_release, parse_envelope,
)
from confidential.customer_nitro_attestation import (
    VerifiedNitroRecipient, verify_aws_nitro_attestation,
)


def challenge_user_data(envelope: Mapping, *, job_id: str, nonce: bytes) -> bytes:
    """SHA-256 of exact document, job and fresh client-generated nonce.

    This digest MUST be passed as NSM user_data by the attested guest.
    It is not a substitute for validating the signature, nonce or PCRs.
    """
    from confidential.customer_release import _ID
    if (not isinstance(job_id, str) or not _ID.fullmatch(job_id)
            or type(nonce) is not bytes or not 32 <= len(nonce) <= 512):
        raise ReleaseDenied("customer release denied")
    ctx = {
        "schema": "notarai.customer-challenge.v1",
        "envelope_sha256": envelope_sha256(parse_envelope(envelope)),
        "job_id": job_id,
        "nonce_sha256": hashlib.sha256(nonce).hexdigest(),
    }
    raw = json.dumps(ctx, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=True).encode("ascii")
    return hashlib.sha256(b"notarai:nitro-customer-challenge:v1\0" + raw).digest()


def issue_attested_job_release(
    envelope: Mapping,
    owner_private_pem: bytes,
    attestation_document: bytes,
    *,
    expected_nonce: bytes,
    expected_pcrs: dict[int, str],
    job_id: str,
    now: datetime | None = None,
    validity_seconds: int = 300,
) -> tuple[dict, VerifiedNitroRecipient]:
    """Release a DEK only to the RSA SPKI embedded in genuine Nitro NSM COSE.

    The customer controls the owner private key, nonce, trusted PCR manifest
    and execution of this code. The operator sees only the encrypted grant.
    """
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ReleaseDenied("customer release denied")
    if type(validity_seconds) is not int or not 1 <= validity_seconds <= 900:
        raise ReleaseDenied("customer release denied")
    user_data = challenge_user_data(envelope, job_id=job_id, nonce=expected_nonce)
    verified = verify_aws_nitro_attestation(
        attestation_document,
        expected_nonce=expected_nonce,
        expected_user_data=user_data,
        expected_pcrs=expected_pcrs,
        now=instant,
    )
    issued_at = int(instant.timestamp())
    grant = issue_job_release(
        envelope, owner_private_pem, verified.public_key_pem,
        job_id=job_id, issued_at=issued_at,
        expires_at=issued_at + validity_seconds,
    )
    return grant, verified
