"""Strict synthesis of five real 14B/32B benchmark shard artifacts.

Group differences by ten algorithm families; avoid overclaiming independence
across parameter variants. Billing unknown until independently provided by
SaladCloud after resources stop.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import argparse
import json
from pathlib import Path
import random

from tools.agent_factory.worker_scale_runner import select_tasks, ARMS
from tools.agent_factory.worker_scale_corpus import VERSION


def aggregate(root: Path) -> dict:
    paths=sorted(Path(root).glob("**/results.json"))
    if len(paths)!=5:
        raise ValueError("expected exactly five complete result artifacts")
    source=[json.loads(p.read_text(encoding="utf-8")) for p in paths]
    first=source[0]
    size_ids=("14B","32B")
    split=first.get("split")
    per_family=first.get("per_family")
    if split!="development" or type(per_family) is not int or per_family not in (1,2,4):
        raise ValueError("invalid registered benchmark design")
    expected={}
    for shard in range(5):
        for task in select_tasks(shard,per_family,split):
            expected[task["id"]]=task
    registered=set()
    cells={}
    for item in source:
        shard=item.get("shard")
        if (type(shard)is not int or shard not in range(5) or shard in registered
                or item.get("status")!="REAL_REMOTE_GPU_MODEL_PAIR_EVALUATION_NOT_TRAINING"
                or item.get("suite")!=VERSION or item.get("split")!=split
                or item.get("per_family")!=per_family
                or item.get("weight_training") is not False
                or item.get("premium_claude_codex_calls")!=0
                or item.get("model_sizes")!=list(size_ids)
                or item.get("models")!=first.get("models")):
            raise ValueError("invalid or incompatible GPU trial shard")
        registered.add(shard)
        for row in item.get("rows",[]):
            task=expected.get(row.get("task_id"))
            if (task is None or
                    row.get("family")!=task["family"] or
                    row.get("task_sha256")!=task["task_sha256"] or
                    row.get("model_size") not in size_ids or row.get("arm") not in ARMS or
                    row.get("split")!=split or type(row.get("accepted"))is not bool or
                    type(row.get("cases_passed"))is not int or
                    row.get("cases_total")!=8 or
                    not 0<=row["cases_passed"]<=8 or
                    (row["accepted"] and row["cases_passed"]!=8) or
                    type(row.get("latency_s")) not in (int,float) or row["latency_s"]<0):
                raise ValueError("invalid benchmark row or grader result")
            if int(task["id"].split("-")[0][1:])-1 not in (shard*2,shard*2+1):
                raise ValueError("task placed in the wrong shard")
            key=(task["id"],row["model_size"],row["arm"])
            if key in cells:
                raise ValueError("duplicate inference result")
            cells[key]=row
    desired={(task_id,size,arm) for task_id in expected
             for size in size_ids for arm in ARMS}
    if set(cells)!=desired:
        raise ValueError("incomplete paired 14B/32B experiment")
    totals={}
    family_group={}
    comparisons={}
    for arm in ARMS:
        comparison=Counter()
        family=defaultdict(lambda:{"n":0,"14B":0,"32B":0})
        for task_id,task in expected.items():
            a=cells[(task_id,"14B",arm)]["accepted"]
            b=cells[(task_id,"32B",arm)]["accepted"]
            category=("both" if a and b else "14B_only" if a else
                      "32B_only" if b else "neither")
            comparison[category]+=1
            family[task["family"]]["n"]+=1
            family[task["family"]]["14B"]+=int(a)
            family[task["family"]]["32B"]+=int(b)
        rng=random.Random(14032)
        names=sorted(family)
        effects=[]
        for _ in range(3000):
            selection=[family[rng.choice(names)] for _ in names]
            numerator=sum(f["32B"]-f["14B"] for f in selection)
            denom=sum(f["n"] for f in selection)
            effects.append(numerator/denom)
        effects.sort()
        comparisons[arm]={
            "paired_outcomes":dict(comparison),
            "32B_minus_14B_acceptance":round(
                sum(f["32B"]-f["14B"] for f in family.values())/len(expected),4
            ),
            "ten_family_cluster_bootstrap_95pct":[round(effects[75],4),round(effects[2924],4)]
        }
        family_group[arm]=dict(sorted(family.items()))
    for size in size_ids:
        totals[size]={}
        for arm in ARMS:
            group=[cells[(task_id,size,arm)] for task_id in expected]
            successes=sum(r["accepted"] for r in group)
            lat=sum(r["latency_s"] for r in group)
            totals[size][arm]={
                "tasks":len(group),"accepted":successes,
                "cases_passed":sum(r["cases_passed"] for r in group),
                "cases_total":sum(r["cases_total"] for r in group),
                "total_request_s":round(lat,2),
                "request_seconds_per_accepted":round(lat/successes,2) if successes else None,
                "prompt_tokens":sum(r.get("prompt_tokens") or 0 for r in group),
                "completion_tokens":sum(r.get("completion_tokens") or 0 for r in group),
            }
    return {
        "status":"REAL_MODEL_PAIR_AGGREGATED_CI_EVIDENCE_NOT_SALAD_BILLING",
        "suite":VERSION,"models":first["models"],
        "parameterized_tasks":len(expected),"algorithm_families":10,
        "actual_model_calls":len(cells),
        "oracle_case_evaluations":sum(r["cases_total"] for r in cells.values()),
        "by_model":totals,"by_prompt":comparisons,"by_family":family_group,
        "actual_gpu_cost_usd":None,"actual_billed_instance_seconds":None,
        "training_performed":False,"claude_code_lead_run":False,
        "warning":"Correlated contracts, 10 algorithm families, untrusted community-GPU inferences, local non-attested Docker tests. Request latency is NOT a proxy for paid instance runtime. No production/customer data."
    }


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    args=p.parse_args()
    if args.output.exists():
        print("BLOCKED: output exists")
        return 2
    try:
        report=aggregate(args.root)
    except (ValueError,TypeError,KeyError,OSError,IndexError,AttributeError) as exc:
        print("BLOCKED:",type(exc).__name__)
        return 2
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:report[k] for k in
          ("status","parameterized_tasks","actual_model_calls","by_model","by_prompt")}))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
