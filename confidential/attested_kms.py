"""KMS key release boundary. No normal/plaintext Decrypt fallback.

AttestationProvider MUST create a fresh Nitro NSM attestation document with
an ephemeral RSA public key and decrypt the CMS response inside the guest.
This module deliberately does not implement or emulate NSM hardware.
"""
from __future__ import annotations

from typing import Protocol


class AttestationProvider(Protocol):
    def signed_document(self) -> bytes:
        """Attestation carrying an ephemeral public key generated in Nitro guest."""
        ...

    def unwrap_recipient_cms(self, cms_der: bytes) -> bytes:
        """Open KMS CiphertextForRecipient inside the Nitro guest."""
        ...


class AttestationRequired(RuntimeError):
    pass


class AttestedKMSUnwrapper:
    def __init__(self, kms_client, provider: AttestationProvider, allowed_key_arn: str):
        if not allowed_key_arn.startswith("arn:aws:kms:eu-"):
            raise ValueError("KMS key must reside in an EU region")
        self._kms = kms_client
        self._provider = provider
        self._key = allowed_key_arn

    def unwrap(self, wrapped_dek: bytes, key_arn: str) -> bytes:
        if key_arn != self._key:
            raise AttestationRequired("KMS key is not approved for this task")
        doc = self._provider.signed_document()
        if not isinstance(doc, bytes) or not doc:
            raise AttestationRequired("missing Nitro attestation")
        response = self._kms.decrypt(
            KeyId=self._key,
            CiphertextBlob=wrapped_dek,
            EncryptionAlgorithm="RSAES_OAEP_SHA_256",
            Recipient={
                "KeyEncryptionAlgorithm": "RSAES_OAEP_SHA_256",
                "AttestationDocument": doc,
            },
        )
        if response.get("Plaintext"):
            raise AttestationRequired("unexpected plaintext KMS response")
        cipher_for_guest = response.get("CiphertextForRecipient")
        if not cipher_for_guest:
            raise AttestationRequired("KMS did not return attested ciphertext")
        return self._provider.unwrap_recipient_cms(cipher_for_guest)
