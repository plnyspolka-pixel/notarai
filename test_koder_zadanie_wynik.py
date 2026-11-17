"""Blok oceny wyniku z zadanie.sh (Python w heredoc) - bez Dockera i GPU.

Wycina blok `python3 - "$OUT" "$ID" ...` z zadanie.sh i uruchamia go na sztucznych
plikach przebiegu: bramka zależności (K5), „zmiana niepotrzebna” (W7), dziennik JSONL.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parent
KARTA = "docs/agent-tasks/kolejka/taksa-kwota-kropki.md"


def _blok() -> str:
    tekst = (ROOT / "tools/agent_factory/koder/zadanie.sh").read_text(encoding="utf-8")
    m = re.search(r'^python3 - "\$OUT" "\$ID" "\$KARTA" "\$RC".*?\n(.*?)^PY$', tekst, re.S | re.M)
    assert m, "nie znaleziono bloku oceny w zadanie.sh"
    return m.group(1)


def _uruchom(tmp: Path, traj: dict, ukryte: dict, zaleznosci: dict | None, zmienione: list[str]):
    (tmp / "k.traj.json").write_text(json.dumps(traj), encoding="utf-8")
    (tmp / "k.ukryte.json").write_text(json.dumps(ukryte), encoding="utf-8")
    if zaleznosci is not None:
        (tmp / "k.zaleznosci.json").write_text(json.dumps(zaleznosci), encoding="utf-8")
    skrypt = tmp / "blok.py"
    skrypt.write_text(_blok(), encoding="utf-8")
    env = {**os.environ, "ROOT": str(ROOT), "KODER_STAN": str(tmp / "brak.json")}
    env.pop("KODER_DZIENNIK", None)
    r = subprocess.run([sys.executable, str(skrypt), str(tmp), "k", KARTA, "0", "0", "7", "agent/x", "", *zmienione],
                       capture_output=True, text=True, env=env, check=True)
    wynik = json.loads(r.stdout)
    dziennik = [json.loads(w) for w in (tmp / "dziennik.jsonl").read_text(encoding="utf-8").splitlines()]
    return wynik, dziennik[-1]


SUB = {"info": {"exit_status": "Submitted", "model_stats": {"api_calls": 5}}}


def test_zaliczone_bez_nowych_zaleznosci(tmp_path):
    w, d = _uruchom(tmp_path, SUB, {"ukryte_zaliczone": True}, {"powod": None, "naruszenia": []}, ["a.py"])
    assert w["zaliczone"] is True and w["nowe_zaleznosci"] == []
    assert d["wynik"] == "zaliczone" and d["powody"] == []
    assert d["koszt_usd"] is None  # nieznany koszt to null, nigdy 0
    assert "manifest" in d and "sha256_karty" in d["manifest"]


def test_zmyslona_paczka_odrzuca(tmp_path):
    zal = {"powod": "nowa_zaleznosc", "naruszenia": [{"plik": "a.py", "modul": "requestz"}]}
    w, d = _uruchom(tmp_path, SUB, {"ukryte_zaliczone": True}, zal, ["a.py"])
    assert w["zaliczone"] is False and w["nowe_zaleznosci"] == ["requestz"]
    assert d["powody"] == ["nowa_zaleznosc"] and d["liczba_nowych_zaleznosci"] == 1


def test_brak_wyniku_bramki_to_odrzucenie(tmp_path):
    w, d = _uruchom(tmp_path, SUB, {"ukryte_zaliczone": True}, None, ["a.py"])
    assert w["zaliczone"] is False and "bramka_nie_zadzialala" in d["powody"]


@pytest.mark.parametrize("ukryte,oczekiwany", [(True, "niepotrzebna"), (False, "odrzucone")])
def test_zmiana_niepotrzebna(tmp_path, ukryte, oczekiwany):
    traj = {"info": {"exit_status": "Submitted", "submission": "ZMIANA NIEPOTRZEBNA: już działa"}}
    w, d = _uruchom(tmp_path, traj, {"ukryte_zaliczone": ukryte}, {"powod": None, "naruszenia": []}, [])
    assert w["niepotrzebna"] == oczekiwany
    assert d["wynik"] == oczekiwany
    if oczekiwany == "odrzucone":
        assert "niepotrzebna_niepotwierdzona" in d["powody"]


def test_dziennik_bez_tresci_promptu(tmp_path):
    traj = {**SUB, "messages": [{"role": "user", "content": "TAJNA TREŚĆ POLECENIA"}]}
    _, d = _uruchom(tmp_path, traj, {"ukryte_zaliczone": True}, {"powod": None, "naruszenia": []}, ["a.py"])
    assert "TAJNA" not in json.dumps(d, ensure_ascii=False)
