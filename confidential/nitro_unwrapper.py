"""Runtime KMS key release for a hardware-attested Nitro ECS sandbox.

Only usable in a Nitro guest with /dev/nsm. No unprotected fallback.
This is a real adapter using AWS NSM attestation and KMS Recipient CMS.
"""
from __future__ import annotations

import os

from confidential.attested_kms import AttestationRequired


class NitroKMSUnwrapper:
    def __init__(self, kms_client, allowed_key_arn: str):
        if not allowed_key_arn.startswith("arn:aws:kms:eu-"):
            raise ValueError("KMS key must be in an EU region")
        self.kms = kms_client
        self.key_arn = allowed_key_arn

    def unwrap(self, wrapped_dek: bytes, key_arn: str) -> bytes:
        if key_arn != self.key_arn:
            raise AttestationRequired("wrong KMS key")
        if not os.path.exists("/dev/nsm"):
            raise AttestationRequired("Nitro Secure Module is required")
        # Local import: the live guest installs optional dependencies
        # from confidential/requirements.txt; the normal app never needs them.
        from confidential.nsm_recipient import AttestedRecipient

        with AttestedRecipient() as recipient:
            response = self.kms.decrypt(
                KeyId=key_arn,
                CiphertextBlob=wrapped_dek,
                EncryptionAlgorithm="RSAES_OAEP_SHA_256",
                Recipient=recipient.kms_recipient,
            )
            if response.get("Plaintext") is not None:
                raise AttestationRequired("KMS returned unprotected plaintext")
            if response.get("KeyId") != key_arn:
                raise AttestationRequired("KMS key mismatch")
            cfr = response.get("CiphertextForRecipient")
            if not isinstance(cfr, bytes) or not cfr:
                raise AttestationRequired("no KMS attested CMS")
            dek = recipient.unwrap(cfr)
            if not isinstance(dek, bytes) or len(dek) != 32:
                raise AttestationRequired("invalid key length")
            return dek
