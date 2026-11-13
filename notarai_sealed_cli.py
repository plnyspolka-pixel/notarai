"""NotarAI Sealed, LOCAL command-line prototype (AES-256-GCM).

Encrypts and decrypts entirely on the notary's device. Never sends plaintext
or passphrase to NotarAI, AWS, Bedrock or any other network endpoint.
This is not a signed production application or a key-management solution.
"""
from __future__ import annotations

import argparse
import base64
import getpass
import json
import os
import re
import sys
import uuid
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

SCHEMA = "notarai.sealed.v1"
ROUNDS = 600_000
LIMIT = 4 * 1024 * 1024
RE_B64 = re.compile(r"^[A-Za-z0-9_-]+$")


def _encoded(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _decoded(value: str, expected: int | None = None) -> bytes:
    if not isinstance(value, str) or not RE_B64.fullmatch(value):
        raise ValueError("Invalid base64url")
    data = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    if _encoded(data) != value:
        raise ValueError("Non-canonical base64url")
    if expected is not None and len(data) != expected:
        raise ValueError("Incorrect metadata length")
    return data


def _aad(document_id: str, tenant_ref: str) -> bytes:
    if not isinstance(tenant_ref, str) or not tenant_ref or len(tenant_ref) > 120 or \
        any(ord(c) < 32 or ord(c) == 127 for c in tenant_ref):
        raise ValueError("Invalid office reference")
    # WebCrypto prototype uses the canonical v4 UUID format.
    parsed = uuid.UUID(document_id)
    if str(parsed) != document_id or parsed.version != 4:
        raise ValueError("Document ID must be a canonical UUIDv4")
    return (SCHEMA + "\x00" + tenant_ref + "\x00" + document_id).encode("utf-8")


def _key(password: str, salt: bytes) -> bytes:
    if not isinstance(password, str) or not 16 <= len(password) <= 1024:
        raise ValueError("Passphrase must have at least 16 characters")
    return PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32,
        salt=salt, iterations=ROUNDS,
    ).derive(password.encode("utf-8"))


def seal_bytes(data: bytes, password: str, tenant_ref: str,
               document_id: str | None = None) -> dict:
    """Compatible with static/sealed-client.mjs; password is never persisted."""
    if not isinstance(data, bytes) or not 1 <= len(data) <= LIMIT:
        raise ValueError("Document size must be 1 byte - 4 MiB")
    document_id = document_id or str(uuid.uuid4())
    aad = _aad(document_id, tenant_ref)
    salt = os.urandom(16)
    nonce = os.urandom(12)
    ciphertext = AESGCM(_key(password, salt)).encrypt(nonce, data, aad)
    return {
        "schema": SCHEMA, "documentId": document_id, "tenantRef": tenant_ref,
        "algorithm": "AES-256-GCM", "kdf": "PBKDF2-SHA256",
        "iterations": ROUNDS, "salt": _encoded(salt),
        "nonce": _encoded(nonce), "ciphertext": _encoded(ciphertext)
    }


def open_envelope(envelope: dict, password: str,
                  expected_office: str | None = None) -> bytes:
    if not isinstance(envelope, dict) or envelope.get("schema") != SCHEMA or \
       envelope.get("algorithm") != "AES-256-GCM" or \
       envelope.get("kdf") != "PBKDF2-SHA256" or \
       envelope.get("iterations") != ROUNDS:
        raise ValueError("Unsupported Sealed format")
    tenant = envelope.get("tenantRef")
    if expected_office is not None and tenant != expected_office:
        raise ValueError("Envelope belongs to another office")
    aad = _aad(envelope["documentId"], tenant)
    salt = _decoded(envelope["salt"], 16)
    nonce = _decoded(envelope["nonce"], 12)
    ciphertext = _decoded(envelope["ciphertext"])
    if not 17 <= len(ciphertext) <= LIMIT + 16:
        raise ValueError("Invalid ciphertext size")
    # InvalidTag means wrong password, wrong office/document AAD, or tampering.
    return AESGCM(_key(password, salt)).decrypt(nonce, ciphertext, aad)


def _write_new(path: Path, data: bytes) -> None:
    # Refuse overwrite rather than risking destructive loss of source files.
    with path.open("xb") as output:
        output.write(data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline NotarAI Sealed POC")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--encrypt", action="store_true")
    mode.add_argument("--decrypt", action="store_true")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--office", required=True, help="Internal office reference, not a secret")
    args = parser.parse_args(argv)
    source, destination = Path(args.input), Path(args.output)
    if source.resolve() == destination.resolve():
        parser.error("Input and output cannot be the same file")
    if destination.exists():
        parser.error("Output already exists; refusing overwrite")
    password = getpass.getpass("Sealed passphrase (not transmitted): ")
    try:
        if args.encrypt:
            data = source.read_bytes()
            envelope = seal_bytes(data, password, args.office)
            encoded = json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            _write_new(destination, encoded)
        else:
            encoded = source.read_bytes()
            if len(encoded) > 6_000_000:
                raise ValueError("Envelope exceeds POC size limit")
            envelope = json.loads(encoded)
            result = open_envelope(envelope, password, expected_office=args.office)
            _write_new(destination, result)
    except (ValueError, InvalidTag, UnicodeError, OSError) as error:
        # Avoid printing document content, keys or raw data to the terminal.
        print("Operation rejected: invalid format, key, file or permissions", file=sys.stderr)
        return 1
    print("Sealed operation finished. No network calls were made.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
