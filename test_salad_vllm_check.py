"""Polecenie `check` z flagą `--json` - bez sieci, dane syntetyczne."""
import argparse
import json

import pytest

from tools.agent_factory import salad_vllm

KEYS = {"SALAD_API_KEY": "x", "SALAD_ORG": "org", "SALAD_PROJECT": "proj"}

SYNTHETIC_GPUS = [
    {"id": "g1", "name": "NVIDIA H100 SXM (80 GB)", "vram": 80, "usd_h": 1.9},
    {"id": "g2", "name": "NVIDIA L40S (48 GB)", "vram": 48, "usd_h": 1.1},
]
SYNTHETIC_GROUPS = [
    {"name": "notarai-koder-20260101t1200"},
    {"name": "notarai-koder-20260102t1300"},
]


@pytest.fixture()
def syntetyczne(monkeypatch):
    monkeypatch.setattr(salad_vllm, "gpu_classes", lambda keys, priority: list(SYNTHETIC_GPUS))
    monkeypatch.setattr(salad_vllm, "our_groups", lambda keys: list(SYNTHETIC_GROUPS))


def _args(**kw):
    a = argparse.Namespace(cmd="check", priority="high")
    for k, v in kw.items():
        setattr(a, k, v)
    return a


def test_check_json(syntetyczne, capsys):
    rc = salad_vllm.cmd_check(KEYS, _args(json=True))
    out = capsys.readouterr().out
    assert rc == 0
    dane = json.loads(out)
    assert dane == {
        "gpu": [
            {"name": "NVIDIA H100 SXM (80 GB)", "vram": 80, "usd_h": 1.9},
            {"name": "NVIDIA L40S (48 GB)", "vram": 48, "usd_h": 1.1},
        ],
        "groups": ["notarai-koder-20260101t1200", "notarai-koder-20260102t1300"],
    }
    # dokładnie jeden obiekt JSON - nic poza nim
    assert out.strip() and out.strip().startswith("{") and out.strip().endswith("}")


def test_check_zwyklie(syntetyczne, capsys):
    rc = salad_vllm.cmd_check(KEYS, _args())
    out = capsys.readouterr().out
    assert rc == 0
    lines = out.strip().splitlines()
    assert "NVIDIA H100 SXM (80 GB)" in lines[0] and "1.900 USD/h" in lines[0]
    assert "NVIDIA L40S (48 GB)" in lines[1] and "1.100 USD/h" in lines[1]
    assert lines[2] == "Nasze grupy: notarai-koder-20260101t1200, notarai-koder-20260102t1300"


def test_check_json_puste(syntetyczne, capsys, monkeypatch):
    monkeypatch.setattr(salad_vllm, "gpu_classes", lambda keys, priority: [])
    monkeypatch.setattr(salad_vllm, "our_groups", lambda keys: [])
    rc = salad_vllm.cmd_check(KEYS, _args(json=True))
    out = capsys.readouterr().out
    assert rc == 0
    assert json.loads(out) == {"gpu": [], "groups": []}
