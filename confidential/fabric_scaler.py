"""On-demand switch for the hourly billed shared Interface endpoints.

The shared confidential VPC has no NAT and no Internet route, so a Nitro host
can only work while the seven core Interface endpoints exist. They are billed
per started hour even when idle. This controller keeps them OFF while no
tenant has work and turns them ON when a job is queued or a guest runs.

It never touches documents, keys, queues' contents or tasks. Its only write is
one CloudFormation UpdateStack that flips ONE parameter of the ONE shared
fabric stack (same template, every other parameter unchanged), so the network
keeps a single source of truth and the fail-closed verifier keeps working.

Uncertainty rules: an unreadable queue, task list or stack state changes
nothing. Endpoints are never removed while any tenant has a queued, in-flight
or running job, and never before ``min_on_seconds`` (the started hour is paid
for anyway). Removing them is a cost decision; it cannot expose data.
"""
from __future__ import annotations

import datetime
import re
import time
from dataclasses import dataclass

REGION = "eu-central-1"
STACK = "notarai-confidential-shared-fabric"
CLUSTER = "notarai-confidential-shared"
FLAG = "EnableCoreInterfaceEndpoints"
REQUIRED_SERVICES = frozenset({
    "kms", "sqs", "ecr.api", "ecr.dkr", "ecs", "ecs-agent", "ecs-telemetry",
})
_ACCOUNT = re.compile(r"^[0-9]{12}$")
_TENANT = re.compile(r"^[a-z0-9]{1,12}$")
_VPC = re.compile(r"^vpc-(?:[0-9a-f]{8}|[0-9a-f]{17})$")
_STABLE = ("CREATE_COMPLETE", "UPDATE_COMPLETE")
_QUEUE_COUNTERS = (
    "ApproximateNumberOfMessages",
    "ApproximateNumberOfMessagesNotVisible",
    "ApproximateNumberOfMessagesDelayed",
)


class ScalerRejected(RuntimeError):
    """No AWS identifiers or exception text in this error."""


@dataclass(frozen=True)
class ScalerConfig:
    account: str
    tenants: tuple
    min_on_seconds: int = 3000

    def validate(self) -> None:
        if not isinstance(self.account, str) or not _ACCOUNT.fullmatch(self.account):
            raise ScalerRejected("invalid account")
        if (type(self.tenants) is not tuple or not 1 <= len(self.tenants) <= 50 or
                len(set(self.tenants)) != len(self.tenants) or
                not all(isinstance(t, str) and _TENANT.fullmatch(t)
                        for t in self.tenants)):
            raise ScalerRejected("invalid tenant list")
        if type(self.min_on_seconds) is not int or not 0 <= self.min_on_seconds <= 86400:
            raise ScalerRejected("invalid minimum on-time")


def decide(*, work: bool, endpoints_on: bool, on_for_seconds: int,
           min_on_seconds: int) -> str:
    """Pure decision table. Returns enable | disable | ready | cooling | idle."""
    if type(work) is not bool or type(endpoints_on) is not bool:
        raise ScalerRejected("unknown fabric state")
    if work:
        return "ready" if endpoints_on else "enable"
    if not endpoints_on:
        return "idle"
    if type(on_for_seconds) is not int or on_for_seconds < min_on_seconds:
        return "cooling"
    return "disable"


def _queue_has_work(sqs, account: str, tenant: str) -> bool:
    url = (f"https://sqs.{REGION}.amazonaws.com/{account}/"
           f"notarai-confidential-{tenant}.fifo")
    attributes = sqs.get_queue_attributes(
        QueueUrl=url, AttributeNames=list(_QUEUE_COUNTERS),
    ).get("Attributes") or {}
    total = 0
    for name in _QUEUE_COUNTERS:
        value = attributes.get(name)
        if not isinstance(value, str) or not value.isdecimal():
            raise ScalerRejected("unknown work queue depth")
        total += int(value)
    return total > 0


def _guests_active(ecs) -> bool:
    response = ecs.list_tasks(
        cluster=CLUSTER, desiredStatus="RUNNING", maxResults=100,
    )
    tasks = response.get("taskArns")
    if not isinstance(tasks, list):
        raise ScalerRejected("unknown guest task inventory")
    # More than one page still means "something is running".
    return bool(tasks) or bool(response.get("nextToken"))


def scale_once(config: ScalerConfig, *, sqs, ecs, cloudformation,
               clock=time.time) -> str:
    config.validate()
    stacks = cloudformation.describe_stacks(StackName=STACK).get("Stacks") or []
    if len(stacks) != 1 or stacks[0].get("StackName") != STACK:
        raise ScalerRejected("shared fabric stack not found")
    stack = stacks[0]
    status = stack.get("StackStatus")
    if isinstance(status, str) and status.endswith("_IN_PROGRESS"):
        return "changing"
    if status not in _STABLE:
        # Rolled back or failed: a person must look, never loop on updates.
        return "needs_review"
    parameters = stack.get("Parameters") or []
    names = [p.get("ParameterKey") for p in parameters if isinstance(p, dict)]
    current = {p.get("ParameterKey"): p.get("ParameterValue")
               for p in parameters if isinstance(p, dict)}
    if (len(names) != len(set(names)) or FLAG not in current or
            current[FLAG] not in ("true", "false") or
            not all(isinstance(n, str) and n for n in names)):
        raise ScalerRejected("shared fabric stack has no endpoint switch")
    endpoints_on = current[FLAG] == "true"

    work = any(_queue_has_work(sqs, config.account, t) for t in config.tenants)
    work = _guests_active(ecs) or work

    changed = stack.get("LastUpdatedTime") or stack.get("CreationTime")
    if not isinstance(changed, datetime.datetime):
        raise ScalerRejected("unknown fabric change time")
    if changed.tzinfo is None:
        changed = changed.replace(tzinfo=datetime.timezone.utc)
    on_for = int(clock() - changed.timestamp())

    action = decide(work=work, endpoints_on=endpoints_on,
                    on_for_seconds=on_for,
                    min_on_seconds=config.min_on_seconds)
    if action not in ("enable", "disable"):
        return action
    target = "true" if action == "enable" else "false"
    cloudformation.update_stack(
        StackName=STACK,
        UsePreviousTemplate=True,
        Parameters=[
            {"ParameterKey": name, "ParameterValue": target} if name == FLAG
            else {"ParameterKey": name, "UsePreviousValue": True}
            for name in names
        ],
    )
    return "enabling" if action == "enable" else "disabling"


def endpoints_ready(ec2, vpc_id: str) -> bool:
    """True only when every core Interface endpoint of the shared VPC is usable.

    Used by the per-tenant dispatcher before RunTask: a Nitro host started
    without them cannot register with ECS and would only burn EC2 time.
    """
    if not isinstance(vpc_id, str) or not _VPC.fullmatch(vpc_id):
        raise ScalerRejected("invalid shared VPC")
    response = ec2.describe_vpc_endpoints(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}],
    )
    if response.get("NextToken"):
        raise ScalerRejected("incomplete endpoint inventory")
    stem = f"com.amazonaws.{REGION}."
    ready = set()
    for item in response.get("VpcEndpoints") or []:
        if (isinstance(item, dict) and item.get("VpcId") == vpc_id and
                item.get("VpcEndpointType") == "Interface" and
                item.get("State") == "available" and
                item.get("PrivateDnsEnabled") is True and
                isinstance(item.get("ServiceName"), str) and
                item["ServiceName"].startswith(stem)):
            ready.add(item["ServiceName"][len(stem):])
    return REQUIRED_SERVICES <= ready
