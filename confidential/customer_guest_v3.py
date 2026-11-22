"""Single-job Nitro-side RSA recipient for the customer-owned release protocol.

The guest must run inside independently approved, measured Nitro hardware.
This is a primitive, not an SQS dispatcher nor a production rollout.
"""
from __future__ import annotations

import os

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from confidential.customer_release import (
    ReleaseDenied, envelope_sha256, open_preview_in_guest, parse_envelope,
)
from confidential.customer_attested_release import challenge_user_data


class CustomerGuestSession:
    """One NSM challenge and at most one preview. Restart for another job."""

    def __init__(self) -> None:
        if not os.path.exists("/dev/nsm"):
            raise ReleaseDenied("Nitro device required")
        self._private = rsa.generate_private_key(
            public_exponent=65537, key_size=3072)
        self._expected_job: str | None = None
        self._envelope_hash: str | None = None
        self._attempted = False
        self._attested = False

    def attest(self, envelope: dict, *, job_id: str, nonce: bytes) -> bytes:
        if self._attested or self._attempted:
            raise ReleaseDenied("guest session already initialized")
        # Enforce exact job/document binding at NSM attestation generation.
        env = parse_envelope(envelope)
        context = challenge_user_data(env, job_id=job_id, nonce=nonce)
        public_der = self._private.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        from confidential.nsm_recipient import _request_attestation
        document = _request_attestation(public_der, nonce=nonce, user_data=context)
        if type(document) is not bytes or not document:
            raise ReleaseDenied("NSM attestation unavailable")
        self._expected_job = job_id
        self._envelope_hash = envelope_sha256(env)
        self._attested = True
        return document

    def open_preview_once(
        self, envelope: dict, grant: dict, *,
        expected_tenant: str, expected_case: str, expected_object: str,
        expected_job: str, origin_receipt: dict, origin_signature: bytes,
        pinned_notary_signing_public_raw: bytes,
        expected_issuer_id: str, expected_s3_version: str, now: int,
    ) -> bytes:
        if (not self._attested or self._attempted
                or self._expected_job != expected_job
                or self._envelope_hash != envelope_sha256(envelope)):
            raise ReleaseDenied("guest session not authorized")
        # Consume the single-use capability BEFORE attempting any decryption,
        # including if origin/signature verification fails.
        self._attempted = True
        key = self._private
        self._private = None
        try:
            guest_pem = key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
            return open_preview_in_guest(
                envelope, grant, guest_pem,
                expected_tenant=expected_tenant,
                expected_case=expected_case,
                expected_object=expected_object,
                expected_job=expected_job,
                origin_receipt=origin_receipt,
                origin_signature=origin_signature,
                pinned_notary_signing_public_raw=pinned_notary_signing_public_raw,
                expected_issuer_id=expected_issuer_id,
                expected_s3_version=expected_s3_version,
                now=now,
            )
        finally:
            # Python cannot guarantee erasure of key copies in memory.
            # The whole measured guest MUST terminate after this call.
            del key
