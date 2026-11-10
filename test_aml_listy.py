"""Listy sankcyjne i PEP: parsery na probkach prawdziwych odpowiedzi
(probki/aml, pobrane 9.10.2026, przyciete do kilku rekordow) oraz migawki
bez sieci."""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import aml_listy as L
import config

PROBKI = Path(__file__).parent / "probki" / "aml"


def probka(nazwa: str) -> str:
    return (PROBKI / nazwa).read_text("utf-8")


class TestUE:
    def test_osoby_i_podmioty_z_aliasami(self):
        rekordy = L.parsuj_ue(probka("eu_fsf_sample.xml"))
        assert len(rekordy) == 4
        saddam = next(r for r in rekordy if "Saddam" in r.nazwy[0])
        assert saddam.rodzaj == "osoba"
        assert "1937-04-28" in saddam.daty_urodzenia
        assert saddam.obywatelstwa == ["IQ"]
        assert "Abu Ali" in saddam.nazwy
        assert saddam.program == "IRQ" and saddam.identyfikator == "13"
        assert any(r.rodzaj == "podmiot" for r in rekordy)

    def test_zachowuje_cyrylice_i_sam_rok(self):
        rekordy = L.parsuj_ue(probka("eu_fsf_sample.xml"))
        assert any(re.search("[Ѐ-ӿ]", n) for r in rekordy for n in r.nazwy)
        assert any(re.fullmatch(r"\d{4}", x) for r in rekordy for x in r.daty_urodzenia)


class TestONZ:
    def test_osoby_daty_i_podmioty(self):
        rekordy = L.parsuj_onz(probka("un_sc_sample.xml"))
        assert len([r for r in rekordy if r.rodzaj == "osoba"]) == 4
        assert len([r for r in rekordy if r.rodzaj == "podmiot"]) == 1
        assert any(len(r.daty_urodzenia) > 1 for r in rekordy)      # przedzial lat
        assert all(r.identyfikator and r.nazwy[0] for r in rekordy)
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", rekordy[0].wpisano)


class TestMSWiA:
    def test_osoby_podmioty_i_wersja(self):
        rekordy, wersja = L.parsuj_mswia(probka("mswia_sample.html"))
        osoby = [r for r in rekordy if r.rodzaj == "osoba"]
        assert len(osoby) == 3 and len(rekordy) - len(osoby) == 3
        a = next(r for r in osoby if r.nazwy[0] == "Apti Aronovich ALAUDINOV")
        assert a.daty_urodzenia == ["1973-10-05"] and a.wpisano == "2022-10-27" and a.obywatelstwa == ["RU"]
        assert wersja == "168.0"


class TestSejm:
    def test_scala_kadencje(self):
        poslowie = json.loads(probka("sejm_term10_mp_sample.json"))
        rekordy = L.parsuj_sejm([
            {"kadencja": {"num": 10, "from": "2023-11-13", "current": True}, "poslowie": poslowie},
            {"kadencja": {"num": 9, "from": "2019-11-12", "to": "2023-11-12"}, "poslowie": [poslowie[0]]},
        ])
        assert len(rekordy) == 3
        assert len(rekordy[0].funkcje) == 2 and rekordy[0].aktualny
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", rekordy[0].daty_urodzenia[0])
        nieaktywny = next(r for r in rekordy if not r.aktualny)
        assert nieaktywny.funkcje[0]["do"] == "2025-08-07"


class TestWikidata:
    def test_zapytania(self):
        assert "YEAR(?end) >= 2000" in L.zapytanie_wikidata_osoby(["Q1054799"], 2000)
        assert "wdt:P1001 wd:Q36" in L.zapytanie_wikidata_stanowiska(["Q83307"], "subclass_pl")

    def test_agreguje_osoby(self):
        rekordy = L.parsuj_wikidata(json.loads(probka("wikidata_holders_sample.json")),
                                    {"Q1054799": "PL-001", "Q15051532": "PL-003"})
        assert len(rekordy) > 5
        kw = next(r for r in rekordy if r.nazwy[0] == "Aleksander Kwaśniewski")
        assert kw.daty_urodzenia == ["1954-11-15"] and "PL" in kw.obywatelstwa
        assert kw.funkcje[0]["kod"] == "PL-001"
        assert kw.adres_zrodla == "https://www.wikidata.org/wiki/Q55758"


class TestKPRM:
    def test_sklad_rzadu(self):
        rekordy = L.parsuj_kprm(probka("kprm_sample.html"))
        assert len(rekordy) == 5
        assert rekordy[0].nazwy == ["Donald Tusk"] and rekordy[0].funkcje[0]["kod"] == "PL-002"
        assert rekordy[1].funkcje[0]["kod"] == "PL-003"
        assert all(r.aktualny and not r.daty_urodzenia for r in rekordy)


@pytest.fixture
def lokalnie(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DANE", tmp_path)
    monkeypatch.setattr(L.magazyn, "TRYB", "lokalny")
    L._INDEKSY.clear()
    yield tmp_path
    L._INDEKSY.clear()


class TestMigawki:
    def test_odswiez_zapisuje_i_buduje_indeks(self, lokalnie, monkeypatch):
        rekordy = L.parsuj_mswia(probka("mswia_sample.html"))[0]
        monkeypatch.setattr(L, "pobierz", lambda zrodlo, klient=None: (rekordy, {"wersja": "168.0"}))
        raport = L.odswiez(["mswia"])
        assert raport == [{"zrodlo": "mswia", "stan": "pobrana", "liczba": 6}]
        assert (lokalnie / "listy_aml" / "mswia.json").exists()
        assert L.gotowe("sankcje")
        indeks, opis = L.indeks("sankcje")
        assert len(indeks) == 6 and any(o.startswith("mswia z ") for o in opis)
        # drugi raz: aktualna, bez pobierania
        monkeypatch.setattr(L, "pobierz", lambda *a, **k: (_ for _ in ()).throw(AssertionError("pobrano")))
        assert L.odswiez(["mswia"])[0]["stan"] == "aktualna"

    def test_pusta_odpowiedz_nie_kasuje_starej_listy(self, lokalnie, monkeypatch):
        rekordy = L.parsuj_mswia(probka("mswia_sample.html"))[0]
        monkeypatch.setattr(L, "pobierz", lambda zrodlo, klient=None: (rekordy, {}))
        L.odswiez(["mswia"])
        monkeypatch.setattr(L, "pobierz", lambda zrodlo, klient=None: (rekordy[:1], {}))
        raport = L.odswiez(["mswia"], wymus=True)
        assert raport[0]["stan"] == "blad" and "podejrzanie malo" in raport[0]["opis"]
        migawka = L.wczytaj_migawke("mswia")
        assert migawka["liczba"] == 6 and migawka["blad"]

    def test_wykreslone_nie_trafiaja_do_indeksu(self, lokalnie):
        rekordy = L.parsuj_mswia(probka("mswia_sample.html"))[0]
        rekordy[0].wykreslono = "2026-01-01"
        L.zapisz_migawke("mswia", {"zrodlo": "mswia", "pobrano": datetime.now().isoformat(timespec="seconds"),
                                   "liczba": len(rekordy), "meta": {}, "blad": None,
                                   "rekordy": [r.slownik() for r in rekordy]})
        indeks, _ = L.indeks("sankcje")
        assert len(indeks) == len(rekordy) - 1

    def test_stan_pokazuje_nieaktualnosc(self, lokalnie):
        stara = (datetime.now() - timedelta(days=3)).isoformat(timespec="seconds")
        L.zapisz_migawke("eu_fsf", {"zrodlo": "eu_fsf", "pobrano": stara, "liczba": 1, "meta": {},
                                    "blad": None, "rekordy": []})
        wpis = next(s for s in L.stan() if s["zrodlo"] == "eu_fsf")
        assert wpis["nieaktualna"] is True and wpis["liczba"] == 1
        assert next(s for s in L.stan() if s["zrodlo"] == "sejm")["pobrano"] is None
        assert all("rekordy" not in s for s in L.stan())

    def test_bez_migawek_nic_nie_jest_gotowe(self, lokalnie):
        assert not L.gotowe("sankcje") and not L.gotowe("pep")
        assert len(L.indeks("pep")[0]) == 0
