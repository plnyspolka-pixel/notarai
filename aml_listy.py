"""Listy sankcyjne i PEP - pobieranie, parsowanie, migawki, indeksy.

Podstawa: ustawa z 1.03.2018 o przeciwdzialaniu praniu pieniedzy (notariusz
to instytucja obowiazana, art. 2 ust. 1 pkt 13), ustawa z 13.04.2022 o
szczegolnych rozwiazaniach w zakresie przeciwdzialania wspieraniu agresji
na Ukraine (lista MSWiA), rozporzadzenie MF z 27.07.2021 w sprawie wykazu
krajowych stanowisk PEP.

Zasady:
 - wylacznie oficjalne zrodla publiczne i Wikidata (CC0); zadnych platnych
   baz, zadnego wysylania danych stron czynnosci na zewnatrz - z zewnatrz
   przychodza tylko listy, dopasowanie liczy aml_dopasowanie.py u nas,
 - migawka listy to jeden plik JSON na zrodlo (lokalnie dane/listy_aml/,
   w chmurze <prefiks>/admin/listy_aml/ w S3 - wspolna dla kancelarii, bo
   nie zawiera ich danych),
 - ochrona przed pusta odpowiedzia: 0 rekordow albo mniej niz polowa
   poprzedniej migawki = blad, stara migawka zostaje,
 - logi: nazwa zrodla, liczba rekordow, czas, typ bledu. Bez nazwisk.

Zrodla (zweryfikowane w finyou 9.10.2026):
 - UE FSF: XML "xmlFullSanctionsList_1_1" (token publiczny z dokumentacji
   FSF; wlasny w PIECZAPP_EU_FSF_TOKEN),
 - ONZ: consolidated.xml Rady Bezpieczenstwa,
 - MSWiA: strona gov.pl z dwiema tabelami (osoby, podmioty),
 - API Sejmu: poslowie trzech ostatnich kadencji (JSON, z data urodzenia),
 - KPRM: sklad Rady Ministrow (HTML, bez dat urodzenia),
 - Wikidata: osoby na stanowiskach z katalogu (SPARQL).
Senat zwraca 403, a API KRS maskuje nazwiska - tych nie uzywamy.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
import html as html_
from datetime import date, datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

import httpx

import config
import magazyn
from aml_dopasowanie import Indeks, Rekord, data_czesciowa, data_z_tekstu_pl, kraj

log = logging.getLogger("pieczapp.aml")

# --- Zrodla ------------------------------------------------------------------

KATEGORIE = {"sankcje": ("eu_fsf", "un_sc", "mswia", "ofac_sdn"),
             "pep": ("sejm", "kprm", "wikidata")}
ETYKIETY = {
    "eu_fsf": "UE - skonsolidowana lista sankcji finansowych",
    "un_sc": "ONZ - skonsolidowana lista Rady Bezpieczenstwa",
    "mswia": "MSWiA - lista sankcyjna (ustawa z 13.04.2022)",
    "ofac_sdn": "OFAC SDN (USA)",
    "sejm": "API Sejmu (poslowie)",
    "kprm": "KPRM / gov.pl (Rada Ministrow)",
    "wikidata": "Wikidata (SPARQL, CC0)",
}
# Co ile odswiezac. Sankcje codziennie, PEP co tydzien.
WAZNOSC = {"eu_fsf": 1, "un_sc": 1, "mswia": 1, "ofac_sdn": 1, "sejm": 7, "kprm": 7, "wikidata": 7}

ADRESY = {
    "eu_fsf": "https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content",
    "un_sc": "https://scsanctions.un.org/resources/xml/en/consolidated.xml",
    "mswia": "https://www.gov.pl/web/mswia/lista-osob-i-podmiotow-objetych-sankcjami",
    "ofac_sdn": "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.CSV",
    "ofac_alt": "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/ALT.CSV",
    "sejm": "https://api.sejm.gov.pl/sejm",
    "kprm": "https://www.gov.pl/web/premier/sklad-rady-ministrow",
    "wikidata": "https://query.wikidata.org/sparql",
}
_EU_FSF_TOKEN_PUBLICZNY = "dG9rZW4tMjAxNw"
# OFAC to lista USA - dla notariusza w Polsce nieobowiazkowa, domyslnie wylaczona.
OFAC_WLACZONY = os.getenv("PIECZAPP_AML_OFAC", "0") == "1"
UA = os.getenv("PIECZAPP_AML_KONTAKT", "notarai-AML/1.0 (+https://notarai.pl)")
MIN_UDZIAL = 0.5          # nowa lista musi miec co najmniej polowe poprzedniej

# Katalog krajowych stanowisk PEP (rozp. MF z 27.07.2021) -> identyfikatory
# stanowisk w Wikidata. Tryb: direct (same QID), subclass_pl (podklasy
# dotyczace Polski), subclass_any (wszystkie podklasy). Pozycje bez zrodla
# maszynowego (sedziowie, zarzad NBP, samorzad...) pokrywa wylacznie
# oswiadczenie strony - patrz docs/rejestry.md.
KATALOG_PEP = {
    "PL-001": ("Prezydent RP", ["Q1054799"], "direct"),
    "PL-002": ("Prezes Rady Ministrow", ["Q3259469"], "direct"),
    "PL-003": ("wiceprezes Rady Ministrow", ["Q15051532"], "direct"),
    "PL-004": ("minister", ["Q83307"], "subclass_pl"),
    "PL-005": ("sekretarz stanu", ["Q9335058"], "direct"),
    "PL-006": ("podsekretarz stanu", ["Q124460155"], "direct"),
    "PL-007": ("posel", ["Q19269361"], "direct"),
    "PL-008": ("senator", ["Q81747225"], "direct"),
    "PL-013": ("Pierwszy Prezes SN", ["Q11816725"], "direct"),
    "PL-014": ("Prezes TK", ["Q115908874"], "direct"),
    "PL-015": ("Prezes NSA", ["Q11827105"], "direct"),
    "PL-017": ("Prezes NBP", ["Q109587536"], "direct"),
    "PL-020": ("ambasador RP", ["Q30064617"], "subclass_any"),
    "PL-022": ("Szef Sztabu Generalnego", ["Q109587453"], "direct"),
    "PL-035": ("Szef KPRM", ["Q107919931"], "direct"),
    "PL-038": ("wojewoda", ["Q275102"], "direct"),
}
WIKIDATA_OD_ROKU = 2000     # funkcje zakonczone wczesniej pomijamy (import lzejszy)


def _klient() -> httpx.Client:
    return httpx.Client(timeout=90, follow_redirects=True, headers={"User-Agent": UA})


def _pobierz_tekst(klient: httpx.Client, adres: str, prob: int = 3, **kw) -> str:
    for i in range(prob):
        try:
            odp = klient.get(adres, **kw)
            if odp.status_code in (429, 502, 503, 504) and i < prob - 1:
                time.sleep(3 * (i + 1))
                continue
            odp.raise_for_status()
            return odp.text
        except httpx.TransportError:
            if i == prob - 1:
                raise
            time.sleep(3 * (i + 1))
    raise RuntimeError("nie udalo sie pobrac")


# --- XML / HTML pomocniczo ----------------------------------------------------


def _bez_ns(korzen: ET.Element) -> ET.Element:
    for el in korzen.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
        for k in list(el.attrib):
            if "}" in k:
                el.attrib[k.split("}", 1)[1]] = el.attrib.pop(k)
    return korzen


def _xml(tekst: str) -> ET.Element:
    return _bez_ns(ET.fromstring(tekst.encode("utf-8") if isinstance(tekst, str) else tekst))


def _tekst(el: ET.Element | None, tag: str) -> str | None:
    if el is None:
        return None
    z = el.find(tag)
    if z is None or z.text is None:
        return None
    t = z.text.strip()
    return t or None


def _bez_znacznikow(html: str) -> str:
    t = re.sub(r"<br\s*/?>", " ", html, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", html_.unescape(t)).strip()


def _unikalne(lista):
    return list(dict.fromkeys(x for x in lista if x))


# --- Parsery sankcji -----------------------------------------------------------


def parsuj_ue(xml: str) -> list[Rekord]:
    wynik = []
    for el in _xml(xml).iter("sanctionEntity"):
        typ = el.find("subjectType")
        kod = typ.get("code", "") if typ is not None else ""
        nazwy, mocne = [], []
        for na in el.findall("nazwa") + el.findall("nameAlias"):
            cala = (na.get("wholeName") or " ".join(
                x for x in (na.get("firstName"), na.get("middleName"), na.get("lastName")) if x)).strip()
            if not cala:
                continue
            nazwy.append(cala)
            if na.get("strong") == "true" and na.get("nameLanguage", "EN") in ("", "EN"):
                mocne.append(cala)
        if not nazwy:
            continue
        glowna = mocne[0] if mocne else nazwy[0]
        daty = [b.get("birthdate") or b.get("year") or "" for b in el.findall("birthdate")]
        kraje = [c.get("countryIso2Code", "").upper() for c in el.findall("citizenship")
                 if c.get("countryIso2Code") and c.get("countryIso2Code") != "00"]
        regulacje = el.findall("regulation")
        daty_publ = sorted(r.get("publicationDate") for r in regulacje if r.get("publicationDate"))
        program = next((r.get("programme") for r in regulacje if r.get("programme")), None)
        adres = _tekst(regulacje[0], "publicationUrl") if regulacje else None
        uwagi = " | ".join(x for x in (
            f"EU ref: {el.get('euReferenceNumber')}" if el.get("euReferenceNumber") else "",
            _tekst(el, "remark") or "") if x) or None
        wynik.append(Rekord(
            zrodlo="eu_fsf", identyfikator=el.get("logicalId") or el.get("euReferenceNumber") or glowna,
            rodzaj={"person": "osoba", "enterprise": "podmiot"}.get(kod, "nieznany"),
            nazwy=[glowna] + [n for n in _unikalne(nazwy) if n != glowna],
            daty_urodzenia=_unikalne(daty), obywatelstwa=_unikalne(kraje), program=program,
            wpisano=daty_publ[0] if daty_publ else None, uwagi=uwagi, adres_zrodla=adres,
        ))
    return wynik


def _daty_onz(el: ET.Element) -> list[str]:
    wynik = []
    for d in el.findall("INDIVIDUAL_DATE_OF_BIRTH"):
        data = _tekst(d, "DATE")
        if data:
            wynik.append(data[:10])
            continue
        rok = _tekst(d, "YEAR")
        if rok:
            wynik.append(rok)
        od, do = _tekst(d, "FROM_YEAR"), _tekst(d, "TO_YEAR")
        if od and do and od.isdigit() and do.isdigit() and 0 <= int(do) - int(od) <= 10:
            wynik.extend(str(r) for r in range(int(od), int(do) + 1))
    return _unikalne(wynik)


def parsuj_onz(xml: str) -> list[Rekord]:
    wynik = []
    korzen = _xml(xml)

    def zbuduj(el: ET.Element, rodzaj: str):
        czesci = [t for t in (_tekst(el, x) for x in ("FIRST_NAME", "SECOND_NAME", "THIRD_NAME", "FOURTH_NAME")) if t]
        if not czesci:
            return
        glowna = " ".join(czesci)
        nazwy = [glowna]
        oryginal = _tekst(el, "NAME_ORIGINAL_SCRIPT")
        if oryginal:
            nazwy.append(oryginal)
        for al in el.findall("INDIVIDUAL_ALIAS" if rodzaj == "osoba" else "ENTITY_ALIAS"):
            n = _tekst(al, "ALIAS_NAME")
            if n:
                nazwy.append(n)
        kraje = [kraj(_tekst(v, "VALUE")) for n in el.findall("NATIONALITY") for v in n.findall("VALUE")]
        kraje = [k for k in kraje if k]
        if not kraje:
            kraje = [k for k in (kraj(_tekst(n, "VALUE")) for n in el.findall("NATIONALITY")) if k]
        wpisano = _tekst(el, "LISTED_ON")
        uwagi = " | ".join(x for x in (_tekst(el, "REFERENCE_NUMBER") or "",
                                       (_tekst(el, "COMMENTS1") or "")[:1000]) if x) or None
        wynik.append(Rekord(
            zrodlo="un_sc", identyfikator=_tekst(el, "DATAID") or _tekst(el, "REFERENCE_NUMBER") or glowna,
            rodzaj=rodzaj, nazwy=_unikalne(nazwy),
            daty_urodzenia=_daty_onz(el) if rodzaj == "osoba" else [],
            obywatelstwa=_unikalne(kraje), program=_tekst(el, "UN_LIST_TYPE"),
            wpisano=wpisano[:10] if wpisano else None, uwagi=uwagi,
            adres_zrodla="https://main.un.org/securitycouncil/en/content/un-sc-consolidated-list",
        ))

    for el in korzen.iter("INDIVIDUAL"):
        zbuduj(el, "osoba")
    for el in korzen.iter("ENTITY"):
        zbuduj(el, "podmiot")
    return wynik


def _data_pl(s: str) -> str | None:
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s or "")
    return f"{m[3]}-{m[2].zfill(2)}-{m[1].zfill(2)}" if m else None


def parsuj_mswia(html: str) -> tuple[list[Rekord], str | None]:
    """Pierwsza tabela - osoby, druga - podmioty, trzecia - historia wersji.
    Kolumny: nazwa | dane identyfikacyjne | uzasadnienie | srodki |
    data umieszczenia | data wykreslenia."""
    tabele = re.findall(r"<table[\s\S]*?</table>", html, flags=re.I)
    rekordy: list[Rekord] = []
    wersja = None

    def tabela(t: str, rodzaj: str):
        for wiersz in re.findall(r"<tr[\s\S]*?</tr>", t, flags=re.I):
            komorki = [_bez_znacznikow(k) for k in re.findall(r"<t[dh][\s\S]*?</t[dh]>", wiersz, flags=re.I)]
            if len(komorki) < 5 or re.match(r"^(Nazwisko|Podmioty|Nazwa)", komorki[0], re.I):
                continue
            nazwa_k, ident, uzasadnienie, srodki, wpis_k = komorki[:5]
            wykr_k = komorki[5] if len(komorki) > 5 else ""
            if not nazwa_k:
                continue
            nazwa = nazwa_k
            if rodzaj == "osoba":
                # "ALAUDINOV Apti Aronovich" - nazwisko wielkimi literami na poczatku.
                m = re.match(r"^((?:[^\W\d_a-zà-ɏ]{2,}[- ]?)+)\s+(.+)$", nazwa_k)
                if m and m[1].strip().isupper():
                    nazwa = f"{m[2].strip()} {m[1].strip()}"
            data, rok = data_z_tekstu_pl(ident) if rodzaj == "osoba" else (None, None)
            alias = re.search(r"(?:znany|znana|znane) (?:rowniez |takze |również |także )?jako[:\s]+([^.;]+)",
                              ident or "", re.I)
            aliasy = [a.strip() for a in re.split(r",| lub ", alias[1])] if alias else []
            kraje = []
            if rodzaj == "osoba":
                if re.search(r"Federacji Rosyjskiej|rosyjsk", uzasadnienie or "", re.I):
                    kraje.append("RU")
                if re.search(r"Białoru|białorusk", uzasadnienie or "", re.I):
                    kraje.append("BY")
            rekordy.append(Rekord(
                zrodlo="mswia", identyfikator=f"{rodzaj}:{re.sub(r'\s+', ' ', nazwa_k.upper()).strip()}",
                rodzaj=rodzaj, nazwy=[nazwa] + [a for a in aliasy if a],
                daty_urodzenia=[data] if data else ([str(rok)] if rok else []),
                obywatelstwa=kraje, program="PL-UA-2022",
                wpisano=_data_pl(wpis_k), wykreslono=_data_pl(wykr_k),
                uwagi=(" | ".join(x for x in (ident, (srodki or "")[:300]) if x))[:1000] or None,
                adres_zrodla=ADRESY["mswia"],
            ))

    for i, t in enumerate(tabele):
        naglowek = _bez_znacznikow(t[:600])
        if re.search(r"Wersja", naglowek, re.I) and re.search(r"Tytu", naglowek, re.I):
            m = re.search(r"Lista os[oó]b i podmiot[oó]w objętych sankcjami (\d+(?:\.\d+)?)", _bez_znacznikow(t))
            wersja = m[1] if m else None
            continue
        tabela(t, "podmiot" if re.search(r"Podmiot|Nazwa podmiotu", naglowek, re.I) or i == 1 else "osoba")
    return rekordy, wersja


def _csv(tekst: str) -> list[list[str]]:
    import csv
    import io
    return [w for w in csv.reader(io.StringIO(tekst)) if any(k.strip() for k in w)]


def parsuj_ofac(sdn: str, alt: str = "") -> list[Rekord]:
    def pusty(v):
        t = (v or "").strip()
        return None if t in ("", "-0-") else t

    def nazwa(surowa: str, osoba: bool) -> str:
        if osoba and "," in surowa:
            nazwisko, *reszta = surowa.split(",")
            return f"{','.join(reszta).strip()} {nazwisko.strip()}".strip()
        return surowa.strip()

    aliasy: dict[str, list[str]] = {}
    for w in _csv(alt):
        if len(w) >= 4 and pusty(w[3]):
            aliasy.setdefault(w[0].strip(), []).append(nazwa(w[3], True))
    miesiace = {m: f"{i:02d}" for i, m in enumerate(
        ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}
    wynik = []
    for w in _csv(sdn):
        if len(w) < 12 or not w[0].strip().isdigit():
            continue
        ident, nazwa_s, typ, program = w[0].strip(), w[1], (pusty(w[2]) or "").lower(), pusty(w[3])
        uwagi = pusty(w[11]) or ""
        osoba = typ == "individual"
        daty = []
        for m in re.finditer(r"DOB ([^;]+)", uwagi):
            for czesc in re.split(r";|\bto\b|,", m[1]):
                c = czesc.strip()
                x = re.match(r"^(\d{1,2}) ([A-Za-z]{3}) (\d{4})$", c)
                if x and x[2].lower() in miesiace:
                    daty.append(f"{x[3]}-{miesiace[x[2].lower()]}-{x[1].zfill(2)}")
                    continue
                x = re.search(r"(\d{4})", c)
                if x:
                    daty.append(x[1])
        kraje = [kraj(m[1]) for m in re.finditer(r"(?:nationality|citizen) ([A-Za-z ]+?)(?:;|\.|$)", uwagi)]
        wynik.append(Rekord(
            zrodlo="ofac_sdn", identyfikator=ident,
            rodzaj="osoba" if osoba else {"vessel": "statek", "aircraft": "samolot"}.get(typ, "podmiot"),
            nazwy=_unikalne([nazwa(nazwa_s, osoba)] + aliasy.get(ident, [])),
            daty_urodzenia=_unikalne(daty) if osoba else [], obywatelstwa=_unikalne(k for k in kraje if k),
            program=program, uwagi=uwagi[:1000] or None,
            adres_zrodla=f"https://sanctionssearch.ofac.treas.gov/Details.aspx?id={ident}",
        ))
    return wynik


# --- Parsery PEP -------------------------------------------------------------


def parsuj_sejm(kadencje: list[dict]) -> list[Rekord]:
    """[{"kadencja": {num, from, to, current}, "poslowie": [...]}] -> osoby z lista mandatow.
    API nie ma globalnego identyfikatora osoby, wiec scalamy po nazwisku,
    imieniu i dacie urodzenia."""
    wedle: dict[str, Rekord] = {}
    for wpis in kadencje:
        k, poslowie = wpis["kadencja"], wpis["poslowie"]
        for p in poslowie:
            if not p.get("firstName") or not p.get("lastName"):
                continue
            klucz = f"{p['lastName']}|{p['firstName']}|{p.get('birthDate') or ''}".lower()
            od = p.get("oathDate") or k.get("from")
            do = (k.get("to") if p.get("active") else (p.get("mandateExpiryDate") or k.get("to"))) or None
            funkcja = {"tytul": f"Posel na Sejm RP ({k['num']}. kadencja)", "kod": "PL-007", "od": od, "do": do}
            aktualny = bool(p.get("active") and k.get("current", True) and not k.get("to"))
            pelna = " ".join(x for x in (p.get("firstName"), p.get("secondName"), p.get("lastName")) if x)
            r = wedle.get(klucz)
            if r:
                r.funkcje.append(funkcja)
                r.aktualny = bool(r.aktualny or aktualny)
                continue
            data, rok = data_czesciowa(p.get("birthDate"))
            wedle[klucz] = Rekord(
                zrodlo="sejm", identyfikator=klucz, rodzaj="osoba",
                nazwy=[pelna] + ([f"{p['firstName']} {p['lastName']}"] if p.get("secondName") else []),
                daty_urodzenia=[data] if data else ([str(rok)] if rok else []),
                obywatelstwa=["PL"], funkcje=[funkcja], aktualny=aktualny,
                adres_zrodla=f"https://www.sejm.gov.pl/Sejm{k['num']}.nsf/posel.xsp?id={str(p.get('id', '')).zfill(3)}&type=A",
            )
    return list(wedle.values())


def _kod_kprm(funkcja: str) -> str:
    f = funkcja.lower()
    if f.startswith("prezes rady ministr"):
        return "PL-002"
    if "wiceprezes rady ministr" in f:
        return "PL-003"
    if "szef kancelarii prezesa rady ministr" in f:
        return "PL-035"
    return "PL-004"


def parsuj_kprm(html: str, adres: str = ADRESY["kprm"]) -> list[Rekord]:
    """gov.pl: <div class="title"><a>Imie Nazwisko</a></div><div class="position">...</div>.
    Bez dat urodzenia, wiec trafienia sa najwyzej "do weryfikacji"."""
    wynik = []
    wzor = re.compile(r'<div class="title">\s*<a[^>]*href="([^"]*)"[^>]*>([\s\S]*?)</a>\s*</div>\s*'
                      r'<div class="position">([\s\S]*?)</div>')
    for m in wzor.finditer(html):
        nazwa, funkcja = _bez_znacznikow(m[2]), _bez_znacznikow(m[3])
        if not nazwa or not funkcja:
            continue
        href = m[1] if m[1].startswith("http") else f"https://www.gov.pl{m[1]}"
        wynik.append(Rekord(
            zrodlo="kprm", identyfikator=href.rsplit("/", 1)[-1] or nazwa.lower(), rodzaj="osoba",
            nazwy=[nazwa], obywatelstwa=["PL"], aktualny=True,
            funkcje=[{"tytul": funkcja, "kod": _kod_kprm(funkcja), "od": None, "do": None}],
            adres_zrodla=href or adres,
        ))
    return wynik


def zapytanie_wikidata_stanowiska(qidy: list[str], tryb: str) -> str:
    wartosci = " ".join(f"wd:{q}" for q in qidy)
    pl = "?pos wdt:P1001 wd:Q36 ." if tryb == "subclass_pl" else ""
    return f"SELECT DISTINCT ?pos WHERE {{ VALUES ?root {{ {wartosci} }} ?pos wdt:P279* ?root . {pl} }}"


def zapytanie_wikidata_osoby(qidy: list[str], od_roku: int) -> str:
    wartosci = " ".join(f"wd:{q}" for q in qidy)
    return f"""SELECT ?person ?namePl ?nameEn ?birth ?prec ?pos ?posLabel ?start ?end
  (GROUP_CONCAT(DISTINCT ?cit; separator="|") AS ?cits)
  (GROUP_CONCAT(DISTINCT ?alias; separator="|") AS ?aliases)
WHERE {{
  VALUES ?pos {{ {wartosci} }}
  ?person p:P39 ?st . ?st ps:P39 ?pos .
  ?person wdt:P31 wd:Q5 .
  OPTIONAL {{ ?st pq:P580 ?start }}
  OPTIONAL {{ ?st pq:P582 ?end }}
  FILTER(!BOUND(?end) || YEAR(?end) >= {int(od_roku)})
  OPTIONAL {{ ?person p:P569/psv:P569 [ wikibase:timeValue ?birth ; wikibase:timePrecision ?prec ] }}
  OPTIONAL {{ ?person wdt:P27/wdt:P297 ?cit }}
  OPTIONAL {{ ?person rdfs:label ?namePl FILTER(LANG(?namePl) = "pl") }}
  OPTIONAL {{ ?person rdfs:label ?nameEn FILTER(LANG(?nameEn) = "en") }}
  OPTIONAL {{ ?person skos:altLabel ?alias FILTER(LANG(?alias) IN ("pl", "en")) }}
  OPTIONAL {{ ?pos rdfs:label ?posLabel FILTER(LANG(?posLabel) = "pl") }}
}}
GROUP BY ?person ?namePl ?nameEn ?birth ?prec ?pos ?posLabel ?start ?end"""


def _w(b: dict, k: str) -> str | None:
    return (b.get(k) or {}).get("value")


def parsuj_wikidata_stanowiska(odp: dict) -> list[str]:
    wynik = []
    for b in odp.get("results", {}).get("bindings", []):
        q = (_w(b, "pos") or "").rsplit("/", 1)[-1]
        if re.fullmatch(r"Q\d+", q):
            wynik.append(q)
    return wynik


def parsuj_wikidata(odp: dict, kody: dict[str, str], dzis: date | None = None) -> list[Rekord]:
    """Wiersze SPARQL (jeden na oswiadczenie P39) -> osoby z lista funkcji."""
    dzis = dzis or date.today()
    wedle: dict[str, Rekord] = {}
    for b in odp.get("results", {}).get("bindings", []):
        qid = (_w(b, "person") or "").rsplit("/", 1)[-1]
        if not qid:
            continue
        nazwa = _w(b, "namePl") or _w(b, "nameEn")
        if not nazwa or re.fullmatch(r"Q\d+", nazwa):
            continue
        qid_poz = (_w(b, "pos") or "").rsplit("/", 1)[-1]
        od = data_czesciowa(_w(b, "start"))[0] if _w(b, "start") else None
        do = data_czesciowa(_w(b, "end"))[0] if _w(b, "end") else None
        r = wedle.get(qid)
        if r is None:
            prec = int(float(_w(b, "prec") or 0))      # 11 = dzien, 10 = miesiac, 9 = rok
            data, rok = data_czesciowa(_w(b, "birth"))
            daty = [data] if (prec >= 11 and data) else ([str(rok)] if rok else [])
            r = Rekord(zrodlo="wikidata", identyfikator=qid, rodzaj="osoba", nazwy=[nazwa],
                       daty_urodzenia=daty, aktualny=False,
                       adres_zrodla=f"https://www.wikidata.org/wiki/{qid}")
            wedle[qid] = r
        for a in [_w(b, "nameEn"), _w(b, "namePl"), *((_w(b, "aliases") or "").split("|"))]:
            if a and a != r.nazwy[0] and a not in r.nazwy:
                r.nazwy.append(a)
        for c in (_w(b, "cits") or "").split("|"):
            if c and c.upper() not in r.obywatelstwa:
                r.obywatelstwa.append(c.upper())
        tytul = _w(b, "posLabel") or qid_poz
        if not any(f["tytul"] == tytul and f["od"] == od and f["do"] == do for f in r.funkcje):
            r.funkcje.append({"tytul": tytul, "kod": kody.get(qid_poz), "od": od, "do": do})
        # Brak daty konca przy poczatku z ostatnich 15 lat - traktujemy jako trwajace.
        if not do and (not od or dzis.year - int(od[:4]) <= 15):
            r.aktualny = True
    return list(wedle.values())


# --- Pobieranie -------------------------------------------------------------------


def _sparql(klient: httpx.Client, zapytanie: str) -> dict:
    for i in range(5):
        odp = klient.post(ADRESY["wikidata"], data={"query": zapytanie},
                          headers={"Accept": "application/sparql-results+json"})
        if odp.status_code in (429, 502, 503, 504) and i < 4:
            time.sleep(5 * (i + 1))
            continue
        odp.raise_for_status()
        return odp.json()
    raise RuntimeError("Wikidata nie odpowiada")


def pobierz(zrodlo: str, klient: httpx.Client | None = None) -> tuple[list[Rekord], dict]:
    """Pobiera i parsuje jedno zrodlo. Zwraca (rekordy, metadane)."""
    klient = klient or _klient()
    if zrodlo == "eu_fsf":
        token = os.getenv("PIECZAPP_EU_FSF_TOKEN") or _EU_FSF_TOKEN_PUBLICZNY
        tekst = _pobierz_tekst(klient, ADRESY["eu_fsf"], params={"token": token})
        return parsuj_ue(tekst), {"sha256": hashlib.sha256(tekst.encode("utf-8")).hexdigest()}
    if zrodlo == "un_sc":
        tekst = _pobierz_tekst(klient, ADRESY["un_sc"])
        return parsuj_onz(tekst), {"sha256": hashlib.sha256(tekst.encode("utf-8")).hexdigest()}
    if zrodlo == "mswia":
        rekordy, wersja = parsuj_mswia(_pobierz_tekst(klient, ADRESY["mswia"]))
        return rekordy, {"wersja": wersja}
    if zrodlo == "ofac_sdn":
        sdn = _pobierz_tekst(klient, ADRESY["ofac_sdn"])
        alt = _pobierz_tekst(klient, ADRESY["ofac_alt"])
        return parsuj_ofac(sdn, alt), {}
    if zrodlo == "sejm":
        kadencje = klient.get(f"{ADRESY['sejm']}/term").raise_for_status().json()
        kadencje = sorted(kadencje, key=lambda k: k.get("num", 0))[-3:]
        dane = []
        for k in kadencje:
            poslowie = klient.get(f"{ADRESY['sejm']}/term{k['num']}/MP").raise_for_status().json()
            dane.append({"kadencja": k, "poslowie": poslowie})
        return parsuj_sejm(dane), {"kadencje": [k["num"] for k in kadencje]}
    if zrodlo == "kprm":
        return parsuj_kprm(_pobierz_tekst(klient, ADRESY["kprm"])), {}
    if zrodlo == "wikidata":
        kody: dict[str, str] = {}
        qidy_wszystkie: list[str] = []
        for kod, (_, qidy, tryb) in KATALOG_PEP.items():
            if tryb != "direct":
                qidy = _unikalne(qidy + parsuj_wikidata_stanowiska(
                    _sparql(klient, zapytanie_wikidata_stanowiska(qidy, tryb))))
            for q in qidy:
                kody.setdefault(q, kod)
                qidy_wszystkie.append(q)
        qidy_wszystkie = _unikalne(qidy_wszystkie)
        rekordy: dict[str, Rekord] = {}
        for i in range(0, len(qidy_wszystkie), 40):
            for r in parsuj_wikidata(_sparql(klient, zapytanie_wikidata_osoby(
                    qidy_wszystkie[i:i + 40], WIKIDATA_OD_ROKU)), kody):
                if r.identyfikator in rekordy:
                    stary = rekordy[r.identyfikator]
                    stary.funkcje.extend(f for f in r.funkcje if f not in stary.funkcje)
                    stary.nazwy.extend(n for n in r.nazwy if n not in stary.nazwy)
                    stary.aktualny = bool(stary.aktualny or r.aktualny)
                else:
                    rekordy[r.identyfikator] = r
        return list(rekordy.values()), {"stanowisk": len(qidy_wszystkie)}
    raise ValueError(f"Nieznane zrodlo: {zrodlo}")


# --- Migawki ----------------------------------------------------------------------

_BLOKADA = threading.Lock()
_INDEKSY: dict[str, tuple[Indeks, str]] = {}      # kategoria -> (indeks, sygnatura migawek)


def _plik_lokalny(zrodlo: str) -> Path:
    return config.DANE / "listy_aml" / f"{zrodlo}.json"


def _klucz_s3(zrodlo: str) -> str:
    return f"{magazyn.PREFIKS}/admin/listy_aml/{zrodlo}.json"


def wczytaj_migawke(zrodlo: str) -> dict | None:
    if magazyn.TRYB == "s3":
        try:
            odp = magazyn._klient_s3().get_object(Bucket=magazyn.BUCKET, Key=_klucz_s3(zrodlo))
        except Exception as blad:  # noqa: BLE001
            if type(blad).__name__ == "NoSuchKey" or magazyn._kod_bledu(blad) in ("NoSuchKey", "404"):
                return None
            raise
        return json.loads(odp["Body"].read().decode("utf-8"))
    plik = _plik_lokalny(zrodlo)
    return json.loads(plik.read_text("utf-8")) if plik.exists() else None


def zapisz_migawke(zrodlo: str, migawka: dict) -> None:
    tresc = json.dumps(migawka, ensure_ascii=False)
    if magazyn.TRYB == "s3":
        magazyn._klient_s3().put_object(Bucket=magazyn.BUCKET, Key=_klucz_s3(zrodlo),
                                        Body=tresc.encode("utf-8"), **magazyn._szyfrowanie())
    else:
        plik = _plik_lokalny(zrodlo)
        plik.parent.mkdir(parents=True, exist_ok=True)
        tymczasowy = plik.with_suffix(".tmp")
        tymczasowy.write_text(tresc, encoding="utf-8")
        tymczasowy.replace(plik)
    _INDEKSY.clear()


def zrodla_wlaczone() -> list[str]:
    return [z for k in KATEGORIE.values() for z in k if z != "ofac_sdn" or OFAC_WLACZONY]


def _nieaktualna(migawka: dict | None, zrodlo: str) -> bool:
    if not migawka or not migawka.get("pobrano"):
        return True
    return datetime.fromisoformat(migawka["pobrano"]) < datetime.now() - timedelta(days=WAZNOSC[zrodlo])


def odswiez(zrodla: list[str] | None = None, wymus: bool = False) -> list[dict]:
    """Pobiera nieaktualne (albo wskazane) listy. Zwraca raport bez danych osob."""
    raport = []
    with _klient() as klient:
        for zrodlo in zrodla or zrodla_wlaczone():
            stara = wczytaj_migawke(zrodlo)
            if not wymus and not _nieaktualna(stara, zrodlo):
                raport.append({"zrodlo": zrodlo, "stan": "aktualna", "liczba": stara.get("liczba", 0)})
                continue
            start = time.time()
            try:
                rekordy, meta = pobierz(zrodlo, klient)
                poprzednia = (stara or {}).get("liczba", 0)
                if not rekordy or (poprzednia and len(rekordy) < poprzednia * MIN_UDZIAL):
                    raise RuntimeError(f"podejrzanie malo rekordow: {len(rekordy)} (bylo {poprzednia})")
                nowa = {"zrodlo": zrodlo, "pobrano": datetime.now().isoformat(timespec="seconds"),
                        "liczba": len(rekordy), "meta": meta, "blad": None,
                        "rekordy": [r.slownik() for r in rekordy]}
                zapisz_migawke(zrodlo, nowa)
                log.info("lista %s: %d rekordow w %.0fs", zrodlo, len(rekordy), time.time() - start)
                raport.append({"zrodlo": zrodlo, "stan": "pobrana", "liczba": len(rekordy)})
            except Exception as blad:  # noqa: BLE001
                opis = f"{type(blad).__name__}: {str(blad)[:160]}"
                log.warning("lista %s: blad pobierania (%s)", zrodlo, type(blad).__name__)
                if stara:
                    stara["blad"] = {"kiedy": datetime.now().isoformat(timespec="seconds"), "opis": opis}
                    zapisz_migawke(zrodlo, stara)
                else:
                    zapisz_migawke(zrodlo, {"zrodlo": zrodlo, "pobrano": None, "liczba": 0, "meta": {},
                                            "blad": {"kiedy": datetime.now().isoformat(timespec="seconds"),
                                                     "opis": opis}, "rekordy": []})
                raport.append({"zrodlo": zrodlo, "stan": "blad", "opis": opis})
    return raport


def stan() -> list[dict]:
    """Co wie interfejs: ktore listy sa, z kiedy, ile maja wpisow. Bez tresci."""
    wynik = []
    for kategoria, zrodla in KATEGORIE.items():
        for zrodlo in zrodla:
            if zrodlo == "ofac_sdn" and not OFAC_WLACZONY:
                continue
            m = wczytaj_migawke(zrodlo) or {}
            wynik.append({
                "zrodlo": zrodlo, "kategoria": kategoria, "etykieta": ETYKIETY[zrodlo],
                "pobrano": m.get("pobrano"), "liczba": m.get("liczba", 0),
                "wersja": (m.get("meta") or {}).get("wersja"), "blad": m.get("blad"),
                "nieaktualna": _nieaktualna(m, zrodlo),
            })
    return wynik


def indeks(kategoria: str) -> tuple[Indeks, list[str]]:
    """Indeks rekordow kategorii (sankcje | pep) i opis uzytych migawek
    ("eu_fsf z 2026-11-07" ...). Budowany raz, do nastepnego odswiezenia."""
    migawki = [(z, wczytaj_migawke(z)) for z in KATEGORIE[kategoria] if z != "ofac_sdn" or OFAC_WLACZONY]
    sygnatura = "|".join(f"{z}:{(m or {}).get('pobrano')}" for z, m in migawki)
    with _BLOKADA:
        gotowy = _INDEKSY.get(kategoria)
        if gotowy and gotowy[1] == sygnatura:
            return gotowy[0], _opis(migawki)
        rekordy = [Rekord.ze_slownika(r) for _, m in migawki if m for r in m.get("rekordy", [])
                   if not r.get("wykreslono")]
        zbudowany = Indeks(rekordy)
        _INDEKSY[kategoria] = (zbudowany, sygnatura)
        return zbudowany, _opis(migawki)


def _opis(migawki) -> list[str]:
    return [f"{z} z {m['pobrano'][:10]}" if m and m.get("pobrano") else f"{z}: brak listy"
            for z, m in migawki]


def gotowe(kategoria: str) -> bool:
    """Czy jest choc jedna migawka kategorii z rekordami."""
    return any((wczytaj_migawke(z) or {}).get("liczba") for z in KATEGORIE[kategoria]
               if z != "ofac_sdn" or OFAC_WLACZONY)


def odswiezaj_w_tle(co_godzin: int = 6) -> threading.Thread:
    """Watek: co kilka godzin odswieza nieaktualne listy. Dwie kopie aplikacji
    moga to robic rownolegle - zapis migawki jest idempotentny."""
    def petla():
        time.sleep(30)          # nie na starcie, zeby nie opozniac sondy /zdrowie
        while True:
            try:
                odswiez()
            except Exception as blad:  # noqa: BLE001
                log.warning("odswiezanie list AML: %s", type(blad).__name__)
            time.sleep(co_godzin * 3600)
    watek = threading.Thread(target=petla, name="listy-aml", daemon=True)
    watek.start()
    return watek
