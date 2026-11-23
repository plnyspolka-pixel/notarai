#!/usr/bin/env python3
"""Ulepszanie klipów „w stylu DLSS” przed montażem: wyjscie/<EP>/klipy → wyjscie/<EP>/klipy_hd.

DLSS (NVIDIA) działa na żywo w silniku gry (wektory ruchu i głębia z renderera), więc do gotowych
plików wideo się go nie podepnie. Ten sam efekt, czyli AI super-rozdzielczość, daje SeedVR2
(ByteDance, Apache 2.0). Liczy się na naszym GPU w SaladCloud przez `ai-clip` z repo finyou
(rodzina `seedvr2`, szablon `seedvr2.up`: krótszy bok → 1080, kl./s i dźwięk bez zmian).

Tory:
  salad    1) `--tor salad` zapisuje zlecenie wyjscie/<EP>/ulepsz-salad.json (klipy poniżej 1080 px),
           2) w repo finyou: node services/ai-clip/ai-clip.mjs run <zlecenie> --pay --max-usd 1
           3) `--przyjmij out/ai-clip/<przebieg>` kopiuje wyniki do klipy_hd pod nazwami źródeł.
  lokalny  Bez GPU i za 0 USD: ffmpeg (klatki pośrednie minterpolate, gdy < 25 kl./s, lanczos, CAS).
           Ostrzejsze krawędzie i płynny ruch, ale detali nie „dorysuje”. Dobre do szkicu.

Klipy, które już mają >= 1080 px szerokości i >= 25 kl./s, są pomijane.
montaz_odcinka.py z flagą --hd bierze klipy z klipy_hd/, gdy tam są.

Użycie:
  ulepsz_klipy.py EP04 --tor salad
  ulepsz_klipy.py EP04 --przyjmij /sciezka/finyou/out/ai-clip/<przebieg>
  ulepsz_klipy.py EP04 --tor lokalny
  ulepsz_klipy.py --plik we.mp4 wy.mp4             # pojedynczy plik, tor lokalny
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time

TU = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(TU, ".."))
W, H, FPS = 1080, 1920, 25


def probe(p: str) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,r_frame_rate", "-of", "json", p], capture_output=True, text=True).stdout
    s = (json.loads(out or "{}").get("streams") or [{}])[0]
    num, _, den = str(s.get("r_frame_rate", "0/1")).partition("/")
    fps = float(num) / float(den) if float(den or 0) else 0.0
    return {"w": int(s.get("width", 0)), "h": int(s.get("height", 0)), "fps": fps}


def ma_audio(p: str) -> bool:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type",
                          "-of", "csv=p=0", p], capture_output=True, text=True).stdout
    return "audio" in out


def run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"ffmpeg błąd:\n{' '.join(cmd)}\n{r.stderr[-1500:]}")


def filtr_lokalny(fps_we: float) -> str:
    """Łańcuch ffmpeg: odszum → klatki pośrednie (gdy fps < 25) → lanczos do 9:16 1080p → CAS."""
    kroki = ["hqdn3d=1.5:1.5:3:3"]          # bez odszumu upscale wzmacnia szum kompresji
    if fps_we and fps_we < FPS - 0.5:
        # mci + aobmc: kompensacja ruchu blokami z nakładaniem; scd=fdiff nie miesza klatek przy cięciu
        kroki.append(f"minterpolate=fps={FPS}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1:scd=fdiff")
    else:
        kroki.append(f"fps={FPS}")
    kroki += [f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos+accurate_rnd",
              f"crop={W}:{H}", "cas=strength=0.55", "format=yuv420p"]
    return ",".join(kroki)


def ulepsz_lokalnie(we: str, wy: str) -> float:
    start = time.time()
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", we, "-vf", filtr_lokalny(probe(we)["fps"]),
           "-c:v", "libx264", "-preset", "slow", "-crf", "16"]
    cmd += ["-c:a", "copy"] if ma_audio(we) else ["-an"]
    run(cmd + [wy])
    return time.time() - start


def slug(nazwa: str) -> str:
    """Ten sam kształt co slugify w ai-clip: a-z, 0-9, myślnik."""
    return re.sub(r"[^a-z0-9]+", "-", os.path.splitext(nazwa)[0].lower()).strip("-")[:60].rstrip("-") or "klip"


def do_ulepszenia(klipy: str, wszystkie: bool) -> list[str]:
    wynik = []
    for f in sorted(os.listdir(klipy)):
        if not f.endswith(".mp4"):
            continue
        p = probe(os.path.join(klipy, f))
        if not wszystkie and p["w"] >= W and p["fps"] >= FPS - 0.5:
            print(f"[{f}] {p['w']}x{p['h']}@{p['fps']:.0f} - już HD, pomijam")
            continue
        wynik.append(f)
    return wynik


def zlecenie_salad(ep: str, baza: str, pliki: list[str]) -> None:
    zl = {"family": "seedvr2",
          "shots": [{"video": os.path.join(baza, "klipy", f), "slug": slug(f), "plik_zrodlowy": f} for f in pliki]}
    if len(zl["shots"]) > 40:
        sys.exit("ai-clip bierze do 40 ujęć na jedno wynajęcie - podziel odcinek")
    cel = os.path.join(baza, "ulepsz-salad.json")
    json.dump(zl, open(cel, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"zlecenie: {cel} ({len(pliki)} klipów)\n"
          f"w repo finyou:\n  node services/ai-clip/ai-clip.mjs plan {cel}\n"
          f"  node services/ai-clip/ai-clip.mjs run {cel} --pay --max-usd 1\n"
          f"potem: ulepsz_klipy.py {ep} --przyjmij <finyou>/out/ai-clip/<przebieg>")


def przyjmij(baza: str, katalog: str) -> None:
    zl = json.load(open(os.path.join(baza, "ulepsz-salad.json"), encoding="utf-8"))
    hd = os.path.join(baza, "klipy_hd")
    os.makedirs(hd, exist_ok=True)
    brak = []
    for s in zl["shots"]:
        src = os.path.join(katalog, f"{s['slug']}.mp4")
        if not os.path.exists(src):
            brak.append(s["plik_zrodlowy"]); continue
        shutil.copy2(src, os.path.join(hd, s["plik_zrodlowy"]))
        p = probe(src)
        print(f"[{s['plik_zrodlowy']}] ← {s['slug']}.mp4 {p['w']}x{p['h']}@{p['fps']:.0f}")
    if brak:
        print(f"bez wyniku (montaż weźmie oryginał): {', '.join(brak)}")


def main(a: list[str]) -> None:
    if not a:
        sys.exit(__doc__)
    if a[0] == "--plik":
        sek = ulepsz_lokalnie(a[1], a[2])
        print(f"{a[1]} → {a[2]} ({sek:.0f} s)")
        return
    ep = a[0].upper()
    tor = a[a.index("--tor") + 1] if "--tor" in a else None
    baza = os.path.join(ROOT, "wyjscie", ep)
    klipy, hd = os.path.join(baza, "klipy"), os.path.join(baza, "klipy_hd")
    if "--przyjmij" in a:
        przyjmij(baza, a[a.index("--przyjmij") + 1])
        print(f"montaż: montaz_odcinka.py {ep} --hd")
        return
    if tor not in ("salad", "lokalny"):
        sys.exit("--tor salad | lokalny  (albo --przyjmij <katalog wyników ai-clip>)")
    if not os.path.isdir(klipy):
        sys.exit(f"brak {klipy}")
    pliki = do_ulepszenia(klipy, "--wszystkie" in a)
    if tor == "salad":
        zlecenie_salad(ep, baza, pliki)
        return
    os.makedirs(hd, exist_ok=True)
    for f in pliki:
        we, wy = os.path.join(klipy, f), os.path.join(hd, f)
        if os.path.exists(wy) and os.path.getmtime(wy) >= os.path.getmtime(we):
            print(f"[{f}] gotowe wcześniej"); continue
        print(f"[{f}] lokalnie {ulepsz_lokalnie(we, wy):.0f} s CPU")
    print(f"gotowe: {hd}  (montaż: montaz_odcinka.py {ep} --hd)")


if __name__ == "__main__":
    main(sys.argv[1:])
