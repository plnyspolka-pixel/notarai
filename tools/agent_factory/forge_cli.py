"""CLI for Agent Forge foundation. No network or third-party libraries."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from tools.agent_factory.forge_core import (
    ForgeError, RunStore, audit_catalog, execute_offline,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "docs" / "agent-factory-research" / "fixtures"
CATALOG = ROOT / "docs" / "agent-factory-research" / "catalog.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Agent Forge offline control-plane MVP")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Validate research catalog (no external calls)")
    demo = commands.add_parser("demo", help="Run synthetic experiment with independent rubric")
    demo.add_argument("--run-id", default="sum-demo-001")
    demo.add_argument("--state", type=Path, default=ROOT / ".agent-forge" / "runs.sqlite3")
    demo.add_argument("--fixtures", type=Path, default=FIXTURES)
    demo.add_argument("--task", default="sum-task.json")
    demo.add_argument("--rubric", default="sum-rubric.json")
    report = commands.add_parser("report", help="List recorded experiments and audit")
    report.add_argument("--state", type=Path, default=ROOT / ".agent-forge" / "runs.sqlite3")
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            result = audit_catalog(CATALOG)
            result.update({"engine": "offline-only", "paid_workers": False,
                           "production_connected": False})
        elif args.command == "demo":
            with RunStore(args.state) as store:
                result = execute_offline(store, args.fixtures,
                                         args.run_id, args.task, args.rubric)
        else:
            with RunStore(args.state) as store:
                runs = store.list_runs()
                result = {"runs": runs, "all_audits_valid": all(
                    store.verify_events(record["run_id"]) for record in runs
                )}
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    except (ForgeError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        # Diagnostics intentionally do not include fixtures or source contents.
        print("BLOCKED: " + type(exc).__name__ + ": " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
