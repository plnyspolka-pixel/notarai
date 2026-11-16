"""Second-round CPU lessons selected from observed failed synthetic families.

The learner changes only PUBLIC work-package instructions; it never exposes
grader fixtures or imports generated code outside the independent Docker worker.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

from tools.agent_factory.benchmark30 import prepare
from tools.agent_factory.benchmark30_cpu_pilot import extract_python
from tools.agent_factory.benchmark30_docker import grade
from tools.agent_factory.worker_learning_lab import job_packet, task_specs
from tools.agent_factory.worker_pool import (
    OPT_IN, OPT_VALUE, SECRET, WorkerPolicyError,
    _generate, endpoint_config, validate_job,
)

REFERENCE = Path(__file__).resolve().parents[2] / (
    "docs/agent-factory-research/cpu-learning/initial-6-family-observation.json"
)
HINTS = {
    "catalog": (
        "Teacher hint derived from the public specification, NOT grading cases: "
        "For this first stage keep every valid row (do not deduplicate). "
        "Convert its id into a string; normalize name consistently for "
        "alphabetical order; return an actual list of dictionaries with "
        "both fields, not a dict keyed by id. Do not mutate the input."
    ),
    "scrub": (
        "Teacher hint derived from the public specification, NOT grading cases: "
        "Replace just the sensitive matching substring, never the surrounding "
        "ordinary sentence. Consider a regular-expression replacement that "
        "recognizes the 'sk-' credential prefix followed by an alphanumeric "
        "token body, and preserve punctuation and spaces outside it. "
        "Return the required exact redaction marker."
    ),
}
ARMS = ("contract_scaffold", "targeted_lesson")


def read_observed_weak_families(path: Path = REFERENCE) -> list[dict]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 15000:
        raise WorkerPolicyError("missing bounded prior study provenance")
    doc = json.loads(path.read_text(encoding="utf-8"))
    if (doc.get("schema_version") != 1 or doc.get("kind") != "observed_cpu_method_ab"
            or doc.get("data_class") != "synthetic"
            or doc.get("training_eligible") is not False
            or doc.get("evidence") != "local_docker_verifier_not_signed"):
        raise WorkerPolicyError("prior record not eligible as diagnostic input")
    failures = doc.get("weak_families")
    if not isinstance(failures, list) or not 1 <= len(failures) <= 4:
        raise WorkerPolicyError("invalid number of lessons")
    known = {t["id"]: t for t in task_specs()}
    seen = set()
    out = []
    for f in failures:
        if not isinstance(f, dict) or set(f) != {
            "task_id", "family", "plain_passed", "scaffold_passed", "weakness"
        }:
            raise WorkerPolicyError("invalid lesson evidence fields")
        task = known.get(f["task_id"])
        if (task is None or task["chain"] != f["family"]
                or f["family"] not in HINTS or f["task_id"] in seen
                or f["scaffold_passed"] is not False):
            raise WorkerPolicyError("unexpected or already resolved lesson")
        seen.add(f["task_id"])
        out.append(task)
    return out


def targeted_packet(task: dict, arm: str) -> dict:
    if arm not in ARMS:
        raise WorkerPolicyError("unknown intervention")
    initial = job_packet(task, "contract_scaffold")
    if arm == "targeted_lesson":
        initial["context"] += "\n\n" + HINTS[task["chain"]]
    return validate_job(initial)


def run(*, image: str, output: Path) -> dict:
    if (os.environ.get("GITHUB_ACTIONS") != "true"
            or os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted"
            or os.environ.get(OPT_IN) != OPT_VALUE
            or os.environ.get("AGENT_BENCH30_ISOLATED_VM_APPROVED")
                != "SYNTHETIC_DISPOSABLE_VM_ONLY"):
        raise WorkerPolicyError("CI disposable VM + model and grader opt-ins required")
    port, model, _ = endpoint_config()
    tasks = read_observed_weak_families()
    output = Path(output).expanduser().resolve()
    if output.exists():
        raise WorkerPolicyError("refusing overwrite")
    output.mkdir(parents=True, mode=0o700)
    rows, review = [], []
    t0 = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="lesson-followup-", dir=os.environ["RUNNER_TEMP"]) as tmp:
        for arm in ARMS:
            workspace = Path(tmp) / arm
            prepare(workspace)
            for task in tasks:
                payload = targeted_packet(task, arm)
                started = time.monotonic()
                response = _generate(payload, port, model, 95)
                outcome = {"status": response.get("status"), "passed": False,
                           "passed_ids": [], "tests": 0}
                candidate = None
                if response.get("status") == "proposed_unverified":
                    try:
                        candidate = extract_python(response["content"])
                        if SECRET.search(candidate):
                            raise WorkerPolicyError("unsafe model result")
                        (workspace / task["path"]).write_text(candidate, encoding="utf-8")
                        outcome = grade(
                            workspace=workspace, chain=task["chain"], upto=1, image=image
                        )
                    except (ValueError, OSError, SyntaxError, WorkerPolicyError):
                        outcome = {"status": "invalid_source", "passed": False,
                                   "passed_ids": [], "tests": 0}
                success = outcome.get("passed") is True
                if success and candidate:
                    review_dir = output / "pending_review"
                    review_dir.mkdir(exist_ok=True, mode=0o700)
                    name = task["id"] + "-" + arm + ".py"
                    file = review_dir / name
                    file.write_text(candidate, encoding="utf-8")
                    os.chmod(file, 0o600)
                    review.append({
                        "task_id": task["id"], "family": task["chain"], "arm": arm,
                        "source": "pending_review/" + name,
                        "sha256": hashlib.sha256(candidate.encode()).hexdigest(),
                        "local_tests_passed": True,
                        "human_approved": False, "signed": False,
                        "training_eligible": False
                    })
                rows.append({
                    "arm": arm, "task_id": task["id"], "family": task["chain"],
                    "passed": success,
                    "passed_tests": len(outcome.get("passed_ids", [])),
                    "tests": outcome.get("tests") or 0,
                    "status": outcome.get("status"),
                    "wall_time_s": round(time.monotonic() - started, 2),
                    "prompt_tokens": response.get("usage", {}).get("prompt_tokens"),
                    "completion_tokens": response.get("usage", {}).get("completion_tokens"),
                })
                print(json.dumps({
                    "arm": arm, "task": task["id"], "passed": success,
                    "checks": f"{rows[-1]['passed_tests']}/{rows[-1]['tests']}"
                }), flush=True)
    summary = {
        "status": "ACTUAL_MODEL_FOLLOWUP_DIAGNOSTIC_NOT_TRAINING",
        "model": model,
        "source_diagnostic_run": 43928286658,
        "task_ids": [t["id"] for t in tasks],
        "arms": {},
        "rows": rows, "pending_review": review,
        "verification": "local sandbox Docker; not signed",
        "same_model_and_test_set": True,
        "not_training_eligible": True,
        "wall_time_s": round(time.monotonic()-t0, 2),
        "gpu_calls": 0, "premium_model_calls": 0,
        "runner_commit": os.environ.get("GITHUB_SHA"),
    }
    for arm in ARMS:
        vals = [r for r in rows if r["arm"] == arm]
        summary["arms"][arm] = {
            "tasks": len(vals), "accepted": sum(r["passed"] for r in vals),
            "test_cases_passed": sum(r["passed_tests"] for r in vals),
            "test_cases_total": sum(r["tests"] for r in vals),
            "seconds": round(sum(r["wall_time_s"] for r in vals), 2),
        }
    (output / "lesson-followup.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps({"status": summary["status"], "arms": summary["arms"]}))
    return summary


def main() -> int:
    cli = argparse.ArgumentParser()
    cli.add_argument("--image", required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    try:
        run(image=args.image, output=args.output)
        return 0
    except (WorkerPolicyError, ValueError, TypeError, OSError, KeyError) as exc:
        print("BLOCKED", type(exc).__name__)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
