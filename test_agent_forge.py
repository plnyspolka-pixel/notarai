"""Offline integration and security regression tests for Agent Forge."""
import json
from pathlib import Path
import sqlite3

import pytest

from tools.agent_factory.forge_core import (
    ForgeError, RunPolicy, RunStore, audit_catalog, canonical, digest,
    execute_offline, fixture_adapter, independent_evaluate, read_fixture,
    validate_rubric, validate_task,
)
from tools.agent_factory.forge_cli import main


def fixture_pair(tmp_path: Path, values=None, answer=10):
    root = tmp_path / "fixtures"
    root.mkdir(exist_ok=True)
    task = {
        "schema_version": 1, "classification": "synthetic",
        "task_id": "sum-fixture-001", "operation": "sum_integers",
        "values": [7, -2, 5] if values is None else values,
    }
    rubric = {
        "schema_version": 1, "task_id": task["task_id"],
        "task_sha256": digest(task),
        "assertions": [{"path": "answer", "operator": "equals", "expected": answer}],
    }
    (root / "task.json").write_text(canonical(task), encoding="utf-8")
    (root / "rubric.json").write_text(canonical(rubric), encoding="utf-8")
    return root, task, rubric


def test_complete_offline_run_and_no_secret_payloads(tmp_path):
    root, task, _ = fixture_pair(tmp_path)
    with RunStore(tmp_path / "state" / "runs.sqlite3") as store:
        outcome = execute_offline(store, root, "fixture-run-001", "task.json", "rubric.json")
        assert outcome["passed"] is True and outcome["audit_valid"]
        assert outcome["external_model_calls"] == 0
        assert outcome["external_gpu_calls"] == 0
        assert outcome["actual_cost_pln"] == "0"
        assert store.get("fixture-run-001")["state"] == "completed"
        assert "values" not in canonical(store.get("fixture-run-001"))
        assert "10" not in canonical(outcome["failed_paths"])


def test_idempotent_replay_never_runs_twice(tmp_path):
    root, _, _ = fixture_pair(tmp_path)
    with RunStore(tmp_path / "runs.sqlite3") as store:
        first = execute_offline(store, root, "fixture-run-002", "task.json", "rubric.json")
        second = execute_offline(store, root, "fixture-run-002", "task.json", "rubric.json")
        assert not first["replayed"] and second["replayed"]
        assert store.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 3


def test_idempotency_conflict_detected(tmp_path):
    root, _, _ = fixture_pair(tmp_path)
    with RunStore(tmp_path / "runs.sqlite3") as store:
        execute_offline(store, root, "fixture-run-003", "task.json", "rubric.json")
        root, _, _ = fixture_pair(tmp_path, values=[4, 6])
        with pytest.raises(ForgeError, match="different inputs"):
            execute_offline(store, root, "fixture-run-003", "task.json", "rubric.json")


def test_bad_expected_answer_is_failed_not_silent_success(tmp_path):
    root, _, _ = fixture_pair(tmp_path, answer=99)
    with RunStore(tmp_path / "runs.sqlite3") as store:
        outcome = execute_offline(store, root, "fixture-run-004", "task.json", "rubric.json")
        assert outcome["passed"] is False
        assert outcome["state"] == "failed"
        assert outcome["failed_paths"] == ["answer"]


@pytest.mark.parametrize("policy", [
    RunPolicy(adapter="external-script"),
    RunPolicy(region="us-east-1"),
    RunPolicy(budget_pln="0.01"),
    RunPolicy(classification="private"),
])
def test_external_or_paid_execution_denied(policy):
    with pytest.raises(ForgeError):
        policy.validate()


@pytest.mark.parametrize("values", [
    [True], [2.1], ["3"], [], list(range(129)), [1000001],
])
def test_non_numeric_or_large_dataset_rejected(values):
    task = {"schema_version": 1, "classification": "synthetic",
            "task_id": "task-001", "operation": "sum_integers", "values": values}
    with pytest.raises(ForgeError):
        validate_task(task)


def test_unknown_task_operations_cannot_execute_code():
    task = {"schema_version": 1, "classification": "synthetic",
            "task_id": "task-001", "operation": "__import__('os').system('id')",
            "values": [1]}
    with pytest.raises(ForgeError):
        fixture_adapter(task)


def test_rubric_hash_rejects_tampering(tmp_path):
    _, task, rubric = fixture_pair(tmp_path)
    task["values"] = [11]
    with pytest.raises(ForgeError, match="integrity"):
        validate_rubric(rubric, task)


def test_rubric_disallows_evaluable_code(tmp_path):
    _, task, rubric = fixture_pair(tmp_path)
    rubric["assertions"][0]["operator"] = "python-eval"
    with pytest.raises(ForgeError, match="fixed output"):
        validate_rubric(rubric, task)


@pytest.mark.parametrize("name", ["../secret.json", "/tmp/secret.json", ".env", "other.txt",
                                  "folder/task.json", "a.json?token=abc"])
def test_path_traversal_and_unexpected_paths_denied(tmp_path, name):
    tmp_path.mkdir(exist_ok=True)
    with pytest.raises(ForgeError):
        read_fixture(tmp_path, name)


def test_symlink_fixture_rejected(tmp_path):
    root, _, _ = fixture_pair(tmp_path)
    (root / "link.json").symlink_to(root / "task.json")
    with pytest.raises(ForgeError, match="symlink"):
        read_fixture(root, "link.json")


def test_event_hash_chain_detects_tampering(tmp_path):
    root, _, _ = fixture_pair(tmp_path)
    with RunStore(tmp_path / "runs.sqlite3") as store:
        execute_offline(store, root, "fixture-run-005", "task.json", "rubric.json")
        assert store.verify_events("fixture-run-005")
        with store.conn:
            store.conn.execute(
                "UPDATE events SET meta_json='{\"malicious\":true}' "
                "WHERE seq=(SELECT MIN(seq) FROM events)"
            )
        assert not store.verify_events("fixture-run-005")


def test_invalid_state_transitions_blocked(tmp_path):
    with RunStore(tmp_path / "runs.sqlite3") as store:
        with pytest.raises(ForgeError):
            store.transition("unknown-run", "completed")
        manifest = {"run_id": "fixture-run-006", "experiment_id": "EXP-01",
                    "task_id": "t", "task_hash": "a" * 64,
                    "rubric_hash": "b" * 64, "adapter": "deterministic-fixture"}
        assert store.register(manifest)
        with pytest.raises(ForgeError):
            store.transition("fixture-run-006", "completed")


def test_canonical_hash_stable():
    assert digest({"a": 1, "b": 2}) == digest({"b": 2, "a": 1})


def test_actual_catalog_structure():
    root = Path(__file__).resolve().parent
    result = audit_catalog(root / "docs" / "agent-factory-research" / "catalog.json")
    assert result["valid"] and result["count"] >= 50


def test_cli_demo_report_and_replay(tmp_path, capsys):
    root, _, _ = fixture_pair(tmp_path)
    db = tmp_path / "database.sqlite3"
    args = ["demo", "--run-id", "fixture-cli-001", "--state", str(db),
            "--fixtures", str(root), "--task", "task.json", "--rubric", "rubric.json"]
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out)["passed"] is True
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out)["replayed"] is True
    assert main(["report", "--state", str(db)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert len(report["runs"]) == 1 and report["all_audits_valid"] is True


def test_cli_prohibits_model_worker(tmp_path):
    root, _, _ = fixture_pair(tmp_path)
    with RunStore(tmp_path / "state.sqlite3") as store:
        with pytest.raises(ForgeError):
            execute_offline(store, root, "fixture-run-007", "task.json", "rubric.json",
                            RunPolicy(adapter="codex-vllm"))

def test_malformed_json_types_are_rejected():
    task = {"schema_version": 1, "classification": "synthetic",
            "task_id": "task-001", "operation": ["sum_integers"], "values": [1]}
    with pytest.raises(ForgeError):
        validate_task(task)
    task["operation"] = "sum_integers"
    task["schema_version"] = True
    with pytest.raises(ForgeError):
        validate_task(task)
