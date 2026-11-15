"""Evidence-aware paired evaluation for Agent Forge, entirely offline.

Not an LLM judge and not an approval system. This reports descriptive effect
sizes, task-cluster bootstrap intervals and an exact sign test. It cannot prove
causality if experiments were not randomized and pre-registered.
"""
from __future__ import annotations

from collections import defaultdict
import json
import math
from pathlib import Path
import random
import re
from typing import Any

from tools.agent_factory.forge_core import ForgeError

HEX = re.compile(r"^[a-f0-9]{64}$")
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,79}$")
RUN_FIELDS = {
    "task_id", "seed", "baseline_success", "candidate_success",
    "baseline_cost_cents", "candidate_cost_cents", "baseline_latency_ms",
    "candidate_latency_ms", "baseline_policy_violations",
    "candidate_policy_violations",
}
META_FIELDS = {
    "source", "split", "dataset_sha256", "evaluator_sha256",
    "baseline_id", "candidate_id",
}


def _strict_int(x: Any, max_value: int) -> bool:
    return type(x) is int and 0 <= x <= max_value


def validate_experiment(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(dataset, dict) or set(dataset) != {
        "schema_version", "provenance", "observations"
    } or type(dataset["schema_version"]) is not int or dataset["schema_version"] != 1:
        raise ForgeError("Invalid paired experiment schema")
    meta = dataset["provenance"]
    if not isinstance(meta, dict) or set(meta) != META_FIELDS:
        raise ForgeError("Provenance must be complete")
    if meta["source"] not in {"synthetic_demo", "measured"}:
        raise ForgeError("Unknown provenance source")
    if meta["split"] not in {"development", "holdout"}:
        raise ForgeError("Unknown evaluation split")
    for key in ("dataset_sha256", "evaluator_sha256"):
        if not isinstance(meta[key], str) or not HEX.fullmatch(meta[key]):
            raise ForgeError("Provenance requires SHA-256 digests")
    for key in ("baseline_id", "candidate_id"):
        if not isinstance(meta[key], str) or not IDENTIFIER.fullmatch(meta[key]):
            raise ForgeError("Invalid model or harness identifier")
    if meta["baseline_id"] == meta["candidate_id"]:
        raise ForgeError("Cannot compare the same version with itself")
    rows = dataset["observations"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= 1500:
        raise ForgeError("Expected 1-1500 paired observations")
    seen: set[tuple[str, int]] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != RUN_FIELDS:
            raise ForgeError("Missing or extra observation field")
        task_id = row["task_id"]
        if not isinstance(task_id, str) or not IDENTIFIER.fullmatch(task_id):
            raise ForgeError("Invalid task ID")
        if not _strict_int(row["seed"], 1_000_000):
            raise ForgeError("Invalid seed")
        key = (task_id, row["seed"])
        if key in seen:
            raise ForgeError("Duplicate task/seed pair")
        seen.add(key)
        for field in ("baseline_success", "candidate_success"):
            if type(row[field]) is not bool:
                raise ForgeError("Success flags must be booleans")
        for field in ("baseline_cost_cents", "candidate_cost_cents"):
            if not _strict_int(row[field], 100_000_000):
                raise ForgeError("Invalid measured cost")
        for field in ("baseline_latency_ms", "candidate_latency_ms"):
            if not _strict_int(row[field], 86_400_000):
                raise ForgeError("Invalid elapsed time")
        for field in ("baseline_policy_violations", "candidate_policy_violations"):
            if not _strict_int(row[field], 1_000):
                raise ForgeError("Invalid policy-violation count")
    return rows


def read_experiment(path: Path) -> dict[str, Any]:
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 500_000:
        raise ForgeError("Paired input must be an existing regular JSON file <=500 KB")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError, UnicodeError) as exc:
        raise ForgeError("Paired input cannot be decoded") from exc
    validate_experiment(data)
    return data


def exact_two_sided_sign_test(wins: int, losses: int) -> float:
    """Binomial test on INDEPENDENT TASK-level win/loss signs, excluding ties."""
    if not _strict_int(wins, 1500) or not _strict_int(losses, 1500):
        raise ForgeError("Invalid wins/losses")
    n = wins + losses
    if n == 0:
        return 1.0
    lower = min(wins, losses)
    numerator = sum(math.comb(n, k) for k in range(lower + 1))
    return min(1.0, 2.0 * (numerator / (2 ** n)))


def _percentile(sorted_values: list[float], quantile: float) -> float:
    index = (len(sorted_values) - 1) * quantile
    lower = int(math.floor(index))
    upper = int(math.ceil(index))
    return (sorted_values[lower] * (upper - index) +
            sorted_values[upper] * (index - lower)) if lower != upper else sorted_values[lower]


def bootstrap_task_delta(grouped: dict[str, list[dict]],
                         *, iterations: int = 2000, seed: int = 20261115) -> tuple[float, float]:
    """Percentile bootstrap resamples task clusters rather than correlated seeds."""
    if type(iterations) is not int or not 200 <= iterations <= 5000:
        raise ForgeError("Bootstrap iterations must be 200-5000")
    task_ids = sorted(grouped)
    if len(task_ids) < 2:
        return (-1.0, 1.0)
    rng = random.Random(seed)
    effects = []
    for _ in range(iterations):
        numerator = denominator = 0
        for _ in task_ids:
            group = grouped[task_ids[rng.randrange(len(task_ids))]]
            numerator += sum(int(r["candidate_success"]) -
                             int(r["baseline_success"]) for r in group)
            denominator += len(group)
        effects.append(numerator / denominator)
    effects.sort()
    return (_percentile(effects, 0.025), _percentile(effects, 0.975))


def compare_paired(dataset: dict[str, Any]) -> dict[str, Any]:
    rows = validate_experiment(dataset)
    meta = dataset["provenance"]
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["task_id"]].append(row)
    task_effects = [
        sum(int(row["candidate_success"]) - int(row["baseline_success"])
            for row in group) / len(group)
        for group in grouped.values()
    ]
    wins = sum(e > 0 for e in task_effects)
    losses = sum(e < 0 for e in task_effects)
    ties = len(task_effects) - wins - losses
    baseline_pass = sum(int(r["baseline_success"]) for r in rows)
    candidate_pass = sum(int(r["candidate_success"]) for r in rows)
    base_cost = sum(r["baseline_cost_cents"] for r in rows)
    candidate_cost = sum(r["candidate_cost_cents"] for r in rows)
    base_ms = sum(r["baseline_latency_ms"] for r in rows)
    candidate_ms = sum(r["candidate_latency_ms"] for r in rows)
    base_policy = sum(r["baseline_policy_violations"] for r in rows)
    candidate_policy = sum(r["candidate_policy_violations"] for r in rows)
    interval = bootstrap_task_delta(grouped)
    n = len(rows)
    counts_per_task = [len(g) for g in grouped.values()]
    exploratory = (
        meta["source"] != "measured" or meta["split"] != "holdout"
        or len(grouped) < 30 or min(counts_per_task) < 3
    )
    p_value = exact_two_sided_sign_test(wins, losses)
    # Never promote a variant on the basis of a statistics-only report.
    return {
        "analysis": "paired-task-cluster-v1",
        "provenance_source": meta["source"],
        "split": meta["split"],
        "baseline": meta["baseline_id"], "candidate": meta["candidate_id"],
        "dataset_sha256": meta["dataset_sha256"],
        "evaluator_sha256": meta["evaluator_sha256"],
        "task_clusters": len(grouped), "paired_observations": n,
        "min_seeds_per_task": min(counts_per_task),
        "baseline_success_rate": baseline_pass / n,
        "candidate_success_rate": candidate_pass / n,
        "absolute_success_delta": (candidate_pass - baseline_pass) / n,
        "cluster_bootstrap_95pct_interval": [round(v, 6) for v in interval],
        "task_level_wins": wins, "task_level_losses": losses,
        "task_level_ties": ties,
        "task_level_exact_sign_test_p": round(p_value, 8),
        "baseline_cost_cents": base_cost,
        "candidate_cost_cents": candidate_cost,
        "baseline_total_latency_ms": base_ms,
        "candidate_total_latency_ms": candidate_ms,
        "baseline_policy_violations": base_policy,
        "candidate_policy_violations": candidate_policy,
        "safety_regression": candidate_policy > base_policy,
        "interpretation": "exploratory_only" if exploratory else "requires_independent_review",
        "promotion_authorized": False,
        "limitations": [
            "Results are observational unless paired runs were randomized",
            "Task-cluster bootstrap is percentile, not BCa; small-N intervals are weak",
            "Task-level sign test ignores effect magnitudes and assumes task independence",
            "Multiple-hypothesis correction is required for candidate selection",
            "Cost values are supplied by dataset and are not vendor-billing verified",
            "No claim about validity of hidden evaluator or dataset contamination",
        ],
    }
