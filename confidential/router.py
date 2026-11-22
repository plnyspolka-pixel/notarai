"""Opaque ciphertext API for the optional confidential document workflow.

The web app NEVER decrypts. Enabled only in authenticated SaaS with
PIECZAPP_CONFIDENTIAL_ENABLED=true and configured approved KMS key.
No task invocation or plaintext logging.
"""
from __future__ import annotations

import hashlib
import json
import os
import re

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from confidential.envelope import Envelope, InvalidEnvelope
from confidential.document_registry import DocumentVersionRegistry, DocumentRegistryDenied
from confidential.auto_mode import DEFAULT_AUTO, UnsafeAutoRequest, validate_preview_options
from confidential.job_ledger import PreviewJobLedger, JobRejected, validate_version_id

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


def _registry(tenant: str) -> DocumentVersionRegistry:
    import boto3
    return DocumentVersionRegistry(
        boto3.client("dynamodb", region_name="eu-central-1"),
        tenant=tenant,
    )


def _approved_public_key_pin() -> str:
    """Configured pin is an operator-side check, NOT an independent trust root."""
    import base64
    pin = os.getenv("PIECZAPP_CONFIDENTIAL_PUBLIC_KEY_SHA256", "")
    try:
        if len(base64.b64decode(pin, validate=True)) != 32:
            raise ValueError("invalid pin size")
    except (ValueError, TypeError):
        raise HTTPException(503, "Brak poprawnego odcisku klucza kustosza.") from None
    return pin


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
    if (envelope.version != 2 or envelope.tenant_id != tenant
            or envelope.case_id != case_id or envelope.object_id != object_id
            or envelope.kms_key_arn != _approved_key()
            or envelope.public_key_sha256 != _approved_public_key_pin()):
        raise HTTPException(403, "Dokument nie odpowiada autoryzowanej kancelarii lub kluczowi.")
    # Do not accept new legacy v1 ciphertext without version/key binding.
    # Validate structure without unwrapping DEK or logging request contents.
    payload = {
        "version": 2, "algorithm": "AES-256-GCM+RSA-OAEP-SHA256",
        "tenant_id": envelope.tenant_id, "case_id": envelope.case_id,
        "object_id": envelope.object_id, "kms_key_arn": envelope.kms_key_arn,
        "document_version": envelope.document_version,
        "public_key_sha256": envelope.public_key_sha256,
    }
    import base64
    payload.update({
        "nonce": base64.b64encode(envelope.nonce).decode("ascii"),
        "wrapped_dek": base64.b64encode(envelope.wrapped_dek).decode("ascii"),
        "ciphertext": base64.b64encode(envelope.ciphertext).decode("ascii"),
    })
    # Reserve once in DynamoDB BEFORE touching S3. S3 IfNoneMatch alone is
    # insufficient: a delete marker makes the key writable again.
    wire = json.dumps(payload, separators=(",", ":")).encode("ascii")
    digest = hashlib.sha256(wire).hexdigest()
    registry = _registry(tenant)
    try:
        registry.reserve(
            case_id=case_id, object_id=object_id,
            document_version=envelope.document_version,
            ciphertext_sha256=digest, key_pin=envelope.public_key_sha256,
        )
    except DocumentRegistryDenied:
        raise HTTPException(409, "Tozsamosc dokumentu juz uzyta lub rejestr niedostepny.") from None
    # New document revision requires a new opaque object ID.
    try:
        result = magazyn._klient_s3().put_object(
            Bucket=_bucket(), Key=key,
            Body=wire,
            ContentType="application/json",
            IfNoneMatch="*",
            Metadata={"document-version": envelope.document_version,
                      "content-sha256": digest},
            **magazyn._szyfrowanie(),
        )
    except Exception as exc:
        if (getattr(exc, "response", {}) or {}).get("Error", {}).get("Code") in (
            "PreconditionFailed", "ConditionalRequestConflict",
        ):
            raise HTTPException(409, "Obiekt istnieje; uzyj nowego identyfikatora wersji.") from None
        raise
    try:
        s3_version = validate_version_id(result.get("VersionId"))
    except JobRejected:
        # A prior put may have succeeded: do not retry or replace blindly.
        raise HTTPException(503, "Magazyn nie potwierdzil wersji niezmiennego obiektu.") from None
    try:
        registry.finalize(
            case_id=case_id, object_id=object_id,
            document_version=envelope.document_version,
            ciphertext_sha256=digest, s3_version=s3_version,
        )
    except DocumentRegistryDenied:
        # Never retry S3 write if the finalization outcome was ambiguous.
        raise HTTPException(503, "Wersja zapisana w S3, ale rejestr wymaga weryfikacji.") from None
    return JSONResponse(
        {"stored": True, "document_version": envelope.document_version,
         "s3_version": s3_version},
        headers={"Cache-Control": "no-store"},
    )


@router.get("/policy")
def automatic_policy(request: Request):
    """Read-only server policy for a signed-in confidential pilot tenant.

    This endpoint exposes no toggle that could enable filing or signatures.
    """
    _scope(request)
    return JSONResponse(
        DEFAULT_AUTO.public(), headers={"Cache-Control": "no-store"}
    )


@router.post("/preview/{case_id}/{object_id}")
async def queue_preview(request: Request, case_id: str, object_id: str):
    """AUTO is the default and the *only* accepted pilot preparation mode.

    Body, submit flags and supervised mode are rejected before any AWS call.
    It never signs, clicks Submit, sends to a portal, or shares plaintext.
    """
    import uuid
    import boto3
    import magazyn

    tenant = _scope(request)
    key = _key(tenant, case_id, object_id)
    # Never silently ignore `{"submit": true}`, `mode=supervised` or
    # any future/unknown parameter. Parsing is strict and fail-closed.
    try:
        policy = validate_preview_options(request.query_params, has_body=False)
        async for part in request.stream():
            if part:
                raise UnsafeAutoRequest("preview body must be empty")
    except UnsafeAutoRequest:
        raise HTTPException(400, "Dostepne jest tylko AUTO bez wysylania i bez danych w body.")
    if tenant != os.getenv("PIECZAPP_CONFIDENTIAL_JOB_TENANT"):
        raise HTTPException(403, "Kolejka nie jest przypisana do tej kancelarii.")
    queue_url = os.getenv("PIECZAPP_CONFIDENTIAL_JOB_QUEUE_URL", "")
    queue_pattern = r"https://sqs\.eu-[a-z0-9-]+\.amazonaws\.com/[0-9]{12}/notarai-confidential-[A-Za-z0-9_-]+(?:\.fifo)?"
    if not re.fullmatch(queue_pattern, queue_url):
        raise HTTPException(503, "Kolejka poufnych zadan nie jest skonfigurowana.")
    _approved_key()  # never enqueue before an approved key has been provisioned
    try:
        object_head = magazyn._klient_s3().head_object(Bucket=_bucket(), Key=key)
    except Exception as exc:
        if type(exc).__name__ in ("NoSuchKey", "ClientError"):
            raise HTTPException(404, "Nie znaleziono zaszyfrowanego dokumentu.")
        raise
    # Only a fully versioned S3 bucket can bind the queued job to the
    # immutable ciphertext bytes later loaded by the Nitro guest.
    try:
        s3_version = validate_version_id(object_head.get("VersionId"))
    except JobRejected:
        raise HTTPException(503, "Magazyn nie gwarantuje niezmiennej wersji dokumentu.") from None
    metadata_s3 = object_head.get("Metadata") or {}
    if (not re.fullmatch(r"[a-f0-9]{32}", metadata_s3.get("document-version", ""))
            or not re.fullmatch(r"[a-f0-9]{64}", metadata_s3.get("content-sha256", ""))):
        raise HTTPException(503, "Brak silnego wiazania wersji zaszyfrowanego dokumentu.")
    try:
        _registry(tenant).claim_preview(
            case_id=case_id, object_id=object_id,
            document_version=metadata_s3["document-version"],
            ciphertext_sha256=metadata_s3["content-sha256"],
            s3_version=s3_version, key_pin=_approved_public_key_pin(),
        )
    except DocumentRegistryDenied:
        raise HTTPException(409, "Odrzucono replay lub niezgodna wersje dokumentu.") from None
    job_id = uuid.uuid4().hex
    metadata = json.dumps({
        "tenant_id": tenant, "case_id": case_id, "object_id": object_id,
        "job_id": job_id, "s3_version": s3_version,
    }, separators=(",", ":"))
    # Durable reservation MUST precede delivery. A job absent from this
    # table can never cause Nitro to decrypt a document.
    ledger = PreviewJobLedger(
        boto3.client("dynamodb", region_name="eu-central-1"), tenant=tenant,
    )
    try:
        ledger.create(
            job_id=job_id, case_id=case_id, object_id=object_id,
            s3_version=s3_version,
        )
    except JobRejected:
        raise HTTPException(503, "Rejestr zadan nie jest dostepny.") from None
    sqs = boto3.client("sqs", region_name="eu-central-1")
    options = {"QueueUrl": queue_url, "MessageBody": metadata}
    if queue_url.endswith(".fifo"):
        options.update(MessageGroupId=tenant, MessageDeduplicationId=job_id)
    try:
        sqs.send_message(**options)
    except Exception:
        ledger.mark_queue_uncertain(job_id)
        raise HTTPException(
            503, "Wysylka do kolejki niepotwierdzona. Zadanie wymaga weryfikacji."
        ) from None
    return JSONResponse(
        {"queued": True, "job_id": job_id, "mode": policy.mode,
         "operation": "preview-only", "thinking_enabled": False,
         "can_submit": False},
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


@router.get("/jobs/{job_id}")
def preview_status(request: Request, job_id: str):
    """Read tenant-bound durable metadata. Do not fetch/decrypt the document."""
    import boto3
    tenant = _scope(request)
    if not _ID.fullmatch(job_id):
        raise HTTPException(400, "Nieprawidlowy identyfikator zadania.")
    ledger = PreviewJobLedger(
        boto3.client("dynamodb", region_name="eu-central-1"), tenant=tenant,
    )
    try:
        status = ledger.status(job_id)
    except JobRejected:
        raise HTTPException(404, "Zadanie nie jest dostepne.") from None
    return JSONResponse(status, headers={"Cache-Control": "no-store"})
