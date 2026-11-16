"""Bench scaling runner: public task packets, strata and no leakage."""
import pytest
from tools.agent_factory.worker_scale_runner import (
    ARMS, job_for, select_tasks
)
from tools.agent_factory.worker_pool import WorkerPolicyError


def test_5_shards_cover_distinct_ten_families_on_dev():
    ids=[]
    families=set()
    for shard in range(5):
        batch=select_tasks(shard,10,"development")
        assert len(batch)==20
        ids.extend(x["id"] for x in batch)
        families.update(x["family"] for x in batch)
    assert len(ids)==100 and len(set(ids))==100
    assert len(families)==10


def test_holdout_is_separate_from_development():
    a={t["id"] for i in range(5) for t in select_tasks(i,10,"development")}
    b={t["id"] for i in range(5) for t in select_tasks(i,10,"heldout")}
    assert len(a)==len(b)==100
    assert not a&b


def test_two_methods_do_not_expose_oracle_cases():
    for shard in range(5):
        for task in select_tasks(shard,4,"development"):
            plain=job_for(task,"plain")
            scoped=job_for(task,"structured")
            assert scoped["instruction"]==plain["instruction"]
            assert scoped["context"]!=plain["context"]
            for p in (plain,scoped):
                assert "case_id" not in str(p)
                assert "cases.json" not in str(p)
                assert p["data_class"]=="synthetic"
                assert len(p["instruction"])<=3500


@pytest.mark.parametrize("shard,limit,split",[
    (-1,1,"development"),(5,1,"development"),
    (0,0,"development"),(0,11,"development"),
    (0,4,"all")
])
def test_rejects_invalid_expansion(shard,limit,split):
    with pytest.raises(WorkerPolicyError):
        select_tasks(shard,limit,split)


def test_rejects_unknown_arm():
    with pytest.raises(WorkerPolicyError):
        job_for(select_tasks(0,1,"development")[0],"fake")
