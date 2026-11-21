"""Shared confidential VPC topology: synthetic static/IAM/dispatcher tests.

One regional VPC per isolated platform, NOT one VPC/endpoints per tenant.
Each individual worker must retain its own IAM/KMS/SQS permissions and Nitro
attestation policy. Offline only, never creates AWS resources.
"""
from dataclasses import replace

import pytest
import yaml

from confidential.dispatch import DispatcherConfig, UnsafeDispatch, dispatch_once
from scripts.render_confidential_shared_capacity import SHARED, shared_capacity
from test_confidential_dispatch import (
    ECSFake, SQSFake, DynamoFake, config, FAMILY,
)
from test_confidential_infra import ROOT, CloudFormationLoader

ACCOUNT = "111122223333"
SUBNET = "subnet-0123456789abcdef0"
SG = "sg-0123456789abcdef0"
REQUIRED = {
    "kms", "sqs", "ecr.api", "ecr.dkr", "ecs",
    "ecs-agent", "ecs-telemetry",
}
OPTIONAL = {
    "sts": "WithSts", "logs": "WithLogs", "signer": "WithSigner",
}


def template(filename):
    return yaml.load((ROOT / filename).read_text("utf-8"),
                     Loader=CloudFormationLoader)


def test_shared_fabric_has_one_vpc_no_tenant_specific_endpoints_or_public_route():
    t = template("notarai-confidential-shared-fabric.yaml")
    resources = t["Resources"]
    assert sum(x["Type"] == "AWS::EC2::VPC" for x in resources.values()) == 1
    assert sum(x["Type"] == "AWS::EC2::Subnet" for x in resources.values()) == 1
    assert sum(x["Type"] == "AWS::EC2::RouteTable" for x in resources.values()) == 1
    assert not any(x["Type"] in {
        "AWS::EC2::InternetGateway", "AWS::EC2::NatGateway",
        "AWS::EC2::EIP", "AWS::EC2::VPCPeeringConnection",
        "AWS::EC2::TransitGateway", "AWS::EC2::Route",
        "AWS::EC2::Instance", "AWS::ECS::Service",
    } for x in resources.values())
    subnet = resources["SharedPrivateSubnet"]["Properties"]
    assert subnet["MapPublicIpOnLaunch"] is False
    assert all("TenantId" not in x for x in t.get("Parameters", {}))
    assert t["Parameters"]["EnableStsEndpoint"]["Default"] == "false"
    assert t["Parameters"]["EnableLogsEndpoint"]["Default"] == "false"
    assert t["Parameters"]["EnableSignerEndpoint"]["Default"] == "false"


def test_seven_shared_interface_endpoints_and_two_free_gateway_endpoints():
    t = template("notarai-confidential-shared-fabric.yaml")
    endpoints = [r for r in t["Resources"].values()
                 if r["Type"] == "AWS::EC2::VPCEndpoint"]
    interfaces = [x for x in endpoints
                  if x["Properties"]["VpcEndpointType"] == "Interface"]
    gateways = [x for x in endpoints
                if x["Properties"]["VpcEndpointType"] == "Gateway"]
    assert len(interfaces) == 10  # 7 core + 3 *optional*, not per client
    assert len(gateways) == 2
    core, optional = set(), set()
    for item in interfaces:
        service = item["Properties"]["ServiceName"]["Sub"].split(".")[-1]
        if service in {"api", "dkr", "ecs", "ecs-agent", "ecs-telemetry",
                       "kms", "sqs", "sts", "logs", "signer"}:
            # Preserve full ECR namespace for the two corresponding endpoints.
            full = item["Properties"]["ServiceName"]["Sub"].split(
                "com.amazonaws.${AWS::Region}."
            )[-1]
            if item.get("Condition"):
                optional.add(full)
                assert item["Condition"] == OPTIONAL[full]
            else:
                core.add(full)
        else:
            raise AssertionError("unrecognized interface endpoint")
        assert item["Properties"]["PrivateDnsEnabled"] is True
        assert len(item["Properties"]["SubnetIds"]) == 1
        assert len(item["Properties"]["SecurityGroupIds"]) == 1
    assert core == REQUIRED
    assert optional == set(OPTIONAL)
    assert {
        x["Properties"]["ServiceName"]["Sub"] for x in gateways
    } == {
        "com.amazonaws.${AWS::Region}.s3",
        "com.amazonaws.${AWS::Region}.dynamodb",
    }


def test_shared_runtime_sg_no_inbound_and_prefix_list_only_egress():
    t = template("notarai-confidential-shared-fabric.yaml")
    sg = t["Resources"]["SharedRuntimeSecurityGroup"]["Properties"]
    assert "SecurityGroupIngress" not in sg
    rules = sg["SecurityGroupEgress"]
    assert len(rules) == 3
    assert all(x["IpProtocol"] == "tcp" and
               x["FromPort"] == x["ToPort"] == 443 and
               not any(k in x for k in ("CidrIp", "CidrIpv6"))
               for x in rules)
    assert len([x for x in rules if "DestinationSecurityGroupId" in x]) == 1
    assert len([x for x in rules if "DestinationPrefixListId" in x]) == 2
    endpoint_ingress = t["Resources"]["SharedEndpointIngress"]["Properties"]
    assert "SourceSecurityGroupId" in endpoint_ingress
    assert not any(k in endpoint_ingress for k in ("CidrIp", "CidrIpv6"))
    assert not any("Principal" in str(x) for x in t["Resources"].values())


def test_one_managed_instance_pool_and_distinct_notarial_guest_roles():
    t = template("notarai-confidential-shared-capacity.yaml")
    assert sum(x["Type"] == "AWS::ECS::Cluster" for x in t["Resources"].values()) == 1
    assert t["Resources"]["SharedConfidentialCluster"]["Properties"]["ClusterName"] == SHARED
    assert not any("TenantId" in x for x in t.get("Parameters", {}))
    assert all(x["Type"] != "AWS::ECS::TaskDefinition"
               for x in t["Resources"].values())
    args = shared_capacity(account=ACCOUNT, subnets=[SUBNET], security_group=SG)
    assert args["name"] == args["cluster"] == SHARED
    m = args["managedInstancesProvider"]
    assert m["instanceLaunchTemplate"]["networkConfiguration"]["securityGroups"] == [SG]
    assert m["instanceLaunchTemplate"]["nitroEnclavesEnabled"] is True
    assert args["name"] != FAMILY
    assert "tenant" not in str(args).lower()
    with pytest.raises(ValueError):
        shared_capacity(account=ACCOUNT, subnets=[SUBNET, SUBNET], security_group=SG)


def test_per_tenant_queues_and_roles_stay_pinned_in_one_shared_cluster():
    c = replace(config(), cluster=SHARED, capacity_provider=SHARED,
                shared_pool=True)
    c.validate()
    assert c.task_definition_arn.endswith(FAMILY + ":12")
    assert c.queue_url.endswith(FAMILY + ".fifo")
    assert c.lease_table.endswith("pilot01")

    class SharedECS(ECSFake):
        def describe_capacity_providers(self, **kwargs):
            assert kwargs == {"capacityProviders": [SHARED]}
            return {"capacityProviders": [{
                "name": SHARED, "status": "ACTIVE",
                "managedInstancesProvider": {
                    "instanceLaunchTemplate": {
                        "nitroEnclavesEnabled": True,
                        "networkConfiguration": {
                            "subnets": [SUBNET], "securityGroups": [SG],
                        },
                    },
                },
            }]}

        def run_task(self, **kwargs):
            assert kwargs["cluster"] == SHARED
            assert kwargs["capacityProviderStrategy"][0]["capacityProvider"] == SHARED
            assert kwargs["taskDefinition"] == c.task_definition_arn
            assert kwargs["networkConfiguration"]["awsvpcConfiguration"] == {
                "subnets": [SUBNET], "securityGroups": [SG],
                "assignPublicIp": "DISABLED",
            }
            assert kwargs["enableExecuteCommand"] is False
            assert not kwargs.get("overrides")
            self.calls.append(kwargs)
            return {"tasks": [{
                "taskArn": "arn:aws:ecs:eu-central-1:111122223333:task/shared/task1",
                "trustedExecutionSummary": {
                    "isolationMode": "CONFIDENTIAL_SANDBOX",
                    "attestationPolicyStatus": "CONFIGURED",
                },
            }], "failures": []}

    ecs = SharedECS()
    result = dispatch_once(c, sqs=SQSFake(), ecs=ecs, dynamodb=DynamoFake(),
                           clock=lambda: 1000, token_factory=lambda: "a" * 32)
    assert result == "launched"
    assert len(ecs.calls) == 1
    wrong = replace(c, task_definition_arn=c.task_definition_arn.replace(
        "pilot01", "other"))
    with pytest.raises(UnsafeDispatch):
        wrong.validate()
    wrong = replace(c, queue_url=c.queue_url.replace("pilot01", "other"))
    with pytest.raises(UnsafeDispatch):
        wrong.validate()
    wrong = replace(c, cluster=FAMILY)
    with pytest.raises(UnsafeDispatch):
        wrong.validate()
    wrong = replace(c, shared_pool=False)
    with pytest.raises(UnsafeDispatch):
        wrong.validate()


def test_shared_dispatch_cloudformation_stays_deny_by_default():
    t = template("notarai-confidential-dispatch.yaml")
    assert t["Parameters"]["SharedCompute"]["Default"] == "false"
    assert t["Parameters"]["DispatchEnabled"]["Default"] == "false"
    env = t["Resources"]["DispatcherFunction"]["Properties"]["Environment"][
        "Variables"
    ]
    assert env["NOTARAI_SHARED_POOL"] == {"Ref": "SharedCompute"}
    rule = t["Resources"]["DispatcherRole"]["Properties"]["Policies"][0][
        "PolicyDocument"]["Statement"
    ]
    run_rule = next(x for x in rule if x["Sid"] == "StartOnlyPinnedTask")
    assert run_rule["Resource"] == {"Ref": "TaskDefinitionArn"}
    assert "ecs:cluster" in run_rule["Condition"]["ArnEquals"]
