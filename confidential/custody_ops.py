"""SEC-06: signed, fail-closed synthetic custody lifecycle.

This module NEVER calls AWS, changes KMS policies, decrypts data, or proves
institutional independence. It provides a deterministic authorization preview
for a separate custodian-controlled control plane. Persistence, key disabling,
and enforcement of revocation at KMS are external, mandatory live controls.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from collections.abc import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from confidential.operator_boundary import BoundaryDenied, canonical_digest
from confidential.release_approval import public_key_fingerprint

_DOMAIN = b"NotarAI:confidential:custody-operation:v1\x00"
_SCHEMA = "notarai.confidential.custody-state.v1"
_EVENT_SCHEMA = "notarai.confidential.custody-operation.v1"
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_PCR = re.compile(r"(?!0{96}\Z)[0-9a-f]{96}\Z")
_ACCOUNT = re.compile(r"[0-9]{12}\Z")
_TENANT = re.compile(r"pilot0[12]\Z")
_ROLE = re.compile(r"arn:aws:iam::([0-9]{12}):role/[A-Za-z0-9+=,.@_/-]+\Z")
_KMS = re.compile(r"arn:aws:kms:eu-central-1:([0-9]{12}):key/[0-9a-fA-F-]{36}\Z")
_TASK = re.compile(r"arn:aws:ecs:eu-central-1:([0-9]{12}):task-definition/notarai-confidential-(pilot0[12]):[1-9][0-9]*\Z")
_STATE_FIELDS = frozenset({
    "schema", "tenant", "workload_account", "custody_account",
    "decrypt_key_arn", "signing_key_arn", "pcr17", "image_sha256",
    "task_definition_arn", "release_sha256", "key_policy_sha256",
    "state", "generation", "revision",
})
_IDENTITY_FIELDS = _STATE_FIELDS - {"schema", "state", "generation", "revision"}
_ROTATION_FIELDS = frozenset({
    "decrypt_key_arn", "signing_key_arn", "pcr17", "image_sha256",
    "task_definition_arn", "release_sha256", "key_policy_sha256",
})
_EVENT_FIELDS = frozenset({
    "schema", "action", "tenant", "revision", "previous_sha256",
    "issued_at", "expires_at", "changes",
})


def _require(ok: bool, description: str) -> None:
    if not ok:
        raise BoundaryDenied(description)


def _utc(value: object) -> datetime:
    _require(isinstance(value, str) and
             re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", value) is not None,
             "custody event timestamp invalid")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError:
        raise BoundaryDenied("custody event timestamp invalid") from None


def validate_state(state: Mapping) -> dict:
    _require(isinstance(state, dict) and set(state) == _STATE_FIELDS,
             "custody state schema invalid")
    _require(state["schema"] == _SCHEMA, "custody state version invalid")
    tenant, workload, custody = (state[x] for x in (
        "tenant", "workload_account", "custody_account"))
    _require(isinstance(tenant, str) and _TENANT.fullmatch(tenant) is not None,
             "only synthetic pilot tenant allowed")
    _require(all(isinstance(x, str) and _ACCOUNT.fullmatch(x)
                 for x in (workload, custody)) and workload != custody,
             "independent custody account required")
    for field in ("decrypt_key_arn", "signing_key_arn"):
        arn = state[field]
        _require(isinstance(arn, str) and
                 (match := _KMS.fullmatch(arn)) is not None and
                 match.group(1) == custody, "custody KMS key ownership mismatch")
    _require(state["decrypt_key_arn"] != state["signing_key_arn"],
             "signing and decryption keys must be separate")
    task = state["task_definition_arn"]
    match = _TASK.fullmatch(task) if isinstance(task, str) else None
    _require(match is not None and match.group(1) == workload and
             match.group(2) == tenant, "task revision not tenant pinned")
    _require(isinstance(state["pcr17"], str) and
             _PCR.fullmatch(state["pcr17"]) is not None, "PCR17 unapproved")
    for name in ("image_sha256", "release_sha256", "key_policy_sha256"):
        value = state[name]
        _require(isinstance(value, str) and _HEX64.fullmatch(value) is not None,
                 "release, image and policy digests must be pinned")
    _require(state["state"] in {"ACTIVE", "FROZEN", "REVOKED", "LOST"},
             "unknown custody state")
    _require(type(state["generation"]) is int and state["generation"] >= 1 and
             type(state["revision"]) is int and state["revision"] >= 1,
             "custody monotonic counters invalid")
    return dict(state)


def validate_pilot_inventory(states: list[dict]) -> dict:
    """Two tenant bindings may not share keys, task, approvals or PCR."""
    _require(isinstance(states, list) and len(states) == 2,
             "two synthetic tenants are required")
    verified = [validate_state(s) for s in states]
    _require({s["tenant"] for s in verified} == {"pilot01", "pilot02"},
             "pilot inventory is not independently tenant bound")
    _require(len({s["workload_account"] for s in verified}) == 1,
             "workload identity must be consistent")
    for field in ("decrypt_key_arn", "signing_key_arn", "pcr17",
                  "task_definition_arn", "release_sha256",
                  "key_policy_sha256"):
        _require(len({s[field] for s in verified}) == 2,
                 "pilot tenant security bindings must be unique")
    return {
        "tenant_count": 2, "static_tenant_isolation_checked": True,
        "live_kms_isolation_verified": False,
        "independent_custody_verified": False,
    }


def validate_governance_snapshot(snapshot: Mapping) -> dict:
    """Fail-closed structural screening; human root/SSO ownership not provable here.

    Every privileged custody role/trust, SSO admin, organization management,
    delegated billing and CloudFormation execution role must be inspected.
    Missing inventory is a denial, not evidence of absence.
    """
    fields = {
        "workload_account", "custody_account", "workload_org_id",
        "custody_org_id", "custody_management_account",
        "custody_admin_roles", "custody_sso_admin_principals",
        "custody_cloudformation_execution_roles",
        "custody_billing_delegates", "custody_root_operator_control",
        "inventory_complete",
    }
    _require(isinstance(snapshot, Mapping) and set(snapshot) == fields,
             "governance inventory incomplete")
    operator = snapshot["workload_account"]
    custody = snapshot["custody_account"]
    manager = snapshot["custody_management_account"]
    _require(all(isinstance(x, str) and _ACCOUNT.fullmatch(x)
                 for x in (operator, custody, manager)) and
             operator != custody and manager != operator,
             "operator controls custody or Organizations management")
    for org_field in ("workload_org_id", "custody_org_id"):
        org = snapshot[org_field]
        _require(org is None or (isinstance(org, str) and
                 re.fullmatch(r"o-[a-z0-9]{10,32}", org)),
                 "organization ID missing or invalid")
    _require(snapshot["workload_org_id"] is None or
             snapshot["custody_org_id"] is None or
             snapshot["workload_org_id"] != snapshot["custody_org_id"],
             "shared operator Organizations boundary")
    _require(snapshot["inventory_complete"] is True and
             snapshot["custody_root_operator_control"] is False,
             "root/SSO governance not independently established")
    roles = snapshot["custody_admin_roles"]
    _require(isinstance(roles, list) and len(roles) > 0,
             "custodian role inventory missing")
    for role in roles:
        _require(isinstance(role, dict) and set(role) == {
            "arn", "trust_principals", "permissions"}, "role inventory invalid")
        arn = role["arn"]
        _require(isinstance(arn, str) and
                 (m := _ROLE.fullmatch(arn)) is not None and
                 m.group(1) == custody, "privileged role outside custody")
        trusts = role["trust_principals"]
        _require(isinstance(trusts, list) and len(trusts) > 0 and
                 all(isinstance(p, str) and p != "*" and
                     not p.startswith("arn:aws:iam::" + operator + ":") and
                     p != operator for p in trusts),
                 "operator can assume custodian role")
        _require(isinstance(role["permissions"], list) and
                 all(isinstance(p, str) for p in role["permissions"]),
                 "role permissions inventory incomplete")
    for field in ("custody_sso_admin_principals",
                  "custody_cloudformation_execution_roles",
                  "custody_billing_delegates"):
        principals = snapshot[field]
        _require(isinstance(principals, list), "delegation inventory incomplete")
        for p in principals:
            _require(isinstance(p, str) and p != "*" and p != operator and
                     not p.startswith("arn:aws:iam::" + operator + ":"),
                     "operator controls custody delegated access")
    return {
        "static_governance_screen_passed": True,
        "independent_custody_verified": False,
        "human_root_sso_organizations_audit": "BLOCKED",
        "live_cross_account_evidence": "BLOCKED",
    }


def _signed_event_bytes(payload: Mapping) -> bytes:
    _require(isinstance(payload, dict) and set(payload) == _EVENT_FIELDS,
             "custody action envelope schema invalid")
    _require(payload["schema"] == _EVENT_SCHEMA, "custody action version invalid")
    try:
        return _DOMAIN + json.dumps(
            payload, sort_keys=True, separators=(",", ":"), allow_nan=False,
            ensure_ascii=True).encode("utf-8")
    except (ValueError, TypeError):
        raise BoundaryDenied("custody action not serializable") from None


def apply_signed_action(
    state: dict | None, envelope: Mapping, *,
    trusted_public_key_pem: bytes, pinned_public_key_sha256: str,
    clock: datetime | None = None,
) -> dict:
    """Pure reducer; caller must persist via independent CAS and enforce KMS deny."""
    _require(isinstance(envelope, dict) and set(envelope) == {
        "payload", "signature_b64"}, "custody signature envelope invalid")
    payload = envelope["payload"]
    signed = _signed_event_bytes(payload)
    action = payload["action"]
    _require(action in {"ENROLL", "FREEZE", "UNFREEZE", "REVOKE",
                        "ROTATE", "MARK_LOST"}, "unknown custody operation")
    _require(isinstance(payload["tenant"], str) and
             _TENANT.fullmatch(payload["tenant"]) is not None,
             "custody tenant not permitted")
    issued, expires = _utc(payload["issued_at"]), _utc(payload["expires_at"])
    now = clock if clock is not None else datetime.now(timezone.utc)
    _require(isinstance(now, datetime) and now.tzinfo is not None,
             "timezone-aware custody clock required")
    now = now.astimezone(timezone.utc)
    _require(issued <= now < expires and
             timedelta(0) < expires - issued <= timedelta(hours=24),
             "custody authorization expired or not yet valid")
    _require(isinstance(pinned_public_key_sha256, str) and
             _HEX64.fullmatch(pinned_public_key_sha256) is not None and
             public_key_fingerprint(trusted_public_key_pem) ==
             pinned_public_key_sha256,
             "custodian fingerprint must be independently pinned")
    signature = envelope["signature_b64"]
    _require(isinstance(signature, str), "custody signature missing")
    try:
        decoded = base64.b64decode(signature, validate=True)
        public = serialization.load_pem_public_key(trusted_public_key_pem)
        _require(isinstance(public, ec.EllipticCurvePublicKey) and
                 isinstance(public.curve, ec.SECP256R1),
                 "custodian ECDSA P-256 signer required")
        public.verify(decoded, signed, ec.ECDSA(hashes.SHA256()))
    except (ValueError, TypeError, binascii.Error, InvalidSignature):
        raise BoundaryDenied("independent custody signature invalid") from None

    changes = payload["changes"]
    _require(isinstance(changes, dict), "custody change set invalid")
    if state is None:
        _require(action == "ENROLL" and
                 payload["previous_sha256"] == "0" * 64 and
                 payload["revision"] == 1 and
                 set(changes) == _IDENTITY_FIELDS and
                 changes.get("tenant") == payload["tenant"],
                 "custody enrollment must be independently approved")
        return validate_state({
            **changes, "schema": _SCHEMA,
            "generation": 1, "revision": 1, "state": "ACTIVE",
        })

    state = validate_state(state)
    _require(payload["tenant"] == state["tenant"] and
             type(payload["revision"]) is int and
             payload["revision"] == state["revision"] + 1 and
             payload["previous_sha256"] == canonical_digest(state),
             "custody action replay, revision or tenant mismatch")
    _require(state["state"] not in {"REVOKED", "LOST"},
             "revoked or lost custody is terminal")
    next_state = dict(state)
    if action == "FREEZE":
        _require(state["state"] == "ACTIVE" and changes == {},
                 "freeze transition invalid")
        next_state["state"] = "FROZEN"
    elif action == "UNFREEZE":
        _require(state["state"] == "FROZEN" and changes == {},
                 "unfreeze needs independent approval")
        next_state["state"] = "ACTIVE"
    elif action == "REVOKE":
        _require(changes == {}, "revocation cannot alter policy")
        next_state["state"] = "REVOKED"
    elif action == "MARK_LOST":
        _require(changes == {}, "key loss must deny recovery")
        next_state["state"] = "LOST"
    elif action == "ROTATE":
        _require(state["state"] == "FROZEN" and
                 set(changes) == _ROTATION_FIELDS and
                 changes["decrypt_key_arn"] != state["decrypt_key_arn"] and
                 changes["signing_key_arn"] != state["signing_key_arn"] and
                 changes["release_sha256"] != state["release_sha256"],
                 "rotation requires frozen state and fresh custody keys")
        next_state.update(changes)
        next_state["generation"] += 1
        next_state["state"] = "FROZEN"  # separate UNFREEZE after KMS policy audit
    else:
        raise BoundaryDenied("re-enrollment would bypass custody history")
    next_state["revision"] += 1
    return validate_state(next_state)


def authorize_binding_preview(state: Mapping, request: Mapping) -> dict:
    """Never performs decrypt. A successful preview is NOT an AWS allow."""
    current = validate_state(state)
    expected = {field: current[field] for field in (
        "tenant", "decrypt_key_arn", "pcr17", "image_sha256",
        "task_definition_arn", "release_sha256", "key_policy_sha256")}
    _require(current["state"] == "ACTIVE" and
             isinstance(request, Mapping) and dict(request) == expected,
             "custody denies decrypt: frozen, revoked, stale or wrong tenant")
    return {
        "binding_preview_passed": True,
        "kms_decrypt_performed": False,
        "hardware_attestation_verified": False,
        "independent_custody_verified": False,
    }


def render_kms_policy_target(state: Mapping) -> dict:
    """Generate a custody-account change request, never apply it to AWS.

    FREEZE/REVOKE/LOST remove all task Decrypt permissions. The independent
    custodian must apply the policy and provide CloudTrail + ListGrants proof
    before claiming effective revocation. An operator cannot use this as an
    implicit authorize/decrypt endpoint.
    """
    s = validate_state(state)
    admin_actions = [
        "kms:DescribeKey", "kms:GetKeyPolicy", "kms:PutKeyPolicy",
        "kms:EnableKey", "kms:DisableKey", "kms:UpdateKeyDescription",
        "kms:ListResourceTags", "kms:TagResource", "kms:UntagResource",
        "kms:ScheduleKeyDeletion", "kms:CancelKeyDeletion",
    ]
    statements = [
        {
            "Sid": "CustodyAdministratorOnly", "Effect": "Allow",
            "Principal": {"AWS": f"arn:aws:iam::{s['custody_account']}:root"},
            "Action": admin_actions, "Resource": "*",
        },
        {
            "Sid": "NotaraiPublicKeyOnly", "Effect": "Allow",
            "Principal": {"AWS": f"arn:aws:iam::{s['workload_account']}:root"},
            "Action": ["kms:GetPublicKey", "kms:DescribeKey"], "Resource": "*",
        },
    ]
    if s["state"] == "ACTIVE":
        statements.append({
            "Sid": "OnlyAttestedNitroTaskDecrypt", "Effect": "Allow",
            "Principal": {"AWS": (
                f"arn:aws:iam::{s['workload_account']}:"
                f"role/notarai-confidential-{s['tenant']}")},
            "Action": "kms:Decrypt", "Resource": "*",
            "Condition": {"StringEqualsIgnoreCase": {
                "kms:RecipientAttestation:PCR17": s["pcr17"],
                "kms:RecipientAttestation:PCR8:ServiceName":
                    "ecs.amazonaws.com"}},
        })
    target = {"Version": "2012-10-17", "Statement": statements}
    return {
        "target_policy": target,
        "target_policy_sha256": canonical_digest(target),
        "requires_independent_custodian_apply": True,
        "kms_policy_changed": False,
        "live_grants_audited": False,
        "live_cloudtrail_verified": False,
    }


def verify_kms_policy_snapshot(state: Mapping, observed_policy: Mapping,
                               observed_grants: list) -> dict:
    """Instantaneous read-only snapshot, not a guarantee against future tamper."""
    s = validate_state(state)
    expected = render_kms_policy_target(s)["target_policy"]
    _require(isinstance(observed_policy, Mapping) and
             dict(observed_policy) == expected,
             "custodian KMS key policy does not enforce lifecycle state")
    _require(isinstance(observed_grants, list) and not observed_grants,
             "unreviewed KMS grants remain")
    if s["state"] == "ACTIVE":
        _require(canonical_digest(dict(observed_policy)) ==
                 s["key_policy_sha256"],
                 "live KMS policy differs from custodian-approved release hash")
    return {
        "kms_policy_snapshot_checked": True,
        "kms_decrypt_exercised": False,
        "independent_custody_verified": False,
    }
