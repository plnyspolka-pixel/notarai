"""No AWS credentials, no customer data, no actual ECS launches."""
import copy
import zipfile

import pytest
import yaml

from confidential.dispatch import (
    DispatcherConfig,
    UnsafeDispatch,
    dispatch_once,
)
from scripts.package_confidential_dispatch import SOURCES, package
from test_confidential_infra import CloudFormationLoader, ROOT


ACCOUNT = "111122223333"
TENANT = "pilot01"
FAMILY = "notarai-confidential-pilot01"
TASK_ARN = f"arn:aws:ecs:eu-central-1:{ACCOUNT}:task-definition/{FAMILY}:12"
QUEUE = f"https://sqs.eu-central-1.amazonaws.com/{ACCOUNT}/{FAMILY}.fifo"
TABLE = f"notarai-confidential-dispatch-{TENANT}"


def config():
    return DispatcherConfig(
        account=ACCOUNT, tenant=TENANT,
        cluster=FAMILY, capacity_provider=FAMILY,
        task_definition_arn=TASK_ARN, queue_url=QUEUE,
        subnet="subnet-0123456789abcdef0",
        security_group="sg-0123456789abcdef0", lease_table=TABLE,
    )


def expected_task():
    return {"taskDefinition": {
        "taskDefinitionArn": TASK_ARN,
        "family": FAMILY, "status": "ACTIVE",
        "networkMode": "awsvpc",
        "requiresCompatibilities": ["MANAGED_INSTANCES"],
        "taskRoleArn": f"arn:aws:iam::{ACCOUNT}:role/{FAMILY}",
        "executionRoleArn": f"arn:aws:iam::{ACCOUNT}:role/notarai-confidential-execution-{TENANT}",
        "trustedExecutionConfiguration": {
            "isolationMode": "CONFIDENTIAL_SANDBOX",
            "attestationPolicy": "ZmljdGlvbmFsLXBsYWNlaG9sZGVy",
        },
        "containerDefinitions": [{
            "name": "confidential-browser",
            "image": f"{ACCOUNT}.dkr.ecr.eu-central-1.amazonaws.com/{FAMILY}@sha256:" + "f" * 64,
            "user": "10001:10001",
            "readonlyRootFilesystem": True,
            "environment": [
                {"name": "NOTARAI_CONFIDENTIAL_REQUIRED", "value": "1"},
                {"name": "NOTARAI_CONFIDENTIAL_TENANT", "value": TENANT},
                {"name": "NOTARAI_CONFIDENTIAL_QUEUE_URL", "value": QUEUE},
                {"name": "AWS_REGION", "value": "eu-central-1"},
                {"name": "NOTARAI_CONFIDENTIAL_BUCKET", "value": "notarai-ciphertext-pilot01"},
                {"name": "NOTARAI_CONFIDENTIAL_KMS_KEY_ARN",
                 "value": f"arn:aws:kms:eu-central-1:{ACCOUNT}:key/12345678-abcd"},
                {"name": "HOME", "value": "/tmp"},
                {"name": "XDG_CACHE_HOME", "value": "/tmp"},
                {"name": "TMPDIR", "value": "/tmp"},
            ],
        }],
    }}


class SQSFake:
    def __init__(self, count=1):
        self.count = count
        self.calls = []

    def get_queue_attributes(self, **kwargs):
        self.calls.append(kwargs)
        return {"Attributes": {"ApproximateNumberOfMessages": str(self.count)}}


class ECSFake:
    def __init__(self):
        self.definition = expected_task()
        self.running = []
        self.calls = []
        self.failures = False
        self.timeout_after_accept = False

    def describe_task_definition(self, **kwargs):
        assert kwargs == {"taskDefinition": TASK_ARN}
        return copy.deepcopy(self.definition)

    def describe_capacity_providers(self, **kwargs):
        assert kwargs == {"capacityProviders": [FAMILY]}
        return {"capacityProviders": [{
            "name": FAMILY, "status": "ACTIVE",
            "managedInstancesProvider": {
                "instanceLaunchTemplate": {
                    "nitroEnclavesEnabled": True,
                    "networkConfiguration": {
                        "subnets": [config().subnet],
                        "securityGroups": [config().security_group],
                    },
                },
            },
        }]}

    def list_tasks(self, **kwargs):
        assert kwargs["desiredStatus"] == "RUNNING" and kwargs["family"] == FAMILY
        return {"taskArns": self.running}

    def describe_tasks(self, **kwargs):
        assert kwargs["cluster"] == FAMILY
        status = getattr(self, "last_status", "PENDING")
        return {"tasks": [{
            "taskArn": kwargs["tasks"][0],
            "taskDefinitionArn": TASK_ARN,
            "clusterArn": f"arn:aws:ecs:eu-central-1:{ACCOUNT}:cluster/{FAMILY}",
            "startedBy": self.calls[-1]["startedBy"] if self.calls else "",
            "lastStatus": status,
            "desiredStatus": "STOPPED" if status == "STOPPED" else "RUNNING",
        }]}

    def run_task(self, **kwargs):
        self.calls.append(kwargs)
        assert kwargs["count"] == 1
        assert kwargs["capacityProviderStrategy"][0]["capacityProvider"] == FAMILY
        assert kwargs["networkConfiguration"]["awsvpcConfiguration"]["assignPublicIp"] == "DISABLED"
        assert not kwargs.get("overrides")
        assert kwargs["enableExecuteCommand"] is False
        if self.timeout_after_accept:
            raise TimeoutError("connection dropped after RunTask")
        if self.failures:
            return {"tasks": [], "failures": [{"reason": "synthetic-capacity"}]}
        return {"tasks": [{
            "taskArn": f"arn:aws:ecs:eu-central-1:{ACCOUNT}:task/{FAMILY}/test-task",
            "trustedExecutionSummary": {
                "isolationMode": "CONFIDENTIAL_SANDBOX",
                "attestationPolicyStatus": "CONFIGURED",
            },
        }]}


class ConditionalFailure(Exception):
    response = {"Error": {"Code": "ConditionalCheckFailedException"}}


class DynamoFake:
    def __init__(self):
        self.item = None
        self.put_calls = 0
        self.updated = False

    def put_item(self, **kwargs):
        self.put_calls += 1
        now = int(kwargs["ExpressionAttributeValues"][":now"]["N"])
        if self.item and int(self.item["lease_until"]["N"]) >= now:
            raise ConditionalFailure()
        self.item = copy.deepcopy(kwargs["Item"])

    def get_item(self, **kwargs):
        assert kwargs["ConsistentRead"] is True
        return {"Item": copy.deepcopy(self.item)} if self.item else {}

    def update_item(self, **kwargs):
        assert self.item["token"]["S"] == kwargs["ExpressionAttributeValues"][":token"]["S"]
        args = kwargs["ExpressionAttributeValues"]
        if ":finished" in args:
            assert self.item["state"]["S"] == "launched"
            self.item["state"] = args[":finished"]
            self.item["lease_until"] = args[":expired"]
        else:
            self.item["state"] = args[":state"]
            if ":arn" in args:
                self.item["task_arn"] = args[":arn"]
        self.updated = True


def tick(ecs=None, sqs=None, ddb=None, now=1000, token="a" * 32):
    ecs = ecs or ECSFake()
    sqs = sqs or SQSFake()
    ddb = ddb or DynamoFake()
    state = dispatch_once(
        config(), sqs=sqs, ecs=ecs, dynamodb=ddb,
        clock=lambda: now, token_factory=lambda: token
    )
    return state, ecs, sqs, ddb


def test_synthetic_launch_uses_pinned_task_and_one_lease():
    state, ecs, sqs, ddb = tick()
    assert state == "launched" and len(ecs.calls) == 1
    assert ddb.item["state"]["S"] == "launched"
    assert ddb.item["lease_until"]["N"] == "1900"
    assert ecs.calls[0]["clientToken"] == "a" * 32
    assert len(sqs.calls) == 1
    assert not hasattr(sqs, "receive_message")


def test_idle_queue_never_launches_a_guest():
    state, ecs, _, ddb = tick(sqs=SQSFake(0))
    assert state == "idle"
    assert not ecs.calls and ddb.item is None


def test_existing_guest_prevents_launch():
    ecs = ECSFake()
    ecs.running = ["arn:aws:ecs:eu-central-1:111122223333:task/active"]
    state, _, _, ddb = tick(ecs=ecs)
    assert state == "already_running"
    assert not ecs.calls and ddb.item is None


def test_finished_worker_lease_is_released_for_next_preview():
    ecs, sqs, ddb = ECSFake(), SQSFake(), DynamoFake()
    assert tick(ecs, sqs, ddb)[0] == "launched"
    ecs.last_status = "STOPPED"
    assert tick(ecs, sqs, ddb, now=1050, token="b" * 32)[0] == "launched"
    assert len(ecs.calls) == 2
    assert ddb.item["token"]["S"] == "b" * 32


def test_pending_worker_never_releases_lease():
    ecs, sqs, ddb = ECSFake(), SQSFake(), DynamoFake()
    assert tick(ecs, sqs, ddb)[0] == "launched"
    ecs.last_status = "PENDING"
    assert tick(ecs, sqs, ddb, now=1050)[0] == "lease_held"
    assert len(ecs.calls) == 1


def test_duplicate_dispatch_does_not_launch_twice():
    ecs, sqs, ddb = ECSFake(), SQSFake(), DynamoFake()
    first = tick(ecs, sqs, ddb)
    second = tick(ecs, sqs, ddb)
    assert first[0] == "launched"
    assert second[0] == "lease_held"
    assert len(ecs.calls) == 1


def test_ambiguous_run_task_response_never_causes_immediate_retry():
    ecs, ddb = ECSFake(), DynamoFake()
    ecs.timeout_after_accept = True
    state, _, _, _ = tick(ecs=ecs, ddb=ddb)
    assert state == "launch_uncertain" and len(ecs.calls) == 1
    assert tick(ecs=ecs, ddb=ddb)[0] == "lease_held"
    assert len(ecs.calls) == 1


def test_explicit_ecs_failure_preserves_reviewable_lease():
    ecs = ECSFake()
    ecs.failures = True
    state, _, _, ddb = tick(ecs=ecs)
    assert state == "launch_uncertain"
    assert ddb.item["state"]["S"] == "launch_uncertain"


@pytest.mark.parametrize("modify", [
    lambda task: task["taskDefinition"].update(status="INACTIVE"),
    lambda task: task["taskDefinition"]["trustedExecutionConfiguration"].update(
        isolationMode="SHARED"
    ),
    lambda task: task["taskDefinition"]["containerDefinitions"][0].update(
        image="fake:latest"
    ),
    lambda task: task["taskDefinition"]["containerDefinitions"][0].update(
        environment=[]
    ),
    lambda task: task["taskDefinition"]["containerDefinitions"][0].update(
        logConfiguration={"logDriver": "awslogs"}
    ),
    lambda task: task["taskDefinition"]["containerDefinitions"].append({}),
])
def test_unapproved_task_definition_blocks_lease_and_launch(modify):
    ecs = ECSFake()
    modify(ecs.definition)
    ddb = DynamoFake()
    with pytest.raises(UnsafeDispatch):
        tick(ecs=ecs, ddb=ddb)
    assert ddb.item is None and not ecs.calls


def test_capacity_provider_with_broad_or_wrong_sg_is_rejected():
    ecs = ECSFake()
    original = ecs.describe_capacity_providers
    def wrong_provider(**kwargs):
        payload = original(**kwargs)
        payload["capacityProviders"][0]["managedInstancesProvider"][
            "instanceLaunchTemplate"
        ]["networkConfiguration"]["securityGroups"] = ["sg-fffffffffffffffff"]
        return payload
    ecs.describe_capacity_providers = wrong_provider
    with pytest.raises(UnsafeDispatch, match="private"):
        tick(ecs=ecs)
    assert not ecs.calls


def test_invalid_target_blocks_without_aws():
    bad = DispatcherConfig(**{**config().__dict__, "queue_url": "https://example.com"})
    with pytest.raises(UnsafeDispatch):
        bad.validate()


def test_lambda_package_contains_only_pinned_source(tmp_path):
    path = tmp_path / "dispatcher.zip"
    digest = package(path)
    with zipfile.ZipFile(path) as z:
        assert set(z.namelist()) == set(SOURCES)
        assert b"def dispatch_once" in z.read("confidential/dispatch.py")
    assert len(digest) == 64
    assert package(path) == digest


def test_cloudformation_schedule_disabled_and_no_live_service():
    template = yaml.load(
        (ROOT / "notarai-confidential-dispatch.yaml").read_text("utf-8"),
        Loader=CloudFormationLoader,
    )
    assert template["Parameters"]["DispatchEnabled"]["Default"] == "false"
    resources = template["Resources"]
    assert "DispatcherSchedule" in resources
    assert resources["DispatcherSchedule"]["Properties"]["State"] == {
        "If": ["EnableScheduler", "ENABLED", "DISABLED"]
    }
    assert resources["DispatcherFunction"]["Properties"]["ReservedConcurrentExecutions"] == 1
    assert not any(x["Type"] == "AWS::ECS::Service" for x in resources.values())
    statements = resources["DispatcherRole"]["Properties"]["Policies"][0][
        "PolicyDocument"
    ]["Statement"]
    assert any(item.get("Action") == "ecs:RunTask" for item in statements)
    assert any(item.get("Action") == "iam:PassRole" and
               len(item["Resource"]) == 2 for item in statements)
    actions = []
    for item in statements:
        value = item.get("Action", [])
        actions.extend([value] if isinstance(value, str) else value)
    assert "sqs:ReceiveMessage" not in actions
    assert "sqs:DeleteMessage" not in actions


def test_cross_tenant_stopped_task_does_not_release_dispatch_lease():
    ecs, sqs, ddb = ECSFake(), SQSFake(), DynamoFake()
    assert tick(ecs, sqs, ddb)[0] == "launched"
    ecs.last_status = "STOPPED"
    original = ecs.describe_tasks

    def foreign(**kwargs):
        payload = original(**kwargs)
        payload["tasks"][0]["taskDefinitionArn"] = (
            f"arn:aws:ecs:eu-central-1:{ACCOUNT}:task-definition/notarai-confidential-pilot02:3"
        )
        payload["tasks"][0]["startedBy"] = "notarai-pilot02-" + "a" * 16
        return payload

    ecs.describe_tasks = foreign
    assert tick(ecs, sqs, ddb, now=1050, token="b" * 32)[0] == "lease_held"
    assert len(ecs.calls) == 1


def test_wrong_cluster_task_arn_is_rejected_before_release():
    from confidential.dispatch import _release_finished_lease
    ecs, sqs, ddb = ECSFake(), SQSFake(), DynamoFake()
    assert tick(ecs, sqs, ddb)[0] == "launched"
    ddb.item["task_arn"]["S"] = (
        f"arn:aws:ecs:eu-central-1:{ACCOUNT}:task/notarai-confidential-pilot02/foreign"
    )
    with pytest.raises(UnsafeDispatch, match="untrusted task identity"):
        _release_finished_lease(ecs, ddb, config(), 1050)
