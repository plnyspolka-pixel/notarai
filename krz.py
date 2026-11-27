"""Sprawdzenie w Krajowym Rejestrze Zadluzonych - czesc serwerowa.

Wiedza o samym portalu (zakladki, wzorce rozpoznawania, przebieg wyszukiwania)
siedzi w krz_portal.py, bo to samo sprawdzenie wykonuje takze pomocnik na
komputerze notariusza. Tutaj zostaje to, co wiaze je ze sprawa: katalog na
zrzuty i wpis audytowy.

Logi: identyfikator sprawy, status, czas. Bez PESEL-i.
"""
import logging
import re
import time
from pathlib import Path

import config
import krz_portal
import rejestry
from krz_portal import (  # nazwy, po ktore siega serwer, testy i pomocnik
    ADRES,
    StronaPlaywright,
    ODSTEP_S,
    STALE_TEKSTY,
    WZORCE_BRAK,
    WZORCE_WPIS,
    ZAKLADKI,
    StronaKRZ,
    WynikZakladki,
    rozpoznaj,
)

log = logging.getLogger("pieczapp.krz")


def sprawdz_osobe(strona: StronaKRZ, pesel: str, identyfikator: str,
                  etykieta: str = "") -> rejestry.WynikSprawdzenia:
    """Dwa wyszukiwania po PESEL, zrzuty do sprawy, jeden wpis audytowy."""
    katalog = config.SPRAWY / identyfikator / "sprawdzenia"
    katalog.mkdir(parents=True, exist_ok=True)
    start = time.time()
    wynik = krz_portal.przebieg(
        strona, pesel, etykieta,
        zrzut_do=lambda nazwa: katalog / nazwa,
        odstep_s=ODSTEP_S,
    )
    log.info("sprawa %s: KRZ status=%s zapytan=%d czas=%.0fs",
             identyfikator, wynik["status"], len(wynik["zakladki"]), time.time() - start)
    return rejestry.WynikSprawdzenia(
        rejestr="KRZ", zapytanie=wynik["maska"], status=wynik["status"],
        szczegoly=wynik["szczegoly"], zrodlo=wynik["zrodlo"], etykieta=etykieta,
    )
