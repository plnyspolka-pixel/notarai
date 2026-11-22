"""Offline validation of regional shared NotarAI private endpoint fabric.

A shared VPC and security groups can serve many tenants. Network sharing
DOES NOT grant access to tenant S3/SQS/KMS: independent task IAM and KMS
attestation are mandatory. No AWS operations in this module.
"""
from __future__ import annotations

import re

_REGION = "eu-central-1"
_REQUIRED = frozenset({
    "kms", "sqs", "ecr.api", "ecr.dkr",
    "ecs", "ecs-agent", "ecs-telemetry",
})
_OPTIONAL = frozenset({"sts", "logs", "signer"})
_IDS = {
    "VpcId": "vpc-", "SubnetId": "subnet-",
    "RouteTableId": "rtb-", "RuntimeGroupId": "sg-",
    "EndpointGroupId": "sg-", "S3Prefix": "pl-", "DynamoDbPrefix": "pl-",
}
_IDENT = re.compile(r"^(?:[0-9a-f]{8}|[0-9a-f]{17})$")


class SharedFabricRejected(ValueError):
    """Sanitized error, never print raw VPC API responses."""


_FOREIGN_ROUTE_TARGETS = (
    "NatGatewayId", "TransitGatewayId", "VpcPeeringConnectionId",
    "InstanceId", "NetworkInterfaceId", "EgressOnlyInternetGatewayId",
    "LocalGatewayId", "CarrierGatewayId", "CoreNetworkArn",
)


def deny_if(ok: bool, message: str) -> None:
    if not ok:
        raise SharedFabricRejected(message)


def validate_fabric(
    *, account: str, ids: dict, vpcs: list, subnets: list,
    route_tables: list, security_groups: list, endpoints: list,
    aws_prefix_lists: list, optional_services: set | frozenset = frozenset(),
) -> dict:
    deny_if(isinstance(account, str) and bool(re.fullmatch(r"[0-9]{12}", account)),
            "unexpected AWS identity")
    deny_if(type(ids) is dict and set(ids) == set(_IDS),
            "shared network IDs incomplete")
    for key, prefix in _IDS.items():
        value = ids[key]
        deny_if(isinstance(value, str) and value.startswith(prefix) and
                bool(_IDENT.fullmatch(value[len(prefix):])),
                "invalid shared fabric resource ID")
    deny_if(type(optional_services) in (set, frozenset) and
            optional_services <= _OPTIONAL,
            "unexpected optional AWS network service")
    def only(items):
        deny_if(isinstance(items, list) and len(items) == 1 and
                isinstance(items[0], dict), "ambiguous shared network resource")
        return items[0]
    vpc = only(vpcs)
    deny_if(vpc.get("VpcId") == ids["VpcId"] and
            vpc.get("State") == "available" and
            vpc.get("IsDefault") is False,
            "shared VPC not isolated from default network")
    subnet = only(subnets)
    deny_if(subnet.get("VpcId") == ids["VpcId"] and
            subnet.get("SubnetId") == ids["SubnetId"] and
            subnet.get("MapPublicIpOnLaunch") is False,
            "shared compute subnet not private")
    routes = only(route_tables)
    deny_if(routes.get("VpcId") == ids["VpcId"] and
            routes.get("RouteTableId") == ids["RouteTableId"] and
            any(a.get("SubnetId") == ids["SubnetId"] for a in
                routes.get("Associations", [])),
            "shared route table not bound to compute subnet")
    # Strictly no NAT, IGW, TGW, VPN or peering path: allow only local and
    # the two AWS managed gateway prefix-list endpoint routes.
    seen_routes = set()
    for route in routes.get("Routes", []):
        prefix = route.get("DestinationPrefixListId")
        if prefix:
            # EC2 DescribeRouteTables reports a gateway endpoint route target
            # in GatewayId ("vpce-..."), not in VpcEndpointId (verified live
            # 22.11.2026). Any other target type on the route is rejected.
            target = route.get("GatewayId")
            deny_if(prefix in (ids["S3Prefix"], ids["DynamoDbPrefix"]) and
                    isinstance(target, str) and
                    bool(re.fullmatch(r"vpce-(?:[0-9a-f]{8}|[0-9a-f]{17})", target)) and
                    route.get("State") == "active" and
                    not any(route.get(k) for k in _FOREIGN_ROUTE_TARGETS),
                    "unapproved shared gateway route")
            seen_routes.add(prefix)
        else:
            deny_if(route.get("GatewayId") == "local" and
                    route.get("DestinationCidrBlock") not in ("0.0.0.0/0", None) and
                    route.get("DestinationIpv6CidrBlock") is None,
                    "shared subnet contains non-local route")
    deny_if(seen_routes == {ids["S3Prefix"], ids["DynamoDbPrefix"]},
            "shared S3 or DynamoDB gateway missing")

    deny_if(isinstance(aws_prefix_lists, list) and len(aws_prefix_lists) == 2,
            "incomplete AWS-managed prefix list verification")
    found = {(x.get("PrefixListId"), x.get("PrefixListName"), x.get("OwnerId"))
             for x in aws_prefix_lists if isinstance(x, dict)}
    deny_if(found == {
        (ids["S3Prefix"], f"com.amazonaws.{_REGION}.s3", "AWS"),
        (ids["DynamoDbPrefix"], f"com.amazonaws.{_REGION}.dynamodb", "AWS"),
    }, "prefix list is not an AWS-owned regional service")

    deny_if(isinstance(security_groups, list) and len(security_groups) == 2,
            "shared security group inventory incomplete")
    groups = {x.get("GroupId"): x for x in security_groups if isinstance(x, dict)}
    deny_if(set(groups) == {ids["RuntimeGroupId"], ids["EndpointGroupId"]},
            "unexpected shared security groups")
    runtime, endpoint_group = (
        groups[ids["RuntimeGroupId"]], groups[ids["EndpointGroupId"]]
    )
    deny_if(runtime.get("VpcId") == ids["VpcId"] and
            endpoint_group.get("VpcId") == ids["VpcId"] and
            not runtime.get("IpPermissions"),
            "untrusted shared security group inbound rules")
    # EC2 DescribeSecurityGroups merges rules that share protocol and ports
    # into ONE IpPermission entry carrying several destinations (verified
    # live 22.11.2026), so count destinations, not entries. Every entry must
    # be tcp/443 with no CIDR at all; the union of destinations must be
    # exactly the endpoint group plus the two AWS gateway prefix lists.
    out = runtime.get("IpPermissionsEgress")
    deny_if(isinstance(out, list) and 1 <= len(out) <= 3 and
            all(isinstance(x, dict) for x in out),
            "shared runtime security group outbound is not strictly bounded")
    targets = []
    for entry in out:
        deny_if(entry.get("IpProtocol") == "tcp" and
                entry.get("FromPort") == 443 and entry.get("ToPort") == 443 and
                not entry.get("IpRanges") and not entry.get("Ipv6Ranges"),
                "shared runtime permits public CIDR outbound")
        groups_out = entry.get("UserIdGroupPairs") or []
        prefixes_out = entry.get("PrefixListIds") or []
        deny_if(len(groups_out) + len(prefixes_out) >= 1,
                "unapproved shared destination rule")
        for pair in groups_out:
            deny_if(isinstance(pair, dict) and
                    pair.get("GroupId") == ids["EndpointGroupId"] and
                    pair.get("UserId") in (None, account) and
                    not pair.get("VpcPeeringConnectionId"),
                    "unapproved shared interface group")
            targets.append("interface")
        for item in prefixes_out:
            pl = item.get("PrefixListId") if isinstance(item, dict) else None
            deny_if(pl in {ids["S3Prefix"], ids["DynamoDbPrefix"]},
                    "unapproved shared gateway destination")
            targets.append(pl)
    deny_if(len(targets) == 3,
            "shared runtime security group outbound is not strictly bounded")
    targets = set(targets)
    deny_if(targets == {"interface", ids["S3Prefix"], ids["DynamoDbPrefix"]},
            "shared egress rules do not match expected endpoints")

    inbound = endpoint_group.get("IpPermissions") or []
    deny_if(len(inbound) == 1 and
            inbound[0].get("IpProtocol") == "tcp" and
            inbound[0].get("FromPort") == 443 and
            inbound[0].get("ToPort") == 443 and
            {x.get("GroupId") for x in
             (inbound[0].get("UserIdGroupPairs") or [])} ==
            {ids["RuntimeGroupId"]} and
            not inbound[0].get("IpRanges") and
            not inbound[0].get("Ipv6Ranges"),
            "shared AWS interface endpoints accept unapproved traffic")

    expected = _REQUIRED | optional_services
    seen = set()
    deny_if(isinstance(endpoints, list), "shared interface endpoint inventory unavailable")
    for item in endpoints:
        if not isinstance(item, dict) or item.get("VpcId") != ids["VpcId"]:
            continue
        name = item.get("ServiceName", "")
        stem = f"com.amazonaws.{_REGION}."
        if not name.startswith(stem):
            continue
        service = name[len(stem):]
        if service not in expected:
            continue
        deny_if(service not in seen and
                item.get("VpcEndpointType") == "Interface" and
                item.get("State") == "available" and
                item.get("PrivateDnsEnabled") is True and
                ids["SubnetId"] in (item.get("SubnetIds") or []) and
                ids["EndpointGroupId"] in {
                    x.get("GroupId") for x in item.get("Groups", [])
                },
                "unavailable or mismatched shared AWS endpoint")
        seen.add(service)
    deny_if(seen == expected, "required shared AWS service endpoint missing")
    return {
        "network": "shared",
        "region": _REGION,
        "interface_services": sorted(seen),
        "tenant_specific_networks": 0,
        "subnet_count": 1,
        "can_submit": False,
    }
