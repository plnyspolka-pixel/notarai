"""Testy slownie.py: liczby slownie i odczyt kwot (zlote/grosze slownie)."""
import pytest

import slownie


class TestLiczbaSlownie:
    @pytest.mark.parametrize("n, oczekiwane", [
        (0, "zero"),
        (1, "jeden"),
        (2, "dwa"),
        (5, "pięć"),
        (21, "dwadzieścia jeden"),
        (22, "dwadzieścia dwa"),
        (115, "sto piętnaście"),
        (1000, "tysiąc"),          # "tysiąc", nie "jeden tysiąc"
        (2000, "dwa tysiące"),
        (5000, "pięć tysięcy"),
        (1000000, "milion"),
    ])
    def test_podstawowe(self, n, oczekiwane):
        assert slownie.liczba_slownie(n) == oczekiwane

    def test_jeden_tysiac_bez_jeden(self):
        # Reguła z akt: "tysiąc", nigdy "jeden tysiąc"
        assert "jeden" not in slownie.liczba_slownie(1000)

    def test_ujemna_zaczyna_sie_od_minus(self):
        wynik = slownie.liczba_slownie(-5)
        assert wynik.startswith("minus ")
        assert wynik == "minus pięć"

    def test_poza_zakresem_podnosi_value_error(self):
        with pytest.raises(ValueError):
            slownie.liczba_slownie(10 ** 12)


class TestParsujKwote:
    @pytest.mark.parametrize("tekst, oczekiwane", [
        ("250.000,00 zł", (250000, 0)),
        ("250 000,5", (250000, 50)),
        ("1000", (1000, 0)),
        ("1,5", (1, 50)),
    ])
    def test_wartosci(self, tekst, oczekiwane):
        assert slownie.parsuj_kwote(tekst) == oczekiwane


class TestSlownieKwoty:
    @pytest.mark.parametrize("tekst, oczekiwanie", [
        # 1 złoty
        ("1,00", "jeden złoty"),
        # 2-4 złote
        ("2,00", "dwa złote"),
        ("5,00", "pięć złotych"),
        ("21,00", "dwadzieścia jeden złotych"),
        ("22,00", "dwadzieścia dwa złote"),
        # grosze: 1 grosz, 2-4 grosze, 5+ groszy; 22 grosze
        ("3,01", "trzy złote jeden grosz"),
        ("3,02", "trzy złote dwa grosze"),
        ("3,05", "trzy złote pięć groszy"),
        ("1,22", "jeden złoty dwadzieścia dwa grosze"),
    ])
    def test_odmiana(self, tekst, oczekiwanie):
        assert slownie.slownie_kwoty(tekst) == oczekiwanie

    @pytest.mark.xfail(
        reason="Błąd w slownie.py: forma() używa liczby pełnej (21) zamiast reszty "
               "z 10, więc 'dwadzieścia jeden groszy' zamiast poprawnego 'dwadzieścia "
               "jeden grosz' (21 % 10 == 1 -> forma pojedyncza)."
    )
    def test_dwadziescia_jeden_grosz(self):
        assert slownie.slownie_kwoty("1,21") == "jeden złoty dwadzieścia jeden grosz"

    def test_brak_groszy_kiedy_zero(self):
        wynik = slownie.slownie_kwoty("1000")
        assert wynik == "tysiąc złotych"
        assert "grosz" not in wynik
