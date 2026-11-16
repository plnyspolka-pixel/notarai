"""Actual, bounded CPU-model pilot for T01-T03. Not the 30-task benchmark.

A local GGUF LLM writes candidate code. The candidate is parsed (never executed)
on this runner, then graded by the independent benchmark30_docker scorer in a
network-disabled container on an ephemeral public-repository GitHub Actions VM.
No external model API, API key, cloud secret or customer data is used.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time

from tools.agent_factory.benchmark30 import MANIFEST, SOURCE_STUB, prepare, read_json, validate
from tools.agent_factory.benchmark30_docker import grade


def extract_python(response: str) -> str:
    """Conservatively accept Python source, optionally wrapped in one code fence."""
    match = re.fullmatch(r"\s*\x60\x60\x60(?:python|py)?\s*\n(.*?)\n\x60\x60\x60\s*", response, re.S | re.I)
    code = (match.group(1) if match else response).strip() + "\n"
    if not code.strip() or len(code.encode("utf-8")) > 32768:
        raise ValueError("empty or oversized candidate")
    ast.parse(code, filename="candidate.py")  # Parsing only; NEVER import/exec here.
    return code


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()



PUBLIC_INPUT_CONTRACTS = {
    "catalog": "INPUT: rows is a list of dictionaries with keys 'id' and 'name'. OUTPUT: list of dictionaries. Handle invalid entries without mutating input.",
    "permissions": "INPUT: request is one Python dictionary: request['role'], request['action']; optional request['tenant'], request['actor_tenant'], request['approved'], request['now'], request['expires_at'], request['revoked']. Never split request as a string. OUTPUT: a Python bool.",
    "slots": "INPUT: request is one Python dictionary with integer start, end, duration, step; optional blocked list of [start,end] integer pairs. OUTPUT: list of integer start times. A valid slot must FIT before end.",
    "deps": "INPUT: request is one Python dictionary with request['imports'] mapping module names to dependency-name lists, and request['changed'] a list of module names. OUTPUT: sorted list of existing affected module names.",
    "ledger": "INPUT: events is list of dictionaries {id,key,op,value,rev}. Put writes event['value'] to key, delete removes it, rev is integer; skip malformed entries. OUTPUT: dictionary key to value.",
    "scrub": "INPUT: text is one Python string. OUTPUT: Python string with selected credential patterns replaced by exact redaction markers, preserving ordinary text."
}


def run_pilot(model_path: Path, output: Path, image: str, model_id: str, max_tasks: int = 3, repair_attempts: int = 0) -> dict:
    if not model_path.is_file() or model_path.stat().st_size < 100_000_000:
        raise ValueError("GGUF file unavailable or implausibly small")
    if output.exists():
        raise ValueError("refusing to overwrite pilot outputs")
    validate()
    if repair_attempts not in (0, 1, 2):
        raise ValueError("retry budget must be 0, 1 or 2")
    if max_tasks not in (3, 30):
        raise ValueError("only three-task smoke test or full thirty-task baseline are allowed")
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted":
        raise ValueError("only allowed on disposable GitHub-hosted runners")
    if os.environ.get("AGENT_BENCH30_ISOLATED_VM_APPROVED") != "SYNTHETIC_DISPOSABLE_VM_ONLY":
        raise ValueError("explicit disposable VM opt-in missing")
    from llama_cpp import Llama  # imported after checking execution environment

    llm = Llama(model_path=str(model_path), n_ctx=4096, n_threads=4,
                n_gpu_layers=0, verbose=False, seed=20261116)
    output.mkdir(parents=True)
    # Workspaces must never be placed in the repository tree.
    with tempfile.TemporaryDirectory(prefix="bench30-real-model-", dir=os.environ["RUNNER_TEMP"]) as tmp:
        work = Path(tmp) / "work"
        prepare(work)
        tasks = read_json(MANIFEST)["tasks"][:max_tasks]
        assert len(tasks) == max_tasks
        rows = []
        started = time.monotonic()
        for task in tasks:
            stage, chain = task["step"], task["chain"]
            solution = work / chain / "solution.py"
            prior_specs = "\n".join(
                f"{t['id']}: {t['request']}"
                for t in tasks if t["chain"] == chain and t["step"] <= stage
            )
            existing = solution.read_text(encoding="utf-8")
            prompt = (
                "Implement Python code in solution.py. Provide ONLY the full standalone source file, "
                "no markdown, no explanations. Implement " + task["entrypoint"] + ". "
                "Use standard-library Python only. Preserve previous requirements. "
                "Never use filesystem, network, subprocess or imports beyond standard library.\n\n"
                "Cumulative task specifications:\n" + prior_specs +
                "\n\nCurrent solution.py:\n" + existing +
                "\nReturn the complete revised Python source file."
            )
            t0 = time.monotonic()
            usage = {}
            syntax_ok = False
            attempts = []
            best_code = existing
            best_result = {"status": "failed", "passed": False, "passed_ids": [], "failed_ids": []}
            best_score = -1
            feedback = ""
            if repair_attempts:
                prompt = (
                    "Write an IMPLEMENTATION, not a plan, of the exact Python function "
                    + task["entrypoint"] + ". The initial stub raising NotImplementedError "
                    "is NEVER an acceptable solution. Do not return unchanged code when "
                    "a new requirement is added. Provide the COMPLETE executable module "
                    "and NO explanations. Use Python standard library only.\\n\\n"
                    "Public input/output contract (NOT a test case): "
                    + PUBLIC_INPUT_CONTRACTS[chain] + "\\n\\n"
                    "All requirements to preserve for this chain, in stage order:\\n"
                    + prior_specs + "\\n\\nExisting code:\\n" + existing
                )
            for attempt in range(repair_attempts + 1):
                request = prompt
                if attempt:
                    request += (
                        "\\n\\nYour previous attempt DID NOT PASS independent checks. "
                        "Repair its actual implementation. Preserve previously working "
                        "behavior. Do not remove or loosen requirements. "
                        "Tests are intentionally not disclosed. "
                        + feedback + "\\nCurrent candidate source:\\n"
                        + solution.read_text(encoding="utf-8")
                    )
                attempt_start = time.monotonic()
                try:
                    response = llm.create_chat_completion(
                        messages=[{"role": "system", "content": "You implement correct Python. Return only source code; never merely echo a stub."},
                                  {"role": "user", "content": request}],
                        max_tokens=900 if repair_attempts else 650,
                        temperature=0.15 if attempt else 0.0, top_p=1.0
                    )
                    usage = response.get("usage", {})
                    code = extract_python(response["choices"][0]["message"]["content"])
                    syntax_ok = True
                    solution.write_text(code, encoding="utf-8")
                    result = grade(workspace=work, chain=chain, upto=stage, image=image)
                except Exception as exc:
                    result = {"status": "failed", "passed": False,
                              "passed_ids": [], "failed_ids": [],
                              "reason": type(exc).__name__, "verification": "not-completed"}
                score = len(result.get("passed_ids", []))
                attempts.append({
                    "attempt": attempt + 1, "passed": bool(result.get("passed")),
                    "passed_count": score, "failed_case_ids": result.get("failed_ids", []),
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "wall_time_s": round(time.monotonic() - attempt_start, 3)
                })
                if score > best_score or (result.get("passed") and not best_result.get("passed")):
                    best_score, best_code, best_result = score, solution.read_text(encoding="utf-8"), result
                if result.get("passed"):
                    break
                feedback = (
                    f"Stage {stage}: {score} verified cases passed; "
                    f"{len(result.get('failed_ids', []))} failed. "
                    f"Failed case IDs: {result.get('failed_ids', [])}. "
                    f"Failure category: {result.get('reason', 'incorrect behavior')}. "
                    "Review data types, edge conditions and all previous requirements."
                )
            solution.write_text(best_code, encoding="utf-8")
            (output / (task["id"] + ".py")).write_text(best_code, encoding="utf-8")
            outcome = best_result
            rows.append({
                "task_id": task["id"], "chain": chain, "step": stage,
                "real_model_inference": True, "syntax_ok": syntax_ok,
                "passed": bool(outcome.get("passed", False)),
                "verifier": outcome, "wall_time_s": round(time.monotonic() - t0, 3),
                "prompt_tokens": sum(x.get("prompt_tokens") or 0 for x in attempts),
                "completion_tokens": sum(x.get("completion_tokens") or 0 for x in attempts),
                "attempts": attempts,
                "first_attempt_passed": bool(attempts and attempts[0]["passed"]),
                "candidate_sha256": hashlib.sha256(solution.read_bytes()).hexdigest()
            })
            print(json.dumps({"task": task["id"], "passed": rows[-1]["passed"],
                              "attempts": len(attempts), "checks_passed": best_score}), flush=True)
        result = {
            "type": "actual-cpu-llm-30-task-baseline" if max_tasks == 30 else "actual-cpu-llm-pilot; not full 30-task benchmark",
            "model": model_id,
            "model_sha256": file_sha256(model_path),
            "verifier_image": image, "workflow_sha": os.environ.get("GITHUB_SHA"),
            "source_of_tasks": "30 tasks / 6 five-stage chains" if max_tasks == 30 else "T01-T03 (one cumulative chain)",
            "tasks_attempted": len(rows), "tasks_passed": sum(int(row["passed"]) for row in rows),
            "model_calls": sum(len(row["attempts"]) for row in rows),
            "repair_attempts": repair_attempts,
            "tasks_passed_at_first_attempt": sum(int(row["first_attempt_passed"]) for row in rows),
            "elapsed_s": round(time.monotonic() - started, 3),
            "gpu_rental_pln": 0, "paid_model_api_pln": 0,
            "github_standard_public_runner_minutes": "free subject to GitHub policy",
            "verifier_attestation": "local docker report only; NOT independently signed",
            "no_production_permissions": True,
            "rows": rows
        }
        (output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({key: result[key] for key in ["type","tasks_attempted","tasks_passed","model_calls","elapsed_s"]}))
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--model-id", default="Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF / q4_k_m / cpu")
    parser.add_argument("--max-tasks", type=int, default=3, choices=(3, 30))
    parser.add_argument("--repair-attempts", type=int, choices=(0, 1, 2), default=0)
    parser.add_argument("--output", type=Path, required=True)
    a = parser.parse_args()
    run_pilot(a.model_path, a.output, a.image, a.model_id, a.max_tasks, a.repair_attempts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
