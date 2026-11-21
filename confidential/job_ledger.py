"""Durable preview-only work ledger; DynamoDB operations are conditional.

No irreversible action can be authorized by this module. The table contains
only opaque case/object/job identifiers and coarse status (no document data,
names, screenshots, signatures, or decrypted fields).

SQS delivery is at-least-once. State transitions and immutable job identity
are enforced server-side. Exactly-once external submission is NOT supported.
"""
from __future__ import annotations

import re
import secrets
import time
from dataclasses import dataclass

_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
_TENANT = re.compile(r"^[a-z0-9]{1,12}$")
_TOKEN = re.compile(r"^[a-f0-9]{32}$")
_VERSION = re.compile(r"^[A-Za-z0-9._~+/=-]{1,1024}$")
_MAX_ATTEMPTS = 3
_LEASE_SECONDS = 900
_STATES = frozenset({
    "queued", "queue_uncertain", "running", "retryable",
    "preview_completed", "needs_review",
})


class JobRejected(ValueError):
    """No client identifiers or exception messages included in denial text."""


def validate_version_id(value: object) -> str:
    """Require a real opaque S3 VersionId, never the unversioned null marker."""
    if (not isinstance(value, str) or not _VERSION.fullmatch(value) or
            value == "null"):
        raise JobRejected("immutable S3 object version required")
    return value



@dataclass(frozen=True)
class Claim:
    state: str  # claimed | completed | busy | needs_review
    token: str = ""
    attempts: int = 0


class PreviewJobLedger:
    def __init__(self, dynamodb, *, tenant: str):
        if not isinstance(tenant, str) or not _TENANT.fullmatch(tenant):
            raise JobRejected("invalid tenant")
        self.ddb = dynamodb
        self.tenant = tenant
        self.table = "notarai-confidential-jobs-" + tenant

    def _pk(self, job_id: str) -> dict:
        if not isinstance(job_id, str) or not _ID.fullmatch(job_id):
            raise JobRejected("invalid job")
        return {"pk": {"S": "JOB#" + self.tenant + "#" + job_id}}

    def _record(self, job_id: str) -> dict:
        try:
            response = self.ddb.get_item(
                TableName=self.table, Key=self._pk(job_id),
                ConsistentRead=True
            )
        except Exception:
            raise JobRejected("job ledger unavailable") from None
        item = response.get("Item") or {}
        if not item:
            raise JobRejected("unknown job")
        if item.get("tenant_id", {}).get("S") != self.tenant:
            raise JobRejected("wrong job tenant")
        if item.get("job_id", {}).get("S") != job_id:
            raise JobRejected("wrong job identifier")
        validate_version_id(item.get("s3_version", {}).get("S"))
        state = item.get("state", {}).get("S")
        if state not in _STATES or item.get("submitted", {}).get("BOOL") is not False:
            raise JobRejected("untrusted job state")
        return item

    def create(self, *, job_id: str, case_id: str, object_id: str,
               s3_version: str, now: int | None = None) -> None:
        pk = self._pk(job_id)
        validate_version_id(s3_version)
        if not all(isinstance(x, str) and _ID.fullmatch(x)
                   for x in (case_id, object_id)):
            raise JobRejected("invalid job scope")
        ts = int(time.time()) if now is None else now
        if type(ts) is not int or ts < 0:
            raise JobRejected("invalid job timestamp")
        item = {
            **pk, "tenant_id": {"S": self.tenant},
            "job_id": {"S": job_id},
            "case_id": {"S": case_id},
            "object_id": {"S": object_id},
            "s3_version": {"S": s3_version},
            "state": {"S": "queued"},
            "submitted": {"BOOL": False},
            "attempts": {"N": "0"},
            "created_at": {"N": str(ts)},
            "updated_at": {"N": str(ts)},
        }
        try:
            self.ddb.put_item(
                TableName=self.table,
                Item=item,
                ConditionExpression="attribute_not_exists(pk)",
            )
        except Exception:
            raise JobRejected("could not reserve unique preview job") from None

    def mark_queue_uncertain(self, job_id: str) -> None:
        """Fail closed after ambiguous SQS errors, not automatically requeued.

        SQS might have accepted a message when the network call timed out.
        The worker refuses such messages until an operator reconciles them.
        """
        try:
            self.ddb.update_item(
                TableName=self.table, Key=self._pk(job_id),
                UpdateExpression="SET #s = :uncertain",
                ConditionExpression="#s = :queued",
                ExpressionAttributeNames={"#s": "state"},
                ExpressionAttributeValues={
                    ":queued": {"S": "queued"},
                    ":uncertain": {"S": "queue_uncertain"},
                },
            )
        except Exception:
            # Any uncertainty here must not trigger a second SQS send.
            pass

    def status(self, job_id: str) -> dict:
        item = self._record(job_id)
        attempts = int(item.get("attempts", {}).get("N", "-1"))
        if not 0 <= attempts <= _MAX_ATTEMPTS:
            raise JobRejected("invalid job attempt count")
        return {
            "job_id": job_id,
            "status": item["state"]["S"],
            "attempts": attempts,
            "submitted": False,
            "mode": "auto",
            "can_submit": False,
        }

    def claim(self, *, job_id: str, case_id: str, object_id: str,
              s3_version: str, now: int | None = None,
              token: str | None = None) -> Claim:
        if not all(isinstance(x, str) and _ID.fullmatch(x)
                   for x in (case_id, object_id)):
            raise JobRejected("invalid message scope")
        validate_version_id(s3_version)
        ts = int(time.time()) if now is None else now
        token = secrets.token_hex(16) if token is None else token
        if type(ts) is not int or ts < 0 or not _TOKEN.fullmatch(token):
            raise JobRejected("invalid claim identity")
        prior = self._record(job_id)
        if (prior.get("case_id", {}).get("S") != case_id or
                prior.get("object_id", {}).get("S") != object_id or
                prior.get("s3_version", {}).get("S") != s3_version):
            raise JobRejected("message is not the reserved job")
        state = prior["state"]["S"]
        attempts = int(prior.get("attempts", {}).get("N", "-1"))
        if not 0 <= attempts <= _MAX_ATTEMPTS:
            raise JobRejected("invalid job attempts")
        if state == "preview_completed":
            return Claim("completed", attempts=attempts)
        if state in ("queue_uncertain", "needs_review") or attempts >= _MAX_ATTEMPTS:
            return Claim("needs_review", attempts=attempts)
        if state == "running" and int(
            prior.get("lease_until", {}).get("N", "0")
        ) >= ts:
            return Claim("busy", attempts=attempts)
        # The conditional update is authoritative when workers race.
        values = {
            ":tenant": {"S": self.tenant},
            ":job": {"S": job_id},
            ":case": {"S": case_id},
            ":object": {"S": object_id},
            ":version": {"S": s3_version},
            ":false": {"BOOL": False},
            ":zero": {"N": "0"},
            ":limit": {"N": str(_MAX_ATTEMPTS)},
            ":queued": {"S": "queued"},
            ":retryable": {"S": "retryable"},
            ":running": {"S": "running"},
            ":token": {"S": token},
            ":lease": {"N": str(ts + _LEASE_SECONDS)},
            ":now": {"N": str(ts)},
            ":one": {"N": "1"},
        }
        try:
            self.ddb.update_item(
                TableName=self.table, Key=self._pk(job_id),
                UpdateExpression=(
                    "SET #s = :running, task_token = :token, "
                    "lease_until = :lease, updated_at = :now ADD attempts :one"
                ),
                ConditionExpression=(
                    "attribute_exists(pk) AND tenant_id = :tenant "
                    "AND job_id = :job AND case_id = :case "
                    "AND object_id = :object AND s3_version = :version "
                    "AND submitted = :false "
                    "AND attempts < :limit AND "
                    "(#s = :queued OR #s = :retryable OR "
                    "(#s = :running AND lease_until < :now))"
                ),
                ExpressionAttributeNames={"#s": "state"},
                ExpressionAttributeValues=values,
                ReturnValues="ALL_NEW",
            )
        except Exception as exc:
            code = (getattr(exc, "response", {}) or {}).get(
                "Error", {}
            ).get("Code")
            if code == "ConditionalCheckFailedException":
                current = self._record(job_id)
                if (current.get("case_id", {}).get("S") != case_id or
                        current.get("object_id", {}).get("S") != object_id or
                        current.get("s3_version", {}).get("S") != s3_version):
                    raise JobRejected("job scope drift") from None
                if current["state"]["S"] == "preview_completed":
                    return Claim("completed", attempts=int(
                        current["attempts"]["N"]
                    ))
                if current["state"]["S"] in ("needs_review", "queue_uncertain"):
                    return Claim("needs_review")
                return Claim("busy")
            raise JobRejected("job claim unavailable") from None
        return Claim("claimed", token=token, attempts=attempts + 1)

    def complete(self, *, job_id: str, token: str) -> None:
        """Call only AFTER the opaque S3 preview marker was stored."""
        self._transition(job_id, token, "preview_completed")

    def fail(self, *, job_id: str, token: str, attempts: int) -> None:
        if type(attempts) is not int or not 1 <= attempts <= _MAX_ATTEMPTS:
            raise JobRejected("invalid failed attempt")
        self._transition(
            job_id, token,
            "needs_review" if attempts == _MAX_ATTEMPTS else "retryable",
        )

    def _transition(self, job_id: str, token: str, state: str) -> None:
        if not isinstance(token, str) or not _TOKEN.fullmatch(token):
            raise JobRejected("invalid task claim token")
        try:
            self.ddb.update_item(
                TableName=self.table, Key=self._pk(job_id),
                UpdateExpression="SET #s = :next REMOVE task_token",
                ConditionExpression="#s = :running AND task_token = :token",
                ExpressionAttributeNames={"#s": "state"},
                ExpressionAttributeValues={
                    ":next": {"S": state},
                    ":running": {"S": "running"},
                    ":token": {"S": token},
                },
            )
        except Exception:
            raise JobRejected("cannot finalize preview job") from None
