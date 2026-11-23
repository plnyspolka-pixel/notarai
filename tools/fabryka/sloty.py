"""Sloty publikacji (09:00 i 16:00 czasu polskiego) i polityka bufora.

Zasady (BIBLIA_V6 §1.1, §8.3):
- dwa sloty dziennie, codziennie, bez przerw między sezonami;
- bufor: zawsze co najmniej 4 gotowe odcinki przed publikacją (2 dni);
- jedna paczka produkcyjna dziennie: 2 odcinki, a 4, gdy bufor spadł poniżej 4.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta

from .wspolne import KORZEN, WARSZAWA, czas

GODZINY = (time(9, 0), time(16, 0))
BUFOR_MIN = 4
PACZKA_NORMALNA = 2
PACZKA_NADROBIENIE = 4
DLUGOSC_SEZONU = 40


def sloty_od(od: datetime, ile: int) -> list[datetime]:
    """Kolejne sloty ściśle po chwili `od` (w czasie Warszawy, z poprawną zmianą czasu)."""
    od = od.astimezone(WARSZAWA)
    wynik: list[datetime] = []
    dzien = od.date()
    while len(wynik) < ile:
        for g in GODZINY:
            s = datetime.combine(dzien, g, tzinfo=WARSZAWA)
            if s > od:
                wynik.append(s)
                if len(wynik) == ile:
                    break
        dzien += timedelta(days=1)
    return wynik


def ma_wideo(o: dict) -> bool:
    """Wideo jako adres https albo istniejący plik w repo. Wpis zastępczy bez pliku się nie liczy."""
    w = (o.get("pliki") or {}).get("wideo") or ""
    return w.startswith("https://") or (bool(w) and (KORZEN / w).exists())


def zajete(kolejka: dict | None) -> set[datetime]:
    return {czas(o["publish_at"]) for o in (kolejka or {}).get("odcinki", []) if o.get("publish_at") and ma_wideo(o)}


def wolne_sloty(kolejka: dict | None, od: datetime, ile: int) -> list[datetime]:
    """Najbliższe wolne sloty po `od`: po ostatnim zajętym, bez dziur w środku kolejki.

    Dziur nie zapełniamy: widz dostaje odcinki po kolei, więc nowy odcinek idzie zawsze
    na koniec kolejki (albo od najbliższego slotu, gdy kolejka jest pusta lub w przeszłości).
    """
    z = sorted(zajete(kolejka))
    start = max([od] + z)
    return sloty_od(start, ile)


def bufor(kolejka: dict | None, chwila: datetime) -> int:
    """Gotowe odcinki z premierą po `chwila` (z plikiem wideo podanym w kolejce)."""
    n = 0
    for o in (kolejka or {}).get("odcinki", []):
        if o.get("status") == "gotowy" and o.get("publish_at") and czas(o["publish_at"]) > chwila:
            if ma_wideo(o):
                n += 1
    return n


def wielkosc_paczki(bufor_teraz: int) -> int:
    return PACZKA_NADROBIENIE if bufor_teraz < BUFOR_MIN else PACZKA_NORMALNA


def nastepne_numery(ostatni: tuple[int, int] | None, ile: int) -> list[tuple[int, int]]:
    """(sezon, odcinek) kolejnych odcinków; po 40. odcinku od razu następny sezon (bez przerwy)."""
    s, e = ostatni or (1, 0)
    wynik = []
    for _ in range(ile):
        e += 1
        if e > DLUGOSC_SEZONU:
            s, e = s + 1, 1
        wynik.append((s, e))
    return wynik


def slot_tekst(d: datetime) -> str:
    return d.astimezone(WARSZAWA).strftime("%H:%M")
