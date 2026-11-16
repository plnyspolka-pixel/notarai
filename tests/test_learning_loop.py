"""Offline proof that training examples require trusted checks and no PII."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import pytest

from tools.agent_factory.learning_loop import (
    WorkerPolicyError, export_training_data, signature, verify_record,
)

KEY = b"a-test-evidence-key-separated-from-worker-context"


def record(n, family, role="implementer", **changes):
    answer = f"def solve(x): return x + {n}\n"
    r = {
        "schema_version": 1, "task_id": f"synthetic_{n}", "task_family": family,
        "role": role, "instruction": "Implement the requested synthetic Python function",
        "context": "The function accepts a synthetic integer and returns an integer.",
        "accepted_answer": answer, "base_commit": "a" * 40,
        "verifier_name": "external-isolated-verifier",
        "verifier_passed": True, "reviewer_approved": True,
        "candidate_sha256": hashlib.sha256(answer.encode()).hexdigest(),
        "data_class": "synthetic", "signature": "0" * 64,
    }
    r.update(changes)
    r["signature"] = signature(r, KEY)
    return r


def test_export_frozen_training_and_holdout_without_family_leakage(tmp_path):
    source = tmp_path / "trusted.jsonl"
    examples = [record(i, f"family_{i // 4}") for i in range(24)]
    source.write_text("".join(json.dumps(x) + "\n" for x in examples))
    out = tmp_path / "training"
    stats = export_training_data(source, out, KEY)
    assert stats["train"] + stats["holdout"] == 24
    a = [json.loads(line) for line in (out / "train.jsonl").read_text().splitlines()]
    b = [json.loads(line) for line in (out / "holdout.jsonl").read_text().splitlines()]
    assert {x["task_family"] for x in a}.isdisjoint(
        {x["task_family"] for x in b})
    assert all(x["messages"][2]["role"] == "assistant" for x in a + b)
    with pytest.raises(WorkerPolicyError):
        export_training_data(source, out, KEY)


def test_rejects_forged_signature():
    r = record(1, "family_0")
    r["accepted_answer"] += "\n# manipulated"
    with pytest.raises(WorkerPolicyError):
        verify_record(r, KEY)


@pytest.mark.parametrize("changes", [
    {"verifier_passed": False}, {"reviewer_approved": False},
    {"data_class": "private"}, {"verifier_name": "self-reported"},
    {"context": "alice@example.com"},
    {"accepted_answer": "sk-abcdefghijklmnopqrst"},
    {"base_commit": "notsha"}, {"candidate_sha256": "0" * 64},
])
def test_rejects_untrusted_examples(changes):
    with pytest.raises(WorkerPolicyError):
        verify_record(record(1, "family_0", **changes), KEY)


def test_rejects_short_signing_key():
    with pytest.raises(WorkerPolicyError):
        signature(record(1, "family_0"), b"short")
