"""SEC-06 no-AWS synthetic acceptance and denial tests.

Do not interpret any assertion below as a live AWS/independent root audit.
"""
import base64
import copy
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from confidential.custody_ops import (
    _IDENTITY_FIELDS, _EVENT_SCHEMA, _SCHEMA, apply_signed_action,
    authorize_binding_preview, validate_governance_snapshot,
    validate_pilot_inventory, validate_state,
)
from confidential.operator_boundary import (
    BoundaryDenied, canonical_digest, inspect_operator_boundary,
)
from confidential.release_approval import public_key_fingerprint
from scripts.verify_confidential_custody_independence import inspect as audit_aws
from test_confidential_operator_boundary import fixture as old_fixture

WORKLOAD = "111122223333"
CUSTODY = "444455556666"
NOW = datetime(2026, 11, 22, 3, 0, tzinfo=timezone.utc)


def state(tenant="pilot01", number=1):
    name = number
    return {
        "schema": _SCHEMA,
        "tenant": tenant,
        "workload_account": WORKLOAD,
        "custody_account": CUSTODY,
        "decrypt_key_arn": (
            f"arn:aws:kms:eu-central-1:{CUSTODY}:key/"
            f"aaaaaaaa-0000-0000-0000-{name:012d}"),
        "signing_key_arn": (
            f"arn:aws:kms:eu-central-1:{CUSTODY}:key/"
            f"bbbbbbbb-0000-0000-0000-{name:012d}"),
        "pcr17": f"{name:x}" * 96,
        "image_sha256": f"{name:x}" * 64,
        "task_definition_arn": (
            f"arn:aws:ecs:eu-central-1:{WORKLOAD}:"
            f"task-definition/notarai-confidential-{tenant}:12"),
        "release_sha256": f"{name + 2:x}" * 64,
        "key_policy_sha256": f"{name + 4:x}" * 64,
        "state": "ACTIVE", "generation": 1, "revision": 1,
    }


def binding(s):
    return {field: s[field] for field in (
        "tenant", "decrypt_key_arn", "pcr17", "image_sha256",
        "task_definition_arn", "release_sha256", "key_policy_sha256")}


def governance():
    return {
        "workload_account": WORKLOAD,
        "custody_account": CUSTODY,
        "workload_org_id": "o-aaaaaaaaaa",
        "custody_org_id": "o-bbbbbbbbbb",
        "custody_management_account": CUSTODY,
        "custody_admin_roles": [{
            "arn": f"arn:aws:iam::{CUSTODY}:role/independent-custodian",
            "trust_principals": [f"arn:aws:iam::{CUSTODY}:root"],
            "permissions": ["kms:PutKeyPolicy"],
        }],
        "custody_sso_admin_principals": [
            f"arn:aws:iam::{CUSTODY}:role/independent-sso"],
        "custody_cloudformation_execution_roles": [
            f"arn:aws:iam::{CUSTODY}:role/independent-deploy"],
        "custody_billing_delegates": [],
        "custody_root_operator_control": False,
        "inventory_complete": True,
    }


def signer():
    private = ec.generate_private_key(ec.SECP256R1())
    public = private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo)
    return private, public, public_key_fingerprint(public)


def signed_event(private, *, action, tenant="pilot01",
                 previous=None, changes=None, revision=None,
                 issued=NOW, expires=None):
    payload = {
        "schema": _EVENT_SCHEMA,
        "action": action,
        "tenant": tenant,
        "previous_sha256": (canonical_digest(previous)
                            if previous is not None else "0" * 64),
        "revision": (previous["revision"] + 1
                     if revision is None and previous else
                     (revision if revision is not None else 1)),
        "issued_at": issued.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": (expires or issued + timedelta(hours=1)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "changes": changes if changes is not None else {},
    }
    # Independently implemented canonical domain for test signing.
    import json
    data = (b"NotarAI:confidential:custody-operation:v1\x00" +
            json.dumps(payload, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False).encode())
    return {
        "payload": payload,
        "signature_b64": base64.b64encode(
            private.sign(data, ec.ECDSA(hashes.SHA256()))).decode(),
    }


def apply(current, event, public, pin, now=NOW):
    return apply_signed_action(
        current, event, trusted_public_key_pem=public,
        pinned_public_key_sha256=pin, clock=now)


def test_k1_governance_static_screen_never_claims_independence():
    result = validate_governance_snapshot(governance())
    assert result["static_governance_screen_passed"] is True
    assert result["independent_custody_verified"] is False
    assert result["human_root_sso_organizations_audit"] == "BLOCKED"


@pytest.mark.parametrize("mutation", [
    lambda d: d.update(custody_account=WORKLOAD),
    lambda d: d.update(custody_management_account=WORKLOAD),
    lambda d: d.update(custody_org_id=d["workload_org_id"]),
    lambda d: d.update(custody_root_operator_control=True),
    lambda d: d.update(inventory_complete=False),
    lambda d: d.pop("custody_billing_delegates"),
    lambda d: d.update(custody_admin_roles=[]),
    lambda d: d["custody_admin_roles"][0]["trust_principals"].append(
        f"arn:aws:iam::{WORKLOAD}:root"),
    lambda d: d["custody_admin_roles"][0]["trust_principals"].append("*"),
    lambda d: d["custody_admin_roles"][0]["trust_principals"].append(
        f"arn:aws:iam::{CUSTODY}:oidc-provider/token.actions.githubusercontent.com"),
    lambda d: d["custody_admin_roles"][0]["trust_principals"].append(
        "arn:aws:iam::999900001111:root"),
    lambda d: d["custody_sso_admin_principals"].append(
        f"arn:aws:iam::{CUSTODY}:saml-provider/externally-managed"),
    lambda d: d["custody_billing_delegates"].append(
        "arn:aws:iam::999900001111:root"),
    lambda d: d["custody_sso_admin_principals"].append(
        f"arn:aws:iam::{WORKLOAD}:role/GitHubOIDC"),
    lambda d: d["custody_cloudformation_execution_roles"].append(
        f"arn:aws:iam::{WORKLOAD}:role/CFN"),
    lambda d: d["custody_billing_delegates"].append(WORKLOAD),
])
def test_k1_operator_root_github_sso_org_cfn_billing_cannot_validate(mutation):
    sample = governance()
    mutation(sample)
    with pytest.raises(BoundaryDenied):
        validate_governance_snapshot(sample)


@pytest.mark.parametrize("mutation", [
    lambda x: x["key_policy"]["Statement"][1]["Action"].append("kms:PutKeyPolicy"),
    lambda x: x["key_policy"]["Statement"][1]["Action"].append("kms:CreateGrant"),
    lambda x: x["key_policy"]["Statement"][1]["Action"].append("kms:Decrypt"),
    lambda x: x["key_policy"]["Statement"][2].update(
        Principal={"AWS": "*"}),
    lambda x: x["key_grants"].append({
        "GranteePrincipal": f"arn:aws:iam::{WORKLOAD}:root",
        "Operations": ["Decrypt"]}),
])
def test_k2_five_kms_policy_and_grant_attacks_denied(mutation):
    snapshot = old_fixture()
    mutation(snapshot)
    with pytest.raises(BoundaryDenied):
        inspect_operator_boundary(**snapshot)


def test_k3_two_tenants_have_distinct_keys_pcr_and_release():
    result = validate_pilot_inventory([
        state("pilot01", 1), state("pilot02", 2)])
    assert result["tenant_count"] == 2
    assert result["static_tenant_isolation_checked"]
    assert not result["live_kms_isolation_verified"]
    with pytest.raises(BoundaryDenied):
        validate_pilot_inventory([
            state("pilot01", 1), state("pilot01", 1)])
    a, b = state("pilot01", 1), state("pilot02", 2)
    b["decrypt_key_arn"] = a["decrypt_key_arn"]
    with pytest.raises(BoundaryDenied):
        validate_pilot_inventory([a, b])


def test_k3_cross_tenant_cannot_approve_other_task_or_key():
    a, b = state("pilot01", 1), state("pilot02", 2)
    assert authorize_binding_preview(a, binding(a))["binding_preview_passed"]
    for field in ("tenant", "decrypt_key_arn", "pcr17", "task_definition_arn",
                  "release_sha256", "key_policy_sha256"):
        bad = binding(a)
        bad[field] = b[field]
        with pytest.raises(BoundaryDenied):
            authorize_binding_preview(a, bad)


def test_k4_enroll_freeze_revoke_fail_closed_without_old_operator_fallback():
    private, pub, pin = signer()
    initial = state()
    enrolled = apply(None, signed_event(
        private, action="ENROLL",
        changes={x: initial[x] for x in _IDENTITY_FIELDS}), pub, pin)
    assert enrolled == initial
    assert authorize_binding_preview(enrolled, binding(enrolled))[
        "kms_decrypt_performed"] is False
    frozen = apply(enrolled, signed_event(
        private, action="FREEZE", previous=enrolled), pub, pin)
    assert frozen["state"] == "FROZEN"
    with pytest.raises(BoundaryDenied):
        authorize_binding_preview(frozen, binding(initial))
    revoked = apply(frozen, signed_event(
        private, action="REVOKE", previous=frozen), pub, pin)
    assert revoked["state"] == "REVOKED"
    with pytest.raises(BoundaryDenied):
        authorize_binding_preview(revoked, binding(initial))
    with pytest.raises(BoundaryDenied):
        apply(revoked, signed_event(
            private, action="UNFREEZE", previous=revoked), pub, pin)


def test_k4_freeze_action_replay_stale_revision_denied():
    private, pub, pin = signer()
    initial = state()
    event = signed_event(private, action="FREEZE", previous=initial)
    frozen = apply(initial, event, pub, pin)
    with pytest.raises(BoundaryDenied):
        apply(frozen, event, pub, pin)


def test_k5_rotate_only_while_frozen_new_key_then_separate_unfreeze():
    private, pub, pin = signer()
    original = state()
    with pytest.raises(BoundaryDenied):
        apply(original, signed_event(
            private, action="ROTATE", previous=original, changes={}),
            pub, pin)
    frozen = apply(original, signed_event(
        private, action="FREEZE", previous=original), pub, pin)
    rotation = state("pilot01", 2)
    changes = {x: rotation[x] for x in (
        "decrypt_key_arn", "signing_key_arn", "pcr17", "image_sha256",
        "task_definition_arn", "release_sha256", "key_policy_sha256")}
    rotated = apply(frozen, signed_event(
        private, action="ROTATE", previous=frozen, changes=changes), pub, pin)
    assert rotated["state"] == "FROZEN"
    assert rotated["generation"] == 2
    with pytest.raises(BoundaryDenied):
        authorize_binding_preview(rotated, binding(rotation))
    active = apply(rotated, signed_event(
        private, action="UNFREEZE", previous=rotated), pub, pin)
    assert authorize_binding_preview(active, binding(active))[
        "binding_preview_passed"]
    with pytest.raises(BoundaryDenied):
        authorize_binding_preview(active, binding(original))


def test_k5_lost_key_is_terminal_no_admin_plaintext_recovery():
    private, pub, pin = signer()
    before = state()
    lost = apply(before, signed_event(
        private, action="MARK_LOST", previous=before), pub, pin)
    assert lost["state"] == "LOST"
    for action in ("UNFREEZE", "ROTATE", "ENROLL"):
        with pytest.raises(BoundaryDenied):
            apply(lost, signed_event(
                private, action=action, previous=lost), pub, pin)
    with pytest.raises(BoundaryDenied):
        authorize_binding_preview(lost, binding(before))


def test_k5_forged_signature_wrong_pin_expiry_wrong_tenant_and_stale_state():
    trusted, pub, pin = signer()
    untrusted, wrong_pub, wrong_pin = signer()
    s = state()
    event = signed_event(trusted, action="FREEZE", previous=s)
    with pytest.raises(BoundaryDenied):
        apply(s, event, wrong_pub, wrong_pin)
    with pytest.raises(BoundaryDenied):
        apply(s, event, pub, wrong_pin)
    bad = copy.deepcopy(event)
    bad["payload"]["action"] = "REVOKE"
    with pytest.raises(BoundaryDenied):
        apply(s, bad, pub, pin)
    with pytest.raises(BoundaryDenied):
        apply(s, signed_event(
            untrusted, action="FREEZE", previous=s), pub, pin)
    with pytest.raises(BoundaryDenied):
        apply(s, event, pub, pin, now=NOW + timedelta(hours=1))
    with pytest.raises(BoundaryDenied):
        apply(s, signed_event(
            trusted, action="FREEZE", previous=s, tenant="pilot02"), pub, pin)
    with pytest.raises(BoundaryDenied):
        apply(s, signed_event(
            trusted, action="FREEZE", previous=s, revision=99), pub, pin)


def test_no_missing_fields_or_operator_minted_custody_state():
    sample = state()
    sample["admin_override"] = True
    with pytest.raises(BoundaryDenied):
        validate_state(sample)
    with pytest.raises(BoundaryDenied):
        authorize_binding_preview(state(), {"operator_bypass": True})


class FakeSession:
    def __init__(self, profile_name, region_name):
        assert region_name == "eu-central-1"
        self.operator = profile_name == "ops"

    def client(self, name):
        owner = self
        class Client:
            def get_caller_identity(self):
                return {"Account": WORKLOAD if owner.operator else CUSTODY}
            def describe_organization(self):
                return {"Organization": {
                    "Id": "o-aaaaaaaaaa" if owner.operator else "o-bbbbbbbbbb",
                    "ManagementAccountId": WORKLOAD if owner.operator else CUSTODY}}
            def list_roles(self, **kwargs):
                assert not owner.operator
                return {"Roles": [{
                    "Arn": f"arn:aws:iam::{CUSTODY}:role/external-custodian",
                    "AssumeRolePolicyDocument": {"Statement": [{
                        "Effect": "Allow", "Principal": {
                            "AWS": f"arn:aws:iam::{CUSTODY}:root"},
                        "Action": "sts:AssumeRole"}]}
                }], "IsTruncated": False}
        assert name in (("sts", "organizations") if owner.operator else
                        ("sts", "organizations", "iam"))
        return Client()


def test_k6_aws_auditor_inert_by_default_and_live_never_proves_independence():
    assert audit_aws(
        operator_profile="ops", custody_profile="custody",
        session_factory=lambda **kw: (_ for _ in ()).throw(
            AssertionError("dry-run tried AWS")))["aws_calls"] == 0
    result = audit_aws(
        operator_profile="ops", custody_profile="custody", check=True,
        session_factory=FakeSession)
    assert result["static_governance_screen_passed"] is True
    assert result["status"] == "BLOCKED"
    assert not result["independent_custody_verified"]
    assert result["root_sso_billing_cloudformation_external_audit"] == "BLOCKED"


def test_k6_aws_auditor_denies_same_org_and_operator_assume_role():
    class SameOrg(FakeSession):
        def client(self, name):
            c = super().client(name)
            if name == "organizations" and not self.operator:
                c.describe_organization = lambda: {"Organization": {
                    "Id": "o-aaaaaaaaaa", "ManagementAccountId": CUSTODY}}
            return c
    class OperatorRole(FakeSession):
        def client(self, name):
            c = super().client(name)
            if name == "iam":
                c.list_roles = lambda **kwargs: {"Roles": [{
                    "Arn": f"arn:aws:iam::{CUSTODY}:role/backdoor",
                    "AssumeRolePolicyDocument": {"Statement": [{
                        "Effect": "Allow",
                        "Principal": {"AWS": f"arn:aws:iam::{WORKLOAD}:root"}}]}
                }], "IsTruncated": False}
            return c
    for factory in (SameOrg, OperatorRole):
        with pytest.raises(BoundaryDenied):
            audit_aws(operator_profile="ops", custody_profile="custody",
                      check=True, session_factory=factory)


def test_k6_missing_live_organization_permissions_blocks_claim():
    class MissingOrg(FakeSession):
        def client(self, name):
            if name == "organizations":
                raise PermissionError("missing")
            return super().client(name)
    with pytest.raises(BoundaryDenied):
        audit_aws(operator_profile="ops", custody_profile="custody",
                  check=True, session_factory=MissingOrg)


def test_k4_rendered_revocation_policy_removes_decrypt_and_no_operator_fallback():
    from confidential.custody_ops import (
        render_kms_policy_target, verify_kms_policy_snapshot)
    active = state()
    active_policy = render_kms_policy_target(active)["target_policy"]
    active["key_policy_sha256"] = canonical_digest(active_policy)
    assert len(active_policy["Statement"]) == 3
    assert verify_kms_policy_snapshot(
        active, active_policy, [])["kms_policy_snapshot_checked"]
    frozen = {**active, "state": "FROZEN", "revision": 2}
    deny_policy = render_kms_policy_target(frozen)["target_policy"]
    assert len(deny_policy["Statement"]) == 2
    assert "kms:Decrypt" not in str(deny_policy)
    assert "kms:CreateGrant" not in str(deny_policy)
    assert verify_kms_policy_snapshot(
        frozen, deny_policy, [])["kms_policy_snapshot_checked"]
    with pytest.raises(BoundaryDenied):
        verify_kms_policy_snapshot(frozen, active_policy, [])
    with pytest.raises(BoundaryDenied):
        verify_kms_policy_snapshot(frozen, deny_policy, [{
            "GranteePrincipal": f"arn:aws:iam::{WORKLOAD}:root",
            "Operations": ["Decrypt"]}])
    revoked = {**frozen, "state": "REVOKED"}
    assert render_kms_policy_target(revoked)["target_policy"] == deny_policy
    lost = {**frozen, "state": "LOST"}
    assert render_kms_policy_target(lost)["target_policy"] == deny_policy


def test_k5_external_custodian_signer_is_dry_run_by_default():
    from scripts.custodian_sign_confidential_operation import sign_operation
    private, pub, pin = signer()
    s = state()
    event = signed_event(private, action="FREEZE", previous=s)
    result = sign_operation(
        payload=event["payload"], state=s, custody_profile="external",
        signing_key_arn=s["signing_key_arn"],
        pinned_public_key_sha256=pin,
        session_factory=lambda **kw: (_ for _ in ()).throw(
            AssertionError("dry-run must not make AWS calls")),
        clock=NOW)
    assert result == {
        "status": "dry-run", "aws_calls": 0,
        "independent_custody_verified": False,
    }


def test_k5_kms_sign_only_external_custody_and_independent_public_pin():
    from scripts.custodian_sign_confidential_operation import sign_operation
    from confidential.custody_ops import _signed_event_bytes
    private, pub, pin = signer()
    state_before = state()
    event = signed_event(private, action="FREEZE", previous=state_before)
    pub_der = private.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo)

    class CustodySession:
        def __init__(self, profile_name, region_name):
            assert profile_name == "custody"
            assert region_name == "eu-central-1"
        def client(self, name):
            class Api:
                def get_caller_identity(self):
                    return {"Account": CUSTODY}
                def describe_key(self, **kwargs):
                    assert kwargs["KeyId"] == state_before["signing_key_arn"]
                    return {"KeyMetadata": {
                        "Arn": state_before["signing_key_arn"],
                        "KeySpec": "ECC_NIST_P256",
                        "KeyUsage": "SIGN_VERIFY", "KeyState": "Enabled"}}
                def get_public_key(self, **kwargs):
                    return {"PublicKey": pub_der}
                def sign(self, **kwargs):
                    assert kwargs["MessageType"] == "RAW"
                    assert kwargs["SigningAlgorithm"] == "ECDSA_SHA_256"
                    return {"Signature": private.sign(
                        kwargs["Message"], ec.ECDSA(hashes.SHA256()))}
            assert name in ("sts", "kms")
            return Api()
    result = sign_operation(
        payload=event["payload"], state=state_before,
        custody_profile="custody",
        signing_key_arn=state_before["signing_key_arn"],
        pinned_public_key_sha256=pin,
        pinned_current_state_sha256=canonical_digest(state_before),
        approve_action=True, session_factory=CustodySession, clock=NOW)
    assert result["aws_calls"] == 4
    assert result["status"] == "signed"
    updated = apply(state_before, result["envelope"], pub, pin)
    assert updated["state"] == "FROZEN"

    with pytest.raises(BoundaryDenied):
        sign_operation(
            payload=event["payload"], state=state_before,
            custody_profile="custody", signing_key_arn=state_before[
                "signing_key_arn"], pinned_public_key_sha256="f" * 64,
            pinned_current_state_sha256=canonical_digest(state_before),
            approve_action=True, session_factory=CustodySession, clock=NOW)

    class WorkloadSession(CustodySession):
        def client(self, name):
            api = super().client(name)
            if name == "sts":
                api.get_caller_identity = lambda: {"Account": WORKLOAD}
            return api
    with pytest.raises(BoundaryDenied):
        sign_operation(
            payload=event["payload"], state=state_before,
            custody_profile="custody", signing_key_arn=state_before[
                "signing_key_arn"], pinned_public_key_sha256=pin,
            pinned_current_state_sha256=canonical_digest(state_before),
            approve_action=True, session_factory=WorkloadSession, clock=NOW)


def test_k5_kms_signer_rejects_operator_approval_minting_and_stale_version():
    from scripts.custodian_sign_confidential_operation import sign_operation
    private, pub, pin = signer()
    s = state()
    for event in (
        signed_event(private, action="UNFREEZE", previous=s),
        signed_event(private, action="FREEZE", previous=s, revision=1),
        signed_event(private, action="ROTATE", previous=s),
        signed_event(private, action="FREEZE", previous=s,
                     tenant="pilot02"),
    ):
        with pytest.raises(BoundaryDenied):
            sign_operation(
                payload=event["payload"], state=s,
                custody_profile="custody",
                signing_key_arn=s["signing_key_arn"],
                pinned_public_key_sha256=pin, clock=NOW)



def test_k3_offline_planner_reproducible_cas_bindings_without_aws():
    from scripts.plan_confidential_custody_operation import plan_operation
    s = state()
    plan = plan_operation(
        action="FREEZE", tenant="pilot01", state=s, clock=NOW)
    assert plan["aws_calls"] == 0
    assert plan["authorized_for_decrypt"] is False
    assert plan["custodian_independent_signature_required"] is True
    assert plan["custodian_ledger_compare_and_swap_required"] is True
    assert plan["kms_policy_write_performed"] is False
    assert plan["unsigned_event_payload"]["previous_sha256"] == canonical_digest(s)
    assert plan["unsigned_event_payload"]["revision"] == 2
    assert plan["unsigned_event_payload"]["expires_at"] == "2026-11-22T03:15:00Z"
    assert len(plan["proposed_key_policy"]["Statement"]) == 2
    assert "kms:Decrypt" not in str(plan["proposed_key_policy"])


def test_k4_planner_requires_approved_tenant_frozen_rotation_and_no_recovery():
    from scripts.plan_confidential_custody_operation import plan_operation
    s = state()
    for kwargs in (
        {"action": "UNFREEZE"},
        {"action": "ROTATE"},
        {"action": "ENROLL"},
    ):
        with pytest.raises(BoundaryDenied):
            plan_operation(tenant="pilot01", state=s, clock=NOW, **kwargs)
    with pytest.raises(BoundaryDenied):
        plan_operation(action="FREEZE", tenant="pilot02", state=s,
                       clock=NOW)
    with pytest.raises(BoundaryDenied):
        plan_operation(action="FREEZE", tenant="pilot01", state=s,
                       ttl_minutes=0, clock=NOW)
    with pytest.raises(BoundaryDenied):
        plan_operation(action="FREEZE", tenant="pilot01", state=s,
                       ttl_minutes=61, clock=NOW)
    with pytest.raises(BoundaryDenied):
        plan_operation(action="FREEZE", tenant="pilot01", state=s,
                       clock=NOW.replace(tzinfo=None))
    private, pub, pin = signer()
    revoked = apply(s, signed_event(private, action="REVOKE", previous=s), pub, pin)
    with pytest.raises(BoundaryDenied):
        plan_operation(action="UNFREEZE", tenant="pilot01",
                       state=revoked, clock=NOW)


def test_k5_planner_rotation_requires_distinct_new_keys_and_freeze():
    from scripts.plan_confidential_custody_operation import plan_operation
    private, pub, pin = signer()
    before = state()
    frozen = apply(before, signed_event(
        private, action="FREEZE", previous=before), pub, pin)
    fresh = state("pilot01", 2)
    changes = {x: fresh[x] for x in (
        "decrypt_key_arn", "signing_key_arn", "pcr17", "image_sha256",
        "task_definition_arn", "release_sha256", "key_policy_sha256")}
    plan = plan_operation(action="ROTATE", tenant="pilot01", state=frozen,
                          changes=changes, clock=NOW)
    assert plan["unsigned_event_payload"]["revision"] == 3
    assert len(plan["proposed_key_policy"]["Statement"]) == 2
    assert "kms:Decrypt" not in str(plan["proposed_key_policy"])
    assert plan["expected_signing_key_arn"] == before["signing_key_arn"]
    targets = plan["required_kms_key_policy_targets"]
    assert len(targets) == 2
    assert {t["key_arn"] for t in targets} == {
        before["decrypt_key_arn"], fresh["decrypt_key_arn"]}
    assert all("kms:Decrypt" not in str(t["target_policy"]) for t in targets)
    assert all(t["requires_no_grants"] for t in targets)
    assert not plan["historical_decrypt_key_inventory_complete"]
    assert not plan["historical_keys_effectively_denied_verified"]
    bad = dict(changes)
    bad["decrypt_key_arn"] = before["decrypt_key_arn"]
    with pytest.raises(BoundaryDenied):
        plan_operation(action="ROTATE", tenant="pilot01", state=frozen,
                       changes=bad, clock=NOW)


def test_k4_planner_freeze_cannot_be_forged_as_signed_decision():
    from scripts.plan_confidential_custody_operation import plan_operation
    s = state()
    private, pub, pin = signer()
    plan = plan_operation(
        action="REVOKE", tenant="pilot01", state=s, clock=NOW)
    assert "signature_b64" not in plan
    assert plan["release_frozen_after_planning"] is False
    with pytest.raises(BoundaryDenied):
        apply_signed_action(
            s, {"payload": plan["unsigned_event_payload"],
                "signature_b64": ""}, trusted_public_key_pem=pub,
            pinned_public_key_sha256=pin, clock=NOW)



def test_k1_github_oidc_federation_and_saml_trust_blocked():
    """A provider in the custody account can still trust operator CI."""
    from scripts.verify_confidential_custody_independence import (
        _scan_custody_role_trusts,
    )
    class FederatedSession:
        def __init__(self, method):
            self.method = method
        def client(self, name):
            assert name == "iam"
            method = self.method
            class Api:
                def list_roles(self, **kwargs):
                    return {"IsTruncated": False, "Roles": [{
                        "Arn": f"arn:aws:iam::{CUSTODY}:role/external-oidc",
                        "Path": "/",
                        "AssumeRolePolicyDocument": {"Version": "2012-10-17",
                            "Statement": [{"Effect": "Allow",
                                "Action": method,
                                "Principal": {"Federated":
                                    f"arn:aws:iam::{CUSTODY}:"
                                    "oidc-provider/token.actions.githubusercontent.com"},
                                "Condition": {"StringLike": {
                                    "token.actions.githubusercontent.com:sub":
                                    "repo:plnyspolka-pixel/notarai:*"}}}]},
                    }]}
            return Api()
    for method in ("sts:AssumeRoleWithWebIdentity", "sts:AssumeRoleWithSAML"):
        with pytest.raises(BoundaryDenied):
            _scan_custody_role_trusts(FederatedSession(method), WORKLOAD,
                                     CUSTODY)


def test_k1_third_party_aws_and_unmanaged_service_trust_denied():
    from scripts.verify_confidential_custody_independence import (
        _scan_custody_role_trusts,
    )
    class OtherTrust:
        def __init__(self, group, principal, path="/"):
            self.group, self.principal, self.path = group, principal, path
        def client(self, name):
            assert name == "iam"
            group, principal, path = self.group, self.principal, self.path
            class Api:
                def list_roles(self, **kwargs):
                    return {"IsTruncated": False, "Roles": [{
                        "Arn": f"arn:aws:iam::{CUSTODY}:role/sensitive-admin",
                        "Path": path,
                        "AssumeRolePolicyDocument": {"Statement": [{
                            "Effect": "Allow",
                            "Action": "sts:AssumeRole",
                            "Principal": {group: principal}}]},
                    }]}
            return Api()
    for group, principal in (
        ("AWS", "arn:aws:iam::999900001111:root"),
        ("Service", "ecs-tasks.amazonaws.com"),
        ("AWS", "*"),
        ("AWS", f"arn:aws:iam::{WORKLOAD}:role/GitHubDeployment"),
    ):
        with pytest.raises(BoundaryDenied):
            _scan_custody_role_trusts(
                OtherTrust(group, principal), WORKLOAD, CUSTODY)


def test_k1_only_service_linked_role_may_pass_service_static_screen():
    from scripts.verify_confidential_custody_independence import (
        _scan_custody_role_trusts,
    )
    class ServiceLinked:
        def client(self, name):
            class Api:
                def list_roles(self, **kwargs):
                    return {"IsTruncated": False, "Roles": [{
                        "Arn": f"arn:aws:iam::{CUSTODY}:role/"
                               "aws-service-role/organizations.amazonaws.com/"
                               "AWSServiceRoleForOrganizations",
                        "Path": "/aws-service-role/organizations.amazonaws.com/",
                        "AssumeRolePolicyDocument": {"Statement": [{
                            "Effect": "Allow", "Action": "sts:AssumeRole",
                            "Principal": {"Service": "organizations.amazonaws.com"}}]},
                    }]}
            return Api()
    assert _scan_custody_role_trusts(ServiceLinked(), WORKLOAD, CUSTODY) == 1



def test_k3_two_tenant_bootstrap_produces_two_unsigned_independent_plans():
    from scripts.prepare_confidential_custody_onboarding import (
        prepare_two_tenant_onboarding,
    )
    one, two = state("pilot01", 1), state("pilot02", 2)
    bindings = [
        {key: s[key] for key in _IDENTITY_FIELDS}
        for s in (two, one)  # input order must not affect plan order
    ]
    plan = prepare_two_tenant_onboarding(bindings=bindings, clock=NOW)
    assert plan["tenant_count"] == 2
    assert plan["aws_calls"] == 0
    assert not plan["kms_resources_created"]
    assert not plan["signing_performed"]
    assert not plan["actual_onboarding_complete"]
    assert not plan["independent_custody_verified"]
    assert [p["unsigned_event_payload"]["tenant"] for p in plan[
        "review_packages"]] == ["pilot01", "pilot02"]
    assert len({p["expected_signing_key_arn"] for p in plan[
        "review_packages"]}) == 2
    assert all(p["unsigned_event_payload"]["action"] == "ENROLL"
               for p in plan["review_packages"])
    assert all("signature_b64" not in p for p in plan["review_packages"])


def test_k3_two_tenant_bootstrap_denies_duplicate_keys_and_wrong_identity():
    from scripts.prepare_confidential_custody_onboarding import (
        prepare_two_tenant_onboarding,
    )
    one, two = state("pilot01", 1), state("pilot02", 2)
    a = {key: one[key] for key in _IDENTITY_FIELDS}
    b = {key: two[key] for key in _IDENTITY_FIELDS}
    for bad in (
        {**b, "decrypt_key_arn": a["decrypt_key_arn"]},
        {**b, "signing_key_arn": a["signing_key_arn"]},
        {**b, "pcr17": a["pcr17"]},
        {**b, "task_definition_arn": a["task_definition_arn"]},
        {**b, "release_sha256": a["release_sha256"]},
        {**b, "tenant": "pilot01"},
        {**b, "extra_operator_override": True},
    ):
        with pytest.raises(BoundaryDenied):
            prepare_two_tenant_onboarding(bindings=[a, bad], clock=NOW)



def test_k5_signer_requires_out_of_band_custody_state_version_pin():
    from scripts.custodian_sign_confidential_operation import sign_operation
    private, pub, pin = signer()
    s = state()
    event = signed_event(private, action="REVOKE", previous=s)
    for pinned in (None, "0" * 64, "f" * 64):
        with pytest.raises(BoundaryDenied,
                           match="independent custody ledger state pin"):
            sign_operation(
                payload=event["payload"], state=s,
                custody_profile="custody",
                signing_key_arn=s["signing_key_arn"],
                pinned_public_key_sha256=pin,
                pinned_current_state_sha256=pinned,
                approve_action=True, clock=NOW,
                session_factory=lambda **kw: (_ for _ in ()).throw(
                    AssertionError("must refuse before calling AWS")))



def test_k6_live_audit_cli_never_signals_success_while_external_proof_blocked(
    monkeypatch,
):
    import scripts.verify_confidential_custody_independence as audit_module
    monkeypatch.setattr(audit_module, "inspect", lambda **kwargs: {
        "status": "BLOCKED",
        "independent_custody_verified": False,
        "static_governance_screen_passed": True,
    })
    assert audit_module.main([
        "--operator-profile", "operator-read",
        "--custody-profile", "external-read", "--check",
    ]) == 3
    # --check not set = informational dry-run, not a compliance gate.
    assert audit_module.main([
        "--operator-profile", "operator-read",
        "--custody-profile", "external-read",
    ]) == 0



def test_k1_k5_malformed_json_types_fail_with_boundary_denial_not_crash():
    from scripts.custodian_sign_confidential_operation import sign_operation
    private, pub, pin = signer()
    s = state()
    malformed = dict(s, state=[])
    with pytest.raises(BoundaryDenied):
        validate_state(malformed)
    event = signed_event(private, action="FREEZE", previous=s)
    tampered = copy.deepcopy(event)
    tampered["payload"]["action"] = ["FREEZE"]
    with pytest.raises(BoundaryDenied):
        apply(s, tampered, pub, pin)
    with pytest.raises(BoundaryDenied):
        sign_operation(
            payload=event["payload"], state=s,
            custody_profile="custodian",
            signing_key_arn=s["signing_key_arn"],
            pinned_public_key_sha256=pin,
            pinned_current_state_sha256=canonical_digest(s),
            approve_action=True,
            clock="not a datetime",
            session_factory=lambda **kw: (_ for _ in ()).throw(
                AssertionError("malformed clock must not call AWS")))
