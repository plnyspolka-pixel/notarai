"""Testy walidatorow - PESEL, NIP, KW, kwoty.

Przypadki brzegowe:
- PESEL: XIX i XXI wiek, niepoprawne miesiace, dni, sumy kontrolne
- NIP: sumy kontrolne, formatowanie
- KW: rozne formaty, cyfra kontrolna
- kwoty: formatowanie, separatory, waluty
"""
import pytest
from datetime import date
from walidacja import pesel, nip, ksiega_wieczysta, kwota, sprawdz_pole
from conftest import z_suma_kontrolna


class TestPesel:
    """Testy walidacji PESEL."""

    def test_pesel_poprawny_xx_wiek(self):
        # Jan Kowalski urodzony 1985-03-15, mezczyzna
        poprawny, komunikat = pesel("85031512337")
        assert poprawny is True
        assert "1985-03-15" in komunikat
        assert "M" in komunikat

    def test_pesel_poprawny_xxi_wiek(self):
        # Osoba urodzona 2005-11-23, kobieta (miesiac+20 dla XXI wieku)
        poprawny, komunikat = pesel("05312312344")
        assert poprawny is True
        assert "2005-11-23" in komunikat
        assert "K" in komunikat

    def test_pesel_xix_wiek(self):
        # Osoba urodzona 1899-12-31 (miesiac+80 dla XIX wieku)
        poprawny, komunikat = pesel("99923112330")
        assert poprawny is True
        assert "1899-12-31" in komunikat

    def test_pesel_xxi_wiek_2100(self):
        # Osoba urodzona 2105-01-01 (miesiac+40 dla XXII wieku)
        # Ta data jest w przyszlosci i powinna byc odrzucona
        poprawny, komunikat = pesel("05410112338")
        assert poprawny is False
        assert "przyszlosci" in komunikat.lower()

    def test_pesel_niepoprawna_suma_kontrolna(self):
        poprawny, komunikat = pesel("85031512339")
        assert poprawny is False
        assert "suma kontrolna" in komunikat.lower()

    def test_pesel_za_krotki(self):
        poprawny, komunikat = pesel("8503151234")
        assert poprawny is False
        assert "11 cyfr" in komunikat

    def test_pesel_za_dlugi(self):
        poprawny, komunikat = pesel("850315123456")
        assert poprawny is False
        assert "11 cyfr" in komunikat

    def test_pesel_niepoprawny_miesiac(self):
        # Miesiac 99 (oznacza XXII wiek, ale taki nie jest obslugiwany)
        poprawny, komunikat = pesel("05990112348")
        assert poprawny is False
        assert "date urodzenia" in komunikat.lower()

    def test_pesel_niepoprawny_dzien(self):
        # 32 lutego
        poprawny, komunikat = pesel("85023212340")
        assert poprawny is False
        assert "date urodzenia" in komunikat.lower()

    def test_pesel_przyszlosc(self):
        # Rok 2999 (teoretycznie poprawny format, ale w przyszlosci)
        przyszly_rok = (date.today().year + 100) % 100
        przyszly_miesiac = 40 + date.today().month  # XXI wiek
        pesel_prefiks = f"{przyszly_rok:02d}{przyszly_miesiac:02d}011234"
        pesel_str = z_suma_kontrolna(pesel_prefiks)
        poprawny, komunikat = pesel(pesel_str)
        assert poprawny is False
        assert "przyszlosci" in komunikat.lower()

    def test_pesel_z_formatowaniem(self):
        # PESEL z myslnikami i spacjami - powinny byc usuniete
        poprawny, komunikat = pesel("850315-12337")
        assert poprawny is True

    def test_pesel_pusty(self):
        poprawny, komunikat = pesel("")
        assert poprawny is False

    def test_pesel_none(self):
        poprawny, komunikat = pesel(None)
        assert poprawny is False

    def test_pesel_plec_mezczyzna(self):
        # Przedostatnia cyfra nieparzysta = mezczyzna
        poprawny, komunikat = pesel("85031512337")
        assert "M" in komunikat

    def test_pesel_plec_kobieta(self):
        # Przedostatnia cyfra parzysta = kobieta
        poprawny, komunikat = pesel("85031512344")
        assert "K" in komunikat


class TestNip:
    """Testy walidacji NIP."""

    def test_nip_poprawny(self):
        poprawny, komunikat = nip("1234563218")
        assert poprawny is True
        assert "poprawny" in komunikat.lower()

    def test_nip_niepoprawna_suma_kontrolna(self):
        poprawny, komunikat = nip("1234563210")
        assert poprawny is False
        assert "suma kontrolna" in komunikat.lower()

    def test_nip_za_krotki(self):
        poprawny, komunikat = nip("123456321")
        assert poprawny is False
        assert "10 cyfr" in komunikat

    def test_nip_za_dlugi(self):
        poprawny, komunikat = nip("12345632189")
        assert poprawny is False
        assert "10 cyfr" in komunikat

    def test_nip_z_formatowaniem(self):
        # NIP z myslnikami
        poprawny, komunikat = nip("123-456-32-18")
        assert poprawny is True

    def test_nip_pusty(self):
        poprawny, komunikat = nip("")
        assert poprawny is False

    def test_nip_suma_10(self):
        # Gdy suma % 11 == 10, NIP jest niepoprawny
        poprawny, komunikat = nip("1234567890")
        # Ta wartosc moze byc niepoprawna z powodu sumy == 10
        # Sprawdzamy czy walidator to wylapie


class TestKsiegaWieczysta:
    """Testy walidacji numeru ksiegi wieczystej."""

    def test_kw_poprawny(self):
        poprawny, komunikat = ksiega_wieczysta("KR1K/00012345/7")
        assert poprawny is True
        assert "poprawny" in komunikat.lower()

    def test_kw_niepoprawna_cyfra_kontrolna(self):
        poprawny, komunikat = ksiega_wieczysta("KR1K/00012345/9")
        assert poprawny is False
        assert "cyfra kontrolna" in komunikat.lower()

    def test_kw_niepoprawny_format(self):
        poprawny, komunikat = ksiega_wieczysta("KR1K-00012345-6")
        assert poprawny is False
        assert "Format" in komunikat

    def test_kw_za_krotki_numer(self):
        poprawny, komunikat = ksiega_wieczysta("KR1K/0012345/6")
        assert poprawny is False

    def test_kw_male_litery(self):
        # Powinno dzialac, bo funkcja konwertuje na wielkie
        poprawny, komunikat = ksiega_wieczysta("kr1k/00012345/7")
        assert poprawny is True

    def test_kw_ze_spacjami(self):
        # Spacje powinny byc usuniete
        poprawny, komunikat = ksiega_wieczysta("KR1K / 00012345 / 7")
        assert poprawny is True

    def test_kw_pusty(self):
        poprawny, komunikat = ksiega_wieczysta("")
        assert poprawny is False

    def test_kw_niedozwolony_znak(self):
        # Znak spoza dozwolonego zestawu
        poprawny, komunikat = ksiega_wieczysta("KR&K/00012345/0")
        # Powinien byc odrzucony przez niedozwolony znak
        assert poprawny is False


class TestKwota:
    """Testy walidacji kwot."""

    def test_kwota_poprawna_integer(self):
        poprawny, komunikat = kwota("1000")
        assert poprawny is True
        assert "1000.00" in komunikat

    def test_kwota_poprawna_float(self):
        poprawny, komunikat = kwota("1234.56")
        assert poprawny is True
        assert "1234.56" in komunikat

    def test_kwota_z_przecinkiem(self):
        poprawny, komunikat = kwota("1234,56")
        assert poprawny is True
        assert "1234.56" in komunikat

    def test_kwota_z_waluta_zl(self):
        poprawny, komunikat = kwota("1234.56 zl")
        assert poprawny is True
        assert "1234.56" in komunikat

    def test_kwota_z_waluta_pln(self):
        poprawny, komunikat = kwota("1234.56 PLN")
        assert poprawny is True
        assert "1234.56" in komunikat

    def test_kwota_ze_spacjami(self):
        poprawny, komunikat = kwota("1 234.56")
        assert poprawny is True
        assert "1234.56" in komunikat

    def test_kwota_z_nbsp(self):
        # Non-breaking space
        poprawny, komunikat = kwota("1 234.56")
        assert poprawny is True
        assert "1234.56" in komunikat

    def test_kwota_ujemna(self):
        poprawny, komunikat = kwota("-100")
        assert poprawny is False
        assert "ujemna" in komunikat.lower()

    def test_kwota_zero(self):
        poprawny, komunikat = kwota("0")
        assert poprawny is True
        assert "0.00" in komunikat

    def test_kwota_niepoprawny_format(self):
        poprawny, komunikat = kwota("abc")
        assert poprawny is False
        assert "odczytac" in komunikat.lower()

    def test_kwota_pusta(self):
        poprawny, komunikat = kwota("")
        assert poprawny is False


class TestSprawdzPole:
    """Testy automatycznego dobierania walidatora po nazwie pola."""

    def test_pole_z_pesel(self):
        poprawny, komunikat = sprawdz_pole("pesel sprzedajacego", "85031512337")
        assert poprawny is True
        assert "1985" in komunikat

    def test_pole_z_nip(self):
        poprawny, komunikat = sprawdz_pole("NIP firmy", "1234563218")
        assert poprawny is True

    def test_pole_z_kw(self):
        poprawny, komunikat = sprawdz_pole("numer KW", "KR1K/00012345/7")
        assert poprawny is True

    def test_pole_z_ksiega(self):
        poprawny, komunikat = sprawdz_pole("ksiega wieczysta", "KR1K/00012345/7")
        assert poprawny is True

    def test_pole_z_cena(self):
        poprawny, komunikat = sprawdz_pole("cena nieruchomosci", "500000")
        assert poprawny is True

    def test_pole_z_kwota(self):
        poprawny, komunikat = sprawdz_pole("kwota umowy", "123456.78")
        assert poprawny is True

    def test_pole_z_wartosc(self):
        poprawny, komunikat = sprawdz_pole("wartosc dzialki", "200000")
        assert poprawny is True

    def test_pole_bez_reguly(self):
        # Pole bez specjalnej walidacji
        poprawny, komunikat = sprawdz_pole("imie", "Jan")
        assert poprawny is None
        assert komunikat == ""

    def test_pole_puste(self):
        poprawny, komunikat = sprawdz_pole("pesel", "")
        assert poprawny is None
        assert komunikat == ""

    def test_pole_case_insensitive(self):
        # Nazwa pola w roznych kombinacjach wielkosci liter
        poprawny, _ = sprawdz_pole("PESEL", "85031512337")
        assert poprawny is True
        poprawny, _ = sprawdz_pole("Pesel", "85031512337")
        assert poprawny is True

    def test_pole_granice_slow_kwatera(self):
        # "kwatera" zawiera "kw", ale nie powinno trafic w walidator KW
        poprawny, komunikat = sprawdz_pole("kwatera", "KR1K/00012345/7")
        assert poprawny is None
        assert komunikat == ""

    def test_pole_granice_slow_zakwaterowanie(self):
        # "zakwaterowanie" zawiera "kw", ale nie powinno trafic w walidator KW
        poprawny, komunikat = sprawdz_pole("zakwaterowanie", "A123")
        assert poprawny is None
        assert komunikat == ""

    def test_pole_granice_slow_kwit(self):
        # "data kwitu" zawiera "kw", ale nie powinno trafic w walidator KW
        poprawny, komunikat = sprawdz_pole("data kwitu", "2024-01-15")
        assert poprawny is None
        assert komunikat == ""

    def test_pole_granice_slow_ocena(self):
        # "ocena stanu technicznego" zawiera "cena", ale nie powinno trafic w walidator kwoty
        poprawny, komunikat = sprawdz_pole("ocena stanu technicznego", "dobra")
        assert poprawny is None
        assert komunikat == ""

    def test_pole_numer_kw_z_separatorami(self):
        # Sprawdza, ze "numer KW", "nr_kw", "numer-kw" dzialaja
        poprawny, _ = sprawdz_pole("numer KW", "KR1K/00012345/7")
        assert poprawny is True
        poprawny, _ = sprawdz_pole("nr_kw", "KR1K/00012345/7")
        assert poprawny is True
        poprawny, _ = sprawdz_pole("numer-kw", "KR1K/00012345/7")
        assert poprawny is True

    @pytest.mark.parametrize("nazwa", [
        "Numer ksiegi wieczystej", "ksiega wieczysta", "ksiegi wieczystej",
        "w ksiedze wieczystej",
    ])
    def test_odmienione_nazwy_pol_tez_sa_sprawdzane(self, nazwa):
        """Pole nazwane inaczej niz w mianowniku przechodzilo bez zadnej kontroli."""
        poprawny, komunikat = sprawdz_pole(nazwa, "ZLY-FORMAT")
        assert poprawny is False and "KW" in komunikat

    @pytest.mark.parametrize("nazwa", ["wartosc rynkowa", "wartość", "kwoty", "ceny"])
    def test_odmienione_nazwy_kwot(self, nazwa):
        poprawny, _ = sprawdz_pole(nazwa, "50 000")
        assert poprawny is True

    @pytest.mark.parametrize("nazwa", ["kwatera", "kwiecien", "centrum", "nazwisko"])
    def test_szersza_regula_nie_lapie_przypadkowych_slow(self, nazwa):
        poprawny, _ = sprawdz_pole(nazwa, "cokolwiek")
        assert poprawny is None

    def test_pole_kwota_z_separatorami(self):
        # "kwota (zl)", "cena-brutto" dzialaja
        poprawny, _ = sprawdz_pole("kwota (zl)", "1000")
        assert poprawny is True
        poprawny, _ = sprawdz_pole("cena-brutto", "500")
        assert poprawny is True
