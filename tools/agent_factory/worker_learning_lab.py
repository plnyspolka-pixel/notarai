"""CPU worker-learning lab: paired prompts, independent grader, lesson planner.

Actual model calls happen only on an operator-approved, disposable CI worker.
The experiments compare DELEGATION METHODS on the SAME model and SAME
synthetic benchmark tasks. They neither train weights nor run Claude.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

from tools.agent_factory.benchmark30 import (
    MANIFEST, read_json, prepare, validate,
)
from tools.agent_factory.benchmark30_cpu_pilot import (
    PUBLIC_INPUT_CONTRACTS, extract_python,
)
from tools.agent_factory.benchmark30_docker import grade
from tools.agent_factory.worker_pool import (
    OPT_IN, OPT_VALUE, SECRET, WorkerPolicyError,
    _generate, endpoint_config, validate_job,
)

# Exactly six disjoint task families; do not expose private grading cases.
FIRST_TASK_IDS = ("T01", "T06", "T11", "T16", "T21", "T26")
ARMS = ("plain_delegation", "contract_scaffold")
NEXT_LESSONS = {
    "catalog": "Normalize text and IDs; retain ALL valid records and stable sorting.",
    "permissions": "Implement deny-by-default role/action matrix; refuse unknown roles.",
    "slots": "Respect duration, step and exclusive end boundary.",
    "deps": "Read graph direction correctly; include changed modules and their dependents.",
    "ledger": "Replay valid put events with integer revisions and deterministic keys.",
    "scrub": "Redact credentials while preserving ordinary text exactly.",
}


def task_specs() -> list[dict]:
    validate()
    tasks = {t["id"]: t for t in read_json(MANIFEST)["tasks"]}
    return [tasks[key] for key in FIRST_TASK_IDS]


def job_packet(task: dict, arm: str) -> dict:
    if arm not in ARMS:
        raise WorkerPolicyError("unknown orchestration arm")
    description = task["request"]
    instruction = (
        "Write the complete executable Python solution.py module implementing "
        + task["entrypoint"] + ". "
        + description
        + " Only Python source code; no markdown, no explanations."
    )
    context = (
        "Existing synthetic module:\n"
        + "def " + task["entrypoint"] + ":\n    raise NotImplementedError\n"
    )
    if arm == "contract_scaffold":
        context += (
            "\nPUBLIC API CONTRACT (not a hidden test or a solution):\n"
            + PUBLIC_INPUT_CONTRACTS[task["chain"]]
            + "\nKeep the signature and return type. Write a working function, "
            "not a stub, pseudocode or a one-word answer. "
            "Handle the edge cases explicitly stated in the task. "
            "This is an isolated synthetic program; never claim tests passed."
        )
    return validate_job({
        "id": task["id"], "role": "implementer",
        "instruction": instruction, "context": context,
        "paths": [task["path"]], "data_class": "synthetic",
    })


def failure_category(result: dict) -> str:
    if result.get("passed") is True:
        return "accepted_by_local_sandbox_tests"
    status = result.get("status")
    if status == "rejected_low_quality":
        return "format_or_completeness"
    if status == "syntax_invalid":
        return "syntax_or_extraction"
    if status in ("transport_failed", "execution_blocked"):
        return "infrastructure_or_protocol"
    if result.get("passed_tests", 0) > 0:
        return "partial_requirements_or_edge_cases"
    return "input_contract_or_core_behavior"


def summarize(rows: list[dict], model: str) -> dict:
    if len(rows) != 12 or {(r["arm"], r["task_id"]) for r in rows} != {
        (arm, task) for arm in ARMS for task in FIRST_TASK_IDS
    }:
        raise ValueError("paired six-task result grid incomplete")
    by_arm = {}
    for arm in ARMS:
        subset = [r for r in rows if r["arm"] == arm]
        by_arm[arm] = {
            "tasks": len(subset),
            "accepted": sum(r["passed"] is True for r in subset),
            "individual_tests_passed": sum(r["passed_tests"] for r in subset),
            "individual_tests_total": sum(r["tests"] for r in subset),
            "model_calls": len(subset),
            "seconds": round(sum(r["wall_time_s"] for r in subset), 2),
            "prompt_tokens": sum(r.get("prompt_tokens") or 0 for r in subset),
            "completion_tokens": sum(r.get("completion_tokens") or 0 for r in subset),
        }
    lessons = []
    for task in task_specs():
        family = task["chain"]
        outcomes = [r for r in rows if r["task_id"] == task["id"]]
        failures = [r for r in outcomes if not r["passed"]]
        lessons.append({
            "task_id": task["id"], "family": family,
            "plain_passed": next(r["passed"] for r in outcomes if r["arm"] == ARMS[0]),
            "scaffold_passed": next(r["passed"] for r in outcomes if r["arm"] == ARMS[1]),
            "failure_modes": sorted({failure_category(r) for r in failures}),
            "next_lesson": NEXT_LESSONS[family] if failures else
                           "Try a second-stage change and check regressions.",
            "training_status": "diagnostic_only_not_human_approved_not_signed"
        })
    lessons.sort(key=lambda r: (
        r["scaffold_passed"], r["plain_passed"], r["task_id"]
    ))
    return {
        "schema_version": 1,
        "status": "ACTUAL_MODEL_DIAGNOSTICS_NOT_WEIGHT_TRAINING",
        "model": model, "same_model_paired": True,
        "benchmark_tasks": list(FIRST_TASK_IDS),
        "grading": "independent per-arm sandbox Docker local results; NOT signed",
        "by_arm": by_arm, "curriculum": lessons,
        "next_experiment": (
            "For failed task families: improve scoped work packages, implement "
            "bounded repair with isolated test feedback, and retest on new cases. "
            "Do not conclude improvement without replication on unseen tasks."
        ),
        "training_data_eligible": False,
        "reason_not_training": (
            "Model outputs are not reviewer-approved and not signed by an "
            "independent evidence authority; withheld tests are reserved."
        )
    }


def evaluate(*, image: str, output: Path, timeout: int = 75) -> dict:
    if os.environ.get("GITHUB_ACTIONS") != "true" or \
            os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted":
        raise WorkerPolicyError("only on disposable GitHub-hosted CI worker")
    if os.environ.get("AGENT_BENCH30_ISOLATED_VM_APPROVED") != \
            "SYNTHETIC_DISPOSABLE_VM_ONLY":
        raise WorkerPolicyError("isolated verifier opt-in missing")
    if os.environ.get(OPT_IN) != OPT_VALUE:
        raise WorkerPolicyError("local synthetic inference opt-in missing")
    if type(timeout) is not int or not 5 <= timeout <= 120:
        raise WorkerPolicyError("invalid timeout")
    port, model, _ = endpoint_config()
    output = Path(output).expanduser().resolve()
    if output.exists():
        raise WorkerPolicyError("refusing to overwrite learning-lab results")
    output.mkdir(parents=True, mode=0o700)
    rows = []
    review_queue = []
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="worker-learning-", dir=os.environ["RUNNER_TEMP"]) as tmp:
        base = Path(tmp)
        for arm in ARMS:
            work = base / arm
            prepare(work)
            for task in task_specs():
                payload = job_packet(task, arm)
                ts = time.monotonic()
                response = _generate(payload, port, model, timeout)
                status = response.get("status")
                passed = False
                passed_tests, tests = 0, 0
                cause = status or "unknown"
                answer_sha256 = response.get("sha256")
                if status == "proposed_unverified":
                    try:
                        candidate = extract_python(response["content"])
                        if SECRET.search(candidate):
                            raise WorkerPolicyError("model output includes unsafe identifier")
                        solution = work / task["path"]
                        solution.write_text(candidate, encoding="utf-8")
                        scored = grade(
                            workspace=work, chain=task["chain"], upto=1, image=image
                        )
                        passed = scored.get("passed") is True
                        if passed:
                            # Store only passing SYNTHETIC code for separate human review.
                            # Local sandbox verification is not authenticated training proof.
                            pending = output / "pending_review"
                            pending.mkdir(exist_ok=True, mode=0o700)
                            candidate_name = task["id"] + "__" + arm + ".py"
                            destination = pending / candidate_name
                            destination.write_text(candidate, encoding="utf-8")
                            os.chmod(destination, 0o600)
                            review_queue.append({
                                "id": task["id"], "role": "implementer",
                                "family": task["chain"], "arm": arm,
                                "candidate_file": "pending_review/" + candidate_name,
                                "candidate_sha256": hashlib.sha256(candidate.encode()).hexdigest(),
                                "verifier_passed": True,
                                "verifier_name": "LOCAL_DOCKER_UNATTESTED",
                                "reviewer_approved": False,
                                "independently_signed": False,
                                "training_eligible": False
                            })
                        passed_tests = len(scored.get("passed_ids", []))
                        tests = scored.get("tests") or 0
                        cause = "graded"
                    except (ValueError, WorkerPolicyError, OSError, SyntaxError):
                        cause = "syntax_invalid"
                        status = "syntax_invalid"
                elif status == "rejected_low_quality":
                    cause = response.get("reason") or "format_rejected"
                else:
                    cause = response.get("error") or "transport_failed"
                    status = "transport_failed"
                row = {
                    "task_id": task["id"], "family": task["chain"],
                    "arm": arm, "status": status, "cause": cause,
                    "passed": passed, "passed_tests": passed_tests,
                    "tests": tests, "answer_sha256": answer_sha256,
                    "wall_time_s": round(time.monotonic() - ts, 3),
                    "prompt_tokens": response.get("usage", {}).get("prompt_tokens"),
                    "completion_tokens": response.get("usage", {}).get("completion_tokens"),
                }
                rows.append(row)
                print(json.dumps({
                    "task": task["id"], "arm": arm, "passed": passed,
                    "checks": f"{passed_tests}/{tests}", "cause": cause,
                }), flush=True)
    result = summarize(rows, model)
    result["pending_review_candidates"] = len(review_queue)
    result["runner_commit"] = os.environ.get("GITHUB_SHA")
    result["verifier_image"] = image
    result["total_wall_time_s"] = round(time.monotonic() - started, 2)
    result["gpu_calls"] = 0
    result["premium_claude_codex_calls"] = 0
    result["no_training_invoked"] = True
    result["observations"] = rows
    (output / "pending-review-index.json").write_text(
        json.dumps({
            "status": "HUMAN_REVIEW_REQUIRED_DO_NOT_TRAIN",
            "candidate_count": len(review_queue), "items": review_queue
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output / "learning-report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )
    (output / "NEXT_LESSONS.md").write_text(
        "# Worker Army: next lessons\n\n"
        + "Real model output scored in isolated synthetic tests. "
          "This is NOT LoRA training and does NOT verify the lead Claude.\n\n"
        + "\n".join(
            f"- **{l['family']}**: {l['next_lesson']} "
            f"(plain={l['plain_passed']}, scaffold={l['scaffold_passed']})"
            for l in result["curriculum"]
        ) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "status": result["status"], "by_arm": result["by_arm"],
        "total_wall_time_s": result["total_wall_time_s"]
    }))
    return result


def main() -> int:
    p = argparse.ArgumentParser(description="Paired low-cost-worker learning lab")
    p.add_argument("--image", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    try:
        evaluate(image=args.image, output=args.output)
        return 0
    except (WorkerPolicyError, OSError, ValueError, KeyError, TypeError) as exc:
        print("BLOCKED:", type(exc).__name__)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
