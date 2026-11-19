"""Fail-closed EU residency and AWS network checks. Never deploys resources."""
from __future__ import annotations
import argparse
import json
import re

# EU-member AWS Regions, with UK and Switzerland explicitly excluded.
ALLOWED_REGIONS = frozenset({
    "eu-central-1", "eu-west-1", "eu-west-3", "eu-north-1",
    "eu-south-1", "eu-south-2",
})


class PreflightDenied(RuntimeError):
    pass


def verify_bedrock_profile(profile: dict, expected_id: str) -> dict:
    if not isinstance(expected_id, str) or not re.fullmatch(r"eu\.[a-z0-9.-]{5,120}", expected_id):
        raise PreflightDenied("Geographic EU profile required")
    if profile.get("status") != "ACTIVE" or profile.get("inferenceProfileId") != expected_id:
        raise PreflightDenied("Wrong or inactive inference profile")
    models = profile.get("models")
    if not isinstance(models, list) or not models:
        raise PreflightDenied("Missing model destinations")
    regions = set()
    for model in models:
        arn = model.get("modelArn") if isinstance(model, dict) else None
        elements = arn.split(":") if isinstance(arn, str) else []
        if len(elements) < 6 or elements[2] != "bedrock":
            raise PreflightDenied("Malformed model destination")
        region = elements[3]
        if region not in ALLOWED_REGIONS:
            raise PreflightDenied("Unapproved or non-EU destination: " + region)
        regions.add(region)
    return {"profile": expected_id, "eu_destinations": sorted(regions)}


def verify_subnets(subnets: list, expected_vpc: str) -> dict:
    if len(subnets) < 2 or len({s.get("AvailabilityZone") for s in subnets}) < 2:
        raise PreflightDenied("Require two AZs")
    for subnet in subnets:
        if (subnet.get("VpcId") != expected_vpc or subnet.get("MapPublicIpOnLaunch")
                or subnet.get("State") != "available"):
            raise PreflightDenied("Unexpected public, unavailable or cross-VPC subnet")
    return {"subnets": len(subnets), "zones": sorted({s["AvailabilityZone"] for s in subnets})}


def verify_route_tables(tables: list, subnet_ids: list[str]) -> dict:
    associated = set()
    for table in tables:
        for assoc in table.get("Associations", []):
            if assoc.get("SubnetId") in subnet_ids and assoc.get("AssociationState", {}).get("State") == "associated":
                associated.add(assoc["SubnetId"])
        for route in table.get("Routes", []):
            # Staging: local-only BEFORE S3 gateway endpoint is deployed.
            if route.get("GatewayId") != "local":
                raise PreflightDenied("Nonlocal route (NAT, TGW, IGW, peering or gateway)")
    if associated != set(subnet_ids):
        raise PreflightDenied("Subnets must have explicit private route table associations")
    return {"private_route_tables": len(tables), "associated_subnets": len(associated)}


def main() -> None:
    p = argparse.ArgumentParser(description="Read-only EU Private AI AWS preflight")
    p.add_argument("--expected-account", required=True)
    p.add_argument("--vpc-id", required=True)
    p.add_argument("--subnet-id", action="append", required=True)
    p.add_argument("--route-table-id", action="append", required=True)
    p.add_argument("--model-id", required=True)
    p.add_argument("--profile", help="Optional local AWS credentials profile")
    args = p.parse_args()
    if not re.fullmatch(r"[0-9]{12}", args.expected_account):
        raise PreflightDenied("Invalid expected account")
    import boto3
    sess = boto3.Session(profile_name=args.profile, region_name="eu-central-1")
    if sess.client("sts").get_caller_identity()["Account"] != args.expected_account:
        raise PreflightDenied("Unexpected AWS account")
    profile = sess.client("bedrock").get_inference_profile(
        inferenceProfileIdentifier=args.model_id)
    ec2 = sess.client("ec2")
    subnets = ec2.describe_subnets(SubnetIds=args.subnet_id)["Subnets"]
    tables = ec2.describe_route_tables(RouteTableIds=args.route_table_id)["RouteTables"]
    evidence = {"account_verified": True, "source_region": "eu-central-1",
                **verify_bedrock_profile(profile, args.model_id),
                **verify_subnets(subnets, args.vpc_id),
                **verify_route_tables(tables, args.subnet_id)}
    print(json.dumps(evidence, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
