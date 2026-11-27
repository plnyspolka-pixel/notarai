"""Ukryte testy karty nazwy-max-dlugosc (W6). Agent ich nie widzi; inne przypadki niż w karcie."""
import nazwy
from nazwy import bezpieczna_nazwa_pliku


def test_limit_z_parametru():
    assert bezpieczna_nazwa_pliku("b" * 30, max_dlugosc=7) == "b" * 7
    assert bezpieczna_nazwa_pliku("b" * 30, 5) == "b" * 5


def test_po_przycieciu_bez_smieci_na_koncu():
    assert bezpieczna_nazwa_pliku("Akt_._ notarialny", max_dlugosc=6) == "Akt"


def test_domyslny_limit_bez_zmian():
    dlugi = "Nowak " * 40
    assert bezpieczna_nazwa_pliku(dlugi) == bezpieczna_nazwa_pliku(dlugi, max_dlugosc=nazwy.MAX_DLUGOSC_NAZWY)
    assert len(bezpieczna_nazwa_pliku(dlugi)) <= nazwy.MAX_DLUGOSC_NAZWY
