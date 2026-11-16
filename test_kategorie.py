"""Kategorie dokumentow: bez_ogonkow i nazwy slownikowe (RODZAJE, CZESCI, OBSZARY)."""
import pytest

import kategorie


class TestBezOgonkow:
    def test_znak_i_wielkosc(self):
        assert kategorie.bez_ogonkow("Stawający ŁĄKA") == "stawajacy laka"

    def test_polskie_znaki(self):
        assert kategorie.bez_ogonkow("Żółć") == "zolc"

    def test_none_zwraca_pusty(self):
        assert kategorie.bez_ogonkow(None) == ""

    def test_pusty_zwraca_pusty(self):
        assert kategorie.bez_ogonkow("") == ""

    def test_bez_polskich_znakow_wraca_male(self):
        assert kategorie.bez_ogonkow("Umowa Sprzedazy ABC") == "umowa sprzedazy abc"


class TestNazwySlownikowe:
    def test_nazwa_rodzaju(self):
        klucz = next(iter(kategorie.RODZAJE))
        assert kategorie.nazwa_rodzaju(klucz) == kategorie.RODZAJE[klucz]["nazwa"]

    def test_nazwa_rodzaju_nieznana(self):
        assert kategorie.nazwa_rodzaju("nie_znam_takiego") == kategorie.NAZWA_INNEGO

    def test_nazwa_czesci(self):
        klucz = next(iter(kategorie.CZESCI))
        assert kategorie.nazwa_czesci(klucz) == kategorie.CZESCI[klucz]["nazwa"]

    def test_nazwa_czesci_nieznana(self):
        assert kategorie.nazwa_czesci("nie_znam_takiej") == kategorie.NAZWA_INNEJ

    def test_nazwa_obszaru(self):
        klucz = next(iter(kategorie.OBSZARY))
        assert kategorie.nazwa_obszaru(klucz) == kategorie.OBSZARY[klucz]["nazwa"]

    def test_nazwa_obszaru_nieznana(self):
        assert kategorie.nazwa_obszaru("nie_znam_takiego") == kategorie.OBSZARY["inne"]["nazwa"]


class TestSlowniki:
    def test_rodzaie_maja_nazwy(self):
        for klucz, wpis in kategorie.RODZAJE.items():
            assert wpis.get("nazwa", "").strip(), klucz
