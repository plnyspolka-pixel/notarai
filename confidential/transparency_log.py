"""Public, append-only transparency log of custodian-signed releases.

Stage 0 of docs/confidential-custody-samorzady.md (pkt 5.1 i 5.7): anyone can
download the log and verify it offline, with no AWS account and no permission
from the NotarAI operator.

What a verified log proves:
  - every entry carries a release signed by a custodian key whose fingerprint
    the verifier pinned out of band,
  - entries are hash-chained, so history cannot be rewritten, reordered or
    truncated without changing the head hash,
  - an earlier checkpoint kept by an independent witness is still a prefix of
    the log (no fork shown to different clients).

What it does NOT prove: the live KMS policy, real Nitro hardware attestation,
organisational independence of the custodian, or that the released code does
not leak. The report keeps those flags False.

Entries hold only fixed-format technical values. There is no free-text field,
so client data and personal data cannot enter the log.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from confidential.release_approval import canonical_bytes, public_key_fingerprint

ENTRY_SCHEMA = "notarai.confidential.transparency-entry.v1"
LOG_SCHEMA = "notarai.confidential.transparency-log.v1"
CHECKPOINT_SCHEMA = "notarai.confidential.transparency-checkpoint.v1"
_ENTRY_DOMAIN = b"NotarAI:confidential:transparency-entry:v1\x00"
GENESIS = "0" * 64
MAX_ENTRIES = 100_000

_ENTRY_FIELDS = frozenset({
    "schema", "index", "previous_hash", "kind", "source_commit",
    "recorded_at", "custody_public_key_sha256", "release",
})
_HEX64 = re.compile(r"^[a-f0-9]{64}$")
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_PAYLOAD_PATTERNS = {
    "tenant": re.compile(r"^[a-z0-9]{1,12}$"),
    "operator_account": re.compile(r"^\d{12}$"),
    "custody_account": re.compile(r"^\d{12}$"),
    "kms_key_arn": re.compile(
        r"^arn:aws:kms:eu-[a-z]+-\d:\d{12}:key/[a-f0-9-]{36}$"),
    "task_definition_arn": re.compile(
        r"^arn:aws:ecs:eu-[a-z]+-\d:\d{12}:task-definition/[A-Za-z0-9_-]{1,255}:\d{1,9}$"),
    "expected_pcr17": re.compile(r"^[a-f0-9]{96}$"),
    "image_sha256": _HEX64,
    "key_policy_sha256": _HEX64,
    "task_definition_sha256": _HEX64,
    "release_id": re.compile(r"^[a-f0-9]{32}$"),
    "issued_at": _UTC,
    "expires_at": _UTC,
}


class LogRejected(ValueError):
    """The transparency log, an entry or a checkpoint failed verification."""


def _time(value: object) -> datetime:
    if not isinstance(value, str) or _UTC.fullmatch(value) is None:
        raise LogRejected("timestamp must be UTC, format YYYY-MM-DDTHH:MM:SSZ")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        raise LogRejected("timestamp invalid") from None


def _check_release(envelope: object) -> dict:
    if not isinstance(envelope, dict) or set(envelope) != {"payload", "signature_b64"}:
        raise LogRejected("release envelope fields invalid")
    payload = envelope["payload"]
    try:
        canonical_bytes(payload)
    except ValueError:
        raise LogRejected("release payload fields invalid") from None
    for name, pattern in _PAYLOAD_PATTERNS.items():
        value = payload[name]
        if not isinstance(value, str) or pattern.fullmatch(value) is None:
            raise LogRejected(f"release field {name} has an unexpected format")
    if _time(payload["expires_at"]) <= _time(payload["issued_at"]):
        raise LogRejected("release validity window invalid")
    if not isinstance(envelope["signature_b64"], str):
        raise LogRejected("release signature missing")
    return payload


def _check_entry_shape(entry: object) -> dict:
    if not isinstance(entry, dict) or set(entry) != _ENTRY_FIELDS:
        raise LogRejected("entry fields invalid")
    if entry["schema"] != ENTRY_SCHEMA or entry["kind"] != "custody-release":
        raise LogRejected("entry schema or kind invalid")
    if type(entry["index"]) is not int or entry["index"] < 0:
        raise LogRejected("entry index invalid")
    for name in ("previous_hash", "custody_public_key_sha256"):
        if not isinstance(entry[name], str) or _HEX64.fullmatch(entry[name]) is None:
            raise LogRejected(f"entry field {name} invalid")
    if (not isinstance(entry["source_commit"], str)
            or re.fullmatch(r"[a-f0-9]{40}", entry["source_commit"]) is None):
        raise LogRejected("entry source_commit must be a full git commit id")
    _time(entry["recorded_at"])
    _check_release(entry["release"])
    return entry


def entry_hash(entry: Mapping) -> str:
    """SHA-256 over a domain-separated canonical encoding of the whole entry."""
    _check_entry_shape(entry)
    encoded = json.dumps(entry, sort_keys=True, ensure_ascii=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(_ENTRY_DOMAIN + encoded).hexdigest()


def _trusted(keys: Mapping[str, bytes]) -> dict:
    """Pinned custodian keys: {sha256 fingerprint pinned out of band: PEM}."""
    if not isinstance(keys, Mapping) or not keys:
        raise LogRejected("at least one independently pinned custodian key is required")
    loaded = {}
    for pinned, pem in keys.items():
        if not isinstance(pinned, str) or _HEX64.fullmatch(pinned) is None:
            raise LogRejected("pinned custodian fingerprint invalid")
        try:
            actual = public_key_fingerprint(pem)
        except ValueError:
            raise LogRejected("custodian public key invalid") from None
        if actual != pinned:
            raise LogRejected("custodian public key differs from the pinned fingerprint")
        loaded[pinned] = serialization.load_pem_public_key(pem)
    return loaded


def _verify_signature(entry: Mapping, keys: Mapping) -> None:
    public = keys.get(entry["custody_public_key_sha256"])
    if public is None:
        raise LogRejected("entry signed by a custodian key that is not pinned")
    try:
        signature = base64.b64decode(entry["release"]["signature_b64"], validate=True)
    except (ValueError, binascii.Error):
        raise LogRejected("release signature encoding invalid") from None
    try:
        public.verify(signature, canonical_bytes(entry["release"]["payload"]),
                      ec.ECDSA(hashes.SHA256()))
    except (InvalidSignature, TypeError, ValueError):
        raise LogRejected("custodian release signature invalid") from None


def verify_log(log: Mapping, *, trusted_keys: Mapping[str, bytes],
               previous_checkpoint: Mapping | None = None) -> dict:
    """Verify the whole log offline. Raises LogRejected on any inconsistency."""
    if not isinstance(log, dict) or set(log) != {"schema", "entries"}:
        raise LogRejected("log fields invalid")
    entries = log["entries"]
    if log["schema"] != LOG_SCHEMA or not isinstance(entries, list):
        raise LogRejected("log schema invalid")
    if len(entries) > MAX_ENTRIES:
        raise LogRejected("log too large")
    keys = _trusted(trusted_keys)

    previous, last_recorded, seen, hashes_by_index, summary = GENESIS, None, set(), [], []
    for position, entry in enumerate(entries):
        _check_entry_shape(entry)
        if entry["index"] != position:
            raise LogRejected("entry index out of sequence")
        if entry["previous_hash"] != previous:
            raise LogRejected("hash chain broken")
        payload = entry["release"]["payload"]
        recorded = _time(entry["recorded_at"])
        if last_recorded is not None and recorded < last_recorded:
            raise LogRejected("entries are not in chronological order")
        if recorded < _time(payload["issued_at"]):
            raise LogRejected("entry recorded before its release was issued")
        if payload["release_id"] in seen:
            raise LogRejected("release recorded twice")
        seen.add(payload["release_id"])
        _verify_signature(entry, keys)
        previous, last_recorded = entry_hash(entry), recorded
        hashes_by_index.append(previous)
        summary.append({
            "index": position, "entry_hash": previous,
            "recorded_at": entry["recorded_at"],
            "source_commit": entry["source_commit"],
            "tenant": payload["tenant"],
            "image_sha256": payload["image_sha256"],
            "expected_pcr17": payload["expected_pcr17"],
            "key_policy_sha256": payload["key_policy_sha256"],
            "task_definition_arn": payload["task_definition_arn"],
            "kms_key_arn": payload["kms_key_arn"],
            "custody_public_key_sha256": entry["custody_public_key_sha256"],
        })

    consistent = None
    if previous_checkpoint is not None:
        old = _check_checkpoint(previous_checkpoint)
        if old["size"] > len(entries):
            raise LogRejected("log is shorter than the earlier checkpoint: history removed")
        expected = hashes_by_index[old["size"] - 1] if old["size"] else GENESIS
        if expected != old["head_hash"]:
            raise LogRejected("log does not extend the earlier checkpoint: history rewritten")
        consistent = True

    return {
        "schema": "notarai.confidential.transparency-report.v1",
        "size": len(entries),
        "head_hash": previous,
        "entries": summary,
        "signatures_verified": True,
        "hash_chain_verified": True,
        "extends_previous_checkpoint": consistent,
        # A log is evidence of what was approved, never of the live system.
        "live_kms_policy_verified": False,
        "hardware_nitro_attestation_verified": False,
        "zero_operator_access_proven": False,
    }


def _check_checkpoint(checkpoint: object) -> dict:
    if not isinstance(checkpoint, dict) or set(checkpoint) != {"schema", "size", "head_hash"}:
        raise LogRejected("checkpoint fields invalid")
    if (checkpoint["schema"] != CHECKPOINT_SCHEMA
            or type(checkpoint["size"]) is not int or checkpoint["size"] < 0
            or not isinstance(checkpoint["head_hash"], str)
            or _HEX64.fullmatch(checkpoint["head_hash"]) is None
            or (checkpoint["size"] == 0) != (checkpoint["head_hash"] == GENESIS)):
        raise LogRejected("checkpoint invalid")
    return checkpoint


def checkpoint(report: Mapping) -> dict:
    """The small value an independent witness stores to detect later rewrites."""
    return _check_checkpoint({"schema": CHECKPOINT_SCHEMA, "size": report["size"],
                              "head_hash": report["head_hash"]})


def empty_log() -> dict:
    return {"schema": LOG_SCHEMA, "entries": []}


def append_release(log: Mapping, *, release: Mapping, source_commit: str,
                   custody_public_key_sha256: str, recorded_at: datetime,
                   trusted_keys: Mapping[str, bytes]) -> dict:
    """Return a new log with one more entry. The input log is not modified.

    The existing log and the new entry are fully verified first, so a release
    that would not verify for the public can never be published.
    """
    report = verify_log(log, trusted_keys=trusted_keys)
    if not isinstance(recorded_at, datetime) or recorded_at.tzinfo is None:
        raise LogRejected("UTC clock required")
    entry = {
        "schema": ENTRY_SCHEMA,
        "index": report["size"],
        "previous_hash": report["head_hash"],
        "kind": "custody-release",
        "source_commit": source_commit,
        "recorded_at": recorded_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "custody_public_key_sha256": custody_public_key_sha256,
        "release": {"payload": dict(release.get("payload") or {}),
                    "signature_b64": release.get("signature_b64")},
    }
    extended = {"schema": LOG_SCHEMA, "entries": [*log["entries"], entry]}
    verify_log(extended, trusted_keys=trusted_keys)
    return extended


def load_json(text: str, *, limit: int = 64 * 1024 * 1024) -> object:
    if not isinstance(text, str) or len(text) > limit:
        raise LogRejected("input too large")
    try:
        return json.loads(text)
    except ValueError:
        raise LogRejected("input is not valid JSON") from None


__all__: Sequence[str] = (
    "LogRejected", "append_release", "checkpoint", "empty_log", "entry_hash",
    "load_json", "verify_log",
)
