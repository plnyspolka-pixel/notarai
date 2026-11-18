"""Testy narzędzi laboratorium OpenAlex — bez sieci (klient podstawiony)."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools", "lab_openalex"))
import radar  # noqa: E402
import weryfikuj  # noqa: E402


def test_identyfikatory_rozpoznaje_arxiv_i_doi():
    assert weryfikuj.identyfikatory({"identifier": "2405.15793"}) == ("2405.15793", None)
    assert weryfikuj.identyfikatory({"source": "https://arxiv.org/abs/2610.22791v2"}) == ("2610.22791", None)
    assert weryfikuj.identyfikatory({"source": "https://doi.org/10.18653/2026.findings-emnlp.2439/"}) == (
        None,
        "10.18653/2026.findings-emnlp.2439",
    )
    assert weryfikuj.identyfikatory({"title": "bez identyfikatora"}) == (None, None)


def test_streszczenie_z_indeksu_odwroconego():
    assert weryfikuj.streszczenie({"agents": [1], "Coding": [0], "fail": [2]}) == "Coding agents fail"
    assert weryfikuj.streszczenie(None) == ""


def test_podobienstwo_ignoruje_wielkosc_liter_i_interpunkcje():
    assert weryfikuj.podobienstwo("SWE-bench: Can LMs?", "swe bench can lms") == pytest.approx(1.0)
    assert weryfikuj.podobienstwo("Prompt injection", "Protein folding") < 0.6


def _praca(tytul, wid="W1"):
    return {"id": f"https://openalex.org/{wid}", "title": tytul, "cited_by_count": 3, "primary_location": {"source": {"display_name": "arXiv"}}}


def test_sprawdz_potwierdza_po_identyfikatorze(monkeypatch):
    monkeypatch.setattr(weryfikuj, "_get", lambda s, p=None: _praca("Self-Evolving Coding Agents"))
    w = weryfikuj.sprawdz({"id": "x", "title": "Self-Evolving Coding Agents", "identifier": "2610.22791"})
    assert w["werdykt"] == "potwierdzona" and w["openalex"].endswith("W1")


def test_sprawdz_wykrywa_inny_tytul_pod_identyfikatorem(monkeypatch):
    monkeypatch.setattr(weryfikuj, "_get", lambda s, p=None: _praca("Completely different paper about soil"))
    w = weryfikuj.sprawdz({"id": "x", "title": "Agent harness optimization", "identifier": "2610.22791"})
    assert w["werdykt"] == "tytul_inny"


def test_sprawdz_nie_znaleziona_bez_wynikow(monkeypatch):
    monkeypatch.setattr(weryfikuj, "_get", lambda s, p=None: None if s.startswith("/works/") else {"results": []})
    monkeypatch.setattr(weryfikuj, "tytul_z_arxiv", lambda n: None)
    w = weryfikuj.sprawdz({"id": "x", "title": "Zmyślony tytuł pracy", "identifier": "2611.99999"})
    assert w["werdykt"] == "nie_znaleziona"


def test_sprawdz_arxiv_ratuje_brak_w_openalex(monkeypatch):
    monkeypatch.setattr(weryfikuj, "_get", lambda s, p=None: None if s.startswith("/works/") else {"results": []})
    monkeypatch.setattr(weryfikuj, "tytul_z_arxiv", lambda n: "Interpreting Coding Agents")
    w = weryfikuj.sprawdz({"id": "x", "title": "Interpreting Coding Agents", "identifier": "2611.17440"})
    assert w["werdykt"] == "potwierdzona_arxiv"


def test_radar_pomija_prace_juz_w_rejestrze(tmp_path, monkeypatch):
    (tmp_path / "zrodla").mkdir()
    (tmp_path / "zrodla" / "a.jsonl").write_text(json.dumps({"openalex": "https://openalex.org/W1"}) + "\n", encoding="utf-8")
    znane = radar.znane_id(str(tmp_path))
    assert znane == {"W1"}
    monkeypatch.setattr(radar, "_get", lambda s, p=None: {"results": [_praca("Stara", "W1"), _praca("Nowa", "W2")]})
    konfig = {"tematy": [{"nazwa": "T", "kierunek": "k", "zapytanie": "q"}]}
    linie, stat = radar.przebieg(konfig, "2026-11-01", znane, sucho=False)
    assert stat == {"T": 1}
    tekst = "\n".join(linie)
    assert "Nowa" in tekst and "Stara" not in tekst


def test_radar_filtruje_po_typie(monkeypatch):
    zapytania = []
    monkeypatch.setattr(radar, "_get", lambda s, p=None: zapytania.append(p) or {"results": []})
    konfig = {"tematy": [{"nazwa": "Z", "kierunek": "k", "zapytanie": "q", "typ": "dataset"},
                         {"nazwa": "P", "kierunek": "k", "zapytanie": "q"}]}
    radar.przebieg(konfig, "2026-11-01", set(), sucho=False)
    assert zapytania[0]["filter"].endswith(",type:dataset")
    assert "type:" not in zapytania[1]["filter"]


def test_rejestr_zbiorow_danych_ma_wymagane_pola():
    sciezka = os.path.join(os.path.dirname(__file__), "..", "docs", "lab-openalex", "zrodla", "zbiory-danych.jsonl")
    with open(sciezka, encoding="utf-8") as f:
        wiersze = [json.loads(l) for l in f if l.strip()]
    assert wiersze and len({w["id"] for w in wiersze}) == len(wiersze)
    for w in wiersze:
        assert w["typ"] == "dataset" and w["doi"] and w["openalex"].startswith("https://openalex.org/W")
        assert w["licencja"] == "do_sprawdzenia" and w["po_co_nam"].strip()


def test_konfiguracja_radaru_jest_poprawna():
    sciezka = os.path.join(os.path.dirname(__file__), "..", "docs", "lab-openalex", "radar.json")
    with open(sciezka, encoding="utf-8") as f:
        konfig = json.load(f)
    nazwy = [t["nazwa"] for t in konfig["tematy"]]
    assert len(nazwy) == len(set(nazwy))
    for t in konfig["tematy"]:
        assert t["zapytanie"].strip() and t["kierunek"]
