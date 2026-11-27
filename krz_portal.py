"""Wiedza o portalu krz.ms.gov.pl - bez zaleznosci od serwera.

Ten modul wie, jak rozmawiac z Krajowym Rejestrem Zadluzonych: ktore zakladki,
jaki odstep miedzy zapytaniami, po czym poznac brak wynikow. Nie wie nic o
sprawach, sciezkach na dysku ani o tym, jak wyglada wpis audytowy.

Taki podzial, bo to samo sprawdzenie wykonuja dwa rozne programy: pieczapp na
komputerze notariusza i pomocnik notarai. Selektory i wzorce rozpoznawania sa
najbardziej kruchą czescia calosci - portal zmienia uklad i trzeba je poprawic.
Gdyby lezaly w dwoch miejscach, przy pierwszej takiej zmianie poprawilibysmy
jedno, a drugie zostaloby po cichu zepsute.

Zapytanie jest tylko do odczytu, bezplatne i bez skutku zewnetrznego, ale
wykonujemy je po jednym na strone czynnosci, z odstepem. Patrz docs/rejestry.md.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

ADRES = "https://krz.ms.gov.pl/"
ZAKLADKI = {
    "prowadzaca": "Osoba fizyczna prowadząca działalność gospodarczą",
    "nieprowadzaca": "Osoba fizyczna nieprowadząca działalności gospodarczej",
}
ODSTEP_S = 2.0  # miedzy zapytaniami - rate limiting po naszej stronie

# Komunikat portalu przy braku wynikow (sprawdzone 17.09.2026, wersja 1.22.002):
# "Nie zostały znalezione żadne pozycje dla podanych kryteriów wyszukiwania."
WZORCE_BRAK = re.compile(
    r"nie zosta[łl]y znalezione|[żz]adne pozycje|brak wynik|nie znaleziono|nie odnaleziono",
    re.I)
# Teksty stale na stronie (zakladki, ramka informacyjna) - wycinane przed szukaniem slow
# o wpisie, bo zawieraja np. "Sygnatura" i "postepowania".
STALE_TEKSTY = re.compile(
    r"Przejd[źz] do kryteri[óo]w wyszukiwania|Podmiot nieb[ęe]d[ąa]cy osob[ąa] fizyczn[ąa]|"
    r"Osoba fizyczna (nie)?prowadz[ąa]ca dzia[łl]alno[śs][ćc]i? gospodarcz[ąe]j?|Sygnatura|"
    r"Poprzednia zak[łl]adka|Nast[ęe]pna zak[łl]adka|zak[łl]adka \d z \d|\d / \d|"
    r"INFORMACJA O KRYTERIACH WYSZUKIWANIA.*?w trakcie post[ęe]powania\.",
    re.I | re.S,
)
WZORCE_WPIS = re.compile(
    r"upad[łl]o|restruktur|zakaz prowadzenia|egzekuc|nr sprawy|numer sprawy|data wszcz", re.I)


def _wzorzec(wyrazenie: re.Pattern) -> dict:
    flagi = ("i" if wyrazenie.flags & re.I else "") + ("s" if wyrazenie.flags & re.S else "")
    return {"zrodlo": wyrazenie.pattern, "flagi": flagi}


def opis_portalu() -> dict:
    """Ta sama wiedza o portalu dla rozszerzenia przegladarki (rozszerzenie/krz.js).

    Rozszerzenie rozpoznaje wynik u notariusza - tekst strony nie wraca na
    serwer - ale wzorcow nie trzyma u siebie. Dostaje je ze zleceniem, zeby po
    zmianie portalu wystarczylo poprawic ten jeden plik. Wyrazenia musza byc
    zrozumiale takze dla JavaScriptu; pilnuje tego test rozszerzenia.
    """
    return {
        "adres": ADRES,
        "zakladki": dict(ZAKLADKI),
        "odstep_s": ODSTEP_S,
        "wzorce": {"brak": _wzorzec(WZORCE_BRAK), "wpis": _wzorzec(WZORCE_WPIS),
                   "stale": _wzorzec(STALE_TEKSTY)},
    }


class StronaKRZ(Protocol):
    """To, czego modul potrzebuje od przegladarki - Playwright, CDP albo atrapa."""
    def otworz(self) -> None: ...
    def wybierz_zakladke(self, nazwa: str) -> None: ...
    def wpisz_identyfikator(self, wartosc: str) -> None: ...
    def wyszukaj(self) -> None: ...
    def wyczysc(self) -> None: ...
    def tekst_wyniku(self) -> str: ...
    def zrzut(self, cel: Path) -> None: ...


@dataclass
class WynikZakladki:
    zakladka: str
    status: str        # brak_wpisu | wpis | blad
    zrzut: str         # nazwa pliku
    opis: str


def maskuj(pesel: str) -> str:
    """'12345678901' -> '1234*******'. Cokolwiek innego - w calosci gwiazdki.

    Swiadome powtorzenie rejestry.maskuj_pesel: ten modul ma nie zalezec od
    serwera. Zgodnosc obu pilnuje test, zeby nie rozjechaly sie po cichu.
    """
    cyfry = re.sub(r"\D", "", pesel or "")
    if len(cyfry) == 11:
        return cyfry[:4] + "*" * 7
    return "*" * max(len(cyfry), 1)


def rozpoznaj(tekst: str) -> tuple[str, str]:
    """Heurystyka na tekscie strony wynikow. Zawsze do potwierdzenia przez czlowieka."""
    t = " ".join((tekst or "").split())
    if WZORCE_BRAK.search(t):
        return "brak_wpisu", "portal: nie znaleziono pozycji"
    reszta = STALE_TEKSTY.sub(" ", t)
    if WZORCE_WPIS.search(reszta):
        return "wpis", "portal: znaleziono pozycje - SPRAWDZ ZRZUT"
    return "blad", "nie rozpoznano wyniku - sprawdz zrzut"


def zlacz(wyniki: list[WynikZakladki]) -> str:
    """Jeden status z dwoch zakladek. Wpis gdziekolwiek przewaza nad brakiem."""
    if any(w.status == "wpis" for w in wyniki):
        return "wpis"
    if wyniki and all(w.status == "brak_wpisu" for w in wyniki):
        return "brak_wpisu"
    return "blad"


def przebieg(strona: StronaKRZ, pesel: str, etykieta: str = "",
             zrzut_do=None, odstep_s: float | None = None, spij=time.sleep) -> dict:
    """Dwa wyszukiwania po PESEL. Zwraca zwykly slownik, bez modelu serwera.

    `zrzut_do(nazwa)` ma zwrocic sciezke, pod ktora zapisac zrzut, albo None,
    gdy zrzutow nie zbieramy.
    """
    # Odstep czytamy przy wywolaniu, a nie przy definicji funkcji - inaczej
    # ustawienie krz_portal.ODSTEP_S nie mialoby zadnego skutku.
    if odstep_s is None:
        odstep_s = ODSTEP_S
    cyfry = re.sub(r"\D", "", pesel or "")
    if len(cyfry) != 11:
        raise ValueError("PESEL musi miec 11 cyfr")
    maska = maskuj(cyfry)
    znacznik = datetime.now().strftime("%Y%m%d-%H%M%S")

    wyniki: list[WynikZakladki] = []
    strona.otworz()
    for klucz, nazwa in ZAKLADKI.items():
        strona.wybierz_zakladke(nazwa)
        strona.wpisz_identyfikator(cyfry)
        strona.wyszukaj()
        # Nazwa pliku niesie cztery poczatkowe cyfry, nigdy caly numer.
        nazwa_zrzutu = f"krz_{klucz}_{maska[:4]}_{znacznik}.png"
        cel = zrzut_do(nazwa_zrzutu) if zrzut_do else None
        if cel is not None:
            strona.zrzut(cel)
        status, opis = rozpoznaj(strona.tekst_wyniku())
        wyniki.append(WynikZakladki(klucz, status, nazwa_zrzutu if cel else "", opis))
        strona.wyczysc()
        spij(odstep_s)

    szczegoly = "; ".join(
        f"{w.zakladka}: {w.opis}" + (f" [{w.zrzut}]" if w.zrzut else "") for w in wyniki)
    if etykieta:
        szczegoly = f"{etykieta} - " + szczegoly
    return {
        "maska": maska,
        "etykieta": etykieta,
        "status": zlacz(wyniki),
        "szczegoly": szczegoly,
        "zrodlo": ADRES,
        "zakladki": [vars(w) for w in wyniki],
    }


# Adapter Playwright: tu, a nie w krz.py, bo uzywa go takze NotarAI V2 na stanowisku.
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
