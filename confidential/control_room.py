"""Read-only control room for synthetic Confidential Browser AUTO previews.

This is NOT an approval or a retry/dispatch API. It reads only a fixed
projection of job metadata indexed by an independently configured
DynamoDB GSI, never S3 objects, documents, personal data, or signatures.
DynamoDB GSI is eventually consistent; its results are informational only.
"""
from __future__ import annotations

import re
import time
from collections import Counter
from dataclasses import dataclass

_TENANT = re.compile(r"^[a-z0-9]{1,12}$")
_JOB = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
_STATES = frozenset({
    "queued", "queue_uncertain", "running", "retryable",
    "preview_completed", "needs_review",
})
_LIMITS = frozenset({5, 10, 20})
_STALE_QUEUED_SECONDS = 15 * 60
_STALE_RETRYABLE_SECONDS = 15 * 60


class ControlRoomRejected(ValueError):
    """Sanitized denial; never include AWS payloads or job data."""


def authorized_notary(account: object) -> bool:
    """Do not infer authorization from a login or a self-asserted UI role."""
    if not isinstance(account, dict):
        return False
    return (
        account.get("rola") == "wlasciciel"
        or account.get("stanowisko") == "notariusz"
    )


def _number(raw: object, *, maximum: int = 2**53 - 1) -> int:
    if (
        not isinstance(raw, str) or
        not raw.isascii() or
        not raw.isdecimal() or
        len(raw) > 20
    ):
        raise ControlRoomRejected("invalid metadata timestamp or counter")
    parsed = int(raw)
    if parsed < 0 or parsed > maximum:
        raise ControlRoomRejected("metadata outside allowed range")
    return parsed


def _s(item: dict, key: str) -> str:
    cell = item.get(key)
    value = cell.get("S") if isinstance(cell, dict) else None
    if not isinstance(value, str):
        raise ControlRoomRejected("untrusted job metadata")
    return value


def _n(item: dict, key: str) -> int:
    cell = item.get(key)
    if not isinstance(cell, dict):
        raise ControlRoomRejected("untrusted job metadata")
    return _number(cell.get("N"))


@dataclass(frozen=True)
class ControlRoom:
    """An exact-tenant metadata query; no scan or cross-tenant listing."""

    ddb: object
    tenant: str

    def __post_init__(self) -> None:
        if not isinstance(self.tenant, str) or not _TENANT.fullmatch(self.tenant):
            raise ControlRoomRejected("invalid tenant scope")

    @property
    def table(self) -> str:
        return "notarai-confidential-jobs-" + self.tenant

    def recent(self, *, limit: int = 10, now: int | None = None) -> dict:
        if type(limit) is not int or limit not in _LIMITS:
            raise ControlRoomRejected("unsupported page size")
        timestamp = int(time.time()) if now is None else now
        if type(timestamp) is not int or timestamp < 0:
            raise ControlRoomRejected("invalid server clock")
        try:
            response = self.ddb.query(
                TableName=self.table,
                IndexName="TenantCreatedAtIndex",
                KeyConditionExpression="tenant_id = :tenant",
                ExpressionAttributeValues={
                    ":tenant": {"S": self.tenant},
                },
                ProjectionExpression=(
                    "tenant_id, created_at, job_id, #s, attempts, "
                    "updated_at, lease_until, submitted"
                ),
                ExpressionAttributeNames={"#s": "state"},
                ScanIndexForward=False,
                Limit=limit + 1,
                ConsistentRead=False,
            )
        except Exception:
            raise ControlRoomRejected("control-room index unavailable") from None
        records = response.get("Items")
        if not isinstance(records, list) or len(records) > limit + 1:
            raise ControlRoomRejected("invalid control-room result")
        output = []
        for item in records[:limit]:
            if not isinstance(item, dict):
                raise ControlRoomRejected("invalid control-room record")
            if _s(item, "tenant_id") != self.tenant:
                raise ControlRoomRejected("cross-tenant control-room record")
            job_id = _s(item, "job_id")
            if not _JOB.fullmatch(job_id):
                raise ControlRoomRejected("invalid job ID in control room")
            state = _s(item, "state")
            if state not in _STATES:
                raise ControlRoomRejected("unrecognized job state")
            submitted = item.get("submitted")
            if not isinstance(submitted, dict) or submitted.get("BOOL") is not False:
                raise ControlRoomRejected("control room contains submitted job")
            attempts = _n(item, "attempts")
            created = _n(item, "created_at")
            if attempts > 3 or created > timestamp + 60:
                raise ControlRoomRejected("invalid job counters or time")
            lease = None
            if state == "running":
                lease = _n(item, "lease_until")
                if lease < created:
                    raise ControlRoomRejected("invalid lease timestamp")
            attention = (
                state in {"queue_uncertain", "needs_review"}
                or state == "running" and lease is not None and lease < timestamp
                or state == "queued" and timestamp - created > _STALE_QUEUED_SECONDS
                or state == "retryable" and timestamp - created > _STALE_RETRYABLE_SECONDS
            )
            if state in ("queue_uncertain", "needs_review"):
                reason = state
            elif state == "running" and attention:
                reason = "expired_lease"
            elif state in ("queued", "retryable") and attention:
                reason = "long_wait"
            else:
                reason = None
            output.append({
                "job_id": job_id,
                "status": state,
                "attempts": attempts,
                "created_at": created,
                "attention_required": bool(attention),
                "attention_reason": reason,
                "submitted": False,
            })
        counts = dict(Counter(item["status"] for item in output))
        return {
            "version": 1,
            "mode": "auto",
            "thinking_enabled": False,
            "can_submit": False,
            "read_only": True,
            "snapshot_at": timestamp,
            "page_size": len(output),
            "more_available": len(records) > limit or bool(response.get("LastEvaluatedKey")),
            "status_counts_on_page": counts,
            "attention_on_page": sum(1 for item in output if item["attention_required"]),
            "jobs": output,
        }
