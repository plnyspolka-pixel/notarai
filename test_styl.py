"""Testy styl._przewaga. Dane syntetyczne, bez sieci."""
import pytest

from styl import _przewaga


@pytest.mark.parametrize("licznik,minimum,udzial", [
    # suma ponizej minimum - brak dominacji
    ({"a": 1, "b": 2}, 4, 0.6),
    ({"a": 5}, 6, 0.6),
    ({"a": 2}, 3, 0.75),
    ({}, 1, 0.6),
])
def test_suma_ponizej_minimum_zwraca_none(licznik, minimum, udzial):
    assert _przewaga(licznik, minimum, udzial) is None


@pytest.mark.parametrize("licznik,minimum,udzial,zwyciezca", [
    # suma rowna minimum i udziat dokladnie rowny progowi - granica wlaczona
    ({"a": 6, "b": 4}, 10, 0.6, "a"),
    ({"x": 3}, 3, 1.0, "x"),
])
def test_granica_minimum_i_udzialu_wlaczona(licznik, minimum, udzial, zwyciezca):
    p = _przewaga(licznik, minimum, udzial)
    assert p is not None and len(p) == 3
    assert p[0] == zwyciezca
    assert p[1] == max(licznik.values())
    assert p[2] == sum(licznik.values())


@pytest.mark.parametrize("licznik,minimum,udzial", [
    # udziat tuz ponizej progu (np. 6/10 = 0.6 < 0.61)
    ({"a": 6, "b": 4}, 10, 0.61),
    ({"a": 5, "b": 5}, 10, 0.55),
    ({"a": 7, "b": 3}, 10, 0.71),
])
def test_udziat_tuz_ponizej_progu_zwraca_none(licznik, minimum, udzial):
    assert _przewaga(licznik, minimum, udzial) is None


@pytest.mark.parametrize("licznik,minimum,udzial", [
    ({"sam": 1}, 1, 0.99),
    ({"sam": 7}, 3, 0.5),
    ({"sam": 100}, 10, 1.0),
])
def test_jeden_wariant_w_liczniku_zwraca_krotke_z_cala_suma(licznik, minimum, udzial):
    p = _przewaga(licznik, minimum, udzial)
    assert p is not None and len(p) == 3
    assert p[0] == "sam"
    # jedyny wariant: jego liczba wystapien to calosc
    assert p[1] == p[2] == sum(licznik.values())


def test_pusty_licznik_przy_minimum_zero_podnosi_wyjatek():
    # max() na pustym liczniku - znany defekt, nie poprawiamy modulu
    with pytest.raises(ValueError):
        _przewaga({}, 0, 0.6)
