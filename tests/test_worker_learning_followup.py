"""Unit tests for adaptive lessons, without model inference."""
import json
import pytest
from tools.agent_factory.worker_learning_followup import (
    HINTS, read_observed_weak_families, targeted_packet,
)
from tools.agent_factory.worker_pool import WorkerPolicyError


def test_picks_only_previous_unresolved_lessons_from_distinct_families():
    tasks = read_observed_weak_families()
    assert [(t["id"], t["chain"]) for t in tasks] == [
        ("T01", "catalog"), ("T26", "scrub")
    ]


def test_targeted_prompts_are_distinct_and_not_hidden_test_vectors():
    for t in read_observed_weak_families():
        a = targeted_packet(t, "contract_scaffold")
        b = targeted_packet(t, "targeted_lesson")
        assert a["instruction"] == b["instruction"]
        assert a["context"] != b["context"]
        assert HINTS[t["chain"]] in b["context"]
        assert "cases.json" not in b["context"]


def test_refuses_forged_diagnostic_that_claims_trainable(tmp_path):
    raw = json.loads(
        __import__("pathlib").Path(
            "docs/agent-factory-research/cpu-learning/initial-6-family-observation.json"
        ).read_text()
    )
    raw["training_eligible"] = True
    p = tmp_path / "report.json"
    p.write_text(json.dumps(raw))
    with pytest.raises(WorkerPolicyError):
        read_observed_weak_families(p)


def test_refuses_resolved_task_in_prior_study(tmp_path):
    raw = json.loads(
        __import__("pathlib").Path(
            "docs/agent-factory-research/cpu-learning/initial-6-family-observation.json"
        ).read_text()
    )
    raw["weak_families"][0]["scaffold_passed"] = True
    p = tmp_path / "report.json"
    p.write_text(json.dumps(raw))
    with pytest.raises(WorkerPolicyError):
        read_observed_weak_families(p)
