#!/usr/bin/env python3
"""Paczka ujęć „bez mowy” z odcinek.json na własnym GPU przez API ComfyUI (Wan 2.2 I2V + LoRA 4-krokowa).

Dla każdego ujęcia typu bez_mowy / reakcja / rekwizyt / przebitka z klatką startową:
klatka → ComfyUI (/upload/image) → workflow wan22_i2v_lightning.json z promptem
= PROMPT BAZOWY + prompt_delta → /prompt → /history → mp4 do wyjscie/<EP>/.
Każdy gotowy klip jest od razu na dysku (odporność na przerwanie poda/spot),
a czas GPU każdego klipu dopisuje się do ../koszty_log.csv (sekundy × USD/h).

Użycie:
  klipy_batch.py ../../odcinki/EP03.json --comfy https://<pod>-8188.proxy.runpod.net [--usd-h 0.34] [--powtorzenia 2]
  klipy_batch.py ../../odcinki/EP03.json --dry-run            # tylko zapisuje gotowe workflow JSON

Rozdzielczość 9:16: 480x832 (szybko, ~70-120 s na 5 s) albo 720x1280 (~2-3 min). 5 s = 81 klatek @16 fps.
Standardowo generujemy 480x832 i upscalujemy w montażu; 720p tylko dla ujęć hero.
NIEPRZETESTOWANE w tej sesji (brak GPU) - pierwszą paczkę puść z --powtorzenia 1 i obejrzyj.
"""
import json
import os
import re
import sys
import time
import urllib.request
import uuid

TU = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(TU, "..", ".."))
PROMPTY = os.path.join(ROOT, "pakiet", "05_biblia_produkcji", "PROMPTY_PRODUKCYJNE.md")
WORKFLOW = os.path.join(TU, "wan22_i2v_lightning.json")
TYPY = ("bez_mowy", "reakcja", "rekwizyt", "przebitka")
NEGATYW = ("blurry, low quality, distorted face, extra fingers, text, watermark, logo, subtitles, "
           "cartoon, anime, exaggerated expression, jitter, flicker")


def prompt_bazowy() -> str:
    tekst = open(PROMPTY, encoding="utf-8").read()
    m = re.search(r"## Stały prompt bazowy.*?\n(.+?)\n\n## ", tekst, re.S)
    return m.group(1).strip() if m else ""


def http(url: str, dane: bytes | None = None, naglowki: dict | None = None) -> bytes:
    req = urllib.request.Request(url, data=dane, headers=naglowki or {})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def wyslij_obraz(comfy: str, sciezka: str) -> str:
    granica = uuid.uuid4().hex
    nazwa = os.path.basename(sciezka)
    with open(sciezka, "rb") as f:
        tresc = f.read()
    cialo = (f"--{granica}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{nazwa}\"\r\n"
             f"Content-Type: application/octet-stream\r\n\r\n").encode() + tresc + \
            f"\r\n--{granica}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n--{granica}--\r\n".encode()
    odp = json.loads(http(f"{comfy}/upload/image", cialo, {"Content-Type": f"multipart/form-data; boundary={granica}"}))
    return odp["name"]


def workflow(klatka: str, prompt: str, szer: int, wys: int, klatek: int, seed: int, prefix: str) -> dict:
    szablon = open(WORKFLOW, encoding="utf-8").read()
    podst = {"klatka": klatka, "prompt": prompt.replace('"', "'"), "negatyw": NEGATYW, "szerokosc": szer,
             "wysokosc": wys, "klatki": klatek, "seed": seed, "prefix": prefix}
    for k, v in podst.items():
        szablon = szablon.replace(f'"{{{{{k}}}}}"', json.dumps(v, ensure_ascii=False))
    w = json.loads(szablon)
    w.pop("_opis", None)
    return w


def czekaj(comfy: str, prompt_id: str, limit_s: int = 1800) -> dict:
    start = time.time()
    while time.time() - start < limit_s:
        hist = json.loads(http(f"{comfy}/history/{prompt_id}"))
        if prompt_id in hist and hist[prompt_id].get("status", {}).get("completed", True) and hist[prompt_id].get("outputs"):
            return hist[prompt_id]
        time.sleep(5)
    raise TimeoutError(f"ComfyUI nie skonczyl {prompt_id} w {limit_s} s")


def pobierz_wyniki(comfy: str, hist: dict, katalog: str) -> list[str]:
    pliki = []
    for wyjscie in hist.get("outputs", {}).values():
        for klucz in ("videos", "gifs", "images"):
            for p in wyjscie.get(klucz, []):
                url = f"{comfy}/view?filename={p['filename']}&subfolder={p.get('subfolder', '')}&type={p.get('type', 'output')}"
                cel = os.path.join(katalog, p["filename"])
                with open(cel, "wb") as f:
                    f.write(http(url))
                pliki.append(cel)
    return pliki


def log_koszt(odcinek: str, pozycja: str, usd: float) -> None:
    sys.path.insert(0, os.path.join(TU, ".."))
    import koszty_odcinka
    koszty_odcinka.log(odcinek, pozycja, f"{usd:.4f}", "gpu_4090")


def main(a: list[str]) -> None:
    if not a:
        sys.exit(__doc__)
    plik, comfy, usd_h, powt, dry = a[0], None, 0.34, 2, False
    i = 1
    while i < len(a):
        if a[i] == "--comfy":
            comfy = a[i + 1].rstrip("/"); i += 2
        elif a[i] == "--usd-h":
            usd_h = float(a[i + 1]); i += 2
        elif a[i] == "--powtorzenia":
            powt = int(a[i + 1]); i += 2
        elif a[i] == "--dry-run":
            dry = True; i += 1
        else:
            i += 1
    odc = json.load(open(plik, encoding="utf-8"))
    ep = f"EP{int(odc.get('odcinek', 0)):02d}"
    katalog = os.path.join(ROOT, "wyjscie", ep)
    os.makedirs(katalog, exist_ok=True)
    baza = prompt_bazowy()
    ujecia = [u for u in odc.get("ujecia", []) if u.get("typ") in TYPY and u.get("klatka_startowa")
              and not str(u["klatka_startowa"]).startswith("DO_WYGENEROWANIA")]
    if not ujecia:
        sys.exit("brak ujec bez mowy z klatka startowa w tym odcinku")
    if not dry and not comfy:
        sys.exit("podaj --comfy <url> albo --dry-run")
    for u in ujecia:
        hero = u.get("jakosc") == "hero"
        szer, wys = (720, 1280) if hero else (480, 832)
        klatek = int(round(float(u.get("czas_s") or 5) * 16)) // 4 * 4 + 1   # 4n+1 klatek dla Wan
        prompt = f"{baza} {u.get('prompt_delta', '')}".strip()
        for nr in range(1, powt + 1):
            seed = (hash((ep, u["id"], nr)) & 0x7FFFFFFF)
            prefix = f"{ep}_{u['id']}_v{nr}"
            if dry:
                w = workflow(os.path.basename(u["klatka_startowa"]), prompt, szer, wys, klatek, seed, prefix)
                cel = os.path.join(katalog, f"{prefix}.workflow.json")
                json.dump(w, open(cel, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                print(f"[{prefix}] workflow → {cel} ({szer}x{wys}, {klatek} klatek)")
                continue
            sciezka = u["klatka_startowa"] if os.path.isabs(u["klatka_startowa"]) else os.path.join(ROOT, u["klatka_startowa"])
            nazwa = wyslij_obraz(comfy, sciezka)
            w = workflow(nazwa, prompt, szer, wys, klatek, seed, prefix)
            start = time.time()
            odp = json.loads(http(f"{comfy}/prompt", json.dumps({"prompt": w}).encode(), {"Content-Type": "application/json"}))
            hist = czekaj(comfy, odp["prompt_id"])
            pliki = pobierz_wyniki(comfy, hist, katalog)
            sek = time.time() - start
            usd = sek / 3600 * usd_h
            log_koszt(ep, f"{u['id']} v{nr} wan2.2 i2v {szer}x{wys}", usd)
            print(f"[{prefix}] {sek:.0f} s GPU ≈ {usd:.4f} USD → {', '.join(os.path.basename(p) for p in pliki)}")
    print(f"gotowe: {katalog}")


if __name__ == "__main__":
    main(sys.argv[1:])
