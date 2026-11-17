"""Weryfikator bibliografii laboratorium w OpenAlex.

Każdy raport badawczy laboratorium (rejestry JSON/JSONL) przechodzi przez to
narzędzie, zanim jego liczby trafią do decyzji. Sprawdza, czy praca istnieje,
czy tytuł się zgadza, i dopisuje identyfikator OpenAlex, liczbę cytowań,
miejsce publikacji oraz streszczenie (do ręcznego porównania z liczbami
w rejestrze).

Bez zależności (Python >= 3.10). Klucz OpenAlex jest opcjonalny
(zmienna OPENALEX_API_KEY, nigdy w repo). Bez klucza: 1000 kredytów dziennie;
pobranie pojedynczego rekordu po DOI/arXiv jest darmowe, wyszukiwanie po
tytule kosztuje 1 kredyt.

Użycie:
    python tools/lab_openalex/weryfikuj.py REJESTR.jsonl [--out wynik.jsonl]
    python tools/lab_openalex/weryfikuj.py academic-evidence.json --out ...

Wynik: jeden wiersz JSON na pozycję, pole `werdykt`:
    potwierdzona     - identyfikator istnieje i tytuł się zgadza (>= 0.85)
    potwierdzona_arxiv - jest na arXiv, OpenAlex jeszcze jej nie zaindeksował
    tytul_inny       - identyfikator istnieje, ale tytuł wyraźnie inny
    znaleziona_tytul - brak identyfikatora, praca znaleziona po tytule
    niepewna         - po tytule znaleziono coś podobnego (0.6-0.85)
    nie_znaleziona   - brak w OpenAlex (możliwa pomyłka albo zmyślenie)
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.openalex.org"
POLA = "id,doi,title,publication_year,publication_date,cited_by_count,type,primary_location,abstract_inverted_index,is_retracted"
ARXIV = re.compile(r"(?:arxiv[:/ ]|abs/|pdf/)?(\d{4}\.\d{4,5})(?:v\d+)?", re.I)
DOI = re.compile(r"(10\.\d{4,9}/[^\s\"'<>]+)", re.I)


def _get(sciezka: str, parametry: dict | None = None) -> dict | None:
    parametry = dict(parametry or {})
    klucz = os.environ.get("OPENALEX_API_KEY")
    if klucz:
        parametry["api_key"] = klucz
    url = f"{API}{sciezka}"
    if parametry:
        url += "?" + urllib.parse.urlencode(parametry)
    zadanie = urllib.request.Request(url, headers={"User-Agent": "lab-openalex-weryfikator/1.0"})
    for proba in range(4):
        try:
            with urllib.request.urlopen(zadanie, timeout=30) as odp:
                return json.load(odp)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code == 429 or e.code >= 500:
                time.sleep(2 ** proba)
                continue
            raise
        except urllib.error.URLError:
            time.sleep(2 ** proba)
    raise RuntimeError(f"OpenAlex nie odpowiada: {sciezka}")


def podobienstwo(a: str, b: str) -> float:
    norm = lambda s: re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).split()
    return difflib.SequenceMatcher(None, " ".join(norm(a)), " ".join(norm(b))).ratio()


def streszczenie(indeks: dict | None) -> str:
    if not indeks:
        return ""
    slowa = sorted((p, w) for w, pozycje in indeks.items() for p in pozycje)
    return " ".join(w for _, w in slowa)


def tytul_z_arxiv(numer: str) -> str | None:
    """Tytuł prosto z arXiv: OpenAlex bywa kilka dni w tyle i nie zawsze ma DOI arXiv."""
    url = f"https://export.arxiv.org/api/query?id_list={numer}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "lab-openalex-weryfikator/1.0"}), timeout=30) as odp:
            tekst = odp.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError):
        return None
    tytuly = re.findall(r"<title>([^<]*)</title>", tekst)
    return re.sub(r"\s+", " ", tytuly[1]).strip() if len(tytuly) > 1 else None


def identyfikatory(rekord: dict) -> tuple[str | None, str | None]:
    tekst = " ".join(str(rekord.get(k, "")) for k in ("identifier", "source", "publication_link", "doi", "doi_or_arxiv", "url", "arxiv"))
    doi = DOI.search(tekst)
    if doi and "arxiv" not in doi.group(1).lower():
        return None, doi.group(1).rstrip(".,);/")
    arx = ARXIV.search(tekst)
    if arx:
        return arx.group(1), None
    return None, (doi.group(1).rstrip(".,);/") if doi else None)


def sprawdz(rekord: dict) -> dict:
    tytul = rekord.get("title") or ""
    arxiv, doi = identyfikatory(rekord)
    praca = None
    sposob = None
    wid = re.search(r"W\d{6,}", str(rekord.get("openalex") or ""))
    if wid:
        praca = _get(f"/works/{wid.group(0)}", {"select": POLA})
        sposob = f"openalex:{wid.group(0)}"
    elif arxiv:
        praca = _get(f"/works/doi:10.48550/arxiv.{arxiv}", {"select": POLA})
        sposob = f"arXiv:{arxiv}"
    elif doi:
        praca = _get(f"/works/doi:{doi}", {"select": POLA})
        sposob = f"doi:{doi}"
    if praca:
        zgodnosc = podobienstwo(tytul, praca.get("title"))
        werdykt = "potwierdzona" if zgodnosc >= 0.85 else "tytul_inny"
    else:
        szukaj = _get("/works", {"search": tytul[:250], "per-page": 3, "select": POLA}) if tytul else None
        kandydaci = (szukaj or {}).get("results", [])
        najlepszy = max(kandydaci, key=lambda w: podobienstwo(tytul, w.get("title")), default=None)
        zgodnosc = podobienstwo(tytul, najlepszy.get("title")) if najlepszy else 0.0
        if najlepszy and zgodnosc >= 0.85:
            praca, werdykt = najlepszy, "znaleziona_tytul"
        elif najlepszy and zgodnosc >= 0.6:
            praca, werdykt = najlepszy, "niepewna"
        else:
            werdykt = "nie_znaleziona"
        sposob = (sposob + " -> " if sposob else "") + "tytuł"
        if arxiv and werdykt in ("znaleziona_tytul", "niepewna", "nie_znaleziona"):
            tytul_arxiv = tytul_z_arxiv(arxiv)
            if tytul_arxiv and podobienstwo(tytul, tytul_arxiv) >= 0.85:
                werdykt = "potwierdzona_arxiv" if werdykt == "nie_znaleziona" else "potwierdzona"
                zgodnosc = max(zgodnosc, podobienstwo(tytul, tytul_arxiv))
                sposob += " -> arXiv API"
    zrodlo = ((praca or {}).get("primary_location") or {}).get("source") or {}
    return {
        "id": rekord.get("id"),
        "tytul_w_rejestrze": tytul,
        "werdykt": werdykt,
        "sposob": sposob,
        "zgodnosc_tytulu": round(zgodnosc, 3),
        "openalex": (praca or {}).get("id"),
        "tytul_openalex": (praca or {}).get("title"),
        "rok": (praca or {}).get("publication_year"),
        "data": (praca or {}).get("publication_date"),
        "typ": (praca or {}).get("type"),
        "miejsce": zrodlo.get("display_name"),
        "cytowania": (praca or {}).get("cited_by_count"),
        "wycofana": (praca or {}).get("is_retracted"),
        "liczby_w_rejestrze": rekord.get("numeric_findings") or rekord.get("claim"),
        "streszczenie": streszczenie((praca or {}).get("abstract_inverted_index"))[:1500],
    }


def wczytaj(sciezka: str) -> list[dict]:
    with open(sciezka, encoding="utf-8") as f:
        tekst = f.read()
    if sciezka.endswith(".jsonl"):
        return [json.loads(w) for w in tekst.splitlines() if w.strip()]
    dane = json.loads(tekst)
    if isinstance(dane, list):
        return dane
    for v in dane.values():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            return v
    raise SystemExit("Nie znaleziono listy rekordów w pliku")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("rejestr")
    p.add_argument("--out")
    a = p.parse_args(argv)
    rekordy = wczytaj(a.rejestr)
    wyniki = []
    for r in rekordy:
        w = sprawdz(r)
        wyniki.append(w)
        print(f"{w['werdykt']:16} {w['zgodnosc_tytulu']:.2f} {str(w['id']):10} {w['tytul_w_rejestrze'][:70]}", file=sys.stderr)
        time.sleep(0.15)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            for w in wyniki:
                f.write(json.dumps(w, ensure_ascii=False) + "\n")
    licz: dict[str, int] = {}
    for w in wyniki:
        licz[w["werdykt"]] = licz.get(w["werdykt"], 0) + 1
    print(json.dumps(licz, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
