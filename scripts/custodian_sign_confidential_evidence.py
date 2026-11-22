#!/usr/bin/env python3
"""SEC-11 independent evidence signer: offline, custodian-owned workstation.

Required: encrypted PKCS#8 Ed25519 PEM private key with owner-only file
permissions; password read from a dedicated file descriptor, never argv/env.
Never execute on NotarAI operator systems. No key generation in this tool.
"""
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from confidential.signed_evidence import (
    canonical_manifest, public_fingerprint, sign_manifest,
)


def sign_from_files(*, manifest_path: Path, key_path: Path, output_path: Path,
                    password_fd: int) -> str:
    """Sign a strict metadata-only manifest and create a new 0600 bundle."""
    if type(password_fd) is not int or password_fd < 3:
        raise ValueError("password pipe descriptor required")
    fd_mode = os.fstat(password_fd).st_mode
    if not (stat.S_ISFIFO(fd_mode) or stat.S_ISSOCK(fd_mode)):
        raise ValueError("password must come from transient pipe or socket")
    if manifest_path.is_symlink() or key_path.is_symlink() or output_path.is_symlink():
        raise ValueError("symlink not allowed")
    if key_path.resolve() == output_path.resolve():
        raise ValueError("private key cannot be overwritten")
    info = key_path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise ValueError("private key must be owner-only regular file")
    if not 1 <= info.st_size <= 16384:
        raise ValueError("private key length invalid")
    if not manifest_path.is_file() or not 1 <= manifest_path.stat().st_size <= 1024 * 1024:
        raise ValueError("manifest length invalid")
    raw = manifest_path.read_text(encoding="utf-8")
    manifest = json.loads(raw)
    canonical_manifest(manifest)
    password = os.read(password_fd, 4097)
    if not password or len(password) > 4096 or not password.endswith(b"\n"):
        raise ValueError("password pipe invalid")
    # Password bytes never enter argv/env/GitHub logs. Password should be
    # provisioned in a local vault and forwarded directly to the FD.
    password = password[:-1]
    key = serialization.load_pem_private_key(key_path.read_bytes(), password=password)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("Ed25519 private key required")
    bundle = sign_manifest(manifest, key)
    pub = key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    pin = public_fingerprint(pub)
    blob = json.dumps(bundle, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"
    # O_EXCL prevents modifying old signed evidence or overwriting a symlink.
    fd = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(blob)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        # Never delete an existing path; file was created exclusively here.
        try:
            output_path.unlink()
        except OSError:
            pass
        raise
    return pin


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--encrypted-key", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--password-fd", type=int, required=True,
                        help="dedicated FD >2 with passphrase + newline; not argv/env")
    args = parser.parse_args(argv)
    try:
        pin = sign_from_files(
            manifest_path=args.manifest, key_path=args.encrypted_key,
            output_path=args.output, password_fd=args.password_fd,
        )
        # Public pin is safe but still MUST be distributed independently.
        print(json.dumps({
            "signed_bundle_written": True, "public_fingerprint": pin,
            "zero_operator_access_proven": False,
        }, sort_keys=True))
        return 0
    except Exception:
        print(json.dumps({
            "signed_bundle_written": False,
            "error": "INDEPENDENT_SIGNING_FAILED",
            "zero_operator_access_proven": False,
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
