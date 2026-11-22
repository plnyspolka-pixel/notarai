"""Nitro-only synthetic document re-encryption behind two external approvals.

Not wired to web/API; no operator-triggered recovery endpoint. The actual
custodian retains full control of KMS key policy and of the one-time approval
registry. New ciphertext must be ingested as a NEW immutable object ID.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import secrets
from collections.abc import Mapping

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from confidential.envelope import Envelope
from confidential.nitro_unwrapper import NitroKMSUnwrapper
from confidential.zk_recovery import authorize_recovery, RecoveryDenied
from confidential.recovery_trust import load_recovery_trust_root
from confidential.custody_nonce import CustodyRecoveryNonceLedger


def _spki_from_pem(pem: str) -> tuple[rsa.RSAPublicKey, str]:
    try:
        key = serialization.load_pem_public_key(pem.encode("ascii"))
        if not isinstance(key, rsa.RSAPublicKey) or key.key_size not in (3072, 4096):
            raise ValueError("unapproved KMS RSA key")
        spki = key.public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return key, base64.b64encode(hashlib.sha256(spki).digest()).decode("ascii")
    except (ValueError, UnicodeError, AttributeError):
        raise RecoveryDenied("untrusted replacement public key") from None


def reencrypt_inside_attested_nitro(
    *, original: Envelope, source_envelope_wire: bytes,
    source_s3_version: str, unwrapper: NitroKMSUnwrapper,
    recovery_request: Mapping, custodian_signature: bytes,
    trustee_signature: bytes, replacement_kms_public_pem: str,
    independent_one_time_ledger, now: int,
) -> dict:
    """After a genuine Nitro/KMS unwrap, return only v2 ciphertext.

    The custody-controlled one-time ledger consumes a request before any
    plaintext exists. No network upload and no KMS key-policy changes here.
    """
    if not os.path.exists("/dev/nsm") or not isinstance(unwrapper, NitroKMSUnwrapper):
        raise RecoveryDenied("hardware-attested Nitro runtime required")
    if not isinstance(original, Envelope) or original.version != 2:
        raise RecoveryDenied("v2 document required")
    # Never trust caller-supplied verification time for an expired approval.
    # Runtime reads its own guest clock; tolerance is for testing skew only.
    if type(now) is not int or abs(now - int(time.time())) > 120:
        raise RecoveryDenied("untrusted recovery approval clock")
    if (not isinstance(source_envelope_wire, bytes)
            or not 0 < len(source_envelope_wire) <= 35 * 1024 * 1024):
        raise RecoveryDenied("source ciphertext bytes required")
    try:
        def reject_duplicates(pairs):
            values = {}
            for key, val in pairs:
                if key in values:
                    raise ValueError("duplicate ciphertext field")
                values[key] = val
            return values
        actual = Envelope.parse(json.loads(
            source_envelope_wire, object_pairs_hook=reject_duplicates
        ))
    except (ValueError, TypeError):
        raise RecoveryDenied("invalid immutable source ciphertext") from None
    if actual != original:
        raise RecoveryDenied("source ciphertext differs from approved envelope")
    if not isinstance(recovery_request, Mapping) or recovery_request.get("action") != "rotate":
        raise RecoveryDenied("only explicit key migration is supported")
    if (recovery_request.get("tenant_id") != original.tenant_id
            or recovery_request.get("case_id") != original.case_id
            or recovery_request.get("object_id") != original.object_id
            or recovery_request.get("document_version") != original.document_version
            or recovery_request.get("old_key_arn") != original.kms_key_arn
            or recovery_request.get("source_key_pin") != original.public_key_sha256
            or recovery_request.get("source_s3_version") != source_s3_version
            or recovery_request.get("source_ciphertext_sha256") !=
                hashlib.sha256(source_envelope_wire).hexdigest()):
        raise RecoveryDenied("original document identity mismatch")
    # Public signing keys NEVER come from the operator/caller. They are
    # released by the independent custodian into the measured Nitro image.
    custodian_public_key, trustee_public_key = load_recovery_trust_root(
        tenant=original.tenant_id, old_key_arn=original.kms_key_arn,
        old_key_pin=original.public_key_sha256, now=now,
    )
    if authorize_recovery(
        request=recovery_request, custodian_signature=custodian_signature,
        trustee_signature=trustee_signature,
        custodian_public_key=custodian_public_key,
        trustee_public_key=trustee_public_key,
        expected_tenant=original.tenant_id,
        expected_old_key=original.kms_key_arn, now=now,
    ) != "rotate":
        raise RecoveryDenied("unapproved migration")
    public, pin = _spki_from_pem(replacement_kms_public_pem)
    if pin != recovery_request["new_key_sha256"]:
        raise RecoveryDenied("replacement key pin does not match approval")
    if not isinstance(independent_one_time_ledger, CustodyRecoveryNonceLedger):
        raise RecoveryDenied("verified external custody ledger required")
    # MUST be implemented in the EXTERNALLY CONTROLLED CUSTODY account, not
    # the NotarAI operator account. Fail closed on ambiguous ledger outcome.
    try:
        independent_one_time_ledger.claim_once(recovery_request["request_id"])
    except Exception:
        raise RecoveryDenied("recovery request already consumed or unavailable") from None

    # Only now is the old DEK and document briefly present in enclave memory.
    plaintext = original.open_inside_attested_task(unwrapper)
    key_bytes = bytearray(secrets.token_bytes(32))
    try:
        nonce = secrets.token_bytes(12)
        target_version = secrets.token_hex(16)
        envelope = Envelope(
            tenant_id=recovery_request["target_tenant_id"],
            case_id=original.case_id,
            object_id=recovery_request["target_object_id"],
            kms_key_arn=recovery_request["new_key_arn"],
            nonce=nonce,
            wrapped_dek=b"",
            ciphertext=b"",
            version=2, document_version=target_version,
            public_key_sha256=pin,
        )
        cipher = AESGCM(bytes(key_bytes)).encrypt(
            nonce, plaintext, envelope.associated_data()
        )
        wrapped = public.encrypt(
            bytes(key_bytes), padding.OAEP(
                mgf=padding.MGF1(hashes.SHA256()),
                algorithm=hashes.SHA256(), label=None,
            ),
        )
        b64 = lambda value: base64.b64encode(value).decode("ascii")
        return {
            "version": 2, "algorithm": "AES-256-GCM+RSA-OAEP-SHA256",
            "tenant_id": envelope.tenant_id,
            "case_id": envelope.case_id, "object_id": envelope.object_id,
            "document_version": target_version,
            "kms_key_arn": envelope.kms_key_arn,
            "public_key_sha256": pin,
            "nonce": b64(nonce), "wrapped_dek": b64(wrapped),
            "ciphertext": b64(cipher),
        }
    finally:
        key_bytes[:] = b"\x00" * len(key_bytes)
        # Python cannot guarantee zeroization of copies / plaintext bytes.
        # Dispose of the entire attested guest after its one allowed operation.
        del plaintext
