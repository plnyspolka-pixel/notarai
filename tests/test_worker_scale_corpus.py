"""Large synthetic corpus determinism, schema, oracle and split boundaries."""
import json
import hashlib
import pytest
from tools.agent_factory.worker_scale_corpus import (
    FAMILIES, COUNT_PER_FAMILY, CASES_PER_TASK,
    make_task, tasks, samples, summary, oracle,
)


def test_two_hundred_distinct_contracts_with_one_thousand_six_hundred_cases():
    report=summary()
    assert report["distinct_parameterized_contracts"]==200
    assert report["development_contracts"]==100
    assert report["heldout_contracts"]==100
    assert report["oracle_case_count"]==1600
    assert report["families"]==10
    assert report["structural_templates"]==10


def test_no_development_holdout_overlap_in_tasks_or_ids():
    dev=tasks("development")
    test=tasks("heldout")
    assert len(dev)==len(test)==100
    assert not ({t["id"] for t in dev} & {t["id"] for t in test})
    assert all(t["data_class"]=="synthetic" for t in dev+test)
    assert all(t["variant"]<10 for t in dev)
    assert all(t["variant"]>=10 for t in test)


def test_every_task_has_deterministic_varied_oracle_vectors():
    for t in tasks():
        cases=samples(t)
        assert len(cases)==CASES_PER_TASK
        assert len({r["case_id"] for r in cases})==len(cases)
        assert cases==samples(t)
        assert all("expected" in r and "input" in r for r in cases)
        assert all(r["expected"]==oracle(t["family"],t["contract"],r["input"]) for r in cases)
        assert "sk-abcdefghij" not in t["instruction"]
        assert "case_id" not in t["instruction"]


def test_public_contracts_unique_and_serializable():
    ids,hashes=set(),set()
    for t in tasks():
        assert t["id"] not in ids
        assert t["task_sha256"] not in hashes
        assert 40<=len(t["instruction"])<=3500
        assert json.loads(json.dumps(t))==t
        ids.add(t["id"])
        hashes.add(t["task_sha256"])
    assert len(ids)==200


def test_oracle_properties_for_edge_cases():
    t=make_task("numeric",0)
    assert oracle(t["family"],t["contract"],[])==0
    t=make_task("slugs",0)
    assert oracle(t["family"],t["contract"],None)==""
    t=make_task("intervals",0)
    assert oracle(t["family"],t["contract"],[[1,3],[3,5]])==[[1,3],[3,5]]
    t=make_task("intervals",1)
    assert oracle(t["family"],t["contract"],[[1,3],[3,5]])==[[1,5]]


@pytest.mark.parametrize("family",FAMILIES)
def test_each_family_has_twenty_variations(family):
    family_tasks=[t for t in tasks() if t["family"]==family]
    assert len(family_tasks)==COUNT_PER_FAMILY
    assert len({t["instruction"] for t in family_tasks})==20
