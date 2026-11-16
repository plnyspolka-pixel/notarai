"""Offline benchmark spec validation. These tests DO NOT execute candidate code."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import sys

import pytest

from tools.agent_factory.benchmark30 import (
    BenchmarkError, CASES, MANIFEST, CHAINS, ENTRY,
    validate, prepare, spec, plan, summarize, main,
)
from tools.agent_factory.benchmark30_docker import command, grade


def _temporary(tmp_path: Path, tasks=None, cases=None):
    m = json.loads(MANIFEST.read_text())
    c = json.loads(CASES.read_text())
    if tasks is not None:
        m['tasks'] = tasks
    if cases is not None:
        c['tests'] = cases
    mp, cp = tmp_path / 'm.json', tmp_path / 'c.json'
    mp.write_text(json.dumps(m), encoding='utf8')
    cp.write_text(json.dumps(c), encoding='utf8')
    return mp, cp


def test_exactly_thirty_real_task_specs_and_61_case_vectors():
    result = validate()
    assert result['tasks'] == 30 and result['chains'] == 6
    assert result['cases'] >= 60 and result['model_calls'] == 0


def test_each_chain_has_five_incremental_tasks():
    manifest = json.loads(MANIFEST.read_text())
    for chain in CHAINS:
        parts = [t for t in manifest['tasks'] if t['chain'] == chain]
        assert [t['step'] for t in parts] == list(range(1, 6))
        assert all(t['entrypoint'] == ENTRY[chain] for t in parts)
        assert all(t['requires_previous_steps'] == list(range(1, t['step'])) for t in parts)


def test_all_tasks_serialize_for_work_dispatch():
    for i in range(1, 31):
        payload = spec(f'T{i:02d}')
        assert payload['task']['id'] == f'T{i:02d}'
        assert 'tests' not in payload
    with pytest.raises(BenchmarkError):
        spec('T31')


def test_prepare_synthetic_workspaces(tmp_path):
    result = prepare(tmp_path / 'generated')
    assert result['model_calls'] == 0
    for chain in CHAINS:
        stub = tmp_path / 'generated' / chain / 'solution.py'
        assert stub.is_file() and 'NotImplementedError' in stub.read_text()
        assert not (stub.parent / 'cases.json').exists()
    with pytest.raises(BenchmarkError, match='already exists'):
        prepare(tmp_path / 'generated')


def test_manifest_missing_task_denied(tmp_path):
    tasks = json.loads(MANIFEST.read_text())['tasks'][:-1]
    mp, cp = _temporary(tmp_path, tasks=tasks)
    with pytest.raises(BenchmarkError):
        validate(mp, cp)


def test_duplicate_stage_denied(tmp_path):
    tasks = json.loads(MANIFEST.read_text())['tasks']
    tasks[1]['step'] = tasks[0]['step']
    mp, cp = _temporary(tmp_path, tasks=tasks)
    with pytest.raises(BenchmarkError):
        validate(mp, cp)


def test_missing_case_denied(tmp_path):
    cases = json.loads(CASES.read_text())['tests']
    cases = [c for c in cases if c['task_id'] != 'T01']
    mp, cp = _temporary(tmp_path, cases=cases)
    with pytest.raises(BenchmarkError):
        validate(mp, cp)


def test_duplicate_case_denied(tmp_path):
    cases = json.loads(CASES.read_text())['tests']
    cases[1]['id'] = cases[0]['id']
    mp, cp = _temporary(tmp_path, cases=cases)
    with pytest.raises(BenchmarkError):
        validate(mp, cp)


def test_bad_case_arity_denied(tmp_path):
    cases = json.loads(CASES.read_text())['tests']
    cases[0]['args'] = []
    mp, cp = _temporary(tmp_path, cases=cases)
    with pytest.raises(BenchmarkError):
        validate(mp, cp)


def test_symlink_manifest_denied(tmp_path):
    m = tmp_path / 'manifest.json'
    m.symlink_to(MANIFEST)
    with pytest.raises(BenchmarkError):
        validate(m, CASES)


def test_docker_must_be_pinned_and_no_elevated_flags(tmp_path):
    prepare(tmp_path / 'code')
    with pytest.raises(BenchmarkError):
        command(workspace=tmp_path / 'code', chain='catalog', upto=1, image='python:latest')
    args = command(workspace=tmp_path / 'code', chain='catalog', upto=1,
                   image='python:3.12-slim@sha256:' + 'a'*64)
    assert '--network' in args and 'none' in args
    assert '--read-only' in args and 'ALL' in args
    assert 'privileged' not in ' '.join(args)
    # GitHub Actions legitimately checks out repositories under /home/runner/.\n    # Inspect mount destinations and privileged paths, not the runner's source path.\n    mounts = [args[i+1] for i, value in enumerate(args[:-1]) if value == '--mount']\n    assert all('dst=/home/' not in x and 'dst=/.ssh' not in x and 'docker.sock' not in x for x in mounts)


def test_docker_grade_denies_without_disposable_vm_opt_in(tmp_path, monkeypatch):
    prepare(tmp_path / 'code')
    monkeypatch.delenv('AGENT_BENCH30_ISOLATED_VM_APPROVED', raising=False)
    with pytest.raises(BenchmarkError, match='explicit opt-in'):
        grade(workspace=tmp_path / 'code', chain='catalog', upto=1,
              image='python:3.12-slim@sha256:' + 'a'*64)


def test_docker_path_symlink_denied(tmp_path):
    prepare(tmp_path / 'code')
    dst = tmp_path / 'code' / 'catalog' / 'solution.py'
    dst.unlink()
    dst.symlink_to(tmp_path / 'nonexistent')
    with pytest.raises(BenchmarkError):
        command(workspace=tmp_path / 'code', chain='catalog', upto=1,
                image='python:3.12-slim@sha256:' + 'a'*64)


def test_report_cannot_invent_results(tmp_path):
    p = tmp_path / 'results.json'
    p.write_text(json.dumps({'results':[{'task_id':f'T{i:02d}','passed':True} for i in range(1,31)]}))
    with pytest.raises(BenchmarkError, match='unattested'):
        summarize(p)


def test_report_remains_unverified_with_fake_attestations(tmp_path):
    p = tmp_path / 'results.json'
    p.write_text(json.dumps({'results':[
        {'task_id':f'T{i:02d}','passed':True,
         'verified_by':'external-isolated-runner','attestation_sha256':'a'*64}
        for i in range(1,31)]}))
    result = summarize(p)
    assert result['reported_passed'] == 30
    assert 'UNVERIFIED' in result['status']
    assert result['cannot_authorize_merge_or_deploy']


def test_cli_plan_is_offline(capsys):
    assert main(['plan']) == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload['tasks']) == 30
    assert payload['does_not_run_models'] is True


def test_case_vectors_require_cumulative_replay():
    cases = json.loads(CASES.read_text())['tests']
    for chain in CHAINS:
        counts = [sum(x['chain'] == chain and x['step'] <= stage for x in cases) for stage in range(1, 6)]
        assert counts == sorted(counts)
        assert all(b >= a + 2 for a, b in zip([0] + counts[:-1], counts))
