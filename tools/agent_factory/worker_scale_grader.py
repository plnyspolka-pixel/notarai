"""Grader code executed *inside* a locked-down disposable Docker container.

Loads synthetic expected outputs from a trusted fixture and checks generated
solution.py. This is functional verification, not adversarially secure
attestation: candidate can execute only in a disposable unprivileged container.
Never run this module with candidate code on a trusted host.
"""
from __future__ import annotations
import copy
import importlib.util
import json
from pathlib import Path
import sys


def main() -> int:
    payload=json.loads(Path("/grader/cases.json").read_text(encoding="utf-8"))
    if not isinstance(payload,dict) or not isinstance(payload.get("cases"),list):
        raise ValueError("bad grader fixture")
    cases=payload["cases"]
    if not 1<=len(cases)<=40:
        raise ValueError("bad case count")
    passed=0
    errors=[]
    try:
        spec=importlib.util.spec_from_file_location("candidate_solution","/work/solution.py")
        if spec is None or spec.loader is None:
            raise ValueError("invalid source")
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        fn=getattr(module,"solve",None)
        if not callable(fn):
            raise ValueError("missing solve(data)")
    except BaseException:
        print(json.dumps({
            "status":"failed","passed":0,"total":len(cases),
            "failed_reason":"import_or_entrypoint","failed_ids":[r["case_id"] for r in cases]
        }))
        return 1
    for item in cases:
        try:
            value=fn(copy.deepcopy(item["input"]))
            if type(value)==type(item["expected"]) and value==item["expected"]:
                passed+=1
            else:
                errors.append(item["case_id"])
        except BaseException:
            errors.append(item["case_id"])
    result={"status":"passed" if passed==len(cases) else "failed",
            "passed":passed,"total":len(cases),"failed_ids":errors}
    print(json.dumps(result,ensure_ascii=False))
    return 0 if passed==len(cases) else 1


if __name__=="__main__":
    raise SystemExit(main())
