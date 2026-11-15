"""No Docker daemon required or used in these tests."""
from pathlib import Path
import pytest

from tools.agent_factory.forge_core import ForgeError
from tools.agent_factory.forge_sandbox import (
    DockerTestConfig, docker_command, run_docker_tests, stage_solution,
    OPT_IN_ENV, OPT_IN_VALUE,
)

PINNED = "python:3.12-slim@sha256:" + "a" * 64


def test_stage_only_synthetic_solution(tmp_path):
    base = tmp_path / "isolated"
    root = stage_solution(base, "synthetic-001",
                          "def solve(xs): return sum(xs)\n")
    assert set(x.name for x in root.iterdir()) == {
        "solution.py", "test_solution.py"
    }
    with pytest.raises(ForgeError):
        stage_solution(base, "synthetic-001", "print('overwrite')")


def test_docker_command_has_all_isolation_flags(tmp_path):
    root = stage_solution(tmp_path, "synthetic-002",
                          "def solve(xs): return sum(xs)\n")
    cmd = docker_command(root, DockerTestConfig(image=PINNED))
    assert cmd[:2] == ["docker", "run"]
    assert "--network" in cmd and cmd[cmd.index("--network")+1] == "none"
    assert "--read-only" in cmd and "--cap-drop" in cmd
    assert "--security-opt" in cmd and "no-new-privileges:true" in cmd
    assert "--user" in cmd and "65534:65534" in cmd
    assert "--pids-limit" in cmd and "--memory" in cmd
    assert "--mount" in cmd
    assert ",readonly" in cmd[cmd.index("--mount")+1]
    assert cmd[-1] == "test_*.py"
    assert "--privileged" not in cmd
    assert "docker.sock" not in " ".join(cmd)


def test_operator_gates_default_off(tmp_path, monkeypatch):
    root = stage_solution(tmp_path, "synthetic-003",
                          "def solve(xs): return sum(xs)\n")
    monkeypatch.delenv(OPT_IN_ENV, raising=False)
    with pytest.raises(ForgeError, match="disabled"):
        run_docker_tests(root, DockerTestConfig(image=PINNED), operator_opt_in=True)
    monkeypatch.setenv(OPT_IN_ENV, OPT_IN_VALUE)
    with pytest.raises(ForgeError, match="disabled"):
        run_docker_tests(root, DockerTestConfig(image=PINNED), operator_opt_in=False)


@pytest.mark.parametrize("image", ["python:latest", "python:3.12", "a@sha256:broken",
                                    "python:3.12;rm -rf /", ""])
def test_unpinned_or_unsafe_image_rejected(image):
    with pytest.raises(ForgeError, match="pinned"):
        DockerTestConfig(image=image).validate()


def test_only_two_files_allowed(tmp_path):
    root = stage_solution(tmp_path, "synthetic-004",
                          "def solve(xs): return sum(xs)\n")
    (root / "token.txt").write_text("should be rejected")
    with pytest.raises(ForgeError, match="exactly two"):
        docker_command(root, DockerTestConfig(image=PINNED))


def test_no_symlinks_in_workspace(tmp_path):
    root = stage_solution(tmp_path, "synthetic-005",
                          "def solve(xs): return sum(xs)\n")
    (root / "solution.py").unlink()
    (root / "solution.py").symlink_to(tmp_path / "missing.txt")
    with pytest.raises(ForgeError, match="unapproved"):
        docker_command(root, DockerTestConfig(image=PINNED))


def test_reject_oversized_source(tmp_path):
    with pytest.raises(ForgeError):
        stage_solution(tmp_path, "synthetic-006", "a" * 32769)


def test_docker_runtime_is_mocked_never_executed(tmp_path, monkeypatch):
    import tools.agent_factory.forge_sandbox as module
    monkeypatch.setenv(OPT_IN_ENV, OPT_IN_VALUE)
    root = stage_solution(tmp_path, "synthetic-007",
                          "def solve(xs): return sum(xs)\n")
    monkeypatch.setattr(module.shutil, "which", lambda *_: "/usr/bin/docker")
    calls = []
    class FakeResult:
        returncode = 0
        stdout = b"ok"
        stderr = b""
    def fake_run(args, **kwargs):
        calls.append(args)
        return FakeResult()
    monkeypatch.setattr(module.subprocess, "run", fake_run)
    result = run_docker_tests(root, DockerTestConfig(image=PINNED),
                              operator_opt_in=True)
    assert result["passed"] is True
    assert len(calls) == 2
    assert calls[0][:3] == ["docker", "image", "inspect"]
    assert calls[1][:2] == ["docker", "run"]
