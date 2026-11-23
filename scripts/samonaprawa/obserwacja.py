"""Obserwacja po wdrozeniu poprawki: czy blad zniknal i czy nie przyszly nowe.

Werdykt:
  "ok"     - naprawiony blad nie wrocil w nowej wersji i nie ma nowych bledow,
  "cofnij" - naprawiony blad wrocil w nowej wersji albo nowa wersja przyniosla
             nowy blad kodu (co najmniej PROG_NOWYCH wystapien).

Uzycie:
  python scripts/samonaprawa/obserwacja.py --odcisk abc123def456 --wersja <tag> \
      --od <ms wdrozenia> --minut 20 --wynik obserwacja.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import zgloszenie  # noqa: E402

PROG_NOWYCH = 3
PRZERWA = 60


def ocen(odcisk: str, wersja: str, przed: list[dict], po: list[dict]) -> dict:
    znane = {w["odcisk"] for w in przed}
    w_nowej = [w for w in po if str(w.get("wersja", "")) == wersja]
    nawroty = sum(1 for w in w_nowej if w["odcisk"] == odcisk)
    nowe = Counter(w["odcisk"] for w in w_nowej
                   if w["odcisk"] not in znane and w["odcisk"] != odcisk and w.get("rodzaj") == "kod")
    grozne = {k: v for k, v in nowe.items() if v >= PROG_NOWYCH}
    powody = []
    if nawroty:
        powody.append(f"naprawiany blad {odcisk} wystapil {nawroty}x w nowej wersji {wersja}")
    for k, v in sorted(grozne.items()):
        powody.append(f"nowy blad {k} w nowej wersji ({v}x)")
    return {"werdykt": "cofnij" if powody else "ok", "powody": powody,
            "zdarzen_w_nowej_wersji": len(w_nowej), "nawroty": nawroty, "nowe": dict(nowe)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--odcisk", required=True)
    parser.add_argument("--wersja", required=True)
    parser.add_argument("--od", type=int, required=True, help="czas wdrozenia, ms od epoki")
    parser.add_argument("--minut", type=int, default=20)
    parser.add_argument("--wynik", required=True)
    args = parser.parse_args()

    przed = zgloszenie.znaczniki(args.od - 24 * 3600_000, args.od)
    koniec = time.time() + args.minut * 60
    wynik = {"werdykt": "ok", "powody": []}
    # Patrzymy przez caly czas obserwacji; przy pierwszym sygnale cofamy od razu.
    while True:
        po = zgloszenie.znaczniki(args.od)
        wynik = ocen(args.odcisk, args.wersja, przed, po)
        print(f"{time.strftime('%H:%M:%S')} {wynik['werdykt']} "
              f"zdarzen={wynik['zdarzen_w_nowej_wersji']} nawroty={wynik['nawroty']}")
        if wynik["werdykt"] == "cofnij" or time.time() >= koniec:
            break
        time.sleep(PRZERWA)
    Path(args.wynik).write_text(json.dumps(wynik, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
