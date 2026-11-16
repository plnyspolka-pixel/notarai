"""Versioned diagnostic routing for Claude/Codex, not a self-training model.

This module treats unsignable small benchmark observations as research signals.
It forbids feeding evaluated benchmark tasks to the LoRA training corpus.
"""
from __future__ import annotations

import json
from pathlib import Path

from tools.agent_factory.worker_pool import WorkerPolicyError

SOURCE = Path(__file__).resolve().parents[2] / (
    "docs/agent-factory-research/cpu-learning/second-2-family-observation.json"
)
ALLOWED = {
    "lead_escalation_or_new_unseen_tasks",
    "fresh_unseen_validation_not_training",
}


def next_learning_actions(path: Path = SOURCE) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 14000:
        raise WorkerPolicyError("diagnostic record not available")
    doc = json.loads(path.read_text(encoding="utf-8"))
    if (doc.get("schema_version") != 1
            or doc.get("kind") != "observed_cpu_targeted_followup"
            or doc.get("data_class") != "synthetic"
            or doc.get("evidence") != "local_docker_verifier_not_signed"
            or doc.get("training_eligible") is not False
            or doc.get("parent_observation_run") != 43928286658):
        raise WorkerPolicyError("diagnostic source schema or lineage not trusted")
    rows = doc.get("family_results")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 4:
        raise WorkerPolicyError("invalid diagnostic outcomes")
    seen = set()
    decisions = []
    for item in rows:
        if not isinstance(item, dict) or set(item) != {
            "task_id", "family", "contract_scaffold_passed",
            "targeted_lesson_passed", "next_route"
        }:
            raise WorkerPolicyError("invalid follow-up row")
        if (item["task_id"], item["family"]) not in {
            ("T01", "catalog"), ("T26", "scrub")
        } or item["task_id"] in seen or item["next_route"] not in ALLOWED:
            raise WorkerPolicyError("invalid diagnostic task or action")
        seen.add(item["task_id"])
        if item["next_route"] == "lead_escalation_or_new_unseen_tasks":
            if item["targeted_lesson_passed"] is not False:
                raise WorkerPolicyError("inconsistent failure escalation")
            decision = {
                "task_id": item["task_id"], "family": item["family"],
                "recommended_owner": "claude_or_codex_lead",
                "next_action": "redesign contract or use NEW unseen tasks; stop tuning same grader",
                "reason": "two instruction styles failed this public benchmark task"
            }
        else:
            if item["targeted_lesson_passed"] is not True:
                raise WorkerPolicyError("inconsistent validation route")
            decision = {
                "task_id": item["task_id"], "family": item["family"],
                "recommended_owner": "independent_evaluator",
                "next_action": "replicate on fresh never-used tests before accepting lesson",
                "reason": "one pass on a small public synthetic benchmark is not robust validation"
            }
        decisions.append(decision)
    return {
        "status": "OBSERVATIONAL_NOT_A_TRAINED_MODEL",
        "source_runs": [43928286658, 43930520281],
        "decisions": decisions,
        "tasks_to_retrain_on": [],
        "training_eligible": False,
        "important": (
            "Never train on these evaluated benchmark items or grader vectors. "
            "Collect novel accepted examples under separate human review and signature."
        )
    }
