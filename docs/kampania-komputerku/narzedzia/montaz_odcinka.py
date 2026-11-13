#!/usr/bin/env python3
"""Montaż szkicu odcinka z gotowych klipów: odcinki/EPxx.json + wyjscie/EPxx/{klipy,plansze} → wyjscie/EPxx/EPxx_szkic.mp4

Dla każdego ujęcia z JSON szuka pliku:
  mowiace  → klipy/<id>_*.mp4 (awatar; czas = długość klipu)
  bez_mowy → klipy/<id>_*.mp4 (przebitka; przycięta do czas_s)
  ekran    → plansze/<id>_ekran.png (czas_s; plansza zastępcza, UI nie generujemy)
  plansza  → plansze/<id>_outro.png (czas_s)
Brak pliku → plansza „ujęcie w produkcji" (żeby dało się montować częściowo).
Wszystko do 1080x1920 @25 fps, AAC 48 kHz; napisy z `kwestia` wypalane na ujęciach mówiących
(DejaVu Sans Bold – na stanowisku montażowym podmienić na Montserrat); ambience z glosy_v2 pod
całością (-24 dB), na końcu loudnorm I=-16 TP=-1.5 (format social, jak w glosy.md).

Użycie: montaz_odcinka.py EP04 [--bez-ambience] [--szer 1080 --wys 1920]
Wymaga ffmpeg z libfreetype (drawtext). Nie woła żadnego API.
"""
import json
import os
import shutil
import subprocess
import sys
import textwrap

TU = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(TU, ".."))
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
AMBIENCE = os.path.join(ROOT, "glosy_v2", "zrodla", "ambience_kancelaria_22s.mp3")
W, H, FPS = 1080, 1920, 25


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"ffmpeg błąd:\n{' '.join(cmd)}\n{r.stderr[-1500:]}")


def dlugosc(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                         capture_output=True, text=True).stdout.strip()
    return float(out) if out else 0.0


def znajdz(katalog, prefix, roz):
    if not os.path.isdir(katalog):
        return None
    k = sorted(f for f in os.listdir(katalog) if f.startswith(prefix + "_") and f.endswith(roz))
    return os.path.join(katalog, k[0]) if k else None


def plansza_brak(sciezka, uid, opis):
    from PIL import Image, ImageDraw, ImageFont
    im = Image.new("RGB", (W, H), (7, 29, 73)); dr = ImageDraw.Draw(im)
    dr.text((120, 860), f"{uid} – ujęcie w produkcji", font=ImageFont.truetype(FONT, 44), fill=(0, 207, 255))
    y = 940
    for ln in textwrap.wrap(opis or "", 44)[:5]:
        dr.text((120, y), ln, font=ImageFont.truetype(FONT, 30), fill=(220, 225, 240)); y += 44
    im.save(sciezka)


def napis_filtr(tekst, plik_txt):
    linie = textwrap.wrap(tekst, 30)[:4]   # 30 znakow DejaVu Bold 46 px miesci sie w 1080 px z marginesem
    open(plik_txt, "w", encoding="utf-8").write("\n".join(linie))
    return (f"drawtext=fontfile={FONT}:textfile='{plik_txt}':fontsize=46:fontcolor=white:line_spacing=12:"
            f"box=1:boxcolor=0x071D49@0.72:boxborderw=22:x=(w-text_w)/2:y=h-400-text_h")


def segment(wejscie, wyjscie, czas, obraz, napis_txt=None):
    """Jeden znormalizowany segment mp4 (wideo 1080x1920@25, audio stereo 48k; obraz → cisza)."""
    skala = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},format=yuv420p")
    vf = skala + (("," + napis_txt) if napis_txt else "")
    if obraz:
        cmd = ["ffmpeg", "-y", "-loop", "1", "-t", f"{czas:.3f}", "-i", wejscie,
               "-f", "lavfi", "-t", f"{czas:.3f}", "-i", "anullsrc=r=48000:cl=stereo",
               "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "128k",
               "-shortest", wyjscie]
    else:
        cmd = ["ffmpeg", "-y", "-i", wejscie, "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
               "-filter_complex", f"[0:v]{vf}[v];[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=0,aresample=48000[a]",
               "-map", "[v]", "-map", "[a]", "-t", f"{czas:.3f}",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "128k", wyjscie]
        # klip bez ścieżki audio (przebitki): amix padnie - wtedy sama cisza
        if not ma_audio(wejscie):
            cmd = ["ffmpeg", "-y", "-i", wejscie, "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                   "-vf", vf, "-map", "0:v", "-map", "1:a", "-t", f"{czas:.3f}",
                   "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "128k", wyjscie]
    run(cmd)


def ma_audio(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type",
                          "-of", "csv=p=0", p], capture_output=True, text=True).stdout
    return "audio" in out


def main(a):
    if not a:
        sys.exit(__doc__)
    ep = a[0].upper()
    ambience = "--bez-ambience" not in a
    odc = json.load(open(os.path.join(ROOT, "odcinki", f"{ep}.json"), encoding="utf-8"))
    baza = os.path.join(ROOT, "wyjscie", ep)
    klipy, plansze, tmp = (os.path.join(baza, d) for d in ("klipy", "plansze", "tmp"))
    os.makedirs(tmp, exist_ok=True)
    segmenty, raport = [], []
    for i, u in enumerate(odc["ujecia"]):
        uid, typ = u["id"], u["typ"]
        cel = os.path.join(tmp, f"{i:02d}_{uid}.mp4")
        czas_plan = float(u.get("czas_s") or 5)
        if typ == "mowiace":
            src = znajdz(klipy, uid, ".mp4")
            if src:
                czas = dlugosc(src) + 0.25
                segment(src, cel, czas, False, napis_filtr(u.get("kwestia", ""), os.path.join(tmp, f"{uid}.txt")))
                raport.append((uid, typ, f"{czas:.1f}s", os.path.basename(src)))
            else:
                p = os.path.join(tmp, f"{uid}_brak.png"); plansza_brak(p, uid, u.get("kwestia", ""))
                segment(p, cel, czas_plan, True, napis_filtr(u.get("kwestia", ""), os.path.join(tmp, f"{uid}.txt")))
                raport.append((uid, typ, f"{czas_plan:.1f}s", "BRAK → plansza"))
        elif typ == "bez_mowy":
            src = znajdz(klipy, uid, ".mp4")
            if src:
                segment(src, cel, min(czas_plan, dlugosc(src)), False)
                raport.append((uid, typ, f"{min(czas_plan, dlugosc(src)):.1f}s", os.path.basename(src)))
            else:
                p = os.path.join(tmp, f"{uid}_brak.png"); plansza_brak(p, uid, u.get("prompt_delta", ""))
                segment(p, cel, czas_plan, True); raport.append((uid, typ, f"{czas_plan:.1f}s", "BRAK → plansza"))
        elif typ == "ekran":
            src = os.path.join(plansze, f"{uid}_ekran.png")
            if not os.path.exists(src):
                src = os.path.join(tmp, f"{uid}_brak.png"); plansza_brak(src, uid, u.get("co_widac", ""))
            segment(src, cel, czas_plan, True); raport.append((uid, typ, f"{czas_plan:.1f}s", os.path.basename(src)))
        else:  # plansza
            src = os.path.join(plansze, f"{uid}_outro.png")
            if not os.path.exists(src):
                src = os.path.join(ROOT, "pakiet", "03_plansze_video", "9x16", "OUTRO_komputerku.png")
            segment(src, cel, czas_plan, True); raport.append((uid, typ, f"{czas_plan:.1f}s", os.path.basename(src)))
        segmenty.append(cel)
    lista = os.path.join(tmp, "lista.txt")
    open(lista, "w").write("".join(f"file '{s}'\n" for s in segmenty))
    sklejka = os.path.join(tmp, "sklejka.mp4")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lista, "-c", "copy", sklejka])
    wynik = os.path.join(baza, f"{ep}_szkic.mp4")
    if ambience and os.path.exists(AMBIENCE):
        run(["ffmpeg", "-y", "-i", sklejka, "-stream_loop", "-1", "-i", AMBIENCE,
             "-filter_complex", "[1:a]volume=-24dB[amb];[0:a][amb]amix=inputs=2:duration=first:dropout_transition=0,"
                                "loudnorm=I=-16:TP=-1.5:LRA=11[a]",
             "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", wynik])
    else:
        run(["ffmpeg", "-y", "-i", sklejka, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:v", "copy", "-c:a", "aac", wynik])
    print(f"{'ujęcie':6} {'typ':9} {'czas':7} źródło")
    for r in raport:
        print(f"{r[0]:6} {r[1]:9} {r[2]:7} {r[3]}")
    print(f"\n{wynik}: {dlugosc(wynik):.1f} s, {os.path.getsize(wynik)/1e6:.1f} MB")


if __name__ == "__main__":
    main(sys.argv[1:])
