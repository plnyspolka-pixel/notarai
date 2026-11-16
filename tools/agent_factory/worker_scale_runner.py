"""Paired, stratified real CPU inference on the larger synthetic coding corpus.

A/B holds model revision, task, verifier and worker budget fixed. No worker
receives grader cases, no candidate executes on the host. On every shard, task
order alternates which prompt style is tested first to reduce order bias.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

from tools.agent_factory.benchmark30_cpu_pilot import extract_python
from tools.agent_factory.worker_pool import (
    WorkerPolicyError, SECRET, _generate, endpoint_config, validate_job,
    OPT_IN, OPT_VALUE
)
from tools.agent_factory.worker_scale_corpus import (
    FAMILIES, CASES_PER_TASK, summary, tasks
)
from tools.agent_factory.worker_scale_sandbox import grade

ARMS=("plain","structured")


def job_for(task: dict, arm: str) -> dict:
    if arm not in ARMS:
        raise WorkerPolicyError("unknown study method")
    instruction=(
        "Write a complete Python source file with exactly one entrypoint "
        "def solve(data). Follow these requirements precisely:\n"
        + task["instruction"] +
        "\nReturn only runnable Python code; no markdown or prose."
    )
    context=(
        "Synthetic new Python module. Existing code:\n"
        "def solve(data):\n    raise NotImplementedError\n"
    )
    if arm=="structured":
        context+=(
            "\nLead-programmer handoff / public contract:\n"
            "Function name is solve, and its ONLY argument is data. "
            "Input type and output shape are described above. "
            "Implement the entire algorithm; explicitly handle edge cases "
            "and invalid inputs mentioned in the specification. "
            "Never retain the NotImplementedError stub. "
            "No external dependencies, network, filesystem, or tools. "
            "Before returning, check that all decision branches, sort "
            "directions, boundary conditions, and specified exact types "
            "match the contract. Never claim you ran a test."
        )
    return validate_job({
        "id":task["id"].replace("-","_"),
        "role":"implementer",
        "instruction":instruction,
        "context":context,
        "paths":["synthetic/solution.py"],
        "data_class":"synthetic",
    })


def select_tasks(shard: int, per_family: int, split: str, start_variant: int = 0) -> list[dict]:
    if type(shard) is not int or not 0<=shard<5:
        raise WorkerPolicyError("expected shard 0..4")
    if type(per_family) is not int or not 1<=per_family<=10:
        raise WorkerPolicyError("expected between one and ten contracts per family")
    if split not in ("development","heldout"):
        raise WorkerPolicyError("invalid split")
    if type(start_variant) is not int or not 0 <= start_variant <= 9 or start_variant + per_family > 10:
        raise WorkerPolicyError("within-split variant range must fit 0..9")
    selected=set(FAMILIES[shard*2:shard*2+2])
    by_family={f:[] for f in selected}
    for t in tasks(split):
        if t["family"] in selected:
            by_family[t["family"]].append(t)
    result=[]
    for family in FAMILIES[shard*2:shard*2+2]:
        current=by_family[family]
        if len(current)<start_variant+per_family:
            raise WorkerPolicyError("family has insufficient contracts")
        result.extend(current[start_variant:start_variant+per_family])
    return result


def evaluate(image: str, output: Path, *, shard: int=0,
             per_family: int=4, split: str="development",
             start_variant: int=0) -> dict:
    if (os.environ.get("GITHUB_ACTIONS")!="true"
            or os.environ.get("RUNNER_ENVIRONMENT")!="github-hosted"
            or os.environ.get("AGENT_BENCH30_ISOLATED_VM_APPROVED")!=
               "SYNTHETIC_DISPOSABLE_VM_ONLY"
            or os.environ.get(OPT_IN)!=OPT_VALUE):
        raise WorkerPolicyError("only on explicitly approved disposable synthetic CI worker")
    port,model,_=endpoint_config()
    report=summary()
    selected=select_tasks(shard,per_family,split,start_variant)
    dest=Path(output).expanduser().resolve()
    if dest.exists() or dest.is_symlink():
        raise WorkerPolicyError("do not overwrite prior results")
    dest.mkdir(parents=True,mode=0o700)
    rows=[]
    started=time.monotonic()
    for task in selected:
        # Counterbalanced order: one model, same case bank; no hidden grader data
        # reaches the model. This is not a multi-agent Claude-led benchmark.
        arms=ARMS if task["variant"]%2==0 else ARMS[::-1]
        for arm in arms:
            t0=time.monotonic()
            job=job_for(task,arm)
            reply=_generate(job,port,model,90)
            scored={"passed":False,"tests":CASES_PER_TASK,"passed_tests":0,
                    "failure_category":reply.get("reason") or reply.get("status")}
            candidate_hash=None
            if reply.get("status")=="proposed_unverified":
                try:
                    code=extract_python(reply["content"])
                    if SECRET.search(code):
                        raise WorkerPolicyError("potential protected identifier in output")
                    candidate_hash=hashlib.sha256(code.encode()).hexdigest()
                    scored=grade(task=task,candidate=code,image=image)
                except (ValueError,TypeError,KeyError,WorkerPolicyError,SyntaxError) as err:
                    scored={"passed":False,"tests":CASES_PER_TASK,
                            "passed_tests":0,"failure_category":type(err).__name__}
            result={
                "task_id":task["id"],"family":task["family"],
                "split":task["split"],"task_sha256":task["task_sha256"],
                "arm":arm,"status":reply.get("status"),
                "accepted":scored["passed"],
                "tests":scored["tests"],"passed_tests":scored["passed_tests"],
                "failure_category":scored["failure_category"],
                "answer_sha256":candidate_hash,
                "elapsed_s":round(time.monotonic()-t0,2),
                "prompt_tokens":(reply.get("usage") or {}).get("prompt_tokens"),
                "completion_tokens":(reply.get("usage") or {}).get("completion_tokens"),
            }
            rows.append(result)
            print(json.dumps({
                "task":task["id"],"arm":arm,"passed":result["accepted"],
                "checks":str(result["passed_tests"])+"/"+str(result["tests"]),
                "cause":result["failure_category"],
            }),flush=True)
    if len(rows)!=2*len(selected) or {
            (r["task_id"],r["arm"]) for r in rows
        }!={(t["id"],a) for t in selected for a in ARMS}:
        raise WorkerPolicyError("incomplete A/B trial, cannot report comparison")
    by_arm={}
    for arm in ARMS:
        subset=[r for r in rows if r["arm"]==arm]
        by_arm[arm]={
            "trials":len(subset),
            "accepted":sum(r["accepted"] is True for r in subset),
            "case_passed":sum(r["passed_tests"] for r in subset),
            "case_total":sum(r["tests"] for r in subset),
            "seconds":round(sum(r["elapsed_s"] for r in subset),2),
            "prompt_tokens":sum(r["prompt_tokens"] or 0 for r in subset),
            "completion_tokens":sum(r["completion_tokens"] or 0 for r in subset),
        }
    result={
        "schema_version":1,"status":"ACTUAL_CPU_MODEL_AB_SYNTHETIC_NOT_TRAINING",
        "suite":report["suite"],"model":model,
        "shard":shard,"per_family":per_family,"start_variant":start_variant,"split":split,
        "algorithmic_families":len({t["family"] for t in selected}),
        "parameterized_contracts":len(selected),
        "total_model_calls":len(rows),"verifier":"disposable_sandbox_not_signed",
        "weight_training":False,"premium_claude_codex_calls":0,
        "gpu_calls":0,"benchmark_evaluation_not_training":True,
        "runner_commit":os.environ.get("GITHUB_SHA"),
        "image":image,"total_seconds":round(time.monotonic()-started,2),
        "arms":by_arm,"results":rows,
        "warning":"Variants within each algorithm family are correlated; no statistical independence claim."
    }
    (dest/"results.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    print(json.dumps({"status":result["status"],"shard":shard,
                      "contracts":len(selected),"arms":by_arm}),flush=True)
    return result


def main() -> int:
    p=argparse.ArgumentParser(description="Real large CPU worker orchestration trial")
    p.add_argument("--image",required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--shard",type=int,required=True)
    p.add_argument("--per-family",type=int,default=4)
    p.add_argument("--start-variant",type=int,default=0)
    p.add_argument("--split",choices=("development","heldout"),default="development")
    a=p.parse_args()
    try:
        evaluate(a.image,a.out,shard=a.shard,per_family=a.per_family,split=a.split,
                 start_variant=a.start_variant)
        return 0
    except (WorkerPolicyError,ValueError,OSError,KeyError,TypeError) as exc:
        print("BLOCKED:",type(exc).__name__,flush=True)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
