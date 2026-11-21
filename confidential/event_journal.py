"""Append-only operational status journal from DynamoDB Streams.

For synthetic AUTO preview only. The journal records validated state
transitions and exact opaque job IDs, never case IDs, object IDs, S3
versions, client data, browser values, or signed legal declarations.
A DynamoDB stream is not an immutable legal evidence system; stream
retention, reprocessing, IAM and data gaps require operational controls.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re

_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
_TENANT = re.compile(r"^[a-z0-9]{1,12}$")
_EVENT = re.compile(r"^[A-Za-z0-9:._+-]{1,300}$")
_STATES = frozenset({
    "queued", "queue_uncertain", "running", "retryable",
    "preview_completed", "needs_review",
})
_EVENTS = frozenset({"INSERT", "MODIFY", "REMOVE"})


class JournalRejected(ValueError):
    """Safe error with no document or AWS exception details."""


def _attr(item: dict, field: str) -> str:
    if not isinstance(item, dict):
        raise JournalRejected("invalid DynamoDB image")
    attr = item.get(field)
    result = attr.get("S") if isinstance(attr, dict) else None
    if not isinstance(result, str):
        raise JournalRejected("unexpected status image")
    return result


def _number(item: dict, field: str, *, limit=2**53-1) -> int:
    attr = item.get(field)
    value = attr.get("N") if isinstance(attr, dict) else None
    if not isinstance(value, str) or not value.isascii() or not value.isdecimal():
        raise JournalRejected("invalid status metadata")
    parsed = int(value)
    if parsed > limit or parsed < 0:
        raise JournalRejected("out-of-range status metadata")
    return parsed


def _guard_image(item: dict, tenant: str) -> tuple[str, str, int]:
    if _attr(item, "tenant_id") != tenant:
        raise JournalRejected("event tenant mismatch")
    job_id = _attr(item, "job_id")
    state = _attr(item, "state")
    if not _ID.fullmatch(job_id) or state not in _STATES:
        raise JournalRejected("untrusted job identity or status")
    flag = item.get("submitted")
    if not isinstance(flag, dict) or flag.get("BOOL") is not False:
        raise JournalRejected("submitted operation in AUTO journal")
    attempts = _number(item, "attempts", limit=3)
    return job_id, state, attempts


def transition(record: dict, *, tenant: str, source_arn: str) -> dict | None:
    """Validate one streamed job-state transition and strip all raw data.

    Returns None for updates that do not change the state/attempt counter.
    """
    if not isinstance(tenant, str) or not _TENANT.fullmatch(tenant):
        raise JournalRejected("invalid audit tenant")
    if not isinstance(source_arn, str) or not re.fullmatch(
        r"arn:aws:dynamodb:eu-central-1:[0-9]{12}:"
        r"table/notarai-confidential-jobs-" + re.escape(tenant) +
        r"/stream/[0-9TZ:.-]+", source_arn,
    ):
        raise JournalRejected("untrusted stream origin")
    if not isinstance(record, dict) or record.get("eventSource") != "aws:dynamodb":
        raise JournalRejected("invalid stream record")
    if record.get("eventSourceARN") != source_arn:
        raise JournalRejected("wrong job stream ARN")
    name = record.get("eventName")
    event_id = record.get("eventID")
    if name not in _EVENTS or not isinstance(event_id, str) or not _EVENT.fullmatch(event_id):
        raise JournalRejected("unknown audit event")
    dynamo = record.get("dynamodb")
    if not isinstance(dynamo, dict):
        raise JournalRejected("missing stream images")
    time_raw = dynamo.get("ApproximateCreationDateTime")
    if (
        type(time_raw) not in (int, float) or
        not math.isfinite(time_raw) or time_raw < 0 or time_raw > 2**53-1
    ):
        raise JournalRejected("invalid event timestamp")
    ts = int(time_raw)
    before_image = dynamo.get("OldImage")
    after_image = dynamo.get("NewImage")
    if name in ("INSERT", "MODIFY"):
        job_id, to_state, attempts = _guard_image(after_image, tenant)
    else:
        job_id, old_state, attempts = _guard_image(before_image, tenant)
        to_state = "deleted"
    if name == "INSERT":
        if before_image not in (None, {}):
            raise JournalRejected("unexpected old image on insert")
        previous = None
    else:
        old_job, previous, _ = _guard_image(before_image, tenant)
        if old_job != job_id:
            raise JournalRejected("job changed in stream event")
    if name == "MODIFY":
        if previous == to_state and (
            _number(before_image, "attempts", limit=3) == attempts
        ):
            return None
    event_hash = hashlib.sha256(event_id.encode("ascii")).hexdigest()
    body = {
        "job_id": job_id, "event": name, "from": previous,
        "to": to_state, "attempts": attempts, "timestamp": ts,
        "event_hash": event_hash,
    }
    return body


class DynamoJobJournal:
    def __init__(self, ddb, *, tenant: str):
        if not isinstance(tenant, str) or not _TENANT.fullmatch(tenant):
            raise JournalRejected("invalid journal tenant")
        self.ddb = ddb
        self.tenant = tenant
        self.table = "notarai-confidential-events-" + tenant

    def _pk(self, job_id: str) -> str:
        if not isinstance(job_id, str) or not _ID.fullmatch(job_id):
            raise JournalRejected("invalid journal job ID")
        return f"JOB#{self.tenant}#{job_id}"

    def append(self, event: dict) -> bool:
        """Idempotent append via a conditional PutItem.

        If a stream batch is replayed, a matching event can be acknowledged.
        If a key is occupied by a different event, fail closed.
        """
        if not isinstance(event, dict) or set(event) != {
            "job_id", "event", "from", "to", "attempts", "timestamp",
            "event_hash",
        }:
            raise JournalRejected("invalid event projection")
        pk = self._pk(event["job_id"])
        digest = event["event_hash"]
        if not isinstance(digest, str) or not re.fullmatch("[0-9a-f]{64}", digest):
            raise JournalRejected("invalid event digest")
        ts = event["timestamp"]
        if type(ts) is not int or ts < 0:
            raise JournalRejected("invalid event timestamp")
        if event["to"] not in (_STATES | {"deleted"}):
            raise JournalRejected("invalid state transition")
        sk = f"EVENT#{ts:013d}#{digest}"
        serialized = json.dumps(event, sort_keys=True, separators=(",", ":"), allow_nan=False)
        content_hash = hashlib.sha256(serialized.encode("ascii")).hexdigest()
        values = {
            "pk": {"S": pk},
            "sk": {"S": sk},
            "event_hash": {"S": digest},
            "content_hash": {"S": content_hash},
            "from_state": {"S": event["from"] if event["from"] is not None else "none"},
            "to_state": {"S": event["to"]},
            "attempts": {"N": str(event["attempts"])},
            "recorded_at": {"N": str(ts)},
        }
        try:
            self.ddb.put_item(
                TableName=self.table, Item=values,
                ConditionExpression="attribute_not_exists(pk) AND attribute_not_exists(sk)",
            )
            return True
        except Exception as exc:
            if (getattr(exc, "response", {}) or {}).get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise JournalRejected("audit journal unavailable") from None
            try:
                old = self.ddb.get_item(
                    TableName=self.table,
                    Key={"pk": {"S": pk}, "sk": {"S": sk}},
                    ConsistentRead=True,
                ).get("Item") or {}
            except Exception:
                raise JournalRejected("cannot reconcile repeated audit event") from None
            if old.get("content_hash", {}).get("S") != content_hash:
                raise JournalRejected("audit event integrity mismatch")
            return False

    def for_job(self, job_id: str, *, limit: int = 20) -> dict:
        pk = self._pk(job_id)
        if type(limit) is not int or limit not in (10, 20):
            raise JournalRejected("invalid history page size")
        try:
            result = self.ddb.query(
                TableName=self.table,
                KeyConditionExpression="pk = :pk",
                ExpressionAttributeValues={":pk": {"S": pk}},
                ScanIndexForward=False,
                Limit=limit + 1,
                ConsistentRead=True,
            )
        except Exception:
            raise JournalRejected("journal history unavailable") from None
        rows = result.get("Items")
        if not isinstance(rows, list) or len(rows) > limit + 1:
            raise JournalRejected("invalid history result")
        out = []
        for row in rows[:limit]:
            if row.get("pk", {}).get("S") != pk:
                raise JournalRejected("cross-tenant history row")
            state = row.get("to_state", {}).get("S")
            from_state = row.get("from_state", {}).get("S")
            digest = row.get("event_hash", {}).get("S")
            if (
                state not in (_STATES | {"deleted"}) or
                from_state not in (_STATES | {"none"}) or
                not isinstance(digest, str) or
                not re.fullmatch("[0-9a-f]{64}", digest)
            ):
                raise JournalRejected("untrusted history row")
            attempts = _number(row, "attempts", limit=3)
            timestamp = _number(row, "recorded_at")
            out.append({
                "timestamp": timestamp, "from": from_state, "to": state,
                "attempts": attempts, "event": digest[:12],
            })
        return {
            "version": 1,
            "read_only": True,
            "job_id": job_id,
            "events": out,
            "more_available": len(rows) > limit or bool(result.get("LastEvaluatedKey")),
            "note": "DynamoDB stream history; timing approximate; not an official filing receipt.",
        }


def lambda_handler(event, context):
    """Stream consumer. Never log raw records; do not skip invalid events."""
    tenant = os.environ.get("NOTARAI_AUDIT_TENANT", "")
    source_arn = os.environ.get("NOTARAI_JOB_STREAM_ARN", "")
    if not isinstance(event, dict) or not isinstance(event.get("Records"), list):
        raise JournalRejected("invalid event batch")
    records = event["Records"]
    if len(records) > 100:
        raise JournalRejected("oversized audit event batch")
    import boto3
    client = DynamoJobJournal(
        boto3.client("dynamodb", region_name="eu-central-1"), tenant=tenant,
    )
    total = 0
    for item in records:
        record = transition(item, tenant=tenant, source_arn=source_arn)
        if record is not None:
            client.append(record)
            total += 1
    # Never echo metadata from source records or identifiers in Lambda logs.
    return {"processed": total}
