"""Stage one strictly fictional encrypted Nitro pilot document, NOT a job.

A separately signed independent origin receipt is mandatory BEFORE enqueue.
This command never starts Nitro or sends SQS; run the separate custody
admission step after verifying the exact ciphertext SHA and S3 version.

Requires a configured AWS profile only when --apply is explicitly set.
No customer files, no arbitrary plaintext input, no decrypted data in S3.
Never retrieves private KMS key material. One fixture == one job.

python scripts/confidential_pilot_fixture.py --account <12-digit account> \
  --profile notarai-admin --tenant pilot01 --apply
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import secrets
import json
import os
import re
import subprocess
import uuid
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import load_der_public_key

REGION = "eu-central-1"
_ACCOUNT = re.compile(r"^\d{12}$")
_TENANT = re.compile(r"^[a-z0-9]{1,12}$")


def fixture_envelope(*, tenant: str, kms_arn: str, public_der: bytes) -> dict:
    """Encrypt only the hardcoded synthetic local form fixture.

    This may be created on a non-Nitro host because the test payload carries
    zero customer data. The wrapping key is a public KMS key.
    """
    pub = load_der_public_key(public_der)
    if not isinstance(pub, rsa.RSAPublicKey) or pub.key_size not in (2048, 3072, 4096):
        raise ValueError("expected KMS RSA public key")
    obj, case = "synthetic01", "pilot01"
    dek = __import__("os").urandom(32)
    nonce = __import__("os").urandom(12)
    payload = json.dumps({
        "form_id": "local-demo",
        "fields": {"name": "FICTIONAL TEST PERSON", "reference": "DEMO-0001"},
    }, separators=(",", ":")).encode("utf-8")
    document_version = secrets.token_hex(16)
    pin = base64.b64encode(hashlib.sha256(public_der).digest()).decode("ascii")
    aad = f"notarai-v2|{tenant}|{case}|{obj}|{document_version}|{kms_arn}|{pin}".encode()
    cipher = AESGCM(dek).encrypt(nonce, payload, aad)
    wrapped = pub.encrypt(dek, padding.OAEP(
        mgf=padding.MGF1(hashes.SHA256()),
        algorithm=hashes.SHA256(), label=None,
    ))
    encoded = lambda data: base64.b64encode(data).decode("ascii")
    return {
        "version": 2, "algorithm": "AES-256-GCM+RSA-OAEP-SHA256",
        "document_version": document_version,
        "public_key_sha256": pin,
        "tenant_id": tenant, "case_id": case, "object_id": obj,
        "kms_key_arn": kms_arn, "nonce": encoded(nonce),
        "wrapped_dek": encoded(wrapped), "ciphertext": encoded(cipher),
    }


def aws(profile: str, args: list[str]) -> dict:
    out = subprocess.run(
        ["aws", *args, "--profile", profile, "--region", REGION,
         "--no-cli-pager", "--output", "json"],
        capture_output=True, check=True, text=True, timeout=90,
    ).stdout
    return json.loads(out)


def outputs(profile: str, stack: str) -> dict[str, str]:
    response = aws(profile, ["cloudformation", "describe-stacks",
                             "--stack-name", stack])
    items = response["Stacks"][0]["Outputs"]
    return {x["OutputKey"]: x["OutputValue"] for x in items}


def create_fixture(*, profile: str, account: str, tenant: str,
                   apply: bool = False,
                   shared_compute: bool = False,
                   ciphertext_output: Path | None = None) -> str | None:
    if not _ACCOUNT.fullmatch(account) or not _TENANT.fullmatch(tenant):
        raise ValueError("invalid account or pilot tenant")
    if not apply:
        print("DRY RUN: would stage only hardcoded fictional ciphertext; NO SQS until independent origin signature.")
        return None
    if ciphertext_output is None:
        raise ValueError("ciphertext output file required for independent post-upload signing")
    if ciphertext_output.exists():
        raise ValueError("refusing to overwrite existing encrypted fixture")
    identity = aws(profile, ["sts", "get-caller-identity"])
    if identity.get("Account") != account:
        raise RuntimeError("AWS account mismatch")
    stage = outputs(
        profile, f"notarai-confidential-staging-{tenant}"
        if shared_compute else "notarai-confidential-staging",
    )
    keyinfo = outputs(
        profile, f"notarai-confidential-demo-kms-{tenant}"
        if shared_compute else "notarai-confidential-demo-kms",
    )
    bucket, queue, key = stage["BucketName"], stage["QueueUrl"], keyinfo["KeyArn"]
    if not bucket.startswith(f"ntr-cf-{tenant}-{account}-eu-central-1"):
        raise RuntimeError("unexpected pilot bucket")
    if not queue.startswith(f"https://sqs.eu-central-1.amazonaws.com/{account}/notarai-confidential-{tenant}.fifo"):
        raise RuntimeError("unexpected pilot SQS queue")
    if not key.startswith(f"arn:aws:kms:eu-central-1:{account}:key/"):
        raise RuntimeError("unexpected pilot key ARN")
    response = aws(profile, ["kms", "get-public-key", "--key-id", key])
    if response.get("KeyUsage") != "ENCRYPT_DECRYPT" or response.get("KeySpec") not in ("RSA_3072", "RSA_4096"):
        raise RuntimeError("KMS public key is not authorized RSA encryption key")
    der = base64.b64decode(response["PublicKey"], validate=True)
    envelope = fixture_envelope(tenant=tenant, kms_arn=key, public_der=der)

    # Independently validate the envelope before uploading.
    from confidential.envelope import Envelope
    Envelope.parse(envelope)
    object_key = f"kancelarie/{tenant}/confidential/pilot01/synthetic01.json"
    object_body = json.dumps(envelope, separators=(",", ":")).encode("ascii")
    # Reserve document identity before S3. Never make a second upload after
    # uncertain S3/registry outcomes (operator performs manual reconciliation).
    import boto3
    from confidential.document_registry import DocumentVersionRegistry
    from confidential.job_ledger import validate_version_id, PreviewJobLedger
    sess = boto3.Session(profile_name=profile, region_name=REGION)
    ddb = sess.client("dynamodb")
    registry = DocumentVersionRegistry(ddb, tenant=tenant)
    digest = hashlib.sha256(object_body).hexdigest()
    reg = dict(
        case_id="pilot01", object_id="synthetic01",
        document_version=envelope["document_version"],
        ciphertext_sha256=digest, key_pin=envelope["public_key_sha256"],
    )
    registry.reserve(**reg)
    uploaded = sess.client("s3").put_object(
        Bucket=bucket, Key=object_key, Body=object_body,
        ContentType="application/json", ServerSideEncryption="AES256",
        IfNoneMatch="*",
        Metadata={"document-version": envelope["document_version"],
                  "content-sha256": digest},
    )
    s3_version = validate_version_id(uploaded.get("VersionId"))
    registry.finalize(
        case_id="pilot01", object_id="synthetic01",
        document_version=envelope["document_version"],
        ciphertext_sha256=digest, s3_version=s3_version,
    )
    # New SEC-03 fail-closed staging protocol: no queue claim or SQS send
    # until the independent issuer signs this exact SHA and S3 VersionId.
    # Write only ciphertext locally for the issuer's separate offline device.
    fd = os.open(str(ciphertext_output), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as target:
        target.write(object_body)
        target.flush()
        os.fsync(target.fileno())
    print("STAGED: synthetic ciphertext only; NO preview was enqueued.")
    print("ciphertext_sha256:", digest)
    print("s3_version:", s3_version)
    print("Signed origin receipt and independent Nitro root required before SQS.")
    return s3_version

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--account", required=True)
    p.add_argument("--profile", required=True)
    p.add_argument("--tenant", default="pilot01")
    p.add_argument("--shared-compute", action="store_true",
                   help="Use per-tenant data/KMS stacks in shared regional Nitro fabric")
    p.add_argument("--ciphertext-output", type=Path,
                   help="New local .encrypted.json path; never overwritten")
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()
    create_fixture(
        profile=args.profile, account=args.account, tenant=args.tenant,
        apply=args.apply, shared_compute=args.shared_compute,
        ciphertext_output=args.ciphertext_output,
    )


if __name__ == "__main__":
    main()
