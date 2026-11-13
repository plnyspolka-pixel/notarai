#!/usr/bin/env python3
"""Zestawienie kosztów całego sezonu z wygenerowanych odcinki/EP*.json.

Dla każdego odcinka: czas, liczba ujęć, koszt w trzech torach (koszty_odcinka.TORY)
oraz zmierzony koszt LLM rozpisania odcinka (pole _produkcja.uzycie, cennik Bedrock
Sonnet 4.6: 3/15 USD za 1M, cache odczyt 10 %, zapis 125 %). Na końcu suma i średnia.

Użycie: sezon_koszty.py [--powtorki 2] [--markdown]
"""
import glob
import json
import os
import sys

import koszty_odcinka as k

TU = os.path.dirname(os.path.abspath(__file__))
ODCINKI = os.path.join(TU, "..", "odcinki")


def koszt_llm(prod: dict) -> float:
    u = prod.get("uzycie") or {}
    model = prod.get("model", "")
    we, wy = (3.0, 15.0) if "sonnet-4" in model else (5.0, 25.0) if "opus-4" in model else (1.0, 5.0)
    return (u.get("inputTokens", 0) * we + u.get("cacheReadInputTokens", 0) * we * 0.1
            + u.get("cacheWriteInputTokens", 0) * we * 1.25 + u.get("outputTokens", 0) * wy) / 1e6


def main(a):
    powt = 2.0
    md = "--markdown" in a
    if "--powtorki" in a:
        powt = float(a[a.index("--powtorki") + 1])
    pliki = sorted(p for p in glob.glob(os.path.join(ODCINKI, "EP*.json")) if ".zlecenie." not in p)
    if not pliki:
        sys.exit("brak odcinki/EP*.json")
    wiersze, sumy = [], {t: 0.0 for t in k.TORY}
    llm_suma = 0.0
    for p in pliki:
        d = json.load(open(p, encoding="utf-8"))
        jedn = k.rozbij(d)
        czas = sum(float(u.get("czas_s") or 0) for u in d.get("ujecia", []))
        koszty = {t: sum(x for _, x in k.wycen(jedn, tor, powt)) for t, tor in k.TORY.items()}
        llm = koszt_llm(d.get("_produkcja", {}))
        llm_suma += llm
        for t in sumy:
            sumy[t] += koszty[t]
        wiersze.append((f"EP{int(d.get('odcinek', 0)):02d}", d.get("tytul", ""), czas, len(d.get("ujecia", [])),
                        koszty, llm))
    n = len(wiersze)
    if md:
        print("| Odcinek | Czas | Ujęć | obecny | tani hostowany | gpu_4090 | LLM (zmierzony) |")
        print("|---|---|---|---|---|---|---|")
        for ep, tyt, czas, uj, ko, llm in wiersze:
            print(f"| {ep} „{tyt}” | {czas:.0f} s | {uj} | {ko['obecny']:.2f} $ | {ko['tani_hostowany']:.2f} $ | "
                  f"{ko['gpu_4090']:.2f} $ | {llm:.2f} $ |")
        print(f"| **Sezon ({n} odc.)** | | | **{sumy['obecny']:.2f} $** | **{sumy['tani_hostowany']:.2f} $** | "
              f"**{sumy['gpu_4090']:.2f} $** | **{llm_suma:.2f} $** |")
        print(f"| Średnio na odcinek | | | {sumy['obecny']/n:.2f} $ | {sumy['tani_hostowany']/n:.2f} $ | "
              f"{sumy['gpu_4090']/n:.2f} $ | {llm_suma/n:.2f} $ |")
    else:
        for ep, tyt, czas, uj, ko, llm in wiersze:
            print(f"{ep} {czas:5.0f} s {uj:3d} ujęć | obecny {ko['obecny']:6.2f} | tani {ko['tani_hostowany']:6.2f} | "
                  f"gpu {ko['gpu_4090']:6.2f} | LLM {llm:.3f} $")
        print(f"SEZON {n} odc.: obecny {sumy['obecny']:.2f} | tani {sumy['tani_hostowany']:.2f} | "
              f"gpu {sumy['gpu_4090']:.2f} | LLM {llm_suma:.2f} $")


if __name__ == "__main__":
    main(sys.argv[1:])
