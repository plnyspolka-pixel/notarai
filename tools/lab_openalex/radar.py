"""Radar laboratorium: nowe prace w OpenAlex dla obserwowanych tematów.

Dla każdego tematu z `docs/lab-openalex/radar.json` pobiera prace opublikowane
od daty ostatniego przebiegu (albo `--od RRRR-MM-DD`), odrzuca te, które już są
w rejestrach laboratorium (po identyfikatorze OpenAlex), i zapisuje przegląd
w Markdown. Przegląd czyta człowiek albo Claude i decyduje, co trafia do
rejestru (`docs/lab-openalex/zrodla/*.jsonl`) — radar niczego sam nie dopisuje.

Bez zależności, klucz opcjonalny (OPENALEX_API_KEY). Jedno zapytanie na temat
(ok. 0,001 USD bez klucza), więc 20 tematów mieści się w darmowym budżecie.

    python tools/lab_openalex/radar.py                  # od ostatniego przebiegu
    python tools/lab_openalex/radar.py --od 2026-11-01  # od zadanej daty
    python tools/lab_openalex/radar.py --sucho          # tylko pokaż zapytania
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from weryfikuj import _get, streszczenie  # noqa: E402

KATALOG = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "lab-openalex")
POLA = "id,title,publication_date,cited_by_count,primary_location,abstract_inverted_index,type"


def znane_id(katalog: str) -> set[str]:
    znane: set[str] = set()
    for plik in glob.glob(os.path.join(katalog, "**", "*.jsonl"), recursive=True):
        with open(plik, encoding="utf-8") as f:
            for wiersz in f:
                if wiersz.strip():
                    oa = json.loads(wiersz).get("openalex")
                    if oa:
                        znane.add(oa.rsplit("/", 1)[-1])
    return znane


def przebieg(konfig: dict, od: str, znane: set[str], sucho: bool) -> tuple[list[str], dict]:
    linie = [f"# Radar laboratorium — prace od {od}", ""]
    statystyka = {}
    for temat in konfig["tematy"]:
        filtr = f"from_publication_date:{od}"
        if temat.get("min_cytowan"):
            filtr += f",cited_by_count:>{temat['min_cytowan'] - 1}"
        if temat.get("typ"):  # np. "dataset" - tylko zbiory danych
            filtr += f",type:{temat['typ']}"
        parametry = {"search": temat["zapytanie"], "filter": filtr, "per-page": temat.get("limit", 8), "select": POLA}
        if sucho:
            print(temat["nazwa"], parametry)
            continue
        wyniki = (_get("/works", parametry) or {}).get("results", [])
        nowe = [w for w in wyniki if w["id"].rsplit("/", 1)[-1] not in znane]
        statystyka[temat["nazwa"]] = len(nowe)
        linie += [f"## {temat['nazwa']} ({temat['kierunek']}) — {len(nowe)} nowych", ""]
        for w in nowe:
            zrodlo = ((w.get("primary_location") or {}).get("source") or {}).get("display_name") or "?"
            abstrakt = streszczenie(w.get("abstract_inverted_index"))[:400]
            linie += [
                f"- **{w['title']}** — {w.get('publication_date')}, {zrodlo}, cytowania {w.get('cited_by_count')}, [{w['id'].rsplit('/', 1)[-1]}]({w['id']})",
                f"  {abstrakt}…" if abstrakt else "  (brak streszczenia)",
            ]
        linie.append("")
    return linie, statystyka


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--od")
    p.add_argument("--sucho", action="store_true")
    p.add_argument("--katalog", default=KATALOG)
    a = p.parse_args(argv)
    sciezka_konfig = os.path.join(a.katalog, "radar.json")
    with open(sciezka_konfig, encoding="utf-8") as f:
        konfig = json.load(f)
    od = a.od or konfig.get("ostatni_przebieg") or (dt.date.today() - dt.timedelta(days=7)).isoformat()
    linie, statystyka = przebieg(konfig, od, znane_id(a.katalog), a.sucho)
    if a.sucho:
        return 0
    dzis = dt.date.today().isoformat()
    os.makedirs(os.path.join(a.katalog, "radar"), exist_ok=True)
    wyjscie = os.path.join(a.katalog, "radar", f"{dzis}.md")
    with open(wyjscie, "w", encoding="utf-8") as f:
        f.write("\n".join(linie))
    konfig["ostatni_przebieg"] = dzis
    with open(sciezka_konfig, "w", encoding="utf-8") as f:
        json.dump(konfig, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps({"plik": wyjscie, "nowe": statystyka}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
