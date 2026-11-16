"""LAB-ONLY audit evidence protocol: allowlisted metadata, SHA-384 and signed checkpoints.

No signing secrets are held by this module; production signing and witnessing
must be external (KMS/HSM and independent WORM witness). The in-memory ledger
is intentionally unsuitable for production traffic, concurrent writes or
recovery. It exists to verify exact semantics with synthetic adversarial tests.
"""
from __future__ import annotations
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Callable

ALLOWED_KEYS = frozenset({
    "tenant_id", "request_id", "purpose", "classification",
    "region", "model", "event", "input_tokens", "output_tokens",
})
ALLOWED_EVENTS = frozenset({"authorized", "failed", "completed"})
HEX384 = re.compile(r"^[0-9a-f]{96}$")


class IntegrityError(ValueError):
    pass


def canonical(item: Any) -> bytes:
    return json.dumps(item, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(item: Any) -> str:
    return hashlib.sha384(canonical(item)).hexdigest()


def _metadata(event: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(event, dict) or not event or set(event) - ALLOWED_KEYS:
        raise IntegrityError("Forbidden audit field")
    for key in ("tenant_id", "request_id", "purpose", "classification", "region", "model"):
        value = event.get(key)
        if not isinstance(value, str) or not 1 <= len(value) <= 140:
            raise IntegrityError("Incomplete or oversized metadata")
    if event.get("event") not in ALLOWED_EVENTS:
        raise IntegrityError("Invalid event")
    for key in ("input_tokens", "output_tokens"):
        if key in event and (type(event[key]) is not int or event[key] < 0):
            raise IntegrityError("Invalid token count")
    return dict(event)


def _make_row(seq: int, prev: str, at: str, event: dict[str, Any]) -> dict:
    item = {"schema": "private-ai-event-v1", "seq": seq, "prev_hash": prev,
            "at": at, "event": _metadata(event)}
    return {**item, "hash": digest(item)}


def verify_chain(rows: list[dict]) -> dict[str, Any]:
    previous = "0" * 96
    for i, row in enumerate(rows, start=1):
        if not isinstance(row, dict) or set(row) != {
            "schema", "seq", "prev_hash", "at", "event", "hash"
        }:
            raise IntegrityError("Malformed ledger entry")
        if row["schema"] != "private-ai-event-v1" or row["seq"] != i:
            raise IntegrityError("Invalid sequence")
        if row["prev_hash"] != previous:
            raise IntegrityError("Broken link / reordering")
        if not isinstance(row["at"], str) or not row["at"]:
            raise IntegrityError("Invalid timestamp")
        _metadata(row["event"])
        expected = digest({key: value for key, value in row.items() if key != "hash"})
        if row["hash"] != expected:
            raise IntegrityError("Tampered metadata")
        previous = expected
    return {"count": len(rows), "head": previous}


class LabLedger:
    """Test fixture ONLY: no independent witness, no durable atomic storage."""
    def __init__(self):
        self.rows: list[dict] = []

    def record(self, event: dict[str, Any]) -> None:
        _metadata(event)
        state = verify_chain(self.rows)
        row = _make_row(
            state["count"] + 1, state["head"],
            datetime.now(timezone.utc).isoformat(), event,
        )
        self.rows.append(row)


def make_checkpoint(rows: list[dict], key_id: str,
                    sign: Callable[[bytes], bytes]) -> dict:
    if not isinstance(key_id, str) or not re.fullmatch(r"[a-zA-Z0-9._:-]{3,120}", key_id):
        raise IntegrityError("Invalid signer identity")
    statement = {
        "schema": "private-ai-checkpoint-v1", "key_id": key_id,
        **verify_chain(rows),
    }
    signature = sign(canonical(statement))
    if not isinstance(signature, bytes) or not signature:
        raise IntegrityError("Signer refused checkpoint")
    return {"statement": statement, "signature_hex": signature.hex()}


def verify_checkpoint(rows: list[dict], checkpoint: dict,
                      verify: Callable[[str, bytes, bytes], bool]) -> None:
    if not isinstance(checkpoint, dict) or set(checkpoint) != {"statement", "signature_hex"}:
        raise IntegrityError("Malformed checkpoint")
    statement = checkpoint["statement"]
    if not isinstance(statement, dict) or set(statement) != {"schema", "key_id", "count", "head"}:
        raise IntegrityError("Malformed signed statement")
    if statement["schema"] != "private-ai-checkpoint-v1":
        raise IntegrityError("Unrecognized receipt")
    current = verify_chain(rows)
    if statement["count"] != current["count"] or statement["head"] != current["head"]:
        raise IntegrityError("Rollback, truncation or divergence detected")
    try:
        sig = bytes.fromhex(checkpoint["signature_hex"])
    except (TypeError, ValueError) as e:
        raise IntegrityError("Invalid signature encoding") from e
    if not verify(statement["key_id"], canonical(statement), sig):
        raise IntegrityError("Checkpoint signature rejected")
