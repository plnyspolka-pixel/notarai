"""Create an independent post-upload origin receipt for EXACT encrypted bytes.

Run on the independent notary/custodian signing workstation, not in NotarAI.
The signer key never leaves the workstation. The file contains ciphertext
only, and the issued receipt is a public signature (no private material).
The signer MUST authenticate the submitting notary and verify the S3 version
and file SHA-256 out of band; CLI flags alone cannot establish this identity.
"""
from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import json
import os
import re
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from confidential.document_authenticity import canonical_origin_receipt
from confidential.envelope import Envelope
from confidential.job_ledger import validate_version_id

_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_MAX_ENCRYPTED = 35 * 1024 * 1024


def sign_origin_receipt(
    *, ciphertext_file: Path, output_file: Path, expected_sha256: str,
    verified_s3_version: str, issuer_id: str, expires_at: int,
    issuer_private_key_pem: bytes, password: bytes | None = None,
    approved_tenant: str, approved_kms_key_arn: str, approved_key_pin: str,
) -> dict:
    """Signing requires verified identifiers from independent channels."""
    if (not isinstance(expected_sha256, str) or not _DIGEST.fullmatch(expected_sha256)
            or not isinstance(issuer_id, str) or not _ID.fullmatch(issuer_id)
            or type(expires_at) is not int or not 0 < expires_at < 4102444800):
        raise ValueError("invalid release/receipt parameters")
    validate_version_id(verified_s3_version)
    with ciphertext_file.open("rb") as src:
        blob = src.read(_MAX_ENCRYPTED + 1)
    if not blob or len(blob) > _MAX_ENCRYPTED:
        raise ValueError("encrypted file absent or oversized")
    # Reject duplicate fields even when they would parse identically.
    def no_dupes(pairs):
        d = {}
        for k, v in pairs:
            if k in d:
                raise ValueError("duplicate ciphertext JSON field")
            d[k] = v
        return d
    env = Envelope.parse(json.loads(blob, object_pairs_hook=no_dupes))
    if env.version != 2 or (env.tenant_id, env.kms_key_arn, env.public_key_sha256) != (
        approved_tenant, approved_kms_key_arn, approved_key_pin
    ):
        raise ValueError("encrypted document does not match independently approved key")
    digest = hashlib.sha256(blob).hexdigest()
    if expected_sha256 != digest:
        raise ValueError("independently reviewed ciphertext SHA-256 mismatch")
    signer = serialization.load_pem_private_key(issuer_private_key_pem, password=password)
    if not isinstance(signer, Ed25519PrivateKey):
        raise ValueError("origin issuer must sign with Ed25519")
    receipt = {
        "schema": "notarai.document-origin.v1",
        "tenant_id": env.tenant_id, "case_id": env.case_id,
        "object_id": env.object_id, "document_version": env.document_version,
        "s3_version": verified_s3_version, "ciphertext_sha256": digest,
        "kms_key_arn": env.kms_key_arn, "key_pin": env.public_key_sha256,
        "issuer_id": issuer_id, "expires_at": expires_at,
    }
    signature = signer.sign(canonical_origin_receipt(receipt))
    bundle = {
        "schema": "notarai.signed-origin-receipt.v1",
        "receipt": receipt, "signature_b64": base64.b64encode(signature).decode("ascii"),
    }
    serialized = json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode("ascii")
    if len(serialized) > 8192:
        raise ValueError("origin receipt exceeds guest limit")
    fd = os.open(str(output_file), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as output:
        output.write(serialized)
        output.flush()
        os.fsync(output.fileno())
    return {"ciphertext_sha256": digest, "s3_version": verified_s3_version}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ciphertext-file", type=Path, required=True)
    parser.add_argument("--output-file", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--verified-s3-version", required=True)
    parser.add_argument("--issuer-id", required=True)
    parser.add_argument("--expires-at", required=True, type=int)
    parser.add_argument("--signing-key", required=True, type=Path)
    parser.add_argument("--encrypted-signing-key", action="store_true")
    parser.add_argument("--approved-tenant", required=True)
    parser.add_argument("--approved-kms-key-arn", required=True)
    parser.add_argument("--approved-key-pin", required=True)
    args = parser.parse_args()
    password = (getpass.getpass("Origin issuer private key password: ").encode()
                if args.encrypted_signing_key else None)
    sign_origin_receipt(
        ciphertext_file=args.ciphertext_file,
        output_file=args.output_file,
        expected_sha256=args.expected_sha256,
        verified_s3_version=args.verified_s3_version,
        issuer_id=args.issuer_id, expires_at=args.expires_at,
        issuer_private_key_pem=args.signing_key.read_bytes(), password=password,
        approved_tenant=args.approved_tenant,
        approved_kms_key_arn=args.approved_kms_key_arn,
        approved_key_pin=args.approved_key_pin,
    )
    print("Independent ciphertext origin receipt generated; no AWS calls.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
