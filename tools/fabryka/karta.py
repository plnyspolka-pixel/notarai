"""Kotwice w prawdziwych sprawach: plan sezonu z biblii, katalog spraw (PR #93), karta sprawy z SAOS.

Karta sprawy powstaje automatycznie jako szkic: metadane orzeczenia z API SAOS, sentencja
i fragmenty ustaleń z usuniętymi danymi osobowymi. Ocenę („co bierzemy do serialu”) dopisuje
konsultant (Claude) w kroku scenariusza. Prawomocność: SAOS jej nie podaje, karta mówi to wprost.
"""
from __future__ import annotations

import html
import json
import re
import urllib.request
from dataclasses import dataclass

from .wspolne import BIBLIA, GALEZ_KATALOG, KATALOG_SPRAW, czytaj

PLIKI_KATALOGU = [
    "01-orzecznictwo.md", "02-instytucje-obciazenia-zmiany.md", "03-sprawy-karne-i-interwencje.md",
    "05-nietypowe-i-humorystyczne-realia.md", "06-humor-absurd-orzecznictwo-druga-kwerenda.md",
]
SAOS_API = "https://www.saos.org.pl/api/judgments/{}"
SAOS_LINK = re.compile(r"saos\.org\.pl/judgments/(\d+)")


@dataclass
class Rekord:
    id: str
    wiersz: str
    plik: str

    @property
    def saos_id(self) -> str | None:
        m = SAOS_LINK.search(self.wiersz)
        return m.group(1) if m else None


def katalog() -> dict[str, Rekord]:
    wynik: dict[str, Rekord] = {}
    for plik in PLIKI_KATALOGU:
        t = czytaj(f"{KATALOG_SPRAW}/{plik}", GALEZ_KATALOG) or ""
        for linia in t.splitlines():
            m = re.match(r"^\|\s*([A-Z]\d{2})\s*\|", linia)
            if m and m.group(1) not in wynik:
                wynik[m.group(1)] = Rekord(m.group(1), linia, plik)
    return wynik


def plan_sezonu(sezon: int = 1) -> dict[int, dict]:
    """Odcinki z biblii: §6.3 (1–8, kotwice) i tabela §6.4 (9–40: slot, kotwica, logline)."""
    t = czytaj(BIBLIA) or ""
    plan: dict[int, dict] = {}
    if sezon != 1:
        return plan  # sezony 2+ mają w biblii tylko zarysy; scenariusz dostaje zarys i numer
    m = re.search(r"EP01 [^\n]*·[^\n]*EP08 [^\n]*", t)
    if m:
        for ep, kotw in re.findall(r"EP(\d{2}) ([A-Z0-9 +]+?)(?= ·|\.|$)", m.group(0)):
            plan[int(ep)] = {"slot": "09:00" if int(ep) % 2 else "16:00", "kotwica": kotw.strip(),
                             "logline": f"istniejący scenariusz EP{ep} (sezon-1/02_SCENARIUSZE) z poprawkami V6"}
    for ep, slot, kotw, log in re.findall(r"^\| (\d{2}) \| (\d{1,2}:\d{2}) \| ([^|]+) \| ([^|]+) \|$", t, re.M):
        plan[int(ep)] = {"slot": slot if len(slot) == 5 else "0" + slot, "kotwica": kotw.strip(), "logline": log.strip()}
    return plan


def kotwice(tekst: str) -> list[str]:
    return re.findall(r"[A-Z]\d{2}", tekst or "")


# --- anonimizacja ---------------------------------------------------------------------------------
_WZORCE = [
    (re.compile(r"\b[A-ZŁŚŻŹĆŃÓ]\. ?[A-ZŁŚŻŹĆŃÓ]\.(?: ?\(\d\))?"), "[osoba]"),  # inicjały „Z. S. (1)”
    (re.compile(r"\b\d{11}\b"), "[PESEL]"),
    (re.compile(r"\b(ul\.|al\.|Al\.|ulicy|alei) [^,;.]{1,40}"), "[adres]"),
    (re.compile(r"\b\d{1,3}(?:[ .]\d{3})+(?:,\d{2})? ?(?:zł|złotych|złote)\b|\b\d+(?:,\d{2})? ?(?:zł|złotych|złote)\b"), "[kwota]"),
    (re.compile(r"\b[Rr]ep(?:\.|ertorium)? ?A ?(?:nr )?\d+/\d{2,4}"), "[repertorium]"),
    (re.compile(r"\b\d{1,2} (stycznia|lutego|marca|kwietnia|maja|czerwca|lipca|sierpnia|września|"
                r"października|listopada|grudnia) \d{4}(?!\d)( ?r\.?)?"), "[data]"),
    (re.compile(r"\b\d{1,2}[./]\d{1,2}[./]\d{2,4}(?!\d)( ?r\.?)?"), "[data]"),
    (re.compile(r"\b\d+(?:,\d+)? ?m2\b"), "[metraż]"),
    (re.compile(r"\b(SSO|SSR|SSA|SSN|Przewodnicząc\w*|Protokolant\w*)[^.]{0,60}"), "[skład sądu]"),
    (re.compile(r"\bw (Ł|W|K|P|G|S|L|B|O|R)\.(?=\W)"), "w [miejscowość]"),
    (re.compile(r"\b(Sygn\. akt|sygn\. akt|sygn\.)\s*[IVX]*\s*[A-Za-z]{1,4}\s*\d+/\d{2}"), "[sygnatura]"),
    (re.compile(r"\b[IVX]{1,4}\s+(ACa|AKa|C|Ca|Cz|CZP|CSK|Ns|K|GC|AGa|UK|ZP|ACz)\s+\d+/\d{2}\b"), "[sygnatura]"),
    (re.compile(r"\b(Sąd\w* (?:Rejonow|Okręgow|Apelacyjn)\w*) w [A-ZŁŚŻŹĆŃÓ][\wąćęłńóśźż-]+"), r"\1 w [miejscowość]"),
    (re.compile(r"\b(19|20)\d{2} ?r\.?"), "[rok]"),
]

# Imię i nazwisko (dwa słowa z wielkiej litery), poza zwrotami prawniczymi.
_NAZWISKO = re.compile(r"\b([A-ZŁŚŻŹĆŃÓ][a-ząćęłńóśźż]+)( [A-ZŁŚŻŹĆŃÓ][a-ząćęłńóśźż]+(?:-[A-ZŁŚŻŹĆŃÓ][a-ząćęłńóśźż]+)?)\b")
_NIE_NAZWISKA = {"Sąd", "Sądu", "Sądem", "Sądowi", "Prawo", "Prawa", "Rzeczypospolitej", "Polskiej", "Najwyższy",
                 "Najwyższego", "Skarbu", "Państwa", "Kodeks", "Kodeksu", "Spółdzielni", "Spółdzielnia", "Narodowym",
                 "Narodowego", "Banku", "Bank", "Polski", "Urzędu", "Urząd", "Wydział", "Wydziału", "Księgi", "Wieczystej"}


def _nazwiska(t: str) -> str:
    def z(m):
        return m.group(0) if m.group(1) in _NIE_NAZWISKA or m.group(2).strip() in _NIE_NAZWISKA else "[osoba]"
    return _NAZWISKO.sub(z, t)


def anonimizuj(t: str) -> str:
    for w, z in _WZORCE:
        t = w.sub(z, t)
    return _nazwiska(t)


def tekst_saos(saos_id: str, timeout: int = 30) -> dict:
    """Pełny tekst z publicznego API SAOS (host dozwolony w środowisku). Zwraca metadane + tekst."""
    req = urllib.request.Request(SAOS_API.format(saos_id), headers={"User-Agent": "notarai-fabryka/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.load(r)["data"]
    tekst = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(d.get("textContent", ""))))
    return {
        "typ": d.get("judgmentType"),
        "data": d.get("judgmentDate"),
        "sygnatury": [c.get("caseNumber") for c in d.get("courtCases", [])],
        "sad": ((d.get("division") or {}).get("court") or {}).get("name"),
        "tekst": tekst,
    }


def fragmenty(tekst: str, slowa=("notariusz", "akt", "odmów", "staranno", "oddala", "zasądza", "ustal"),
              ile: int = 8, dl: int = 420) -> list[str]:
    """Kilka zdań z kluczowymi słowami, już po anonimizacji (do oceny w kroku scenariusza)."""
    wynik = []
    i = tekst.find("UZASADNIENIE")
    tekst = tekst[i:] if i >= 0 else tekst  # nagłówek wyroku to głównie skład i sygnatury
    tekst = anonimizuj(tekst)  # całość przed cięciem, żeby wzorce widziały pełne zwroty
    for m in re.finditer("|".join(slowa), tekst, re.I):
        a = max(0, m.start() - dl // 3)
        f = tekst[a:a + dl].strip()
        if not any(f[:80] in w for w in wynik):
            wynik.append(f)
        if len(wynik) >= ile:
            break
    return wynik


def szkic_karty(rek: Rekord, saos: dict | None) -> str:
    linie = [
        f"# Karta sprawy {rek.id} (szkic automatyczny)",
        "",
        "**Status:** szkic z fabryki odcinków. Konsultant (Claude) uzupełnia sekcję „Mechanizm dla serialu”",
        "i zatwierdza kartę w kroku scenariusza. Bez tego kotwica nie trafia do odcinka.",
        "",
        "## Wpis w katalogu (PR #93)",
        f"- Plik: `{rek.plik}`",
        f"- Wiersz: {anonimizuj(rek.wiersz.strip())}",
        "",
    ]
    if saos:
        linie += [
            "## Orzeczenie (SAOS)",
            f"- Sąd: {saos.get('sad')}; rodzaj: {saos.get('typ')}; data: {saos.get('data')}",
            "- Sygnatura: tylko w karcie, nigdy w odcinku.",
            "- **Prawomocność: SAOS jej nie podaje.** Sprawdzić przed publikacją (apelacja/kasacja).",
            "",
            "## Fragmenty uzasadnienia (po anonimizacji)",
            *[f"> {f}" for f in fragmenty(saos["tekst"])],
            "",
        ]
    else:
        linie += ["## Źródło", "Brak pełnego tekstu w SAOS dla tej pozycji (np. uchwała SN, komunikat organu).",
                  "Konsultant czyta źródło z linku w wierszu katalogu.", ""]
    linie += [
        "## Dane, których nie przenosimy",
        "Inicjały i nazwiska, skład sądu, miejscowości, adresy, daty, kwoty, metraże, relacje rodzinne",
        "i prywatne motywy stron. W odcinku zero sygnatur i odwołań do źródła.",
        "",
        "## Mechanizm dla serialu",
        "_Do uzupełnienia przez konsultanta: jedno zdanie mechanizmu, co bierzemy, czego nie, jak notariusz",
        "wypada (musi korzystnie)._",
        "",
    ]
    return "\n".join(linie)
