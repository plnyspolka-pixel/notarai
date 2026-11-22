"""SEC-08 static contract for synthetic, dedicated-VPC Resolver DNS firewall.

This cannot verify live DNS, VPC resolver, bypasses, or operator rights.
Input is parsed CloudFormation read from an independently reviewed revision.
"""
from __future__ import annotations

from collections.abc import Mapping


class DnsPolicyRejected(ValueError):
    """Never echo source expressions or tenant data."""


EXPECTED_HOSTS = frozenset({
    "kms.${AWS::Region}.amazonaws.com",
    "sqs.${AWS::Region}.amazonaws.com",
    "api.ecr.${AWS::Region}.amazonaws.com",
    "${AWS::AccountId}.dkr.ecr.${AWS::Region}.amazonaws.com",
    "ecs.${AWS::Region}.amazonaws.com",
    "ecs-agent.${AWS::Region}.amazonaws.com",
    "ecs-telemetry.${AWS::Region}.amazonaws.com",
    "sts.${AWS::Region}.amazonaws.com",
    "logs.${AWS::Region}.amazonaws.com",
    "s3.${AWS::Region}.amazonaws.com",
    "${EncryptedBucketName}.s3.${AWS::Region}.amazonaws.com",
    "dynamodb.${AWS::Region}.amazonaws.com",
})


def _require(ok: bool) -> None:
    if not ok:
        raise DnsPolicyRejected("unapproved DNS firewall configuration")


def _resource(resources: Mapping, name: str, kind: str) -> Mapping:
    resource = resources.get(name)
    _require(isinstance(resource, dict) and resource.get("Type") == kind)
    props = resource.get("Properties")
    _require(isinstance(props, dict))
    return props


def validate_dns_firewall_template(document: Mapping) -> None:
    """Fail closed on changed allowlists, rule precedence or VPC association."""
    _require(isinstance(document, dict))
    params = document.get("Parameters")
    _require(isinstance(params, dict) and
             params.get("DedicatedVpcAcknowledgement", {}).get("AllowedValues") ==
             ["isolated-synthetic-vpc-only"])
    resources = document.get("Resources")
    _require(isinstance(resources, dict) and set(resources) == {
        "ApprovedPrivateEndpoints", "DenyAllOtherDomains", "StrictDnsRuleGroup",
        "DedicatedPilotVpcAssociation", "FailClosedDnsResolver",
    })
    kind = "AWS::Route53Resolver::"
    allowed = _resource(resources, "ApprovedPrivateEndpoints", kind+"FirewallDomainList")
    names = allowed.get("Domains")
    _require(isinstance(names, list) and len(names) == len(EXPECTED_HOSTS) and
             all(isinstance(x, dict) and set(x) == {"Sub"} and
                 isinstance(x["Sub"], str) for x in names))
    _require({x["Sub"] for x in names} == EXPECTED_HOSTS)
    denied = _resource(resources, "DenyAllOtherDomains", kind+"FirewallDomainList")
    _require(denied.get("Domains") == ["*"])
    rules = _resource(resources, "StrictDnsRuleGroup", kind+"FirewallRuleGroup")
    firewall_rules = rules.get("FirewallRules")
    _require(isinstance(firewall_rules, list) and len(firewall_rules) == 3)
    approved = {"Ref": "ApprovedPrivateEndpoints"}
    _require(firewall_rules[0] == {
        "Action": "ALLOW", "FirewallDomainListId": approved, "Priority": 100,
        "FirewallDomainRedirectionAction": "INSPECT_REDIRECTION_DOMAIN",
        "Qtype": "A",
    })
    _require(firewall_rules[1] == {
        "Action": "ALLOW", "FirewallDomainListId": approved, "Priority": 110,
        "FirewallDomainRedirectionAction": "INSPECT_REDIRECTION_DOMAIN",
        "Qtype": "AAAA",
    })
    _require(firewall_rules[2] == {
        "Action": "BLOCK", "BlockResponse": "NXDOMAIN",
        "FirewallDomainListId": {"Ref": "DenyAllOtherDomains"},
        "FirewallDomainRedirectionAction": "INSPECT_REDIRECTION_DOMAIN",
        "Priority": 200,
    })
    association = _resource(
        resources, "DedicatedPilotVpcAssociation", kind+"FirewallRuleGroupAssociation")
    _require(association.get("MutationProtection") == "ENABLED" and
             association.get("Priority") == 101 and
             association.get("FirewallRuleGroupId") == {"Ref": "StrictDnsRuleGroup"} and
             association.get("VpcId") == {"Ref": "VpcId"})
    fail_closed = _resource(resources, "FailClosedDnsResolver", kind+"FirewallConfig")
    _require(fail_closed == {
        "ResourceId": {"Ref": "VpcId"}, "FirewallFailOpen": "DISABLED",
    })
    _require(resources["FailClosedDnsResolver"].get("DependsOn") ==
             "DedicatedPilotVpcAssociation")
