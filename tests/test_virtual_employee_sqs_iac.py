"""Offline-only assertions for the OPTIONAL synthetic SQS bridge.

No AWS connection, no cloud resource creation, no customer information.
"""
from pathlib import Path

import yaml

TEMPLATE = (
    Path(__file__).resolve().parents[1] / "infra" / "virtual-employee" /
    "notarai-ve-sqs-pilot.yaml"
)


class CfnLoader(yaml.SafeLoader):
    pass


def cloudformation_tag(loader, suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return {suffix: loader.construct_scalar(node)}
    if isinstance(node, yaml.SequenceNode):
        return {suffix: loader.construct_sequence(node)}
    return {suffix: loader.construct_mapping(node)}


CfnLoader.add_multi_constructor("!", cloudformation_tag)
CFN = yaml.load(TEMPLATE.read_text(encoding="utf-8"), Loader=CfnLoader)
RESOURCES = CFN["Resources"]


def properties(key):
    return RESOURCES[key]["Properties"]


def test_transport_is_private_only_and_requires_existing_vm():
    assert CFN["Parameters"]["VpcId"]["Type"] == "AWS::EC2::VPC::Id"
    assert CFN["Parameters"]["PrivateSubnetId"]["Type"] == "AWS::EC2::Subnet::Id"
    assert CFN["Parameters"]["EndpointSecurityGroupId"]["Type"] == "AWS::EC2::SecurityGroup::Id"
    assert CFN["Parameters"]["WindowsRoleName"]["Type"] == "String"
    assert {x["Type"] for x in RESOURCES.values()}.isdisjoint({
        "AWS::EC2::InternetGateway", "AWS::EC2::NatGateway", "AWS::EC2::Route",
        "AWS::EC2::SecurityGroup", "AWS::EC2::Instance", "AWS::EC2::SecurityGroupIngress",
    })
    endpoint = properties("SqsEndpoint")
    assert endpoint["VpcEndpointType"] == "Interface"
    assert endpoint["PrivateDnsEnabled"] is True
    assert endpoint["ServiceName"] == {"Sub": "com.amazonaws.${AWS::Region}.sqs"}
    assert endpoint["SubnetIds"] == [{"Ref": "PrivateSubnetId"}]
    assert endpoint["SecurityGroupIds"] == [{"Ref": "EndpointSecurityGroupId"}]


def test_fifo_encryption_retention_and_dlq():
    for name in ("PilotDeadLetterQueue", "PilotJobQueue"):
        p = properties(name)
        assert p["FifoQueue"] is True
        assert p["SqsManagedSseEnabled"] is True
        assert p["QueueName"] == {
            "Sub": "notarai-ve-${TenantId}-dead.fifo" if name == "PilotDeadLetterQueue"
            else "notarai-ve-${TenantId}-jobs.fifo"
        }
    q = properties("PilotJobQueue")
    assert q["VisibilityTimeout"] == 60
    assert q["ReceiveMessageWaitTimeSeconds"] == 20
    assert q["MessageRetentionPeriod"] == 86400
    assert q["RedrivePolicy"]["maxReceiveCount"] == 3
    assert q["RedrivePolicy"]["deadLetterTargetArn"] == {
        "GetAtt": "PilotDeadLetterQueue.Arn"
    }
    assert properties("PilotDeadLetterQueue")["MessageRetentionPeriod"] == 1209600


def test_instance_role_can_only_consume_from_tenant_queue_vpce():
    policy = properties("WindowsConsumerPolicy")
    assert policy["Roles"] == [{"Ref": "WindowsRoleName"}]
    statement = policy["PolicyDocument"]["Statement"]
    assert len(statement) == 1
    actions = set(statement[0]["Action"])
    assert actions == {
        "sqs:ReceiveMessage", "sqs:DeleteMessage",
        "sqs:ChangeMessageVisibility", "sqs:GetQueueAttributes",
    }
    assert "sqs:SendMessage" not in actions
    assert statement[0]["Resource"] == {"GetAtt": "PilotJobQueue.Arn"}
    assert statement[0]["Condition"]["StringEquals"]["aws:sourceVpce"] == {
        "Ref": "SqsEndpoint"
    }


def test_queue_policy_denies_plaintext_and_nonprivate_consumers():
    policy = properties("QueueAccessPolicy")["PolicyDocument"]["Statement"]
    deny = {item["Sid"]: item for item in policy}
    assert set(deny) == {"DenyPlaintext", "DenyConsumerOutsidePrivateEndpoint"}
    for statement in deny.values():
        assert statement["Effect"] == "Deny"
        assert statement["Resource"] == {"GetAtt": "PilotJobQueue.Arn"}
    assert deny["DenyPlaintext"]["Condition"]["Bool"]["aws:SecureTransport"] == "false"
    isolated = deny["DenyConsumerOutsidePrivateEndpoint"]
    assert set(isolated["Action"]) == {
        "sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:ChangeMessageVisibility"
    }
    assert isolated["Condition"]["StringNotEquals"]["aws:sourceVpce"] == {
        "Ref": "SqsEndpoint"
    }


def test_worker_has_no_arbitrary_code_execution_or_production_queue():
    source = (
        Path(__file__).resolve().parents[1] / "agent" /
        "NotarAI.VirtualEmployee.Probe" / "SqsDiagnosticPoller.cs"
    ).read_text(encoding="utf-8")
    assert "sqs.eu-central-1.amazonaws.com" in source
    assert "notarai-ve-{tenant}-jobs.fifo" in source
    assert "MaxNumberOfMessages = 1" in source
    assert "JobAdmission.Admit" in source
    assert "LocalInboxProcessor.WriteOutcome" in source
    assert "DeleteMessageAsync" in source
    assert source.index("LocalInboxProcessor.WriteOutcome") < source.index("DeleteMessageAsync")
    assert "SendMessageAsync" not in source
