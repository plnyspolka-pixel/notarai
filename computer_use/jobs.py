"""Durable, tenant-partitioned NotarAI Virtual Employee control plane.

DynamoDB stores ONLY job metadata; payload/result live in per-tenant encrypted
objects. Queue messages contain only opaque job IDs and no client content.
Workers never accept tenant IDs from SQS: they use their bound deployment.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any, Mapping

from .fallback_router import Risk

_ID = re.compile(r"^[a-zA-Z0-9_-]{2,80}$")
_TERMINAL = frozenset({"completed", "cancelled", "denied", "failed",
                        "needs_reconciliation", "expired"})
_ALLOWED_ACTIONS = {"read_field": Risk.READ_ONLY,
                    "fill_draft_field": Risk.DRAFT}


class JobConflict(Exception):
    pass


class JobMissing(Exception):
    pass


def _require_identifier(value: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError("invalid_identifier")
    return value


def _partition(tenant: str) -> str:
    return "TENANT#" + _require_identifier(tenant)


def _sort_key(job_id: str) -> str:
    return "JOB#" + _require_identifier(job_id)


def _secure_summary(item: Mapping[str, Any]) -> dict:
    """Explicit allowlist: payload or personal data never reach the console."""
    return {name: item[name] for name in (
        "job_id", "app_id", "action", "risk", "status", "created_at", "updated_at",
        "last_strategy", "reason", "approval_expires", "cancellation_requested"
    ) if name in item}


@dataclass(frozen=True)
class TenantIdentity:
    tenant_id: str
    actor_id: str
    can_approve: bool = False

    def __post_init__(self):
        _require_identifier(self.tenant_id)
        if not self.actor_id or len(self.actor_id) > 128:
            raise ValueError("invalid_actor")


class JobControl:
    def __init__(self, *, table, sqs, payloads, queue_resolver,
                 settings_table=None, clock=time.time):
        self.table = table
        self.settings_table = settings_table
        self.sqs = sqs
        self.payloads = payloads  # encrypted S3 object adapter, not DDB
        self.queue_resolver = queue_resolver
        self.clock = clock

    def create(self, caller: TenantIdentity, *, app_id: str, action: str,
               field: str, value: str | None = None) -> dict:
        _require_identifier(app_id)
        _require_identifier(field)
        if action not in _ALLOWED_ACTIONS:
            raise ValueError("action_not_allowed")
        risk = _ALLOWED_ACTIONS[action]
        if risk is Risk.READ_ONLY and value is not None:
            raise ValueError("unexpected_value")
        if risk is Risk.DRAFT and (
                not isinstance(value, str) or not value or len(value) > 2000):
            raise ValueError("invalid_draft_value")
        queue_url = self.queue_resolver(caller.tenant_id)  # trusted provisioning
        if not queue_url:
            raise ValueError("worker_not_provisioned")
        job_id = "j" + uuid.uuid4().hex
        now = int(self.clock())
        # Value may contain notarial PII. Encrypt and store before publishing.
        payload = {"field": field}
        if value is not None:
            payload["value"] = value
        object_ref = self.payloads.write(caller.tenant_id, job_id, "input", payload)
        item = {
            "PK": _partition(caller.tenant_id),
            "SK": _sort_key(job_id),
            "job_id": job_id,
            "app_id": app_id,
            "action": action,
            "risk": risk.value,
            "status": "waiting_for_approval" if risk is Risk.DRAFT else "queued",
            "input_ref": object_ref,
            "created_at": now,
            "updated_at": now,
            "expires_at": now + 30 * 86400,
            "version": 1,
        }
        self.table.put_item(Item=item, ConditionExpression="attribute_not_exists(PK)")
        if risk is Risk.READ_ONLY:
            self._publish(caller.tenant_id, job_id, queue_url)
        return _secure_summary(item)

    def _publish(self, tenant: str, job: str, queue_url: str) -> None:
        try:
            self.sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps({"job_id": job}),
                MessageGroupId=tenant,
                MessageDeduplicationId=job,
            )
        except Exception:
            # The job stays queued for an admin-controlled outbox reconciler;
            # no duplicate UI execution is possible without a worker claim.
            raise RuntimeError("job_queued_but_delivery_unconfirmed") from None

    def get(self, caller: TenantIdentity, job_id: str) -> dict:
        item = self.table.get_item(
            Key={"PK": _partition(caller.tenant_id), "SK": _sort_key(job_id)},
            ConsistentRead=True,
        ).get("Item")
        if not item:
            raise JobMissing()
        return _secure_summary(item)

    def list(self, caller: TenantIdentity, *, limit: int = 30) -> list[dict]:
        if not 1 <= limit <= 100:
            raise ValueError("invalid_limit")
        response = self.table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :p)",
            ExpressionAttributeValues={":pk": _partition(caller.tenant_id), ":p": "JOB#"},
            ScanIndexForward=False, Limit=limit, ConsistentRead=True,
        )
        return [_secure_summary(v) for v in response.get("Items", [])]

    def approval_preview(self, caller: TenantIdentity, job_id: str) -> dict:
        """Provide the FULL intended draft field/value to an authorized approver.

        This data is never embedded in metadata listings or audit logs. The
        response is private, non-cacheable at the HTTP boundary.
        """
        if not caller.can_approve:
            raise PermissionError("notary_approval_required")
        item = self._get_raw(caller.tenant_id, job_id)
        if item["status"] != "waiting_for_approval" or item["risk"] != Risk.DRAFT.value:
            raise JobConflict()
        body = self.payloads.read(caller.tenant_id, job_id, "input", item["input_ref"])
        if not isinstance(body, dict) or not isinstance(body.get("field"), str):
            raise JobConflict()
        value = body.get("value")
        if not isinstance(value, str):
            raise JobConflict()
        return {"job_id": job_id, "app_id": item["app_id"], "action": item["action"],
                "field": body["field"], "value": value}

    def approve(self, caller: TenantIdentity, job_id: str) -> dict:
        if not caller.can_approve:
            raise PermissionError("notary_approval_required")
        job = self._get_raw(caller.tenant_id, job_id)
        if job["status"] != "waiting_for_approval" or job["risk"] != Risk.DRAFT.value:
            raise JobConflict()
        now = int(self.clock())
        try:
            self.table.update_item(
                Key={"PK": _partition(caller.tenant_id), "SK": _sort_key(job_id)},
                UpdateExpression="SET #s = :new, approval_expires = :expiry, updated_at = :now ADD version :one",
                ConditionExpression="#s = :expected AND version = :version",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":new": "queued", ":expiry": now + 300, ":now": now,
                    ":expected": "waiting_for_approval",
                    ":version": job["version"], ":one": 1,
                },
            )
        except Exception:
            raise JobConflict() from None
        self._publish(caller.tenant_id, job_id, self.queue_resolver(caller.tenant_id))
        return self.get(caller, job_id)

    def cancel(self, caller: TenantIdentity, job_id: str) -> dict:
        job = self._get_raw(caller.tenant_id, job_id)
        if job["status"] in _TERMINAL:
            return _secure_summary(job)
        now = int(self.clock())
        if job["status"] in ("queued", "waiting_for_approval"):
            expr = "SET #s = :cancelled, updated_at = :now ADD version :one"
            values = {":cancelled": "cancelled", ":now": now, ":one": 1}
        else:
            expr = "SET cancellation_requested = :yes, updated_at = :now ADD version :one"
            values = {":yes": True, ":now": now, ":one": 1}
        try:
            self.table.update_item(
                Key={"PK": _partition(caller.tenant_id), "SK": _sort_key(job_id)},
                UpdateExpression=expr,
                ConditionExpression="#s = :expected AND version = :version",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={**values, ":expected": job["status"],
                                           ":version": job["version"]},
            )
        except Exception:
            raise JobConflict() from None
        return self.get(caller, job_id)

    def _get_raw(self, tenant: str, job_id: str) -> dict:
        item = self.table.get_item(
            Key={"PK": _partition(tenant), "SK": _sort_key(job_id)},
            ConsistentRead=True,
        ).get("Item")
        if not item:
            raise JobMissing()
        return item

    def claim(self, *, bound_tenant: str, job_id: str, worker_id: str) -> dict:
        """Atomic one-time claim. Expired running jobs must be reconciled."""
        _require_identifier(worker_id)
        item = self._get_raw(bound_tenant, job_id)
        if item["status"] != "queued" or item.get("cancellation_requested"):
            raise JobConflict()
        now = int(self.clock())
        if item["risk"] != Risk.READ_ONLY.value and item.get("approval_expires", 0) <= now:
            raise JobConflict()
        try:
            self.table.update_item(
                Key={"PK": _partition(bound_tenant), "SK": _sort_key(job_id)},
                UpdateExpression="SET #s = :running, worker_id = :w, lease_until = :lease, updated_at = :now ADD version :one",
                ConditionExpression="#s = :queued AND version = :version",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":running": "running", ":w": worker_id, ":lease": now + 120,
                    ":now": now, ":one": 1, ":queued": "queued", ":version": item["version"],
                },
            )
        except Exception:
            raise JobConflict() from None
        return self._get_raw(bound_tenant, job_id)

    def finish(self, *, bound_tenant: str, job_id: str, worker_id: str,
               outcome: str, strategy: str | None = None,
               reason: str | None = None, result: Any = None) -> dict:
        allowed = {"completed", "needs_reconciliation", "waiting_for_human",
                   "denied", "failed", "cancelled"}
        if outcome not in allowed:
            raise ValueError("invalid_outcome")
        item = self._get_raw(bound_tenant, job_id)
        if item["status"] != "running" or item.get("worker_id") != worker_id:
            raise JobConflict()
        ref = None
        if result is not None and outcome == "completed":
            ref = self.payloads.write(bound_tenant, job_id, "result", result)
        now = int(self.clock())
        updates = {
            ":new": outcome, ":now": now, ":worker": worker_id,
            ":running": "running", ":one": 1,
        }
        expression = "SET #s = :new, updated_at = :now"
        if ref is not None:
            expression += ", result_ref = :ref"
            updates[":ref"] = ref
        if strategy is not None and re.fullmatch(r"[a-z_]{2,32}", strategy):
            expression += ", last_strategy = :strategy"
            updates[":strategy"] = strategy
        if reason is not None and re.fullmatch(r"[a-z_]{2,70}", reason):
            expression += ", reason = :reason"
            updates[":reason"] = reason
        expression += " ADD version :one"
        try:
            self.table.update_item(
                Key={"PK": _partition(bound_tenant), "SK": _sort_key(job_id)},
                UpdateExpression=expression,
                ConditionExpression="#s = :running AND worker_id = :worker",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues=updates,
            )
        except Exception:
            raise JobConflict() from None
        return self._get_raw(bound_tenant, job_id)

    def reconcile_expired(self, caller: TenantIdentity, job_id: str) -> dict:
        """For an expired running lease, NEVER auto-retry a GUI operation.

        Authorized approver moves the job to a durable investigation state.
        Condition protects against a racing live worker. Reconciliation is
        distinct from replay; only an operator can resolve the actual UI state.
        """
        if not caller.can_approve:
            raise PermissionError("notary_approval_required")
        item = self._get_raw(caller.tenant_id, job_id)
        if item["status"] != "running":
            raise JobConflict()
        now = int(self.clock())
        if item.get("lease_until", now + 1) >= now:
            raise JobConflict()
        try:
            self.table.update_item(
                Key={"PK": _partition(caller.tenant_id), "SK": _sort_key(job_id)},
                UpdateExpression=(
                    "SET #s = :new, reason = :reason, updated_at = :now "
                    "ADD version :one"
                ),
                ConditionExpression=(
                    "#s = :running AND version = :version "
                    "AND lease_until < :now"
                ),
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":new": "needs_reconciliation",
                    ":reason": "worker_lease_expired",
                    ":now": now,
                    ":one": 1,
                    ":running": "running",
                    ":version": item["version"],
                },
            )
        except Exception:
            raise JobConflict() from None
        return self.get(caller, job_id)

    def result(self, caller: TenantIdentity, job_id: str) -> Any:
        job = self._get_raw(caller.tenant_id, job_id)
        if job["status"] != "completed" or "result_ref" not in job:
            raise JobConflict()
        return self.payloads.read(caller.tenant_id, job_id, "result", job["result_ref"])

    def pending_input(self, *, bound_tenant: str, job_id: str) -> dict:
        job = self._get_raw(bound_tenant, job_id)
        if job["status"] != "running":
            raise JobConflict()
        return self.payloads.read(bound_tenant, job_id, "input", job["input_ref"])

    def kill_switch(self, *, bound_tenant: str) -> bool:
        # Crucially separate from the jobs table: the execution role can only
        # GetItem from settings, never UpdateItem and never clear the kill switch.
        if self.settings_table is None:
            return True
        item = self.settings_table.get_item(
            Key={"PK": _partition(bound_tenant), "SK": "CONFIG#WORKER"},
            ConsistentRead=True,
        ).get("Item", {})
        return bool(item.get("disabled", True))  # missing = disabled

    def set_kill_switch(self, caller: TenantIdentity, *, disabled: bool) -> None:
        if not caller.can_approve:
            raise PermissionError("notary_approval_required")
        if self.settings_table is None:
            raise RuntimeError("settings_store_not_configured")
        self.settings_table.update_item(
            Key={"PK": _partition(caller.tenant_id), "SK": "CONFIG#WORKER"},
            UpdateExpression="SET disabled = :disabled, updated_at = :now",
            ExpressionAttributeValues={
                ":disabled": bool(disabled), ":now": int(self.clock()),
            },
        )
