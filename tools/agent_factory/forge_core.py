"""Agent Forge foundation: offline, deterministic experiment engine.

No untrusted code execution, GPU allocation, network calls or client data.
This is an experiment control plane, NOT a sandbox or production runner.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Mapping

VERSION = "forge-foundation-v1"
RUN_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{2,63}$")
TASK_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{2,63}$")
FIXTURE_FILE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}\.json$")
HEX256 = re.compile(r"^[a-f0-9]{64}$")
GENESIS = "0" * 64
MAX_FILE_BYTES = 32768


class ForgeError(ValueError):
    """A local experiment violates validation or state policy."""


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_fixture(root: Path, name: str) -> dict[str, Any]:
    """Read ONLY a named JSON file below an explicitly selected fixture root."""
    if not FIXTURE_FILE.fullmatch(name):
        raise ForgeError("Fixture name must be a simple .json filename")
    base = root.resolve(strict=True)
    if not base.is_dir():
        raise ForgeError("Fixture root must be a directory")
    candidate = base / name
    if candidate.is_symlink() or not candidate.is_file():
        raise ForgeError("Fixture not found or is a symlink")
    if candidate.stat().st_size > MAX_FILE_BYTES:
        raise ForgeError("Fixture exceeds size limit")
    try:
        result = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ForgeError("Invalid fixture JSON") from exc
    if not isinstance(result, dict):
        raise ForgeError("Fixture must be a JSON object")
    return result


def validate_task(task: Mapping[str, Any]) -> None:
    """Narrow data format: integers only, so no customer content is accepted."""
    required = {"schema_version", "classification", "task_id", "operation", "values"}
    if set(task) != required:
        raise ForgeError("Task schema fields do not match")
    if task["schema_version"] != 1 or task["classification"] != "synthetic":
        raise ForgeError("Only schema 1 synthetic tasks are allowed")
    if not isinstance(task["task_id"], str) or not TASK_ID.fullmatch(task["task_id"]):
        raise ForgeError("Invalid task ID")
    if task["operation"] not in {"sum_integers", "count_integers", "max_integer"}:
        raise ForgeError("Unapproved fixture operation")
    values = task["values"]
    if not isinstance(values, list) or not 1 <= len(values) <= 128:
        raise ForgeError("Fixture requires 1-128 integers")
    if any(type(n) is not int or abs(n) > 1_000_000 for n in values):
        raise ForgeError("Fixture values must be bounded integers")


def validate_rubric(rubric: Mapping[str, Any], task: Mapping[str, Any]) -> None:
    required = {"schema_version", "task_id", "task_sha256", "assertions"}
    if set(rubric) != required or rubric.get("schema_version") != 1:
        raise ForgeError("Invalid rubric schema")
    if rubric.get("task_id") != task["task_id"] or rubric.get("task_sha256") != digest(task):
        raise ForgeError("Rubric/task integrity mismatch")
    assertions = rubric["assertions"]
    if not isinstance(assertions, list) or not 1 <= len(assertions) <= 16:
        raise ForgeError("Rubric requires 1-16 assertions")
    for item in assertions:
        if not isinstance(item, dict) or set(item) != {"path", "operator", "expected"}:
            raise ForgeError("Invalid assertion")
        if item["path"] != "answer" or item["operator"] != "equals":
            raise ForgeError("Only fixed output equality assertions are supported")
        if type(item["expected"]) is not int:
            raise ForgeError("Expected answer must be an integer")


@dataclass(frozen=True)
class RunPolicy:
    """Policy cannot be overridden from task or rubric content."""
    adapter: str = "deterministic-fixture"
    region: str = "local"
    budget_pln: str = "0"
    classification: str = "synthetic"

    def validate(self) -> None:
        if self.adapter != "deterministic-fixture":
            raise ForgeError("External/model worker adapters are not enabled")
        if self.region != "local" or self.budget_pln != "0":
            raise ForgeError("GPU/cloud spending and non-local execution are disabled")
        if self.classification != "synthetic":
            raise ForgeError("Only synthetic data is permitted")


def fixture_adapter(task: Mapping[str, Any]) -> dict[str, int]:
    """Trusted built-in function, not a shell, model, plugin or sandbox."""
    validate_task(task)
    values = task["values"]
    op = task["operation"]
    if op == "sum_integers":
        result = sum(values)
    elif op == "count_integers":
        result = len(values)
    else:
        result = max(values)
    return {"answer": result}


def independent_evaluate(output: Mapping[str, Any], rubric: Mapping[str, Any]) -> dict[str, Any]:
    """Never executes Python supplied by a task, model or rubric."""
    checks = [{"path": "answer", "passed": type(output.get("answer")) is int
               and output["answer"] == item["expected"]}
              for item in rubric["assertions"]]
    return {
        "passed": all(item["passed"] for item in checks),
        "passed_checks": sum(1 for item in checks if item["passed"]),
        "total_checks": len(checks),
        "failed_paths": [item["path"] for item in checks if not item["passed"]],
    }


class RunStore:
    """SQLite registry and append-only *hash-linked* local audit; not tamper-proof."""
    def __init__(self, filename: Path):
        self.filename = Path(filename)
        self.filename.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.filename), timeout=10)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA busy_timeout=10000")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS runs(
                run_id TEXT PRIMARY KEY, manifest_hash TEXT NOT NULL,
                experiment_id TEXT NOT NULL, task_id TEXT NOT NULL,
                task_hash TEXT NOT NULL, rubric_hash TEXT NOT NULL,
                adapter TEXT NOT NULL, state TEXT NOT NULL,
                result_hash TEXT, passed INTEGER, created_at TEXT NOT NULL,
                finished_at TEXT
            );
            CREATE TABLE IF NOT EXISTS events(
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL REFERENCES runs(run_id),
                ts TEXT NOT NULL, event_type TEXT NOT NULL,
                meta_json TEXT NOT NULL, prev_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL
            );
        """)
        self.conn.commit()

    def __enter__(self) -> "RunStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.conn.close()

    def _event(self, run_id: str, event_type: str, meta: Mapping[str, Any]) -> None:
        last = self.conn.execute(
            "SELECT event_hash FROM events WHERE run_id=? ORDER BY seq DESC LIMIT 1",
            (run_id,),
        ).fetchone()
        prev = last["event_hash"] if last else GENESIS
        ts = utc_now()
        meta_json = canonical(meta)
        event_hash = digest([run_id, ts, event_type, meta_json, prev])
        self.conn.execute(
            "INSERT INTO events(run_id,ts,event_type,meta_json,prev_hash,event_hash) "
            "VALUES(?,?,?,?,?,?)",
            (run_id, ts, event_type, meta_json, prev, event_hash),
        )

    def register(self, manifest: Mapping[str, str]) -> bool:
        run_id = manifest["run_id"]
        if not RUN_ID.fullmatch(run_id):
            raise ForgeError("Invalid run ID")
        fingerprint = digest(manifest)
        with self.conn:
            existing = self.conn.execute(
                "SELECT manifest_hash FROM runs WHERE run_id=?", (run_id,)
            ).fetchone()
            if existing:
                if existing["manifest_hash"] != fingerprint:
                    raise ForgeError("Run ID already exists with different inputs")
                return False
            self.conn.execute(
                "INSERT INTO runs(run_id,manifest_hash,experiment_id,task_id,"
                "task_hash,rubric_hash,adapter,state,created_at)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                (run_id, fingerprint, manifest["experiment_id"], manifest["task_id"],
                 manifest["task_hash"], manifest["rubric_hash"],
                 manifest["adapter"], "registered", utc_now()),
            )
            self._event(run_id, "registered", {"manifest_hash": fingerprint})
        return True

    def transition(self, run_id: str, new_state: str, *,
                   result_hash: str | None = None, passed: bool | None = None) -> None:
        allowed = {"registered": {"running"}, "running": {"completed", "failed"}}
        with self.conn:
            previous = self.conn.execute(
                "SELECT state FROM runs WHERE run_id=?", (run_id,)
            ).fetchone()
            if previous is None or new_state not in allowed.get(previous["state"], set()):
                raise ForgeError("Forbidden run-state transition")
            terminal = new_state in {"completed", "failed"}
            self.conn.execute(
                "UPDATE runs SET state=?,result_hash=?,passed=?,finished_at=? WHERE run_id=?",
                (new_state, result_hash, int(passed) if passed is not None else None,
                 utc_now() if terminal else None, run_id),
            )
            self._event(run_id, new_state, {
                "result_hash": result_hash, "passed": passed
            } if terminal else {})

    def get(self, run_id: str) -> dict[str, Any]:
        row = self.conn.execute(
            "SELECT * FROM runs WHERE run_id=?", (run_id,)
        ).fetchone()
        if row is None:
            raise ForgeError("Run does not exist")
        return dict(row)

    def list_runs(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.conn.execute(
            "SELECT run_id,experiment_id,task_id,adapter,state,passed,created_at,finished_at "
            "FROM runs ORDER BY created_at,run_id"
        )]

    def verify_events(self, run_id: str) -> bool:
        self.get(run_id)
        previous = GENESIS
        rows = self.conn.execute(
            "SELECT ts,event_type,meta_json,prev_hash,event_hash FROM events "
            "WHERE run_id=? ORDER BY seq", (run_id,)
        )
        count = 0
        for row in rows:
            if row["prev_hash"] != previous:
                return False
            if row["event_hash"] != digest([
                run_id, row["ts"], row["event_type"], row["meta_json"], previous
            ]):
                return False
            previous = row["event_hash"]
            count += 1
        return count >= 1


def execute_offline(store: RunStore, root: Path, run_id: str,
                    task_file: str, rubric_file: str,
                    policy: RunPolicy | None = None) -> dict[str, Any]:
    """Run an entire ZERO-COST, no-network experiment using only built-in operations."""
    p = policy if policy is not None else RunPolicy()
    p.validate()
    if not RUN_ID.fullmatch(run_id):
        raise ForgeError("Invalid run ID")
    task = read_fixture(root, task_file)
    validate_task(task)
    rubric = read_fixture(root, rubric_file)
    validate_rubric(rubric, task)
    manifest = {
        "schema": VERSION, "run_id": run_id, "experiment_id": "EXP-01",
        "task_id": task["task_id"], "task_hash": digest(task),
        "rubric_hash": digest(rubric), "adapter": p.adapter,
        "region": p.region, "budget_pln": p.budget_pln,
        "classification": p.classification,
    }
    if not store.register(manifest):
        # Idempotent: no new execution and no additional event.
        return summarize(store, run_id, replayed=True)
    store.transition(run_id, "running")
    output = fixture_adapter(task)
    grade = independent_evaluate(output, rubric)
    store.transition(run_id, "completed" if grade["passed"] else "failed",
                     result_hash=digest(output), passed=grade["passed"])
    result = summarize(store, run_id, replayed=False)
    result.update({"checks_passed": grade["passed_checks"],
                   "checks_total": grade["total_checks"],
                   "failed_paths": grade["failed_paths"]})
    return result


def summarize(store: RunStore, run_id: str, replayed: bool) -> dict[str, Any]:
    record = store.get(run_id)
    return {
        "run_id": run_id, "task_id": record["task_id"], "state": record["state"],
        "passed": None if record["passed"] is None else bool(record["passed"]),
        "result_hash": record["result_hash"],
        "audit_valid": store.verify_events(run_id),
        "replayed": replayed,
        "actual_cost_pln": "0",
        "external_model_calls": 0,
        "external_gpu_calls": 0,
    }


def audit_catalog(path: Path) -> dict[str, Any]:
    """Schema sanity check of existing research catalog; no network/download/install."""
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("entries")
    if data.get("schema_version") != 1 or not isinstance(entries, list):
        raise ForgeError("Invalid catalog schema")
    seen: set[str] = set()
    for item in entries:
        if not isinstance(item, dict):
            raise ForgeError("Malformed catalog entry")
        repo = item.get("repo")
        if not isinstance(repo, str) or not re.fullmatch(
            r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo
        ):
            raise ForgeError("Invalid repository URL")
        if repo in seen:
            raise ForgeError("Duplicate repository")
        seen.add(repo)
        if item.get("priority") not in {"P0", "P1", "P2", "R&D"}:
            raise ForgeError("Unknown priority")
    if data.get("total") != len(entries):
        raise ForgeError("Catalog count does not match entries")
    return {"count": len(entries), "unique": len(seen), "valid": True}
