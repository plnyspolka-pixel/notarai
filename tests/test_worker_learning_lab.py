"""Offline tests: learning plan never claims trained weights or trusted outcomes."""
import pytest
from tools.agent_factory.worker_learning_lab import (
    FIRST_TASK_IDS, ARMS, failure_category, job_packet, summarize, task_specs,
)
from tools.agent_factory.worker_pool import WorkerPolicyError


def test_six_distinct_synthetic_families_without_grader_or_secrets():
    tasks = task_specs()
    assert [t["id"] for t in tasks] == list(FIRST_TASK_IDS)
    assert len({t["chain"] for t in tasks}) == 6
    for task in tasks:
        for arm in ARMS:
            p = job_packet(task, arm)
            assert p["data_class"] == "synthetic"
            assert p["role"] == "implementer"
            assert "cases.json" not in p["context"]
            assert "expected" not in p["context"].lower()


def test_learning_task_rejects_unknown_or_sensitive_orchestration_arms():
    with pytest.raises(WorkerPolicyError):
        job_packet(task_specs()[0], "run-as-admin")


def test_failure_category_distinguishes_format_and_semantics():
    assert failure_category({"passed": True}) == "accepted_by_local_sandbox_tests"
    assert failure_category({"passed": False, "status": "rejected_low_quality"}) == "format_or_completeness"
    assert failure_category({"passed": False, "passed_tests": 1, "status": "proposed_unverified"}) == "partial_requirements_or_edge_cases"
    assert failure_category({"passed": False, "status": "transport_failed"}) == "infrastructure_or_protocol"


def test_curriculum_is_always_diagnostic_not_training_evidence():
    rows = []
    for arm in ARMS:
        for task in task_specs():
            rows.append({
                "arm": arm, "task_id": task["id"],
                "passed": arm == ARMS[1], "passed_tests": int(arm == ARMS[1]),
                "tests": 2, "status": "proposed_unverified",
                "wall_time_s": 1.1, "prompt_tokens": 40, "completion_tokens": 20
            })
    out = summarize(rows, "test-model")
    assert out["by_arm"][ARMS[0]]["accepted"] == 0
    assert out["by_arm"][ARMS[1]]["accepted"] == 6
    assert out["training_data_eligible"] is False
    assert len(out["curriculum"]) == 6
    with pytest.raises(ValueError):
        summarize(rows[:-1], "test-model")
