"""Versioned wire envelope for client-encrypted NotarAI documents.

All plaintext processing MUST run inside a verified confidential task.
The web/API service is only permitted to store or transport this opaque JSON.
"""
from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass
from typing import Any, Mapping

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
_MAX_CIPHER_BYTES = 25 * 1024 * 1024
_DOC_VERSION = re.compile(r"^[a-f0-9]{32}$")
_FINGERPRINT = re.compile(r"^[A-Za-z0-9+/]{43}=$")


class InvalidEnvelope(ValueError):
    """Invalid or tampered input: never include client values in this error."""


def _b64(value: Any, max_bytes: int) -> bytes:
    if not isinstance(value, str) or len(value) > ((max_bytes + 2) // 3) * 4 + 4:
        raise InvalidEnvelope("invalid encoded field")
    try:
        result = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise InvalidEnvelope("invalid encoded field") from exc
    if not result or len(result) > max_bytes:
        raise InvalidEnvelope("invalid encoded field size")
    return result


@dataclass(frozen=True)
class Envelope:
    tenant_id: str
    case_id: str
    object_id: str
    kms_key_arn: str
    nonce: bytes
    wrapped_dek: bytes
    ciphertext: bytes
    version: int = 1
    document_version: str | None = None
    public_key_sha256: str | None = None

    @classmethod
    def parse(cls, payload: Mapping[str, Any]) -> "Envelope":
        if not isinstance(payload, Mapping):
            raise InvalidEnvelope("invalid envelope")
        keys = {"version", "algorithm", "tenant_id", "case_id", "object_id",
                "kms_key_arn", "nonce", "wrapped_dek", "ciphertext"}
        version = payload.get("version")
        if type(version) is not int or version not in (1, 2):
            raise InvalidEnvelope("unsupported envelope version or fields")
        expected_keys = keys if version == 1 else keys | {"document_version", "public_key_sha256"}
        if set(payload) != expected_keys:
            raise InvalidEnvelope("unsupported envelope version or fields")
        document_version = None
        fingerprint = None
        if version == 2:
            document_version = payload["document_version"]
            fingerprint = payload["public_key_sha256"]
            if not isinstance(document_version, str) or not _DOC_VERSION.fullmatch(document_version):
                raise InvalidEnvelope("invalid logical document version")
            if not isinstance(fingerprint, str) or not _FINGERPRINT.fullmatch(fingerprint):
                raise InvalidEnvelope("invalid public key pin")
            if len(_b64(fingerprint, 32)) != 32:
                raise InvalidEnvelope("invalid public key pin")
        if payload["algorithm"] != "AES-256-GCM+RSA-OAEP-SHA256":
            raise InvalidEnvelope("unsupported envelope algorithm")
        for key in ("tenant_id", "case_id", "object_id"):
            if not isinstance(payload[key], str) or not _ID.fullmatch(payload[key]):
                raise InvalidEnvelope("invalid document identity")
        arn = payload["kms_key_arn"]
        if not isinstance(arn, str) or not re.fullmatch(
            r"arn:aws:kms:eu-[a-z0-9-]+:\d{12}:key/[A-Za-z0-9-]+", arn
        ):
            raise InvalidEnvelope("invalid regional KMS key")
        nonce = _b64(payload["nonce"], 12)
        dek = _b64(payload["wrapped_dek"], 512)
        ciphertext = _b64(payload["ciphertext"], _MAX_CIPHER_BYTES)
        if len(nonce) != 12 or len(dek) not in (256, 384, 512) or len(ciphertext) < 17:
            raise InvalidEnvelope("invalid cryptographic field length")
        return cls(payload["tenant_id"], payload["case_id"], payload["object_id"],
                   arn, nonce, dek, ciphertext, version, document_version, fingerprint)

    def associated_data(self) -> bytes:
        if self.version == 2:
            # document_version is a client-generated logical version, not the
            # S3 VersionId (which does not exist until *after* upload).
            return ("notarai-v2|" + self.tenant_id + "|" + self.case_id + "|" +
                    self.object_id + "|" + self.document_version + "|" +
                    self.kms_key_arn + "|" + self.public_key_sha256).encode("ascii")
        return ("notarai-v1|" + self.tenant_id + "|" + self.case_id + "|" + self.object_id).encode("ascii")

    def open_inside_attested_task(self, unwrapper: Any) -> bytes:
        """Decrypt only when passed a correctly attested KMS key-unwrapper.

        The supplied unwrapper must use a Nitro attestation-gated KMS Decrypt
        call and resolve CiphertextForRecipient inside the guest. No fallback
        to a normal KMS Decrypt response is permitted.
        """
        dek = unwrapper.unwrap(self.wrapped_dek, self.kms_key_arn)
        if not isinstance(dek, bytes) or len(dek) != 32:
            raise InvalidEnvelope("invalid released data key")
        try:
            return AESGCM(dek).decrypt(self.nonce, self.ciphertext, self.associated_data())
        except InvalidTag as exc:
            raise InvalidEnvelope("document authentication failed") from exc
