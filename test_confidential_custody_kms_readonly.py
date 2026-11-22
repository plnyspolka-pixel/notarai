"""SEC-06: synthetic, read-only live KMS policy/grant inspection tests."""
import copy
import json

import pytest

from confidential.operator_boundary import BoundaryDenied, canonical_digest
from confidential.custody_ops import render_kms_policy_target
from scripts.verify_confidential_custody_kms import inspect, _read_policy, _list_all
from test_confidential_independent_custody_ops import state, CUSTODY, WORKLOAD


def approved_state(lifecycle="ACTIVE"):
    s = state()
    s["state"] = lifecycle
    s["key_policy_sha256"] = canonical_digest(
        render_kms_policy_target(s)["target_policy"])
    return s


class KMSFixture:
    def __init__(self, state, *, account=CUSTODY, grant_pages=None,
                 policy_pages=None, raw_policy=None, key_metadata=None):
        self.state = state
        self.account = account
        self.grant_pages = grant_pages
        self.policy_pages = policy_pages
        self.raw_policy = raw_policy
        self.key_metadata = key_metadata
        self.calls = []

    def __call__(self, *, profile_name, region_name):
        assert profile_name == "custodian-readonly"
        assert region_name == "eu-central-1"
        fixture = self

        class Session:
            def client(self, service):
                assert service in ("sts", "kms")
                return self

            def get_caller_identity(self):
                fixture.calls.append("sts:GetCallerIdentity")
                return {"Account": fixture.account}

            def describe_key(self, *, KeyId):
                fixture.calls.append("kms:DescribeKey")
                assert KeyId == fixture.state["decrypt_key_arn"]
                return {"KeyMetadata": (
                    fixture.key_metadata if fixture.key_metadata is not None
                    else {
                        "Arn": fixture.state["decrypt_key_arn"],
                        "AWSAccountId": CUSTODY,
                        "KeyManager": "CUSTOMER", "Origin": "AWS_KMS",
                        "KeySpec": "RSA_3072", "KeyUsage": "ENCRYPT_DECRYPT",
                        "KeyState": "Enabled", "Enabled": True,
                        "MultiRegion": False,
                    }
                )}

            def list_key_policies(self, **kwargs):
                fixture.calls.append("kms:ListKeyPolicies")
                assert kwargs["KeyId"] == fixture.state["decrypt_key_arn"]
                pages = fixture.policy_pages
                if pages is None:
                    return {"PolicyNames": ["default"], "Truncated": False}
                idx = 1 if kwargs.get("Marker") == "next" else 0
                return pages[idx]

            def get_key_policy(self, *, KeyId, PolicyName):
                fixture.calls.append("kms:GetKeyPolicy")
                assert KeyId == fixture.state["decrypt_key_arn"]
                assert PolicyName == "default"
                body = (fixture.raw_policy if fixture.raw_policy is not None
                        else json.dumps(
                            render_kms_policy_target(fixture.state)["target_policy"]))
                return {"Policy": body}

            def list_grants(self, **kwargs):
                fixture.calls.append("kms:ListGrants")
                assert kwargs["KeyId"] == fixture.state["decrypt_key_arn"]
                pages = fixture.grant_pages
                if pages is None:
                    return {"Grants": [], "Truncated": False}
                idx = 1 if kwargs.get("Marker") == "next" else 0
                return pages[idx]

        return Session()


def test_k2_k4_kms_snapshot_readonly_reports_blocked_and_never_mutates():
    s = approved_state()
    f = KMSFixture(s)
    report = inspect(state=s, custody_profile="custodian-readonly",
                     check=True, session_factory=f)
    assert report["kms_policy_snapshot_checked"]
    assert report["kms_grants_fully_enumerated"]
    assert report["kms_grant_count"] == 0
    assert report["status"] == "BLOCKED"
    assert report["effective_revocation_verified"] is False
    assert report["independent_custody_verified"] is False
    assert report["kms_decrypt_performed"] is False
    assert report["kms_policy_write_performed"] is False
    assert set(f.calls) == {
        "sts:GetCallerIdentity", "kms:DescribeKey",
        "kms:ListKeyPolicies", "kms:GetKeyPolicy", "kms:ListGrants",
    }


def test_k2_kms_audit_has_zero_aws_calls_without_explicit_check():
    s = approved_state()
    f = KMSFixture(s)
    report = inspect(state=s, custody_profile="custodian-readonly",
                     session_factory=f)
    assert report["aws_calls"] == 0
    assert report["status"] == "BLOCKED"
    assert f.calls == []


@pytest.mark.parametrize("lifecycle", ["FROZEN", "REVOKED", "LOST"])
def test_k4_kms_frozen_lost_revoked_require_denied_policy(lifecycle):
    s = approved_state(lifecycle)
    f = KMSFixture(s)
    report = inspect(state=s, custody_profile="custodian-readonly",
                     check=True, session_factory=f)
    assert report["state"] == lifecycle
    assert not report["effective_revocation_verified"]
    assert not report["kms_decrypt_performed"]
    f.raw_policy = json.dumps(
        render_kms_policy_target(approved_state())["target_policy"])
    with pytest.raises(BoundaryDenied):
        inspect(state=s, custody_profile="custodian-readonly",
                check=True, session_factory=f)


def test_k2_paginated_grant_hidden_on_second_page_is_denied():
    s = approved_state()
    f = KMSFixture(s, grant_pages=[
        {"Grants": [], "Truncated": True, "NextMarker": "next"},
        {"Grants": [{"GranteePrincipal": f"arn:aws:iam::{WORKLOAD}:root",
                     "Operations": ["Decrypt"]}], "Truncated": False},
    ])
    with pytest.raises(BoundaryDenied):
        inspect(state=s, custody_profile="custodian-readonly",
                check=True, session_factory=f)
    assert f.calls.count("kms:ListGrants") == 2


@pytest.mark.parametrize("invalid", [
    {"Grants": [], "Truncated": True},
    {"Grants": [], "Truncated": True, "NextMarker": ""},
    {"Grants": [], "Truncated": True, "NextMarker": "next"},
    {"Grants": [], "Truncated": "false"},
    {"Grants": [], "Truncated": None},
    {"Truncated": False},
])
def test_k2_incomplete_grant_enumeration_fails_closed(invalid):
    s = approved_state()
    pages = [invalid, invalid] if invalid.get("NextMarker") == "next" else [invalid]
    f = KMSFixture(s, grant_pages=pages)
    with pytest.raises(BoundaryDenied):
        inspect(state=s, custody_profile="custodian-readonly",
                check=True, session_factory=f)


@pytest.mark.parametrize("policies", [
    [{"PolicyNames": ["default", "AWS_RAM"], "Truncated": False}],
    [{"PolicyNames": [], "Truncated": False}],
    [{"PolicyNames": ["default"], "Truncated": True}],
    [{"PolicyNames": ["default"], "Truncated": "false"}],
])
def test_k2_additional_or_incomplete_key_policy_inventory_denied(policies):
    s = approved_state()
    f = KMSFixture(s, policy_pages=policies)
    with pytest.raises(BoundaryDenied):
        inspect(state=s, custody_profile="custodian-readonly",
                check=True, session_factory=f)


def test_k2_duplicate_json_key_policy_field_denied():
    s = approved_state()
    f = KMSFixture(s, raw_policy='{"Version":"2012-10-17",'
                                  '"Statement":[],"Statement":[]}')
    with pytest.raises(BoundaryDenied, match="duplicate JSON field"):
        inspect(state=s, custody_profile="custodian-readonly",
                check=True, session_factory=f)


def test_k2_wrong_custody_account_or_key_type_denied():
    s = approved_state()
    f = KMSFixture(s, account=WORKLOAD)
    with pytest.raises(BoundaryDenied):
        inspect(state=s, custody_profile="custodian-readonly",
                check=True, session_factory=f)
    f = KMSFixture(s, key_metadata={
        "Arn": s["decrypt_key_arn"], "AWSAccountId": CUSTODY,
        "KeyManager": "CUSTOMER", "Origin": "AWS_KMS",
        "KeySpec": "SYMMETRIC_DEFAULT", "KeyUsage": "ENCRYPT_DECRYPT",
        "KeyState": "Enabled", "Enabled": True, "MultiRegion": False,
    })
    with pytest.raises(BoundaryDenied):
        inspect(state=s, custody_profile="custodian-readonly",
                check=True, session_factory=f)


def test_k6_kms_cli_check_mode_cannot_return_release_success(monkeypatch, tmp_path):
    import scripts.verify_confidential_custody_kms as module
    path = tmp_path / "state.json"
    path.write_text(json.dumps(approved_state()))
    monkeypatch.setattr(module, "inspect", lambda **kwargs: {
        "status": "BLOCKED", "independent_custody_verified": False,
        "kms_policy_snapshot_checked": True,
    })
    assert module.main([
        "--state-file", str(path),
        "--custody-profile", "custodian-readonly",
        "--check",
    ]) == 3
    assert module.main([
        "--state-file", str(path),
        "--custody-profile", "custodian-readonly",
    ]) == 0
