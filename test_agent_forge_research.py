"""Reproducibility, statistical and policy tests; no external model or network."""
import copy
import json
from pathlib import Path
import pytest

from tools.agent_factory.forge_core import ForgeError
from tools.agent_factory.forge_research_stats import (
    validate_experiment, read_experiment, exact_two_sided_sign_test,
    bootstrap_task_delta, compare_paired,
)
from tools.agent_factory.forge_research_cli import main

DEMO = Path(__file__).resolve().parent / "docs" / "agent-factory-research" / "fixtures" / "paired-research-demo.json"


def make_data():
    return json.loads(DEMO.read_text(encoding="utf-8"))


def test_demo_does_not_assert_real_model_superiority():
    result = compare_paired(make_data())
    assert result["provenance_source"] == "synthetic_demo"
    assert result["interpretation"] == "exploratory_only"
    assert result["promotion_authorized"] is False
    assert result["paired_observations"] == 8
    assert result["task_clusters"] == 4
    assert 0 <= result["task_level_exact_sign_test_p"] <= 1


def test_exact_sign_test():
    assert exact_two_sided_sign_test(3, 0) == pytest.approx(0.25)
    assert exact_two_sided_sign_test(2, 2) == 1.0
    assert exact_two_sided_sign_test(0, 0) == 1.0
    assert exact_two_sided_sign_test(10, 0) == pytest.approx(2 / 1024)


def test_bootstrap_reproducible_across_calls():
    data = make_data()
    by_task = {}
    for row in data["observations"]:
        by_task.setdefault(row["task_id"], []).append(row)
    assert bootstrap_task_delta(by_task) == bootstrap_task_delta(by_task)


def test_cluster_bootstrap_constant_effect():
    grouped = {
        f"t-{i:03d}": [{
            "baseline_success": False, "candidate_success": True
        }] for i in range(10)
    }
    assert bootstrap_task_delta(grouped) == (1.0, 1.0)


def test_duplicate_task_seed_rejected():
    data = make_data()
    data["observations"].append(copy.deepcopy(data["observations"][0]))
    with pytest.raises(ForgeError, match="Duplicate"):
        validate_experiment(data)


@pytest.mark.parametrize("field,value", [
    ("baseline_success", 1),
    ("candidate_cost_cents", -1),
    ("seed", True),
    ("candidate_policy_violations", -1),
    ("candidate_latency_ms", "150"),
])
def test_metrics_types_rejected(field, value):
    data = make_data()
    data["observations"][0][field] = value
    with pytest.raises(ForgeError):
        compare_paired(data)


def test_provenance_must_have_real_hashes_and_distinct_models():
    data = make_data()
    data["provenance"]["dataset_sha256"] = "unknown"
    with pytest.raises(ForgeError):
        compare_paired(data)
    data = make_data()
    data["provenance"]["candidate_id"] = data["provenance"]["baseline_id"]
    with pytest.raises(ForgeError):
        compare_paired(data)


def test_no_arbitrary_fields_or_text_payloads():
    data = make_data()
    data["observations"][0]["raw_prompt"] = "Sensitive private source text"
    with pytest.raises(ForgeError):
        compare_paired(data)


def test_safety_regression_never_promotes():
    data = make_data()
    data["provenance"]["source"] = "measured"
    data["observations"][0]["candidate_policy_violations"] = 1
    result = compare_paired(data)
    assert result["safety_regression"]
    assert result["promotion_authorized"] is False


def test_small_n_remains_exploratory_even_measured():
    data = make_data()
    data["provenance"]["source"] = "measured"
    assert compare_paired(data)["interpretation"] == "exploratory_only"


def test_read_file_symlink_and_size_denied(tmp_path):
    alias = tmp_path / "sample.json"
    alias.symlink_to(DEMO)
    with pytest.raises(ForgeError):
        read_experiment(alias)
    too_big = tmp_path / "too-big.json"
    too_big.write_text("x" * 500001)
    with pytest.raises(ForgeError):
        read_experiment(too_big)


def test_zero_cost_does_not_imply_actual_model_run():
    data = make_data()
    result = compare_paired(data)
    assert result["provenance_source"] == "synthetic_demo"
    assert result["baseline_cost_cents"] == 0


def test_cli_reports_json(capsys):
    assert main([]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["interpretation"] == "exploratory_only"

@pytest.mark.parametrize("key,value", [
    ("source", ["synthetic_demo"]),
    ("split", {"holdout": True}),
    ("source", None),
])
def test_unhashable_or_invalid_metadata_is_rejected(key, value):
    data = make_data()
    data["provenance"][key] = value
    with pytest.raises(ForgeError):
        compare_paired(data)
