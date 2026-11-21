"""Generate one strictly fictional, encrypted Nitro pilot document and SQS job.

Requires a configured AWS profile only when --apply is explicitly set.
No customer files, no arbitrary plaintext input, no decrypted data in S3.
Never retrieves private KMS key material. One fixture == one job.

python scripts/confidential_pilot_fixture.py --account <12-digit account> \
  --profile notarai-admin --tenant pilot01 --apply
"""
from __future__ import annotations

import argparse
import base64
import json
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
    aad = f"notarai-v1|{tenant}|{case}|{obj}".encode()
    cipher = AESGCM(dek).encrypt(nonce, payload, aad)
    wrapped = pub.encrypt(dek, padding.OAEP(
        mgf=padding.MGF1(hashes.SHA256()),
        algorithm=hashes.SHA256(), label=None,
    ))
    encoded = lambda data: base64.b64encode(data).decode("ascii")
    return {
        "version": 1, "algorithm": "AES-256-GCM+RSA-OAEP-SHA256",
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
                   apply: bool = False) -> str | None:
    if not _ACCOUNT.fullmatch(account) or not _TENANT.fullmatch(tenant):
        raise ValueError("invalid account or pilot tenant")
    if not apply:
        print("DRY RUN: would encrypt only a hardcoded fictional form and submit SQS metadata.")
        return None
    identity = aws(profile, ["sts", "get-caller-identity"])
    if identity.get("Account") != account:
        raise RuntimeError("AWS account mismatch")
    stage = outputs(profile, "notarai-confidential-staging")
    keyinfo = outputs(profile, "notarai-confidential-demo-kms")
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
    object_body = json.dumps(envelope, separators=(",", ":"))
    # boto3 uses the same configured profile and has native binary upload.
    import boto3
    sess = boto3.Session(profile_name=profile, region_name=REGION)
    sess.client("s3").put_object(
        Bucket=bucket, Key=object_key, Body=object_body.encode("ascii"),
        ContentType="application/json", ServerSideEncryption="AES256",
    )
    job_id = uuid.uuid4().hex
    # Same ordered lifecycle as the SaaS API; a duplicate or unknown SQS
    # message cannot cause decryption in the verified Nitro guest.
    from confidential.job_ledger import PreviewJobLedger
    ledger = PreviewJobLedger(sess.client("dynamodb"), tenant=tenant)
    ledger.create(job_id=job_id, case_id="pilot01", object_id="synthetic01")
    try:
        sess.client("sqs").send_message(
            QueueUrl=queue,
            MessageGroupId=tenant,
            MessageDeduplicationId=job_id,
            MessageBody=json.dumps({
                "tenant_id": tenant, "case_id": "pilot01",
                "object_id": "synthetic01", "job_id": job_id,
            }, separators=(",", ":")),
        )
    except Exception:
        ledger.mark_queue_uncertain(job_id)
        raise RuntimeError("synthetic queue delivery uncertain; review job ledger") from None
    print("Queued synthetic encrypted form preview.")
    print("job_id:", job_id)
    print("Only fictional data was uploaded; no task was launched.")
    return job_id


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--account", required=True)
    p.add_argument("--profile", required=True)
    p.add_argument("--tenant", default="pilot01")
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()
    create_fixture(
        profile=args.profile, account=args.account, tenant=args.tenant,
        apply=args.apply
    )


if __name__ == "__main__":
    main()
