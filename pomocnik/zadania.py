"""Co pomocnik potrafi wykonac dla notarai.

Kazdy wykonawca dostaje zlecenie (slownik z serwera) i zwraca raport (slownik).
Nic tu nie wie o HTTP ani o kolejce - to robota klient.py.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import krz_portal
from pomocnik import cdp, krz_cdp

log = logging.getLogger("notarai.pomocnik.zadania")


def katalog_zrzutow(sprawa: str) -> Path:
    """Gdzie ladują zrzuty ze sprawdzen.

    Zostaja na komputerze notariusza. To dowod starannosci, wiec musi byc
    dostepny od razu - przesylanie ich do sprawy w chmurze dolozymy osobno,
    a do tego czasu lepiej, zeby lezaly u niego niz nigdzie.
    """
    baza = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "notarai" / "zrzuty"
    katalog = baza / (sprawa or "bez-sprawy")
    katalog.mkdir(parents=True, exist_ok=True)
    return katalog


def krz(zlecenie: dict, polacz=cdp.polacz, portal_z=krz_cdp.StronaKRZ) -> dict:
    """Sprawdzenie w Krajowym Rejestrze Zadluzonych dla kazdej osoby ze zlecenia.

    Blad przy jednej osobie nie przerywa pozostalych: notariusz woli dostac
    siedem wynikow z osmiu i wyraznie zaznaczony jeden brak, niz nic.
    """
    osoby = (zlecenie.get("tresc") or {}).get("osoby") or []
    sprawa = zlecenie.get("sprawa", "")
    if not osoby:
        return {"sprawdzenia": [], "bledy": ["Zlecenie nie wskazuje zadnej osoby."]}

    katalog = katalog_zrzutow(sprawa)
    sprawdzenia: list[dict] = []
    bledy: list[str] = []

    polaczenie, strona = polacz()
    try:
        portal = portal_z(strona)
        for osoba in osoby:
            etykieta = osoba.get("etykieta", "")
            try:
                wynik = krz_portal.przebieg(
                    portal, osoba.get("pesel", ""), etykieta,
                    zrzut_do=lambda nazwa: katalog / nazwa,
                )
            except Exception as blad:  # noqa: BLE001 - bez numeru w komunikacie
                log.error("krz: %s", type(blad).__name__)
                bledy.append(f"{etykieta or 'jedna ze stron'}: "
                             f"nie dokonczylem sprawdzenia ({type(blad).__name__})")
                continue
            sprawdzenia.append({
                "rejestr": "KRZ",
                "pesel": osoba.get("pesel", ""),
                "status": wynik["status"],
                "szczegoly": wynik["szczegoly"],
                "etykieta": etykieta,
                "zrodlo": krz_portal.ADRES,
            })
    finally:
        polaczenie.zamknij()

    log.info("krz: osob=%d sprawdzen=%d bledow=%d", len(osoby), len(sprawdzenia), len(bledy))
    return {"sprawdzenia": sprawdzenia, "bledy": bledy, "zrzuty_w": str(katalog)}


WYKONAWCY = {"krz": krz}
