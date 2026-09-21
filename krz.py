"""Sprawdzenie w Krajowym Rejestrze Zadluzonych (krz.ms.gov.pl).

Zapytanie tylko do odczytu, wykonywane w przegladarce notariusza (polaczenie
CDP przez uruchom_przegladarke.bat). Dla osoby fizycznej dwa wyszukiwania po
PESEL: "prowadzaca dzialalnosc" i "nieprowadzaca dzialalnosci". Wynik to zrzuty
ekranu + wpis audytowy. Rozpoznanie tresci wyniku jest heurystyczne - notariusz
oglada zrzut i zatwierdza. Patrz docs/rejestry.md.

Logi: identyfikator sprawy, ktore wyszukiwanie, status, czas. Bez PESEL-i.
"""
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

import config
import rejestry

log = logging.getLogger("pieczapp.krz")

ADRES = "https://krz.ms.gov.pl/"
ZAKLADKI = {
    "prowadzaca": "Osoba fizyczna prowadząca działalność gospodarczą",
    "nieprowadzaca": "Osoba fizyczna nieprowadząca działalności gospodarczej",
}
ODSTEP_S = 2.0  # miedzy zapytaniami - rate limiting po naszej stronie

# Komunikat portalu przy braku wynikow (sprawdzone 17.09.2026, wersja 1.22.002):
# "Nie zostały znalezione żadne pozycje dla podanych kryteriów wyszukiwania."
WZORCE_BRAK = re.compile(r"nie zosta[łl]y znalezione|[żz]adne pozycje|brak wynik|nie znaleziono|nie odnaleziono", re.I)
# Teksty stale na stronie (zakladki, ramka informacyjna) - wycinane przed szukaniem slow o wpisie,
# bo zawieraja np. "Sygnatura" i "postepowania".
STALE_TEKSTY = re.compile(
    r"Przejd[źz] do kryteri[óo]w wyszukiwania|Podmiot nieb[ęe]d[ąa]cy osob[ąa] fizyczn[ąa]|"
    r"Osoba fizyczna (nie)?prowadz[ąa]ca dzia[łl]alno[śs][ćc]i? gospodarcz[ąe]j?|Sygnatura|"
    r"Poprzednia zak[łl]adka|Nast[ęe]pna zak[łl]adka|zak[łl]adka \d z \d|\d / \d|"
    r"INFORMACJA O KRYTERIACH WYSZUKIWANIA.*?w trakcie post[ęe]powania\.",
    re.I | re.S,
)
WZORCE_WPIS = re.compile(r"upad[łl]o|restruktur|zakaz prowadzenia|egzekuc|nr sprawy|numer sprawy|data wszcz", re.I)


class StronaKRZ(Protocol):
    """To, czego modul potrzebuje od przegladarki - Playwright albo atrapa."""
    def otworz(self) -> None: ...
    def wybierz_zakladke(self, nazwa: str) -> None: ...
    def wpisz_identyfikator(self, wartosc: str) -> None: ...
    def wyszukaj(self) -> None: ...
    def wyczysc(self) -> None: ...
    def tekst_wyniku(self) -> str: ...
    def zrzut(self, cel: Path) -> None: ...


@dataclass
class WynikKRZ:
    zakladka: str
    status: str        # brak_wpisu | wpis | blad
    zrzut: str         # nazwa pliku
    opis: str


def rozpoznaj(tekst: str) -> tuple[str, str]:
    """Heurystyka na tekscie strony wynikow. Zawsze do potwierdzenia przez czlowieka."""
    t = " ".join((tekst or "").split())
    if WZORCE_BRAK.search(t):
        return "brak_wpisu", "portal: nie znaleziono pozycji"
    reszta = STALE_TEKSTY.sub(" ", t)
    if WZORCE_WPIS.search(reszta):
        return "wpis", "portal: znaleziono pozycje - SPRAWDZ ZRZUT"
    return "blad", "nie rozpoznano wyniku - sprawdz zrzut"


def sprawdz_osobe(strona: StronaKRZ, pesel: str, identyfikator: str, etykieta: str = "") -> rejestry.WynikSprawdzenia:
    """Dwa wyszukiwania po PESEL, zrzuty do sprawy, jeden wpis audytowy."""
    cyfry = re.sub(r"\D", "", pesel or "")
    if len(cyfry) != 11:
        raise ValueError("PESEL musi miec 11 cyfr")
    katalog = config.SPRAWY / identyfikator / "sprawdzenia"
    katalog.mkdir(parents=True, exist_ok=True)
    maska = rejestry.maskuj_pesel(cyfry)
    znacznik = datetime.now().strftime("%Y%m%d-%H%M%S")

    wyniki: list[WynikKRZ] = []
    start = time.time()
    strona.otworz()
    for klucz, nazwa in ZAKLADKI.items():
        strona.wybierz_zakladke(nazwa)
        strona.wpisz_identyfikator(cyfry)
        strona.wyszukaj()
        plik = katalog / f"krz_{klucz}_{maska[-4:]}_{znacznik}.png"
        strona.zrzut(plik)
        status, opis = rozpoznaj(strona.tekst_wyniku())
        wyniki.append(WynikKRZ(klucz, status, plik.name, opis))
        strona.wyczysc()
        time.sleep(ODSTEP_S)

    if any(w.status == "wpis" for w in wyniki):
        status = "wpis"
    elif all(w.status == "brak_wpisu" for w in wyniki):
        status = "brak_wpisu"
    else:
        status = "blad"
    szczegoly = "; ".join(f"{w.zakladka}: {w.opis} [{w.zrzut}]" for w in wyniki)
    if etykieta:
        szczegoly = f"{etykieta} - " + szczegoly
    log.info("sprawa %s: KRZ status=%s zapytan=%d czas=%.0fs",
             identyfikator, status, len(wyniki), time.time() - start)
    return rejestry.WynikSprawdzenia(
        rejestr="KRZ", zapytanie=maska, status=status, szczegoly=szczegoly, zrodlo=ADRES,
        etykieta=etykieta,
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
