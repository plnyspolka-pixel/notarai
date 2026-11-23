#!/usr/bin/env python3
"""Buduje i renderuje plany zdjęciowe.

    python zbuduj.py --plan s02                       # wszystkie warianty, stille + najazd
    python zbuduj.py --plan s02 --podglad             # szybki podgląd 1/3 rozdzielczości, bez głębi
    python zbuduj.py --plan s02 --warianty dzien --kamery K01_plan_ogolny
    python zbuduj.py --plan wszystkie --bez-ruchu

Uruchamiać interpreterem z modułem bpy (pip install bpy; Blender 5.x).
"""
from __future__ import annotations

import argparse
import importlib
import os
import sys
import time

TU = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TU)
sys.path.insert(0, os.path.join(TU, "sety"))
sys.path.insert(0, os.path.dirname(TU))

# Twarda reguła (23.11.2026): render scenografii nigdy na GitHub Actions, tylko Cloudflare (finyou-scena).
from tools.zakaz_gha import zakaz_renderu_na_github_actions  # noqa: E402

zakaz_renderu_na_github_actions("render scenografii (scenografia/zbuduj.py)")

import bpy  # noqa: E402

import wspolne as w  # noqa: E402

PLANY = {
    "s01": "s01_recepcja",
    "s02": "s02_gabinet_heleny",
    "s03": "s03_pokoj_marty_kuby",
    "s04": "s04_korytarz_klatka",
    "s05": "s05_kancelaria_teresy",
    "s06": "s06_kawiarnia",
    "s07": "s07_ulica",
    "s08": "s08_parking",
    "s09": "s09_sala_szkoleniowa",
    "s10": "s10_mieszkanie_ireny",
}


def jeden(kod, a):
    mod = importlib.import_module(PLANY[kod])
    warianty = a.warianty.split(",") if a.warianty else mod.WARIANTY
    czasy, ruch = {}, None
    for i, war in enumerate(warianty):
        w.nowa_scena(probki=a.probki)
        plan = w.Plan(kod, mod.NAZWA)
        mod.zbuduj(plan, war)
        plan.siedziska = w.kontrola_siedzisk(plan)  # przerywa budowę, gdy siedzisko odwrócone od celu
        sc = bpy.context.scene
        if i == 0 and (a.rzut or not a.podglad):
            w.rzut_z_gory(plan, os.path.join(w.RENDERY, kod, "rzut_z_gory.png"))
        if a.rzut:
            break
        if a.podglad:
            sc.render.resolution_percentage = 33
            sc.cycles.samples = 12
            kat = os.path.join(w.RENDERY, "_tmp", "podglad", kod)
            os.makedirs(kat, exist_ok=True)
            for k in plan.kamery:
                if a.kamery and k["nazwa"] not in a.kamery.split(","):
                    continue
                sc.camera = bpy.data.objects[k["nazwa"]]
                t = time.time()
                sc.render.filepath = os.path.join(kat, f"{k['nazwa']}_{war}.jpg")
                sc.render.image_settings.file_format = "JPEG"
                bpy.ops.render.render(write_still=True)
                print(f"podglad {kod} {k['nazwa']} {war} {time.time() - t:.0f}s", flush=True)
            continue
        wybor = a.kamery.split(",") if a.kamery else getattr(mod, "KAMERY_WARIANTU", {}).get(war)
        if wybor is None and i > 0:
            wybor = [k["nazwa"] for k in plan.kamery[:3]]
        cz = w.render_stille(plan, war, kamery=wybor)
        czasy[war] = cz
        if i == 0 and not a.bez_ruchu and getattr(mod, "RUCH", None):
            kam, kon = mod.RUCH
            ruch = w.render_ruch(plan, kam, kon, wariant=war)
        w.zapisz_opis(plan, {war: cz}, ruch)
        if i == 0:
            w.zapisz_blend(plan)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--warianty")
    ap.add_argument("--kamery")
    ap.add_argument("--probki", type=int, default=32)
    ap.add_argument("--podglad", action="store_true")
    ap.add_argument("--bez-ruchu", action="store_true")
    ap.add_argument("--rzut", action="store_true", help="tylko kontrola siedzisk i rzut z góry (rendery/<kod>/rzut_z_gory.png)")
    a = ap.parse_args()
    kody = list(PLANY) if a.plan == "wszystkie" else a.plan.split(",")
    for kod in kody:
        jeden(kod, a)


if __name__ == "__main__":
    main()
