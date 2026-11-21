"""Offline validation of proposed private-only Nitro guest network metadata.

AWS security groups alone are NOT proof that DNS, URL paths, metadata access,
proxy routes and host-layer traffic are safe. This checker validates a
dedicated VPC/private route + guest SG + AWS VPC endpoints for a pilot only.
It makes NO AWS calls; callers must provide independently fetched EC2 data.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence


class PrivateEgressRejected(ValueError):
    """No AWS details or user data in denial messages."""


_ENDPOINT_SERVICES = frozenset({
    "kms", "sqs", "ecr.api", "ecr.dkr",
    "ecs", "ecs-agent", "ecs-telemetry", "sts", "logs",
})
_REGION = "eu-central-1"
_ID = re.compile(r"^[0-9a-f]{8}$|^[0-9a-f]{17}$")


def _id(value: object, prefix: str) -> bool:
    return (
        isinstance(value, str) and value.startswith(prefix) and
        bool(_ID.fullmatch(value[len(prefix):]))
    )


def _require(ok: bool, reason: str) -> None:
    if not ok:
        raise PrivateEgressRejected(reason)


def _one(data: Mapping, field: str) -> dict:
    result = data.get(field)
    _require(isinstance(result, list) and len(result) == 1 and
             isinstance(result[0], dict), "missing or ambiguous EC2 network resource")
    return result[0]


def validate_private_egress(
    *, vpc_id: str, subnet_id: str, private_route_table_id: str,
    guest_sg_id: str, endpoint_sg_id: str, s3_prefix_list_id: str,
    subnet_response: Mapping, route_response: Mapping,
    group_response: Mapping, endpoints_response: Mapping,
) -> None:
    for value, prefix in (
        (vpc_id, "vpc-"), (subnet_id, "subnet-"),
        (private_route_table_id, "rtb-"), (guest_sg_id, "sg-"),
        (endpoint_sg_id, "sg-"), (s3_prefix_list_id, "pl-"),
    ):
        _require(_id(value, prefix), "unexpected pilot network identifier")
    subnet = _one(subnet_response, "Subnets")
    _require(subnet.get("SubnetId") == subnet_id and
             subnet.get("VpcId") == vpc_id and
             subnet.get("MapPublicIpOnLaunch") is False,
             "pilot subnet is not private")

    route = _one(route_response, "RouteTables")
    _require(route.get("RouteTableId") == private_route_table_id and
             route.get("VpcId") == vpc_id and
             any(a.get("SubnetId") == subnet_id for a in route.get("Associations", [])),
             "route table is not dedicated to selected subnet")
    # No 0/0 route, including NAT, Internet Gateway, Transit Gateway or IPv6.
    for item in route.get("Routes", []):
        _require(item.get("DestinationCidrBlock") != "0.0.0.0/0" and
                 item.get("DestinationIpv6CidrBlock") != "::/0",
                 "pilot subnet has unrestricted default egress")
    _require(
        any(item.get("DestinationPrefixListId") == s3_prefix_list_id and
            isinstance(item.get("VpcEndpointId"), str) and
            item["VpcEndpointId"].startswith("vpce-")
            for item in route.get("Routes", [])),
        "S3 gateway endpoint route unavailable",
    )

    groups = group_response.get("SecurityGroups")
    _require(isinstance(groups, list) and len(groups) == 2,
             "missing guest or endpoint SG")
    by_id = {x.get("GroupId"): x for x in groups if isinstance(x, dict)}
    _require(set(by_id) == {guest_sg_id, endpoint_sg_id},
             "unapproved security groups")
    guest, endpoint = by_id[guest_sg_id], by_id[endpoint_sg_id]
    _require(guest.get("VpcId") == vpc_id and endpoint.get("VpcId") == vpc_id,
             "cross-VPC security group")
    _require(not guest.get("IpPermissions"), "guest security group permits inbound")
    egress = guest.get("IpPermissionsEgress")
    _require(isinstance(egress, list) and len(egress) == 2,
             "guest outbound must have exactly two PrivateLink/S3 rules")
    seen = set()
    for rule in egress:
        _require(rule.get("IpProtocol") == "tcp" and
                 rule.get("FromPort") == 443 and rule.get("ToPort") == 443,
                 "guest egress not restricted to HTTPS")
        _require(not rule.get("IpRanges") and not rule.get("Ipv6Ranges"),
                 "guest has public CIDR egress")
        pairs = rule.get("UserIdGroupPairs") or []
        prefixes = rule.get("PrefixListIds") or []
        _require(len(pairs) + len(prefixes) == 1,
                 "unexpected egress destination")
        if pairs:
            _require(pairs[0].get("GroupId") == endpoint_sg_id,
                     "guest egress points to external security group")
            seen.add("interface")
        if prefixes:
            _require(prefixes[0].get("PrefixListId") == s3_prefix_list_id,
                     "guest S3 prefix list mismatch")
            seen.add("s3")
    _require(seen == {"interface", "s3"},
             "missing or duplicated private egress rule")
    ingress = endpoint.get("IpPermissions") or []
    _require(len(ingress) == 1 and
             ingress[0].get("IpProtocol") == "tcp" and
             ingress[0].get("FromPort") == 443 and
             ingress[0].get("ToPort") == 443 and
             not ingress[0].get("IpRanges") and
             not ingress[0].get("Ipv6Ranges") and
             {x.get("GroupId") for x in
              ingress[0].get("UserIdGroupPairs", [])} == {guest_sg_id},
             "PrivateLink endpoints accept unapproved clients")

    endpoints = endpoints_response.get("VpcEndpoints")
    _require(isinstance(endpoints, list), "missing endpoint inventory")
    seen_services = set()
    for item in endpoints:
        if not isinstance(item, dict) or item.get("VpcId") != vpc_id:
            continue
        name = item.get("ServiceName", "")
        prefix = "com.amazonaws." + _REGION + "."
        if not name.startswith(prefix):
            continue
        service = name[len(prefix):]
        if service not in _ENDPOINT_SERVICES:
            continue
        _require(service not in seen_services, "duplicate private endpoints")
        _require(item.get("VpcEndpointType") == "Interface" and
                 item.get("State") == "available" and
                 item.get("PrivateDnsEnabled") is True and
                 subnet_id in (item.get("SubnetIds") or []) and
                 endpoint_sg_id in {
                     x.get("GroupId") for x in (item.get("Groups") or [])
                 },
                 "private service endpoint misconfigured")
        seen_services.add(service)
    _require(seen_services == _ENDPOINT_SERVICES,
             "missing required private AWS service endpoint")
