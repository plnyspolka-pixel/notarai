"""SEC-08 DNS deny-by-default configuration regression (offline only)."""
import copy

import pytest

from confidential.dns_firewall import (
    EXPECTED_HOSTS, DnsPolicyRejected, validate_dns_firewall_template,
)
from test_confidential_infra import template


def valid_fixture():
    return template("notarai-confidential-dns-egress.yaml")


def test_dedicated_dns_firewall_has_exact_service_allowlist_and_fail_closed():
    policy = valid_fixture()
    validate_dns_firewall_template(policy)
    allowed = policy["Resources"]["ApprovedPrivateEndpoints"]["Properties"]["Domains"]
    assert len(allowed) == len(EXPECTED_HOSTS)
    assert all(not entry["Sub"].startswith("*") for entry in allowed)
    assert policy["Resources"]["DenyAllOtherDomains"]["Properties"]["Domains"] == ["*"]
    assert policy["Resources"]["FailClosedDnsResolver"]["Properties"]["FirewallFailOpen"] == "DISABLED"
    assert policy["Parameters"]["DedicatedVpcAcknowledgement"]["AllowedValues"] == [
        "isolated-synthetic-vpc-only"
    ]


@pytest.mark.parametrize("mutation", [
    lambda p: p["Resources"]["ApprovedPrivateEndpoints"]["Properties"]["Domains"].append(
        {"Sub": "*.amazonaws.com"}),
    lambda p: p["Resources"]["ApprovedPrivateEndpoints"]["Properties"]["Domains"].pop(),
    lambda p: p["Resources"]["DenyAllOtherDomains"]["Properties"].update(Domains=[]),
    lambda p: p["Resources"]["DenyAllOtherDomains"]["Properties"].update(Domains=["*.evil.test"]),
    lambda p: p["Resources"]["StrictDnsRuleGroup"]["Properties"]["FirewallRules"][0].update(
        Priority=300),
    lambda p: p["Resources"]["StrictDnsRuleGroup"]["Properties"]["FirewallRules"][0].update(
        Qtype="ANY"),
    lambda p: p["Resources"]["StrictDnsRuleGroup"]["Properties"]["FirewallRules"][0].update(
        FirewallDomainRedirectionAction="TRUST_REDIRECTION_DOMAIN"),
    lambda p: p["Resources"]["StrictDnsRuleGroup"]["Properties"]["FirewallRules"][1].update(
        Action="ALERT"),
    lambda p: p["Resources"]["StrictDnsRuleGroup"]["Properties"]["FirewallRules"][2].update(
        Action="ALERT"),
    lambda p: p["Resources"]["FailClosedDnsResolver"]["Properties"].update(
        FirewallFailOpen="ENABLED"),
    lambda p: p["Resources"]["FailClosedDnsResolver"].pop("DependsOn"),
    lambda p: p["Resources"]["DedicatedPilotVpcAssociation"]["Properties"].update(
        MutationProtection="DISABLED"),
    lambda p: p["Resources"]["DedicatedPilotVpcAssociation"]["Properties"].update(
        VpcId={"Ref": "OtherVpc"}),
    lambda p: p["Parameters"]["DedicatedVpcAcknowledgement"].update(
        AllowedValues=["shared-production-vpc"]),
    lambda p: p["Resources"].update({"PublicResolverBypass": {
        "Type": "AWS::EC2::NatGateway", "Properties": {}}}),
])
def test_unapproved_dns_policy_mutation_is_denied(mutation):
    policy = copy.deepcopy(valid_fixture())
    mutation(policy)
    with pytest.raises(DnsPolicyRejected, match="unapproved DNS firewall"):
        validate_dns_firewall_template(policy)
