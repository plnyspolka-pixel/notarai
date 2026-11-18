"""Ukryte testy karty taksa-kwota-kropki (W6). Agent ich nie widzi; inne przypadki niż w karcie."""
from decimal import Decimal

import pytest

from taksa import kwota


@pytest.mark.parametrize("napis, oczekiwane", [
    ("1.000.000,99 zł", Decimal("1000000.99")),   # kropki i przecinek: kropki to tysiące
    ("2.500,5", Decimal("2500.5")),
    ("12.345.678", Decimal("12345678")),           # same kropki, więcej niż jedna
    ("99.5", Decimal("99.5")),                     # jedna kropka bez przecinka: ułamek, bez zmian
    ("3 000,00 zł", Decimal("3000.00")),           # spacje jak dotąd
])
def test_kropki_jako_separator_tysiecy(napis, oczekiwane):
    assert kwota(napis) == oczekiwane


@pytest.mark.parametrize("napis", ["-1.000,00", "x.y,z", ""])
def test_smieci_i_ujemne_dalej_zero(napis):
    assert kwota(napis) == Decimal("0")
