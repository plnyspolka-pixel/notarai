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


class StronaPlaywright:
    """Adapter na strone Playwright (karta w przegladarce notariusza)."""

    def __init__(self, page):
        self._p = page

    _ramka = None

    @property
    def _r(self):
        """Ramka z formularzem: ta, w ktorej jest przycisk Wyszukaj (adres ramki bywa rozny)."""
        if self._ramka is not None:
            try:
                if self._ramka.get_by_role("button", name="Wyszukaj").count():
                    return self._ramka
            except Exception:  # noqa: BLE001
                pass
        for _ in range(40):
            for ramka in self._p.frames:
                try:
                    if ramka.get_by_role("button", name="Wyszukaj").count():
                        self._ramka = ramka
                        return ramka
                except Exception:  # noqa: BLE001
                    continue
            self._p.wait_for_timeout(500)
        raise RuntimeError("Nie znaleziono formularza wyszukiwania KRZ (brak ramki z przyciskiem Wyszukaj)")

    def otworz(self) -> None:
        self._ramka = None
        self._p.goto(ADRES, wait_until="domcontentloaded")
        self._p.wait_for_timeout(2500)
        zgoda = self._p.get_by_role("button", name="Akceptuję")
        if zgoda.count():
            zgoda.first.click()
            self._p.wait_for_timeout(500)
        link = self._p.get_by_text("Wyszukiwanie podmiotów", exact=True).first
        if link.count() and link.is_visible():
            link.click()
        self._r  # czeka, az formularz sie pojawi

    def wybierz_zakladke(self, nazwa: str) -> None:
        r = self._r
        cel = r.get_by_text(nazwa, exact=False).first
        cel.scroll_into_view_if_needed(timeout=10000)
        cel.click(timeout=10000)
        self._p.wait_for_timeout(800)

    def wpisz_identyfikator(self, wartosc: str) -> None:
        # kazda zakladka ma wlasny formularz - bierzemy tylko widoczne pole
        pole = self._r.get_by_label(re.compile("Identyfikator", re.I)).filter(visible=True).first
        pole.fill(wartosc, timeout=10000)

    def wyszukaj(self) -> None:
        r = self._r
        r.get_by_role("button", name="Wyszukaj").filter(visible=True).first.click(timeout=10000)
        # czekamy na komunikat "nie znaleziono" albo liste wynikow, max ok. 15 s
        for _ in range(30):
            self._p.wait_for_timeout(500)
            try:
                tekst = r.locator("body").inner_text(timeout=2000)
            except Exception:  # noqa: BLE001
                continue
            if WZORCE_BRAK.search(tekst) or WZORCE_WPIS.search(STALE_TEKSTY.sub(" ", tekst)):
                break

    def wyczysc(self) -> None:
        przycisk = self._r.get_by_role("button", name="Wyczyść").filter(visible=True)
        if przycisk.count():
            przycisk.first.click(timeout=10000)
            self._p.wait_for_timeout(500)

    def tekst_wyniku(self) -> str:
        try:
            return self._r.locator("body").inner_text(timeout=5000)
        except Exception:  # noqa: BLE001
            return ""

    def zrzut(self, cel: Path) -> None:
        try:
            self._r.locator("body").screenshot(path=str(cel))
        except Exception:  # noqa: BLE001
            self._p.screenshot(path=str(cel), full_page=True)
