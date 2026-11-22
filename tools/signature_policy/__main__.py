"""Read-only offline triage of a DSS SimpleReport and independently hashed document."""

import argparse
import json
from pathlib import Path
import sys
from .report_gate import InvalidReport, evaluate_report, sha256_regular_file, MAX_REPORT_BYTES


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--document", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.report.is_symlink() or not args.report.is_file() or args.report.stat().st_size > MAX_REPORT_BYTES:
            raise InvalidReport("invalid XML report file")
        if args.output and args.output.is_symlink():
            raise InvalidReport("invalid output path")
        report = evaluate_report(args.report.read_bytes(), sha256_regular_file(args.document))
        result = json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as handle:
                handle.write(result)
        else:
            print(result, end="")
        return 0
    except (InvalidReport, OSError) as exc:
        # Never print paths or XML content in application logs.
        reason = str(exc) if isinstance(exc, InvalidReport) else "filesystem failure"
        print("DSS triage rejected: " + reason, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
