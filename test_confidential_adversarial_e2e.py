"""SEC-12: synthetic adversarial matrix, never actual AWS proof."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from confidential.adversarial_gate import (
    ATTACKS, FAULTS, TENANTS, SCENARIO_NAMES,
    _attack, evaluate_gate, make_attempt, offline_matrix,
    synthetic_admission,
)


NOW = datetime(2026, 11, 22, 8, tzinfo=timezone.utc)


def test_two_positive_tenants_use_isolated_kms_keys_roles_no_submit():
    one, two = (make_attempt(t, NOW) for t in TENANTS)
    assert one.kms_key != two.kms_key
    assert one.task_role != two.task_role
    assert one.image_digest == two.image_digest
    assert synthetic_admission(one, now=NOW) == "preview_completed"
    assert synthetic_admission(two, now=NOW) == "preview_completed"
    assert one.submit is False and two.submit is False


@pytest.mark.parametrize("attack", ATTACKS)
def test_thirteen_operator_attacks_rejected(attack):
    baseline = make_attempt("pilot01", NOW)
    modified = _attack(baseline, attack, NOW)
    assert modified != baseline
    assert synthetic_admission(modified, now=NOW) == "DENIED"


@pytest.mark.parametrize("fault", FAULTS)
def test_four_fault_injections_never_submit_or_lose_scope(fault):
    attempt = replace(make_attempt("pilot01", NOW), fault=fault)
    assert synthetic_admission(attempt, now=NOW) == "needs_review"
    assert attempt.submit is False
    assert synthetic_admission(replace(attempt, submit=True), now=NOW) == "DENIED"


def test_matrix_complete_and_mock_is_explicit():
    rows = offline_matrix(now=NOW)
    assert len(rows) == 2 + len(ATTACKS) + len(FAULTS) == 19
    assert len(set(x["case"] for x in rows)) == len(SCENARIO_NAMES)
    assert all(x["source"] == "MOCK" and not x["submitted"] for x in rows)
    assert evaluate_gate(rows)["offline_matrix"] == "PASS"


def test_untrusted_live_flags_never_authorize_commercial_deployment():
    rows = offline_matrix(now=NOW)
    result = evaluate_gate(rows, custody_independent=True,
        hardware_evidence_verified=True, signed_evidence_verified=True,
        canary_hits=0)
    assert result["decision"] == "NO_GO" and result["commercial_go"] is False
    assert result["live_hardware"] == "BLOCKED"
    assert result["signed_evidence"] == "BLOCKED"


@pytest.mark.parametrize("case", SCENARIO_NAMES)
def test_missing_each_required_case_prevents_even_offline_pass(case):
    rows = tuple(x for x in offline_matrix(now=NOW) if x["case"] != case)
    assert evaluate_gate(rows)["offline_matrix"] == "FAIL"
    assert evaluate_gate(rows)["commercial_go"] is False


@pytest.mark.parametrize("attack", ATTACKS)
def test_forged_negative_pass_or_submission_rejected(attack):
    rows = list(offline_matrix(now=NOW))
    pos = next(i for i, row in enumerate(rows) if row["case"] == attack)
    rows[pos] = {**rows[pos], "outcome": "preview_completed", "submitted": True}
    assert evaluate_gate(tuple(rows))["offline_matrix"] == "FAIL"


def test_duplicate_or_changed_source_is_not_admitted():
    rows = list(offline_matrix(now=NOW))
    rows.append(dict(rows[0]))
    assert evaluate_gate(tuple(rows))["offline_matrix"] == "FAIL" or (
        evaluate_gate(tuple(rows))["commercial_go"] is False
    )
    rows = list(offline_matrix(now=NOW))
    rows[0] = {**rows[0], "source": "AWS"}
    assert evaluate_gate(tuple(rows))["offline_matrix"] == "FAIL"
