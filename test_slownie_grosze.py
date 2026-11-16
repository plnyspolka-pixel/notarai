"""Testy slownie.slownie_kwoty - grosze slownie albo jako ulamek."""
import pytest

import slownie

_KWOTY = ["1000,50", "1000,05", "1000"]


@pytest.mark.parametrize("tekst", _KWOTY)
def test_grosze_slownie_domyślnie(tekst):
    assert slownie.slownie_kwoty(tekst) == slownie.slownie_kwoty(tekst, True)


@pytest.mark.parametrize("tekst,końcówka", [
    ("1000,50", "tysiąc złotych pięćdziesiąt groszy"),
    ("1000,05", "tysiąc złotych pięć groszy"),
    ("1000", "tysiąc złotych"),
])
def test_grosze_slownie(tekst, końcówka):
    assert slownie.slownie_kwoty(tekst, grosze_slownie=True).endswith(końcówka)


@pytest.mark.parametrize("tekst,końcówka", [
    ("1000,50", "tysiąc złotych 50/100"),
    ("1000,05", "tysiąc złotych 05/100"),
    ("1000", "tysiąc złotych 00/100"),
])
def test_grosze_jako_ulamek(tekst, końcówka):
    assert slownie.slownie_kwoty(tekst, grosze_slownie=False).endswith(końcówka)
