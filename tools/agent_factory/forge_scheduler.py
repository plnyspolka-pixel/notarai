"""Agent Forge local job queue with explicit leases, cancellation and stop switch.

This is an offline coordination primitive. It cannot launch LLMs, containers,
GPU instances, external scripts or long-running background processes.
"""
from __future__ import annotations

from pathlib import Path
import sqlite3
import time
import uuid

from tools.agent_factory.forge_core import ForgeError, RUN_ID, FIXTURE_FILE, digest, RunStore, execute_offline


class JobQueue:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path), timeout=10)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA busy_timeout=10000")
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS queue_settings (
                key TEXT PRIMARY KEY, value TEXT NOT NULL
            );
            INSERT OR IGNORE INTO queue_settings(key,value) VALUES ('paused','0');
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                manifest_hash TEXT NOT NULL,
                task_file TEXT NOT NULL, rubric_file TEXT NOT NULL,
                adapter TEXT NOT NULL,
                state TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL,
                lease_token TEXT, lease_deadline REAL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_jobs_state_time
            ON jobs(state, created_at);
        """)
        self.conn.commit()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.conn.close()

    def _now(self) -> float:
        return time.time()

    def paused(self) -> bool:
        row = self.conn.execute(
            "SELECT value FROM queue_settings WHERE key='paused'"
        ).fetchone()
        return row["value"] == "1"

    def set_paused(self, value: bool) -> None:
        if type(value) is not bool:
            raise ForgeError("Pause requires a boolean")
        with self.conn:
            self.conn.execute("UPDATE queue_settings SET value=? WHERE key='paused'",
                              ("1" if value else "0",))

    def submit(self, job_id: str, task_file: str, rubric_file: str,
               *, max_attempts: int = 2) -> bool:
        if not isinstance(job_id, str) or not RUN_ID.fullmatch(job_id):
            raise ForgeError("Invalid job ID")
        if not isinstance(task_file, str) or not FIXTURE_FILE.fullmatch(task_file):
            raise ForgeError("Invalid task filename")
        if not isinstance(rubric_file, str) or not FIXTURE_FILE.fullmatch(rubric_file):
            raise ForgeError("Invalid rubric filename")
        if type(max_attempts) is not int or not 1 <= max_attempts <= 3:
            raise ForgeError("max_attempts must be 1-3")
        manifest = {"job_id": job_id, "task": task_file, "rubric": rubric_file,
                    "adapter": "deterministic-fixture", "max_attempts": max_attempts}
        fingerprint = digest(manifest)
        now = self._now()
        with self.conn:
            existing = self.conn.execute(
                "SELECT manifest_hash FROM jobs WHERE job_id=?", (job_id,)
            ).fetchone()
            if existing:
                if existing["manifest_hash"] != fingerprint:
                    raise ForgeError("Job idempotency conflict")
                return False
            self.conn.execute(
                "INSERT INTO jobs(job_id,manifest_hash,task_file,rubric_file,adapter,"
                "state,max_attempts,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (job_id, fingerprint, task_file, rubric_file, "deterministic-fixture",
                 "queued", max_attempts, now, now),
            )
        return True

    def claim(self, lease_seconds: int = 30) -> dict | None:
        if type(lease_seconds) is not int or not 5 <= lease_seconds <= 300:
            raise ForgeError("Lease must be 5-300 seconds")
        now = self._now()
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            if self.paused():
                self.conn.commit()
                return None
            self.conn.execute(
                "UPDATE jobs SET state='dead',lease_token=NULL,lease_deadline=NULL,"
                "updated_at=? WHERE state='leased' AND lease_deadline<=? "
                "AND attempts>=max_attempts", (now, now)
            )
            row = self.conn.execute(
                "SELECT * FROM jobs WHERE state='queued' OR "
                "(state='leased' AND lease_deadline<=? AND attempts<max_attempts) "
                "ORDER BY created_at,job_id LIMIT 1", (now,)
            ).fetchone()
            if row is None:
                self.conn.commit()
                return None
            token = uuid.uuid4().hex
            self.conn.execute(
                "UPDATE jobs SET state='leased',attempts=attempts+1,"
                "lease_token=?,lease_deadline=?,updated_at=? WHERE job_id=?",
                (token, now + lease_seconds, now, row["job_id"]),
            )
            self.conn.commit()
            return {
                "job_id": row["job_id"], "task_file": row["task_file"],
                "rubric_file": row["rubric_file"], "adapter": row["adapter"],
                "attempt": row["attempts"] + 1, "lease_token": token,
            }
        except BaseException:
            self.conn.rollback()
            raise

    def finish(self, job_id: str, token: str, passed: bool) -> None:
        if type(passed) is not bool:
            raise ForgeError("Result must be a boolean")
        now = self._now()
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            row = self.conn.execute(
                "SELECT state,lease_token,lease_deadline FROM jobs WHERE job_id=?",
                (job_id,),
            ).fetchone()
            if (row is None or self.paused()
                    or row["state"] != "leased"
                    or row["lease_token"] != token
                    or row["lease_deadline"] <= now):
                raise ForgeError("Missing, expired, revoked or paused lease")
            self.conn.execute(
                "UPDATE jobs SET state=?,lease_token=NULL,lease_deadline=NULL,"
                "updated_at=? WHERE job_id=?",
                ("completed" if passed else "failed", now, job_id),
            )
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise

    def cancel(self, job_id: str) -> bool:
        with self.conn:
            updated = self.conn.execute(
                "UPDATE jobs SET state='cancelled',lease_token=NULL,lease_deadline=NULL,"
                "updated_at=? WHERE job_id=? AND state IN ('queued','leased')",
                (self._now(), job_id),
            )
        return updated.rowcount == 1

    def status(self) -> dict:
        rows = self.conn.execute(
            "SELECT state,COUNT(*) AS count FROM jobs GROUP BY state ORDER BY state"
        )
        return {"paused": self.paused(),
                "counts": {row["state"]: row["count"] for row in rows}}

    def list_jobs(self) -> list[dict]:
        return [
            dict(row) for row in self.conn.execute(
                "SELECT job_id,task_file,rubric_file,adapter,state,attempts,max_attempts "
                "FROM jobs ORDER BY created_at,job_id"
            )
        ]


def tick(queue: JobQueue, runs: RunStore, fixtures: Path) -> dict:
    """Consume exactly one offline fixture job (never loops or forks)."""
    lease = queue.claim()
    if lease is None:
        return {"status": "idle-or-paused"}
    if lease["adapter"] != "deterministic-fixture":
        raise ForgeError("Unsupported job adapter")
    try:
        result = execute_offline(
            runs, fixtures, lease["job_id"],
            lease["task_file"], lease["rubric_file"],
        )
        accepted = result["state"] == "completed" and result["passed"] is True
        queue.finish(lease["job_id"], lease["lease_token"], accepted)
        return {"job_id": lease["job_id"], "status": "completed" if accepted else "failed",
                "attempt": lease["attempt"], "audit_valid": result["audit_valid"]}
    except (ForgeError, OSError, ValueError):
        # Never expose source content, response text or user credentials in job errors.
        try:
            queue.finish(lease["job_id"], lease["lease_token"], False)
        except ForgeError:
            pass
        return {"job_id": lease["job_id"], "status": "failed", "error": "worker-failed"}
