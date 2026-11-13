"""Encrypted-only NotarAI prototype storage.

Only authenticates office membership and validates the structure of AES-GCM
ciphertext. It NEVER derives keys or receives plaintext/password. Content
provenance and encryption cannot be established by the server alone. Separate
offline client has to be pinned/signed to claim operator-blind workflow.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import re
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

import magazyn

router = APIRouter(prefix="/api/sealed", tags=["Sealed Vault POC"])
VAULT = "sealed_vault"
SCHEMA = "notarai.sealed.v1"
BASE64URL = re.compile(r"^[A-Za-z0-9_-]+$")
MAX_CHARS = 5_600_000
MAX_OBJECTS = 50


def _decode(value: str, expected_length: int | None = None) -> bytes:
    if not BASE64URL.fullmatch(value):
        raise ValueError("Invalid base64url")
    try:
        data = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        if base64.urlsafe_b64encode(data).decode("ascii").rstrip("=") != value:
            raise ValueError("Non-canonical base64url")
    except (ValueError, binascii.Error) as error:
        raise ValueError("Invalid base64url") from error
    if expected_length is not None and len(data) != expected_length:
        raise ValueError("Invalid ciphertext metadata size")
    return data


class SealedEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_name: str = Field(alias="schema")
    documentId: uuid.UUID
    tenantRef: str = Field(min_length=1, max_length=120)
    algorithm: str
    kdf: str
    iterations: int
    salt: str = Field(min_length=22, max_length=22)
    nonce: str = Field(min_length=16, max_length=16)
    ciphertext: str = Field(min_length=23, max_length=MAX_CHARS)


def _valid(envelope: SealedEnvelope) -> None:
    if envelope.schema_name != SCHEMA or envelope.algorithm != "AES-256-GCM" or \
       envelope.kdf != "PBKDF2-SHA256" or envelope.iterations != 600_000:
        raise HTTPException(422, "Unsupported Sealed envelope v1")
    if envelope.tenantRef != magazyn.kancelaria():
        raise HTTPException(403, "Vault belongs to another office")
    try:
        _decode(envelope.salt, 16)
        _decode(envelope.nonce, 12)
        ciphertext = _decode(envelope.ciphertext)
        if not 17 <= len(ciphertext) <= 4 * 1024 * 1024 + 16:
            raise ValueError("Invalid ciphertext length")
    except ValueError as error:
        raise HTTPException(422, "Invalid ciphertext envelope") from error


def _read():
    return magazyn.wczytaj_plik_kancelarii(VAULT, {"documents": {}})


@router.get("/context")
def context():
    if magazyn.u_klienta():
        raise HTTPException(409, "Local-only office: vault storage disabled")
    return {"tenantRef": magazyn.kancelaria(), "schema": SCHEMA, "mode": "POC_ONLY"}


@router.post("/documents", status_code=201)
def store_document(envelope: SealedEnvelope):
    if magazyn.u_klienta():
        raise HTTPException(409, "Local-only office: vault storage disabled")
    _valid(envelope)
    serial = envelope.model_dump(by_alias=True, mode="json")
    import json
    # Bind every authenticated envelope field, not just ciphertext bytes.
    canonical = json.dumps(serial, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def insert(state):
        documents = state.setdefault("documents", {})
        key = str(envelope.documentId)
        existing = documents.get(key)
        if existing:
            if existing["envelope_sha256"] == digest:
                return {"documentId": key, "envelope_sha256": digest, "created": False}
            raise HTTPException(409, "Sealed document ID already used for another version")
        if len(documents) >= MAX_OBJECTS:
            raise HTTPException(413, "Office Sealed POC quota reached")
        documents[key] = {"envelope": serial, "envelope_sha256": digest}
        return {"documentId": key, "envelope_sha256": digest, "created": True}
    return magazyn.zmien_plik_kancelarii(VAULT, insert, {"documents": {}})


@router.get("/documents/{document_id}")
def load_document(document_id: uuid.UUID):
    if magazyn.u_klienta():
        raise HTTPException(409, "Local-only office: vault storage disabled")
    record = _read().get("documents", {}).get(str(document_id))
    if not record:
        raise HTTPException(404, "No sealed document with this ID")
    return record["envelope"]
