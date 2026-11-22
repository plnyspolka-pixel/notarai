#!/usr/bin/env python3
"""SEC-10 metadata-only AWS audit for two SYNTHETIC pilot tenants.

Read-only. Never fetches S3 object bodies, SQS messages, CloudTrail events,
CloudWatch log lines, snapshots, decrypted data or KMS plaintext.

Default mode is OFFLINE; '--check' needs an explicit account and AWS profile.
Outputs only booleans/counts and does NOT mark Zero Knowledge verified.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

_REGION = "eu-central-1"
_ACCOUNT = re.compile(r"^[0-9]{12}$")
_TENANTS = frozenset({"pilot01", "pilot02"})


class UnsafeAudit(ValueError):
    pass


def validate_scope(*, account: str, tenant: str, bucket: str,
                   queue_url: str, task_arn: str) -> None:
    if not _ACCOUNT.fullmatch(account) or tenant not in _TENANTS:
        raise UnsafeAudit("invalid account or synthetic tenant")
    if bucket != f"ntr-cf-{tenant}-{account}-{_REGION}":
        raise UnsafeAudit("bucket outside synthetic pilot")
    if queue_url != (f"https://sqs.{_REGION}.amazonaws.com/{account}/"
                     f"notarai-confidential-{tenant}.fifo"):
        raise UnsafeAudit("queue outside synthetic pilot")
    if not re.fullmatch(
        rf"arn:aws:ecs:{_REGION}:{account}:task-definition/"
        rf"notarai-confidential-{tenant}:[1-9][0-9]*", task_arn,
    ):
        raise UnsafeAudit("task definition outside synthetic pilot")


def inspect_task_definition(task: dict) -> dict:
    containers = task.get("containerDefinitions", [])
    if len(containers) != 1:
        raise UnsafeAudit("unexpected guest container count")
    container = containers[0]
    tmpfs = container.get("linuxParameters", {}).get("tmpfs", [])
    runtime = task.get("trustedExecutionConfiguration", {})
    image = container.get("image", "")
    result = {
        "guest_readonly": container.get("readonlyRootFilesystem") is True,
        "one_ephemeral_tmpfs": (
            len(tmpfs) == 1 and tmpfs[0].get("containerPath") == "/tmp"
            and set(tmpfs[0].get("mountOptions", [])) >= {"nosuid", "nodev"}
        ),
        "persistent_mounts_absent": not container.get("mountPoints") and not task.get("volumes"),
        "log_driver_absent": "logConfiguration" not in container,
        "nitro_sandbox_declared": runtime.get("isolationMode") == "CONFIDENTIAL_SANDBOX",
        "image_is_digest_pinned": bool(re.fullmatch(r".+@sha256:[0-9a-f]{64}", image)),
    }
    return result


def read_only_audit(session, *, account: str, tenant: str, bucket: str,
                    queue_url: str, task_arn: str) -> dict:
    validate_scope(account=account, tenant=tenant, bucket=bucket,
                   queue_url=queue_url, task_arn=task_arn)
    if session.region_name != _REGION:
        raise UnsafeAudit("wrong AWS region")
    sts = session.client("sts")
    if sts.get_caller_identity().get("Account") != account:
        raise UnsafeAudit("AWS account mismatch")
    s3 = session.client("s3")
    sqs = session.client("sqs")
    ddb = session.client("dynamodb")
    ecs = session.client("ecs")
    cloudtrail = session.client("cloudtrail")

    task = ecs.describe_task_definition(taskDefinition=task_arn)["taskDefinition"]
    if task.get("taskDefinitionArn") != task_arn:
        raise UnsafeAudit("returned task definition not pinned")
    options = inspect_task_definition(task)

    versioning = s3.get_bucket_versioning(Bucket=bucket).get("Status")
    try:
        lifecycle = s3.get_bucket_lifecycle_configuration(Bucket=bucket)
        lifecycle_rule_count = len(lifecycle.get("Rules", []))
    except Exception as exc:
        code = (getattr(exc, "response", {}) or {}).get("Error", {}).get("Code")
        if code not in ("NoSuchLifecycleConfiguration",):
            raise UnsafeAudit("S3 lifecycle read unavailable") from None
        lifecycle_rule_count = 0

    # Metadata only; no object bodies, values or identifiers printed/stored.
    versions = s3.list_object_versions(
        Bucket=bucket, Prefix=f"kancelarie/{tenant}/confidential/", MaxKeys=1000
    )
    queue = sqs.get_queue_attributes(
        QueueUrl=queue_url,
        AttributeNames=["MessageRetentionPeriod", "RedrivePolicy"],
    ).get("Attributes", {})
    backups = ddb.describe_continuous_backups(
        TableName=f"notarai-confidential-jobs-{tenant}"
    )["ContinuousBackupsDescription"].get("PointInTimeRecoveryDescription", {})
    trails = cloudtrail.describe_trails(includeShadowTrails=False).get("trailList", [])
    return {
        "scope": "synthetic pilot only",
        "region": _REGION,
        "account_matched": True,
        "task_controls": options,
        "s3_versioning_enabled": versioning == "Enabled",
        "s3_lifecycle_rule_count": lifecycle_rule_count,
        "s3_version_count_on_first_page": len(versions.get("Versions", [])),
        "s3_version_list_truncated": bool(versions.get("IsTruncated")),
        "sqs_retention_seconds": int(queue.get("MessageRetentionPeriod", "-1")),
        "sqs_has_redrive": "RedrivePolicy" in queue,
        "ddb_pitr_status": backups.get("PointInTimeRecoveryStatus", "UNKNOWN"),
        "ddb_pitr_days": backups.get("RecoveryPeriodInDays"),
        "cloudtrail_trail_count": len(trails),
        "contains_plaintext": False,
        "scope_limitations": [
            "metadata-only, no logs or file bodies inspected",
            "not a substitute for Nitro attestation or independent audit",
            "no claim about RAM erasure, history deletion or legal compliance",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="Opt in to actual read-only AWS metadata calls")
    parser.add_argument("--profile", default="")
    parser.add_argument("--account", default="")
    parser.add_argument("--tenant", default="")
    parser.add_argument("--bucket", default="")
    parser.add_argument("--queue-url", default="")
    parser.add_argument("--task-arn", default="")
    a = parser.parse_args(argv)
    if not a.check:
        print("SEC-10: DRY RUN; AWS calls DISABLED. Use --check and explicit synthetic scope.")
        return 0
    if not a.profile:
        print("SEC-10: explicit AWS profile required", file=sys.stderr)
        return 2
    try:
        validate_scope(account=a.account, tenant=a.tenant, bucket=a.bucket,
                       queue_url=a.queue_url, task_arn=a.task_arn)
        import boto3
        session = boto3.Session(profile_name=a.profile, region_name=_REGION)
        report = read_only_audit(
            session, account=a.account, tenant=a.tenant, bucket=a.bucket,
            queue_url=a.queue_url, task_arn=a.task_arn
        )
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception as exc:
        # Never log the exception message, response headers or resource names.
        print("SEC-10 audit BLOCKED: " + type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
