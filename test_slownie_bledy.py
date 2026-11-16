import pytest

from slownie import liczba_slownie, parsuj_kwote, slownie_kwoty


@pytest.mark.parametrize("tekst", ["abc", "", "zł", ","])
def test_bez_cyfr_podnosi_value_error(tekst):
    with pytest.raises(ValueError, match="Brak kwoty w tekście"):
        parsuj_kwote(tekst)


def test_slownie_kwoty_bez_cyfr_podnosi_value_error():
    with pytest.raises(ValueError, match="Brak kwoty w tekście"):
        slownie_kwoty("abc")


@pytest.mark.parametrize("tekst,zlote,grosze", [
    ("0", 0, 0),
    ("0,00 zł", 0, 0),
    ("250.000,00 zł", 250000, 0),
    (",50", 0, 50),
])
def test_poprawne_kwoty_sie_nie_zmieniaja(tekst, zlote, grosze):
    assert parsuj_kwote(tekst) == (zlote, grosze)


def test_liczba_slownie_sie_nie_zmienia():
    assert liczba_slownie(0) == "zero"
    assert liczba_slownie(250000) == "dwieście pięćdziesiąt tysięcy"
