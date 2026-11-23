"""Rozpoznawanie JAWNEGO polecenia sprawdzenia KW w rozmowie o sprawie.

Bez decyzji modelu AI o wykonywaniu operacji; skan/wynik Bedrock nie
uruchamia pobierania. Nie zgadujemy numeru, gdy jest ich kilka.
"""
from __future__ import annotations
import re

import ekw

_KW = re.compile(r"(?<![A-Z0-9])([A-Z]{2}[A-Z0-9]{2}\s*/\s*\d{1,8}\s*/\s*\d)(?![A-Z0-9])", re.I)
_CZYNNOSC = re.compile(r"\b(sprawdz|sprawdź|pobierz|odczytaj|zweryfikuj|przeanalizuj)\b", re.I)
_CEL = re.compile(r"\b(kw|ksi[eę]g\w*|hipotek\w*|dzia[łl]\s+(?:i|ii|iii|iv|1|2|3|4))\b", re.I)


def _numery(tekst: str) -> tuple[list[str], bool]:
    znalezione = []
    bledne = False
    for match in _KW.finditer(tekst or ""):
        try:
            numer = ekw.normalizuj_numer(match.group(1))
        except ValueError:
            bledne = True
            continue
        if numer not in znalezione:
            znalezione.append(numer)
    return znalezione, bledne


def rozpoznaj(wiadomosc: str, kontekst: str) -> tuple[bool, str | None, str]:
    """(czy polecenie EKW, numer albo None, komunikat dopytania)."""
    if not (_CZYNNOSC.search(wiadomosc) and _CEL.search(wiadomosc)):
        return False, None, ""
    numery, bledne = _numery(wiadomosc)
    if bledne:
        return True, None, "W poleceniu jest numer KW z błędną cyfrą kontrolną. Podaj poprawny numer."
    if not numery:
        numery, _ = _numery(kontekst)
    if not numery:
        return True, None, "Podaj pełny numer księgi wieczystej (np. WA4M/00160286/2)."
    if len(numery) > 1:
        return True, None, "W sprawie jest kilka numerów KW. Napisz, którą księgę sprawdzić."
    return True, numery[0], ""


def odpowiedz(ksiega: dict) -> str:
    stany = []
    for d in ksiega["dzialy"]:
        stan = "brak wpisów" if d["pusty"] else "są wpisy — otwórz dział w karcie EKW"
        stany.append(f"Dział {d['oznaczenie']}: {stan}")
    return (f"Pobrano aktualną treść KW {ksiega['numer_kw']} z {ksiega['zrodlo']} "
            f"i zapisano do tej sprawy razem ze śladem sprawdzenia.\n"
            + "\n".join(stany)
            + "\nTo nie jest odpis urzędowy. Zweryfikuj wzmianki, datę odczytu oraz treść działów w źródle.")
