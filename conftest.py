"""Wspólne funkcje pomocnicze dla testów."""
import pytest

from walidacja import WAGI_PESEL


@pytest.fixture(autouse=True)
def _bez_geokodera():
    """Żaden test nie pyta prawdziwego geokodera (OpenStreetMap). Testy mapy
    notariuszy włączają go same, z atrapą transportu HTTP.

    Bez monkeypatch celowo: fixture autouse z monkeypatch zmieniałby kolejność
    sprzątania i reload modułów w `_przywroc_moduly` (test_logowanie)
    odbywałby się ze środowiskiem jeszcze podmienionym (PIECZAPP_MULTI=true)."""
    import notariusze
    poprzedni = notariusze.GEOKODER
    notariusze.GEOKODER = ""
    yield
    notariusze.GEOKODER = poprzedni


def z_suma_kontrolna(dziesiec_cyfr: str) -> str:
    """Dodaje cyfrę kontrolną PESEL do 10-cyfrowego prefiksu."""
    suma = sum(int(c) * w for c, w in zip(dziesiec_cyfr, WAGI_PESEL))
    return dziesiec_cyfr + str((10 - suma % 10) % 10)
