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
CORE_CONDITION = "WithCoreInterfaces"
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
            if item.get("Condition") == CORE_CONDITION:
                core.add(full)
            else:
                optional.add(full)
                assert item["Condition"] == OPTIONAL[full]
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


def test_core_interface_endpoints_are_on_by_default_and_switch_as_one_set():
    t = template("notarai-confidential-shared-fabric.yaml")
    flag = t["Parameters"]["EnableCoreInterfaceEndpoints"]
    assert flag["Default"] == "true"
    assert flag["AllowedValues"] == ["true", "false"]
    assert t["Conditions"][CORE_CONDITION] == {
        "Equals": [{"Ref": "EnableCoreInterfaceEndpoints"}, "true"]}
    gated = {
        x["Properties"]["ServiceName"]["Sub"].split(
            "com.amazonaws.${AWS::Region}.")[-1]
        for x in t["Resources"].values()
        if x.get("Condition") == CORE_CONDITION
    }
    assert gated == REQUIRED
    # Gateways, VPC, subnet and security groups never depend on the switch.
    for name in ("SharedVpc", "SharedPrivateSubnet", "SharedRouteTable",
                 "SharedRuntimeSecurityGroup", "SharedEndpointSecurityGroup",
                 "S3Gateway", "DynamoDbGateway"):
        assert "Condition" not in t["Resources"][name]


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
        def __init__(self):
            super().__init__()
            self.definition["taskDefinition"]["containerDefinitions"][0]["image"] = (
                f"{ACCOUNT}.dkr.ecr.eu-central-1.amazonaws.com/"
                "notarai-confidential-shared@sha256:" + "f" * 64
            )

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


def test_shared_ecr_digest_is_identical_for_distinct_tenant_tasks():
    from scripts.render_confidential_taskdef import make_task
    shared_img = (
        f"{ACCOUNT}.dkr.ecr.eu-central-1.amazonaws.com/"
        "notarai-confidential-shared@sha256:" + "a" * 64
    )
    def make(tenant):
        return make_task(
            ACCOUNT, tenant, shared_img,
            f"arn:aws:kms:eu-central-1:{ACCOUNT}:key/12345678-abcd",
            f"notarai-ciphertext-{tenant}",
            f"https://sqs.eu-central-1.amazonaws.com/{ACCOUNT}/"
            f"notarai-confidential-{tenant}.fifo",
            shared_image=True,
        )
    one, two = make("pilot01"), make("pilot02")
    assert one["containerDefinitions"][0]["image"] == shared_img
    assert two["containerDefinitions"][0]["image"] == shared_img
    assert one["taskRoleArn"] != two["taskRoleArn"]
    assert one["family"] != two["family"]
    assert one["containerDefinitions"][0]["environment"] != (
        two["containerDefinitions"][0]["environment"]
    )
    with pytest.raises(ValueError):
        make_task(
            ACCOUNT, "pilot01", shared_img,
            f"arn:aws:kms:eu-central-1:{ACCOUNT}:key/12345678-abcd",
            "notarai-ciphertext-pilot01",
            f"https://sqs.eu-central-1.amazonaws.com/{ACCOUNT}/"
            "notarai-confidential-pilot01.fifo",
        )
    t = template("notarai-confidential-shared-ecr.yaml")
    repo = t["Resources"]["SharedBrowserImage"]
    assert repo["Properties"]["RepositoryName"] == "notarai-confidential-shared"
    assert repo["Properties"]["ImageTagMutability"] == "IMMUTABLE"


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


def _mock_aws_inventory():
    return {
        "account": ACCOUNT,
        "ids": {
            "VpcId": "vpc-0123456789abcdef0",
            "SubnetId": SUBNET,
            "RouteTableId": "rtb-0123456789abcdef0",
            "RuntimeGroupId": SG,
            "EndpointGroupId": "sg-11111111111111111",
            "S3Prefix": "pl-0123456789abcdef0",
            "DynamoDbPrefix": "pl-11111111111111111",
        },
    }


def _inventory():
    data = _mock_aws_inventory()
    ids = data["ids"]
    data.update({
        "vpcs": [{"VpcId": ids["VpcId"], "State": "available",
                  "IsDefault": False}],
        "subnets": [{"VpcId": ids["VpcId"], "SubnetId": SUBNET,
                     "MapPublicIpOnLaunch": False}],
        "route_tables": [{
            "VpcId": ids["VpcId"],
            "RouteTableId": ids["RouteTableId"],
            "Associations": [{"SubnetId": SUBNET}],
            "Routes": [
                {"DestinationCidrBlock": "10.253.0.0/16", "GatewayId": "local"},
                {"DestinationPrefixListId": ids["S3Prefix"],
                 "GatewayId": "vpce-0123456789abcdef0", "State": "active",
                 "Origin": "CreateRoute"},
                {"DestinationPrefixListId": ids["DynamoDbPrefix"],
                 "GatewayId": "vpce-11111111111111111", "State": "active",
                 "Origin": "CreateRoute"},
            ],
        }],
        "security_groups": [
            {"GroupId": SG, "VpcId": ids["VpcId"], "IpPermissions": [],
             "IpPermissionsEgress": [
                 {"IpProtocol": "tcp", "FromPort": 443, "ToPort": 443,
                  "UserIdGroupPairs": [{"GroupId": ids["EndpointGroupId"]}]},
                 {"IpProtocol": "tcp", "FromPort": 443, "ToPort": 443,
                  "PrefixListIds": [{"PrefixListId": ids["S3Prefix"]}]},
                 {"IpProtocol": "tcp", "FromPort": 443, "ToPort": 443,
                  "PrefixListIds": [{"PrefixListId": ids["DynamoDbPrefix"]}]},
             ]},
            {"GroupId": ids["EndpointGroupId"], "VpcId": ids["VpcId"],
             "IpPermissions": [
                 {"IpProtocol": "tcp", "FromPort": 443, "ToPort": 443,
                  "UserIdGroupPairs": [{"GroupId": SG}]}
             ]},
        ],
        "aws_prefix_lists": [
            {"PrefixListId": ids["S3Prefix"],
             "PrefixListName": "com.amazonaws.eu-central-1.s3",
             "OwnerId": "AWS"},
            {"PrefixListId": ids["DynamoDbPrefix"],
             "PrefixListName": "com.amazonaws.eu-central-1.dynamodb",
             "OwnerId": "AWS"},
        ],
        "endpoints": [
            {"VpcId": ids["VpcId"],
             "ServiceName": "com.amazonaws.eu-central-1." + service,
             "VpcEndpointType": "Interface", "State": "available",
             "PrivateDnsEnabled": True,
             "SubnetIds": [SUBNET],
             "Groups": [{"GroupId": ids["EndpointGroupId"]}]}
            for service in REQUIRED
        ],
    })
    return data


def test_live_metadata_validator_accepts_only_one_shared_private_fabric():
    from confidential.shared_fabric import validate_fabric
    actual = validate_fabric(**_inventory())
    assert actual["network"] == "shared"
    assert actual["tenant_specific_networks"] == 0
    assert actual["can_submit"] is False
    assert actual["interface_services"] == sorted(REQUIRED)


@pytest.mark.parametrize("mutate", [
    lambda d: d["vpcs"][0].update(IsDefault=True),
    lambda d: d["subnets"][0].update(MapPublicIpOnLaunch=True),
    lambda d: d["route_tables"][0]["Routes"].append(
        {"DestinationCidrBlock": "0.0.0.0/0", "NatGatewayId": "nat-untrusted"}
    ),
    lambda d: d["route_tables"][0]["Routes"].append(
        {"DestinationCidrBlock": "10.20.0.0/16", "TransitGatewayId": "tgw-untrusted"}
    ),
    # Gateway prefix-list routes must target an active vpce-, nothing else.
    lambda d: d["route_tables"][0]["Routes"][1].update(GatewayId="igw-0123456789abcdef0"),
    lambda d: d["route_tables"][0]["Routes"][1].update(State="blackhole"),
    lambda d: d["route_tables"][0]["Routes"][1].update(NatGatewayId="nat-untrusted"),
    lambda d: (d["route_tables"][0]["Routes"][1].pop("GatewayId"),
               d["route_tables"][0]["Routes"][1].update(
                   VpcEndpointId="vpce-0123456789abcdef0")),
    lambda d: d["security_groups"][0]["IpPermissions"].append(
        {"IpProtocol": "tcp", "FromPort": 443, "ToPort": 443}
    ),
    lambda d: d["security_groups"][0]["IpPermissionsEgress"].append(
        {"IpProtocol": "-1", "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}
    ),
    lambda d: d["security_groups"][0]["IpPermissionsEgress"][0][
        "UserIdGroupPairs"][0].update(GroupId="sg-99999999999999999"),
    lambda d: d["aws_prefix_lists"][0].update(OwnerId="untrusted"),
    lambda d: d["endpoints"].pop(),
    lambda d: d["endpoints"][0].update(PrivateDnsEnabled=False),
    lambda d: d["endpoints"][0].update(State="pending"),
])
def test_unapproved_public_routes_and_endpoint_drift_fail_closed(mutate):
    import copy
    from confidential.shared_fabric import validate_fabric, SharedFabricRejected
    data = copy.deepcopy(_inventory())
    mutate(data)
    with pytest.raises(SharedFabricRejected):
        validate_fabric(**data)


def test_no_aws_calls_until_explicit_shared_preflight_check():
    from scripts.verify_confidential_shared_fabric import verify

    def reject_session(**kwargs):
        raise AssertionError("unexpected AWS call")
    assert verify(profile="test", account=ACCOUNT,
                  session_factory=reject_session)["aws_calls"] == 0


def _merged_egress(data):
    """Real EC2 shape: one tcp/443 entry carrying all three destinations."""
    ids = data["ids"]
    runtime = next(g for g in data["security_groups"]
                   if g["GroupId"] == ids["RuntimeGroupId"])
    runtime["IpPermissionsEgress"] = [{
        "IpProtocol": "tcp", "FromPort": 443, "ToPort": 443,
        "UserIdGroupPairs": [{"GroupId": ids["EndpointGroupId"],
                              "UserId": data["account"]}],
        "IpRanges": [], "Ipv6Ranges": [],
        "PrefixListIds": [{"PrefixListId": ids["S3Prefix"]},
                          {"PrefixListId": ids["DynamoDbPrefix"]}],
    }]
    return runtime["IpPermissionsEgress"][0]


def test_runtime_egress_merged_by_ec2_into_one_entry_is_accepted():
    import copy
    from confidential.shared_fabric import validate_fabric
    data = copy.deepcopy(_inventory())
    _merged_egress(data)
    assert validate_fabric(**data)["network"] == "shared"


@pytest.mark.parametrize("mutate", [
    lambda e: e["IpRanges"].append({"CidrIp": "0.0.0.0/0"}),
    lambda e: e["Ipv6Ranges"].append({"CidrIpv6": "::/0"}),
    lambda e: e["PrefixListIds"].append({"PrefixListId": "pl-99999999"}),
    lambda e: e["PrefixListIds"].pop(),
    lambda e: e["PrefixListIds"].append(dict(e["PrefixListIds"][0])),
    lambda e: e["UserIdGroupPairs"].append({"GroupId": "sg-99999999999999999"}),
    lambda e: e["UserIdGroupPairs"][0].update(UserId="999999999999"),
    lambda e: e["UserIdGroupPairs"].clear(),
    lambda e: e.update(FromPort=0, ToPort=65535),
    lambda e: e.update(IpProtocol="-1"),
])
def test_merged_runtime_egress_drift_fails_closed(mutate):
    import copy
    from confidential.shared_fabric import validate_fabric, SharedFabricRejected
    data = copy.deepcopy(_inventory())
    mutate(_merged_egress(data))
    with pytest.raises(SharedFabricRejected):
        validate_fabric(**data)
