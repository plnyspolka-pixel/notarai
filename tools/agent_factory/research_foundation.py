"""Offline, no-dependency research-backed foundations for coding agents.

This module DOES NOT execute agents, run untrusted tests, access a model, or deploy.
It produces reproducible evidence and policy decisions for a separately sandboxed runner.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import re
import sqlite3
import statistics
from typing import Any, Iterable

SOURCES = {".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".yaml", ".yml", ".md"}
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", "coverage", "dane", "secrets", ".aws", ".ssh", ".next"}
RISKY = re.compile(r"(^|/)(?:\.env(?:\..*)?|.*(?:auth|payment|platnosc|migration|migracj|secret|credential|deploy|infra|kms|signing|podpis|kyc|aml).*)(?:/|$)", re.I)
CODE_SYMBOL = re.compile(r"^\s*(?:export\s+)?(?:async\s+)?(?:function|class|interface|type|const)\s+([A-Za-z_$][\w$]*)", re.M)
WORDS = re.compile(r"[A-Za-z_][A-Za-z_0-9]{2,}")
ALLOWED_MEM_TYPES = {"bug-location", "regression", "decision", "test-evidence"}


class ResearchPolicyError(ValueError):
    """Untrusted input violates the local research policy."""


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def sha(value: bytes | Any) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value).encode("utf-8")).hexdigest()


def _tokens(value: str) -> set[str]:
    expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value).replace("_", " ")
    return {word.lower() for word in WORDS.findall(expanded)}


def _safe_source(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or len(relative) > 500 or "\\" in relative:
        raise ResearchPolicyError("invalid relative path")
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts or any(p in SKIP_DIRS or p.startswith(".env") for p in path.parts):
        raise ResearchPolicyError("path outside permitted source scope")
    current = root.resolve()
    for part in path.parts:
        current = current / part
        if current.is_symlink():
            raise ResearchPolicyError("symlink source forbidden")
    final = current.resolve()
    if not final.is_relative_to(root.resolve()) or not final.is_file():
        raise ResearchPolicyError("missing/outside source")
    return final


def _load_json(path: Path) -> Any:
    if path.stat().st_size > 2_000_000:
        raise ResearchPolicyError("JSON exceeds size limit")
    return json.loads(path.read_text(encoding="utf-8"))


def load_studies(path: Path) -> list[dict[str, Any]]:
    """Parse earlier research inventory, without treating any abstract as instructions."""
    if path.stat().st_size > 2_000_000:
        raise ResearchPolicyError("catalog too large")
    if path.suffix == ".jsonl":
        items = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    else:
        value = _load_json(path)
        items = value["studies"] if isinstance(value, dict) else value
    if not isinstance(items, list):
        raise ResearchPolicyError("catalog is not a list")
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            raise ResearchPolicyError("invalid study")
        identifier = str(item.get("identifier", ""))
        source = str(item.get("source", ""))
        valid = (re.fullmatch(r"\d{4}\.\d{4,5}", identifier) is not None
                 and source == f"https://arxiv.org/abs/{identifier}")
        valid |= (re.fullmatch(r"10\.\d{4,9}/[A-Za-z0-9._;()/:+-]+", identifier) is not None
                  and source == f"https://doi.org/{identifier}")
        valid |= (re.fullmatch(r"https://openreview\.net/forum\?id=[A-Za-z0-9_-]+", identifier) is not None
                  and source == identifier)
        if not valid or identifier in seen:
            raise ResearchPolicyError("duplicate study or invalid canonical source")
        seen.add(identifier)
    return items


def catalog_summary(path: Path) -> dict[str, Any]:
    studies = load_studies(path)
    return {
        "count": len(studies),
        "categories": dict(sorted(Counter(s.get("category", "unknown") for s in studies).items())),
        "with_numeric_findings": sum(bool(s.get("numeric_findings")) for s in studies),
        "catalog_digest": sha(studies),
        "status": "source-metadata-only; requires reproduction before production claim",
    }


def index_repository(root: Path, query: str, max_files: int = 2500, max_bytes: int = 128_000, limit: int = 15) -> list[dict[str, Any]]:
    """Conservative lexical + Python AST / TS structural anchors, at current file hashes.

    No embeddings or network; a deterministic baseline for future CodeNib/AST/LSP A/B.
    """
    root = root.resolve()
    if not root.is_dir() or not 1 <= max_files <= 25000 or not 1 <= limit <= 100:
        raise ResearchPolicyError("invalid indexing scope")
    terms = _tokens(query)
    if not terms:
        raise ResearchPolicyError("empty query")
    results = []
    scanned = 0
    for source in sorted(root.rglob("*")):
        if len(results) >= max_files * 20:
            break
        if not source.is_file() or source.suffix not in SOURCES or any(p in SKIP_DIRS or p.startswith(".env") for p in source.relative_to(root).parts):
            continue
        if source.is_symlink() or source.stat().st_size > max_bytes:
            continue
        scanned += 1
        if scanned > max_files:
            raise ResearchPolicyError("file budget exceeded; narrow scope")
        relative = source.relative_to(root).as_posix()
        try:
            text = source.read_text(encoding="utf-8")
        except (UnicodeError, OSError):
            continue
        hits = _tokens(relative + " " + text) & terms
        if not hits:
            continue
        symbols: list[str] = []
        if source.suffix == ".py":
            try:
                tree = ast.parse(text)
                symbols = [n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
            except SyntaxError:
                pass
        elif source.suffix in {".ts", ".tsx", ".js", ".jsx"}:
            symbols = CODE_SYMBOL.findall(text)[:300]
        symbols = list(dict.fromkeys(symbols))[:100]
        match_symbols = [s for s in symbols if _tokens(s) & terms]
        results.append({"file": relative, "sha256": sha(text.encode()), "matched_terms": sorted(hits),
                        "symbols": match_symbols[:12], "score": len(hits) * 2 + len(match_symbols),
                        "source": "local-file-hash", "repo_commit": "must-be-pinned-by-caller"})
    return sorted(results, key=lambda x: (-x["score"], x["file"]))[:limit]


class EvidenceLedger:
    """Local metadata-only ledger. Historical evidence is stale after source changes."""
    def __init__(self, db: Path, repo_root: Path):
        self.repo_root = repo_root.resolve()
        db.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(db)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("""CREATE TABLE IF NOT EXISTS facts (
            id INTEGER PRIMARY KEY, repo_root TEXT NOT NULL, base_commit TEXT NOT NULL,
            source_path TEXT NOT NULL, source_sha TEXT NOT NULL,
            kind TEXT NOT NULL, label TEXT NOT NULL, at_utc TEXT NOT NULL)""")
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def record(self, base_commit: str, path: str, kind: str, label: str) -> int:
        if not re.fullmatch(r"[0-9a-f]{40}", base_commit) or kind not in ALLOWED_MEM_TYPES:
            raise ResearchPolicyError("invalid provenance or event kind")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,49}(?::[A-Za-z0-9_-]{1,30})?", label):
            raise ResearchPolicyError("memory labels are identifiers, not freeform content")
        source = _safe_source(self.repo_root, path)
        file_hash = sha(source.read_bytes())
        with self.db:
            row = self.db.execute("INSERT INTO facts (repo_root,base_commit,source_path,source_sha,kind,label,at_utc) VALUES (?,?,?,?,?,?,?)",
                (str(self.repo_root), base_commit, path, file_hash, kind, label, datetime.now(timezone.utc).isoformat()))
        return row.lastrowid

    def recall(self, current_commit: str, *, include_stale: bool = False) -> list[dict[str, Any]]:
        if not re.fullmatch(r"[0-9a-f]{40}", current_commit):
            raise ResearchPolicyError("invalid git commit")
        records = self.db.execute("SELECT id,base_commit,source_path,source_sha,kind,label FROM facts WHERE repo_root=? ORDER BY id", (str(self.repo_root),)).fetchall()
        result = []
        for ident, commit, name, old_sha, kind, label in records:
            try:
                current_hash = sha(_safe_source(self.repo_root, name).read_bytes())
                fresh = (commit == current_commit and current_hash == old_sha)
            except (OSError, ResearchPolicyError):
                fresh = False
            if fresh or include_stale:
                result.append({"id": ident, "source_path": name, "kind": kind, "label": label,
                               "valid": fresh, "status": "valid" if fresh else "stale-needs-revalidation"})
        return result


def freeze_test_plan(plan: dict[str, Any]) -> str:
    """Return external immutable fingerprint: store this OUTSIDE agent-editable worktree."""
    if not isinstance(plan, dict) or plan.get("classification") != "synthetic":
        raise ResearchPolicyError("only synthetic test plans")
    tests = plan.get("tests", [])
    if not isinstance(tests, list) or not tests or len(tests) > 200:
        raise ResearchPolicyError("test plan requires bounded tests")
    if any(not isinstance(t, dict) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", str(t.get("id", ""))) for t in tests):
        raise ResearchPolicyError("invalid test identifiers")
    if len({t["id"] for t in tests}) != len(tests):
        raise ResearchPolicyError("duplicate test identifiers")
    return sha(plan)


def gate_patch(*, plan: dict[str, Any], expected_digest: str, changed_paths: list[str], test_results: list[dict[str, Any]],
               review_criteria: dict[str, bool], approval: bool = False) -> dict[str, Any]:
    """Fail-closed advisory gate; cannot substitute for external sandbox or protected CI."""
    failures = []
    try:
        if freeze_test_plan(plan) != expected_digest:
            failures.append("frozen-plan-integrity")
    except ResearchPolicyError:
        failures.append("invalid-plan")
    planned = {t["id"] for t in plan.get("tests", []) if isinstance(t, dict) and isinstance(t.get("id"), str)}
    observed = {t.get("id") for t in test_results if isinstance(t, dict) and t.get("passed") is True}
    if not planned or not planned.issubset(observed):
        failures.append("tests-missing-or-failed")
    if not changed_paths or len(changed_paths) > 300:
        failures.append("invalid-patch-scope")
    for path in changed_paths:
        if not isinstance(path, str) or Path(path).is_absolute() or ".." in Path(path).parts or "\\" in path:
            failures.append("invalid-changed-path"); continue
        if RISKY.search(path) and not approval:
            failures.append("sensitive-change-needs-human-approval")
    if not review_criteria or any(type(x) is not bool or not x for x in review_criteria.values()):
        failures.append("review-criteria-unmet")
    return {"accepted": not failures, "reasons": sorted(set(failures)), "plan_sha256": expected_digest,
            "requires_external_ci_and_human_review": True}


def evaluate_pairs(rows: Iterable[dict[str, Any]], baseline: str = "baseline", candidate: str = "candidate", seed: int = 73) -> dict[str, Any]:
    """Paired outcome comparisons at same pinned task/commit; 95% bootstrap CIs."""
    groups = defaultdict(dict)
    for r in rows:
        key = (r.get("task_id"), r.get("base_commit"), r.get("replicate", 0))
        variant = r.get("variant")
        if not isinstance(r.get("task_id"), str) or not re.fullmatch(r"[0-9a-f]{40}", str(r.get("base_commit", ""))):
            raise ResearchPolicyError("unverifiable task pairing")
        if variant not in {baseline, candidate} or variant in groups[key]:
            raise ResearchPolicyError("duplicate/unknown experimental variant")
        if type(r.get("accepted")) is not bool or type(r.get("cost_pln")) not in (int, float) or r["cost_pln"] < 0:
            raise ResearchPolicyError("invalid outcome measurement")
        groups[key][variant] = r
    pairs = [group for group in groups.values() if len(group) == 2]
    if len(pairs) != len(groups) or not pairs:
        raise ResearchPolicyError("missing paired experimental runs")
    diffs = [100 * (int(g[candidate]["accepted"]) - int(g[baseline]["accepted"])) for g in pairs]
    rng = random.Random(seed)
    estimates = [statistics.mean(rng.choice(diffs) for _ in diffs) for _ in range(2000)]
    estimates.sort()
    def summary(variant: str) -> dict[str, Any]:
        yes = sum(g[variant]["accepted"] for g in pairs)
        cost = sum(g[variant]["cost_pln"] for g in pairs)
        return {"accepted": yes, "success_pct": round(100 * yes / len(pairs), 2),
                "cost_pln_total": round(cost, 4), "cost_pln_per_accepted": round(cost / yes, 4) if yes else None}
    return {"pairs": len(pairs), "baseline": summary(baseline), "candidate": summary(candidate),
            "paired_gain_pp": round(statistics.mean(diffs), 2),
            "bootstrap_95pct_ci_pp": [round(estimates[49], 2), round(estimates[1949], 2)],
            "note": "observational unless task sampling, model and budget are experimentally controlled"}


def evaluate_horizon(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    chains = defaultdict(list)
    for r in rows:
        key = (r.get("chain_id"), r.get("variant"))
        if not isinstance(r.get("step"), int) or type(r.get("passed")) is not bool or r["step"] < 1:
            raise ResearchPolicyError("invalid chain step")
        chains[key].append((r["step"], r["passed"]))
    if not chains:
        raise ResearchPolicyError("no chains")
    result = defaultdict(lambda: {"chains": 0, "fully_solved": 0, "steps": 0, "passed_steps": 0})
    for (_, variant), values in chains.items():
        ordered = sorted(values)
        if [n for n, _ in ordered] != list(range(1, len(ordered) + 1)):
            raise ResearchPolicyError("noncontinuous or duplicate steps")
        a = result[variant]
        a["chains"] += 1; a["fully_solved"] += int(all(x for _, x in ordered))
        a["steps"] += len(ordered); a["passed_steps"] += sum(x for _, x in ordered)
    for v in result.values():
        v["chain_success_pct"] = round(100 * v["fully_solved"] / v["chains"], 2)
        v["step_success_pct"] = round(100 * v["passed_steps"] / v["steps"], 2)
    return dict(result)


def json_lines(path: Path) -> list[dict[str, Any]]:
    if path.stat().st_size > 2_000_000:
        raise ResearchPolicyError("results file too large")
    return [json.loads(s) for s in path.read_text(encoding="utf-8").splitlines() if s.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Research foundation: OFFLINE / no code execution")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("catalog"); p.add_argument("path", type=Path)
    p = sub.add_parser("index"); p.add_argument("root", type=Path); p.add_argument("query")
    p = sub.add_parser("pairs"); p.add_argument("results", type=Path)
    p = sub.add_parser("horizon"); p.add_argument("results", type=Path)
    p = sub.add_parser("gate"); p.add_argument("manifest", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "catalog": result = catalog_summary(args.path)
        elif args.command == "index": result = index_repository(args.root, args.query)
        elif args.command == "pairs": result = evaluate_pairs(json_lines(args.results))
        elif args.command == "horizon": result = evaluate_horizon(json_lines(args.results))
        elif args.command == "gate":
            manifest = _load_json(args.manifest)
            result = gate_patch(**manifest)
        else: raise ResearchPolicyError("unknown command")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ResearchPolicyError, ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
