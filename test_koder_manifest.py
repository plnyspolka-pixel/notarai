"""Manifest przebiegu kodera i dziennik JSONL: komplet pól, koszt nieznany = null."""
import json
from pathlib import Path

import pytest

from tools.agent_factory.koder import manifest as mf

STAN = {"model": "RedHatAI/Qwen3.8-27B-INT4", "image": "vllm/vllm-openai:latest", "context": 65536,
        "vllm_args": "--kv-cache-dtype fp8 --language-model-only --enforce-eager", "gpu": "RTX 5090",
        "usd_h": 0.6, "vllm_version": "0.13.1"}
POLA = {"model", "obraz_vllm", "wersja_vllm", "dtype", "kv_cache_dtype", "kwantyzacja", "kwantyzacja_zrodlo",
        "max_model_len", "prefix_caching", "gpu", "gpu_usd_h", "wersja_harness", "sha256_karty",
        "skrot_ukrytych"}


@pytest.fixture
def karta(tmp_path) -> Path:
    p = tmp_path / "karta.md"
    p.write_text("---\nid: x\n---\n# T\n", encoding="utf-8")
    return p


def test_manifest_ma_wszystkie_pola(tmp_path, karta):
    (tmp_path / "u").mkdir()
    (tmp_path / "u" / "test_a.py").write_text("def test_a(): pass\n", encoding="utf-8")
    m = mf.manifest(karta, STAN, tmp_path, ["u/test_a.py"], env={"GITHUB_SHA": "abc"})
    assert set(m) == POLA
    assert m["dtype"] == "auto" and m["kv_cache_dtype"] == "fp8" and m["max_model_len"] == 65536
    assert m["kwantyzacja"] == "INT4" and m["kwantyzacja_zrodlo"] == "nazwa_modelu"
    assert m["prefix_caching"] == "domyslne" and m["gpu"] == "RTX 5090" and m["wersja_vllm"] == "0.13.1"
    assert len(m["sha256_karty"]) == 64 and len(m["skrot_ukrytych"]) == 64
    assert m["wersja_harness"]  # sha z git albo GITHUB_SHA


def test_flagi_jawne_wygrywaja(karta, tmp_path):
    stan = {**STAN, "vllm_args": "--dtype bfloat16 --quantization awq --no-enable-prefix-caching"}
    m = mf.manifest(karta, stan, tmp_path, env={})
    assert (m["dtype"], m["kwantyzacja"], m["kwantyzacja_zrodlo"], m["prefix_caching"]) == \
        ("bfloat16", "awq", "flaga", False)


def test_brak_stanu_to_null_a_nie_zgadywanie(karta, tmp_path):
    m = mf.manifest(karta, {}, tmp_path, env={})
    assert m["dtype"] is None and m["prefix_caching"] is None and m["skrot_ukrytych"] is None


def test_zmiana_ukrytego_testu_zmienia_skrot(tmp_path):
    (tmp_path / "t.py").write_text("a", encoding="utf-8")
    s1 = mf.skrot_plikow(tmp_path, ["t.py"])
    (tmp_path / "t.py").write_text("b", encoding="utf-8")
    assert mf.skrot_plikow(tmp_path, ["t.py"]) != s1


def test_rekord_koszt_null_gdy_nieznany_i_dziennik(tmp_path, karta):
    traj = tmp_path / "x.traj.json"
    traj.write_text(json.dumps({"info": {"exit_status": "Submitted",
                                         "model_stats": {"api_calls": 7, "instance_cost": 0}},
                                "messages": [{"role": "user", "content": "TAJNY PROMPT"}]}), encoding="utf-8")
    r = mf.rekord_zadania("x", "odrzucone", ["nowa_zaleznosc"], mf.manifest(karta, STAN, tmp_path, env={}),
                          traj, 42, None, ["halucynacja"])
    assert r["koszt_usd"] is None and r["tokeny_wej"] is None
    assert r["kroki"] == 7 and r["exit_status"] == "Submitted" and r["liczba_nowych_zaleznosci"] == 1
    dz = mf.sciezka_dziennika(tmp_path / "out", env={})
    mf.dopisz_dziennik(dz, r)
    mf.dopisz_dziennik(dz, r)
    wiersze = dz.read_text(encoding="utf-8").splitlines()
    assert len(wiersze) == 2 and "TAJNY PROMPT" not in wiersze[0]
    assert json.loads(wiersze[0])["koszt_usd"] is None and "kiedy" in json.loads(wiersze[0])


def test_tokeny_liczone_gdy_sa(tmp_path):
    traj = tmp_path / "t.json"
    msg = {"role": "assistant", "extra": {"response": {"usage": {"prompt_tokens": 10, "completion_tokens": 3}}}}
    traj.write_text(json.dumps({"info": {}, "messages": [msg, msg]}), encoding="utf-8")
    t = mf.z_trajektorii(traj)
    assert (t["tokeny_wej"], t["tokeny_wyj"]) == (20, 6)


def test_zly_wynik_i_sciezka_z_env(tmp_path):
    with pytest.raises(ValueError):
        mf.rekord_zadania("x", "zielone", [], {})
    assert mf.sciezka_dziennika(tmp_path, env={"KODER_DZIENNIK": "/x/d.jsonl"}) == Path("/x/d.jsonl")
