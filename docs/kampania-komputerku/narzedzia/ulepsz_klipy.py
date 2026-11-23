#!/usr/bin/env python3
"""Ulepszanie klipów „w stylu DLSS”: AI super-rozdzielczość + generowanie klatek pośrednich.

DLSS (NVIDIA) działa w czasie rzeczywistym wewnątrz silnika gry (wektory ruchu, głębia z renderera),
więc do gotowych plików wideo się go nie podepnie. Ten sam efekt dla offline'owego wideo dają:
  * super-rozdzielczość:  SeedVR2 (ByteDance, Apache 2.0) - odpowiednik DLSS Super Resolution,
  * generowanie klatek:   RIFE 4.7 (MIT)                   - odpowiednik DLSS Frame Generation.

Wejście:  wyjscie/<EP>/klipy/*.mp4   (Wan 2.2: 480x832 @16 fps; HeyGen: 1080x1920 @25 fps)
Wyjście:  wyjscie/<EP>/klipy_hd/*.mp4 (1080x1920 @25 fps, audio skopiowane)
montaz_odcinka.py z flagą --hd bierze klipy z klipy_hd/, gdy tam są.

Tory:
  --tor gpu      ComfyUI na tym samym podzie co Wan (runpod_4090.sh instaluje węzły SeedVR2 i RIFE).
                 Najlepsza jakość: odtwarza fakturę tkanin, papieru, włosów.
  --tor lokalny  Bez GPU i za 0 USD: ffmpeg minterpolate (kompensacja ruchu) + lanczos + CAS.
                 Wyraźnie lepiej niż obecny `scale`, ale detali nie „dorysuje”.

Klipy, które już mają >= docelowej szerokości (awatary HeyGen), są pomijane: upscale twarzy
mówiącej grozi „pływaniem” rysów i ust, a te klipy są już w 1080p/25.

Użycie:
  ulepsz_klipy.py EP04 --tor lokalny
  ulepsz_klipy.py EP04 --tor gpu --comfy https://<pod>-8188.proxy.runpod.net [--usd-h 0.34]
  ulepsz_klipy.py EP04 --tor gpu --dry-run       # tylko zapisuje workflow JSON
  ulepsz_klipy.py --plik we.mp4 wy.mp4 --tor lokalny   # pojedynczy plik (test)
"""
import json
import os
import shutil
import subprocess
import sys
import time

TU = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(TU, ".."))
WORKFLOW = os.path.join(TU, "gpu", "seedvr2_rife_upscale.json")
W, H, FPS = 1080, 1920, 25


def probe(p: str) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,r_frame_rate", "-of", "json", p], capture_output=True, text=True).stdout
    s = (json.loads(out or "{}").get("streams") or [{}])[0]
    num, _, den = str(s.get("r_frame_rate", "0/1")).partition("/")
    fps = float(num) / float(den or 1) if float(den or 1) else 0.0
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
    """Łańcuch ffmpeg: klatki pośrednie (gdy fps < 25) → lanczos do 9:16 1080p → CAS (wyostrzanie adaptacyjne)."""
    kroki = ["hqdn3d=1.5:1.5:3:3"]          # lekki odszum: bez tego upscale wzmacnia szum kompresji Wan
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


# ---------- tor GPU (ComfyUI: SeedVR2 + RIFE) ----------
def workflow_gpu(nazwa_we: str, prefix: str, fps_we: float) -> dict:
    mnoznik = 2 if fps_we and fps_we < FPS - 0.5 else 1      # 16 → 32 fps; montaż zrzuca do 25
    podst = {"wideo": nazwa_we, "prefix": prefix, "rozdzielczosc": min(W, H), "mnoznik": mnoznik,
             "fps_wy": round((fps_we or FPS) * mnoznik, 3)}
    szablon = open(WORKFLOW, encoding="utf-8").read()
    for k, v in podst.items():
        szablon = szablon.replace(f'"{{{{{k}}}}}"', json.dumps(v))
    w = json.loads(szablon)
    w.pop("_opis", None)
    return w


def ulepsz_gpu(we: str, wy: str, comfy: str, prefix: str) -> float:
    sys.path.insert(0, os.path.join(TU, "gpu"))
    import klipy_batch as kb  # wspólne: upload, czekanie na /history, pobieranie wyników
    start = time.time()
    nazwa = kb.wyslij_obraz(comfy, we)               # /upload/image przyjmuje też mp4 (trafia do input/)
    w = workflow_gpu(nazwa, prefix, probe(we)["fps"])
    odp = json.loads(kb.http(f"{comfy}/prompt", json.dumps({"prompt": w}).encode(), {"Content-Type": "application/json"}))
    hist = kb.czekaj(comfy, odp["prompt_id"], limit_s=3600)
    tmp = os.path.join(os.path.dirname(wy), "_comfy")
    os.makedirs(tmp, exist_ok=True)
    pliki = [p for p in kb.pobierz_wyniki(comfy, hist, tmp) if p.endswith(".mp4")]
    if not pliki:
        sys.exit(f"ComfyUI nie zwrócił mp4 dla {prefix}")
    # dokończenie w ffmpeg: dokładnie 1080x1920@25 + oryginalne audio (ComfyUI gubi ścieżkę dźwięku)
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", pliki[0], "-i", we, "-map", "0:v",
           "-vf", f"fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},format=yuv420p",
           "-c:v", "libx264", "-preset", "slow", "-crf", "16"]
    cmd += ["-map", "1:a", "-c:a", "copy", "-shortest"] if ma_audio(we) else ["-an"]
    run(cmd + [wy])
    shutil.rmtree(tmp, ignore_errors=True)
    return time.time() - start


def main(a: list[str]) -> None:
    if not a:
        sys.exit(__doc__)
    tor, comfy, usd_h, dry, sila = "lokalny", None, 0.34, False, False
    i, poz = 0, []
    while i < len(a):
        if a[i] == "--tor":
            tor = a[i + 1]; i += 2
        elif a[i] == "--comfy":
            comfy = a[i + 1].rstrip("/"); i += 2
        elif a[i] == "--usd-h":
            usd_h = float(a[i + 1]); i += 2
        elif a[i] == "--dry-run":
            dry = True; i += 1
        elif a[i] == "--wszystkie":          # także klipy już w 1080p (np. wymuszenie na awatarach)
            sila = True; i += 1
        else:
            poz.append(a[i]); i += 1
    if tor not in ("lokalny", "gpu"):
        sys.exit("--tor lokalny | gpu")
    if tor == "gpu" and not dry and not comfy:
        sys.exit("tor gpu: podaj --comfy <url> albo --dry-run")

    if poz and poz[0] == "--plik" or (len(poz) == 2 and poz[0].endswith(".mp4")):
        we, wy = poz[-2], poz[-1]
        sek = ulepsz_lokalnie(we, wy) if tor == "lokalny" else ulepsz_gpu(we, wy, comfy, "test")
        print(f"{we} → {wy} ({sek:.0f} s)")
        return

    ep = poz[0].upper()
    baza = os.path.join(ROOT, "wyjscie", ep)
    klipy, hd = os.path.join(baza, "klipy"), os.path.join(baza, "klipy_hd")
    if not os.path.isdir(klipy):
        sys.exit(f"brak {klipy}")
    os.makedirs(hd, exist_ok=True)
    for f in sorted(os.listdir(klipy)):
        if not f.endswith(".mp4"):
            continue
        we, wy = os.path.join(klipy, f), os.path.join(hd, f)
        p = probe(we)
        if not sila and p["w"] >= W and p["fps"] >= FPS - 0.5:
            print(f"[{f}] {p['w']}x{p['h']}@{p['fps']:.0f} - już HD, pomijam")
            continue
        if dry:
            cel = os.path.join(hd, f.replace(".mp4", ".workflow.json"))
            json.dump(workflow_gpu(f, f"{ep}_{f[:-4]}_hd", p["fps"]), open(cel, "w", encoding="utf-8"), indent=1)
            print(f"[{f}] workflow → {cel}"); continue
        if os.path.exists(wy) and os.path.getmtime(wy) >= os.path.getmtime(we):
            print(f"[{f}] gotowe wcześniej"); continue
        if tor == "lokalny":
            sek = ulepsz_lokalnie(we, wy)
            print(f"[{f}] {p['w']}x{p['h']}@{p['fps']:.0f} → {W}x{H}@{FPS} lokalnie, {sek:.0f} s CPU")
        else:
            sek = ulepsz_gpu(we, wy, comfy, f"{ep}_{f[:-4]}_hd")
            usd = sek / 3600 * usd_h
            sys.path.insert(0, TU)
            import koszty_odcinka
            koszty_odcinka.log(ep, f"{f} seedvr2+rife {W}x{H}", f"{usd:.4f}", "gpu_4090")
            print(f"[{f}] SeedVR2+RIFE {sek:.0f} s GPU ≈ {usd:.4f} USD")
    print(f"gotowe: {hd}  (montaż: montaz_odcinka.py {ep} --hd)")


if __name__ == "__main__":
    main(sys.argv[1:])
