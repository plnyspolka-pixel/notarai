"""Reproducible synthetic benchmark. No network calls by default."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.agent_factory.forge_core import ForgeError, RunStore, execute_offline
from tools.agent_factory.forge_llm import get_metrics

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "docs" / "agent-factory-research" / "fixtures"
DB = ROOT / ".agent-forge" / "runs.sqlite3"
SUITE = [
    ("sum", "sum-task.json", "sum-rubric.json"),
    ("count", "count-task.json", "count-rubric.json"),
    ("max", "max-task.json", "max-rubric.json"),
]


def benchmark_offline(store: RunStore, fixtures: Path, prefix: str) -> dict:
    if (not isinstance(prefix, str) or not prefix.isascii()
            or not 3 <= len(prefix) <= 30
            or not prefix.replace("-", "").replace("_", "").isalnum()):
        raise ForgeError("Invalid benchmark prefix")
    rows = []
    for label, task, rubric in SUITE:
        result = execute_offline(store, fixtures, prefix + "-" + label, task, rubric)
        rows.append({"task": label, "run_id": result["run_id"],
                     "passed": result["passed"], "replayed": result["replayed"],
                     "audit_valid": result["audit_valid"]})
    passed = sum(bool(x["passed"]) for x in rows)
    return {
        "suite": "synthetic-integers-3-v1",
        "adapter": "deterministic-fixture",
        "tasks": len(rows), "passed": passed, "success_rate": passed / len(rows),
        "actual_cost_pln": "0", "external_calls": 0, "runs": rows,
    }


def compare_runs(store: RunStore) -> dict:
    """Observational comparison; not an apples-to-apples model benchmark."""
    groups = {}
    for record in store.list_runs():
        adapter = record["adapter"]
        group = groups.setdefault(adapter, {
            "runs": 0, "evaluated": 0, "passed": 0,
            "latency_ms": [], "prompt_tokens": 0, "completion_tokens": 0,
            "unknown_pricing": False, "audit_failures": 0,
        })
        group["runs"] += 1
        if record["passed"] is not None:
            group["evaluated"] += 1
            group["passed"] += bool(record["passed"])
        if not store.verify_events(record["run_id"]):
            group["audit_failures"] += 1
        if adapter == "local-chat-completions":
            group["unknown_pricing"] = True
            metrics = get_metrics(store, record["run_id"])
            if metrics:
                group["latency_ms"].append(metrics["elapsed_ms"])
                group["prompt_tokens"] += metrics["prompt_tokens"] or 0
                group["completion_tokens"] += metrics["completion_tokens"] or 0
    return {
        "status": "observational, do not compare unlike datasets",
        "groups": {name: {
            "runs": item["runs"], "evaluated": item["evaluated"],
            "passed": item["passed"],
            "success_rate": item["passed"] / item["evaluated"] if item["evaluated"] else None,
            "average_latency_ms": round(sum(item["latency_ms"]) / len(item["latency_ms"]), 1)
                if item["latency_ms"] else None,
            "prompt_tokens": item["prompt_tokens"],
            "completion_tokens": item["completion_tokens"],
            "cost_pln": None if item["unknown_pricing"] else "0",
            "audit_failures": item["audit_failures"],
        } for name, item in groups.items()},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Agent Forge reproducible baseline")
    parser.add_argument("--state", type=Path, default=DB)
    parser.add_argument("--fixtures", type=Path, default=FIXTURES)
    parser.add_argument("--prefix", default="bench-offline")
    parser.add_argument("--compare", action="store_true")
    args = parser.parse_args(argv)
    try:
        with RunStore(args.state) as store:
            result = compare_runs(store) if args.compare else benchmark_offline(
                store, args.fixtures, args.prefix
            )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (ForgeError, OSError, ValueError, KeyError) as exc:
        print("BLOCKED: " + type(exc).__name__)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
