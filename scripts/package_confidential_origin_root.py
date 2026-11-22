"""Prepare the independent issuer trust root for one Nitro guest RELEASE.

Run and review OUTSIDE the NotarAI operator account. The public key digest
must come from a separately trusted notary/custodian channel. This does NOT
sign or approve the Docker image. Only a custodian-approved Nitro image/PCR
and independently held KMS policy may turn this file into a trust anchor.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

_TENANT = re.compile(r"^[a-z0-9]{1,12}$")
_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
_KMS = re.compile(r"^arn:aws:kms:eu-central-1:[0-9]{12}:key/[A-Za-z0-9-]+$")
_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_PIN = re.compile(r"^[A-Za-z0-9+/]{43}=$")


def package_origin_root(
    *, destination: Path, tenant_id: str, issuer_id: str,
    issuer_public_key_pem: bytes, independently_pinned_issuer_spki_sha256: str,
    kms_key_arn: str, kms_public_key_sha256: str, expires_at: int,
) -> dict:
    if (
        not isinstance(tenant_id, str) or not _TENANT.fullmatch(tenant_id)
        or not isinstance(issuer_id, str) or not _ID.fullmatch(issuer_id)
        or not isinstance(kms_key_arn, str) or not _KMS.fullmatch(kms_key_arn)
        or not isinstance(kms_public_key_sha256, str)
        or not _PIN.fullmatch(kms_public_key_sha256)
        or not isinstance(independently_pinned_issuer_spki_sha256, str)
        or not _DIGEST.fullmatch(independently_pinned_issuer_spki_sha256)
        or type(expires_at) is not int or not 0 < expires_at < 4102444800
    ):
        raise ValueError("invalid independently pinned issuer root")
    issuer = serialization.load_pem_public_key(issuer_public_key_pem)
    if not isinstance(issuer, Ed25519PublicKey):
        raise ValueError("issuer must be Ed25519")
    spki = issuer.public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    digest = hashlib.sha256(spki).hexdigest()
    if digest != independently_pinned_issuer_spki_sha256:
        raise ValueError("independent issuer SPKI pin mismatch")
    raw_key = issuer.public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )
    root = {
        "schema": "notarai.origin-root.v1",
        "tenant_id": tenant_id, "issuer_id": issuer_id,
        "issuer_public_key_b64": base64.b64encode(raw_key).decode("ascii"),
        "kms_key_arn": kms_key_arn,
        "public_key_sha256": kms_public_key_sha256,
        "expires_at": expires_at,
    }
    blob = json.dumps(root, sort_keys=True, separators=(",", ":")).encode("ascii")
    if len(blob) > 2048:
        raise ValueError("origin root exceeds guest limit")
    fd = os.open(str(destination), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as output:
        output.write(blob)
        output.flush()
        os.fsync(output.fileno())
    return {"issuer_spki_sha256": digest, "root_sha256": hashlib.sha256(blob).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--issuer", required=True)
    parser.add_argument("--issuer-public-key", required=True, type=Path)
    parser.add_argument("--independent-issuer-spki-sha256", required=True)
    parser.add_argument("--kms-key-arn", required=True)
    parser.add_argument("--kms-key-pin", required=True)
    parser.add_argument("--expires-at", type=int, required=True)
    args = parser.parse_args()
    package_origin_root(
        destination=args.output, tenant_id=args.tenant, issuer_id=args.issuer,
        issuer_public_key_pem=args.issuer_public_key.read_bytes(),
        independently_pinned_issuer_spki_sha256=args.independent_issuer_spki_sha256,
        kms_key_arn=args.kms_key_arn, kms_public_key_sha256=args.kms_key_pin,
        expires_at=args.expires_at,
    )
    print("Independent public trust root prepared; not yet part of an approved image.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
