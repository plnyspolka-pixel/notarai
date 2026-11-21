"""Read-only security gate before a synthetic Nitro pilot uses a private SG.

Without --check this prints a no-op plan; with --check it verifies the
account identity, subnet, route table, SGs and AWS PrivateLink endpoints.
It never creates or mutates resources and never uses customer data.
"""
from __future__ import annotations

import argparse
import re

from confidential.private_egress import validate_private_egress


def verify(
    *, account: str, profile: str, vpc: str, subnet: str,
    route_table: str, guest_sg: str, endpoint_sg: str, s3_prefix: str,
    check: bool = False,
) -> bool:
    if not re.fullmatch(r"[0-9]{12}", account):
        raise ValueError("invalid AWS account")
    if not check:
        print("DRY RUN: would validate the private pilot network, no AWS calls.")
        return False

    import boto3
    session = boto3.Session(profile_name=profile, region_name="eu-central-1")
    if session.client("sts").get_caller_identity().get("Account") != account:
        raise RuntimeError("AWS account mismatch")
    ec2 = session.client("ec2")
    subnet_data = ec2.describe_subnets(SubnetIds=[subnet])
    route_data = ec2.describe_route_tables(RouteTableIds=[route_table])
    groups = ec2.describe_security_groups(GroupIds=[guest_sg, endpoint_sg])
    endpoints = ec2.describe_vpc_endpoints(
        Filters=[{"Name": "vpc-id", "Values": [vpc]}],
    )
    if endpoints.get("NextToken"):
        raise RuntimeError("incomplete PrivateLink endpoint inventory")
    validate_private_egress(
        vpc_id=vpc, subnet_id=subnet, private_route_table_id=route_table,
        guest_sg_id=guest_sg, endpoint_sg_id=endpoint_sg,
        s3_prefix_list_id=s3_prefix,
        subnet_response=subnet_data, route_response=route_data,
        group_response=groups, endpoints_response=endpoints,
    )
    print("PASS: private staging route table, guest SG and AWS endpoints validated.")
    print("NOT verified: DNS/GET side effects, ECS data-plane reachability or Nitro hardware.")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("account", "profile", "vpc", "subnet", "route-table",
                "guest-sg", "endpoint-sg", "s3-prefix"):
        parser.add_argument("--" + arg, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    verify(
        account=args.account, profile=args.profile, vpc=args.vpc,
        subnet=args.subnet, route_table=args.route_table,
        guest_sg=args.guest_sg, endpoint_sg=args.endpoint_sg,
        s3_prefix=args.s3_prefix, check=args.check,
    )


if __name__ == "__main__":
    main()
