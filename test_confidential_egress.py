"""Static and synthetic tests for private-only Confidential Browser pilot egress."""
import copy

import pytest
import yaml

from confidential.private_egress import (
    PrivateEgressRejected,
    validate_private_egress,
)
from scripts.verify_confidential_private_network import verify
from test_confidential_infra import CloudFormationLoader, ROOT


VPC = "vpc-0123456789abcdef0"
SUBNET = "subnet-0123456789abcdef0"
ROUTE = "rtb-0123456789abcdef0"
GUEST = "sg-0123456789abcdef0"
ENDPOINT = "sg-11111111111111111"
S3 = "pl-0123456789abcdef0"
AWS = (
    "kms", "sqs", "ecr.api", "ecr.dkr", "ecs", "ecs-agent",
    "ecs-telemetry", "sts", "logs",
)


def synthetic():
    subnet = {"Subnets": [{
        "VpcId": VPC, "SubnetId": SUBNET, "MapPublicIpOnLaunch": False,
    }]}
    routes = {"RouteTables": [{
        "VpcId": VPC, "RouteTableId": ROUTE,
        "Associations": [{"SubnetId": SUBNET}],
        "Routes": [
            {"DestinationCidrBlock": "10.0.0.0/16", "GatewayId": "local"},
            {"DestinationPrefixListId": S3,
             "VpcEndpointId": "vpce-0123456789abcdef0"},
        ],
    }]}
    groups = {"SecurityGroups": [
        {
            "GroupId": GUEST, "VpcId": VPC, "IpPermissions": [],
            "IpPermissionsEgress": [
                {"IpProtocol": "tcp", "FromPort": 443, "ToPort": 443,
                 "UserIdGroupPairs": [{"GroupId": ENDPOINT}],
                 "PrefixListIds": [], "IpRanges": [], "Ipv6Ranges": []},
                {"IpProtocol": "tcp", "FromPort": 443, "ToPort": 443,
                 "PrefixListIds": [{"PrefixListId": S3}],
                 "UserIdGroupPairs": [], "IpRanges": [], "Ipv6Ranges": []},
            ],
        },
        {
            "GroupId": ENDPOINT, "VpcId": VPC,
            "IpPermissions": [{
                "IpProtocol": "tcp", "FromPort": 443, "ToPort": 443,
                "UserIdGroupPairs": [{"GroupId": GUEST}],
                "IpRanges": [], "Ipv6Ranges": [],
            }],
        },
    ]}
    endpoints = {"VpcEndpoints": [
        {
            "VpcId": VPC, "ServiceName": "com.amazonaws.eu-central-1." + name,
            "VpcEndpointType": "Interface", "State": "available",
            "PrivateDnsEnabled": True, "SubnetIds": [SUBNET],
            "Groups": [{"GroupId": ENDPOINT}],
        }
        for name in AWS
    ]}
    return subnet, routes, groups, endpoints


def check(parts):
    subnet, route, groups, endpoints = parts
    validate_private_egress(
        vpc_id=VPC, subnet_id=SUBNET, private_route_table_id=ROUTE,
        guest_sg_id=GUEST, endpoint_sg_id=ENDPOINT,
        s3_prefix_list_id=S3,
        subnet_response=subnet, route_response=route,
        group_response=groups, endpoints_response=endpoints,
    )


def test_known_private_endpoint_only_pilot_network_passes():
    check(synthetic())


@pytest.mark.parametrize("mutate", [
    lambda a: a[0]["Subnets"][0].update(MapPublicIpOnLaunch=True),
    lambda a: a[0]["Subnets"][0].update(VpcId="vpc-aaaaaaaaaaaaaaaaa"),
    lambda a: a[1]["RouteTables"][0]["Routes"].append(
        {"DestinationCidrBlock": "0.0.0.0/0", "NatGatewayId": "nat-12345678"}
    ),
    lambda a: a[1]["RouteTables"][0]["Routes"].append(
        {"DestinationIpv6CidrBlock": "::/0", "GatewayId": "igw-12345678"}
    ),
    lambda a: a[1]["RouteTables"][0]["Routes"].pop(),
    lambda a: a[2]["SecurityGroups"][0]["IpPermissions"].append(
        {"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22}
    ),
    lambda a: a[2]["SecurityGroups"][0]["IpPermissionsEgress"].append(
        {"IpProtocol": "-1", "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}
    ),
    lambda a: a[2]["SecurityGroups"][0]["IpPermissionsEgress"][0][
        "UserIdGroupPairs"][0].update(GroupId="sg-99999999999999999"),
    lambda a: a[2]["SecurityGroups"][1]["IpPermissions"][0][
        "UserIdGroupPairs"][0].update(GroupId="sg-99999999999999999"),
    lambda a: a[3]["VpcEndpoints"].pop(),
    lambda a: a[3]["VpcEndpoints"][0].update(State="pending"),
    lambda a: a[3]["VpcEndpoints"][0].update(PrivateDnsEnabled=False),
    lambda a: a[3]["VpcEndpoints"][0].update(SubnetIds=[]),
])
def test_unsafe_network_configuration_is_rejected(mutate):
    data = copy.deepcopy(synthetic())
    mutate(data)
    with pytest.raises(PrivateEgressRejected):
        check(data)


def test_staging_cloudformation_never_allows_public_guest_egress():
    template = yaml.load(
        (ROOT / "notarai-confidential-private-egress.yaml").read_text("utf-8"),
        Loader=CloudFormationLoader,
    )
    resources = template["Resources"]
    assert "S3GatewayEndpoint" in resources
    sg = resources["GuestPrivateSecurityGroup"]["Properties"]
    assert "SecurityGroupIngress" not in sg
    assert len(sg["SecurityGroupEgress"]) == 2
    assert all(rule["FromPort"] == 443 and rule["ToPort"] == 443
               and "CidrIp" not in rule and "CidrIpv6" not in rule
               for rule in sg["SecurityGroupEgress"])
    services = {
        r["Properties"]["ServiceName"]["Sub"]
        for r in resources.values()
        if r["Type"] == "AWS::EC2::VPCEndpoint" and
        r["Properties"].get("VpcEndpointType") == "Interface"
    }
    assert services == {"com.amazonaws.${AWS::Region}." + x for x in AWS}
    assert all(r["Properties"]["PrivateDnsEnabled"] is True
               for r in resources.values() if
               r["Type"] == "AWS::EC2::VPCEndpoint" and
               r["Properties"].get("VpcEndpointType") == "Interface")
    assert all(r["Type"] not in (
        "AWS::ECS::Service", "AWS::IAM::Policy",
        "AWS::EC2::NatGateway", "AWS::EC2::InternetGateway"
    ) for r in resources.values())


def test_network_operator_cli_never_calls_aws_without_check(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "boto3", None)
    assert verify(
        account="111122223333", profile="pilot", vpc=VPC,
        subnet=SUBNET, route_table=ROUTE, guest_sg=GUEST,
        endpoint_sg=ENDPOINT, s3_prefix=S3, check=False
    ) is False
