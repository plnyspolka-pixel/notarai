"""SEC-07 AWS organization metadata structural checks, no credentials."""
import json
import sys

import pytest

from confidential.nitro_organization_guard import (
    OrgBoundaryRejected, audit_organization_separation,
)
from scripts import check_nitro_org_separation as cli


class FakeError(Exception):
    def __init__(self, code):
        super().__init__("synthetic AWS Organizations test")
        self.response = {"Error": {"Code": code}}


def session_factory(*, operator_org="o-abcdefghijkl",
                    custody_org="o-qrstuvwxyzab",
                    missing_org=None, unexpected_error=None,
                    account_override=None):
    calls = []

    class FakeSTS:
        def __init__(self, account):
            self.account = account

        def get_caller_identity(self):
            calls.append("sts:GetCallerIdentity")
            return {"Account": self.account}

    class FakeOrganizations:
        def __init__(self, org, side):
            self.org = org
            self.side = side

        def describe_organization(self):
            calls.append("organizations:DescribeOrganization")
            if unexpected_error and self.side == unexpected_error:
                raise FakeError("AccessDeniedException")
            if missing_org == self.side:
                raise FakeError("AWSOrganizationsNotInUseException")
            return {"Organization": {"Id": self.org}}

    class Session:
        def __init__(self, profile_name, region_name):
            assert region_name == "eu-central-1"
            assert profile_name in ("operator-ro", "custody-ro")
            self.side = "operator" if profile_name == "operator-ro" else "custody"

        def client(self, name):
            if name == "sts":
                a = (
                    "111122223333" if self.side == "operator" else
                    "444455556666"
                )
                return FakeSTS(account_override or a)
            if name == "organizations":
                return FakeOrganizations(
                    operator_org if self.side == "operator" else custody_org,
                    self.side,
                )
            raise AssertionError("unexpected AWS client: " + name)

    return Session, calls


def audit(factory):
    return audit_organization_separation(
        operator_profile="operator-ro",
        custody_profile="custody-ro",
        workload_account="111122223333",
        custody_account="444455556666",
        session_factory=factory,
    )


def test_distinct_orgs_only_establish_partial_not_operator_independence():
    factory, calls = session_factory()
    result = audit(factory)
    assert result["distinct_organizations_observed"] is True
    assert result["shared_aws_organization_detected"] is False
    assert result["workload_org_sha256"] != result["custody_org_sha256"]
    assert result["administrative_independence_proven"] is False
    assert result["zero_operator_access_proven"] is False
    assert result["hardware_attestation_verified"] is False
    assert "organizations:DescribeOrganization" in calls
    assert set(calls) == {
        "sts:GetCallerIdentity", "organizations:DescribeOrganization",
    }


def test_two_accounts_in_same_organization_are_denied():
    factory, _ = session_factory(
        operator_org="o-abcdefghijkl", custody_org="o-abcdefghijkl",
    )
    with pytest.raises(OrgBoundaryRejected, match="share AWS Organizations"):
        audit(factory)


@pytest.mark.parametrize("side", ["operator", "custody"])
def test_standalone_account_can_be_observed_but_not_independence_proven(side):
    factory, _ = session_factory(missing_org=side)
    result = audit(factory)
    assert result["hardware_attestation_verified"] is False
    assert result[f"{'workload' if side == 'operator' else 'custody'}_is_standalone"] is True


@pytest.mark.parametrize("side", ["operator", "custody"])
def test_org_access_denied_is_not_mistaken_for_standalone(side):
    factory, _ = session_factory(unexpected_error=side)
    with pytest.raises(OrgBoundaryRejected):
        audit(factory)


def test_account_sts_mismatch_rejected_before_organizations():
    factory, calls = session_factory(account_override="999999999999")
    with pytest.raises(OrgBoundaryRejected):
        audit(factory)
    assert "organizations:DescribeOrganization" not in calls


def test_same_aws_session_profile_rejected():
    factory, _ = session_factory()
    with pytest.raises(OrgBoundaryRejected):
        audit_organization_separation(
            operator_profile="operator-ro",
            custody_profile="operator-ro",
            workload_account="111122223333",
            custody_account="444455556666",
            session_factory=factory,
        )


def test_offline_command_is_blocked_without_aws_credentials(
    monkeypatch, capsys,
):
    monkeypatch.setattr(sys, "argv", ["check_nitro_org_separation.py", "--check"])
    assert cli.main() == 2
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "BLOCKED"
    assert report["zero_operator_access_proven"] is False
    assert report["hardware_attestation_verified"] is False
