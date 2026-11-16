"""Thirty-task synthetic coding benchmark, offline orchestration and checks.

This tool NEVER executes agent-written Python. Worktrees contain synthetic stubs.
Scoring agent code requires an external, restricted verification worker and
attested measurements; this module only verifies reference data and prepares tasks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs/agent-factory-research/benchmark30/tasks.json"
CASES = ROOT / "docs/agent-factory-research/benchmark30/cases.json"
CHAINS = ("catalog", "permissions", "slots", "deps", "ledger", "scrub")
ENTRY = {
    "catalog": "normalize_catalog(rows)",
    "permissions": "decide(request)",
    "slots": "slots(request)",
    "deps": "affected(request)",
    "ledger": "reduce_events(events)",
    "scrub": "scrub(text)",
}
SOURCE_STUB = {
    "catalog": 'def normalize_catalog(rows):\n    """Return normalized [{"id":..., "name":...}] items."""\n    raise NotImplementedError\n',
    "permissions": 'def decide(request):\n    """Evaluate a synthetic authorization request, returning bool."""\n    raise NotImplementedError\n',
    "slots": 'def slots(request):\n    """Return integer slot starts in the supplied time window."""\n    raise NotImplementedError\n',
    "deps": 'def affected(request):\n    """Return affected modules, sorted in ascending order."""\n    raise NotImplementedError\n',
    "ledger": 'def reduce_events(events):\n    """Return a dictionary of live keys after event replay."""\n    raise NotImplementedError\n',
    "scrub": 'def scrub(text):\n    """Redact synthetic identifiers from a text string."""\n    raise NotImplementedError\n',
}


class BenchmarkError(ValueError):
    pass


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def read_json(path: Path) -> object:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 512_000:
        raise BenchmarkError("missing, oversized or symlinked benchmark file")
    return json.loads(path.read_text(encoding="utf-8"))


def validate(manifest_path: Path = MANIFEST, cases_path: Path = CASES) -> dict:
    manifest = read_json(manifest_path)
    cases = read_json(cases_path)
    if not isinstance(manifest, dict) or not isinstance(cases, dict):
        raise BenchmarkError("manifest/cases must be objects")
    tasks = manifest.get("tasks")
    tests = cases.get("tests")
    if manifest.get("schema_version") != 1 or manifest.get("classification") != "synthetic" or not isinstance(tasks, list) or len(tasks) != 30:
        raise BenchmarkError("expected exactly thirty synthetic tasks")
    if cases.get("schema_version") != 1 or not isinstance(tests, list) or len(tests) < 60:
        raise BenchmarkError("missing test vectors")
    task_ids, case_ids, stages = set(), set(), {c: set() for c in CHAINS}
    for item in tasks:
        if not isinstance(item, dict):
            raise BenchmarkError("task must be object")
        task_id, chain, stage = item.get("id"), item.get("chain"), item.get("step")
        if not isinstance(task_id, str) or not re.fullmatch(r"T(0[1-9]|[12][0-9]|30)", task_id) or task_id in task_ids:
            raise BenchmarkError("duplicate or invalid task ID")
        if chain not in CHAINS or type(stage) is not int or not 1 <= stage <= 5 or stage in stages[chain]:
            raise BenchmarkError("chain stage missing or duplicate")
        if (item.get("entrypoint") != ENTRY[chain] or item.get("path") != f"{chain}/solution.py"
                or not isinstance(item.get("request"), str) or len(item["request"]) < 50):
            raise BenchmarkError("invalid task specification")
        if not isinstance(item.get("acceptance"), list) or not item["acceptance"]:
            raise BenchmarkError("no acceptance criteria")
        if not isinstance(item.get("research"), list) or not item["research"]:
            raise BenchmarkError("missing research anchors")
        task_ids.add(task_id)
        stages[chain].add(stage)
    if any(vals != {1, 2, 3, 4, 5} for vals in stages.values()):
        raise BenchmarkError("all chains require steps 1..5")
    stage_counts = {(chain, step): 0 for chain in CHAINS for step in range(1, 6)}
    for case in tests:
        if not isinstance(case, dict) or case.get("chain") not in CHAINS or type(case.get("step")) is not int:
            raise BenchmarkError("invalid case")
        chain, step = case["chain"], case["step"]
        if (chain, step) not in stage_counts or not isinstance(case.get("id"), str) or case["id"] in case_ids:
            raise BenchmarkError("case id or stage invalid")
        if "args" not in case or not isinstance(case["args"], list) or len(case["args"]) != 1 or "expected" not in case:
            raise BenchmarkError("cases require one argument and expected output")
        case_ids.add(case["id"])
        stage_counts[(chain, step)] += 1
    if min(stage_counts.values()) < 2:
        raise BenchmarkError("every task requires >=2 independently specified cases")
    return {"status": "validated-offline", "tasks": len(tasks), "chains": len(CHAINS), "cases": len(tests),
            "manifest_sha256": digest(manifest), "cases_sha256": digest(cases), "model_calls": 0,
            "warning": "Not an LLM evaluation; case expectations were checked separately against a trusted oracle."}


def prepare(output: Path, manifest_path: Path = MANIFEST) -> dict:
    """Create 6 writable starter projects, never touching an existing output."""
    validate(manifest_path, CASES)
    output = output.expanduser().resolve()
    if output.exists():
        raise BenchmarkError("output already exists; refusing overwrite")
    if output == ROOT or ROOT in output.parents:
        raise BenchmarkError("do not create agent worktrees inside source repository")
    output.mkdir(parents=True)
    for chain in CHAINS:
        directory = output / chain
        directory.mkdir()
        (directory / "solution.py").write_text(SOURCE_STUB[chain], encoding="utf-8")
        (directory / "README.md").write_text(
            f"# Synthetic task chain: {chain}\n\nImplement `{ENTRY[chain]}` in `solution.py`. "
            "Use only synthetic data. Complete tasks T01-T30 in chain order. "
            "The tests and grader are managed outside this worktree. "
            "No external API, credentials, deploy, cloud, or production data.\n", encoding="utf-8")
    return {"status": "prepared", "root": str(output), "chains": list(CHAINS), "model_calls": 0}


def spec(task_id: str, manifest_path: Path = MANIFEST) -> dict:
    manifest = read_json(manifest_path)
    for task in manifest["tasks"]:
        if task["id"] == task_id:
            # Include only published acceptance statements, not private case vectors.
            return {"task": task, "instructions": "Edit only chain/solution.py; preserve all earlier stages. No network, secrets, production or bypass of tests."}
    raise BenchmarkError("unknown task")


def plan(manifest_path: Path = MANIFEST) -> dict:
    manifest = read_json(manifest_path)
    rows = [{"id": t["id"], "chain": t["chain"], "step": t["step"], "entrypoint": t["entrypoint"]} for t in manifest["tasks"]]
    return {"tasks": rows, "runs_per_model": 30, "recommended_variants": [
        "baseline-terminal", "indexed-context", "independent-tests", "memory-gated", "independent-review"],
        "experiment_policy": "Identical model/version, prompts, budgets, pinned base, tests. Replay all previous tests each step.",
        "requires": "isolated code worker, independently stored verifier, model authorization, cost accounting",
        "does_not_run_models": True}


def summarize(results_path: Path, manifest_path: Path = MANIFEST) -> dict:
    """Conservative report: refuse to credit results without verifier attestation."""
    tasks = read_json(manifest_path)["tasks"]
    doc = read_json(results_path)
    if not isinstance(doc, dict) or not isinstance(doc.get("results"), list):
        raise BenchmarkError("invalid results envelope")
    rows = doc["results"]
    if len(rows) != 30 or {row.get("task_id") for row in rows if isinstance(row, dict)} != {t["id"] for t in tasks}:
        raise BenchmarkError("require thirty task results")
    if any(row.get("verified_by") != "external-isolated-runner" or not row.get("attestation_sha256") or type(row.get("passed")) is not bool for row in rows):
        raise BenchmarkError("cannot report pass rate from unattested or fabricated outcomes")
    # Attestations are NOT validated here: no trusted public key or external identity.
    # Therefore report is deliberately provisional and unverified.
    return {"tasks": 30, "reported_passed": sum(int(row["passed"]) for row in rows),
            "status": "UNVERIFIED - requires authenticated verifier attestation validation",
            "cannot_authorize_merge_or_deploy": True}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark30: synthetic plans; no model execution")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate")
    sub.add_parser("plan")
    prep = sub.add_parser("prepare"); prep.add_argument("--output", type=Path, required=True)
    task = sub.add_parser("spec"); task.add_argument("task_id")
    report = sub.add_parser("report"); report.add_argument("results", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.cmd == "validate": result = validate()
        elif args.cmd == "plan": result = plan()
        elif args.cmd == "prepare": result = prepare(args.output)
        elif args.cmd == "spec": result = spec(args.task_id)
        elif args.cmd == "report": result = summarize(args.results)
        else: raise BenchmarkError("unknown command")
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (BenchmarkError, ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"error": type(exc).__name__}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
