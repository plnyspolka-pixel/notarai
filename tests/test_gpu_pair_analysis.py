"""Never accept incomplete GPU trial artifacts or invented differences."""
from pathlib import Path
import json
import pytest

from tools.agent_factory.gpu_pair_analysis import aggregate
from tools.agent_factory.worker_scale_runner import select_tasks
from tools.agent_factory.worker_scale_corpus import VERSION


def seed(tmp_path: Path):
    for shard in range(5):
        entries=[]
        for task in select_tasks(shard,1,"development"):
            for model in ("14B","32B"):
                for arm in ("plain","structured"):
                    accepted=(model=="32B" or arm=="structured")
                    entries.append({
                        "task_id":task["id"],"family":task["family"],
                        "task_sha256":task["task_sha256"],"split":"development",
                        "model_size":model,"arm":arm,
                        "accepted":accepted,"cases_passed":8 if accepted else 3,
                        "cases_total":8,"latency_s":2.0,
                        "prompt_tokens":100,"completion_tokens":40,
                    })
        folder=tmp_path/f"shard-{shard}"
        folder.mkdir()
        (folder/"results.json").write_text(json.dumps({
            "status":"REAL_REMOTE_GPU_MODEL_PAIR_EVALUATION_NOT_TRAINING",
            "suite":VERSION,"shard":shard,"split":"development","per_family":1,
            "weight_training":False,"premium_claude_codex_calls":0,
            "model_sizes":["14B","32B"],
            "models":{"14B":"qwen14b","32B":"qwen32b"},
            "rows":entries,
        }))


def test_cross_model_pairs_and_family_bootstrap(tmp_path):
    seed(tmp_path)
    r=aggregate(tmp_path)
    assert r["parameterized_tasks"]==10
    assert r["algorithm_families"]==10
    assert r["actual_model_calls"]==40
    assert r["by_model"]["14B"]["plain"]["accepted"]==0
    assert r["by_model"]["32B"]["plain"]["accepted"]==10
    assert r["by_prompt"]["plain"]["32B_minus_14B_acceptance"]==1
    assert r["by_prompt"]["structured"]["32B_minus_14B_acceptance"]==0
    assert r["actual_gpu_cost_usd"] is None


def test_rejects_missing_shard(tmp_path):
    seed(tmp_path)
    (tmp_path/"shard-4/results.json").unlink()
    with pytest.raises(ValueError):
        aggregate(tmp_path)


def test_rejects_incomplete_model_pair(tmp_path):
    seed(tmp_path)
    f=tmp_path/"shard-0/results.json"
    data=json.loads(f.read_text())
    data["rows"]=data["rows"][:-1]
    f.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        aggregate(tmp_path)


def test_rejects_wrong_source_digest(tmp_path):
    seed(tmp_path)
    f=tmp_path/"shard-0/results.json"
    data=json.loads(f.read_text())
    data["rows"][0]["task_sha256"]="0"*64
    f.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        aggregate(tmp_path)
