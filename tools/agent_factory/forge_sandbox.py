"""Cautious synthetic-code test sandbox builder. NEVER a security guarantee.

Docker can be dangerous on a host with sensitive workloads; use ONLY on a
disposable, isolated worker VM. No container runs without explicit opt-in.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import subprocess

from tools.agent_factory.forge_core import ForgeError, RUN_ID

IMAGE = re.compile(r"^[a-z0-9][a-z0-9._/:@-]{0,180}@sha256:[a-f0-9]{64}$")
OPT_IN_ENV = "AGENT_FORGE_ALLOW_DOCKER_TEST"
OPT_IN_VALUE = "I_APPROVE_ISOLATED_SYNTHETIC_TEST"
MAX_SOURCE_BYTES = 32768
TRUSTED_TEST = """import unittest
from solution import solve

class SumFixtureTests(unittest.TestCase):
    def test_positive(self):
        self.assertEqual(solve([1, 2, 3]), 6)

    def test_negatives(self):
        self.assertEqual(solve([-9, 4, 5]), 0)

    def test_empty(self):
        self.assertEqual(solve([]), 0)
"""


def stage_solution(base: Path, run_id: str, source: str) -> Path:
    """Stage only a synthetic Python solution and fixed trusted tests.

    This writes text but NEVER imports/evals/executes it on the host.
    A generated solution cannot edit the test definitions.
    """
    if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
        raise ForgeError("Invalid sandbox run ID")
    if not isinstance(source, str):
        raise ForgeError("Expected source text")
    raw = source.encode("utf-8")
    if not raw or len(raw) > MAX_SOURCE_BYTES or b"\0" in raw:
        raise ForgeError("Invalid synthetic solution size")
    base = Path(base)
    if base.exists() and base.is_symlink():
        raise ForgeError("Workspace base cannot be a symlink")
    base.mkdir(parents=True, exist_ok=True)
    if base.is_symlink():
        raise ForgeError("Workspace base cannot be a symlink")
    workspace = base / run_id
    try:
        workspace.mkdir(mode=0o755, exist_ok=False)
    except FileExistsError as exc:
        raise ForgeError("Workspace already exists; refuse overwrite") from exc
    (workspace / "solution.py").write_bytes(raw)
    (workspace / "test_solution.py").write_text(TRUSTED_TEST, encoding="utf-8")
    os.chmod(workspace, 0o755)
    for item in workspace.iterdir():
        os.chmod(item, 0o644)
    return workspace.resolve(strict=True)


@dataclass(frozen=True)
class DockerTestConfig:
    image: str
    timeout_s: int = 45

    def validate(self) -> None:
        if not isinstance(self.image, str) or not IMAGE.fullmatch(self.image):
            raise ForgeError("Image must be pinned to a full sha256 digest")
        if type(self.timeout_s) is not int or not 5 <= self.timeout_s <= 120:
            raise ForgeError("Timeout must be 5-120 seconds")


def docker_command(workspace: Path, config: DockerTestConfig) -> list[str]:
    """Command never contains a model-supplied shell fragment."""
    config.validate()
    workspace = Path(workspace)
    if workspace.is_symlink() or not workspace.is_dir():
        raise ForgeError("Workspace must be a concrete directory")
    if set(item.name for item in workspace.iterdir()) != {
        "solution.py", "test_solution.py"
    }:
        raise ForgeError("Workspace must contain exactly two synthetic files")
    for item in workspace.iterdir():
        if item.is_symlink() or not item.is_file() or item.stat().st_size > MAX_SOURCE_BYTES:
            raise ForgeError("Workspace contains unapproved files")
    # Docker --mount option values are comma-separated; reject delimiter injection.
    absolute = str(workspace.resolve(strict=True))
    if any(c in absolute for c in (",", "\n", "\r", "\0")):
        raise ForgeError("Unsafe workspace path")
    return [
        "docker", "run", "--rm", "--pull", "never",
        "--network", "none", "--read-only",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
        "--pids-limit", "64", "--memory", "512m", "--cpus", "1",
        "--ipc", "private", "--user", "65534:65534",
        "--tmpfs", "/tmp:rw,nosuid,noexec,size=64m",
        "--env", "HOME=/tmp", "--env", "PYTHONDONTWRITEBYTECODE=1",
        "--workdir", "/workspace",
        "--mount", "type=bind,source=" + absolute + ",target=/workspace,readonly",
        config.image, "python", "-B", "-m", "unittest", "discover",
        "-s", "/workspace", "-p", "test_*.py",
    ]


def run_docker_tests(workspace: Path, config: DockerTestConfig,
                     *, operator_opt_in: bool = False) -> dict:
    """No auto-pull, no network, no Docker privileged mode; operator must opt in.

    SECURITY: Docker daemon is privileged and host kernel is shared. Run this
    only on a separate disposable VM with no secrets or customer data.
    """
    cmd = docker_command(workspace, config)
    if operator_opt_in is not True or os.environ.get(OPT_IN_ENV) != OPT_IN_VALUE:
        raise ForgeError("Container execution disabled without two explicit approvals")
    if not shutil.which("docker"):
        raise ForgeError("Docker is not installed on the isolated worker")
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
           "HOME": str(Path(workspace).parent)}
    try:
        image_check = subprocess.run(
            ["docker", "image", "inspect", config.image],
            env=env, check=False, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=10,
        )
        if image_check.returncode != 0:
            raise ForgeError("Pinned Docker image is not cached; downloads disabled")
        completed = subprocess.run(
            cmd, env=env, check=False, capture_output=True,
            timeout=config.timeout_s,
        )
        return {
            "passed": completed.returncode == 0,
            "exit_code": completed.returncode,
            "stdout_sha256": __import__("hashlib").sha256(completed.stdout).hexdigest(),
            "stderr_sha256": __import__("hashlib").sha256(completed.stderr).hexdigest(),
            "runtime": "docker-offline",
            "output_stored": False,
        }
    except subprocess.TimeoutExpired as exc:
        # Docker CLI timeout does not guarantee descendants/container are gone.
        raise ForgeError("Docker test timed out; inspect for surviving container") from exc
    except OSError as exc:
        raise ForgeError("Docker test launch failed") from exc
