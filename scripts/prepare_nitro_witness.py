"""SEC-07: prepare an identical offline witness signing payload.

This does NOT sign, produce keys, access AWS, run negative trials, or establish
a hardware result. Both independent witnesses must separately obtain trusted
evidence, review it and sign these exact domain-separated bytes out of band.

Example (all files OUTSIDE the repository):
  python scripts/prepare_nitro_witness.py \
    --matrix /secure/negative-matrix.json \
    --observed-at 2026-11-22T09:00:00Z \
    --expires-at 2026-11-22T10:00:00Z \
    --payload-out /secure/witness.json \
    --signing-bytes-out /secure/witness.signing.bin

  openssl dgst -sha256 -sign /private/custodian-p256.pem \
    -out /secure/custodian.der /secure/witness.signing.bin
  openssl base64 -A -in /secure/custodian.der -out /secure/custodian.b64

Never store private keys in the NotarAI repository or operator account.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from confidential.nitro_denial_matrix import (
    CASES, KMS_CASES, DenialEvidenceRejected, validate_matrix,
)
from confidential.nitro_witness import (
    _matrix_hash, canonical_witness, validate_witness_payload,
)

_MAX_BYTES = 32 * 1024


def generate_payload(matrix: dict, observed_at: str,
                     expires_at: str) -> tuple[dict, bytes]:
    """A reproducible unsigned payload, with no self-claimed hardware PASS."""
    validate_matrix(matrix)
    payload = {
        "schema": "notarai.confidential.nitro-denial-witness.v1",
        "tenant": matrix["tenant"],
        "job_id": matrix["job_id"],
        "matrix_sha256": _matrix_hash(matrix),
        "observed_at": observed_at,
        "expires_at": expires_at,
        "denied_event_ids": {
            case: matrix["trials"][case]["event_id"]
            for case in sorted(KMS_CASES)
        },
        "trial_receipt_sha256": {
            case: matrix["trials"][case]["receipt_sha256"]
            for case in CASES
        },
        "result": "SIX_DENIALS_WITNESSED",
        "submitted": False,
        "signed": False,
    }
    return payload, validate_witness_payload(payload, matrix)


def _secure_new_file(path: str, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
    except Exception:
        Path(path).unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", required=True)
    parser.add_argument("--observed-at", required=True)
    parser.add_argument("--expires-at", required=True)
    parser.add_argument("--payload-out", required=True)
    parser.add_argument("--signing-bytes-out", required=True)
    args = parser.parse_args()
    try:
        if Path(args.payload_out).resolve() == Path(args.signing_bytes_out).resolve():
            raise DenialEvidenceRejected("two separate output files required")
        with Path(args.matrix).open("rb") as matrix_file:
            raw = matrix_file.read(_MAX_BYTES + 1)
        if not raw or len(raw) > _MAX_BYTES:
            raise DenialEvidenceRejected("matrix file invalid")
        matrix = json.loads(raw)
        payload, signing_bytes = generate_payload(
            matrix, args.observed_at, args.expires_at,
        )
        formatted = json.dumps(
            payload, sort_keys=True, indent=2, ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8") + b"\n"
        if Path(args.payload_out).exists() or Path(args.signing_bytes_out).exists():
            raise DenialEvidenceRejected("cannot overwrite an existing witness file")
        _secure_new_file(args.payload_out, formatted)
        try:
            _secure_new_file(args.signing_bytes_out, signing_bytes)
        except Exception:
            Path(args.payload_out).unlink(missing_ok=True)
            raise
        # Explicit machine-checkable output; creating files is NOT a proof.
        print(json.dumps({
            "status": "PREPARED_NOT_SIGNED",
            "witness_hardware_verified": False,
            "two_independent_signatures_required": True,
            "signing_bytes_length": len(signing_bytes),
        }, sort_keys=True))
        return 0
    except Exception:
        print(json.dumps({
            "status": "BLOCKED",
            "hardware_attestation_verified": False,
            "production_enabled": False,
            "reason": "witness_preparation_rejected",
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
