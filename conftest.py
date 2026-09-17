"""Wspólne funkcje pomocnicze dla testów."""
from walidacja import WAGI_PESEL


def z_suma_kontrolna(dziesiec_cyfr: str) -> str:
    """Dodaje cyfrę kontrolną PESEL do 10-cyfrowego prefiksu."""
    suma = sum(int(c) * w for c, w in zip(dziesiec_cyfr, WAGI_PESEL))
    return dziesiec_cyfr + str((10 - suma % 10) % 10)
