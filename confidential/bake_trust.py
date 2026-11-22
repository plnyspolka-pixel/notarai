"""Build-time only: bake the public Ed25519 notary-origin trust anchor into Nitro image.

No default key; no private keys. The resulting OCI image digest MUST be
independently pinned by the customer's signed PCR/image manifest.
"""
from __future__ import annotations

import base64
import binascii
import json
import os
import re
from pathlib import Path


def bake(*, issuer_id: str, signing_public_b64: str,
         target: Path = Path("/opt/notarai/trust/customer-origin-v1.json")) -> None:
    if not isinstance(issuer_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", issuer_id):
        raise ValueError("missing or invalid build-time trusted origin issuer")
    try:
        key = base64.b64decode(signing_public_b64, validate=True)
    except (ValueError, binascii.Error, TypeError):
        raise ValueError("invalid origin trust anchor") from None
    if len(key) != 32 or base64.b64encode(key).decode("ascii") != signing_public_b64:
        raise ValueError("invalid Ed25519 public key length")
    data = json.dumps({
        "schema": "notarai.customer-origin-trust.v1",
        "issuer_id": issuer_id,
        "public_ed25519_b64": signing_public_b64,
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o644)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data + b"\n")


if __name__ == "__main__":
    bake(
        issuer_id=os.environ.get("TRUSTED_ORIGIN_ISSUER_ID", ""),
        signing_public_b64=os.environ.get("TRUSTED_ORIGIN_PUBLIC_B64", ""),
    )
