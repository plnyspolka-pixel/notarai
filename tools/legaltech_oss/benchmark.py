"""Synthetic-only quality evaluation of third-party PII anonymizers.

No third-party code is executed and no network requests are made. The tool
exports fictional inputs for offline evaluation and scores transformed text
created by an engine in a separate, isolated environment. Never point it at
real notarial acts or case records.

This is a recall/retention smoke-test, NOT a proof of anonymization or a
production authorization to send documents to an LLM.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ALLOWED_KINDS = frozenset({
    "NAME", "ADDRESS", "PESEL", "NIP", "REGON", "KRS", "KW",
    "PHONE", "EMAIL", "IBAN", "CASE_ID", "COMPANY",
})
STRUCTURED_KINDS = frozenset({"PESEL", "NIP", "REGON", "KRS", "KW", "PHONE", "IBAN"})
CASE_ID_RE = re.compile(r"[a-z][a-z0-9_-]{1,60}\Z")
MAX_CORPUS_BYTES = 512 * 1024
MAX_RESULT_BYTES = 256 * 1024


class BenchmarkError(ValueError):
    """Input or output is invalid; messages never contain document content."""


def _read_regular_file(path: Path, max_bytes: int) -> str:
    if path.is_symlink() or not path.is_file():
        raise BenchmarkError("expected a non-symlink regular file")
    if path.stat().st_size > max_bytes:
        raise BenchmarkError("file exceeds size limit")
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeError, OSError) as exc:
        raise BenchmarkError("cannot read UTF-8 file") from exc


def load_corpus(path: Path) -> list[dict[str, Any]]:
    try:
        corpus = json.loads(_read_regular_file(path, MAX_CORPUS_BYTES))
    except json.JSONDecodeError as exc:
        raise BenchmarkError("invalid corpus JSON") from exc
    if not isinstance(corpus, dict) or corpus.get("synthetic_only") is not True:
        raise BenchmarkError("corpus must explicitly declare synthetic_only=true")
    cases = corpus.get("cases")
    if not isinstance(cases, list) or not cases:
        raise BenchmarkError("corpus must contain cases")
    seen: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            raise BenchmarkError("invalid case shape")
        ident = case.get("id")
        if not isinstance(ident, str) or not CASE_ID_RE.fullmatch(ident) or ident in seen:
            raise BenchmarkError("case id is invalid or repeated")
        seen.add(ident)
        content, expected, preserved = (
            case.get("text"), case.get("secrets"), case.get("must_preserve", []),
        )
        if not isinstance(content, str) or not content or len(content) > 10000:
            raise BenchmarkError("case text invalid")
        if not isinstance(expected, list) or not isinstance(preserved, list):
            raise BenchmarkError("case expectations invalid")
        for secret in expected:
            if not isinstance(secret, dict) or secret.get("kind") not in ALLOWED_KINDS:
                raise BenchmarkError("invalid secret kind")
            value = secret.get("value")
            if not isinstance(value, str) or len(value) < 3 or value.casefold() not in content.casefold():
                raise BenchmarkError("secret not present verbatim in synthetic input")
        for anchor in preserved:
            if not isinstance(anchor, str) or not anchor or anchor.casefold() not in content.casefold():
                raise BenchmarkError("preservation anchor missing from synthetic input")
    return cases


def _compact(value: str, kind: str) -> str:
    """Recognize reformatting of structured identifiers by stripping separators."""
    if kind in {"PESEL", "NIP", "REGON", "KRS", "PHONE"}:
        return "".join(c for c in value if c.isdigit())
    if kind in {"KW", "IBAN"}:
        return "".join(c for c in value.upper() if c.isalnum())
    return value.casefold()


def is_leaked(secret: dict[str, str], output: str) -> bool:
    value = secret["value"]
    if value.casefold() in output.casefold():
        return True
    kind = secret["kind"]
    if kind in STRUCTURED_KINDS:
        needle = _compact(value, kind)
        if len(needle) >= 7 and needle in _compact(output, kind):
            return True
    return False


def export_cases(cases: list[dict[str, Any]], target: Path) -> dict[str, int]:
    if target.exists():
        if target.is_symlink() or not target.is_dir() or any(target.iterdir()):
            raise BenchmarkError("export directory must be empty and not a symlink")
    else:
        target.mkdir(parents=True, mode=0o700)
    try:
        os.chmod(target, 0o700)
    except OSError:
        pass  # Windows ACLs are managed by the caller's isolated test VM.
    for case in cases:
        path = target / (case["id"] + ".txt")
        with path.open("x", encoding="utf-8") as stream:
            stream.write(case["text"])
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    return {"synthetic_cases_exported": len(cases)}


def score_cases(cases: list[dict[str, Any]], outputs: Path) -> dict[str, Any]:
    if outputs.is_symlink() or not outputs.is_dir():
        raise BenchmarkError("output directory missing or is symlink")
    markers = 0
    leaked_markers = 0
    failed_cases: list[str] = []
    missing_cases: list[str] = []
    missing_anchors: list[str] = []
    leaked_kinds: Counter[str] = Counter()
    total_by_kind: Counter[str] = Counter()
    for case in cases:
        path = outputs / (case["id"] + ".txt")
        if path.is_symlink():
            raise BenchmarkError("output file must not be a symlink")
        if not path.exists():
            missing_cases.append(case["id"])
            continue
        output = _read_regular_file(path, MAX_RESULT_BYTES)
        case_failed = False
        for secret in case["secrets"]:
            markers += 1
            kind = secret["kind"]
            total_by_kind[kind] += 1
            if is_leaked(secret, output):
                leaked_markers += 1
                leaked_kinds[kind] += 1
                case_failed = True
        if any(anchor.casefold() not in output.casefold() for anchor in case["must_preserve"]):
            missing_anchors.append(case["id"])
            case_failed = True
        if case_failed:
            failed_cases.append(case["id"])
    # Deliberately NO 'safe_for_llm' flag. Passing tests does not prove PII-free.
    return {
        "status": "REVIEW_REQUIRED" if not failed_cases and not missing_cases else "FAIL",
        "cases": len(cases),
        "evaluated_cases": len(cases) - len(missing_cases),
        "marker_checks": markers,
        "leaked_markers": leaked_markers,
        "case_ids_with_failures": sorted(failed_cases),
        "case_ids_without_output": sorted(missing_cases),
        "case_ids_with_content_loss": sorted(missing_anchors),
        "leaked_markers_by_kind": dict(sorted(leaked_kinds.items())),
        "checked_markers_by_kind": dict(sorted(total_by_kind.items())),
        "production_approved": False,
        "disclaimer": "Synthetic exact-match test only; never proof of anonymization",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("export", "score"))
    parser.add_argument("--corpus", type=Path, default=Path(__file__).with_name("synthetic_cases.json"))
    parser.add_argument("--dir", type=Path, required=True, help="Export destination or scored output files")
    parser.add_argument("--report", type=Path, help="Optional aggregate JSON report, never raw text")
    args = parser.parse_args(argv)
    try:
        cases = load_corpus(args.corpus)
        result = export_cases(cases, args.dir) if args.mode == "export" else score_cases(cases, args.dir)
        report = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.report:
            if args.report.is_symlink():
                raise BenchmarkError("report path must not be a symlink")
            args.report.write_text(report, encoding="utf-8")
        print(report, end="")
        return 0 if args.mode == "export" or result["status"] == "REVIEW_REQUIRED" else 2
    except (BenchmarkError, OSError) as exc:
        # Never echo paths/inputs from a third-party tool into CI logs.
        reason = str(exc) if isinstance(exc, BenchmarkError) else "I/O failure"
        print("benchmark input/output invalid: " + reason, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
