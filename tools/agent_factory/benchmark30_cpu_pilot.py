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


def run_pilot(model_path: Path, output: Path, image: str, model_id: str, max_tasks: int = 3) -> dict:
    if not model_path.is_file() or model_path.stat().st_size < 100_000_000:
        raise ValueError("GGUF file unavailable or implausibly small")
    if output.exists():
        raise ValueError("refusing to overwrite pilot outputs")
    validate()
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
            try:
                response = llm.create_chat_completion(
                    messages=[{"role": "system", "content": "You write correct, minimal, secure Python code. Reply with code only."},
                              {"role": "user", "content": prompt}],
                    max_tokens=650, temperature=0.0, top_p=1.0
                )
                usage = response.get("usage", {})
                raw = response["choices"][0]["message"]["content"]
                code = extract_python(raw)
                syntax_ok = True
                solution.write_text(code, encoding="utf-8")
                (output / (task["id"] + ".py")).write_text(code, encoding="utf-8")
                outcome = grade(workspace=work, chain=chain, upto=stage, image=image)
            except Exception as exc:
                outcome = {"status": "failed", "reason": type(exc).__name__,
                           "passed": False, "verification": "not-completed"}
            rows.append({
                "task_id": task["id"], "chain": chain, "step": stage,
                "real_model_inference": True, "syntax_ok": syntax_ok,
                "passed": bool(outcome.get("passed", False)),
                "verifier": outcome, "wall_time_s": round(time.monotonic() - t0, 3),
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "candidate_sha256": hashlib.sha256(solution.read_bytes()).hexdigest()
            })
        result = {
            "type": "actual-cpu-llm-30-task-baseline" if max_tasks == 30 else "actual-cpu-llm-pilot; not full 30-task benchmark",
            "model": model_id,
            "model_sha256": file_sha256(model_path),
            "verifier_image": image, "workflow_sha": os.environ.get("GITHUB_SHA"),
            "source_of_tasks": "30 tasks / 6 five-stage chains" if max_tasks == 30 else "T01-T03 (one cumulative chain)",
            "tasks_attempted": len(rows), "tasks_passed": sum(int(row["passed"]) for row in rows),
            "model_calls": len(rows), "elapsed_s": round(time.monotonic() - started, 3),
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
    parser.add_argument("--output", type=Path, required=True)
    a = parser.parse_args()
    run_pilot(a.model_path, a.output, a.image, a.model_id, a.max_tasks)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
