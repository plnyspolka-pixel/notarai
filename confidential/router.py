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
    allowed = os.getenv("PIECZAPP_CONFIDENTIAL_ALLOWED_TENANT", "")
    if not allowed or tenant != allowed:
        raise HTTPException(403, "Poufny tryb nie jest wlaczony dla tej kancelarii.")
    if not isinstance(tenant, str) or not _ID.fullmatch(tenant):
        raise HTTPException(403, "Brak uprawnien kancelarii.")
    return tenant


def _key(tenant: str, case_id: str, object_id: str) -> str:
    if not _ID.fullmatch(case_id) or not _ID.fullmatch(object_id):
        raise HTTPException(400, "Nieprawidlowy identyfikator.")
    return "kancelarie/" + tenant + "/confidential/" + case_id + "/" + object_id + ".json"


def _bucket() -> str:
    """Dedicated ciphertext-only bucket: never fall back to existing case storage."""
    bucket = os.getenv("PIECZAPP_CONFIDENTIAL_BUCKET", "")
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{2,62}", bucket):
        raise HTTPException(503, "Oddzielny magazyn poufny nie jest skonfigurowany.")
    return bucket


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
        Bucket=_bucket(), Key=key,
        Body=json.dumps(payload, separators=(",", ":")).encode(),
        ContentType="application/json",
        **magazyn._szyfrowanie(),
    )
    return JSONResponse({"stored": True}, headers={"Cache-Control": "no-store"})


@router.post("/preview/{case_id}/{object_id}")
def queue_preview(request: Request, case_id: str, object_id: str):
    """Queue a PREVIEW-only job for a specifically configured test tenant.

    This never starts an ECS task, submits a form, or shares plaintext.
    The isolated ECS task must be started by the separately provisioned runner.
    """
    import uuid
    import boto3
    import magazyn

    tenant = _scope(request)
    key = _key(tenant, case_id, object_id)
    if tenant != os.getenv("PIECZAPP_CONFIDENTIAL_JOB_TENANT"):
        raise HTTPException(403, "Kolejka nie jest przypisana do tej kancelarii.")
    queue_url = os.getenv("PIECZAPP_CONFIDENTIAL_JOB_QUEUE_URL", "")
    queue_pattern = r"https://sqs\.eu-[a-z0-9-]+\.amazonaws\.com/[0-9]{12}/notarai-confidential-[A-Za-z0-9_-]+(?:\.fifo)?"
    if not re.fullmatch(queue_pattern, queue_url):
        raise HTTPException(503, "Kolejka poufnych zadan nie jest skonfigurowana.")
    _approved_key()  # never enqueue before an approved key has been provisioned
    try:
        magazyn._klient_s3().head_object(Bucket=_bucket(), Key=key)
    except Exception as exc:
        if type(exc).__name__ in ("NoSuchKey", "ClientError"):
            raise HTTPException(404, "Nie znaleziono zaszyfrowanego dokumentu.")
        raise
    job_id = uuid.uuid4().hex
    metadata = json.dumps({
        "tenant_id": tenant, "case_id": case_id, "object_id": object_id,
        "job_id": job_id,
    }, separators=(",", ":"))
    sqs = boto3.client("sqs", region_name="eu-central-1")
    options = {"QueueUrl": queue_url, "MessageBody": metadata}
    if queue_url.endswith(".fifo"):
        options.update(MessageGroupId=tenant, MessageDeduplicationId=job_id)
    sqs.send_message(**options)
    return JSONResponse(
        {"queued": True, "job_id": job_id, "mode": "preview-only"},
        status_code=202, headers={"Cache-Control": "no-store"},
    )


@router.get("/envelopes/{case_id}/{object_id}")
def retrieve(request: Request, case_id: str, object_id: str):
    import magazyn
    tenant = _scope(request)
    key = _key(tenant, case_id, object_id)
    try:
        body = magazyn._klient_s3().get_object(Bucket=_bucket(), Key=key)["Body"].read()
    except Exception as exc:
        # Never leak AWS error details, identifiers or object contents.
        if type(exc).__name__ in ("NoSuchKey", "ClientError"):
            raise HTTPException(404, "Nie znaleziono zaszyfrowanego dokumentu.")
        raise
    if len(body) > _MAX_BODY:
        raise HTTPException(500, "Nieprawidlowy zapis dokumentu.")
    return JSONResponse(json.loads(body), headers={"Cache-Control": "no-store"})
