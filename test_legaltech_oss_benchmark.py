"""Offline tests. Test fixtures contain only fictional identities and numbers."""

import json
from pathlib import Path

import pytest

from tools.legaltech_oss import benchmark as b

CORPUS = Path(__file__).parent / "tools" / "legaltech_oss" / "synthetic_cases.json"


def _cases():
    return b.load_corpus(CORPUS)


def _clean_output(case):
    result = case["text"]
    for i, secret in enumerate(case["secrets"]):
        result = result.replace(secret["value"], f"[REDACTED_{i}]")
    return result


def _write_outputs(folder: Path, cases):
    folder.mkdir()
    for c in cases:
        (folder / f"{c['id']}.txt").write_text(_clean_output(c), encoding="utf-8")


def test_corpus_is_declared_synthetic_and_complete():
    cases = _cases()
    assert len(cases) >= 20
    assert sum(len(x["secrets"]) for x in cases) >= 20
    assert {"NAME", "PESEL", "NIP", "REGON", "KW", "IBAN", "EMAIL", "ADDRESS"} <= {
        secret["kind"] for c in cases for secret in c["secrets"]
    }
    assert any(not c["secrets"] for c in cases)


def test_clean_mock_is_review_required_not_approved(tmp_path):
    cases = _cases()
    outputs = tmp_path / "out"
    _write_outputs(outputs, cases)
    scored = b.score_cases(cases, outputs)
    assert scored["status"] == "REVIEW_REQUIRED"
    assert scored["production_approved"] is False
    assert scored["leaked_markers"] == 0
    assert not scored["case_ids_with_failures"]


def test_exact_name_leak_fails(tmp_path):
    cases = _cases()
    outputs = tmp_path / "out"
    _write_outputs(outputs, cases)
    (outputs / "person_nominative.txt").write_text(
        next(c["text"] for c in cases if c["id"] == "person_nominative"), encoding="utf-8"
    )
    scored = b.score_cases(cases, outputs)
    assert scored["status"] == "FAIL"
    assert scored["leaked_markers_by_kind"]["NAME"] >= 1
    assert "person_nominative" in scored["case_ids_with_failures"]


def test_structured_identifier_with_changed_spacing_is_still_leak():
    marker = {"kind": "PESEL", "value": "99923100014"}
    assert b.is_leaked(marker, "PESEL 999 231-000 14")
    marker = {"kind": "KW", "value": "LU1I/99999999/6"}
    assert b.is_leaked(marker, "KW LU1I 99999999 6")
    marker = {"kind": "IBAN", "value": "PL14 9999 9999 0000 0000 0000 0001"}
    assert b.is_leaked(marker, "PL14999999990000000000000001")


def test_non_sensitive_label_not_counted_as_identifier():
    assert not b.is_leaked({"kind": "PESEL", "value": "99923100014"}, "PESEL [REDACTED]")


def test_preservation_failure_detected(tmp_path):
    cases = _cases()
    outputs = tmp_path / "out"
    _write_outputs(outputs, cases)
    (outputs / "negative_control.txt").write_text("[REDACTED ALL]", encoding="utf-8")
    scored = b.score_cases(cases, outputs)
    assert "negative_control" in scored["case_ids_with_content_loss"]
    assert scored["status"] == "FAIL"


def test_missing_output_blocks(tmp_path):
    cases = _cases()
    outputs = tmp_path / "out"
    _write_outputs(outputs, cases)
    (outputs / "negative_control.txt").unlink()
    scored = b.score_cases(cases, outputs)
    assert "negative_control" in scored["case_ids_without_output"]
    assert scored["production_approved"] is False


def test_no_literals_in_aggregate_report(tmp_path):
    cases = _cases()
    outputs = tmp_path / "out"
    _write_outputs(outputs, cases)
    (outputs / "person_nominative.txt").write_text(
        next(c["text"] for c in cases if c["id"] == "person_nominative"), encoding="utf-8"
    )
    report = json.dumps(b.score_cases(cases, outputs), ensure_ascii=False)
    for case in cases:
        assert case["text"] not in report
        for secret in case["secrets"]:
            assert secret["value"] not in report


def test_export_uses_regular_files(tmp_path):
    target = tmp_path / "out"
    result = b.export_cases(_cases(), target)
    assert result["synthetic_cases_exported"] == len(_cases())
    assert len(list(target.glob("*.txt"))) == len(_cases())
    with pytest.raises(b.BenchmarkError):
        b.export_cases(_cases(), target)


def test_reject_non_synthetic_corpus(tmp_path):
    path = tmp_path / "input.json"
    path.write_text(json.dumps({"cases": _cases()}), encoding="utf-8")
    with pytest.raises(b.BenchmarkError):
        b.load_corpus(path)


def test_reject_path_traversal_in_case_id(tmp_path):
    obj = {"synthetic_only": True, "cases": [{
        "id": "../unsafe", "text": "Sample", "secrets": [], "must_preserve": ["Sample"],
    }]}
    path = tmp_path / "input.json"
    path.write_text(json.dumps(obj), encoding="utf-8")
    with pytest.raises(b.BenchmarkError):
        b.load_corpus(path)


def test_reject_secret_not_present_in_source(tmp_path):
    obj = {"synthetic_only": True, "cases": [{
        "id": "test", "text": "Sample", "secrets": [{"kind": "NAME", "value": "Other"}],
        "must_preserve": [],
    }]}
    path = tmp_path / "input.json"
    path.write_text(json.dumps(obj), encoding="utf-8")
    with pytest.raises(b.BenchmarkError):
        b.load_corpus(path)


def test_output_symlink_rejected(tmp_path):
    cases = _cases()
    outputs = tmp_path / "out"
    _write_outputs(outputs, cases)
    output = outputs / "person_nominative.txt"
    output.unlink()
    output.symlink_to(tmp_path / "does-not-exist")
    with pytest.raises(b.BenchmarkError):
        b.score_cases(cases, outputs)


def test_cli_returns_failure_without_echoing_source(tmp_path, capsys):
    cases = _cases()
    outputs = tmp_path / "out"
    _write_outputs(outputs, cases)
    (outputs / "person_nominative.txt").write_text(
        next(c["text"] for c in cases if c["id"] == "person_nominative"), encoding="utf-8"
    )
    assert b.main(["score", "--corpus", str(CORPUS), "--dir", str(outputs)]) == 2
    out = capsys.readouterr().out
    assert "Alicja Testowska" not in out
    assert '"status": "FAIL"' in out


def test_cli_export_and_score(tmp_path, capsys):
    cases = _cases()
    target = tmp_path / "source"
    assert b.main(["export", "--corpus", str(CORPUS), "--dir", str(target)]) == 0
    outputs = tmp_path / "outputs"
    _write_outputs(outputs, cases)
    assert b.main(["score", "--corpus", str(CORPUS), "--dir", str(outputs)]) == 0


def test_all_upstream_pins_are_real_commit_shapes():
    path = Path(__file__).parent / "tools" / "legaltech_oss" / "upstreams.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["snapshot_date"] == "2026-11-22"
    assert len(data["repositories"]) >= 6
    for entry in data["repositories"]:
        assert len(entry["commit"]) == 40
        assert set(entry["commit"]) <= set("0123456789abcdef")
        assert entry["url"].startswith("https://github.com/")
        assert entry["status"] != "PRODUCTION_APPROVED"
