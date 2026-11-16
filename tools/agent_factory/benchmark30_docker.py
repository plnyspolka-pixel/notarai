"""Explicitly opt-in container grading for synthetic code on a DISPOSABLE VM.

This is defense in depth, not proof of container or host isolation. NEVER run
on a host with production credentials, a Docker socket exposed to agents, or
shared sensitive data. No network, no elevated privileges, pinned image only.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess

from tools.agent_factory.benchmark30 import BenchmarkError, CHAINS, CASES, validate

IMAGE = re.compile(r"^[a-z0-9][a-z0-9._/:@-]{0,180}@sha256:[a-f0-9]{64}$")
OPT_IN = "AGENT_BENCH30_ISOLATED_VM_APPROVED"
VALUE = "SYNTHETIC_DISPOSABLE_VM_ONLY"


def command(*, workspace: Path, chain: str, upto: int, image: str) -> list[str]:
    """Make a fixed argv, no shell; no Docker execution until operator calls run()."""
    if chain not in CHAINS or type(upto) is not int or not 1 <= upto <= 5:
        raise BenchmarkError("unknown chain/stage")
    if not isinstance(image, str) or not IMAGE.fullmatch(image):
        raise BenchmarkError("Docker image must be pinned by digest")
    workspace = Path(workspace).expanduser().resolve()
    solution = workspace / chain / "solution.py"
    if solution.is_symlink() or not solution.is_file() or solution.stat().st_size > 32_768:
        raise BenchmarkError("solution not found or unsafe")
    validate()
    case_path = CASES.resolve()
    verifier_path = (Path(__file__).resolve().parent / "benchmark30_verifier.py").resolve()
    return [
        "docker", "run", "--rm", "--init", "--network", "none", "--read-only",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--pids-limit", "64", "--memory", "256m", "--cpus", "1",
        "--user", "65534:65534", "--tmpfs", "/tmp:rw,nosuid,noexec,size=16m",
        "--mount", f"type=bind,src={solution},dst=/workspace/solution.py,readonly",
        "--mount", f"type=bind,src={case_path},dst=/grader/cases.json,readonly",
        "--mount", f"type=bind,src={verifier_path},dst=/grader/verifier.py,readonly",
        "--workdir", "/workspace", "--entrypoint", "python", image,
        "-I", "/grader/verifier.py", "--chain", chain, "--upto", str(upto)
    ]


def grade(*, workspace: Path, chain: str, upto: int, image: str) -> dict:
    args = command(workspace=workspace, chain=chain, upto=upto, image=image)
    if os.environ.get(OPT_IN) != VALUE:
        raise BenchmarkError("Docker grading requires verified disposable VM and explicit opt-in")
    try:
        result = subprocess.run(args, timeout=50, capture_output=True, text=True, check=False,
                                env={"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/nonexistent"})
    except (OSError, subprocess.TimeoutExpired):
        return {"status": "failed", "reason": "worker-not-available-or-timeout", "verified": False}
    if len(result.stdout) > 16_000 or len(result.stderr) > 16_000:
        return {"status": "failed", "reason": "oversized-worker-output", "verified": False}
    try:
        payload = json.loads(result.stdout.strip().splitlines()[-1]); assert isinstance(payload, dict)
        if payload.get("status") not in {"passed", "failed"}:
            raise ValueError()
        passed = result.returncode == 0 and payload["status"] == "passed"
        return {"status": "passed" if passed else "failed", "passed": passed,
                "tests": payload.get("total"), "passed_ids": payload.get("passed_ids", []),
                "failed_ids": payload.get("failed_ids", []),
                "verification": "local-docker-isolated-ephemeral; NOT a signed CI attestation",
                "requires_independent_review": True}
    except (IndexError, json.JSONDecodeError, ValueError, AssertionError):
        return {"status": "failed", "reason": "untrusted-worker-output", "verified": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manual isolated VM Docker verification, NOT general runner")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--chain", choices=CHAINS, required=True)
    parser.add_argument("--upto", type=int, choices=range(1, 6), required=True)
    parser.add_argument("--image", required=True, help="Trusted audited image@sha256 digest")
    args = parser.parse_args(argv)
    try:
        result = grade(workspace=args.workspace, chain=args.chain, upto=args.upto, image=args.image)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("passed") else 1
    except BenchmarkError as e:
        print(json.dumps({"status": "BLOCKED", "reason": str(e)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
