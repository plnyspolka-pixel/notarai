"""Stage 2 of fictional SEC-03 Nitro pilot: signed origin -> one preview job.

Must be run only after independent issuer signs exact staged ciphertext bytes
AND immutable S3 VersionId. No production notarial data. No plaintext or DEK
in this tool. The --apply flag is mandatory for ANY AWS call.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import time
import uuid
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from confidential.document_authenticity import verify_document_origin
from confidential.document_registry import DocumentVersionRegistry
from confidential.envelope import Envelope
from confidential.job_ledger import PreviewJobLedger, validate_version_id

REGION = "eu-central-1"
_MAX_CIPHER = 35 * 1024 * 1024
_MAX_RECEIPT = 8192
_ACCOUNT = re.compile(r"^[0-9]{12}$")
_TENANT = re.compile(r"^[a-z0-9]{1,12}$")
_SHA = re.compile(r"^[a-f0-9]{64}$")


def _load_json_strict(blob: bytes):
    def no_duplicates(pairs):
        parsed = {}
        for k, v in pairs:
            if k in parsed:
                raise ValueError("duplicate JSON property")
            parsed[k] = v
        return parsed
    return json.loads(blob, object_pairs_hook=no_duplicates)


def enqueue_signed_synthetic(
    *, s3, ddb, sqs, tenant: str, bucket: str,
    queue_url: str, kms_key_arn: str, s3_version: str,
    ciphertext_file: Path, origin_receipt_file: Path,
    trusted_issuer_public_key_pem: bytes,
    independent_issuer_spki_sha256: str, now: int | None = None,
    new_job_id=None,
) -> str:
    """Require issuer signature and byte-for-byte S3 readback before any SQS."""
    if not isinstance(tenant, str) or not _TENANT.fullmatch(tenant):
        raise ValueError("invalid pilot tenant")
    if not isinstance(independent_issuer_spki_sha256, str) or not _SHA.fullmatch(
        independent_issuer_spki_sha256
    ):
        raise ValueError("missing independently pinned issuer key")
    if not isinstance(queue_url, str) or not queue_url.startswith(
        f"https://sqs.{REGION}.amazonaws.com/"
    ) or not queue_url.endswith(f"/notarai-confidential-{tenant}.fifo"):
        raise ValueError("unexpected pilot queue")
    validate_version_id(s3_version)
    now = int(time.time()) if now is None else now
    with ciphertext_file.open("rb") as f:
        wire = f.read(_MAX_CIPHER + 1)
    with origin_receipt_file.open("rb") as f:
        signed = f.read(_MAX_RECEIPT + 1)
    if not wire or len(wire) > _MAX_CIPHER or not signed or len(signed) > _MAX_RECEIPT:
        raise ValueError("untrusted pilot fixture size")
    envelope = Envelope.parse(_load_json_strict(wire))
    if (envelope.version != 2 or envelope.tenant_id != tenant
            or envelope.case_id != "pilot01" or envelope.object_id != "synthetic01"
            or envelope.kms_key_arn != kms_key_arn):
        raise ValueError("only the hardcoded fictional fixture is permitted")
    key = serialization.load_pem_public_key(trusted_issuer_public_key_pem)
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("issuer Ed25519 key required")
    spki = key.public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    if hashlib.sha256(spki).hexdigest() != independent_issuer_spki_sha256:
        raise ValueError("issuer public key not independently pinned")
    bundle = _load_json_strict(signed)
    if (not isinstance(bundle, dict)
            or set(bundle) != {"schema", "receipt", "signature_b64"}
            or bundle["schema"] != "notarai.signed-origin-receipt.v1"):
        raise ValueError("untrusted signed receipt")
    signature = base64.b64decode(bundle["signature_b64"], validate=True)
    digest = hashlib.sha256(wire).hexdigest()
    receipt = bundle["receipt"]
    verify_document_origin(
        receipt=receipt, signature=signature,
        independent_issuer_public_key=key.public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        ),
        expected_tenant=tenant, expected_case="pilot01",
        expected_object="synthetic01", expected_document_version=envelope.document_version,
        expected_s3_version=s3_version, expected_ciphertext_sha256=digest,
        expected_key_arn=kms_key_arn, expected_key_pin=envelope.public_key_sha256,
        expected_issuer_id=receipt["issuer_id"], now=now,
    )
    object_key = f"kancelarie/{tenant}/confidential/pilot01/synthetic01.json"
    result = s3.get_object(Bucket=bucket, Key=object_key, VersionId=s3_version)
    with result["Body"] as body:
        actual = body.read(_MAX_CIPHER + 1)
    if actual != wire or result.get("VersionId") != s3_version:
        raise ValueError("actual S3 bytes or version differ from signed ciphertext")
    registry = DocumentVersionRegistry(ddb, tenant=tenant)
    check = dict(case_id="pilot01", object_id="synthetic01",
                 document_version=envelope.document_version,
                 ciphertext_sha256=digest, key_pin=envelope.public_key_sha256,
                 s3_version=s3_version)
    registry.require_stored(**check)
    # S3 sidecar exists only after signer verification. Never overwrite it.
    s3.put_object(
        Bucket=bucket,
        Key=f"kancelarie/{tenant}/confidential/pilot01/synthetic01.origin.json",
        Body=signed, ContentType="application/json",
        ServerSideEncryption="AES256", IfNoneMatch="*",
    )
    # One-way state transition; any ambiguity or failure is for manual review,
    # never automatic retry with a fresh signature or a second SQS send.
    registry.claim_preview(**check)
    job_id = new_job_id() if new_job_id is not None else uuid.uuid4().hex
    ledger = PreviewJobLedger(ddb, tenant=tenant)
    ledger.create(
        job_id=job_id, case_id="pilot01", object_id="synthetic01",
        s3_version=s3_version,
    )
    metadata = json.dumps({
        "tenant_id": tenant, "case_id": "pilot01",
        "object_id": "synthetic01", "job_id": job_id,
        "s3_version": s3_version,
    }, separators=(",", ":"))
    try:
        sqs.send_message(
            QueueUrl=queue_url, MessageGroupId=tenant,
            MessageDeduplicationId=job_id, MessageBody=metadata,
        )
    except Exception:
        ledger.mark_queue_uncertain(job_id)
        raise RuntimeError("synthetic SQS delivery uncertain; review ledger") from None
    return job_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--account", required=True)
    parser.add_argument("--tenant", default="pilot01")
    parser.add_argument("--shared-compute", action="store_true")
    parser.add_argument("--ciphertext-file", required=True, type=Path)
    parser.add_argument("--signed-origin", required=True, type=Path)
    parser.add_argument("--immutable-s3-version", required=True)
    parser.add_argument("--trusted-issuer-pem", required=True, type=Path)
    parser.add_argument("--independent-issuer-spki-sha256", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.apply:
        print("DRY RUN: no AWS calls, receipt NOT queued.")
        return 0
    if not _ACCOUNT.fullmatch(args.account) or not _TENANT.fullmatch(args.tenant):
        raise SystemExit("DENIED: invalid account or pilot tenant")
    import boto3
    from scripts.confidential_pilot_fixture import aws, outputs
    if aws(args.profile, ["sts", "get-caller-identity"]).get("Account") != args.account:
        raise SystemExit("DENIED: AWS operator account mismatch")
    stage = outputs(
        args.profile,
        f"notarai-confidential-staging-{args.tenant}"
        if args.shared_compute else "notarai-confidential-staging",
    )
    keyinfo = outputs(
        args.profile,
        f"notarai-confidential-demo-kms-{args.tenant}"
        if args.shared_compute else "notarai-confidential-demo-kms",
    )
    session = boto3.Session(profile_name=args.profile, region_name=REGION)
    job = enqueue_signed_synthetic(
        s3=session.client("s3"), ddb=session.client("dynamodb"),
        sqs=session.client("sqs"), tenant=args.tenant,
        bucket=stage["BucketName"], queue_url=stage["QueueUrl"],
        kms_key_arn=keyinfo["KeyArn"],
        s3_version=args.immutable_s3_version,
        ciphertext_file=args.ciphertext_file,
        origin_receipt_file=args.signed_origin,
        trusted_issuer_public_key_pem=args.trusted_issuer_pem.read_bytes(),
        independent_issuer_spki_sha256=args.independent_issuer_spki_sha256,
    )
    print("Queued exactly one synthetic preview job; no form submission:", job)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
