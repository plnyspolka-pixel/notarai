"""Single-step operator CLI for the offline Agent Forge scheduler."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from tools.agent_factory.forge_core import ForgeError, RunStore
from tools.agent_factory.forge_scheduler import JobQueue, tick

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE = ROOT / ".agent-forge"
FIXTURES = ROOT / "docs" / "agent-factory-research" / "fixtures"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Agent Forge offline queue")
    parser.add_argument("--queue", type=Path, default=DEFAULT_STATE / "jobs.sqlite3")
    parser.add_argument("--runs", type=Path, default=DEFAULT_STATE / "runs.sqlite3")
    parser.add_argument("--fixtures", type=Path, default=FIXTURES)
    sub = parser.add_subparsers(dest="command", required=True)
    job = sub.add_parser("submit")
    job.add_argument("--job-id", required=True)
    job.add_argument("--task", default="sum-task.json")
    job.add_argument("--rubric", default="sum-rubric.json")
    job.add_argument("--max-attempts", type=int, default=2)
    sub.add_parser("tick")
    sub.add_parser("list")
    sub.add_parser("pause")
    sub.add_parser("resume")
    cancel = sub.add_parser("cancel")
    cancel.add_argument("--job-id", required=True)
    args = parser.parse_args(argv)
    try:
        with JobQueue(args.queue) as queue:
            if args.command == "submit":
                result = {"new": queue.submit(args.job_id, args.task, args.rubric,
                                               max_attempts=args.max_attempts)}
            elif args.command == "tick":
                with RunStore(args.runs) as runs:
                    result = tick(queue, runs, args.fixtures)
            elif args.command == "pause":
                queue.set_paused(True)
                result = queue.status()
            elif args.command == "resume":
                queue.set_paused(False)
                result = queue.status()
            elif args.command == "cancel":
                result = {"cancelled": queue.cancel(args.job_id)}
            else:
                result = {"jobs": queue.list_jobs(), **queue.status()}
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    except (ForgeError, OSError, ValueError) as exc:
        print("BLOCKED: " + type(exc).__name__)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
