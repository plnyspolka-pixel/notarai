"""Stage a synthetic coding task. Execution disabled without dual opt-in."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.agent_factory.forge_core import ForgeError
from tools.agent_factory.forge_sandbox import (
    DockerTestConfig, docker_command, run_docker_tests, stage_solution,
)

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / ".agent-forge" / "sandbox-workspaces"
SYNTHETIC_SOLUTION = "def solve(values):\n    return sum(values)\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Synthetic Agent Forge code sandbox")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--workspace-root", type=Path, default=BASE)
    parser.add_argument("--image", required=True,
                        help="Operator-provisioned local image with @sha256 digest")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    try:
        workspace = stage_solution(
            args.workspace_root, args.run_id, SYNTHETIC_SOLUTION
        )
        config = DockerTestConfig(image=args.image)
        plan = docker_command(workspace, config)
        if not args.execute:
            result = {
                "status": "staged-only", "workspace": str(workspace),
                "container_executed": False, "image": config.image,
                "args": plan,
            }
        else:
            result = run_docker_tests(workspace, config, operator_opt_in=True)
        print(json.dumps(result, indent=2))
        return 0
    except (ForgeError, OSError) as exc:
        print("BLOCKED: " + type(exc).__name__)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
