"""SQS consumer running ONLY on a tenant-bound Windows/browser machine.

The queue message never chooses tenant, worker, app, profile, IAM credentials,
or permissions. DynamoDB's atomic claim prevents duplicate GUI execution after
an SQS redelivery. Unknown side effects require human reconciliation.
"""
import json
import time
from typing import Callable

from .fallback_router import AutomationRequest, Outcome, Risk
from .jobs import JobConflict, JobControl, JobMissing, _require_identifier


class QueueConsumer:
    def __init__(self, *, bound_tenant: str, worker_id: str,
                 queue_url: str, sqs, control: JobControl, worker,
                 before_action: Callable | None = None):
        self.tenant_id = _require_identifier(bound_tenant)
        self.worker_id = _require_identifier(worker_id)
        if not queue_url:
            raise ValueError("missing_tenant_queue")
        self.queue_url = queue_url
        self.sqs = sqs
        self.control = control
        self.worker = worker
        self.before_action = before_action

    def poll_once(self) -> str:
        """One message/one GUI task; called inside single-session worker loop."""
        if self.control.kill_switch(bound_tenant=self.tenant_id):
            return "disabled"
        received = self.sqs.receive_message(
            QueueUrl=self.queue_url, MaxNumberOfMessages=1,
            WaitTimeSeconds=10, VisibilityTimeout=180,
        ).get("Messages", [])
        if not received:
            return "idle"
        message = received[0]
        receipt = message["ReceiptHandle"]
        try:
            payload = json.loads(message["Body"])
            if not isinstance(payload, dict) or set(payload) != {"job_id"}:
                return "invalid_message"
            job_id = _require_identifier(payload["job_id"])
        except (ValueError, TypeError, KeyError):
            return "invalid_message"

        if self.control.kill_switch(bound_tenant=self.tenant_id):
            # Leave message for when the tenant re-enables the worker.
            return "disabled"
        try:
            job = self.control.claim(bound_tenant=self.tenant_id, job_id=job_id,
                                     worker_id=self.worker_id)
        except JobConflict:
            # May be an SQS duplicate after success, a cancelled job or a
            # stale running job. Do not execute it a second time.
            self.sqs.delete_message(QueueUrl=self.queue_url, ReceiptHandle=receipt)
            return "already_claimed_or_cancelled"
        except JobMissing:
            # Unknown ID: discard only this message, not arbitrary data.
            self.sqs.delete_message(QueueUrl=self.queue_url, ReceiptHandle=receipt)
            return "unknown_job"

        try:
            body = self.control.pending_input(bound_tenant=self.tenant_id,
                                               job_id=job_id)
            if self.before_action is not None:
                self.before_action(job)
            if self.control.kill_switch(bound_tenant=self.tenant_id):
                result = self.control.finish(
                    bound_tenant=self.tenant_id, job_id=job_id,
                    worker_id=self.worker_id, outcome="cancelled",
                    reason="worker_disabled",
                )
            else:
                req = AutomationRequest(
                    job_id=job_id, tenant_id=self.tenant_id,
                    app_id=job["app_id"], action=job["action"],
                    risk=Risk(job["risk"]),
                    approval_id=job_id if job["risk"] == Risk.DRAFT.value else None,
                    payload=body,
                )
                out = self.worker.execute(req)
                result = self.control.finish(
                    bound_tenant=self.tenant_id, job_id=job_id,
                    worker_id=self.worker_id,
                    outcome=("waiting_for_human" if out.outcome is Outcome.UNSUPPORTED
                             else out.outcome.value),
                    strategy=out.strategy,
                    reason=("no_supported_method" if out.outcome is Outcome.UNSUPPORTED
                            else out.reason),
                    result=out.data if out.outcome is Outcome.COMPLETED else None,
                )
        except Exception:
            # Never acknowledge failure after starting GUI execution: the
            # durable job remains RUNNING until manual/stale reconciliation.
            # No exception content (might include PII) is logged or returned.
            return "execution_unconfirmed"

        self.sqs.delete_message(QueueUrl=self.queue_url, ReceiptHandle=receipt)
        return "completed"
