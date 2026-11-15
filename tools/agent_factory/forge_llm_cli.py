"""Operator-only local model benchmark CLI. Does not provision GPUs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from tools.agent_factory.forge_core import ForgeError, RunStore
from tools.agent_factory.forge_llm import LocalModelConfig, run_local_model

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "docs" / "agent-factory-research" / "fixtures"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Operator-approved local model run")
    parser.add_argument("--state", type=Path, default=ROOT / ".agent-forge" / "runs.sqlite3")
    parser.add_argument("--fixtures", type=Path, default=FIXTURES)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--task", default="sum-task.json")
    parser.add_argument("--rubric", default="sum-rubric.json")
    parser.add_argument("--model", required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--max-output-tokens", type=int, default=48)
    parser.add_argument("--allow-local-model", action="store_true")
    args = parser.parse_args(argv)
    config = LocalModelConfig(
        model=args.model, endpoint=args.endpoint,
        timeout_s=args.timeout, max_output_tokens=args.max_output_tokens,
    )
    try:
        with RunStore(args.state) as store:
            result = run_local_model(
                store, args.fixtures, args.run_id, args.task, args.rubric,
                config, operator_opt_in=args.allow_local_model,
            )
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        return 0 if result["passed"] else 1
    except (ForgeError, OSError, ValueError) as exc:
        print("BLOCKED: " + type(exc).__name__ + ": " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
