"""Offline-only fixture signer for NotarAI VE diagnostic jobs.

NOT a production endpoint. The two allowed operations do not read client data.
No key, password, text, or notarisation payload is stored in the repository.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import time

OPERATIONS = {"probe.session", "probe.notepad"}
TENANT_PATTERN = re.compile(r"[a-z][a-z0-9]{2,11}\Z")


def canonical(job: dict) -> bytes:
    fields = (
        "notarai-ve/v1",
        str(job["schema"]),
        job["tenantId"],
        job["jobId"],
        job["operation"],
        str(job["issuedAtUnix"]),
        str(job["expiresAtUnix"]),
        job["nonce"],
    )
    return "\n".join(fields).encode("utf-8")


def make_diagnostic_job(tenant: str, operation: str, key: bytes, *, now: int | None = None) -> dict:
    if not TENANT_PATTERN.fullmatch(tenant):
        raise ValueError("tenant must be a synthetic lowercase ID")
    if operation not in OPERATIONS:
        raise ValueError("only read-only diagnostic operations are permitted")
    if len(key) < 32:
        raise ValueError("HMAC key must contain 32+ bytes")
    if now is None:
        now = int(time.time())
    job = {
        "schema": 1,
        "tenantId": tenant,
        "jobId": secrets.token_hex(16),
        "operation": operation,
        "issuedAtUnix": now,
        "expiresAtUnix": now + 120,
        "nonce": secrets.token_hex(16),
    }
    job["signature"] = hmac.new(key, canonical(job), hashlib.sha256).hexdigest()
    return job


def write_private_file(path: Path, contents: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(contents)
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Create offline NotarAI VE diagnostic fixture")
    parser.add_argument("--tenant", default="pilot01")
    parser.add_argument("--operation", choices=sorted(OPERATIONS), default="probe.session")
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--job-file", type=Path, required=True)
    parser.add_argument("--generate-disposable-key", action="store_true")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    for path in (args.key_file, args.job_file):
        if path.resolve().is_relative_to(repo):
            parser.error("Do not write keys or fixture jobs inside the Git repository")
    if args.generate_disposable_key:
        write_private_file(args.key_file, secrets.token_bytes(32))
        print("Created disposable test key outside repo; protect its Windows ACL separately")
    key = args.key_file.read_bytes()
    job = make_diagnostic_job(args.tenant, args.operation, key)
    write_private_file(args.job_file, (json.dumps(job, separators=(",", ":"), sort_keys=True) + "\n").encode())
    print("Created short-lived, signed diagnostic job (no data payload)")


if __name__ == "__main__":
    main()
