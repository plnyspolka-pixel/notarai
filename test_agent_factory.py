"""No external services, cloud credentials or browsers required."""
import argparse
from pathlib import Path

import pytest

from tools.agent_factory.runner import (
    MAX_TASK_BYTES,
    PolicyError,
    codex_command,
    list_tasks,
    load_task,
    restricted_env,
    validate_endpoint,
    validate_model,
)
from tools.agent_factory.browser_smoke import BrowserPolicyError, local_origin


@pytest.mark.parametrize("value", [
    "https://external.example/v1",
    "http://gpu.example:8000/v1",
    "http://127.0.0.1:8000/admin",
    "http://127.0.0.1:8000/v1?token=secret",
    "http://user:pw@localhost:8000/v1",
    "file:///etc/passwd",
])
def test_reject_non_local_endpoints(value):
    with pytest.raises(PolicyError):
        validate_endpoint(value)


def test_allow_local_tunnel():
    assert validate_endpoint("http://127.0.0.1:8000/v1") == "http://127.0.0.1:8000/v1"


def test_model_identifier():
    assert validate_model("qwen3-coder") == "qwen3-coder"
    with pytest.raises(PolicyError):
        validate_model("model; cat /etc/passwd")


def test_command_uses_sandbox_and_no_shell():
    cmd = codex_command("local-model", "http://localhost:8000/v1", "Fix synthetic test")
    assert cmd[:4] == ["codex", "exec", "--sandbox", "workspace-write"]
    assert "sandbox_workspace_write.network_access=false" in cmd
    assert "--dangerously-bypass-approvals-and-sandbox" not in cmd
    assert "Fix synthetic test" in cmd[-1]


def test_task_confined_to_committed_subtree(tmp_path):
    root = tmp_path / "repo"
    tasks = root / "docs" / "agent-tasks"
    tasks.mkdir(parents=True)
    legit = tasks / "sample.md"
    legit.write_text("Write tests on fictional data", encoding="utf-8")
    assert load_task(legit, root).startswith("Write tests")
    other = root / "sensitive.md"
    other.write_text("secrets", encoding="utf-8")
    with pytest.raises(PolicyError):
        load_task(other, root)
    symlink = tasks / "link.md"
    symlink.symlink_to(other)
    with pytest.raises(PolicyError):
        load_task(symlink, root)


def test_list_tasks_skips_symlinks_and_oversized(tmp_path):
    root = tmp_path / "repo"
    tasks = root / "docs" / "agent-tasks"
    tasks.mkdir(parents=True)
    (tasks / "ok.md").write_text("Zadanie syntetyczne", encoding="utf-8")
    (tasks / "huge.md").write_bytes(b"x" * (MAX_TASK_BYTES + 1))
    (tasks / "inne.txt").write_text("nie markdown", encoding="utf-8")
    # Dowiazanie do poprawnego pliku .md tez musi zostac pominiete.
    (tasks / "link.md").symlink_to(tasks / "ok.md")
    assert list_tasks(root) == ["docs/agent-tasks/ok.md"]
    # Brak katalogu: pusta lista, bez bladów.
    assert list_tasks(tmp_path / "brak") == []


def test_env_does_not_forward_credentials(monkeypatch):
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "not-for-workers")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-for-workers")
    monkeypatch.setenv("OPENAI_API_KEY", "not-for-workers")
    env = restricted_env()
    for key in ("AWS_SECRET_ACCESS_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        assert key not in env
    assert env["GIT_TERMINAL_PROMPT"] == "0"


@pytest.mark.parametrize("url", [
    "https://notarai.pl",
    "http://notarai.pl:80",
    "http://127.0.0.1:8000@evil.example/",
    "file:///etc/passwd",
])
def test_browser_origin_restriction(url):
    with pytest.raises(BrowserPolicyError):
        local_origin(url)


def test_browser_local_origin():
    assert local_origin("http://localhost:8000/zdrowie") == "http://localhost:8000"
