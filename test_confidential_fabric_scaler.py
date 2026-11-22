"""On-demand shared Interface endpoints: offline tests, no AWS resources."""
import datetime
import zipfile

import pytest
import yaml

from confidential import fabric_scaler as fs
from confidential.fabric_scaler import (
    FLAG, STACK, ScalerConfig, ScalerRejected, decide, endpoints_ready,
    scale_once,
)
from test_confidential_infra import ROOT, CloudFormationLoader

ACCOUNT = "111122223333"
NOW = 1_800_000_000
PARAMS = ["SharedNetworkName", "AvailabilityZone", FLAG, "EnableStsEndpoint",
          "EnableLogsEndpoint", "EnableSignerEndpoint", "S3PrefixListId",
          "DynamoDbPrefixListId"]


def cfg(**kw):
    return ScalerConfig(account=ACCOUNT, tenants=("pilot02", "pilot03"), **kw)


class Queues:
    def __init__(self, depth=None, broken=None):
        self.depth, self.broken, self.seen = depth or {}, broken, []

    def get_queue_attributes(self, **kwargs):
        url = kwargs["QueueUrl"]
        prefix = f"https://sqs.eu-central-1.amazonaws.com/{ACCOUNT}/notarai-confidential-"
        assert url.startswith(prefix) and url.endswith(".fifo")
        assert "-dead" not in url  # the dead-letter queue is not work
        tenant = url[len(prefix):-5]
        self.seen.append(tenant)
        if self.broken == tenant:
            return {"Attributes": {"ApproximateNumberOfMessages": "?"}}
        visible, inflight, delayed = self.depth.get(tenant, (0, 0, 0))
        return {"Attributes": {
            "ApproximateNumberOfMessages": str(visible),
            "ApproximateNumberOfMessagesNotVisible": str(inflight),
            "ApproximateNumberOfMessagesDelayed": str(delayed),
        }}


class Guests:
    def __init__(self, tasks=(), token=None, broken=False):
        self.tasks, self.token, self.broken = list(tasks), token, broken

    def list_tasks(self, **kwargs):
        assert kwargs == {"cluster": "notarai-confidential-shared",
                          "desiredStatus": "RUNNING", "maxResults": 100}
        if self.broken:
            return {}
        return {"taskArns": self.tasks, **({"nextToken": self.token} if self.token else {})}


class Stacks:
    def __init__(self, on, age=10_000, status="UPDATE_COMPLETE", params=None):
        self.on, self.age, self.status, self.updates = on, age, status, []
        self.params = PARAMS if params is None else params

    def describe_stacks(self, **kwargs):
        assert kwargs == {"StackName": STACK}
        return {"Stacks": [{
            "StackName": STACK, "StackStatus": self.status,
            "LastUpdatedTime": datetime.datetime.fromtimestamp(
                NOW - self.age, datetime.timezone.utc),
            "Parameters": [
                {"ParameterKey": k,
                 "ParameterValue": ("true" if self.on else "false") if k == FLAG else "x"}
                for k in self.params],
        }]}

    def update_stack(self, **kwargs):
        self.updates.append(kwargs)


def run(stack, queues=None, guests=None, config=None):
    return scale_once(config or cfg(), sqs=queues or Queues(),
                      ecs=guests or Guests(), cloudformation=stack,
                      clock=lambda: NOW)


def test_decision_table():
    kw = dict(min_on_seconds=3000)
    assert decide(work=True, endpoints_on=False, on_for_seconds=0, **kw) == "enable"
    assert decide(work=True, endpoints_on=True, on_for_seconds=99999, **kw) == "ready"
    assert decide(work=False, endpoints_on=False, on_for_seconds=99999, **kw) == "idle"
    assert decide(work=False, endpoints_on=True, on_for_seconds=2999, **kw) == "cooling"
    assert decide(work=False, endpoints_on=True, on_for_seconds=3000, **kw) == "disable"
    for bad in (dict(work=None, endpoints_on=True), dict(work=True, endpoints_on="true")):
        with pytest.raises(ScalerRejected):
            decide(on_for_seconds=0, **kw, **bad)


def test_queued_work_turns_endpoints_on_with_one_parameter_change():
    stack = Stacks(on=False)
    assert run(stack, Queues({"pilot03": (1, 0, 0)})) == "enabling"
    assert len(stack.updates) == 1
    call = stack.updates[0]
    assert set(call) == {"StackName", "UsePreviousTemplate", "Parameters"}
    assert call["StackName"] == STACK and call["UsePreviousTemplate"] is True
    changed = [p for p in call["Parameters"] if "ParameterValue" in p]
    assert changed == [{"ParameterKey": FLAG, "ParameterValue": "true"}]
    kept = [p for p in call["Parameters"] if p not in changed]
    assert kept == [{"ParameterKey": k, "UsePreviousValue": True}
                    for k in PARAMS if k != FLAG]
    # No template, role, capability, tag or policy can be smuggled in.
    assert not {"TemplateBody", "TemplateURL", "RoleARN", "Capabilities",
                "StackPolicyBody", "Tags"} & set(call)


@pytest.mark.parametrize("queues,guests", [
    (Queues({"pilot02": (0, 1, 0)}), Guests()),      # message being processed
    (Queues({"pilot02": (0, 0, 1)}), Guests()),      # delayed message
    (Queues(), Guests(tasks=["arn:task/1"])),        # guest still running
    (Queues(), Guests(token="more")),                # unknown further pages
])
def test_endpoints_never_removed_while_any_tenant_has_work(queues, guests):
    stack = Stacks(on=True, age=999_999)
    assert run(stack, queues, guests) == "ready"
    assert stack.updates == []


def test_idle_endpoints_are_removed_only_after_minimum_on_time():
    young = Stacks(on=True, age=2999)
    assert run(young) == "cooling" and young.updates == []
    old = Stacks(on=True, age=3000)
    assert run(old) == "disabling"
    assert [p for p in old.updates[0]["Parameters"] if "ParameterValue" in p] == [
        {"ParameterKey": FLAG, "ParameterValue": "false"}]
    off = Stacks(on=False)
    assert run(off) == "idle" and off.updates == []


@pytest.mark.parametrize("status,expected", [
    ("UPDATE_IN_PROGRESS", "changing"),
    ("UPDATE_COMPLETE_CLEANUP_IN_PROGRESS", "changing"),
    ("UPDATE_ROLLBACK_COMPLETE", "needs_review"),
    ("UPDATE_ROLLBACK_FAILED", "needs_review"),
    ("ROLLBACK_COMPLETE", "needs_review"),
])
def test_unstable_or_failed_stack_is_never_updated_again(status, expected):
    stack = Stacks(on=False, status=status)
    queues = Queues({"pilot02": (5, 0, 0)})
    assert run(stack, queues) == expected
    assert stack.updates == [] and queues.seen == []


@pytest.mark.parametrize("stack,queues,guests", [
    (Stacks(on=True, age=999_999), Queues(broken="pilot03"), Guests()),
    (Stacks(on=False), Queues(broken="pilot02"), Guests()),
    (Stacks(on=True, age=999_999), Queues(), Guests(broken=True)),
    (Stacks(on=True, params=[p for p in PARAMS if p != FLAG]), Queues(), Guests()),
    (Stacks(on=True, params=PARAMS + [FLAG]), Queues(), Guests()),
])
def test_unreadable_state_changes_nothing(stack, queues, guests):
    with pytest.raises(ScalerRejected):
        run(stack, queues, guests)
    assert stack.updates == []


@pytest.mark.parametrize("bad", [
    dict(account="12345"), dict(tenants=()), dict(tenants=["pilot02"]),
    dict(tenants=("pilot02", "pilot02")), dict(tenants=("Pilot02",)),
    dict(tenants=("pilot02", "x-dead")), dict(min_on_seconds=-1),
    dict(min_on_seconds=True), dict(tenants=tuple(f"t{i}" for i in range(51))),
])
def test_invalid_configuration_is_rejected_before_any_aws_call(bad):
    values = dict(account=ACCOUNT, tenants=("pilot02",), min_on_seconds=3000)
    values.update(bad)

    class Never:
        def __getattr__(self, name):
            raise AssertionError("no AWS call allowed")
    with pytest.raises(ScalerRejected):
        scale_once(ScalerConfig(**values), sqs=Never(), ecs=Never(),
                   cloudformation=Never())


def test_endpoints_ready_requires_every_core_service_available():
    from test_confidential_shared_fabric import EndpointsFake, FABRIC_VPC
    assert endpoints_ready(EndpointsFake(), FABRIC_VPC) is True
    for service in fs.REQUIRED_SERVICES:
        assert endpoints_ready(EndpointsFake(missing={service}), FABRIC_VPC) is False
    assert endpoints_ready(EndpointsFake(state="pending"), FABRIC_VPC) is False
    with pytest.raises(ScalerRejected):
        endpoints_ready(EndpointsFake(paged=True), FABRIC_VPC)
    with pytest.raises(ScalerRejected):
        endpoints_ready(EndpointsFake(), "vpc-not-valid")
    # Same seven services the template gates and the verifier requires.
    from confidential.shared_fabric import _REQUIRED
    assert fs.REQUIRED_SERVICES == set(_REQUIRED)


def test_lambda_is_inert_unless_enabled_and_ticked(monkeypatch):
    from confidential import fabric_scaler_lambda as entry
    monkeypatch.delenv("NOTARAI_FABRIC_SCALER_ENABLED", raising=False)
    assert entry.handler({"source": "notarai.confidential.fabric"}, None) == {"state": "disabled"}
    monkeypatch.setenv("NOTARAI_FABRIC_SCALER_ENABLED", "true")
    assert entry.handler({"source": "something.else"}, None) == {"state": "ignored"}
    assert entry.handler("not-a-dict", None) == {"state": "ignored"}


def _template(name):
    return yaml.load((ROOT / name).read_text("utf-8"), Loader=CloudFormationLoader)


def test_scaler_template_can_only_flip_the_one_stack_through_cloudformation():
    t = _template("notarai-confidential-fabric-scaler.yaml")
    assert t["Parameters"]["ScalerEnabled"]["Default"] == "false"
    assert t["Resources"]["ScalerSchedule"]["Properties"]["State"] == {
        "If": ["EnableSchedule", "ENABLED", "DISABLED"]}
    assert {r["Type"] for r in t["Resources"].values()} == {
        "AWS::IAM::Role", "AWS::Lambda::Function", "AWS::Events::Rule",
        "AWS::Lambda::Permission"}
    role = t["Resources"]["ScalerRole"]["Properties"]
    assert role["ManagedPolicyArns"] == [
        "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"]
    statements = {s["Sid"]: s for s in role["Policies"][0]["PolicyDocument"]["Statement"]}
    flip = statements["FlipOnlyTheSharedFabricStack"]
    assert flip["Action"] == ["cloudformation:DescribeStacks", "cloudformation:UpdateStack"]
    assert flip["Resource"]["Sub"].endswith(":stack/notarai-confidential-shared-fabric/*")
    write = statements["EndpointChangesOnlyViaCloudFormation"]
    assert write["Condition"]["ForAnyValue:StringEquals"] == {
        "aws:CalledVia": "cloudformation.amazonaws.com"}
    assert write["Condition"]["StringEquals"] == {"aws:RequestedRegion": "eu-central-1"}
    assert set(write["Action"]) == {
        "ec2:CreateVpcEndpoint", "ec2:DeleteVpcEndpoints", "ec2:CreateTags",
        "ec2:DeleteTags", "route53:AssociateVPCWithHostedZone"}
    every = [a for s in statements.values()
             for a in (s["Action"] if isinstance(s["Action"], list) else [s["Action"]])]
    assert all(s["Effect"] == "Allow" for s in statements.values())
    forbidden = ("*", "iam:", "kms:", "s3:", "dynamodb:", "secretsmanager:",
                 "ecs:RunTask", "ecs:StopTask", "sqs:Receive", "sqs:Delete",
                 "sqs:Send", "sqs:Purge", "Route", "Gateway", "SecurityGroupIngress",
                 "SecurityGroupEgress", "AuthorizeSecurityGroup", "RunInstances",
                 "cloudformation:Create", "cloudformation:Delete",
                 "cloudformation:SetStackPolicy")
    for action in every:
        assert "*" not in action, action
        if action.startswith("ec2:Describe"):
            continue  # read-only network inventory
        assert not any(f in action for f in forbidden if f != "*"), action
    unconditional_writes = [
        a for s in statements.values() if "Condition" not in s
        for a in (s["Action"] if isinstance(s["Action"], list) else [s["Action"]])
        if not (a.startswith("ec2:Describe") or a in (
            "sqs:GetQueueAttributes", "cloudformation:DescribeStacks",
            "cloudformation:UpdateStack"))]
    assert unconditional_writes == []
    function = t["Resources"]["ScalerFunction"]["Properties"]
    assert function["Handler"] == "confidential.fabric_scaler_lambda.handler"
    assert set(function["Environment"]["Variables"]) == {
        "NOTARAI_FABRIC_SCALER_ENABLED", "NOTARAI_ACCOUNT", "NOTARAI_TENANTS",
        "NOTARAI_MIN_ON_SECONDS"}


def test_dispatcher_template_wires_shared_vpc_and_read_only_endpoint_lookup():
    t = _template("notarai-confidential-dispatch.yaml")
    assert t["Parameters"]["SharedVpcId"]["Default"] == ""
    assert set(t["Rules"]) == {"SharedComputeNamesItsVpc", "TenantPoolNamesNoVpc"}
    env = t["Resources"]["DispatcherFunction"]["Properties"]["Environment"]["Variables"]
    assert env["NOTARAI_FABRIC_VPC"] == {"Ref": "SharedVpcId"}
    statements = {s["Sid"]: s for s in t["Resources"]["DispatcherRole"][
        "Properties"]["Policies"][0]["PolicyDocument"]["Statement"]}
    assert statements["ReadSharedEndpointReadiness"]["Action"] == "ec2:DescribeVpcEndpoints"
    ec2_actions = [a for s in statements.values()
                   for a in (s["Action"] if isinstance(s["Action"], list) else [s["Action"]])
                   if a.startswith("ec2:")]
    assert ec2_actions == ["ec2:DescribeVpcEndpoints"]


def test_dispatcher_zip_contains_the_readiness_module(tmp_path):
    from scripts.package_confidential_dispatch import package
    out = tmp_path / "d.zip"
    first = package(out)
    assert set(zipfile.ZipFile(out).namelist()) == {
        "confidential/__init__.py", "confidential/dispatch.py",
        "confidential/dispatch_lambda.py", "confidential/fabric_scaler.py",
        "confidential/fabric_scaler_lambda.py"}
    assert package(tmp_path / "e.zip") == first  # reproducible
