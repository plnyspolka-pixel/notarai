"""Kontrola zwięzłej karty (W7): kryteria akceptacji, zakaz kart otwartych, „zmiana niepotrzebna”.

Karta „otwarta” to taka, której tytuł albo punkt listy zaczyna się od niejasnego czasownika
(popraw, zrefaktoruj, ulepsz, uporządkuj...) - model nie wie wtedy, kiedy skończyć.
Taka karta musi mieć sekcję `## Kryteria akceptacji` z 1-3 obserwowalnymi punktami.
Sekcja jest poza tym opcjonalna (karta ma zostać krótka - patrz PROPOZYCJA-W7.md).

API (karta = słownik z karta.wczytaj(), wystarczą klucze `tytul` i `tresc`):
    bledy(karta) -> list[str]             błędy W7 (pusta lista = ok)
    kryteria(tresc) -> list[str] | None   punkty sekcji; None, gdy jej nie ma
    otwarta(karta) -> str | None          pierwszy niejasny czasownik
    deklaruje_niepotrzebna(tekst) -> bool  agent zakończył wynikiem „ZMIANA NIEPOTRZEBNA: ...”
    wynik_niepotrzebnej(zmienione, testy_zielone) -> (wynik, powody)
"""
from __future__ import annotations

import re

MAKS_KRYTERIOW = 3
OTWARTE_RE = re.compile(r"^(popraw|zrefaktoruj|refaktoruj|ulepsz|uporządkuj|usprawnij|"
                        r"zoptymalizuj|posprzątaj|uprość|przejrzyj|dopracuj)(?![\wąćęłńóśźż])", re.I)
_PUNKT_RE = re.compile(r"^\s*(?:[-*]|\d+\.)\s+")
ZNACZNIK_NIEPOTRZEBNA = re.compile(r"ZMIANA\s+NIEPOTRZEBNA\s*:\s*\S", re.I)
# Zdanie do dopisania w zasadach polecenia dla agenta (karta.ZASADY).
ZASADA_NIEPOTRZEBNA = ("- Jeżeli stan docelowy już jest spełniony, niczego nie zmieniaj i zakończ wynikiem "
                       "`ZMIANA NIEPOTRZEBNA: <uzasadnienie w jednym zdaniu>` - to dozwolony wynik.")


def kryteria(tresc: str) -> list[str] | None:
    m = re.search(r"^## Kryteria akceptacji[ \t]*$(.*?)(?=^## |\Z)", tresc, re.M | re.S)
    if not m:
        return None
    return [_PUNKT_RE.sub("", w).strip() for w in m.group(1).split("\n") if _PUNKT_RE.match(w)]


def otwarta(karta: dict) -> str | None:
    tytul = str(karta.get("tytul", ""))
    kandydaci = [tytul, *tytul.split(":")[1:]]
    kandydaci += [_PUNKT_RE.sub("", w) for w in str(karta.get("tresc", "")).split("\n") if _PUNKT_RE.match(w)]
    for k in kandydaci:
        m = OTWARTE_RE.match(k.strip().strip("`*_"))
        if m:
            return m.group(1).lower()
    return None


def bledy(karta: dict) -> list[str]:
    out = []
    kryt = kryteria(str(karta.get("tresc", "")))
    if kryt is not None and not 1 <= len(kryt) <= MAKS_KRYTERIOW:
        out.append(f"Kryteria akceptacji: 1-{MAKS_KRYTERIOW} punkty, obserwowalne")
    czasownik = otwarta(karta)
    if czasownik and not kryt:
        out.append(f"karta otwarta („{czasownik}…”) - dopisz `## Kryteria akceptacji` "
                   f"(1-{MAKS_KRYTERIOW} punkty) albo zawęź zadanie")
    return out


def deklaruje_niepotrzebna(tekst: str | None) -> bool:
    return bool(ZNACZNIK_NIEPOTRZEBNA.search(tekst or ""))


def wynik_niepotrzebnej(zmienione: list[str], testy_zielone: bool) -> tuple[str, list[str]]:
    """Ocena deklaracji „zmiana niepotrzebna”: dozwolona, gdy nic nie zmieniono i testy
    (z ukrytymi) już przechodzą na bazie; inaczej odrzucenie z osobnym powodem."""
    if zmienione:
        return "odrzucone", ["niepotrzebna_niepotwierdzona"]
    if not testy_zielone:
        return "odrzucone", ["niepotrzebna_niepotwierdzona"]
    return "niepotrzebna", []
