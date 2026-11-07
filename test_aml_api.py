"""Sprawdzenia AML przez API: strony z odczytu sprawy na listach, decyzja
notariusza, CRBR, stan list. Listy to atrapa indeksu, bramka CRBR to atrapa.
Zero sieci, zero pelnych PESEL-i w sladzie."""
import json

import pytest
from fastapi.testclient import TestClient

import aml_dopasowanie as d
import aml_listy
import app as modul
import config
import crbr
from conftest import z_suma_kontrolna

PESEL_JAN = z_suma_kontrolna("8005051234")      # ur. 1980-05-05
PESEL_ANNA = z_suma_kontrolna("7501014567")     # ur. 1975-01-01


@pytest.fixture
def klient(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "SPRAWY", tmp_path)
    monkeypatch.setattr(config, "DANE", tmp_path)
    sprawa = tmp_path / "abc123"
    sprawa.mkdir()
    (sprawa / "sprawa.json").write_text(json.dumps({"id": "abc123", "nazwa": "test"}), "utf-8")
    (sprawa / "odczyt.json").write_text(json.dumps({"pola": [
        {"nazwa": "aaa: zbywca (imie i nazwisko)", "wartosc": "Jan Kowalski"},
        {"nazwa": "pesel zbywcy", "wartosc": PESEL_JAN},
        {"nazwa": "bbb: nabywca (imie i nazwisko)", "wartosc": "Anna Nowak"},
        {"nazwa": "pesel nabywcy", "wartosc": PESEL_ANNA},
        {"nazwa": "nip nabywcy", "wartosc": "526-104-08-28"},
    ]}, ensure_ascii=False), "utf-8")
    sankcje = d.Indeks([d.Rekord("mswia", "x", "osoba", ["Jan Kowalski"], ["1980-05-05"], ["RU"], program="PL-UA-2022",
                                 wpisano="2022-04-26", adres_zrodla="https://gov.pl/x")])
    pep = d.Indeks([d.Rekord("sejm", "y", "osoba", ["Anna Nowak"], ["1975-01-01"], ["PL"],
                             funkcje=[{"tytul": "Posel na Sejm RP (10. kadencja)", "kod": "PL-007",
                                       "od": "2023-11-13", "do": None}], aktualny=True)])
    monkeypatch.setattr(aml_listy, "gotowe", lambda kategoria: True)
    monkeypatch.setattr(aml_listy, "indeks", lambda kategoria: (sankcje if kategoria == "sankcje" else pep,
                                                                 [f"{kategoria} z 2026-11-07"]))
    return TestClient(modul.app)


def test_wymaga_potwierdzenia(klient):
    assert klient.post("/api/sprawy/abc123/aml", json={}).status_code == 400


def test_strony_z_odczytu_na_obu_listach(klient):
    odp = klient.post("/api/sprawy/abc123/aml", json={"potwierdzam": True})
    assert odp.status_code == 200, odp.text
    wpisy = odp.json()
    assert [(w["rejestr"], w["status"]) for w in wpisy] == [
        ("SANKCJE", "wpis"), ("PEP", "brak_wpisu"), ("SANKCJE", "brak_wpisu"), ("PEP", "wpis")]
    jan = wpisy[0]
    assert jan["etykieta"] == "zbywca" and jan["zapytanie"] == "Jan Kowalski (8005*******)"
    assert jan["trafienia"][0]["wynik"] == 100 and jan["trafienia"][0]["zrodlo"] == "mswia"
    assert "mswia" in jan["trafienia"][0]["etykieta_zrodla"].lower() or "MSWiA" in jan["trafienia"][0]["etykieta_zrodla"]
    anna = wpisy[3]
    assert anna["trafienia"][0]["status_pep"] == "pep" and anna["trafienia"][0]["funkcje"]
    tekst = json.dumps(wpisy)
    assert PESEL_JAN not in tekst and PESEL_ANNA not in tekst


def test_podane_osoby_zamiast_odczytu(klient):
    odp = klient.post("/api/sprawy/abc123/aml", json={
        "potwierdzam": True, "rejestry": ["SANKCJE"],
        "strony": [{"imie_nazwisko": "Zofia Wiśniewska", "pesel": "", "etykieta": "pelnomocnik"}]})
    assert odp.status_code == 200
    assert len(odp.json()) == 1
    assert odp.json()[0]["status"] == "brak_wpisu" and odp.json()[0]["zapytanie"] == "Zofia Wiśniewska"


def test_nieznana_lista(klient):
    assert klient.post("/api/sprawy/abc123/aml", json={"potwierdzam": True, "rejestry": ["KRD"]}).status_code == 400


def test_listy_niepobrane_daja_niedostepny(klient, monkeypatch):
    monkeypatch.setattr(aml_listy, "gotowe", lambda kategoria: False)
    wpisy = klient.post("/api/sprawy/abc123/aml", json={"potwierdzam": True, "rejestry": ["PEP"]}).json()
    assert {w["status"] for w in wpisy} == {"niedostepny"}


def test_decyzja_notariusza(klient):
    klient.post("/api/sprawy/abc123/aml", json={"potwierdzam": True, "rejestry": ["SANKCJE"]})
    # za krotkie uzasadnienie
    odp = klient.post("/api/sprawy/abc123/sprawdzenia/decyzja",
                      json={"indeks": 0, "decyzja": "falszywe_trafienie", "uzasadnienie": "nie"})
    assert odp.status_code == 400
    # PESEL w uzasadnieniu
    odp = klient.post("/api/sprawy/abc123/sprawdzenia/decyzja",
                      json={"indeks": 0, "decyzja": "falszywe_trafienie", "uzasadnienie": f"to nie on {PESEL_JAN}"})
    assert odp.status_code == 400
    odp = klient.post("/api/sprawy/abc123/sprawdzenia/decyzja",
                      json={"indeks": 0, "decyzja": "falszywe_trafienie",
                            "uzasadnienie": "Inne obywatelstwo i miejsce urodzenia wg dowodu."})
    assert odp.status_code == 200, odp.text
    wpisy = odp.json()
    assert wpisy[-1]["decyzja"] == "falszywe_trafienie" and wpisy[-1]["dotyczy"] == 0
    assert wpisy[-1]["status"] == "brak_wpisu" and wpisy[0]["status"] == "wpis"   # stary wpis bez zmian
    # druga decyzja o tym samym wpisie nie przechodzi
    odp = klient.post("/api/sprawy/abc123/sprawdzenia/decyzja",
                      json={"indeks": 0, "decyzja": "potwierdzone", "uzasadnienie": "jednak to ta osoba, hmm"})
    assert odp.status_code == 400
    # decyzja o wpisie "brak_wpisu" (nabywca na sankcjach) nie ma sensu
    odp = klient.post("/api/sprawy/abc123/sprawdzenia/decyzja",
                      json={"indeks": 1, "decyzja": "potwierdzone", "uzasadnienie": "cokolwiek dluzszego"})
    assert odp.status_code == 400


def test_crbr_przez_atrape(klient, monkeypatch):
    def atrapa(nip=None, krs=None, nazwa=None, klient=None):
        assert crbr.normalizuj_nip(nip) == "5261040828"
        return crbr.WynikCRBR("ok", "Wpis w CRBR.", spolka=crbr.Spolka("5261040828", "0000012345", "PRZYKLAD SP. Z O.O."),
                              beneficjenci=[crbr.Osoba("Jan", "Kowalski", "8005*******", "1980-05-05", ["Polska"],
                                                       uprawnienia="udzialy 60 proc.")],
                              zglaszajacy=[crbr.Osoba("Anna", "Nowak", funkcja="prezes zarzadu")])
    monkeypatch.setattr(crbr, "sprawdz", atrapa)
    assert klient.post("/api/sprawy/abc123/crbr", json={"nip": "5261040828"}).status_code == 400
    odp = klient.post("/api/sprawy/abc123/crbr", json={"nip": "526-104-08-28", "etykieta": "nabywca", "potwierdzam": True})
    assert odp.status_code == 200, odp.text
    w = odp.json()[-1]
    assert w["rejestr"] == "CRBR" and w["status"] == "wpis" and w["zapytanie"] == "NIP 5261040828"
    assert "Strony czynnosci wsrod beneficjentow: Jan Kowalski" in w["szczegoly"]
    assert "poza CRBR: Anna Nowak" in w["szczegoly"]
    beneficjent = next(t for t in w["trafienia"] if t["rola"] == "beneficjent")
    assert beneficjent["strona_czynnosci"] is True and beneficjent["pesel"] == "8005*******"


def test_crbr_brak_i_bledne_dane(klient, monkeypatch):
    monkeypatch.setattr(crbr, "sprawdz", lambda *a, **k: crbr.WynikCRBR("brak", "Brak wpisu w CRBR dla podanego kryterium."))
    w = klient.post("/api/sprawy/abc123/crbr", json={"krs": "12345", "potwierdzam": True}).json()[-1]
    assert w["status"] == "brak_wpisu" and w["zapytanie"] == "KRS 0000012345"


def test_crbr_bledne_dane_bez_sieci(klient):
    # crbr.sprawdz odrzuca za krotka nazwe, zanim cokolwiek wysle
    assert klient.post("/api/sprawy/abc123/crbr", json={"nazwa": "ab", "potwierdzam": True}).status_code == 400


def test_stan_list_i_odswiezanie_tylko_dla_admina(klient, monkeypatch):
    monkeypatch.setattr(aml_listy.magazyn, "TRYB", "lokalny")
    odp = klient.get("/api/aml/listy")
    assert odp.status_code == 200
    assert {s["zrodlo"] for s in odp.json()} >= {"eu_fsf", "un_sc", "mswia", "sejm", "kprm", "wikidata"}
    assert klient.post("/api/admin/aml/listy/odswiez").status_code in (401, 503)
