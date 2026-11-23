#!/usr/bin/env python3
"""Pobiera zasoby CC0 z Poly Haven według scenografia/manifest.json do scenografia/.cache/.

Zasoby nie trafiają do repozytorium (.cache jest w .gitignore). Skrypt jest
idempotentny: plik o zgodnym rozmiarze nie jest pobierany drugi raz.

    python3 scenografia/pobierz_zasoby.py            # wszystko
    python3 scenografia/pobierz_zasoby.py --tylko hdri

Zapisuje też scenografia/.cache/zasoby.json z ostatecznymi ścieżkami i adresami
źródeł (do raportu licencyjnego i dla skryptów budujących sceny).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request

TU = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(TU, ".cache")
API = "https://api.polyhaven.com"
UA = {"User-Agent": "notarai-scenografia/1.0"}


def _get_json(url: str) -> dict:
    for proba in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as o:
                return json.load(o)
        except Exception:  # noqa: BLE001 - ponawiamy przy błędach sieci
            time.sleep(2 + proba * 5)
    raise RuntimeError(f"Nie udało się pobrać {url}")


def _pobierz(url: str, cel: str, rozmiar: int | None) -> None:
    if os.path.exists(cel) and (rozmiar is None or os.path.getsize(cel) == rozmiar):
        return
    os.makedirs(os.path.dirname(cel), exist_ok=True)
    for proba in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as o, open(cel + ".part", "wb") as f:
                while True:
                    blok = o.read(1 << 20)
                    if not blok:
                        break
                    f.write(blok)
            os.replace(cel + ".part", cel)
            return
        except Exception:  # noqa: BLE001
            time.sleep(2 + proba * 5)
    raise RuntimeError(f"Nie udało się pobrać {url}")


def modele(lista: list[str], res: str, wynik: dict) -> None:
    for aid in lista:
        pliki = _get_json(f"{API}/files/{aid}")
        blend = pliki["blend"].get(res) or pliki["blend"][sorted(pliki["blend"])[0]]
        b = blend["blend"]
        katalog = os.path.join(CACHE, "modele", aid)
        cel = os.path.join(katalog, os.path.basename(b["url"]))
        _pobierz(b["url"], cel, b.get("size"))
        for rel, inc in b.get("include", {}).items():
            _pobierz(inc["url"], os.path.join(katalog, rel), inc.get("size"))
        wynik["modele"][aid] = {"blend": cel, "zrodlo": f"https://polyhaven.com/a/{aid}", "licencja": "CC0"}
        print("model", aid, flush=True)


def tekstury(lista: list[str], res: str, mapy: list[str], wynik: dict) -> None:
    for aid in lista:
        pliki = _get_json(f"{API}/files/{aid}")
        wpis = {"zrodlo": f"https://polyhaven.com/a/{aid}", "licencja": "CC0", "mapy": {}}
        for mapa in mapy:
            if mapa not in pliki and mapa == "Diffuse":
                zast = next((k for k in ("diff", "col_01", "col_1", "Color") if k in pliki), None)
                if zast is None:
                    continue
                pliki["Diffuse"] = pliki[zast]
            if mapa not in pliki:
                continue
            warianty = pliki[mapa].get(res) or pliki[mapa][sorted(pliki[mapa])[0]]
            plik = warianty.get("jpg") or warianty.get("png") or next(iter(warianty.values()))
            cel = os.path.join(CACHE, "tekstury", aid, os.path.basename(plik["url"]))
            _pobierz(plik["url"], cel, plik.get("size"))
            wpis["mapy"][mapa] = cel
        wynik["tekstury"][aid] = wpis
        print("tekstura", aid, flush=True)


def hdri(lista: list[str], res: str, wynik: dict) -> None:
    for aid in lista:
        pliki = _get_json(f"{API}/files/{aid}")
        h = pliki["hdri"].get(res) or pliki["hdri"][sorted(pliki["hdri"])[0]]
        plik = h["hdr"]
        cel = os.path.join(CACHE, "hdri", os.path.basename(plik["url"]))
        _pobierz(plik["url"], cel, plik.get("size"))
        wynik["hdri"][aid] = {"plik": cel, "zrodlo": f"https://polyhaven.com/a/{aid}", "licencja": "CC0"}
        print("hdri", aid, flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tylko", choices=["modele", "tekstury", "hdri"])
    a = ap.parse_args()
    m = json.load(open(os.path.join(TU, "manifest.json"), encoding="utf-8"))
    sciezka = os.path.join(CACHE, "zasoby.json")
    wynik = json.load(open(sciezka)) if os.path.exists(sciezka) else {"modele": {}, "tekstury": {}, "hdri": {}}
    if a.tylko in (None, "modele"):
        modele(m["modele"]["lista"], m["modele"]["res"], wynik)
    if a.tylko in (None, "tekstury"):
        tekstury(m["tekstury"]["lista"], m["tekstury"]["res"], m["tekstury"]["mapy"], wynik)
    if a.tylko in (None, "hdri"):
        hdri(m["hdri"]["lista"], m["hdri"]["res"], wynik)
    os.makedirs(CACHE, exist_ok=True)
    json.dump(wynik, open(sciezka, "w"), indent=1, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
