"""Zgloszenie samonaprawy: walidacja danych z aplikacji i historia z CloudWatch.

Dane przychodza z repository_dispatch (aplikacja) albo z workflow_dispatch
(recznie). Traktujemy je jak dane z zewnatrz: tylko znane pola, tylko
dozwolone znaki, przyciete. Do agenta i do zgloszenia na GitHubie idzie
wylacznie wynik tej funkcji - nigdy surowy ladunek.

Uzycie:
  python scripts/samonaprawa/zgloszenie.py --wejscie ladunek.json --wyjscie zgloszenie.json [--logi]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

ZNACZNIK = "samonaprawa"
GRUPA_LOGOW = "/ecs/notarai"
_ODCISK = re.compile(r"^[0-9a-f]{12}$")
# Opis bledu to typ, kod AWS i miejsca w kodzie - bez znakow sterujacych powloki.
_BEZPIECZNY = re.compile(r"[^\w .,:;()\[\]<>/=+\-'\"|!?%@#ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]")
_MIEJSCE = re.compile(r"^[\w.]+\.py:\d+ [\w<>]+$")


def _tekst(wartosc, dlugosc: int) -> str:
    return _BEZPIECZNY.sub("", str(wartosc or ""))[:dlugosc].strip()


def oczysc(ladunek: dict) -> dict:
    """Znane pola zgloszenia, oczyszczone. Bez odcisku - ValueError."""
    if not isinstance(ladunek, dict):
        raise ValueError("ladunek nie jest obiektem")
    odcisk = str(ladunek.get("odcisk", "")).strip().lower()
    uwagi = _tekst(ladunek.get("uwagi"), 2000)
    if not odcisk and uwagi:
        # Zgloszenie reczne (wlasciciel opisuje blad slowami): odcisk z opisu.
        odcisk = hashlib.sha256(uwagi.lower().encode()).hexdigest()[:12]
        ladunek = {**ladunek, "rodzaj": "reczne"}
    if not _ODCISK.match(odcisk):
        raise ValueError("brak poprawnego odcisku bledu")
    miejsca = [m for m in (ladunek.get("miejsca") or []) if isinstance(m, str) and _MIEJSCE.match(m)][:8]
    rodzaj = str(ladunek.get("rodzaj", "kod"))
    return {
        "odcisk": odcisk,
        "rodzaj": rodzaj if rodzaj in ("kod", "przejsciowy", "reczne") else "kod",
        "typ": _tekst(ladunek.get("typ"), 80),
        "kod_aws": _tekst(ladunek.get("kod_aws"), 80),
        "opis": _tekst(ladunek.get("opis"), 1500),
        "miejsca": miejsca,
        "endpoint": _tekst(ladunek.get("endpoint"), 120),
        "wersja": _tekst(ladunek.get("wersja"), 40),
        "czas": _tekst(ladunek.get("czas"), 30),
        # Reczne zgloszenie wlasciciela (np. zrzut ekranu z bledem) - opis slowami.
        "uwagi": uwagi,
    }


def znaczniki(od_ms: int, do_ms: int | None = None, klient=None) -> list[dict]:
    """Znaczniki samonaprawy z logow aplikacji w przedziale czasu."""
    if klient is None:
        import boto3
        klient = boto3.client("logs")
    wynik, token = [], None
    while True:
        argumenty = {"logGroupName": GRUPA_LOGOW, "startTime": od_ms,
                     "filterPattern": f'"{ZNACZNIK} {{"'}
        if do_ms:
            argumenty["endTime"] = do_ms
        if token:
            argumenty["nextToken"] = token
        odp = klient.filter_log_events(**argumenty)
        for zdarzenie in odp.get("events", []):
            wpis = odczytaj_znacznik(zdarzenie.get("message", ""))
            if wpis:
                wpis["ts"] = zdarzenie.get("timestamp")
                wynik.append(wpis)
        token = odp.get("nextToken")
        if not token or len(wynik) > 5000:
            return wynik


def odczytaj_znacznik(linia: str) -> dict | None:
    poz = linia.find(f"{ZNACZNIK} {{")
    if poz < 0:
        return None
    try:
        wpis = json.loads(linia[poz + len(ZNACZNIK) + 1:])
    except ValueError:
        return None
    return wpis if isinstance(wpis, dict) and _ODCISK.match(str(wpis.get("odcisk", ""))) else None


def historia(odcisk: str, dni: int = 7, klient=None) -> dict:
    teraz = int(time.time() * 1000)
    wpisy = [w for w in znaczniki(teraz - dni * 86400_000, klient=klient) if w["odcisk"] == odcisk]
    return {
        "wystapien_7_dni": len(wpisy),
        "wersje": sorted({str(w.get("wersja", "")) for w in wpisy}),
        "endpointy": sorted({str(w.get("endpoint", "")) for w in wpisy if w.get("endpoint")})[:10],
        "pierwsze": min((w["ts"] for w in wpisy), default=None),
        "ostatnie": max((w["ts"] for w in wpisy), default=None),
    }


def kandydaci(minut: int, klient=None) -> list[dict]:
    """Bledy kodu z ostatnich minut: ostatni znacznik kazdego odcisku + liczba, od najczestszych.

    Przeglad okresowy (cron) dziala bez tokenu w aplikacji: workflow sam czyta
    znaczniki z CloudWatch.
    """
    teraz = int(time.time() * 1000)
    ostatnie: dict[str, dict] = {}
    ile: dict[str, int] = {}
    for w in znaczniki(teraz - minut * 60_000, klient=klient):
        if w.get("rodzaj") != "kod":
            continue
        ile[w["odcisk"]] = ile.get(w["odcisk"], 0) + 1
        if w["odcisk"] not in ostatnie or (w.get("ts") or 0) >= (ostatnie[w["odcisk"]].get("ts") or 0):
            ostatnie[w["odcisk"]] = w
    wynik = [{**ostatnie[k], "wystapien": ile[k]} for k in ostatnie]
    return sorted(wynik, key=lambda w: -w["wystapien"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wejscie")
    parser.add_argument("--wyjscie", required=True)
    parser.add_argument("--logi", action="store_true", help="dopisz historie z CloudWatch")
    parser.add_argument("--przeglad", type=int, metavar="MINUT",
                        help="zamiast --wejscie: lista bledow kodu z ostatnich MINUT minut")
    args = parser.parse_args()
    if args.przeglad:
        lista = [oczysc(w) | {"wystapien": w["wystapien"]} for w in kandydaci(args.przeglad)]
        Path(args.wyjscie).write_text(json.dumps(lista, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"bledow kodu: {len(lista)}")
        return 0
    if not args.wejscie:
        parser.error("--wejscie albo --przeglad")
    try:
        zgloszenie = oczysc(json.loads(Path(args.wejscie).read_text(encoding="utf-8")))
    except (OSError, ValueError) as e:
        print(f"::error::Zle zgloszenie samonaprawy: {e}")
        return 1
    if args.logi:
        try:
            zgloszenie["historia"] = historia(zgloszenie["odcisk"])
        except Exception as e:  # noqa: BLE001 - historia to dodatek
            print(f"::warning::Brak historii z CloudWatch ({type(e).__name__})")
    Path(args.wyjscie).write_text(json.dumps(zgloszenie, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(zgloszenie, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
