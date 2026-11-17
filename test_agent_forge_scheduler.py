"""Scheduler concurrency, expiry, idempotency and circuit breaker tests."""
from pathlib import Path
import pytest

from tools.agent_factory.forge_core import ForgeError, RunStore
from tools.agent_factory.forge_scheduler import JobQueue, tick
from tools.agent_factory.forge_scheduler_cli import main

FIXTURES = Path(__file__).resolve().parent / "docs" / "agent-factory-research" / "fixtures"


def test_single_job_end_to_end(tmp_path):
    with JobQueue(tmp_path / "queue.db") as q, RunStore(tmp_path / "runs.db") as r:
        assert q.submit("job-fixture-001", "sum-task.json", "sum-rubric.json")
        assert not q.submit("job-fixture-001", "sum-task.json", "sum-rubric.json")
        result = tick(q, r, FIXTURES)
        assert result["status"] == "completed"
        assert result["audit_valid"]
        assert q.status()["counts"]["completed"] == 1
        assert tick(q, r, FIXTURES)["status"] == "idle-or-paused"


def test_idempotency_conflict(tmp_path):
    with JobQueue(tmp_path / "queue.db") as q:
        q.submit("job-fixture-002", "sum-task.json", "sum-rubric.json")
        with pytest.raises(ForgeError, match="conflict"):
            q.submit("job-fixture-002", "max-task.json", "max-rubric.json")


def test_pause_prevents_claim_and_completion(tmp_path):
    with JobQueue(tmp_path / "queue.db") as q:
        q.submit("job-fixture-003", "sum-task.json", "sum-rubric.json")
        q.set_paused(True)
        assert q.claim() is None
        q.set_paused(False)
        lease = q.claim()
        assert lease is not None
        q.set_paused(True)
        with pytest.raises(ForgeError):
            q.finish(lease["job_id"], lease["lease_token"], True)
        q.set_paused(False)
        q.finish(lease["job_id"], lease["lease_token"], True)


def test_expired_lease_reclaim_and_dead_letter(tmp_path, monkeypatch):
    import tools.agent_factory.forge_scheduler as module
    monkeypatch.setattr(module.time, "time", lambda: 100.0)
    with JobQueue(tmp_path / "queue.db") as q:
        q.submit("job-fixture-004", "sum-task.json", "sum-rubric.json",
                 max_attempts=2)
        first = q.claim(lease_seconds=5)
        monkeypatch.setattr(module.time, "time", lambda: 106.0)
        reclaimed = q.claim(lease_seconds=5)
        assert reclaimed["attempt"] == 2
        assert first["lease_token"] != reclaimed["lease_token"]
        with pytest.raises(ForgeError):
            q.finish(first["job_id"], first["lease_token"], True)
        monkeypatch.setattr(module.time, "time", lambda: 112.0)
        assert q.claim(lease_seconds=5) is None
        assert q.status()["counts"]["dead"] == 1


def test_cancellation_revokes_lease(tmp_path):
    with JobQueue(tmp_path / "queue.db") as q:
        q.submit("job-fixture-005", "sum-task.json", "sum-rubric.json")
        lease = q.claim()
        assert q.cancel("job-fixture-005")
        assert not q.cancel("job-fixture-005")
        with pytest.raises(ForgeError):
            q.finish(lease["job_id"], lease["lease_token"], True)


def test_queue_rejects_untrusted_filenames_and_attempts(tmp_path):
    with JobQueue(tmp_path / "queue.db") as q:
        for name in ("../.env", "folder/task.json", "secrets.txt"):
            with pytest.raises(ForgeError):
                q.submit("job-fixture-006", name, "sum-rubric.json")
        for attempts in (0, -1, 4, True):
            with pytest.raises(ForgeError):
                q.submit("job-fixture-007", "sum-task.json", "sum-rubric.json",
                         max_attempts=attempts)


def test_second_connection_cannot_claim_same_job(tmp_path):
    path = tmp_path / "queue.db"
    with JobQueue(path) as q1, JobQueue(path) as q2:
        q1.submit("job-fixture-008", "sum-task.json", "sum-rubric.json")
        first = q1.claim()
        assert q2.claim() is None
        q1.finish(first["job_id"], first["lease_token"], True)
        assert q2.status()["counts"]["completed"] == 1


def test_failure_marks_job_failed_and_does_not_retry(tmp_path):
    with JobQueue(tmp_path / "queue.db") as q, RunStore(tmp_path / "runs.db") as r:
        q.submit("job-fixture-009", "sum-task.json", "max-rubric.json")
        result = tick(q, r, FIXTURES)
        assert result["status"] == "failed"
        assert q.status()["counts"]["failed"] == 1
        assert q.claim() is None


def test_queue_cli_commands(tmp_path):
    base = ["--queue", str(tmp_path / "q.db"), "--runs", str(tmp_path / "r.db")]
    assert main(base + ["submit", "--job-id", "job-fixture-010"]) == 0
    assert main(base + ["pause"]) == 0
    assert main(base + ["tick"]) == 0
    assert main(base + ["resume"]) == 0
    assert main(base + ["tick"]) == 0
    assert main(base + ["list"]) == 0
