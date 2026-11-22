"""SEC-06: verify ALL historical KMS keys, not just current key."""
import copy
import json

import pytest

from confidential.custody_ops import render_kms_policy_target
from confidential.operator_boundary import BoundaryDenied
from scripts.audit_confidential_custody_all_keys import audit_all_generations
from test_confidential_custody_history import make_history
from test_confidential_independent_custody_ops import CUSTODY, WORKLOAD, state

OLD = state("pilot01", 1)["decrypt_key_arn"]
NEW = state("pilot01", 2)["decrypt_key_arn"]


class AllGenerationKMS:
    def __init__(self, *, owner=CUSTODY, grant_on=None, active_old=False,
                 missing_key=None, wrong_spec=None, incomplete_grants=None):
        self.owner = owner
        self.grant_on = grant_on
        self.active_old = active_old
        self.missing_key = missing_key
        self.wrong_spec = wrong_spec
        self.incomplete_grants = incomplete_grants
        self.calls = []
        self.snapshots = []

    def __call__(self, *, profile_name, region_name):
        assert profile_name == "independent-readonly-custodian"
        assert region_name == "eu-central-1"
        mock = self

        class Session:
            def client(self, name):
                assert name in ("sts", "kms")
                return self

            def get_caller_identity(self):
                mock.calls.append(("sts", None))
                return {"Account": mock.owner}

            def describe_key(self, *, KeyId):
                mock.calls.append(("describe_key", KeyId))
                if KeyId == mock.missing_key:
                    raise PermissionError("missing KMS key")
                assert KeyId in (OLD, NEW)
                return {"KeyMetadata": {
                    "Arn": KeyId,
                    "AWSAccountId": CUSTODY,
                    "KeyManager": "CUSTOMER", "Origin": "AWS_KMS",
                    "KeySpec": (
                        "SYMMETRIC_DEFAULT"
                        if KeyId == mock.wrong_spec else "RSA_3072"),
                    "KeyUsage": "ENCRYPT_DECRYPT", "MultiRegion": False,
                    "KeyState": "Enabled", "Enabled": True,
                }}

            def list_key_policies(self, **kwargs):
                arn = kwargs["KeyId"]
                mock.calls.append(("list_key_policies", arn))
                assert arn in (OLD, NEW)
                return {"PolicyNames": ["default"], "Truncated": False}

            def get_key_policy(self, *, KeyId, PolicyName):
                mock.calls.append(("get_key_policy", KeyId))
                assert PolicyName == "default"
                expected = state("pilot01", 1 if KeyId == OLD else 2)
                expected["state"] = "ACTIVE" if KeyId == OLD and mock.active_old else "FROZEN"
                # FROZEN/LOST have the same two-statement deny-only policy.
                return {"Policy": json.dumps(
                    render_kms_policy_target(expected)["target_policy"])}

            def list_grants(self, **kwargs):
                arn = kwargs["KeyId"]
                mock.calls.append(("list_grants", arn))
                if arn == mock.incomplete_grants:
                    return {"Grants": [], "Truncated": True}
                if arn == mock.grant_on:
                    if "Marker" not in kwargs:
                        return {
                            "Grants": [], "Truncated": True,
                            "NextMarker": "next",
                        }
                    return {
                        "Grants": [{
                            "GranteePrincipal":
                                f"arn:aws:iam::{WORKLOAD}:root",
                            "Operations": ["Decrypt"],
                        }],
                        "Truncated": False,
                    }
                return {"Grants": [], "Truncated": False}

        return Session()


def _audit(fixture, mock, check=True):
    return audit_all_generations(
        tenant=fixture["tenant"],
        event_items=fixture["event_items"],
        state_item=fixture["state_item"],
        trust_roots=fixture["trust_roots"],
        pinned_final_state_sha256=fixture["pinned_final_state_sha256"],
        custody_profile="independent-readonly-custodian",
        check=check, clock=fixture["clock"],
        session_factory=mock,
    )


def test_k5_k6_all_generation_kms_audit_reaches_every_physical_key():
    f = make_history()
    mock = AllGenerationKMS()
    report = _audit(f, mock)
    assert report["status"] == "BLOCKED_PENDING_EXTERNAL_CUSTODY_EVIDENCE"
    assert report["offline_chain_integrity_checked"]
    assert report["all_generations_read_only_snapshots_checked"]
    assert report["kms_key_snapshots_checked"] == 2
    assert report["retired_key_count"] == 1
    assert report["final_lifecycle_state"] == "LOST"
    assert [x["key_arn"] for x in report["kms_key_snapshots"]] == [OLD, NEW]
    assert [x["role"] for x in report["kms_key_snapshots"]] == [
        "retired", "current"]
    assert all(x["static_deny_only_snapshot_checked"]
               for x in report["kms_key_snapshots"])
    assert {v for name, v in mock.calls if name == "describe_key"} == {OLD, NEW}
    assert mock.calls.count(("sts", None)) == 2
    assert not report["historical_keys_effectively_denied_verified"]
    assert not report["live_negative_decrypt_for_every_generation"]
    assert not report["independent_custody_verified"]
    assert not report["kms_decrypt_performed"]
    assert not report["kms_write_performed"]


def test_k5_all_generation_audit_inert_without_explicit_check():
    f = make_history()
    mock = AllGenerationKMS()
    report = _audit(f, mock, check=False)
    assert report["status"] == "BLOCKED"
    assert report["aws_calls"] == 0
    assert report["expected_key_count"] == 2
    assert report["retired_key_count"] == 1
    assert not report["all_generations_read_only_snapshots_checked"]
    assert mock.calls == []


@pytest.mark.parametrize("grant_key", [OLD, NEW])
def test_k4_any_hidden_grant_in_old_or_new_key_denies_everything(grant_key):
    f = make_history()
    mock = AllGenerationKMS(grant_on=grant_key)
    with pytest.raises(BoundaryDenied):
        _audit(f, mock)
    assert ("list_grants", grant_key) in mock.calls
    assert mock.calls.count(("list_grants", grant_key)) == 2


def test_k4_old_key_with_active_decrypt_policy_denies_even_if_current_is_safe():
    f = make_history()
    mock = AllGenerationKMS(active_old=True)
    with pytest.raises(BoundaryDenied):
        _audit(f, mock)
    assert ("get_key_policy", OLD) in mock.calls
    assert ("describe_key", NEW) not in mock.calls


@pytest.mark.parametrize("missing_key", [OLD, NEW])
def test_k5_missing_physical_history_key_is_not_considered_revoked(missing_key):
    f = make_history()
    mock = AllGenerationKMS(missing_key=missing_key)
    with pytest.raises(BoundaryDenied):
        _audit(f, mock)
    assert ("describe_key", missing_key) in mock.calls


def test_k5_incomplete_pagination_on_retired_key_must_fail():
    f = make_history()
    mock = AllGenerationKMS(incomplete_grants=OLD)
    with pytest.raises(BoundaryDenied):
        _audit(f, mock)


def test_k1_custody_account_must_be_external_even_for_retired_keys():
    f = make_history()
    mock = AllGenerationKMS(owner=WORKLOAD)
    with pytest.raises(BoundaryDenied):
        _audit(f, mock)
    assert mock.calls == [("sts", None)]


def test_k2_wrong_old_kms_key_type_denied():
    f = make_history()
    mock = AllGenerationKMS(wrong_spec=OLD)
    with pytest.raises(BoundaryDenied):
        _audit(f, mock)
    assert ("describe_key", OLD) in mock.calls


@pytest.mark.parametrize("corrupt", [
    lambda f: f["event_items"].pop(1),
    lambda f: f.update(pinned_final_state_sha256="0" * 64),
    lambda f: f["trust_roots"].pop(2),
    lambda f: f["state_item"]["state_sha256"].update(S="f" * 64),
])
def test_k5_corrupt_historical_chain_rejected_before_any_live_aws(corrupt):
    f = make_history()
    corrupt(f)
    mock = AllGenerationKMS()
    with pytest.raises(BoundaryDenied):
        _audit(f, mock)
    assert mock.calls == []


def test_k6_all_key_read_only_audit_never_becomes_release_gate(monkeypatch, tmp_path):
    import scripts.audit_confidential_custody_all_keys as module
    f = make_history()
    export = tmp_path / "signed-events.json"
    roots = tmp_path / "trust-roots.json"
    export.write_text(json.dumps({
        "event_items": f["event_items"],
        "state_item": f["state_item"],
    }))
    manifest = {}
    for gen, (pem, pin) in f["trust_roots"].items():
        path = tmp_path / f"root-{gen}.pem"
        path.write_bytes(pem)
        manifest[str(gen)] = {"pem_file": str(path), "sha256": pin}
    roots.write_text(json.dumps(manifest))
    monkeypatch.setattr(
        module, "audit_all_generations",
        lambda **kwargs: {
            "status": "BLOCKED_PENDING_EXTERNAL_CUSTODY_EVIDENCE",
            "kms_key_snapshots_checked": 2,
            "aws_calls": "read-only",
            "independent_custody_verified": False,
        })
    assert module.main([
        "--tenant", "pilot01",
        "--history-file", str(export),
        "--trust-roots-file", str(roots),
        "--pinned-final-sha256", f["pinned_final_state_sha256"],
        "--custody-profile", "independent-readonly-custodian",
        "--check",
        "--output", str(tmp_path / "audit.json"),
    ]) == 3
