"""Read-only preflight for the ONE regional NotarAI confidential VPC.

Usage:
  python scripts/verify_confidential_shared_fabric.py --profile notarai-ops \
    --account 123456789012 --check

Without --check, performs NO AWS calls. Never creates, changes or removes
VPC endpoints, IAM or tenant data. Fails if stack, prefixes or SGs drift.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from confidential.shared_fabric import SharedFabricRejected, validate_fabric

_REGION = "eu-central-1"
_STACK = "notarai-confidential-shared-fabric"


def verify(*, profile: str, account: str, check: bool = False,
           session_factory=None) -> dict:
    if not isinstance(account, str) or not re.fullmatch("[0-9]{12}", account):
        raise ValueError("invalid explicit AWS account")
    if not check:
        print("DRY RUN: one regional network; no AWS call or charge.")
        return {"mode": "dry-run", "aws_calls": 0}
    if session_factory is None:
        import boto3
        session_factory = boto3.Session
    session = session_factory(profile_name=profile, region_name=_REGION)
    if session.client("sts").get_caller_identity().get("Account") != account:
        raise SharedFabricRejected("wrong AWS account for shared fabric")
    stacks = session.client("cloudformation").describe_stacks(
        StackName=_STACK,
    ).get("Stacks", [])
    if len(stacks) != 1 or stacks[0].get("StackStatus") not in {
        "CREATE_COMPLETE", "UPDATE_COMPLETE",
    }:
        raise SharedFabricRejected("shared fabric stack not ready")
    outputs = {
        x["OutputKey"]: x["OutputValue"] for x in stacks[0].get("Outputs", [])
    }
    params = {x["ParameterKey"]: x["ParameterValue"] for x in
              stacks[0].get("Parameters", [])}
    keys = {
        "VpcId": "SharedVpcId",
        "SubnetId": "SharedPrivateSubnetId",
        "RouteTableId": "SharedRouteTableId",
        "RuntimeGroupId": "SharedRuntimeSecurityGroupId",
        "EndpointGroupId": "SharedEndpointSecurityGroupId",
    }
    try:
        ids = {k: outputs[o] for k, o in keys.items()}
        ids["S3Prefix"] = params["S3PrefixListId"]
        ids["DynamoDbPrefix"] = params["DynamoDbPrefixListId"]
    except KeyError:
        raise SharedFabricRejected("shared stack outputs or parameters missing") from None
    optional = set()
    for flag, service in [
        ("EnableStsEndpoint", "sts"),
        ("EnableLogsEndpoint", "logs"),
        ("EnableSignerEndpoint", "signer"),
    ]:
        value = params.get(flag, "false")
        if value not in {"true", "false"}:
            raise SharedFabricRejected("unexpected optional endpoint setting")
        if value == "true":
            optional.add(service)
    ec2 = session.client("ec2")
    vpc = ec2.describe_vpcs(VpcIds=[ids["VpcId"]])
    subnet = ec2.describe_subnets(SubnetIds=[ids["SubnetId"]])
    routes = ec2.describe_route_tables(RouteTableIds=[ids["RouteTableId"]])
    groups = ec2.describe_security_groups(
        GroupIds=[ids["RuntimeGroupId"], ids["EndpointGroupId"]],
    )
    prefixes = ec2.describe_managed_prefix_lists(
        PrefixListIds=[ids["S3Prefix"], ids["DynamoDbPrefix"]],
    )
    endpoints = ec2.describe_vpc_endpoints(
        Filters=[{"Name": "vpc-id", "Values": [ids["VpcId"]]}],
    )
    if endpoints.get("NextToken") or prefixes.get("NextToken"):
        raise SharedFabricRejected("incomplete regional endpoint verification")
    result = validate_fabric(
        account=account,
        ids=ids,
        vpcs=vpc.get("Vpcs"),
        subnets=subnet.get("Subnets"),
        route_tables=routes.get("RouteTables"),
        security_groups=groups.get("SecurityGroups"),
        aws_prefix_lists=prefixes.get("PrefixLists"),
        endpoints=endpoints.get("VpcEndpoints"),
        optional_services=optional,
    )
    print("PASS: isolated tenant-neutral shared VPC, restrictive runtime SG, "
          "regional AWS endpoints; no public path.")
    print("NOT proven: actual host/ENI effective policy, DNS abuse, "
          "Nitro at-rest/in-use attestation, user or portal permission.")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--account", required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    verify(profile=args.profile, account=args.account, check=args.check)


if __name__ == "__main__":
    main()
