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
from fastapi.responses import JSONResponse, Response

from confidential.envelope import Envelope, InvalidEnvelope
from confidential.document_authenticity import canonical_origin_receipt, UntrustedDocumentOrigin
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


def _origin_key(tenant: str, case_id: str, object_id: str) -> str:
    _key(tenant, case_id, object_id)  # scope validation
    return f"kancelarie/{tenant}/confidential/{case_id}/{object_id}.origin.json"


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


def _strict_envelope_json(data: bytes) -> dict:
    """Reject duplicate JSON fields to prevent multi-parser ambiguity."""
    def no_duplicates(pairs):
        result = {}
        for name, value in pairs:
            if name in result:
                raise ValueError("duplicate JSON field")
            result[name] = value
        return result
    return json.loads(data, object_pairs_hook=no_duplicates)


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
        # Retain the EXACT bytes from the independent client, so that its
        # locally computed SHA-256 can be signed after S3 returns VersionId.
        # Do not reserialize or transform ciphertext on the operator backend.
        wire = bytes(data)
        envelope = Envelope.parse(_strict_envelope_json(wire))
    except (ValueError, TypeError, InvalidEnvelope):
        raise HTTPException(400, "Bledna struktura zaszyfrowanego dokumentu.") from None
    finally:
        data.clear()
    if (envelope.version != 2 or envelope.tenant_id != tenant
            or envelope.case_id != case_id or envelope.object_id != object_id
            or envelope.kms_key_arn != _approved_key()
            or envelope.public_key_sha256 != _approved_public_key_pin()):
        raise HTTPException(403, "Dokument nie odpowiada autoryzowanej kancelarii lub kluczowi.")
    # The strict parser proves the envelope contains only the permitted
    # fields. Preserve exact opaque bytes for independently signed provenance.
    # Reserve once in DynamoDB BEFORE touching S3. S3 IfNoneMatch alone is
    # insufficient: a delete marker makes the key writable again.
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
         "s3_version": s3_version, "ciphertext_sha256": digest},
        headers={"Cache-Control": "no-store"},
    )


@router.put("/origin-receipts/{case_id}/{object_id}")
async def store_origin_receipt(request: Request, case_id: str, object_id: str):
    """Store an independently signed, immutable receipt, NOT signing material.

    Operator web backend cannot issue origin signatures. Guest verifies an
    image-pinned independent signing key before any KMS unwrap.
    """
    import base64
    import magazyn
    tenant = _scope(request)
    ciphertext_key = _key(tenant, case_id, object_id)
    raw = bytearray()
    async for part in request.stream():
        if len(raw) + len(part) > 8192:
            raise HTTPException(413, "Podpis pochodzenia jest za duzy.")
        raw.extend(part)
    try:
        bundle = _strict_envelope_json(bytes(raw))
        if (not isinstance(bundle, dict) or set(bundle) !=
                {"schema", "receipt", "signature_b64"} or
                bundle["schema"] != "notarai.signed-origin-receipt.v1"):
            raise ValueError("wrong signature bundle")
        canonical_origin_receipt(bundle["receipt"])
        sig = base64.b64decode(bundle["signature_b64"], validate=True)
        if len(sig) != 64:
            raise ValueError("invalid origin signature length")
        # Preserve exactly the signed bundle; issuer key is not provided by
        # any request field and only the pinned Nitro release can verify it.
        encoded = bytes(raw)
    except (ValueError, TypeError, UntrustedDocumentOrigin, KeyError):
        raise HTTPException(400, "Nieprawidlowe potwierdzenie pochodzenia.") from None
    finally:
        raw.clear()
    receipt = bundle["receipt"]
    if (receipt["tenant_id"], receipt["case_id"], receipt["object_id"],
            receipt["kms_key_arn"], receipt["key_pin"]) != (
        tenant, case_id, object_id, _approved_key(),
        _approved_public_key_pin(),
    ):
        raise HTTPException(403, "Potwierdzenie pochodzi od innej kancelarii.")
    s3 = magazyn._klient_s3()
    try:
        head = s3.head_object(Bucket=_bucket(), Key=ciphertext_key)
        actual_s3 = validate_version_id(head.get("VersionId"))
        md = head.get("Metadata") or {}
        if (receipt["document_version"] != md.get("document-version")
                or receipt["ciphertext_sha256"] != md.get("content-sha256")
                or receipt["s3_version"] != actual_s3):
            raise DocumentRegistryDenied("receipt differs from exact S3 version")
        _registry(tenant).require_stored(
            case_id=case_id, object_id=object_id,
            document_version=receipt["document_version"],
            ciphertext_sha256=receipt["ciphertext_sha256"],
            s3_version=actual_s3, key_pin=receipt["key_pin"],
        )
    except (DocumentRegistryDenied, JobRejected):
        raise HTTPException(409, "Podpis nie odpowiada zapisanej wersji.") from None
    except Exception:
        raise HTTPException(503, "Weryfikacja dokumentu chwilowo niedostepna.") from None
    try:
        s3.put_object(
            Bucket=_bucket(), Key=_origin_key(tenant, case_id, object_id),
            Body=encoded, ContentType="application/json", IfNoneMatch="*",
            **magazyn._szyfrowanie(),
        )
    except Exception as exc:
        if (getattr(exc, "response", {}) or {}).get("Error", {}).get("Code") in (
            "PreconditionFailed", "ConditionalRequestConflict",
        ):
            raise HTTPException(409, "Potwierdzenie pochodzenia juz istnieje.") from None
        raise HTTPException(503, "Nie udalo sie zapisac podpisu pochodzenia.") from None
    return JSONResponse({"stored": True, "signature_verified": False},
                        headers={"Cache-Control": "no-store"})


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
    # Avoid burning the one-use preview token when no signed receipt is
    # present. This is only an existence precheck; the guest validates the
    # Ed25519 signature against its independently pinned root.
    try:
        sidecar_head = magazyn._klient_s3().head_object(
            Bucket=_bucket(), Key=_origin_key(tenant, case_id, object_id),
        )
        size = sidecar_head.get("ContentLength", 0)
        if type(size) is not int or not 0 < size <= 8192:
            raise ValueError("missing or oversized origin receipt")
    except Exception:
        raise HTTPException(409, "Brak podpisanego potwierdzenia pochodzenia.") from None
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
        saved = magazyn._klient_s3().get_object(Bucket=_bucket(), Key=key)
        body = saved["Body"].read(_MAX_BODY + 1)
    except Exception as exc:
        # Never leak AWS error details, identifiers or object contents.
        if type(exc).__name__ in ("NoSuchKey", "ClientError"):
            raise HTTPException(404, "Nie znaleziono zaszyfrowanego dokumentu.") from None
        raise HTTPException(503, "Odczyt dokumentu chwilowo niedostepny.") from None
    if len(body) > _MAX_BODY:
        raise HTTPException(500, "Nieprawidlowy zapis dokumentu.")
    try:
        env = Envelope.parse(_strict_envelope_json(body))
        if env.version != 2 or (env.tenant_id, env.case_id, env.object_id,
                                env.kms_key_arn, env.public_key_sha256) != (
            tenant, case_id, object_id, _approved_key(), _approved_public_key_pin()
        ):
            raise DocumentRegistryDenied("wrong retrieved document scope")
        s3_version = validate_version_id(saved.get("VersionId"))
        _registry(tenant).require_stored(
            case_id=case_id, object_id=object_id,
            s3_version=s3_version,
            ciphertext_sha256=hashlib.sha256(body).hexdigest(),
            document_version=env.document_version, key_pin=env.public_key_sha256,
        )
    except (ValueError, TypeError, DocumentRegistryDenied, JobRejected):
        raise HTTPException(409, "Zaszyfrowany dokument nie zgadza sie z rejestrem.") from None
    # Preserve the originally signed ciphertext bytes on download, not a
    # lossy JSON reserialization that would alter its independent SHA-256.
    return Response(
        content=body, media_type="application/json",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


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
