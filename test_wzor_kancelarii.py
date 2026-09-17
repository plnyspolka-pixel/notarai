"""Testy wzorow pisanych w konwencji kancelarii.

Wzory z kancelarii nie uzywaja {{nazwa}} ani [NAZWA]. Zamiast tego:
- legenda na poczatku:  "aaa - zbywca (Jan Kowalski)"
- "??" w tresci = luka do wypelnienia
- "//" rozdziela warianty tresci
Dane w testach sa zmyslone.
"""
from pathlib import Path

import pytest

from dokumenty import analizuj_wzor, pola_ze_wzoru, wzor_na_tekst
from walidacja import sprawdz_pole

WZOR = """aaa- zbywca (Jan Kowalski)
aa2 – zbywcy (Jana Kowalskiego)
ccc – numer działki
ggg – nr kw
zzz – data aktu

Repertorium A nr_________/2026

AKT NOTARIALNY

Dnia zzz przed notariuszem stawili się:
1. ??, syn ??, (dowód osobisty nr ??, ważny do dnia ??r.), PESEL ??, zamieszkały ??,
§1. aaa oświadczył, że jest właścicielem działki nr ccc, dla której prowadzona jest Kw nr ggg,
a) w dziale II wpisany jest ?? na podstawie ??
// , dla której nie była zakładana księga wieczysta.
§2. aaa sprzedaje za cenę ?? zł (?? złotych), na rzecz aa2.
"""


class TestLegenda:
    def test_legenda_odczytana(self):
        legenda = analizuj_wzor(WZOR)["legenda"]
        assert set(legenda) == {"aaa", "aa2", "ccc", "ggg", "zzz"}

    def test_opis_i_przyklad_rozdzielone(self):
        legenda = analizuj_wzor(WZOR)["legenda"]
        assert legenda["aaa"] == {"opis": "zbywca", "przyklad": "Jan Kowalski"}
        assert legenda["ccc"] == {"opis": "numer działki", "przyklad": ""}

    def test_rozne_myslniki(self):
        legenda = analizuj_wzor("aaa- x\nbbb – y\nccc — z\n\ntresc aaa")["legenda"]
        assert set(legenda) == {"aaa", "bbb", "ccc"}

    def test_legenda_usunieta_z_tresci(self):
        tresc = analizuj_wzor(WZOR)["tresc"]
        assert "zbywca (Jan Kowalski)" not in tresc
        assert "AKT NOTARIALNY" in tresc

    def test_brak_legendy(self):
        wynik = analizuj_wzor("Dnia {{data}} stawil sie ??")
        assert wynik["legenda"] == {}
        assert wynik["tresc"] == "Dnia {{data}} stawil sie ??"

    def test_kod_bez_legendy_nie_jest_polem(self):
        # "aaa" w tresci bez legendy to zwykle slowo
        assert pola_ze_wzoru("stawil sie aaa i bbb") == []


class TestKodyWTresci:
    def test_kod_staje_sie_polem_z_opisem(self):
        pola = pola_ze_wzoru(WZOR)
        assert "aaa: zbywca" in pola
        assert "ggg: nr kw" in pola
        assert "zzz: data aktu" in pola

    def test_kod_tylko_jako_cale_slowo(self):
        wzor = "ggg – nr kw\n\nKw nr ggg oraz eggg i gggx"
        assert pola_ze_wzoru(wzor) == ["ggg: nr kw"]

    def test_warianty_gramatyczne_osobno(self):
        pola = pola_ze_wzoru(WZOR)
        assert "aaa: zbywca" in pola
        assert "aa2: zbywcy" in pola

    def test_duplikaty_kodow_pomijane(self):
        pola = pola_ze_wzoru(WZOR)
        assert pola.count("aaa: zbywca") == 1


class TestZnaczniki:
    def test_liczba_znacznikow(self):
        wynik = analizuj_wzor(WZOR)
        assert len(wynik["znaczniki"]) == WZOR.count("??")

    def test_nazwa_z_kontekstu(self):
        pola = pola_ze_wzoru(WZOR)
        assert pola[1] == "??1: 1. __ , syn …,"

    def test_luka_wlasciwa_i_sasiednie(self):
        pola = pola_ze_wzoru(WZOR)
        pesel = next(p for p in pola if "PESEL __" in p)
        assert pesel.startswith("??5:")
        assert pesel.count("__") == 1

    def test_numeracja_ciagla_i_unikalna(self):
        znaczniki = analizuj_wzor(WZOR)["znaczniki"]
        assert [z["nr"] for z in znaczniki] == list(range(1, len(znaczniki) + 1))
        assert len({z["nazwa"] for z in znaczniki}) == len(znaczniki)


class TestKolejnosc:
    def test_kolejnosc_wystapienia(self):
        pola = pola_ze_wzoru(WZOR)
        assert pola[0] == "zzz: data aktu"
        assert pola.index("aaa: zbywca") < pola.index("ccc: numer działki")
        assert pola.index("ccc: numer działki") < pola.index("ggg: nr kw")

    def test_mieszanie_z_klasycznymi(self):
        wzor = "aaa – zbywca\n\n{{data}} aaa ?? [MIASTO]"
        assert pola_ze_wzoru(wzor) == [
            "data",
            "aaa: zbywca",
            "??1: {{data}} aaa __ [MIASTO]",
            "MIASTO",
        ]


class TestWarianty:
    def test_liczenie_wariantow(self):
        assert analizuj_wzor(WZOR)["warianty"] == 1

    def test_separator_nie_jest_polem(self):
        assert all("//" not in p for p in pola_ze_wzoru(WZOR))


class TestWalidacjaPolZnacznikowych:
    def test_pesel_po_kontekscie(self):
        poprawne, _ = sprawdz_pole("??5: …, ważny do dnia …r.), PESEL __ , zamieszkały", "123")
        assert poprawne is False

    def test_data_waznosci_nie_jest_peselem(self):
        # "PESEL" jest dalej w zdaniu, ale luka to data waznosci dowodu
        poprawne, _ = sprawdz_pole("??4: nr …, ważny do dnia __ r.), PESEL …,", "12.05.2030")
        assert poprawne is None

    def test_kw_po_kontekscie(self):
        poprawne, _ = sprawdz_pole("??9: Kw nr __ z dnia", "KR1K/00012345/7")
        assert poprawne is True

    def test_kod_legendy_kw(self):
        poprawne, _ = sprawdz_pole("ggg: nr kw", "KR1K/00012345/7")
        assert poprawne is True

    def test_cena_odmieniona(self):
        poprawne, komentarz = sprawdz_pole("??12: sprzedaje za cenę __ zł", "50 000")
        assert poprawne is True
        assert komentarz == "50000.00 zl"


WZOR_KANCELARII = Path(__file__).parent / "dane" / "wzory" / "wzor_kancelarii.docx"


@pytest.mark.skipif(not WZOR_KANCELARII.exists(), reason="brak wzoru w dane/wzory")
class TestPrawdziwyWzor:
    """Uruchamiane tylko, gdy w dane/wzory lezy prawdziwy wzor kancelarii."""

    def test_wzor_kancelarii_daje_pola(self):
        wynik = analizuj_wzor(wzor_na_tekst(WZOR_KANCELARII))
        assert len(wynik["legenda"]) >= 10
        assert len(wynik["znaczniki"]) > 50
        assert "ggg: nr kw" in wynik["pola"]


class TestKontekstBezCudzyslowow:
    def test_cudzyslowy_usuniete_z_nazwy(self):
        pola = pola_ze_wzoru('stan cywilny, używający imienia „ ”, zamieszkały ??,')
        assert '"' not in pola[0] and "„" not in pola[0] and "”" not in pola[0]
        assert pola[0] == "??1: stan cywilny, używający imienia , zamieszkały __ ,"
