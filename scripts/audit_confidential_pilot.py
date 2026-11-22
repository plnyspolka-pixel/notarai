"""Read-only Nitro pilot audit, no SQS consumption or customer data.

By default --check is absent: NO AWS calls. With --check the program reads
only metadata for the exact synthetic pilot account and tenant and reports
pending/retry/DLQ counts. It never changes task, queue or KMS configuration.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from confidential.job_ledger import PreviewJobLedger, JobRejected


def _count(value) -> int:
    if not isinstance(value, str) or not value.isdecimal():
        raise ValueError("cannot verify SQS approximate count")
    return int(value)


def audit(*, profile: str, account: str, tenant: str,
          job_id: str, check: bool = False, session_factory=None,
          shared_compute: bool = False) -> dict:
    if type(shared_compute) is not bool:
        raise ValueError("invalid shared compute selector")
    if (not re.fullmatch(r"[0-9]{12}", account) or
        not re.fullmatch(r"[a-z0-9]{1,12}", tenant) or
        not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", job_id)):
        raise ValueError("invalid synthetic pilot identity")
    if not check:
        print("DRY RUN: read-only AWS pilot audit plan. No AWS calls.")
        return {"mode": "dry_run", "aws_calls": 0}
    if session_factory is None:
        import boto3
        session_factory = boto3.Session
    session = session_factory(profile_name=None if profile == "environment" else profile,
        region_name="eu-central-1")
    if session.client("sts").get_caller_identity().get("Account") != account:
        raise RuntimeError("unexpected AWS account")
    stage = session.client("cloudformation").describe_stacks(
        # Shared fabric: per-tenant data stacks carry the tenant suffix and all
        # tenants run in the one regional cluster; the task family stays
        # tenant-specific so another tenant's tasks are never counted.
        StackName=(f"notarai-confidential-staging-{tenant}"
                   if shared_compute else "notarai-confidential-staging"),
    ).get("Stacks", [])
    if len(stage) != 1 or stage[0].get("StackStatus") not in (
        "CREATE_COMPLETE", "UPDATE_COMPLETE",
    ):
        raise RuntimeError("synthetic pilot stage unavailable")
    outputs = {
        x["OutputKey"]: x["OutputValue"] for x in stage[0].get("Outputs", [])
    }
    prefix = "notarai-confidential-" + tenant
    bucket = f"ntr-cf-{tenant}-{account}-eu-central-1"
    queue_url = (
        f"https://sqs.eu-central-1.amazonaws.com/{account}/{prefix}.fifo"
    )
    if outputs.get("BucketName") != bucket or outputs.get("QueueUrl") != queue_url:
        raise RuntimeError("pilot resource scope mismatch")
    sqs = session.client("sqs")
    names = ["ApproximateNumberOfMessages", "ApproximateNumberOfMessagesNotVisible"]
    q = sqs.get_queue_attributes(
        QueueUrl=queue_url, AttributeNames=names,
    )["Attributes"]
    dead_url = sqs.get_queue_url(
        QueueName=prefix + "-dead.fifo"
    )["QueueUrl"]
    if dead_url != queue_url[:-5] + "-dead.fifo":
        raise RuntimeError("unexpected dead-letter queue")
    dead = sqs.get_queue_attributes(
        QueueUrl=dead_url,
        AttributeNames=["ApproximateNumberOfMessages"],
    )["Attributes"]
    ecs = session.client("ecs").list_tasks(
        cluster="notarai-confidential-shared" if shared_compute else prefix,
        family=prefix, desiredStatus="RUNNING",
        maxResults=100,
    )
    if ecs.get("nextToken"):
        raise RuntimeError("incomplete running-task inventory")
    ledger = PreviewJobLedger(session.client("dynamodb"), tenant=tenant)
    status = ledger.status(job_id)
    marker = False
    if status["status"] == "preview_completed":
        key = f"kancelarie/{tenant}/confidential-results/{job_id}.json"
        try:
            session.client("s3").head_object(Bucket=bucket, Key=key)
            marker = True
        except Exception:
            marker = False
    result = {
        "mode": "read_only",
        "region": "eu-central-1",
        "tenant": tenant,
        "job_id": job_id,
        "job_status": status["status"],
        "attempts": status["attempts"],
        "submitted": False,
        "result_marker_exists": marker,
        "queue_visible_approx": _count(q.get("ApproximateNumberOfMessages")),
        "queue_inflight_approx": _count(
            q.get("ApproximateNumberOfMessagesNotVisible")
        ),
        "dead_letter_visible_approx": _count(
            dead.get("ApproximateNumberOfMessages")
        ),
        "ecs_active_count": len(ecs.get("taskArns", [])),
    }
    print(json.dumps(result, sort_keys=True))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--account", required=True)
    parser.add_argument("--tenant", default="pilot01")
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--shared-compute", action="store_true",
                        help="Per-tenant stacks in the shared regional Nitro fabric")
    args = parser.parse_args()
    audit(
        profile=args.profile, account=args.account, tenant=args.tenant,
        job_id=args.job_id, check=args.check,
        shared_compute=args.shared_compute,
    )


if __name__ == "__main__":
    main()
