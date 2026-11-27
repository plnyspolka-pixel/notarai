"""Zastępstwo modułu rejestry.py V1: funkcja AWS nie prowadzi rejestru sprawdzeń spraw."""
from dataclasses import dataclass, field


@dataclass
class WynikSprawdzenia:
    rejestr: str = ""
    zapytanie: str = ""
    status: str = ""
    szczegoly: str = ""
    zrodlo: str = ""
    etykieta: str = ""
    pliki: list = field(default_factory=list)


def zapisz_sprawdzenie(*args, **kwargs):
    raise RuntimeError("funkcja AWS nie zapisuje sprawdzen")
