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

_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


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
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(
                accept_downloads=False, service_workers="block", permissions=[],
            )
            page = await context.new_page()
            try:
                result = await fill_form(
                    page, form, values, job_id=job_id,
                    submit=False, loopback_for_tests=True,
                )
                if result.submitted or result.filled_fields != 2:
                    raise RuntimeError("unexpected demo result")
            finally:
                await context.close()
                await browser.close()
    finally:
        server.shutdown()
        server.server_close()


def _parse_message(body: str, tenant: str) -> tuple[str, str, str]:
    msg = json.loads(body)
    if not isinstance(msg, dict) or set(msg) != {"tenant_id", "case_id", "object_id", "job_id"}:
        raise ValueError("invalid job message")
    if msg["tenant_id"] != tenant:
        raise ValueError("cross-tenant job denied")
    for field in ("case_id", "object_id", "job_id"):
        if not isinstance(msg[field], str) or not _ID.fullmatch(msg[field]):
            raise ValueError("invalid job identity")
    return msg["case_id"], msg["object_id"], msg["job_id"]


def _load_decrypted_form(s3, kms, bucket: str, tenant: str, case_id: str,
                         object_id: str, key_arn: str) -> dict:
    from confidential.nitro_unwrapper import NitroKMSUnwrapper
    object_key = "kancelarie/" + tenant + "/confidential/" + case_id + "/" + object_id + ".json"
    result = s3.get_object(Bucket=bucket, Key=object_key)
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


def main() -> int:
    try:
        tenant, bucket, queue_url, kms_key_arn = _config()
        import boto3
        session = boto3.Session(region_name="eu-central-1")
        sqs = session.client("sqs")
        incoming = sqs.receive_message(
            QueueUrl=queue_url, MaxNumberOfMessages=1, WaitTimeSeconds=10,
            VisibilityTimeout=900,
        ).get("Messages", [])
        if not incoming:
            print("confidential-worker: no job")
            return 0
        message = incoming[0]
        case_id, object_id, job_id = _parse_message(message["Body"], tenant)
        values = _load_decrypted_form(
            session.client("s3"), session.client("kms"),
            bucket, tenant, case_id, object_id, kms_key_arn
        )
        asyncio.run(_prepare_fictional_form(job_id, values))
        # Status contains no documents, form values, URL, name, or PESEL.
        session.client("s3").put_object(
            Bucket=bucket,
            Key=f"kancelarie/{tenant}/confidential-results/{job_id}.json",
            Body=json.dumps({
                "version": 1, "job_id": job_id, "status": "preview_completed",
                "fields_filled": 2, "submitted": False,
            }, separators=(",", ":")).encode("ascii"),
            ContentType="application/json", ServerSideEncryption="AES256",
        )
        sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=message["ReceiptHandle"])
        print("confidential-worker: fictional preview completed")
        return 0
    except Exception as exc:  # NEVER include untrusted exception content!
        print("confidential-worker: failed (" + type(exc).__name__ + ")", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
