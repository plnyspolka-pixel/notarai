"""Offline cryptographic pilot: customer-owned key -> one Nitro recipient.

This is a *pure cryptographic component*, not an attestation verifier or an
AWS deployment. The recipient public key MUST be checked by an independently
trusted client against a fresh, authentic Nitro attestation and an approved
image/PCR before issue_job_release. The guest MUST enforce independent signed
origin admission, tenant/job authorization, no-egress, and one-shot lifecycle
before calling open_preview_in_guest. No KMS/external custodian is used here.

Operationally: a customer-held RSA key seals DEKs; after verifying a live
attestation the offline customer client rewraps one DEK to one guest key.
The operator may store ciphertext and grants, but never receives the DEK.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
from collections.abc import Mapping

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_MAX_DOCUMENT = 25 * 1024 * 1024
_MAX_TTL_SECONDS = 900
_ID = re.compile(r"[A-Za-z0-9_-]{1,80}\Z")
_VERSION = re.compile(r"[a-f0-9]{32}\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_PIN = re.compile(r"[A-Za-z0-9+/]{43}=\Z")
_ENVELOPE_KEYS = frozenset({
    "schema", "tenant_id", "case_id", "object_id", "document_version",
    "owner_spki_sha256", "nonce_b64", "ciphertext_b64", "owner_wrapped_dek_b64",
})
_GRANT_KEYS = frozenset({
    "schema", "tenant_id", "case_id", "object_id", "document_version",
    "envelope_sha256", "job_id", "operation", "recipient_spki_sha256",
    "issued_at", "expires_at", "release_nonce_b64", "recipient_wrapped_dek_b64",
})


class ReleaseDenied(ValueError):
    """Generic failure only, never include customer data or secrets."""


def _check(ok: bool) -> None:
    if not ok:
        raise ReleaseDenied("customer release denied")


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _from_b64(value: object, *, size: int, maximum: int | None = None) -> bytes:
    _check(isinstance(value, str) and len(value) <= ((maximum or size) + 2) // 3 * 4 + 4)
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        raise ReleaseDenied("customer release denied") from None
    _check(len(raw) == size if maximum is None else size <= len(raw) <= maximum)
    _check(_b64(raw) == value)
    return raw


def _json(data: Mapping) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _load_public(pem: bytes) -> rsa.RSAPublicKey:
    try:
        key = serialization.load_pem_public_key(pem)
    except (ValueError, TypeError):
        raise ReleaseDenied("customer release denied") from None
    _check(isinstance(key, rsa.RSAPublicKey) and key.key_size >= 3072)
    return key


def _load_private(pem: bytes) -> rsa.RSAPrivateKey:
    try:
        key = serialization.load_pem_private_key(pem, password=None)
    except (ValueError, TypeError):
        raise ReleaseDenied("customer release denied") from None
    _check(isinstance(key, rsa.RSAPrivateKey) and key.key_size >= 3072)
    return key


def _pin(pub: rsa.RSAPublicKey) -> str:
    spki = pub.public_bytes(serialization.Encoding.DER,
                            serialization.PublicFormat.SubjectPublicKeyInfo)
    return _b64(hashlib.sha256(spki).digest())


def _oaep(label: bytes) -> padding.OAEP:
    return padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),
                        algorithm=hashes.SHA256(), label=hashlib.sha256(label).digest())


def _headers(envelope: Mapping) -> dict:
    return {k: envelope[k] for k in (
        "tenant_id", "case_id", "object_id", "document_version", "owner_spki_sha256")}


def _aad(envelope: Mapping) -> bytes:
    return b"notarai:customer-envelope:v1\0" + _json(_headers(envelope))


def parse_envelope(envelope: Mapping) -> dict:
    _check(isinstance(envelope, Mapping) and set(envelope) == _ENVELOPE_KEYS)
    _check(envelope["schema"] == "notarai.customer-envelope.v1")
    for key in ("tenant_id", "case_id", "object_id"):
        _check(isinstance(envelope[key], str) and bool(_ID.fullmatch(envelope[key])))
    _check(isinstance(envelope["document_version"], str)
           and bool(_VERSION.fullmatch(envelope["document_version"])))
    _check(isinstance(envelope["owner_spki_sha256"], str)
           and bool(_PIN.fullmatch(envelope["owner_spki_sha256"])))
    _from_b64(envelope["owner_spki_sha256"], size=32)
    _from_b64(envelope["nonce_b64"], size=12)
    _from_b64(envelope["ciphertext_b64"], size=17, maximum=_MAX_DOCUMENT + 16)
    _from_b64(envelope["owner_wrapped_dek_b64"], size=384, maximum=512)
    return dict(envelope)


def envelope_sha256(envelope: Mapping) -> str:
    return hashlib.sha256(_json(parse_envelope(envelope))).hexdigest()


def seal_document(plaintext: bytes, owner_public_pem: bytes, *,
                  tenant_id: str, case_id: str, object_id: str,
                  document_version: str) -> dict:
    """Encrypt locally; only ciphertext can be uploaded to operator S3."""
    _check(isinstance(plaintext, bytes) and 0 < len(plaintext) <= _MAX_DOCUMENT)
    owner = _load_public(owner_public_pem)
    envelope = {
        "schema": "notarai.customer-envelope.v1",
        "tenant_id": tenant_id, "case_id": case_id, "object_id": object_id,
        "document_version": document_version, "owner_spki_sha256": _pin(owner),
    }
    # Refuse bad IDs before using or deriving a DEK.
    for key in ("tenant_id", "case_id", "object_id"):
        _check(isinstance(envelope[key], str) and bool(_ID.fullmatch(envelope[key])))
    _check(isinstance(document_version, str) and bool(_VERSION.fullmatch(document_version)))
    dek, nonce = os.urandom(32), os.urandom(12)
    aad = _aad(envelope)
    envelope.update({
        "nonce_b64": _b64(nonce),
        "ciphertext_b64": _b64(AESGCM(dek).encrypt(nonce, plaintext, aad)),
        "owner_wrapped_dek_b64": _b64(owner.encrypt(dek, _oaep(aad))),
    })
    return parse_envelope(envelope)


def _grant_aad(grant: Mapping) -> bytes:
    metadata = {k: v for k, v in grant.items() if k != "recipient_wrapped_dek_b64"}
    return b"notarai:customer-release:v1\0" + _json(metadata)


def parse_grant(grant: Mapping) -> dict:
    _check(isinstance(grant, Mapping) and set(grant) == _GRANT_KEYS)
    _check(grant["schema"] == "notarai.customer-release.v1"
           and grant["operation"] == "preview-only")
    for key in ("tenant_id", "case_id", "object_id", "job_id"):
        _check(isinstance(grant[key], str) and bool(_ID.fullmatch(grant[key])))
    _check(isinstance(grant["document_version"], str)
           and bool(_VERSION.fullmatch(grant["document_version"])))
    _check(isinstance(grant["envelope_sha256"], str)
           and bool(_SHA.fullmatch(grant["envelope_sha256"])))
    _check(isinstance(grant["recipient_spki_sha256"], str)
           and bool(_PIN.fullmatch(grant["recipient_spki_sha256"])))
    _from_b64(grant["recipient_spki_sha256"], size=32)
    _from_b64(grant["release_nonce_b64"], size=24)
    _from_b64(grant["recipient_wrapped_dek_b64"], size=384, maximum=512)
    _check(type(grant["issued_at"]) is int and type(grant["expires_at"]) is int
           and 0 < grant["issued_at"] < grant["expires_at"] < 4102444800
           and grant["expires_at"] - grant["issued_at"] <= _MAX_TTL_SECONDS)
    return dict(grant)


def issue_job_release(envelope: Mapping, owner_private_pem: bytes,
                      independently_verified_recipient_public_pem: bytes, *,
                      job_id: str, issued_at: int, expires_at: int) -> dict:
    """Offline customer operation; caller MUST verify NSM attestation first.

    Do not call with a public key taken directly from an operator-controlled
    endpoint. This component does not validate COSE/NSM attestation itself.
    """
    env = parse_envelope(envelope)
    owner = _load_private(owner_private_pem)
    _check(_pin(owner.public_key()) == env["owner_spki_sha256"])
    recipient = _load_public(independently_verified_recipient_public_pem)
    aad = _aad(env)
    try:
        dek = owner.decrypt(_from_b64(env["owner_wrapped_dek_b64"], size=384, maximum=512),
                            _oaep(aad))
        _check(len(dek) == 32)
        # Prove this is the DEK that actually opens the exact authenticated doc.
        AESGCM(dek).decrypt(_from_b64(env["nonce_b64"], size=12),
                            _from_b64(env["ciphertext_b64"], size=17, maximum=_MAX_DOCUMENT + 16), aad)
    except Exception:
        raise ReleaseDenied("customer release denied") from None
    grant = {
        "schema": "notarai.customer-release.v1",
        **{k: env[k] for k in ("tenant_id", "case_id", "object_id", "document_version")},
        "envelope_sha256": envelope_sha256(env), "job_id": job_id,
        "operation": "preview-only", "recipient_spki_sha256": _pin(recipient),
        "issued_at": issued_at, "expires_at": expires_at,
        "release_nonce_b64": _b64(os.urandom(24)),
    }
    _check(isinstance(job_id, str) and bool(_ID.fullmatch(job_id)))
    _check(type(issued_at) is int and type(expires_at) is int
           and 0 < issued_at < expires_at < 4102444800
           and expires_at - issued_at <= _MAX_TTL_SECONDS)
    grant["recipient_wrapped_dek_b64"] = _b64(recipient.encrypt(dek, _oaep(_grant_aad(grant))))
    return parse_grant(grant)


def open_preview_in_guest(envelope: Mapping, grant: Mapping,
                          guest_ephemeral_private_pem: bytes, *,
                          expected_tenant: str, expected_case: str,
                          expected_object: str, expected_job: str,
                          origin_receipt: Mapping, origin_signature: bytes,
                          pinned_notary_signing_public_raw: bytes,
                          expected_issuer_id: str, expected_s3_version: str,
                          now: int) -> bytes:
    """Crypto primitive ONLY. Guest MUST first verify origin and authorization.

    This method does not perform physical attestation or enforce one-time job
    consumption. Never connect it to AWS without those controls, a pinned
    issuer public key in the measured image, and a verified Nitro trust root.
    """
    # Existing SEC-03 origin admission, adapted for customer-owned v3.
    # MUST run before any private-key operation or DEK unwrap.
    from confidential.customer_origin import verify_customer_origin
    verify_customer_origin(
        envelope, origin_receipt, origin_signature,
        pinned_notary_signing_public_raw=pinned_notary_signing_public_raw,
        expected_issuer_id=expected_issuer_id,
        expected_s3_version=expected_s3_version, now=now,
    )
    env, approval = parse_envelope(envelope), parse_grant(grant)
    key = _load_private(guest_ephemeral_private_pem)
    _check(type(now) is int and approval["issued_at"] <= now < approval["expires_at"])
    _check(approval["recipient_spki_sha256"] == _pin(key.public_key()))
    _check(approval["envelope_sha256"] == envelope_sha256(env))
    for field, expected in (
        ("tenant_id", expected_tenant), ("case_id", expected_case),
        ("object_id", expected_object), ("job_id", expected_job),
    ):
        _check(approval[field] == expected)
        if field != "job_id":
            _check(env[field] == expected)
    _check(approval["document_version"] == env["document_version"])
    try:
        dek = key.decrypt(_from_b64(approval["recipient_wrapped_dek_b64"], size=384, maximum=512),
                          _oaep(_grant_aad(approval)))
        _check(len(dek) == 32)
        return AESGCM(dek).decrypt(
            _from_b64(env["nonce_b64"], size=12),
            _from_b64(env["ciphertext_b64"], size=17, maximum=_MAX_DOCUMENT + 16),
            _aad(env),
        )
    except Exception:
        raise ReleaseDenied("customer release denied") from None