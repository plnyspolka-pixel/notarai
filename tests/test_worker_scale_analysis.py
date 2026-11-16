"""Aggregation unit tests with synthetic, not model-generated, summary rows."""
import json
from pathlib import Path
import pytest
from tools.agent_factory.worker_scale_analysis import combine
from tools.agent_factory.worker_scale_corpus import (
    FAMILIES, VERSION, tasks
)


def fixture(tmp_path: Path, *, per_family: int = 2) -> Path:
    source = {t["id"]:t for t in tasks("development")
              if t["variant"]<per_family}
    for shard in range(5):
        path=tmp_path/f"shard-{shard}"
        path.mkdir()
        rows=[]
        for t in source.values():
            if FAMILIES.index(t["family"])//2!=shard:
                continue
            for arm in ("plain","structured"):
                passed=arm=="structured" or t["variant"]==0
                rows.append({
                    "task_id":t["id"],"family":t["family"],
                    "split":"development","task_sha256":t["task_sha256"],
                    "arm":arm,"accepted":passed,"tests":8,
                    "passed_tests":8 if passed else 3,
                    "failure_category":"none" if passed else "wrong_behavior",
                    "elapsed_s":8.0,"prompt_tokens":100,"completion_tokens":40,
                })
        (path/"results.json").write_text(json.dumps({
            "status":"ACTUAL_CPU_MODEL_AB_SYNTHETIC_NOT_TRAINING",
            "suite":VERSION,"model":"test-model","shard":shard,
            "split":"development","per_family":per_family,
            "weight_training":False,"benchmark_evaluation_not_training":True,
            "premium_claude_codex_calls":0,"gpu_calls":0,"results":rows
        }))
    return tmp_path


def test_aggregator_preserves_ten_family_uncertainty(tmp_path):
    report=combine(fixture(tmp_path))
    assert report["parameterized_contracts"]==20
    assert report["actual_model_calls"]==40
    assert report["independent_algorithm_families"]==10
    assert report["arms"]["plain"]["accepted"]==10
    assert report["arms"]["structured"]["accepted"]==20
    assert report["training_eligible"] is False
    assert report["family_cluster_bootstrap_95pct"]==[0.5,0.5]


def test_rejects_missing_shard(tmp_path):
    fixture(tmp_path)
    (tmp_path/"shard-4/results.json").unlink()
    with pytest.raises(ValueError):
        combine(tmp_path)


def test_rejects_fabricated_score_or_duplicate(tmp_path):
    fixture(tmp_path)
    path=tmp_path/"shard-0/results.json"
    report=json.loads(path.read_text())
    report["results"][0]["passed_tests"]=55
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError):
        combine(tmp_path)
