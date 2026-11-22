"""One-shot Nitro guest worker: SQS -> S3 ciphertext -> attested KMS -> demo form.

Runs only inside /dev/nsm. This worker currently knows ONLY the local,
fictional demonstration adapter. Official portal adapters are not shipped.
No automatic form submission; no plaintext, screenshots or values in logs.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import threading
from http.server import ThreadingHTTPServer

from confidential.envelope import Envelope, InvalidEnvelope
from confidential.form_engine import TrustedForm, fill_form
from confidential.job_ledger import PreviewJobLedger, validate_version_id
from confidential.plaintext_lifecycle import harden_guest_process, ephemeral_browser_home, silence_guest_stdio

_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")

# Must be comfortably below the SQS visibility and DynamoDB claim lease
# (both currently 900 seconds). This bounds normal asyncio-controlled
# plaintext/browser lifetime, but cannot replace a host-level kill watchdog.
_PREVIEW_TIMEOUT_SECONDS = 180


def _config() -> tuple[str, str, str, str]:
    if os.environ.get("NOTARAI_CONFIDENTIAL_REQUIRED") != "1" or not os.path.exists("/dev/nsm"):
        raise RuntimeError("hardware attestation required")
    tenant = os.environ["NOTARAI_CONFIDENTIAL_TENANT"]
    bucket = os.environ["NOTARAI_CONFIDENTIAL_BUCKET"]
    queue = os.environ["NOTARAI_CONFIDENTIAL_QUEUE_URL"]
    key = os.environ["NOTARAI_CONFIDENTIAL_KMS_KEY_ARN"]
    if not _ID.fullmatch(tenant) or not key.startswith("arn:aws:kms:eu-"):
        raise RuntimeError("invalid confidential task configuration")
    if not queue.startswith("https://sqs.eu-") or not bucket:
        raise RuntimeError("invalid EU queue/storage configuration")
    return tenant, bucket, queue, key


async def _prepare_fictional_form(job_id: str, values: dict) -> None:
    from playwright.async_api import async_playwright
    from confidential.demo_browser import Handler

    if set(values) != {"name", "reference"}:
        raise ValueError("unsupported fictional form fields")
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        origin = "http://127.0.0.1:" + str(server.server_port)
        form = TrustedForm(
            "local-demo", origin + "/", (origin,),
            {"name": "#name", "reference": "#ref"}, "#submit",
        )
        # Every browser profile, cache and temporary file lives on verified
        # tmpfs. Never use a persistent user data dir, downloads or traces.
        with ephemeral_browser_home():
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(
                    headless=True,
                    args=["--disable-breakpad", "--disable-crash-reporter",
                          "--disable-background-networking"],
                )
                try:
                    context = await browser.new_context(
                        accept_downloads=False, service_workers="block",
                        permissions=[],
                    )
                    try:
                        page = await context.new_page()
                        result = await fill_form(
                            page, form, values, job_id=job_id,
                            submit=False, execution_mode="auto",
                            loopback_for_tests=True,
                        )
                        if result.submitted or result.filled_fields != 2:
                            raise RuntimeError("unexpected demo result")
                    finally:
                        await context.close()
                finally:
                    await browser.close()
    finally:
        server.shutdown()
        server.server_close()


def _parse_message(body: str, tenant: str) -> tuple[str, str, str, str]:
    msg = json.loads(body)
    if not isinstance(msg, dict) or set(msg) != {
        "tenant_id", "case_id", "object_id", "job_id", "s3_version"
    }:
        raise ValueError("invalid job message")
    if msg["tenant_id"] != tenant:
        raise ValueError("cross-tenant job denied")
    for field in ("case_id", "object_id", "job_id"):
        if not isinstance(msg[field], str) or not _ID.fullmatch(msg[field]):
            raise ValueError("invalid job identity")
    return (
        msg["case_id"], msg["object_id"], msg["job_id"],
        validate_version_id(msg["s3_version"]),
    )


def _load_decrypted_form(s3, kms, bucket: str, tenant: str, case_id: str,
                         object_id: str, key_arn: str,
                         s3_version: str) -> dict:
    from confidential.nitro_unwrapper import NitroKMSUnwrapper
    object_key = "kancelarie/" + tenant + "/confidential/" + case_id + "/" + object_id + ".json"
    result = s3.get_object(
        Bucket=bucket, Key=object_key,
        VersionId=validate_version_id(s3_version),
    )
    with result["Body"] as stream:
        ciphertext = stream.read(35 * 1024 * 1024 + 1)
    if len(ciphertext) > 35 * 1024 * 1024:
        raise ValueError("ciphertext object too large")
    env = Envelope.parse(json.loads(ciphertext))
    if (env.tenant_id, env.case_id, env.object_id, env.kms_key_arn) != (
        tenant, case_id, object_id, key_arn
    ):
        raise ValueError("envelope does not belong to this task")
    plaintext = env.open_inside_attested_task(NitroKMSUnwrapper(kms, key_arn))
    try:
        data = json.loads(plaintext)
    finally:
        # Python bytes cannot be reliably scrubbed from memory; the entire
        # Nitro task must be terminated after processing its one job.
        del plaintext
    if not isinstance(data, dict) or set(data) != {"form_id", "fields"}:
        raise ValueError("invalid confidential job payload")
    if data["form_id"] != "local-demo" or not isinstance(data["fields"], dict):
        raise ValueError("no trusted portal adapter for this form")
    return data["fields"]


def _process_one(session, tenant: str, bucket: str, queue_url: str,
                 kms_key_arn: str) -> int:
    sqs = session.client("sqs")
    incoming = sqs.receive_message(
        QueueUrl=queue_url, MaxNumberOfMessages=1, WaitTimeSeconds=10,
        VisibilityTimeout=900,
    ).get("Messages", [])
    if not incoming:
        print("confidential-worker: no job")
        return 0
    message = incoming[0]
    case_id, object_id, job_id, s3_version = _parse_message(
        message["Body"], tenant
    )
    ledger = PreviewJobLedger(session.client("dynamodb"), tenant=tenant)
    claim = ledger.claim(
        job_id=job_id, case_id=case_id, object_id=object_id,
        s3_version=s3_version,
    )
    if claim.state == "completed":
        # Redelivery after successful preview and uncertain SQS acknowledgement.
        # No decryption, browser run or external effect is repeated.
        sqs.delete_message(
            QueueUrl=queue_url, ReceiptHandle=message["ReceiptHandle"]
        )
        return 0
    if claim.state == "busy":
        # Another worker owns the lease. Leave message unacknowledged.
        return 0
    if claim.state != "claimed":
        # queue_uncertain / exhausted retry: retained for DLQ + manual review.
        return 1
    try:
        # Before any KMS release, remove inherited stdout/stderr as potential
        # sinks for decrypted names, browser exception messages and vendor logs.
        # A failure is fatal and leaves the queue item for review/retry.
        silence_guest_stdio()
        values = _load_decrypted_form(
            session.client("s3"), session.client("kms"),
            bucket, tenant, case_id, object_id, kms_key_arn,
            s3_version,
        )
        try:
            asyncio.run(asyncio.wait_for(
                _prepare_fictional_form(job_id, values),
                timeout=_PREVIEW_TIMEOUT_SECONDS,
            ))
        finally:
            # Only best-effort reference release: Python immutable strings
            # cannot be securely overwritten. One-job Nitro termination is
            # the primary isolation boundary.
            values.clear()
        # Synthetic status marker contains no documents, values, names,
        # URLs, screenshots, or personal identifiers.
        session.client("s3").put_object(
            Bucket=bucket,
            Key=f"kancelarie/{tenant}/confidential-results/{job_id}.json",
            Body=json.dumps({
                "version": 1, "job_id": job_id,
                "status": "preview_completed", "fields_filled": 2,
                "submitted": False,
            }, separators=(",", ":")).encode("ascii"),
            ContentType="application/json", ServerSideEncryption="AES256",
        )
        # Finalize only AFTER S3 marker exists, then acknowledge SQS.
        ledger.complete(job_id=job_id, token=claim.token)
    except Exception:
        # A retryable preview may repeat after SQS visibility timeout.
        # Future irreversible actions must NEVER use this retry protocol.
        try:
            ledger.fail(
                job_id=job_id, token=claim.token, attempts=claim.attempts,
            )
        except Exception:
            pass  # unknown outcome: retain queue item for reconciliation
        raise
    sqs.delete_message(
        QueueUrl=queue_url, ReceiptHandle=message["ReceiptHandle"]
    )
    print("confidential-worker: fictional AUTO preview completed")
    return 0


def main() -> int:
    try:
        harden_guest_process()
        tenant, bucket, queue_url, kms_key_arn = _config()
        import boto3
        session = boto3.Session(region_name="eu-central-1")
        return _process_one(session, tenant, bucket, queue_url, kms_key_arn)
    except Exception as exc:  # NEVER include untrusted exception contents!
        print(
            "confidential-worker: failed (" + type(exc).__name__ + ")",
            file=sys.stderr,
        )
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
