"""Analysis of scale-worker CI artifacts, with 10-family clustered uncertainty.

Never infer cost savings or model training from synthetic pass counts.
These are local observations; CI artifacts are not cryptographically attested.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import random

from tools.agent_factory.worker_scale_corpus import FAMILIES, VERSION, tasks

ARMS=("plain","structured")


def combine(root: Path) -> dict:
    paths=sorted(Path(root).glob("**/results.json"))
    if len(paths)!=5:
        raise ValueError("require exactly five successful independent shard reports")
    loaded=[json.loads(p.read_text(encoding="utf-8")) for p in paths]
    first=loaded[0]
    if first.get("status")!="ACTUAL_CPU_MODEL_AB_SYNTHETIC_NOT_TRAINING":
        raise ValueError("missing real-model trial status")
    split=first.get("split")
    per_family=first.get("per_family")
    start_variant=first.get("start_variant",0)
    if (split not in ("development","heldout") or
            type(per_family) is not int or not 1<=per_family<=10 or
            type(start_variant) is not int or not 0<=start_variant<=9 or
            start_variant+per_family>10):
        raise ValueError("invalid corpus slice")
    expected={t["id"]:t for t in tasks(split)
              if start_variant<=t["variant"]%10<start_variant+per_family}
    all_rows=[]
    seen_shards=set()
    for report in loaded:
        if (report.get("shard") in seen_shards or type(report.get("shard"))is not int or
                report["shard"] not in range(5) or report.get("model")!=first.get("model") or
                report.get("suite")!=VERSION or report.get("split")!=split or
                report.get("per_family")!=per_family or
                report.get("start_variant",0)!=start_variant or
                report.get("weight_training") is not False or
                report.get("benchmark_evaluation_not_training") is not True or
                report.get("premium_claude_codex_calls")!=0 or
                report.get("gpu_calls")!=0):
            raise ValueError("shard provenance mismatch")
        seen_shards.add(report["shard"])
        for row in report.get("results", []):
            task=expected.get(row.get("task_id"))
            if (task is None or row.get("family")!=task["family"] or
                    row.get("task_sha256")!=task["task_sha256"] or
                    row.get("split")!=split or row.get("arm") not in ARMS or
                    type(row.get("accepted")) is not bool or
                    type(row.get("passed_tests")) is not int or
                    type(row.get("tests")) is not int or
                    row["tests"]!=8 or not 0<=row["passed_tests"]<=8 or
                    (row["accepted"] and row["passed_tests"]!=8)):
                raise ValueError("invalid task result or score")
            # Verify that a job graded only its assigned family pair.
            if FAMILIES.index(task["family"])//2!=report["shard"]:
                raise ValueError("cross-shard contamination")
            all_rows.append(row)
    if len(all_rows)!=2*len(expected):
        raise ValueError("incomplete paired task grid")
    keyed={}
    for row in all_rows:
        key=(row["task_id"],row["arm"])
        if key in keyed:
            raise ValueError("duplicated task result")
        keyed[key]=row
    if set(keyed)!={(task_id,arm) for task_id in expected for arm in ARMS}:
        raise ValueError("missing paired result")
    totals={}
    for arm in ARMS:
        matched=[row for row in all_rows if row["arm"]==arm]
        accepted=sum(row["accepted"] for row in matched)
        seconds=sum(row["elapsed_s"] for row in matched)
        totals[arm]={
            "tasks":len(matched),"accepted":accepted,
            "cases_passed":sum(row["passed_tests"] for row in matched),
            "cases_total":sum(row["tests"] for row in matched),
            "total_seconds":round(seconds,2),
            "seconds_per_accepted_change":round(seconds/accepted,2) if accepted else None,
            "prompt_tokens":sum(row.get("prompt_tokens") or 0 for row in matched),
            "completion_tokens":sum(row.get("completion_tokens") or 0 for row in matched)
        }
    pairs=Counter()
    fam=defaultdict(lambda:{"plain":0,"structured":0,"count":0})
    failed=Counter()
    for id_ in expected:
        a=keyed[(id_,"plain")]
        b=keyed[(id_,"structured")]
        kind=("both" if a["accepted"] and b["accepted"] else
              "plain_only" if a["accepted"] else
              "structured_only" if b["accepted"] else "neither")
        pairs[kind]+=1
        group=fam[expected[id_]["family"]]
        group["count"]+=1
        group["plain"]+=int(a["accepted"])
        group["structured"]+=int(b["accepted"])
        for x in (a,b):
            if not x["accepted"]:
                failed[(x["family"],x["failure_category"])]+=1
    # Resample by ALGORITHM FAMILY, not by correlated parameter variations.
    rng=random.Random(20261116)
    effects=[]
    groups=list(sorted(fam))
    for _ in range(3000):
        sample=[fam[rng.choice(groups)] for __ in range(len(groups))]
        successes=sum(v["structured"]-v["plain"] for v in sample)
        total=sum(v["count"] for v in sample)
        effects.append(successes/total)
    effects.sort()
    report={
        "status":"OBSERVATIONAL_PAIRED_CPU_CORPUS_NOT_MODEL_TRAINING",
        "model":first["model"],"suite":VERSION,"split":split,
        "start_variant":start_variant,"per_family":per_family,
        "parameterized_contracts":len(expected),
        "independent_algorithm_families":len(fam),
        "actual_model_calls":len(all_rows),"oracle_checks":sum(row["tests"] for row in all_rows),
        "paired_outcomes":dict(pairs),"arms":totals,
        "structured_minus_plain_acceptance":round(
            (totals["structured"]["accepted"]-totals["plain"]["accepted"])/len(expected),4
        ),
        "family_cluster_bootstrap_95pct": [
            round(effects[75],4),round(effects[2924],4)
        ],
        "per_family":dict(sorted(fam.items())),
        "top_failure_categories":[{"family":family,"category":cat,"count":count}
                                  for (family,cat),count in failed.most_common(30)],
        "training_eligible":False,
        "no_claude_code_lead_calls":True,
        "no_gpu":True,
        "warning":"Correlated synthetic variants and unauthenticated local CI grading; bootstrap is exploratory, not causal proof. Do not train on evaluation tasks."
    }
    return report


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("root",type=Path)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    try:
        report=combine(a.root)
    except (ValueError,OSError,TypeError,KeyError,AttributeError) as exc:
        print("BLOCKED",type(exc).__name__)
        return 2
    a.output.parent.mkdir(parents=True,exist_ok=True)
    if a.output.exists():
        print("BLOCKED existing aggregate result")
        return 2
    a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({key:report[key] for key in (
        "status","parameterized_contracts","actual_model_calls",
        "paired_outcomes","arms","structured_minus_plain_acceptance"
    )},ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
