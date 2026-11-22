"""Safe, preview-only Nitro guest scheduler with optional SHARED capacity pool.

Multiple tenants may run on one ECS Nitro capacity provider, but each
scheduler retains its own fixed task family, roles, queue, lease and KMS key.
This scheduler DOES NOT consume SQS messages: the existing pinned guest worker
must be the sole SQS consumer. This avoids ECS container env/command overrides
which otherwise change default Nitro container admission measurements.

Only a single worker per pilot tenant is launched at a time. The DynamoDB
lease is a concurrency gate, NOT proof of exactly-once completion. Never use
this path for form submission or other irreversible operations.
"""
from __future__ import annotations

import re
import secrets
import time
from dataclasses import dataclass

REGION = "eu-central-1"
_ACCOUNT = re.compile(r"^[0-9]{12}$")
_TENANT = re.compile(r"^[a-z0-9]{1,12}$")
_SUBNET = re.compile(r"^subnet-(?:[0-9a-f]{8}|[0-9a-f]{17})$")
_SG = re.compile(r"^sg-(?:[0-9a-f]{8}|[0-9a-f]{17})$")
_DIGEST = re.compile(r"^[a-f0-9]{64}$")


class UnsafeDispatch(ValueError):
    """Do not include client data or AWS exception details in this error."""


@dataclass(frozen=True)
class DispatcherConfig:
    account: str
    tenant: str
    cluster: str
    capacity_provider: str
    task_definition_arn: str
    queue_url: str
    subnet: str
    security_group: str
    lease_table: str
    shared_pool: bool = False
    external_custody_key_arn: str = ""  # empty only for synthetic legacy tests

    def validate(self) -> None:
        if not _ACCOUNT.fullmatch(self.account) or not _TENANT.fullmatch(self.tenant):
            raise UnsafeDispatch("invalid pilot identity")
        family = f"notarai-confidential-{self.tenant}"
        arn_prefix = f"arn:aws:ecs:{REGION}:{self.account}:task-definition/{family}:"
        if type(self.shared_pool) is not bool:
            raise UnsafeDispatch("invalid shared compute selector")
        pool = "notarai-confidential-shared" if self.shared_pool else family
        if (self.cluster != pool or self.capacity_provider != pool or
                not self.task_definition_arn.startswith(arn_prefix) or
                not self.task_definition_arn[len(arn_prefix):].isdigit()):
            raise UnsafeDispatch("unapproved ECS task target")
        queue = f"https://sqs.{REGION}.amazonaws.com/{self.account}/{family}.fifo"
        if self.queue_url != queue:
            raise UnsafeDispatch("unapproved SQS queue")
        if not _SUBNET.fullmatch(self.subnet) or not _SG.fullmatch(self.security_group):
            raise UnsafeDispatch("invalid private networking identifiers")
        if self.lease_table != f"notarai-confidential-dispatch-{self.tenant}":
            raise UnsafeDispatch("unapproved lease ledger")
        if self.external_custody_key_arn:
            # Never reinterpret an invalid external key as permission to use
            # the operator-owned demo key.
            if (not self.shared_pool or not re.fullmatch(
                r"arn:aws:kms:eu-central-1:[0-9]{12}:key/[A-Za-z0-9-]+",
                self.external_custody_key_arn
            ) or self.external_custody_key_arn.split(":")[4] == self.account):
                raise UnsafeDispatch("external custody key is not independent")


def _verify_task(ecs, config: DispatcherConfig) -> None:
    definition = ecs.describe_task_definition(
        taskDefinition=config.task_definition_arn
    )["taskDefinition"]
    family = f"notarai-confidential-{config.tenant}"
    repo = "notarai-confidential-shared" if config.shared_pool else family
    expected_repo = (
        f"{config.account}.dkr.ecr.{REGION}.amazonaws.com/{repo}@sha256:"
    )
    containers = definition.get("containerDefinitions") or []
    if len(containers) != 1:
        raise UnsafeDispatch("unexpected guest container count")
    guest = containers[0]
    image = guest.get("image", "")
    if (
        definition.get("taskDefinitionArn") != config.task_definition_arn
        or definition.get("family") != family
        or definition.get("status") != "ACTIVE"
        or definition.get("networkMode") != "awsvpc"
        or definition.get("requiresCompatibilities") != ["MANAGED_INSTANCES"]
        or definition.get("taskRoleArn") !=
        f"arn:aws:iam::{config.account}:role/{family}"
        or definition.get("executionRoleArn") !=
        f"arn:aws:iam::{config.account}:role/notarai-confidential-execution-{config.tenant}"
        or (definition.get("trustedExecutionConfiguration") or {}).get("isolationMode")
        != "CONFIDENTIAL_SANDBOX"
        or not (definition.get("trustedExecutionConfiguration") or {}).get("attestationPolicy")
        or not isinstance(image, str)
        or not image.startswith(expected_repo)
        or not _DIGEST.fullmatch(image[len(expected_repo):])
        or guest.get("name") != "confidential-browser"
        or guest.get("readonlyRootFilesystem") is not True
        or guest.get("user") != "10001:10001"
        or guest.get("privileged") is True
        or guest.get("logConfiguration")
        or guest.get("secrets")
        or guest.get("environmentFiles")
        or guest.get("mountPoints")
        or guest.get("volumesFrom")
        or guest.get("portMappings")
        or definition.get("volumes")
    ):
        raise UnsafeDispatch("unverified Nitro guest task definition")
    env = guest.get("environment") or []
    values = {v.get("name"): v.get("value") for v in env if isinstance(v, dict)}
    required_env = {
        "NOTARAI_CONFIDENTIAL_REQUIRED", "NOTARAI_CONFIDENTIAL_TENANT",
        "NOTARAI_CONFIDENTIAL_BUCKET", "NOTARAI_CONFIDENTIAL_QUEUE_URL",
        "NOTARAI_CONFIDENTIAL_KMS_KEY_ARN", "AWS_REGION",
        "HOME", "XDG_CACHE_HOME", "TMPDIR",
    }
    if (len(env) != len(required_env) or set(values) != required_env or
            values.get("NOTARAI_CONFIDENTIAL_REQUIRED") != "1"):
        raise UnsafeDispatch("guest environment is not pinned")
    kms = values["NOTARAI_CONFIDENTIAL_KMS_KEY_ARN"]
    bucket = values["NOTARAI_CONFIDENTIAL_BUCKET"]
    if (values.get("NOTARAI_CONFIDENTIAL_TENANT") != config.tenant or
            values.get("NOTARAI_CONFIDENTIAL_QUEUE_URL") != config.queue_url or
            values.get("AWS_REGION") != REGION or
            not isinstance(kms, str) or
            (config.external_custody_key_arn and kms != config.external_custody_key_arn)
            or (not config.external_custody_key_arn and
                not kms.startswith(f"arn:aws:kms:{REGION}:{config.account}:key/")) or
            not isinstance(bucket, str) or not re.fullmatch(
                r"[a-z0-9][a-z0-9.-]{2,62}", bucket
            )):
        raise UnsafeDispatch("guest is pointed at another queue, key or tenant")

    provider = ecs.describe_capacity_providers(
        capacityProviders=[config.capacity_provider]
    ).get("capacityProviders", [])
    if len(provider) != 1 or provider[0].get("name") != config.capacity_provider:
        raise UnsafeDispatch("unapproved ECS capacity provider")
    launch = (provider[0].get("managedInstancesProvider") or {}).get(
        "instanceLaunchTemplate"
    ) or {}
    instance_network = launch.get("networkConfiguration") or {}
    if (provider[0].get("status") != "ACTIVE" or
            launch.get("nitroEnclavesEnabled") is not True or
            instance_network.get("securityGroups") != [config.security_group] or
            config.subnet not in (instance_network.get("subnets") or [])):
        raise UnsafeDispatch("Nitro capacity provider is outside private pilot network")


def _active_guest_count(ecs, config: DispatcherConfig) -> int:
    # ECS desiredStatus RUNNING includes tasks whose lastStatus is PENDING.
    # Family filtering ensures unrelated application tasks are not counted.
    response = ecs.list_tasks(
        cluster=config.cluster,
        family=f"notarai-confidential-{config.tenant}",
        desiredStatus="RUNNING",
        maxResults=100,
    )
    if response.get("nextToken"):
        # Limit to one active guest; unknown pagination must never permit launch.
        raise UnsafeDispatch("cannot inspect all active guest tasks")
    return len(response.get("taskArns", []))


def _release_finished_lease(ecs, dynamodb, config: DispatcherConfig,
                            now: int) -> None:
    """Unlock a finished worker after ECS confirms STOPPED; never by guess."""
    key = {"pk": {"S": f"TENANT#{config.tenant}"}}
    record = dynamodb.get_item(
        TableName=config.lease_table, Key=key, ConsistentRead=True
    ).get("Item") or {}
    if (record.get("state", {}).get("S") != "launched" or
            not record.get("task_arn", {}).get("S")):
        return
    arn = record["task_arn"]["S"]
    if not arn.startswith(f"arn:aws:ecs:{REGION}:{config.account}:task/"):
        raise UnsafeDispatch("ledger has wrong ECS task")
    task_report = ecs.describe_tasks(cluster=config.cluster, tasks=[arn])
    tasks = task_report.get("tasks") or []
    if (task_report.get("failures") or len(tasks) != 1 or
            tasks[0].get("taskArn") != arn or
            tasks[0].get("lastStatus") != "STOPPED" or
            tasks[0].get("desiredStatus") != "STOPPED"):
        return
    try:
        dynamodb.update_item(
            TableName=config.lease_table,
            Key=key,
            UpdateExpression="SET #s = :finished, lease_until = :expired",
            ConditionExpression="token = :token AND #s = :launched",
            ExpressionAttributeNames={"#s": "state"},
            ExpressionAttributeValues={
                ":token": record["token"],
                ":launched": {"S": "launched"},
                ":finished": {"S": "finished"},
                ":expired": {"N": str(now - 1)},
            },
        )
    except Exception as exc:
        # Another invocation may have changed the lease; it must win.
        if (getattr(exc, "response", {}) or {}).get("Error", {}).get(
            "Code"
        ) != "ConditionalCheckFailedException":
            raise


def dispatch_once(config: DispatcherConfig, *, sqs, ecs, dynamodb,
                  release_gate=None, clock=time.time, token_factory=None) -> str:
    """Launch at most one verified, unmodified preview guest per lease.

    One SQS FIFO work queue stays owned by the guest, not the scheduler.
    Pending jobs can be delayed; failed launches are NOT immediately retried
    if ECS may have accepted the request. Human review is required for
    ambiguous failures. This deliberately fails toward no task launch.
    """
    config.validate()
    if not callable(release_gate):
        raise UnsafeDispatch("independent signed release gate is mandatory")
    token_factory = token_factory or (lambda: secrets.token_hex(16))
    depth = sqs.get_queue_attributes(
        QueueUrl=config.queue_url,
        AttributeNames=["ApproximateNumberOfMessages"],
    ).get("Attributes", {}).get("ApproximateNumberOfMessages", "0")
    if not isinstance(depth, str) or not depth.isdigit():
        raise UnsafeDispatch("unknown work queue depth")
    if int(depth) == 0:
        return "idle"

    # No optional demo bypass or client-supplied "approved" Boolean.
    try:
        release_gate()
    except Exception:
        raise UnsafeDispatch("independent release authorization denied") from None
    _verify_task(ecs, config)
    if _active_guest_count(ecs, config):
        return "already_running"

    now = int(clock())
    _release_finished_lease(ecs, dynamodb, config, now)
    token = token_factory()
    if not isinstance(token, str) or not re.fullmatch(r"[0-9a-f]{32}", token):
        raise UnsafeDispatch("invalid idempotency token")
    # 15-minute hold (>= SQS visibility timeout). The lease is deliberately
    # sticky after uncertain ECS exceptions to avoid rapid duplicate launches.
    ledger_item = {
        "pk": {"S": f"TENANT#{config.tenant}"},
        "token": {"S": token},
        "state": {"S": "launching"},
        "created_at": {"N": str(now)},
        "lease_until": {"N": str(now + 900)},
    }
    try:
        dynamodb.put_item(
            TableName=config.lease_table, Item=ledger_item,
            ConditionExpression="attribute_not_exists(pk) OR lease_until < :now",
            ExpressionAttributeValues={":now": {"N": str(now)}},
        )
    except Exception as exc:
        if (getattr(exc, "response", {}) or {}).get("Error", {}).get(
            "Code"
        ) == "ConditionalCheckFailedException":
            return "lease_held"
        raise

    state = "launch_uncertain"
    task_arn = None
    try:
        # Recheck immediately before RunTask to reduce policy/image drift
        # between first authorization and the acquired lease.
        release_gate()
        _verify_task(ecs, config)
        # Never set containerOverrides, command, launchType, or ECS Exec here.
        # Environment values remain pinned by the Nitro attestation policy.
        result = ecs.run_task(
            cluster=config.cluster,
            taskDefinition=config.task_definition_arn,
            capacityProviderStrategy=[
                {"capacityProvider": config.capacity_provider, "weight": 1}
            ],
            networkConfiguration={"awsvpcConfiguration": {
                "subnets": [config.subnet],
                "securityGroups": [config.security_group],
                "assignPublicIp": "DISABLED",
            }},
            count=1,
            enableExecuteCommand=False,
            clientToken=token,
            startedBy=f"notarai-{config.tenant}-{token[:16]}",
        )
        tasks = result.get("tasks", [])
        if not result.get("failures") and len(tasks) == 1:
            task_arn = tasks[0].get("taskArn")
            trust = tasks[0].get("trustedExecutionSummary") or {}
            if (isinstance(task_arn, str) and
                    task_arn.startswith(
                        f"arn:aws:ecs:{REGION}:{config.account}:task/"
                    ) and
                    trust.get("isolationMode") == "CONFIDENTIAL_SANDBOX" and
                    trust.get("attestationPolicyStatus") == "CONFIGURED"):
                state = "launched"
    except Exception:
        # ECS may have accepted the task even if its response was lost.
        # Keep the lease. Never call RunTask a second time in this invocation.
        pass
    try:
        updates = {
            ":token": {"S": token},
            ":state": {"S": state},
        }
        expression = "SET #s = :state"
        if task_arn and state == "launched":
            updates[":arn"] = {"S": task_arn}
            expression += ", task_arn = :arn"
        dynamodb.update_item(
            TableName=config.lease_table,
            Key={"pk": {"S": f"TENANT#{config.tenant}"}},
            UpdateExpression=expression,
            ConditionExpression="token = :token",
            ExpressionAttributeNames={"#s": "state"},
            ExpressionAttributeValues=updates,
        )
    except Exception:
        # The lease was saved before ECS RunTask. Do not attempt another start
        # merely because we failed to record the resulting task status.
        return "launch_uncertain"
    return state
