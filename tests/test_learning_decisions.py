"""Evidence routing: weak tasks escalate, single wins need new holdout."""
import json
import pytest

from tools.agent_factory.learning_decisions import next_learning_actions
from tools.agent_factory.worker_pool import WorkerPolicyError


def test_diagnostic_routes_to_appropriate_next_owner():
    p = next_learning_actions()
    assert p["training_eligible"] is False
    assert p["tasks_to_retrain_on"] == []
    by_id = {x["task_id"]: x for x in p["decisions"]}
    assert by_id["T01"]["recommended_owner"] == "claude_or_codex_lead"
    assert by_id["T26"]["recommended_owner"] == "independent_evaluator"


def test_refuses_promoting_observed_benchmark_into_train_examples(tmp_path):
    from tools.agent_factory.learning_decisions import SOURCE
    doc = json.loads(SOURCE.read_text())
    doc["training_eligible"] = True
    p = tmp_path / "forged.json"
    p.write_text(json.dumps(doc))
    with pytest.raises(WorkerPolicyError):
        next_learning_actions(p)
