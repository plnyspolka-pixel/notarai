"""Testy klauzule.py - zapora danych osobowych, podobienstwo, pola szkieletu.

Przypadki brzegowe:
- ma_dane_osobowe: PESEL, numer ksiegi wieczystej, dowod osobisty (z i bez
  spacji), e-mail; szkielet z samymi polami, 10 i 12 cyfr, pusty napis, None
- podobienstwo: 1.0 dla zdan identycznych (takze gdy roznia sie tylko polskimi
  znakami i wielkoscia liter), 0.0 przy pustej stronie, wartosc z (0, 1) dla
  zdan czesciowo wspolnych, symetria
- pola_szkieletu: pola w klamrach wedlug wzoru _KLAMRY ({A-Z_}), posortowane,
  bez powtorzen; pusta lista bez pol i dla None
"""
from klauzule import ma_dane_osobowe, podobienstwo, pola_szkieletu


class TestMaDaneOsobowe:
    """Zapora przed zapisem: PESEL, KW, dowod osobisty, e-mail."""

    def test_pesel_jedenascie_cyfr(self):
        assert ma_dane_osobowe("Wplata 500 zl za akt nr 85031512337")

    def test_numer_ksiegi_wiecznej(self):
        assert ma_dane_osobowe("Nieruchomosc z ksiega wieczysta KR1K/00012345/7")

    def test_numer_dowodu_bez_spacji(self):
        assert ma_dane_osobowe("Dowod osobisty ABC123456 z wydanego urzedu")

    def test_numer_dowodu_z_spacja(self):
        assert ma_dane_osobowe("Dowod osobisty ABC 123456 z wydanego urzedu")

    def test_adres_e_mail(self):
        assert ma_dane_osobowe("Odpis wyslano na kontakt@przyklad.dom")

    def test_szkielet_samymi_polami(self):
        assert not ma_dane_osobowe("{OSOBA} sprzedaje {NIERUCHOMOSC} za {KWOTA} {POW}")

    def test_dziesiec_cyfr_to_za_krotko(self):
        assert not ma_dane_osobowe("Czynsz wynosi 1234567890 zl za rok")

    def test_dwanzescie_cyfr_to_za_dlugi_ciag(self):
        assert not ma_dane_osobowe("Numer operacji 123456789012 w banku")

    def test_pusty_napis(self):
        assert not ma_dane_osobowe("")

    def test_none(self):
        assert not ma_dane_osobowe(None)


class TestPodobienstwo:
    """0..1 - czy dwie klauzule to to samo sformulowanie."""

    def test_identyczne_zdania(self):
        zdanie = "Sprzedawca przekazuje nabywcy nieruchomosc w stanie istniejacym."
        assert podobienstwo(zdanie, zdanie) == 1.0

    def test_tylko_inne_polskie_znaki(self):
        assert podobienstwo('Strony ustalają, że cena wynosi określona kwotę.',
                            'STRONY USTALAJA, ZE CENA WYNOSI OKRESLONA KWOTE.') == 1.0

    def test_tylko_inne_wielkosc_liter(self):
        assert podobienstwo('Strony ustalaja, ze cena wynosi okreslona kwote.',
                            'STRONY USTALAJA, ZE CENA WYNOSI OKRESLONA KWOTE.') == 1.0

    def test_pierwsza_strona_pusta(self):
        assert podobienstwo("", "Jakies zdanie klauzuli.") == 0.0

    def test_druga_strona_pusta(self):
        assert podobienstwo("Jakies zdanie klauzuli.", "") == 0.0

    def test_czesciowo_wspolne_miedzy_zero_i_jedna(self):
        a = "Nabywca przyjmuje nieruchomosc wraz z jej obciazeniami."
        b = "Nabywca przyjmuje nieruchomosc bez zadnych obciazen."
        assert 0.0 < podobienstwo(a, b) < 1.0

    def test_symetria(self):
        a = "Strony moga wyznaczyc termin odbioru dokumentow w dowolnym czasie."
        b = "Strony wyznaczaja termin odbioru dokumentow z trzydniowym wyprzedzeniem."
        assert podobienstwo(a, b) == podobienstwo(b, a)


class TestPolaSzkieletu:
    """Nazwy pol w klamrach wedlug wzoru _KLAMRY: {A-Z_}."""

    def test_posortowane_bez_powtorzen(self):
        szkielet = "{OSOBA} zbywa {NIERUCHOMOSC} za {KWOTA} na rzecz {OSOBA}"
        assert pola_szkieletu(szkielet) == ["{KWOTA}", "{NIERUCHOMOSC}", "{OSOBA}"]

    def test_pola_wieloznakowe_i_z_podkreSleniem(self):
        assert pola_szkieletu("Zobacz {MIEJSCOWOSC}") == ["{MIEJSCOWOSC}"]
        assert pola_szkieletu("Zobacz {KWOTA_SLOWNIE} i {MIEJSCOWOSC}") == [
            "{KWOTA_SLOWNIE}",
            "{MIEJSCOWOSC}",
        ]

    def test_brak_pol(self):
        assert pola_szkieletu("Zwykle zdanie bez zadnych klamer.") == []

    def test_none(self):
        assert pola_szkieletu(None) == []
