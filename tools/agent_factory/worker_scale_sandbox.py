"""Isolated synthetic-code scale grader on disposable GitHub runner only."""
from __future__ import annotations
import ast
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from tools.agent_factory.worker_pool import WorkerPolicyError
from tools.agent_factory.worker_scale_corpus import samples

IMAGE=re.compile(r"^[a-z0-9][a-z0-9._/:@-]{0,180}@sha256:[a-f0-9]{64}$")
APPROVED="SYNTHETIC_DISPOSABLE_VM_ONLY"


def _cmd(task: dict, source: Path, cases: Path, image: str) -> list[str]:
    if not isinstance(image,str) or not IMAGE.fullmatch(image):
        raise WorkerPolicyError("digest-pinned isolated image required")
    for f in (source,cases):
        if f.is_symlink() or not f.is_file() or f.stat().st_size > 64_000:
            raise WorkerPolicyError("unsafe synthetic grading files")
    verifier=Path(__file__).resolve().parent / "worker_scale_grader.py"
    return [
        "docker","run","--rm","--init","--network","none","--read-only",
        "--cap-drop","ALL","--security-opt","no-new-privileges",
        "--pids-limit","64","--memory","256m","--cpus","1",
        "--user","65534:65534","--tmpfs","/tmp:rw,nosuid,noexec,size=16m",
        "--mount",f"type=bind,src={source.resolve()},dst=/work/solution.py,readonly",
        "--mount",f"type=bind,src={cases.resolve()},dst=/grader/cases.json,readonly",
        "--mount",f"type=bind,src={verifier.resolve()},dst=/grader/verify.py,readonly",
        "--workdir","/work","--entrypoint","python",image,
        "-I","/grader/verify.py"
    ]


def grade(*,task:dict,candidate:str,image:str)->dict:
    if os.environ.get("GITHUB_ACTIONS")!="true" or \
            os.environ.get("RUNNER_ENVIRONMENT")!="github-hosted" or \
            os.environ.get("AGENT_BENCH30_ISOLATED_VM_APPROVED")!=APPROVED:
        raise WorkerPolicyError("untrusted generated code can run only on disposable opt-in CI")
    if not isinstance(candidate,str) or len(candidate.encode())>32768:
        raise WorkerPolicyError("invalid generated candidate size")
    try:
        ast.parse(candidate,filename="synthetic_candidate.py")  # parse, DO NOT exec
    except SyntaxError:
        return {"status":"failed","passed":False,"tests":8,"passed_tests":0,
                "failure_category":"syntax"}
    vectors=samples(task)
    with tempfile.TemporaryDirectory(prefix="scale-grader-",dir=os.environ["RUNNER_TEMP"]) as tmp:
        root=Path(tmp)
        src=root/"solution.py"
        fixture=root/"cases.json"
        src.write_text(candidate,encoding="utf-8")
        fixture.write_text(json.dumps({"cases":vectors},ensure_ascii=False),encoding="utf-8")
        os.chmod(src,0o644)
        os.chmod(fixture,0o644)
        cmd=_cmd(task,src,fixture,image)
        try:
            outcome=subprocess.run(cmd,capture_output=True,text=True,timeout=40,
                                  env={"PATH":"/usr/local/bin:/usr/bin:/bin","HOME":"/nonexistent"})
        except (OSError,subprocess.TimeoutExpired):
            return {"status":"failed","passed":False,"tests":8,
                    "passed_tests":0,"failure_category":"sandbox_timeout_or_missing"}
        if len(outcome.stdout)>4000 or len(outcome.stderr)>8000:
            return {"status":"failed","passed":False,"tests":8,
                    "passed_tests":0,"failure_category":"oversized_or_malformed"}
        try:
            info=json.loads(outcome.stdout.strip().splitlines()[-1])
            score=info.get("passed")
            total=info.get("total")
            if (type(score)is not int or type(total)is not int or
                    total!=len(vectors) or not 0<=score<=total or
                    info.get("status") not in ("passed","failed")):
                raise ValueError()
            accepted=score==total and outcome.returncode==0 and info["status"]=="passed"
            return {"status":"passed" if accepted else "failed",
                    "passed":accepted,"tests":total,"passed_tests":score,
                    "failure_category":("none" if accepted else
                         info.get("failed_reason","wrong_behavior")),
                    "local_sandbox_only":True}
        except (IndexError,ValueError,TypeError,KeyError,json.JSONDecodeError):
            return {"status":"failed","passed":False,"tests":8,
                    "passed_tests":0,"failure_category":"invalid_grader_response"}
