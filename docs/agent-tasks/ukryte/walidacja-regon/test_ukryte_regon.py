"""Ukryte testy karty walidacja-regon (W6). Agent ich nie widzi; inne przypadki niż w karcie."""
import pytest

from walidacja import REGULY, regon, sprawdz_pole


@pytest.mark.parametrize("wartosc", ["012345675", "730-500-128", "100000050", "0123 4567 5012 39"])
def test_poprawne(wartosc):
    assert regon(wartosc) == (True, "REGON poprawny")


@pytest.mark.parametrize("wartosc", ["012345676", "730500129", "01234567501230"])
def test_bledna_kontrolna(wartosc):
    assert regon(wartosc) == (False, "Bledna cyfra kontrolna REGON")


def test_czternascie_cyfr_ze_zla_dziewiatka():
    # Poprawna końcówka 14-cyfrowa nie ratuje złej cyfry kontrolnej pierwszych dziewięciu.
    ok, _ = regon("01234567601239")
    assert ok is False


@pytest.mark.parametrize("wartosc", ["", "12345678", "1234567890", "0123456750123", "abcdefghi"])
def test_zla_dlugosc(wartosc):
    assert regon(wartosc) == (False, "REGON musi miec 9 albo 14 cyfr")


def test_rejestracja():
    assert REGULY["regon"] is regon
    assert sprawdz_pole("regon", "730500128") == (True, "REGON poprawny")
