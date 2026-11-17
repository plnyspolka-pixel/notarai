"""Offline academic analysis CLI. Only strict, anonymized paired metrics."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from tools.agent_factory.forge_core import ForgeError
from tools.agent_factory.forge_research_stats import compare_paired, read_experiment

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "docs" / "agent-factory-research" / "fixtures" / "paired-research-demo.json"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Research-grade paired task comparison")
    parser.add_argument("--input", type=Path, default=DEMO)
    args = parser.parse_args(argv)
    try:
        result = compare_paired(read_experiment(args.input))
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (ForgeError, OSError, ValueError) as exc:
        # Never log raw input or document contents.
        print("BLOCKED: " + type(exc).__name__)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
