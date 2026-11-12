"""Tresc ksiegi z EKW jako zrodlo projektu aktu. Atrapa modelu, dane fikcyjne.

- ksiega z pustymi dzialami III/IV trafia do wywolania modelu (osobny blok),
- bez ksiegi wywolanie modelu jest takie jak dotad,
- rozbieznosc wlasciciela -> model dostaje polecenie zostawienia <<WYBOR>>,
- w logach tylko identyfikator sprawy i liczby - bez numeru KW i tresci.
"""
import json
import logging
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import app as aplikacja
import bedrock
import config
import ekw
import prompty

SPRAWA = "abc123ekw456"
KW = "WA4M/00160286/2"
INNA_KW = "WA1M/00012345/6"
WZOR = ("AKT NOTARIALNY\n§ 2. Ksiega wieczysta KW nr ?? - w dziale III i IV nie ma wpisow "
        "// w dziale IV wpisana jest hipoteka umowna ...")


def ksiega(numer=KW, dzial2="Jan Testowy, udzial 1/1", dzial4=None, pobrano="2026-11-10T09:15:00"):
    def dz(oznaczenie, tekst):
        return {"oznaczenie": oznaczenie, "tytul": f"DZIAL {oznaczenie}",
                "pusty": tekst is None, "tekst": "BRAK WPISÓW" if tekst is None else tekst}
    return {
        "numer_kw": numer, "kod_sadu": numer[:4], "sad": "SAD REJONOWY TESTOWY", "typ": "LOKAL",
        "widok": "aktualna", "pobrano": pobrano, "zrodlo": "atrapa", "dostawca": "finyou",
        "dzialy": [dz("I-O", "Lokal nr 5, powierzchnia 48,50 m2"), dz("I-Sp", None),
                   dz("II", dzial2), dz("III", None), dz("IV", dzial4)],
    }


@pytest.fixture
def klient(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SPRAWY", tmp_path)
    katalog = tmp_path / SPRAWA
    katalog.mkdir()
    (katalog / "wzor.txt").write_text(WZOR, "utf-8")
    (katalog / "sprawa.json").write_text(json.dumps({"id": SPRAWA, "nazwa": "Testowy", "skany": []}), "utf-8")
    return TestClient(aplikacja.app), katalog


def zapisz_ksiege(katalog, k):
    d = katalog / ekw.KATALOG
    d.mkdir(exist_ok=True)
    (d / f"{ekw.nazwa_pliku(k['numer_kw'])}.json").write_text(json.dumps(k, ensure_ascii=False), "utf-8")


def pola(wlasciciel="Jan Testowy", kw=KW):
    return [{"nazwa": "Numer KW", "wartosc": kw},
            {"nazwa": "Sprzedajacy - imie i nazwisko", "wartosc": wlasciciel},
            {"nazwa": "Powierzchnia lokalu", "wartosc": "48,50 m2"}]


def generuj(k, lista_pol, polecenie=""):
    with patch("bedrock.sporzadz_projekt", return_value="AKT NOTARIALNY\n§ 2. w dziale III i IV nie ma wpisow") as sp:
        odp = k.post(f"/api/sprawy/{SPRAWA}/projekt", json={"pola": lista_pol, "polecenie": polecenie})
    assert odp.status_code == 200, odp.text
    return sp, odp.json()


class TestProjektZKsiega:
    def test_pusta_ksiega_trafia_do_modelu(self, klient, caplog):
        k, katalog = klient
        zapisz_ksiege(katalog, ksiega())
        with caplog.at_level(logging.INFO):
            sp, wynik = generuj(k, pola())
        blok = sp.call_args.kwargs["ksiegi"]
        assert f"TRESC KSIEGI WIECZYSTEJ {KW} Z EKW (nie odpis urzedowy, pobrano 2026-11-10 09:15:00)" in blok
        assert "--- DZIAL III" in blok and "--- DZIAL IV" in blok
        assert blok.count("BRAK WPISOW") >= 3  # I-Sp, III, IV
        assert "ROZSTRZYGA warianty" in blok and "BEZ znacznika <<WYBOR>>" in blok
        assert "WYKRYTE ROZBIEZNOSCI" not in blok
        assert wynik["zrodla"]["ksiegi"] == [KW]
        assert wynik["zrodla"]["ksiegi_pobrano"][KW] == "2026-11-10T09:15:00"
        potwierdzone = {w["pole"] for w in wynik["zrodla"]["weryfikacja"] if w["stan"] == "potwierdza"}
        assert potwierdzone == {"Numer KW", "Sprzedajacy - imie i nazwisko", "Powierzchnia lokalu"}
        # RODO: w logach bez numeru KW i tresci ksiegi.
        assert KW not in caplog.text and "Testowy" not in caplog.text
        assert f"sprawa {SPRAWA}: projekt z trescia ksiag EKW=1, rozbieznosci=0" in caplog.text
        # Zrodla zostaja przy sprawie - widok projektu po odswiezeniu.
        assert k.get(f"/api/sprawy/{SPRAWA}").json()["zrodla"]["ksiegi"] == [KW]

    def test_blok_trafia_do_polecenia_generowania(self, klient):
        k, katalog = klient
        zapisz_ksiege(katalog, ksiega(dzial4="Hipoteka umowna 300 000 zl na rzecz Banku Testowego"))
        with patch("bedrock._rozmowa", return_value="AKT") as r:
            k.post(f"/api/sprawy/{SPRAWA}/projekt", json={"pola": pola(), "polecenie": ""})
        tekst = r.call_args.args[1][0]["text"]
        assert "Hipoteka umowna 300 000 zl" in tekst
        assert tekst.index("DANE ZWALIDOWANE") < tekst.index("TRESC KSIEGI WIECZYSTEJ") \
            < tekst.index("POLECENIE UZYTKOWNIKA")

    def test_bez_ksiegi_wywolanie_jak_dotad(self, klient):
        k, _ = klient
        sp, wynik = generuj(k, pola())
        assert "ksiegi" not in sp.call_args.kwargs
        assert set(sp.call_args.kwargs) == {"personalizacja"} and len(sp.call_args.args) == 5
        assert wynik["zrodla"] == {"ksiegi": [], "ksiegi_pobrano": {}, "weryfikacja": []}
        with patch("bedrock._rozmowa", return_value="AKT") as r:
            k.post(f"/api/sprawy/{SPRAWA}/projekt", json={"pola": pola(), "polecenie": ""})
        tekst = r.call_args.args[1][0]["text"]
        assert "KSIEGI" not in tekst and "EKW" not in tekst

    def test_rozbieznosc_wlasciciela_wymaga_wyboru(self, klient, caplog):
        k, katalog = klient
        zapisz_ksiege(katalog, ksiega(dzial2="Anna Inna, udzial 1/1"))
        with caplog.at_level(logging.INFO):
            sp, wynik = generuj(k, pola(wlasciciel="Jan Testowy"))
        blok = sp.call_args.kwargs["ksiegi"]
        assert "WYKRYTE ROZBIEZNOSCI" in blok
        assert '- pole "Sprzedajacy - imie i nazwisko", KW ' + KW in blok
        assert "inny właściciel" in blok and "<<WYBOR" in blok and "nie zgaduj" in blok
        rozb = [w for w in wynik["zrodla"]["weryfikacja"] if w["stan"] == "rozbieznosc"]
        assert [w["pole"] for w in rozb] == ["Sprzedajacy - imie i nazwisko"]
        # Opis rozbieznosci nie powtarza danych osobowych.
        assert "Testowy" not in rozb[0]["opis"] and "Anna" not in rozb[0]["opis"]
        assert "rozbieznosci=1" in caplog.text and "Anna" not in caplog.text

    def test_tylko_ksiegi_wymienione_w_polach(self, klient):
        k, katalog = klient
        zapisz_ksiege(katalog, ksiega())
        zapisz_ksiege(katalog, ksiega(numer=INNA_KW, pobrano="2026-11-11T08:00:00"))
        sp, wynik = generuj(k, pola())
        assert wynik["zrodla"]["ksiegi"] == [KW]
        assert INNA_KW not in sp.call_args.kwargs["ksiegi"]

    def test_bez_numeru_w_polach_wszystkie_ksiegi_z_numerami(self, klient):
        k, katalog = klient
        zapisz_ksiege(katalog, ksiega())
        zapisz_ksiege(katalog, ksiega(numer=INNA_KW, pobrano="2026-11-11T08:00:00"))
        sp, wynik = generuj(k, [{"nazwa": "Cena", "wartosc": "500 000 zl"}])
        assert wynik["zrodla"]["ksiegi"] == [INNA_KW, KW]
        blok = sp.call_args.kwargs["ksiegi"]
        assert f"KONIEC KSIEGI {KW}" in blok and f"KONIEC KSIEGI {INNA_KW}" in blok

    def test_numer_z_polecenia_wybiera_ksiege(self, klient):
        k, katalog = klient
        zapisz_ksiege(katalog, ksiega())
        zapisz_ksiege(katalog, ksiega(numer=INNA_KW))
        _, wynik = generuj(k, [], polecenie=f"Sprzedaz lokalu z KW {INNA_KW.lower()}")
        assert wynik["zrodla"]["ksiegi"] == [INNA_KW]

    def test_kontrola_zasad_dalej_dziala(self, klient):
        k, katalog = klient
        zapisz_ksiege(katalog, ksiega())
        _, wynik = generuj(k, pola())
        assert "zgodnosc" in wynik and isinstance(wynik["zgodnosc"], dict)
        assert (katalog / "zgodnosc.json").exists()


class TestPorownanie:
    def test_rozbieznosc_powierzchni(self):
        w = ekw.porownaj_z_polami([ksiega()], [{"nazwa": "Powierzchnia lokalu", "wartosc": "52,10 m2"}])
        assert [x["stan"] for x in w] == ["rozbieznosc"]

    def test_adres_w_polu_nie_daje_falszywego_alarmu(self):
        w = ekw.porownaj_z_polami([ksiega()], [{"nazwa": "Sprzedajacy", "wartosc":
                                   "Jan Testowy zamieszkaly w Warszawie przy ulicy Dlugiej"}])
        assert w == []

    def test_polskie_znaki_i_wielkosc_liter(self):
        w = ekw.porownaj_z_polami([ksiega(dzial2="ŁUKASZ ŻÓŁTY, udział 1/1")],
                                  [{"nazwa": "Właściciel", "wartosc": "Łukasz Żółty"}])
        assert [x["stan"] for x in w] == ["potwierdza"]

    def test_bez_ksiag_pusto(self):
        assert ekw.porownaj_z_polami([], pola()) == []
        assert prompty.blok_ksiag([]) == ""

    def test_sporzadz_projekt_bez_ksiag_bez_bloku(self):
        with patch("bedrock._rozmowa", return_value="AKT") as r:
            bedrock.sporzadz_projekt(WZOR, pola(), "", None, [])
        assert "EKW" not in r.call_args.args[1][0]["text"]


class TestAtrapaDemo:
    """scripts/demo_odcinek01.py --atrapa-modelu: atrapa przyjmuje ksiegi
    i - jak model - wybiera wariant § 2 ze stanu dzialow III/IV."""

    WZOR_DEMO = ("§ 2. aaa oświadcza, że w dziale III i IV księgi wieczystej nie ma wpisów "
                 "// w dziale IV księgi wieczystej wpisana jest hipoteka, która zostanie wykreślona.")

    def atrapa(self):
        import importlib.util
        import pathlib
        sciezka = pathlib.Path(__file__).parent / "scripts" / "demo_odcinek01.py"
        spec = importlib.util.spec_from_file_location("demo_odcinek01_test", sciezka)
        modul = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modul)
        return modul.atrapa_projektu(0)

    def test_puste_dzialy_pierwszy_wariant(self):
        tekst = self.atrapa()(self.WZOR_DEMO, [], "", ksiegi=prompty.blok_ksiag([ksiega()]))
        assert "nie ma wpisów" in tekst and "hipoteka" not in tekst and "<<WYBOR" not in tekst

    def test_hipoteka_drugi_wariant(self):
        blok = prompty.blok_ksiag([ksiega(dzial4="Hipoteka umowna 100 000 zl")])
        tekst = self.atrapa()(self.WZOR_DEMO, [], "", ksiegi=blok)
        assert "wpisana jest hipoteka" in tekst and "nie ma wpisów" not in tekst

    def test_bez_ksiegi_wybor_jak_dotad(self):
        tekst = self.atrapa()(self.WZOR_DEMO, [], "")
        assert "<<WYBOR:" in tekst
