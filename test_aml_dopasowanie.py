"""Dopasowanie do list sankcyjnych i PEP - przypadki brzegowe przeniesione
z testow finyou (scoring.test.ts): popularne nazwiska, nazwiska dwuczlonowe,
literowki, cyrylica, brak daty urodzenia."""
from datetime import date

import aml_dopasowanie as d


def osoba(nazwa, data=None, kraje=()):
    dd, rok = d.data_czesciowa(data)
    return d.Podmiot([nazwa], "osoba", dd, rok, list(kraje))


def rekord(nazwy, daty=(), kraje=(), rodzaj="osoba", **kw):
    return d.Rekord("test", "1", rodzaj, list(nazwy), list(daty), list(kraje), **kw)


class TestNormalizacja:
    def test_transliteruje_polskie_znaki(self):
        assert d.ascii_fold("Łukasz Żółć-Gęślą") == "Lukasz Zolc-Gesla"
        assert d.znormalizuj("Łukasz Żółć") == "lukasz zolc"

    def test_usuwa_tytuly_i_rozbija_nazwiska_dwuczlonowe(self):
        assert d.tokeny("prof. dr hab. inż. Anna Nowak-Jeziorańska") == ["anna", "nowak", "jezioranska"]
        assert d.tokeny("Mr. John O'Brien, Jr.") == ["john", "obrien"]

    def test_pomija_formy_prawne_podmiotow(self):
        assert d.znormalizuj("„1C-POLAND” Sp. z o.o.", podmiot=True) == "1c poland"
        assert d.znormalizuj("ACRON PAO", podmiot=True) == "acron"

    def test_warianty_cyrylicy(self):
        w = d.warianty_cyrylicy("Шевченко Щербак Жуков")
        assert d.ascii_fold(w["pl"]) == "szewczenko szczerbak zukow"
        assert w["en"] == "shevchenko shcherbak zhukov"
        assert d.ascii_fold(w["iso9"]) == "sevcenko serbak zukov"
        klucze = [x.klucz for x in d.warianty("Александр Лукашенко")]
        assert "aleksandr lukaszenko" in klucze and "aleksandr lukashenko" in klucze

    def test_daty_w_formatach_zrodel(self):
        assert d.data_czesciowa("1959-01-04") == ("1959-01-04", 1959)
        assert d.data_czesciowa("04.01.1959") == ("1959-01-04", 1959)
        assert d.data_czesciowa("1960") == (None, 1960)
        assert d.data_czesciowa("+1954-11-15T00:00:00Z") == ("1954-11-15", 1954)
        assert d.data_z_tekstu_pl("urodzony 5 października 1973 r.") == ("1973-10-05", 1973)

    def test_kraje(self):
        assert d.kraj("Russian Federation") == "RU"
        assert d.kraj("pl") == "PL"
        assert d.kraj("Atlantyda") is None


class TestPodobienstwo:
    def test_jaro_winkler_klasyczne(self):
        assert round(d.jaro_winkler("martha", "marhta"), 3) == 0.961
        assert d.jaro_winkler("kowalski", "kowalski") == 1

    def test_niezalezne_od_kolejnosci(self):
        assert d.podobienstwo_zbiorow(["kowalski", "jan"], ["jan", "kowalski"])[0] == 1

    def test_inicjal_pasuje_do_imienia(self):
        assert d.podobienstwo_tokenow("j", "jan") == 0.9

    def test_szkielet_fonetyczny(self):
        assert d.szkielet("szewczenko") == d.szkielet("shevchenko")


class TestOcena:
    def test_pelna_zgodnosc_to_silne_trafienie(self):
        o = d.ocen(osoba("Andrzej Adamczyk", "1959-01-04"),
                   rekord(["Andrzej Mieczysław Adamczyk"], ["1959-01-04"], ["PL"]))
        assert o.pasmo == "silne" and o.data == "zgodna"

    def test_brak_daty_w_zrodle_to_najwyzej_do_weryfikacji(self):
        o = d.ocen(osoba("Jan Kowalski", "1980-05-05"), rekord(["Jan Kowalski"]))
        assert o.razem == d.DOMYSLNE.prog_silne - 1
        assert o.pasmo == "mozliwe"
        assert "zrodle" in o.ograniczenie

    def test_brak_daty_strony_tez_ogranicza(self):
        o = d.ocen(osoba("Jan Kowalski"), rekord(["Jan Kowalski"], ["1980-05-05"]))
        assert o.razem == 89 and "strony" in o.ograniczenie

    def test_niezgodna_data_obniza_ale_nie_odrzuca(self):
        o = d.ocen(osoba("Jan Kowalski", "1980-05-05"), rekord(["Jan Kowalski"], ["1950-02-02"]))
        assert o.data == "niezgodna" and o.razem == 75 and o.pasmo == "mozliwe"

    def test_zgodny_rok_gdy_zrodlo_zna_tylko_rok(self):
        o = d.ocen(osoba("Viktor Petrov", "1965-03-01"), rekord(["Viktor Petrov"], ["1965"]))
        assert o.data == "zgodny_rok" and o.pasmo == "silne"

    def test_inne_imie_to_brak_trafienia(self):
        o = d.ocen(osoba("Piotr Kowalski", "1980-05-05"), rekord(["Jan Kowalski"], ["1980-05-05"]))
        assert o.pasmo == "brak"

    def test_literowka_i_odwrocona_kolejnosc(self):
        o = d.ocen(osoba("Lukashenka Alexandr", "1954-08-30"), rekord(["Aleksandr Lukashenko"], ["1954-08-30"]))
        assert o.pasmo == "silne"

    def test_cyrylica_na_liscie(self):
        o = d.ocen(osoba("Aleksandr Łukaszenko", "1954-08-30"), rekord(["Александр Лукашенко"], ["1954-08-30"]))
        assert o.pasmo == "silne"

    def test_premie_nie_podnosza_slabej_nazwy(self):
        o = d.ocen(osoba("Anna Nowak", "1980-01-01", ["PL"]), rekord(["Zofia Wiśniewska"], ["1980-01-01"], ["PL"]))
        assert o.razem <= o.wynik_nazwy < 70

    def test_podmiot_bez_daty(self):
        o = d.ocen(d.Podmiot(["ACRON PAO"], "podmiot"), rekord(["ACRON PAO"], rodzaj="podmiot"))
        assert o.data == "nie_dotyczy" and o.razem == 100


class TestIndeks:
    def zbuduj(self):
        return d.Indeks([
            rekord(["Saddam Hussein Al-Tikriti", "Abu Ali"], ["1937-04-28"], ["IQ"]),
            rekord(["Apti Aronovich ALAUDINOV"], ["1973-10-05"], ["RU"]),
            rekord(["ACRON PAO"], rodzaj="podmiot"),
            rekord(["Jan Kowalski"], ["1950-02-02"]),
        ])

    def test_znajduje_po_literowce(self):
        trafienia = self.zbuduj().szukaj(osoba("Apti Alaudinow", "1973-10-05"))
        assert trafienia and trafienia[0][0].pasmo == "silne"

    def test_nie_zwraca_osob_dla_podmiotu(self):
        trafienia = self.zbuduj().szukaj(d.Podmiot(["Acron"], "podmiot"))
        assert [r.nazwy[0] for _, r in trafienia] == ["ACRON PAO"]

    def test_brak_trafien_dla_obcego_nazwiska(self):
        assert self.zbuduj().szukaj(osoba("Zofia Wiśniewska", "1990-01-01")) == []

    def test_slownik_i_z_powrotem(self):
        r = rekord(["Jan Kowalski"], ["1950"], funkcje=[{"tytul": "posel", "od": "2019-11-12", "do": None}])
        assert d.Rekord.ze_slownika(r.slownik()) == r


class TestStatusPep:
    def test_funkcja_trwa(self):
        r = rekord(["X"], funkcje=[{"tytul": "posel", "od": "2023-11-13", "do": None}], aktualny=True)
        assert d.pep_status(r, date(2026, 11, 7)) == "pep"

    def test_w_karencji_12_miesiecy(self):
        r = rekord(["X"], funkcje=[{"tytul": "minister", "od": "2020-01-01", "do": "2026-01-15"}], aktualny=False)
        assert d.pep_status(r, date(2026, 11, 7)) == "pep"

    def test_po_karencji_byly_pep(self):
        r = rekord(["X"], funkcje=[{"tytul": "minister", "od": "2005-01-01", "do": "2007-11-16"}], aktualny=False)
        assert d.pep_status(r, date(2026, 11, 7)) == "byly_pep"
