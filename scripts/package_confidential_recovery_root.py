"""Build an independently pinned custodian+trustee recovery root for Nitro.

Not a recovery operation and not a KMS grant. Public keys and both out-of-band
SPKI SHA-256 digests MUST be reviewed by independent custody before releasing
a measured Nitro image. Never publish private keys or trust an operator-provided
fingerprint as independent evidence.
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

_KMS = re.compile(r"^arn:aws:kms:eu-central-1:[0-9]{12}:key/[A-Za-z0-9-]+$")
_TENANT = re.compile(r"^[a-z0-9]{1,12}$")
_PIN = re.compile(r"^[A-Za-z0-9+/]{43}=$")
_SHA = re.compile(r"^[a-f0-9]{64}$")


def _pin_ed25519(pem: bytes, expected: str) -> bytes:
    if not isinstance(expected, str) or not _SHA.fullmatch(expected):
        raise ValueError("unverified signer key fingerprint")
    key = serialization.load_pem_public_key(pem)
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("recovery signer must use Ed25519")
    der = key.public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    if hashlib.sha256(der).hexdigest() != expected:
        raise ValueError("independent signer public key pin mismatch")
    return key.public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )


def package_recovery_root(
    *, output_file: Path, tenant: str, old_key_arn: str, old_key_pin: str,
    custodian_public_key_pem: bytes, trustee_public_key_pem: bytes,
    custodian_spki_sha256: str, trustee_spki_sha256: str,
    expires_at: int,
) -> dict:
    if (
        not isinstance(tenant, str) or not _TENANT.fullmatch(tenant)
        or not isinstance(old_key_arn, str) or not _KMS.fullmatch(old_key_arn)
        or not isinstance(old_key_pin, str) or not _PIN.fullmatch(old_key_pin)
        or type(expires_at) is not int or not 0 < expires_at < 4102444800
    ):
        raise ValueError("invalid recovery root scope")
    custodian = _pin_ed25519(custodian_public_key_pem, custodian_spki_sha256)
    trustee = _pin_ed25519(trustee_public_key_pem, trustee_spki_sha256)
    if custodian == trustee:
        raise ValueError("recovery must use two different external signers")
    root = {
        "schema": "notarai.recovery-root.v1",
        "tenant_id": tenant, "old_key_arn": old_key_arn,
        "old_key_pin": old_key_pin,
        "custodian_public_key_b64": base64.b64encode(custodian).decode("ascii"),
        "trustee_public_key_b64": base64.b64encode(trustee).decode("ascii"),
        "expires_at": expires_at,
    }
    wire = json.dumps(root, separators=(",", ":"), sort_keys=True).encode("ascii")
    if len(wire) > 2048:
        raise ValueError("recovery root exceeds guest limit")
    fd = os.open(str(output_file), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as dest:
        dest.write(wire)
        dest.flush()
        os.fsync(dest.fileno())
    return {"root_sha256": hashlib.sha256(wire).hexdigest(),
            "two_signers_independently_pinned": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--old-kms-key-arn", required=True)
    parser.add_argument("--old-kms-public-key-pin", required=True)
    parser.add_argument("--custodian-public-key", type=Path, required=True)
    parser.add_argument("--trustee-public-key", type=Path, required=True)
    parser.add_argument("--independent-custodian-spki-sha256", required=True)
    parser.add_argument("--independent-trustee-spki-sha256", required=True)
    parser.add_argument("--expires-at", type=int, required=True)
    args = parser.parse_args()
    package_recovery_root(
        output_file=args.output, tenant=args.tenant,
        old_key_arn=args.old_kms_key_arn, old_key_pin=args.old_kms_public_key_pin,
        custodian_public_key_pem=args.custodian_public_key.read_bytes(),
        trustee_public_key_pem=args.trustee_public_key.read_bytes(),
        custodian_spki_sha256=args.independent_custodian_spki_sha256,
        trustee_spki_sha256=args.independent_trustee_spki_sha256,
        expires_at=args.expires_at,
    )
    print("Two-party recovery trust root packaged; no key released or migrated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
