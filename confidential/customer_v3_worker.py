"""AWS Nitro v3 one-shot dispatcher: SQS metadata, S3 challenge/attestation/grant.

The only DEK release is an *independent customer client's* grant to the
ephemeral, NSM-attested recipient. No KMS decrypt path exists here. The client
verifies Nitro COSE/PCRs separately; the dispatcher never treats S3 as trusted.
Fictional preview only; no external submission and no plaintext logging.

Per-job objects (untrusted S3 transport):
  confidential-control/<job_id>/challenge.json    customer-created, once
  confidential-control/<job_id>/attestation.cbor   guest-created, once
  confidential-control/<job_id>/grant.json         customer-created, once

The Ed25519 origin verification key is BAKED INTO the measured image at
/opt/notarai/trust/customer-origin-v1.json, never loaded from S3/environment.
"""
from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

from confidential.customer_attested_release import challenge_user_data
from confidential.customer_guest_v3 import CustomerGuestSession
from confidential.customer_release import _json, envelope_sha256, parse_envelope
from confidential.customer_v3_execution import (
    _read_object, _strict_json, process_preview_once,
)
from confidential.document_registry import DocumentVersionRegistry
from confidential.job_ledger import PreviewJobLedger, validate_version_id

_TENANT = re.compile(r"[a-z0-9]{1,12}\Z")
_ID = re.compile(r"[A-Za-z0-9_-]{1,80}\Z")
_BUCKET = re.compile(r"[a-z0-9][a-z0-9.-]{2,62}\Z")
_TRUST_FILE = Path("/opt/notarai/trust/customer-origin-v1.json")
_MAX_CONTROL = 8192
_MAX_ATTESTATION = 32768


class DispatchDenied(ValueError):
    """No AWS error, customer identifier or document content in exception."""


def _deny() -> None:
    raise DispatchDenied("customer v3 dispatch denied")


def _read_optional(s3, bucket: str, key: str, maximum: int) -> bytes | None:
    try:
        reply = s3.get_object(Bucket=bucket, Key=key)
    except Exception as exc:
        code = (getattr(exc, "response", {}) or {}).get("Error", {}).get("Code")
        if code in ("NoSuchKey", "404", "NotFound"):
            return None
        _deny()
    with reply["Body"] as stream:
        value = stream.read(maximum + 1)
    if not value or len(value) > maximum:
        _deny()
    return value


def _b64(value: object, expected_size: int) -> bytes:
    if not isinstance(value, str):
        _deny()
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error):
        _deny()
    if len(raw) != expected_size or base64.b64encode(raw).decode("ascii") != value:
        _deny()
    return raw


def _trust_from_image(path: Path = _TRUST_FILE) -> tuple[str, bytes]:
    """Caller MUST use the fixed baked path, not a runtime tenant setting."""
    raw = path.read_bytes()
    if len(raw) > 4096:
        _deny()
    data = _strict_json(raw)
    if (set(data) != {"schema", "issuer_id", "public_ed25519_b64"}
            or data["schema"] != "notarai.customer-origin-trust.v1"
            or not isinstance(data["issuer_id"], str)
            or not _ID.fullmatch(data["issuer_id"])):
        _deny()
    return data["issuer_id"], _b64(data["public_ed25519_b64"], 32)


def _message(raw: str, tenant: str) -> tuple[str, str, str, str]:
    if len(raw) > 2048:
        _deny()
    msg = _strict_json(raw.encode("utf-8"))
    if (set(msg) != {"schema", "tenant_id", "case_id", "object_id",
                     "job_id", "s3_version"}
            or msg["schema"] != "notarai.customer-job.v1"
            or msg["tenant_id"] != tenant
            or any(not isinstance(msg.get(k), str) or not _ID.fullmatch(msg[k])
                   for k in ("case_id", "object_id", "job_id"))):
        _deny()
    return msg["case_id"], msg["object_id"], msg["job_id"], validate_version_id(msg["s3_version"])


def _challenge(raw: bytes, *, envelope: dict, job_id: str, now: int) -> bytes:
    ctx = _strict_json(raw)
    if (set(ctx) != {"schema", "job_id", "envelope_sha256", "created_at",
                     "expires_at", "nonce_b64", "user_data_b64"}
            or ctx["schema"] != "notarai.customer-nitro-challenge.v1"
            or ctx["job_id"] != job_id
            or ctx["envelope_sha256"] != envelope_sha256(envelope)
            or type(ctx["created_at"]) is not int
            or type(ctx["expires_at"]) is not int
            or not ctx["created_at"] <= now < ctx["expires_at"]
            or not 0 < ctx["expires_at"] - ctx["created_at"] <= 180):
        _deny()
    nonce = _b64(ctx["nonce_b64"], 32)
    if _b64(ctx["user_data_b64"], 32) != challenge_user_data(
            envelope, job_id=job_id, nonce=nonce):
        _deny()
    return nonce


def _control(tenant: str, job_id: str, suffix: str) -> str:
    return f"kancelarie/{tenant}/confidential-control/{job_id}/{suffix}"


async def process_queued_v3(*, s3, ddb, tenant: str, bucket: str,
                            body: str, now: int | None = None,
                            poll_seconds: int = 90, pause=time.sleep) -> dict:
    """Attest one queued job, wait for encrypted grant, burn ledger once.

    The nonce is issued by the customer beforehand. Never accept a public key
    from S3 as if it were an attested recipient. A timeout is fail closed and
    requires a new, explicitly authorized job/challenge.
    """
    if not _TENANT.fullmatch(tenant) or not _BUCKET.fullmatch(bucket):
        _deny()
    if not 0 <= poll_seconds <= 180:
        _deny()
    instant = int(time.time()) if now is None else now
    case_id, object_id, job_id, version = _message(body, tenant)
    ledger = PreviewJobLedger(ddb, tenant=tenant)
    record = ledger._record(job_id)
    if (record["state"]["S"] != "queued"
            or record["case_id"]["S"] != case_id
            or record["object_id"]["S"] != object_id
            or record["s3_version"]["S"] != version
            or "release_consumed_sha256" in record):
        _deny()
    key = f"kancelarie/{tenant}/confidential/{case_id}/{object_id}.json"
    raw_envelope = _read_object(s3, bucket=bucket, key=key, version=version)
    envelope = parse_envelope(_strict_json(raw_envelope))
    if (raw_envelope != _json(envelope)
            or envelope["tenant_id"] != tenant
            or envelope["case_id"] != case_id
            or envelope["object_id"] != object_id):
        _deny()
    DocumentVersionRegistry(ddb, tenant=tenant).require_guest(
        case_id=case_id, object_id=object_id, s3_version=version,
        ciphertext_sha256=hashlib.sha256(raw_envelope).hexdigest(),
        document_version=envelope["document_version"],
        key_pin=envelope["owner_spki_sha256"],
    )
    challenge_key = _control(tenant, job_id, "challenge.json")
    challenge = _read_optional(s3, bucket, challenge_key, _MAX_CONTROL)
    if challenge is None:
        _deny()
    nonce = _challenge(challenge, envelope=envelope, job_id=job_id, now=instant)
    issuer_id, issuer_key = _trust_from_image()
    guest = CustomerGuestSession()
    attestation = guest.attest(envelope, job_id=job_id, nonce=nonce)
    if len(attestation) > _MAX_ATTESTATION:
        _deny()
    s3.put_object(
        Bucket=bucket, Key=_control(tenant, job_id, "attestation.cbor"),
        Body=attestation, ContentType="application/cbor",
        IfNoneMatch="*", ServerSideEncryption="AES256",
    )
    grant_key = _control(tenant, job_id, "grant.json")
    start = time.monotonic()
    grant_raw = _read_optional(s3, bucket, grant_key, _MAX_CONTROL)
    while grant_raw is None and time.monotonic() - start < poll_seconds:
        pause(min(2, poll_seconds))
        grant_raw = _read_optional(s3, bucket, grant_key, _MAX_CONTROL)
    if grant_raw is None:
        _deny()
    grant = _strict_json(grant_raw)
    return await process_preview_once(
        s3=s3, ddb=ddb, guest=guest, tenant=tenant, bucket=bucket,
        case_id=case_id, object_id=object_id, job_id=job_id,
        s3_version=version, grant=grant, expected_issuer_id=issuer_id,
        pinned_notary_signing_public_raw=issuer_key, now=int(time.time()),
    )


def _config() -> tuple[str, str, str]:
    if (os.getenv("NOTARAI_CONFIDENTIAL_REQUIRED") != "1"
            or os.getenv("NOTARAI_3ZERO_MODE") != "customer-v3"
            or not os.path.exists("/dev/nsm")):
        raise DispatchDenied("NSM and customer-v3 mode required")
    tenant = os.environ["NOTARAI_CONFIDENTIAL_TENANT"]
    bucket = os.environ["NOTARAI_CONFIDENTIAL_BUCKET"]
    queue = os.environ["NOTARAI_CONFIDENTIAL_QUEUE_URL"]
    account = os.getenv("AWS_ACCOUNT_ID", "")
    if (not _TENANT.fullmatch(tenant) or not _BUCKET.fullmatch(bucket)
            or not re.fullmatch(r"[0-9]{12}", account)
            or queue != f"https://sqs.eu-central-1.amazonaws.com/{account}/notarai-confidential-{tenant}.fifo"
            or os.getenv("AWS_REGION") != "eu-central-1"):
        _deny()
    return tenant, bucket, queue


def main() -> int:
    try:
        tenant, bucket, queue = _config()
        import boto3
        session = boto3.Session(region_name="eu-central-1")
        sqs = session.client("sqs")
        received = sqs.receive_message(
            QueueUrl=queue, MaxNumberOfMessages=1, WaitTimeSeconds=10,
            VisibilityTimeout=600,
        ).get("Messages", [])
        if not received:
            print("customer-v3-worker: no job")
            return 0
        msg = received[0]
        result = asyncio.run(process_queued_v3(
            s3=session.client("s3"), ddb=session.client("dynamodb"),
            tenant=tenant, bucket=bucket, body=msg["Body"],
        ))
        if result["status"] != "preview_completed" or result["submitted"] is not False:
            _deny()
        sqs.delete_message(QueueUrl=queue, ReceiptHandle=msg["ReceiptHandle"])
        print("customer-v3-worker: preview completed")
        return 0
    except Exception as exc:
        print("customer-v3-worker: failed (" + type(exc).__name__ + ")", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
