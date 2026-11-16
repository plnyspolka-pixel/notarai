import json
from pathlib import Path
import pytest
from tools.agent_factory.research_foundation import (
    EvidenceLedger, ResearchPolicyError, catalog_summary, evaluate_horizon,
    evaluate_pairs, freeze_test_plan, gate_patch, index_repository, load_studies,
)

SHA = "a" * 40
PLAN = {"classification": "synthetic", "tests": [{"id": "t1"}, {"id": "t2"}]}


def test_catalog_100_uniqueness(tmp_path):
    content = [{"identifier": "2609.09133", "source": "https://arxiv.org/abs/2609.09133", "category": "testing", "numeric_findings": "11.4 pp"}]
    path = tmp_path / "papers.json"
    path.write_text(json.dumps({"studies": content}))
    assert catalog_summary(path)["count"] == 1
    content.append(content[0]); path.write_text(json.dumps(content))
    with pytest.raises(ResearchPolicyError): load_studies(path)


def test_catalog_invalid_url(tmp_path):
    p = tmp_path / "papers.jsonl"
    p.write_text('{"identifier":"2609.09133","source":"https://evil.example/abs/2609.09133"}')
    with pytest.raises(ResearchPolicyError): load_studies(p)


def test_index_ast_typescript_and_no_secret_text(tmp_path):
    (tmp_path / "app.py").write_text("def evaluate_agent():\n    return 5\n")
    (tmp_path / "lib.ts").write_text("export function evaluateMetric() {}")
    (tmp_path / ".env").write_text("evaluate_agent=secret")
    (tmp_path / "dane").mkdir()
    (tmp_path / "dane" / "secret.py").write_text("def evaluate_agent(): pass")
    results = index_repository(tmp_path, "evaluate agent")
    assert {r["file"] for r in results} == {"app.py", "lib.ts"}
    assert all("secret" not in json.dumps(r) for r in results)


def test_index_skips_symlink(tmp_path):
    (tmp_path / "secret.py").write_text("def hidden_index(): pass")
    (tmp_path / "linked.py").symlink_to(tmp_path / "secret.py")
    files = index_repository(tmp_path, "hidden index")
    assert [r["file"] for r in files] == ["secret.py"]


def test_ledger_stale_after_file_change_and_commit(tmp_path):
    source = tmp_path / "src.py"; source.write_text("print(1)")
    with EvidenceLedger(tmp_path / "memory.db", tmp_path) as ledger:
        ledger.record(SHA, "src.py", "bug-location", "line:1")
        assert ledger.recall(SHA)[0]["valid"]
        assert ledger.recall("b" * 40) == []
        source.write_text("print(2)")
        assert ledger.recall(SHA) == []
        assert ledger.recall(SHA, include_stale=True)[0]["status"] == "stale-needs-revalidation"


def test_ledger_rejects_secrets_and_links(tmp_path):
    (tmp_path / ".env").write_text("API_KEY=whatever")
    (tmp_path / "code.py").write_text("print(1)")
    (tmp_path / "link.py").symlink_to(tmp_path / "code.py")
    with EvidenceLedger(tmp_path / "db.sqlite3", tmp_path) as ledger:
        for path in (".env", "../etc/passwd", "link.py"):
            with pytest.raises(ResearchPolicyError):
                ledger.record(SHA, path, "decision", "safe")
        with pytest.raises(ResearchPolicyError):
            ledger.record(SHA, "code.py", "decision", "PESEL 12345678901")


def test_freeze_plan_prevents_mutation():
    digest = freeze_test_plan(PLAN)
    good = gate_patch(plan=PLAN, expected_digest=digest, changed_paths=["src/code.py"],
                      test_results=[{"id": "t1", "passed": True}, {"id": "t2", "passed": True}],
                      review_criteria={"contract": True, "lint": True})
    assert good["accepted"]
    tampered = {**PLAN, "tests": [{"id": "fake"}]}
    bad = gate_patch(plan=tampered, expected_digest=digest, changed_paths=["src/code.py"],
                     test_results=[{"id": "fake", "passed": True}], review_criteria={"contract": True})
    assert "frozen-plan-integrity" in bad["reasons"]


def test_gate_deny_sensitive_patch_without_approval():
    d = freeze_test_plan(PLAN)
    params = dict(plan=PLAN, expected_digest=d, changed_paths=["infra/iam.yaml"],
                  test_results=[{"id": "t1", "passed": True}, {"id": "t2", "passed": True}],
                  review_criteria={"security": True})
    assert not gate_patch(**params)["accepted"]
    assert gate_patch(**params, approval=True)["accepted"]


def test_gate_review_and_test_failures_are_fail_closed():
    d = freeze_test_plan(PLAN)
    res = gate_patch(plan=PLAN, expected_digest=d, changed_paths=["src/hello.py"],
        test_results=[{"id": "t1", "passed": True}], review_criteria={"security": False})
    assert set(res["reasons"]) == {"tests-missing-or-failed", "review-criteria-unmet"}


def test_gate_rejects_relative_escape():
    d = freeze_test_plan(PLAN)
    res = gate_patch(plan=PLAN, expected_digest=d, changed_paths=["../../secrets"],
                     test_results=[{"id": "t1", "passed": True}, {"id": "t2", "passed": True}],
                     review_criteria={"contract": True})
    assert not res["accepted"]


def test_paired_bootstrap_determinism_and_cost():
    rows = []
    for i in range(10):
        for variant in ("baseline", "candidate"):
            rows.append({"task_id": f"task{i}", "base_commit": SHA, "variant": variant,
                         "replicate": 0, "accepted": i < (3 if variant == "baseline" else 6),
                         "cost_pln": 1.0 if variant == "baseline" else 1.4})
    a = evaluate_pairs(rows)
    assert a == evaluate_pairs(rows)
    assert a["paired_gain_pp"] == 30
    assert a["candidate"]["cost_pln_per_accepted"] > 0


def test_paired_missing_variant_rejected():
    with pytest.raises(ResearchPolicyError):
        evaluate_pairs([{"task_id": "task", "base_commit": SHA, "variant": "baseline", "accepted": True, "cost_pln": 1}])


def test_horizon_chain_not_single_task():
    rows = [{"chain_id": "A", "variant": "candidate", "step": i, "passed": i < 3} for i in range(1, 6)]
    result = evaluate_horizon(rows)
    assert result["candidate"]["chain_success_pct"] == 0
    assert result["candidate"]["step_success_pct"] == 40


def test_horizon_rejects_gap():
    with pytest.raises(ResearchPolicyError):
        evaluate_horizon([{"chain_id": "A", "variant": "candidate", "step": 2, "passed": True}])
