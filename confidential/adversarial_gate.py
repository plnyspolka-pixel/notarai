"""SEC-12 synthetic adversarial matrix and *fail-closed* commercial gate.

This module models attacks on the expected contracts. It does not invoke AWS,
attest Nitro hardware, execute a real browser, or validate the independent
custodian's signature. Passing it MUST NOT enable a commercial feature flag.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import re

IMAGE_DIGEST = "a" * 64
PCR17 = "b" * 96
POLICY_HASH = "c" * 64
RELEASE_ID = "d" * 32
OPERATOR = "111122223333"
CUSTODY = "444455556666"
REGION = "eu-central-1"
TENANTS = ("pilot01", "pilot02")

ATTACKS = (
    "operator_passrole", "kms_policy_mutation", "kms_creategrant",
    "image_digest_swap", "pcr_tamper", "release_replay",
    "release_expiry", "s3_version_swap", "wrong_tenant",
    "api_scope_bypass", "exfil_get", "exfil_post", "auto_submit",
)
FAULTS = ("timeout", "retry", "duplicate_sqs", "guest_crash")
SCENARIO_NAMES = tuple(f"{t}_preview" for t in TENANTS) + ATTACKS + FAULTS
_REJECTED = "DENIED"
_COMPLETED = "preview_completed"
_REVIEW = "needs_review"


@dataclass(frozen=True)
class SyntheticAttempt:
    tenant: str
    requested_tenant: str
    api_tenant: str
    kms_key: str
    task_role: str
    image_digest: str
    pcr17: str
    policy_hash: str
    release_id: str
    release_expires: datetime
    source_version: str
    requested_version: str
    http_method: str = "GET"
    origin: str = "https://forms.notarai.invalid"
    submit: bool = False
    operator_passrole: bool = False
    operator_can_mutate_key_policy: bool = False
    operator_can_create_grant: bool = False
    already_used_release: bool = False
    fault: str | None = None


def _key(tenant: str) -> str:
    return f"arn:aws:kms:{REGION}:{CUSTODY}:key/synthetic-{tenant}"


def _role(tenant: str) -> str:
    return f"arn:aws:iam::{OPERATOR}:role/notarai-confidential-{tenant}"


def make_attempt(tenant: str, now: datetime) -> SyntheticAttempt:
    if tenant not in TENANTS or now.tzinfo is None:
        raise ValueError("fictional tenant and aware clock required")
    return SyntheticAttempt(
        tenant=tenant, requested_tenant=tenant, api_tenant=tenant,
        kms_key=_key(tenant), task_role=_role(tenant),
        image_digest=IMAGE_DIGEST, pcr17=PCR17,
        policy_hash=POLICY_HASH, release_id=RELEASE_ID,
        release_expires=now + timedelta(minutes=30),
        source_version="synthetic-version-1",
        requested_version="synthetic-version-1",
    )


def synthetic_admission(attempt: SyntheticAttempt, *, now: datetime) -> str:
    """A policy *model*, not authoritative IAM/KMS/NSM enforcement."""
    if now.tzinfo is None or attempt.tenant not in TENANTS:
        return _REJECTED
    if any((attempt.requested_tenant != attempt.tenant,
            attempt.api_tenant != attempt.tenant,
            attempt.kms_key != _key(attempt.tenant),
            attempt.task_role != _role(attempt.tenant),
            attempt.image_digest != IMAGE_DIGEST,
            attempt.pcr17 != PCR17,
            attempt.policy_hash != POLICY_HASH,
            attempt.release_id != RELEASE_ID,
            attempt.source_version != attempt.requested_version,
            attempt.release_expires <= now,
            attempt.operator_passrole,
            attempt.operator_can_mutate_key_policy,
            attempt.operator_can_create_grant,
            attempt.already_used_release,
            attempt.submit,
            attempt.origin != "https://forms.notarai.invalid",
            attempt.http_method not in ("GET", "HEAD"),
           )):
        return _REJECTED
    if attempt.fault in FAULTS:
        return _REVIEW  # never retry an irreversible operation
    if attempt.fault is not None:
        return _REJECTED
    return _COMPLETED


def _attack(attempt: SyntheticAttempt, name: str, now: datetime) -> SyntheticAttempt:
    changes = {
        "operator_passrole": {"operator_passrole": True},
        "kms_policy_mutation": {"operator_can_mutate_key_policy": True},
        "kms_creategrant": {"operator_can_create_grant": True},
        "image_digest_swap": {"image_digest": "0" * 64},
        "pcr_tamper": {"pcr17": "0" * 96},
        "release_replay": {"already_used_release": True},
        "release_expiry": {"release_expires": now - timedelta(seconds=1)},
        "s3_version_swap": {"requested_version": "synthetic-version-2"},
        "wrong_tenant": {"requested_tenant": "pilot02"},
        "api_scope_bypass": {"api_tenant": "pilot02"},
        "exfil_get": {"origin": "https://attacker.invalid"},
        "exfil_post": {"http_method": "POST"},
        "auto_submit": {"submit": True},
    }
    if name not in ATTACKS:
        raise ValueError("unrecognized synthetic attack")
    return replace(attempt, **changes[name])


def offline_matrix(*, now: datetime | None = None) -> tuple[dict, ...]:
    """19 deterministic fake outcomes: 2 successful + 13 denied + 4 safe faults."""
    now = now or datetime(2026, 11, 22, tzinfo=timezone.utc)
    if now.tzinfo is None:
        raise ValueError("UTC clock required")
    rows = []
    for tenant in TENANTS:
        result = synthetic_admission(make_attempt(tenant, now), now=now)
        rows.append({"case": f"{tenant}_preview", "kind": "positive",
                     "outcome": result, "submitted": False, "source": "MOCK"})
    baseline = make_attempt("pilot01", now)
    for case in ATTACKS:
        result = synthetic_admission(_attack(baseline, case, now), now=now)
        rows.append({"case": case, "kind": "negative", "outcome": result,
                     "submitted": False, "source": "MOCK"})
    for case in FAULTS:
        result = synthetic_admission(replace(baseline, fault=case), now=now)
        rows.append({"case": case, "kind": "fault", "outcome": result,
                     "submitted": False, "source": "MOCK"})
    return tuple(rows)


def evaluate_gate(cases: tuple[dict, ...], *, custody_independent: bool = False,
                  hardware_evidence_verified: bool = False,
                  signed_evidence_verified: bool = False,
                  canary_hits: int | None = None) -> dict:
    """Never trust Boolean evidence from a caller as release authorization.

    The independent verifier (SEC-11) and live AWS tests (SEC-07) MUST be
    integrated with a real trusted evidence root before GO can be supported.
    No self-asserted booleans can ever flip commercial_go to True.
    """
    by_id = {item.get("case"): item for item in cases if isinstance(item, dict)}
    coverage = (len(cases) == len(SCENARIO_NAMES) and
                len(by_id) == len(SCENARIO_NAMES) and
                set(by_id) == set(SCENARIO_NAMES))
    expectations = {
        row: (_COMPLETED if row.endswith("_preview") else
              _REVIEW if row in FAULTS else _REJECTED)
        for row in SCENARIO_NAMES
    }
    mock_pass = coverage and all(
        by_id[name].get("outcome") == expected
        and by_id[name].get("submitted") is False
        and by_id[name].get("source") == "MOCK"
        for name, expected in expectations.items()
    )
    # These are untrusted assertions and cannot replace evidence signatures,
    # independently controlled WORM storage, Nitro NSM or actual CloudTrail.
    _ = (custody_independent, hardware_evidence_verified,
         signed_evidence_verified, canary_hits)
    return {
        "schema": "notarai.sec12.release-gate.v1",
        "scenario_count": len(SCENARIO_NAMES),
        "offline_matrix": "PASS" if mock_pass else "FAIL",
        "live_hardware": "BLOCKED",
        "independent_custody": "BLOCKED",
        "canary_scan": "BLOCKED",
        "signed_evidence": "BLOCKED",
        "commercial_go": False,
        "decision": "NO_GO",
    }
