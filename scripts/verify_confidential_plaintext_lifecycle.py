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


def scan_version_metadata(s3, *, bucket: str, account: str, tenant: str,
                          subprefix: str = "confidential",
                          max_pages: int = 50) -> dict:
    """Complete bounded S3 version inventory; no object body or identifiers in output.

    Pagination markers are used solely as opaque request cursors. A malformed,
    repeated or incomplete continuation fails closed. S3 remains authoritative;
    this operation does not prove replica/backup purging or future consistency.
    """
    if type(max_pages) is not int or not 1 <= max_pages <= 100:
        raise UnsafeAudit("invalid S3 inventory page bound")
    if tenant not in _TENANTS or not isinstance(account, str) or not _ACCOUNT.fullmatch(account):
        raise UnsafeAudit("invalid synthetic inventory scope")
    if subprefix not in ("confidential", "confidential-results"):
        raise UnsafeAudit("S3 inventory prefix outside synthetic pilot")
    if bucket != f"ntr-cf-{tenant}-{account}-{_REGION}":
        raise UnsafeAudit("S3 inventory outside synthetic pilot")
    prefix = f"kancelarie/{tenant}/{subprefix}/"
    key_marker = None
    version_marker = None
    seen: set[tuple[str, str]] = set()
    count = 0
    markers = 0
    for page in range(1, max_pages + 1):
        kwargs = {
            "Bucket": bucket, "ExpectedBucketOwner": account,
            "Prefix": prefix, "MaxKeys": 1000,
        }
        if key_marker is not None:
            kwargs["KeyMarker"] = key_marker
            if version_marker:
                kwargs["VersionIdMarker"] = version_marker
        response = s3.list_object_versions(**kwargs)
        if not isinstance(response, dict):
            raise UnsafeAudit("S3 inventory response invalid")
        versions = response.get("Versions", [])
        deleted = response.get("DeleteMarkers", [])
        truncated = response.get("IsTruncated")
        if (not isinstance(versions, list) or not isinstance(deleted, list)
                or type(truncated) is not bool):
            raise UnsafeAudit("S3 inventory response invalid")
        count += len(versions)
        markers += len(deleted)
        if not truncated:
            return {
                "s3_inventory_complete": True,
                "s3_inventory_pages": page,
                "s3_version_count": count,
                "s3_delete_marker_count": markers,
            }
        next_key = response.get("NextKeyMarker")
        next_version = response.get("NextVersionIdMarker", "")
        if (not isinstance(next_key, str) or not next_key.startswith(prefix)
                or not isinstance(next_version, str)):
            raise UnsafeAudit("S3 inventory continuation missing")
        cursor = (next_key, next_version)
        if cursor in seen:
            raise UnsafeAudit("S3 inventory pagination loop")
        seen.add(cursor)
        key_marker, version_marker = cursor
    raise UnsafeAudit("S3 inventory exceeds bounded review")


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
    logs = session.client("logs")

    task = ecs.describe_task_definition(taskDefinition=task_arn)["taskDefinition"]
    if task.get("taskDefinitionArn") != task_arn:
        raise UnsafeAudit("returned task definition not pinned")
    options = inspect_task_definition(task)

    # Bucket names alone cannot prove storage locality. Verify the real
    # regional placement before enumerating any synthetic object metadata.
    bucket_region = s3.get_bucket_location(Bucket=bucket, ExpectedBucketOwner=account).get("LocationConstraint")
    if bucket_region != _REGION:
        raise UnsafeAudit("S3 bucket outside approved EU region")
    versioning = s3.get_bucket_versioning(Bucket=bucket, ExpectedBucketOwner=account).get("Status")
    # Missing replication / object lock configuration is a distinct state.
    # Unknown permissions must never be treated as "not configured".
    try:
        replication = s3.get_bucket_replication(Bucket=bucket, ExpectedBucketOwner=account).get(
            "ReplicationConfiguration", {}
        )
        replication_state = "configured" if replication.get("Rules") else "unknown"
    except Exception as exc:
        code = (getattr(exc, "response", {}) or {}).get("Error", {}).get("Code")
        if code in ("ReplicationConfigurationNotFoundError", "NoSuchReplicationConfiguration"):
            replication_state = "none-reported"
        elif code in ("AccessDenied", "AccessDeniedException"):
            replication_state = "unverified"
        else:
            raise UnsafeAudit("S3 replication status unavailable") from None
    try:
        lock = s3.get_object_lock_configuration(Bucket=bucket, ExpectedBucketOwner=account).get(
            "ObjectLockConfiguration", {}
        )
        object_lock_state = lock.get("ObjectLockEnabled", "unknown")
    except Exception as exc:
        code = (getattr(exc, "response", {}) or {}).get("Error", {}).get("Code")
        if code in ("ObjectLockConfigurationNotFoundError", "NoSuchObjectLockConfiguration"):
            object_lock_state = "not-configured"
        elif code in ("AccessDenied", "AccessDeniedException"):
            object_lock_state = "unverified"
        else:
            raise UnsafeAudit("S3 object lock status unavailable") from None
    try:
        lifecycle = s3.get_bucket_lifecycle_configuration(Bucket=bucket, ExpectedBucketOwner=account)
        lifecycle_rule_count = len(lifecycle.get("Rules", []))
    except Exception as exc:
        code = (getattr(exc, "response", {}) or {}).get("Error", {}).get("Code")
        if code not in ("NoSuchLifecycleConfiguration",):
            raise UnsafeAudit("S3 lifecycle read unavailable") from None
        lifecycle_rule_count = 0

    # Metadata only, all S3 pages; no body or identifiers printed.
    inventory = scan_version_metadata(
        s3, bucket=bucket, account=account, tenant=tenant,
        subprefix="confidential",
    )
    result_inventory = scan_version_metadata(
        s3, bucket=bucket, account=account, tenant=tenant,
        subprefix="confidential-results",
    )
    queue = sqs.get_queue_attributes(
        QueueUrl=queue_url,
        AttributeNames=["MessageRetentionPeriod", "RedrivePolicy"],
    ).get("Attributes", {})
    dlq_retention = None
    if queue.get("RedrivePolicy"):
        try:
            redrive = json.loads(queue["RedrivePolicy"])
        except (ValueError, TypeError):
            raise UnsafeAudit("invalid SQS redrive policy") from None
        target = (f"arn:aws:sqs:{_REGION}:{account}:"
                  f"notarai-confidential-{tenant}-dead.fifo")
        if redrive.get("deadLetterTargetArn") != target:
            raise UnsafeAudit("DLQ outside synthetic pilot")
        dlq_url = (f"https://sqs.{_REGION}.amazonaws.com/{account}/"
                   f"notarai-confidential-{tenant}-dead.fifo")
        dlq_attrs = sqs.get_queue_attributes(
            QueueUrl=dlq_url, AttributeNames=["MessageRetentionPeriod"]
        ).get("Attributes", {})
        dlq_retention = int(dlq_attrs.get("MessageRetentionPeriod", "-1"))
    backups = ddb.describe_continuous_backups(
        TableName=f"notarai-confidential-jobs-{tenant}"
    )["ContinuousBackupsDescription"].get("PointInTimeRecoveryDescription", {})
    trails = cloudtrail.describe_trails(includeShadowTrails=False).get("trailList", [])
    # Only inspect retention settings. Never call GetLogEvents/FilterLogEvents.
    group_page = logs.describe_log_groups(
        logGroupNamePrefix=f"notarai-confidential-{tenant}", limit=50
    )
    retention_days = [g.get("retentionInDays") for g in group_page.get("logGroups", [])]
    return {
        "scope": "synthetic pilot only",
        "region": _REGION,
        "account_matched": True,
        "task_controls": options,
        "s3_bucket_region_verified": bucket_region == _REGION,
        "s3_versioning_enabled": versioning == "Enabled",
        "s3_replication_state": replication_state,
        "s3_bucket_object_lock_state": object_lock_state,
        "s3_lifecycle_rule_count": lifecycle_rule_count,
        **inventory,
        "s3_result_inventory_complete": result_inventory["s3_inventory_complete"],
        "s3_result_inventory_pages": result_inventory["s3_inventory_pages"],
        "s3_result_version_count": result_inventory["s3_version_count"],
        "s3_result_delete_marker_count": result_inventory["s3_delete_marker_count"],
        "sqs_retention_seconds": int(queue.get("MessageRetentionPeriod", "-1")),
        "sqs_has_redrive": "RedrivePolicy" in queue,
        "sqs_dlq_retention_seconds": dlq_retention,
        "ddb_pitr_status": backups.get("PointInTimeRecoveryStatus", "UNKNOWN"),
        "ddb_pitr_days": backups.get("RecoveryPeriodInDays"),
        "cloudtrail_trail_count": len(trails),
        "cloudwatch_named_group_count": len(retention_days),
        "cloudwatch_named_group_retention_days": retention_days,
        "cloudwatch_named_group_list_truncated": bool(group_page.get("nextToken")),
        "report_contains_customer_content": False,
        "scope_limitations": [
            "metadata-only, no logs or file bodies inspected",
            "CloudWatch coverage limited to exact synthetic tenant log prefix",
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
