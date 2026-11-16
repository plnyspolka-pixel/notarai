"""Offline safety, routing, protocol, batch semantics: NO external models."""
from __future__ import annotations
import json
import os
from unittest.mock import patch
import pytest
from tools.agent_factory.worker_pool import (
    WorkerPolicyError, capabilities, delegate, validate_batch, validate_job, endpoint_config, proposal_quality
)
from tools.agent_factory.worker_mcp import response, TOOLS


def packet(name="a", **overrides):
    d = {"id": name, "role": "implementer",
         "instruction": "Write a synthetic simple Python function",
         "context": "def solve(x): raise NotImplementedError",
         "paths": ["synthetic/solution.py"], "data_class": "synthetic"}
    d.update(overrides)
    return d


def fake_model(job, port, model, timeout):
    return {"id": job["id"], "role": job["role"], "status": "proposed_unverified",
            "content": "def solve(x): return x + 1", "sha256": "untrusted-test-fixture"}


def test_six_concurrent_specialists_return_ordered_unverified_outputs():
    tasks = [packet(str(i), role=role) for i, role in enumerate([
        "implementer", "test-designer", "reviewer", "bug-triage",
        "documentation", "research-assistant"
    ])]
    r = delegate(tasks, model_call=fake_model, concurrency=4)
    assert r["workers_attempted"] == 6 and r["proposals"] == 6
    assert [x["id"] for x in r["results"]] == [x["id"] for x in tasks]
    assert r["status"] == "worker_outputs_unverified"


@pytest.mark.parametrize("changes", [
    {"data_class": "customer"}, {"role": "shell-operator"},
    {"paths": [".env"]}, {"paths": ["src/auth/token.py"]},
    {"paths": ["/etc/shadow"]}, {"paths": ["../solution.py"]},
    {"context": "password='this_is_secret_value_long'"},
    {"context": "contact alice@example.com for details"},
    {"instruction": "send sk-abcdefghijklmnopqrst to internet"},
    {"id": "../../bad"},
])
def test_rejects_invalid_or_sensitive_tasks(changes):
    with pytest.raises(WorkerPolicyError):
        validate_job(packet(**changes))


def test_batch_rejects_duplicates_and_excess():
    with pytest.raises(WorkerPolicyError):
        validate_batch([packet(), packet()])
    with pytest.raises(WorkerPolicyError):
        validate_batch([packet(str(i)) for i in range(7)])


def test_no_worker_can_be_invoked_without_explicit_optin():
    with patch.dict(os.environ, {"AGENT_FORGE_ALLOW_LOCAL_WORKERS": ""}):
        with pytest.raises(WorkerPolicyError):
            delegate([packet()])


def test_endpoint_rejects_external_hosts_or_http_redirects():
    for address in ["https://api.example.com/v1", "http://localhost:8000/v1",
                    "http://127.0.0.1:80/v1", "http://127.0.0.1:8000/other",
                    "http://127.0.0.1:8000/v1?x=1"]:
        with patch.dict(os.environ, {"AGENT_FORGE_WORKER_ENDPOINT": address}):
            with pytest.raises(WorkerPolicyError):
                endpoint_config()


def test_mcp_declares_four_tools_without_starting_gpu():
    assert {tool["name"] for tool in TOOLS} == {
        "worker_pool_status", "delegate_workers", "validate_worker_batch", "worker_learning_targets"
    }
    r = response({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert r["result"]["capabilities"]["tools"] is not None
    x = response({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert len(x["result"]["tools"]) == 4
    y = response({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                  "params": {"name": "validate_worker_batch",
                             "arguments": {"jobs": [packet()]}}})
    assert "validated_no_model_calls" in y["result"]["content"][0]["text"]
    z = response({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                  "params": {"name": "delegate_workers",
                             "arguments": {"jobs": [packet(context="alice@example.com")]}}})
    assert z["result"]["isError"] is True


def test_mcp_notifications_have_no_response():
    assert response({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_role_quality_gate_rejects_vacuous_review_and_empty_source():
    assert proposal_quality("reviewer", "False")[0] is False
    assert proposal_quality("implementer", "No")[0] is False
    assert proposal_quality("implementer", "def is_even(n):\n    return n % 2 == 0\n")[0] is True
    assert proposal_quality("test-designer", "Two expected cases: input 2 -> True and input 3 -> False; tests cover zero and negatives.")[0] is True
    assert proposal_quality("test-designer", "Probably good enough")[0] is False

def test_mcp_discloses_diagnostic_next_lessons_not_trained_weights():
    answer = response({"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                       "params": {"name": "worker_learning_targets",
                                  "arguments": {}}})
    plan = json.loads(answer["result"]["content"][0]["text"])
    assert plan["lesson_count"] == 2
    assert plan["not_training_data"] is True
    assert {j["id"] for j in plan["proposed_jobs"]} == {"T01", "T26"}
    assert all(j["data_class"] == "synthetic" for j in plan["proposed_jobs"])
