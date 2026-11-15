"""Loopback-only mock model tests. No real provider or rented GPU."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading

import pytest

from tools.agent_factory.forge_core import ForgeError, RunStore
from tools.agent_factory.forge_llm import (
    LocalModelConfig, OPT_IN_ENV, OPT_IN_VALUE, parse_chat, require_opt_in,
    run_local_model,
)
from tools.agent_factory.forge_benchmark import benchmark_offline, compare_runs

FIXTURES = Path(__file__).resolve().parent / "docs" / "agent-factory-research" / "fixtures"


@pytest.mark.parametrize("url", [
    "http://evil.example:8000/v1", "https://127.0.0.1:8000/v1",
    "http://127.0.0.1.evil.com:8000/v1", "http://localhost:8000/v1",
    "http://name@127.0.0.1:8000/v1", "http://127.0.0.1:8000/admin",
    "http://127.0.0.1:8000/v1?target=external", "file:///etc/passwd",
    "http://127.0.0.1:80/v1", "http://127.0.0.1:8000/v1#fragment",
])
def test_strict_network_boundary(url):
    with pytest.raises(ForgeError):
        LocalModelConfig(model="test-model", endpoint=url).validate()


def test_default_model_access_denied(tmp_path, monkeypatch):
    monkeypatch.delenv(OPT_IN_ENV, raising=False)
    with RunStore(tmp_path / "runs.db") as store:
        with pytest.raises(ForgeError, match="disabled"):
            run_local_model(store, FIXTURES, "mock-001", "sum-task.json",
                            "sum-rubric.json", LocalModelConfig(model="test-model"),
                            operator_opt_in=True)
        assert store.list_runs() == []


def test_both_gates_required(monkeypatch):
    monkeypatch.setenv(OPT_IN_ENV, OPT_IN_VALUE)
    with pytest.raises(ForgeError):
        require_opt_in(False)
    monkeypatch.setenv(OPT_IN_ENV, "1")
    with pytest.raises(ForgeError):
        require_opt_in(True)


def test_strict_response_validation():
    answer, usage = parse_chat({
        "choices": [{"message": {"content": '{"answer":10}'}}],
        "usage": {"prompt_tokens": 8, "completion_tokens": 4},
    })
    assert answer == {"answer": 10} and usage["completion_tokens"] == 4
    for message in [
        {"content": '{"answer":true}'},
        {"content": '{"answer":"10"}'},
        {"content": '{"answer":10,"command":"run"}'},
        {"content": '{"answer":10}', "tool_calls": [{"id": "bad"}]},
        {"content": "Correct answer is 10"},
    ]:
        with pytest.raises(ForgeError):
            parse_chat({"choices": [{"message": message}]})


class MockModel(BaseHTTPRequestHandler):
    calls = 0
    body = {"choices": [{"message": {"content": '{"answer":10}'}}],
            "usage": {"prompt_tokens": 14, "completion_tokens": 5}}

    def do_POST(self):
        assert self.path == "/v1/chat/completions"
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        assert payload["model"] == "test-model"
        assert payload["stream"] is False and "tools" not in payload
        assert payload["max_tokens"] <= 128
        type(self).calls += 1
        raw = json.dumps(type(self).body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *_):
        return


@pytest.fixture
def mock_model_server():
    MockModel.calls = 0
    MockModel.body = {"choices": [{"message": {"content": '{"answer":10}'}}],
                      "usage": {"prompt_tokens": 14, "completion_tokens": 5}}
    server = ThreadingHTTPServer(("127.0.0.1", 0), MockModel)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def test_real_http_protocol_over_loopback_and_idempotency(tmp_path, mock_model_server, monkeypatch):
    monkeypatch.setenv(OPT_IN_ENV, OPT_IN_VALUE)
    config = LocalModelConfig(model="test-model",
                              endpoint="http://127.0.0.1:" + str(mock_model_server.server_port) + "/v1")
    with RunStore(tmp_path / "runs.db") as store:
        first = run_local_model(store, FIXTURES, "mock-002",
                                "sum-task.json", "sum-rubric.json",
                                config, operator_opt_in=True)
        assert first["passed"] and first["audit_valid"]
        assert first["metrics"]["prompt_tokens"] == 14
        assert first["actual_cost_pln"] is None
        replay = run_local_model(store, FIXTURES, "mock-002",
                                 "sum-task.json", "sum-rubric.json",
                                 config, operator_opt_in=True)
        assert replay["replayed"]
        assert MockModel.calls == 1
        summary = compare_runs(store)
        assert summary["groups"]["local-chat-completions"]["cost_pln"] is None


def test_invalid_model_json_fails_closed(tmp_path, mock_model_server, monkeypatch):
    monkeypatch.setenv(OPT_IN_ENV, OPT_IN_VALUE)
    MockModel.body = {"choices": [{"message": {"content": "not-json"}}]}
    config = LocalModelConfig(model="test-model",
                              endpoint="http://127.0.0.1:" + str(mock_model_server.server_port) + "/v1")
    with RunStore(tmp_path / "runs.db") as store:
        with pytest.raises(ForgeError, match="output schema"):
            run_local_model(store, FIXTURES, "mock-003",
                            "sum-task.json", "sum-rubric.json",
                            config, operator_opt_in=True)
        assert store.get("mock-003")["state"] == "failed"
        assert store.verify_events("mock-003")


def test_wrong_answer_marked_failed(tmp_path, mock_model_server, monkeypatch):
    monkeypatch.setenv(OPT_IN_ENV, OPT_IN_VALUE)
    MockModel.body = {"choices": [{"message": {"content": '{"answer":11}'}}]}
    config = LocalModelConfig(model="test-model",
                              endpoint="http://127.0.0.1:" + str(mock_model_server.server_port) + "/v1")
    with RunStore(tmp_path / "runs.db") as store:
        result = run_local_model(store, FIXTURES, "mock-004",
                                 "sum-task.json", "sum-rubric.json",
                                 config, operator_opt_in=True)
        assert result["state"] == "failed" and result["passed"] is False


def test_three_task_offline_benchmark(tmp_path):
    with RunStore(tmp_path / "runs.db") as store:
        result = benchmark_offline(store, FIXTURES, "suite-test")
        again = benchmark_offline(store, FIXTURES, "suite-test")
        assert result["tasks"] == 3 and result["success_rate"] == 1
        assert len(store.list_runs()) == 3
        assert all(item["replayed"] for item in again["runs"])
        assert compare_runs(store)["groups"]["deterministic-fixture"]["passed"] == 3
