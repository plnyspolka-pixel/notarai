"""Opaque ciphertext API for the optional confidential document workflow.

The web app NEVER decrypts. Enabled only in authenticated SaaS with
PIECZAPP_CONFIDENTIAL_ENABLED=true and configured approved KMS key.
No task invocation or plaintext logging.
"""
from __future__ import annotations

import json
import os
import re

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from confidential.envelope import Envelope, InvalidEnvelope

router = APIRouter(prefix="/api/confidential", tags=["confidential"])
_MAX_BODY = 35 * 1024 * 1024
_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


def _scope(request: Request) -> str:
    import autoryzacja
    import magazyn
    if not autoryzacja.MULTI or magazyn.TRYB != "s3":
        raise HTTPException(503, "Funkcja dostepna tylko w bezpiecznym SaaS.")
    if not getattr(request.state, "email", None) or getattr(request.state, "serwis", False):
        raise HTTPException(403, "Wymagane osobiste logowanie do kancelarii.")
    tenant = getattr(request.state, "kancelaria", "")
    if not isinstance(tenant, str) or not _ID.fullmatch(tenant):
        raise HTTPException(403, "Brak uprawnien kancelarii.")
    return tenant


def _key(tenant: str, case_id: str, object_id: str) -> str:
    if not _ID.fullmatch(case_id) or not _ID.fullmatch(object_id):
        raise HTTPException(400, "Nieprawidlowy identyfikator.")
    return "kancelarie/" + tenant + "/confidential/" + case_id + "/" + object_id + ".json"


def _approved_key() -> str:
    arn = os.getenv("PIECZAPP_CONFIDENTIAL_KMS_KEY_ARN", "")
    if not arn:
        raise HTTPException(503, "Poufne szyfrowanie nie jest skonfigurowane.")
    return arn


@router.put("/envelopes/{case_id}/{object_id}")
async def store(request: Request, case_id: str, object_id: str):
    import magazyn
    tenant = _scope(request)
    key = _key(tenant, case_id, object_id)
    # Read incrementally to enforce size even without Content-Length.
    data = bytearray()
    async for part in request.stream():
        if len(data) + len(part) > _MAX_BODY:
            raise HTTPException(413, "Dokument zaszyfrowany jest za duzy.")
        data.extend(part)
    try:
        envelope = Envelope.parse(json.loads(bytes(data)))
    except (ValueError, TypeError, InvalidEnvelope):
        raise HTTPException(400, "Bledna struktura zaszyfrowanego dokumentu.")
    finally:
        data.clear()
    if (envelope.tenant_id != tenant or envelope.case_id != case_id
            or envelope.object_id != object_id
            or envelope.kms_key_arn != _approved_key()):
        raise HTTPException(403, "Dokument nie odpowiada autoryzowanej kancelarii lub kluczowi.")
    # The payload is opaque; no server-side crypto or plaintext transformation.
    # The already validated envelope is serialised deterministically without PII.
    payload = {
        "version": 1, "algorithm": "AES-256-GCM+RSA-OAEP-SHA256",
        "tenant_id": envelope.tenant_id, "case_id": envelope.case_id,
        "object_id": envelope.object_id, "kms_key_arn": envelope.kms_key_arn,
    }
    import base64
    payload.update({
        "nonce": base64.b64encode(envelope.nonce).decode("ascii"),
        "wrapped_dek": base64.b64encode(envelope.wrapped_dek).decode("ascii"),
        "ciphertext": base64.b64encode(envelope.ciphertext).decode("ascii"),
    })
    magazyn._klient_s3().put_object(
        Bucket=magazyn.BUCKET, Key=key,
        Body=json.dumps(payload, separators=(",", ":")).encode(),
        ContentType="application/json",
        **magazyn._szyfrowanie(),
    )
    return JSONResponse({"stored": True}, headers={"Cache-Control": "no-store"})


@router.get("/envelopes/{case_id}/{object_id}")
def retrieve(request: Request, case_id: str, object_id: str):
    import magazyn
    tenant = _scope(request)
    key = _key(tenant, case_id, object_id)
    try:
        body = magazyn._klient_s3().get_object(Bucket=magazyn.BUCKET, Key=key)["Body"].read()
    except Exception as exc:
        # Never leak AWS error details, identifiers or object contents.
        if type(exc).__name__ in ("NoSuchKey", "ClientError"):
            raise HTTPException(404, "Nie znaleziono zaszyfrowanego dokumentu.")
        raise
    if len(body) > _MAX_BODY:
        raise HTTPException(500, "Nieprawidlowy zapis dokumentu.")
    return JSONResponse(json.loads(body), headers={"Cache-Control": "no-store"})
