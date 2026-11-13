#!/usr/bin/env python3
"""Koszt odcinka „Komputerku…” w trzech torach produkcji: obecnym, tanim hostowanym i na własnym GPU.

Czyta odcinek.json (schemat: ../odcinek-szablon.json) i liczy, ile kosztują
klatki, głosy, ujęcia mówiące, ujęcia bez mowy i montaż. Ceny są z 13.11.2026
(źródła: README.md §5, awatary.md, docs/kampania-komputerku/KOSZTY_I_COMPUTE_2026-11-13.md).
Skrypt NIE woła żadnego API - tylko liczy. Realne wydatki dopisuje `log`.

Użycie:
  koszty_odcinka.py policz ../odcinek-szablon.json [--powtorki 2] [--odcinkow 8] [--csv wynik.csv]
  koszty_odcinka.py log <odcinek> <pozycja> <usd> [zrodlo]      dopisuje do koszty_log.csv
  koszty_odcinka.py ceny                                        wypisuje cenniki torów

Czas kwestii szacujemy z długości tekstu: ok. 15 znaków/s polskiej mowy, min. 3 s.
"""
import csv
import json
import os
import sys
from datetime import date

KURS_USD_PLN = float(os.getenv("KURS_USD_PLN", "3.70"))
ZNAKOW_NA_SEKUNDE = 15.0
MIN_CZAS_KWESTII_S = 3.0
TU = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(TU, "koszty_log.csv")

# Kadry „zbliżenie” idą do HeyGen (stabilna twarz); plan ogólny / przez ramię to „w planie”.
KADRY_ZBLIZENIE = {"B_85mm", "B"}

# GPU: RunPod Community RTX 4090, 0,34 USD/h (per-sekunda) + 5 min rozgrzewki na sesję.
GPU_USD_H = float(os.getenv("GPU_USD_H", "0.34"))
GPU_ROZGRZEWKA_S = 300

TORY = {
    "obecny": {
        "opis": "ElevenLabs v3 + fal Nano Banana Pro edit + HeyGen Avatar 6 Turbo (zbliżenia) "
                "+ fal Kling AI Avatar v2 Pro (w planie) + fal Kling 2.5 Turbo Pro i2v (bez mowy)",
        "klatka_usd": 0.15,            # fal nano-banana-pro/edit, za obraz
        "klatka_proby": 3,
        "glos_usd_1k": 0.08,           # ElevenLabs API PAYG v3
        "glos_podejscia": 3,
        "zblizenie_usd_s": 0.039,      # HeyGen heygen-avatar-6-turbo (zmierzone, awatary.md)
        "plan_usd_s": 0.115,           # fal Kling AI Avatar v2 Pro
        "bez_mowy_usd_s": 0.07,        # fal Kling 2.5 Turbo Pro i2v, klip min. 5 s
        "bez_mowy_min_s": 5,
        "llm_usd": 0.05,
        "montaz_usd": 0.10,            # Remotion Lambda
        "gpu_rozgrzewka_usd": 0.0,
    },
    "tani_hostowany": {
        "opis": "Google Chirp 3 HD (1 mln zn./mies. gratis) + fal Seedream 4 (klatki) + HeyGen Avatar 6 Turbo "
                "(zbliżenia) + WaveSpeed InfiniteTalk (w planie) + Replicate Wan 2.2 fast i2v (bez mowy)",
        "klatka_usd": 0.03,            # fal bytedance/seedream/v4 edit
        "klatka_proby": 3,
        "glos_usd_1k": 0.0,            # Chirp 3 HD w darmowym limicie; po limicie 0,03 USD/1k
        "glos_podejscia": 3,
        "zblizenie_usd_s": 0.039,
        "plan_usd_s": 0.03,            # WaveSpeed InfiniteTalk (awatary.md: ok. 0,03-0,06)
        "bez_mowy_usd_s": 0.02,        # Replicate Wan 2.2 i2v fast 720p: 0,10 USD za klip 5 s
        "bez_mowy_min_s": 5,
        "llm_usd": 0.03,               # Sonnet 4.6 z cache + Haiku 4.5
        "montaz_usd": 0.0,             # ffmpeg / Remotion lokalnie albo GitHub Actions
        "gpu_rozgrzewka_usd": 0.0,
    },
    "gpu_4090": {
        "opis": f"Własne GPU (RTX 4090 {GPU_USD_H:.2f} USD/h): Qwen-Image-Edit-2511 (klatki), Wan 2.2 14B + LoRA 4-krokowa "
                "(bez mowy), EchoMimicV3 / InfiniteTalk (w planie); HeyGen Avatar 6 Turbo zostaje na zbliżenia; TTS Chirp 3 HD",
        "klatka_usd": GPU_USD_H / 3600 * 25,     # ~25 s na obraz 2K (edycja wieloreferencyjna)
        "klatka_proby": 3,
        "glos_usd_1k": 0.0,
        "glos_podejscia": 3,
        "zblizenie_usd_s": 0.039,                # bez zamiennika o tej samej stabilności twarzy (awatary.md)
        "plan_usd_s": GPU_USD_H / 3600 * 25,     # ~25x czas rzeczywisty (InfiniteTalk 4-krokowy, 480p + upscale)
        "bez_mowy_usd_s": GPU_USD_H / 3600 * 30, # Wan 2.2 14B fp8 + LightX2V: ~150 s na klip 5 s 720p
        "bez_mowy_min_s": 5,
        "llm_usd": 0.03,
        "montaz_usd": 0.0,
        "gpu_rozgrzewka_usd": GPU_USD_H / 3600 * GPU_ROZGRZEWKA_S,
    },
}


def czas_kwestii(ujecie: dict) -> float:
    if ujecie.get("czas_s"):
        return float(ujecie["czas_s"])
    znakow = len(ujecie.get("kwestia", ""))
    return max(MIN_CZAS_KWESTII_S, znakow / ZNAKOW_NA_SEKUNDE)


def rozbij(odcinek: dict) -> dict:
    """Jednostki do wyceny: unikalne klatki, znaki dialogu, sekundy wg typu ujęcia."""
    klatki, znaki, zblizenie_s, plan_s, bez_mowy = set(), 0, 0.0, 0.0, []
    for u in odcinek.get("ujecia", []):
        typ = u.get("typ")
        if typ == "mowiace":
            znaki += len(u.get("kwestia", ""))
            if u.get("klatka_startowa"):
                klatki.add(u["klatka_startowa"])
            t = czas_kwestii(u)
            if u.get("kadr", "").split("_")[0] in KADRY_ZBLIZENIE or u.get("kadr") in KADRY_ZBLIZENIE:
                zblizenie_s += t
            else:
                plan_s += t
        elif typ in ("bez_mowy", "reakcja", "rekwizyt", "przebitka"):
            if u.get("klatka_startowa"):
                klatki.add(u["klatka_startowa"])
            bez_mowy.append(float(u.get("czas_s") or 5))
        # ekran (nagranie aplikacji) i plansza: 0 USD
    return {"klatki": len(klatki), "znaki": znaki, "zblizenie_s": zblizenie_s,
            "plan_s": plan_s, "bez_mowy": bez_mowy}


def wycen(jedn: dict, tor: dict, powtorki: float) -> list[tuple[str, float]]:
    bez_mowy_s = sum(max(c, tor["bez_mowy_min_s"]) for c in jedn["bez_mowy"])
    pozycje = [
        ("klatki ujęć", jedn["klatki"] * tor["klatka_proby"] * tor["klatka_usd"]),
        ("głosy", jedn["znaki"] / 1000 * tor["glos_podejscia"] * tor["glos_usd_1k"]),
        ("zbliżenia mówiące", jedn["zblizenie_s"] * powtorki * tor["zblizenie_usd_s"]),
        ("mówiące w planie", jedn["plan_s"] * powtorki * tor["plan_usd_s"]),
        ("ujęcia bez mowy", bez_mowy_s * powtorki * tor["bez_mowy_usd_s"]),
        ("scenariusz / plan ujęć (LLM)", tor["llm_usd"]),
        ("montaż", tor["montaz_usd"]),
        ("rozgrzewka GPU (sesja)", tor["gpu_rozgrzewka_usd"]),
    ]
    return [(n, round(k, 4)) for n, k in pozycje]


def policz(sciezka: str, powtorki: float, odcinkow: int, csv_out: str | None) -> None:
    with open(sciezka, encoding="utf-8") as f:
        odcinek = json.load(f)
    jedn = rozbij(odcinek)
    czas = jedn["zblizenie_s"] + jedn["plan_s"] + sum(jedn["bez_mowy"]) + sum(
        float(u.get("czas_s") or 0) for u in odcinek.get("ujecia", []) if u.get("typ") in ("ekran", "plansza"))
    print(f"Odcinek {odcinek.get('odcinek')}: „{odcinek.get('tytul')}” — ok. {czas:.0f} s, "
          f"{jedn['klatki']} klatek, {jedn['znaki']} znaków dialogu, mówiące: zbliżenia {jedn['zblizenie_s']:.0f} s, "
          f"w planie {jedn['plan_s']:.0f} s, bez mowy {sum(jedn['bez_mowy']):.0f} s; powtórki ×{powtorki:g}\n")
    wiersze = []
    sumy = {}
    for nazwa, tor in TORY.items():
        pozycje = wycen(jedn, tor, powtorki)
        suma = sum(k for _, k in pozycje)
        sumy[nazwa] = suma
        print(f"== {nazwa}: {tor['opis']}")
        for n, k in pozycje:
            if k:
                print(f"   {n:32s} {k:8.3f} USD")
                wiersze.append((odcinek.get("odcinek"), nazwa, n, k))
        print(f"   {'RAZEM na odcinek':32s} {suma:8.2f} USD ≈ {suma * KURS_USD_PLN:6.2f} zł"
              f"   | {odcinkow} odc.: {suma * odcinkow:7.2f} USD\n")
    baza = sumy["obecny"]
    for nazwa, suma in sumy.items():
        if nazwa != "obecny" and baza:
            print(f"{nazwa}: {100 * (1 - suma / baza):.0f}% taniej niż obecny tor "
                  f"(oszczędność {(baza - suma) * odcinkow:.2f} USD na {odcinkow} odc.)")
    print("\nPoza odcinkiem: abonamenty (ElevenLabs Creator 22 USD, HeyGen Creator 29 USD, Descript 24-35 USD) "
          "i ok. 7 USD/mies. za dysk sieciowy z modelami przy torze GPU.")
    if csv_out:
        with open(csv_out, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["odcinek", "tor", "pozycja", "usd"])
            w.writerows(wiersze)
        print(f"zapisano {csv_out}")


def log(odcinek: str, pozycja: str, usd: str, zrodlo: str = "") -> None:
    nowy = not os.path.exists(LOG)
    with open(LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if nowy:
            w.writerow(["data", "odcinek", "pozycja", "usd", "zrodlo"])
        w.writerow([date.today().isoformat(), odcinek, pozycja, f"{float(usd):.4f}", zrodlo])
    print(f"dopisano do {LOG}")


def ceny() -> None:
    for nazwa, tor in TORY.items():
        print(f"== {nazwa}")
        for k, v in tor.items():
            if k != "opis":
                print(f"   {k:20s} {v}")


def main(a: list[str]) -> None:
    if not a or a[0] not in ("policz", "log", "ceny"):
        sys.exit(__doc__)
    if a[0] == "ceny":
        return ceny()
    if a[0] == "log":
        if len(a) < 4:
            sys.exit("log <odcinek> <pozycja> <usd> [zrodlo]")
        return log(a[1], a[2], a[3], a[4] if len(a) > 4 else "")
    powtorki, odcinkow, csv_out = 2.0, 8, None
    reszta = a[1:]
    sciezka = None
    i = 0
    while i < len(reszta):
        if reszta[i] == "--powtorki":
            powtorki = float(reszta[i + 1]); i += 2
        elif reszta[i] == "--odcinkow":
            odcinkow = int(reszta[i + 1]); i += 2
        elif reszta[i] == "--csv":
            csv_out = reszta[i + 1]; i += 2
        else:
            sciezka = reszta[i]; i += 1
    if not sciezka:
        sys.exit("policz <odcinek.json> [--powtorki 2] [--odcinkow 8] [--csv plik]")
    policz(sciezka, powtorki, odcinkow, csv_out)


if __name__ == "__main__":
    main(sys.argv[1:])
