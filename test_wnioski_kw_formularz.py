"""Wnioski KW - dane formularza i kroki portalu. Bez sieci i bez zapisu:
same dane zmyslone (zaden prawdziwy PESEL ani numer KW z rzeczywistoscia)."""
import wnioski_kw
from conftest import z_suma_kontrolna

PESEL_1 = z_suma_kontrolna("90010112345")
PESEL_2 = z_suma_kontrolna("85021554321")


def dane_wniosku():
    """Pelny, poprawny wniosek: dwa uczestnicy, dwa zadania, komplet podstawy."""
    return {
        "numer_kw": "WA4M/00160286/2",
        "sad": "Sad Rejonowy Testowy, Wydzial I Gospodarczy",
        "uczestnicy": [
            {"nazwa": "Anna Testowa", "rola": "wnioskodawca", "pesel": PESEL_1,
             "adres": "ul. Prosta 1, Testowo"},
            {"nazwa": "Adam Testowy", "rola": "uczestnik", "pesel": PESEL_2,
             "adres": "ul. Prosta 2, Testowo"},
        ],
        "zadania": [
            {"rodzaj": "wpis_wlasnosci", "na_rzecz": ["Anna Testowa"], "udzial": "1/2"},
            {"rodzaj": "wpis_hipoteki", "na_rzecz": ["Adam Testowy"],
             "suma": "150000", "waluta": "PLN", "rodzaj_hipoteki": "umowna"},
        ],
        "akt": {"rep_a": "1234/2025", "data": "2025-06-01",
                "notariusz": "not. Testowy", "siedziba": "Testowo, ul. Prosta 10"},
        "dokumenty": [],
    }


def _wniosek():
    wniosek = wnioski_kw.przygotuj(dane_wniosku())
    assert wniosek["gotowy"] and not wniosek["braki"]
    return wniosek


def test_przygotuj_pelny_wniosek_jest_gotowy():
    wniosek = _wniosek()
    assert wniosek["gotowy"] is True
    assert wniosek["braki"] == []
    assert wniosek["numer_kw"] == "WA4M/00160286/2"


def test_dane_formularza_klucze_i_wartosci():
    dane = wnioski_kw.dane_formularza(_wniosek())
    # uczestnicy 1:1 z danymi wejsciowymi
    assert dane["uczestnik_1_nazwa"] == "Anna Testowa"
    assert dane["uczestnik_1_pesel"] == PESEL_1
    assert dane["uczestnik_2_nazwa"] == "Adam Testowy"
    assert dane["uczestnik_2_pesel"] == PESEL_2
    # zadania 1:1 z danymi wejsciowymi (dzial wg ZADANIA, tresc opis + na rzecz)
    assert dane["zadanie_1_dzial"] == "II"
    assert dane["zadanie_1_tresc"] == "Wpis własności / użytkowania wieczystego na rzecz Anna Testowa"
    assert dane["zadanie_2_dzial"] == "IV"
    assert dane["zadanie_2_tresc"] == "Wpis hipoteki na rzecz Adam Testowy"
    # podstawowa czesc formularza
    assert dane["sad"] == "Sad Rejonowy Testowy, Wydzial I Gospodarczy"
    assert dane["numer_kw"] == "WA4M/00160286/2"
    assert dane["rep_a"] == "1234/2025"
    assert dane["data_aktu"] == "2025-06-01"


def test_pakiet_portalu_kolejnosc_krokow():
    wniosek = _wniosek()
    kroki = wnioski_kw.pakiet_portalu(wniosek)
    nazwy = [k["krok"] for k in kroki]
    # stala kolejnosc formularza portalu: sad -> uczestnicy -> zadania -> podstawa -> oplata -> stop
    assert nazwy == ["Sad i ksiega", "Uczestnik", "Uczestnik", "Zadanie", "Zadanie",
                     "Podstawa wpisu - akt notarialny", "Opłata sądowa",
                     "STOP - podpis i wyslanie"]
    # pola pierwszego kroku z danych wniosku
    assert kroki[0]["pola"]["Sad / wydzial"] == wniosek["sad"]
    assert kroki[0]["pola"]["Numer księgi wieczystej"] == "WA4M/00160286/2"
    # krok STOP: zatrzymanie przed podpisem i wyslaniem - tekst wprost z kodu
    assert kroki[-1]["pola"] == {
        "Kto": "notariusz, kwalifikowanym podpisem elektronicznym w portalu MS",
        "Potem": "wpisz w notarai numer REP.C - wniosek trafi do repertorium C"}


def test_wniosek_bez_uczestnikow_niegotowy():
    dane = dane_wniosku()
    dane["uczestnicy"] = []
    wniosek = wnioski_kw.przygotuj(dane)
    assert wniosek["gotowy"] is False
    assert wniosek["braki"]
    assert "Co najmniej jeden uczestnik" in wniosek["braki"]
