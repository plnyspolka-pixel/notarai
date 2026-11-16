"""Safety contracts for the large synthetic grader (no Docker required)."""
from pathlib import Path
import pytest

from tools.agent_factory.worker_scale_corpus import make_task, samples
from tools.agent_factory.worker_scale_sandbox import _cmd, grade
from tools.agent_factory.worker_pool import WorkerPolicyError


def test_sandbox_command_requires_digest_and_unprivileged_no_network(tmp_path):
    a=tmp_path/"solution.py"
    b=tmp_path/"cases.json"
    a.write_text("def solve(data): return data\n")
    b.write_text('{"cases":[]}')
    img="python@sha256:"+"a"*64
    cmd=_cmd(make_task("numeric",0),a,b,img)
    assert "--network" in cmd and cmd[cmd.index("--network")+1]=="none"
    assert "--cap-drop" in cmd and cmd[cmd.index("--cap-drop")+1]=="ALL"
    assert "--user" in cmd and cmd[cmd.index("--user")+1]=="65534:65534"
    assert "--read-only" in cmd
    assert "--security-opt" in cmd
    with pytest.raises(WorkerPolicyError):
        _cmd(make_task("numeric",0),a,b,"python:latest")


def test_candidate_never_executes_on_the_host(monkeypatch):
    monkeypatch.delenv("AGENT_BENCH30_ISOLATED_VM_APPROVED",raising=False)
    with pytest.raises(WorkerPolicyError):
        grade(task=make_task("numeric",0),
              candidate="import os\nos.system('touch /tmp/NO')",
              image="python@sha256:"+"a"*64)


def test_oracle_case_sizes_bounded():
    for family in ("numeric","text","records","authorization","timeslots",
                   "dependencies","eventlog","redaction","slugs","intervals"):
        case=samples(make_task(family,0))
        assert len(case)==8
