#!/usr/bin/env python3
"""Tor poprawek odcinka: od najtańszej metody w górę, z wersjonowaniem klipów i dziennikiem.

Metody (koszt jednego ujęcia):
  rozmyj    0 USD           rozmycie boksów tekstu (z kontrola.json: OCR, a gdy brak – boksy modelu z marginesem); drobne etykiety w tle
  kadruj    0 USD           pseudo-napisy przy dolnej krawędzi (częste w ujęciach mówiących): przycięcie kadru od dołu i skalowanie do 9:16
  dokument  0 USD           zamiana ujęcia na warstwę czytelną (dokumenty.py) – gdy widz ma coś PRZECZYTAĆ
  plansza   0 USD           plansza zastępcza (ostateczność, żeby montaż się domknął)
  klatka    0,03 + 0,21 USD nowa klatka startowa (Seedream 4 edit, prompt BEZ_TEKSTU) → QC klatki ZANIM zapłacimy za wideo → Kling 2.5 Turbo i2v 5 s
  awatar    0,056 USD/s     ponowne ujęcie mówiące (Kling AI Avatar v2 Std) z czystą klatką startową

Skrypt nie woła fal sam (klucz jest w konektorze fal / panelu fu): dla metod płatnych zapisuje gotowe zlecenia
wyjscie/EPxx/zlecenia/<id>_<metoda>.json (endpoint + input), a wynik przyjmuje przez `zapisz-klatke` / `zapisz-klip`.
Wersje: stary klip → klipy/archiwum/<nazwa>_vN.mp4; nowy pod prefiksem <id>_ (montaz_odcinka.py bierze aktualny).
Dziennik: wyjscie/EPxx/poprawki.log (data, ujęcie, metoda, powód, koszt).

Użycie:
  poprawki.py EP04 --auto                               zalecenia z kontrola.json: metody 0 USD wykonuje, płatne → zlecenia
  poprawki.py EP04 u1 rozmyj "etykieta na teczce"
  poprawki.py EP04 u9 dokument "dokument nie po polsku" [--szablon porownanie_kw]
  poprawki.py EP04 u2 klatka "bełkot na wydrukach"          → zlecenia/u2_klatka.json
  poprawki.py EP04 u2 zapisz-klatke <url|plik>              → QC klatki → zlecenia/u2_i2v.json (albo odrzucenie)
  poprawki.py EP04 u2 zapisz-klip <url|plik> [--tag broll]  → archiwum + nowy klip + QC klipu
  poprawki.py EP04 u16 awatar "zniekształcona dłoń"         → zlecenia/u16_awatar.json
Po poprawkach: montaz_odcinka.py EP04 (0 USD).
"""
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request

TU = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(TU, ".."))
sys.path.insert(0, TU)
import dokumenty  # noqa: E402

BEZ_TEKSTU = ("Absolutely no writing, letters, numbers, logos, labels, stamps or printed text anywhere in the image; "
              "every paper, folder, screen and book spine is blank, face down, closed or out of focus.")
NEGATYW_WIDEO = ("text, letters, words, numbers, captions, subtitles, watermark, logo, typography, signage, handwriting, "
                 "blur, distort, low quality, extra fingers, deformed hands")
ENDPOINTY = {"klatka": "fal-ai/bytedance/seedream/v4/edit",
             "i2v": "fal-ai/kling-video/v2.5-turbo/standard/image-to-video",
             "awatar": "fal-ai/kling-video/ai-avatar/v2/standard"}
REPO_RAW = "https://raw.githubusercontent.com/plnyspolka-pixel/notarai/{galaz}/docs/kampania-komputerku/{rel}"
KOSZT = {"klatka": 0.03, "i2v_5s": 0.21, "awatar_s": 0.056}


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"błąd {cmd[0]}: {r.stderr[-800:]}")
    return r.stdout


def galaz():
    try:
        return subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip() or "master"
    except Exception:
        return "master"


def raw_url(rel):
    return REPO_RAW.format(galaz=galaz(), rel=rel)


def wymiary(p):
    out = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", p]).strip()
    w, h = out.split(",")[:2]
    return int(w), int(h)


def czas(p):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]).strip()
    return float(out) if out else 0.0


def wczytaj(ep):
    odc = json.load(open(os.path.join(ROOT, "odcinki", f"{ep}.json"), encoding="utf-8"))
    baza = os.path.join(ROOT, "wyjscie", ep)
    rp = os.path.join(baza, "kontrola.json")
    raport = json.load(open(rp, encoding="utf-8")) if os.path.exists(rp) else {}
    for d in ("klipy", "plansze", "zlecenia", "tmp", os.path.join("klipy", "archiwum")):
        os.makedirs(os.path.join(baza, d), exist_ok=True)
    return odc, baza, raport


def zapisz_odcinek(ep, odc):
    json.dump(odc, open(os.path.join(ROOT, "odcinki", f"{ep}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def zapisz_raport(baza, raport):
    json.dump(raport, open(os.path.join(baza, "kontrola.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def log(baza, uid, metoda, powod, koszt=0.0, info=""):
    with open(os.path.join(baza, "poprawki.log"), "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M}\t{uid}\t{metoda}\t{koszt:.2f} USD\t{powod}\t{info}\n")


def klipy_ujecia(klipy, uid):
    return sorted(os.path.join(klipy, f) for f in os.listdir(klipy) if f.startswith(uid + "_") and f.endswith(".mp4"))


def archiwizuj(klipy, uid):
    arch = os.path.join(klipy, "archiwum"); os.makedirs(arch, exist_ok=True)
    przeniesione = []
    for p in klipy_ujecia(klipy, uid):
        baza = os.path.splitext(os.path.basename(p))[0]
        n = 1 + len([f for f in os.listdir(arch) if f.startswith(baza + "_v")])
        cel = os.path.join(arch, f"{baza}_v{n}.mp4")
        shutil.move(p, cel); przeniesione.append(os.path.basename(cel))
    return przeniesione


def pobierz(zrodlo, cel):
    if re.match(r"https?://", zrodlo):
        with urllib.request.urlopen(zrodlo, timeout=120) as r, open(cel, "wb") as f:
            shutil.copyfileobj(r, f)
    else:
        shutil.copy(zrodlo, cel)
    return cel


def ujecie(odc, uid):
    for u in odc["ujecia"]:
        if u["id"] == uid:
            return u
    sys.exit(f"brak ujęcia {uid} w odcinku")


# ------------------------------------------------------------------ metody 0 USD

def boksy_do_rozmycia(wpis):
    """Boksy tekstu [x0,y0,x1,y1] w ułamkach; OCR jest dokładny (+2 %), boksy modelu są orientacyjne (+8 %)."""
    boksy = []
    for p in wpis.get("problemy", []):
        if p.get("typ") != "tekst" or not p.get("boks_proc") or not any(p["boks_proc"]):
            continue
        b, m = p["boks_proc"], (0.02 if p.get("zrodlo") == "ocr" else 0.08)
        boksy.append([max(0, b[0] / 100 - m), max(0, b[1] / 100 - m), min(1, b[2] / 100 + m), min(1, b[3] / 100 + m)])
    return boksy


def rozmyj(ep, odc, u, baza, raport, powod):
    uid, klipy = u["id"], os.path.join(baza, "klipy")
    src = klipy_ujecia(klipy, uid)
    if not src:
        return print(f"{uid}: brak klipu do rozmycia")
    src = src[0]
    boksy = boksy_do_rozmycia(raport.get(uid, {}))
    if not boksy:
        return print(f"{uid}: kontrola.json nie ma boksów tekstu – najpierw kontrola_ujec.py")
    W, H = wymiary(src)
    czesci, prev = [], "[0:v]"
    for i, b in enumerate(boksy):
        x, y = int(b[0] * W), int(b[1] * H)
        w, h = max(8, int((b[2] - b[0]) * W)), max(8, int((b[3] - b[1]) * H))
        w, h = min(w, W - x) // 2 * 2, min(h, H - y) // 2 * 2
        czesci.append(f"{prev}split=2[a{i}][b{i}];[b{i}]crop={w}:{h}:{x}:{y},"
                      f"boxblur=luma_radius=18:luma_power=3:chroma_radius=10:chroma_power=2[r{i}];[a{i}][r{i}]overlay={x}:{y}[v{i}]")
        prev = f"[v{i}]"
    tmp = os.path.join(baza, "tmp", f"{uid}_rozmyty.mp4")
    run(["ffmpeg", "-y", "-v", "error", "-i", src, "-filter_complex", ";".join(czesci), "-map", prev, "-map", "0:a?",
         "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-c:a", "copy", tmp])
    nazwa = os.path.basename(src)
    arch = archiwizuj(klipy, uid)
    shutil.move(tmp, os.path.join(klipy, nazwa))
    log(baza, uid, "rozmyj", powod, 0.0, f"{len(boksy)} boksów; stary → {', '.join(arch)}")
    print(f"{uid}: rozmyto {len(boksy)} boksów → klipy/{nazwa} (stary w archiwum)")


def kadruj(ep, odc, u, baza, raport, powod):
    """Tekst przy dolnej krawędzi: przycinamy kadr tak, żeby boks wypadł poza obraz, i skalujemy z powrotem do 9:16."""
    uid, klipy = u["id"], os.path.join(baza, "klipy")
    src = klipy_ujecia(klipy, uid)
    if not src:
        return print(f"{uid}: brak klipu")
    src = src[0]
    boksy = [p["boks_proc"] for p in raport.get(uid, {}).get("problemy", []) if p.get("typ") == "tekst" and p.get("boks_proc") and any(p["boks_proc"])]
    if not boksy:
        return print(f"{uid}: brak boksów tekstu w kontrola.json")
    y0 = min(b[1] for b in boksy) / 100
    if y0 < 0.6:
        return print(f"{uid}: tekst nie przy dolnej krawędzi (y0={y0:.2f}) – użyj rozmyj albo awatar")
    W, H = wymiary(src)
    nh = int(y0 * H) - 12; nh -= nh % 2
    nw = int(nh * W / H); nw -= nw % 2
    x = (W - nw) // 2
    tmp = os.path.join(baza, "tmp", f"{uid}_kadr.mp4")
    run(["ffmpeg", "-y", "-v", "error", "-i", src, "-vf", f"crop={nw}:{nh}:{x}:0,scale={W}:{H}:flags=lanczos",
         "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-c:a", "copy", tmp])
    nazwa = os.path.basename(src)
    arch = archiwizuj(klipy, uid)
    shutil.move(tmp, os.path.join(klipy, nazwa))
    log(baza, uid, "kadruj", powod, 0.0, f"zoom ×{H / nh:.2f}; stary → {', '.join(arch)}")
    print(f"{uid}: przycięto dolne {100 - y0 * 100:.0f} % kadru (zoom ×{H / nh:.2f}) → klipy/{nazwa}")


def dokument(ep, odc, u, baza, raport, powod, szablon=None, dane=None):
    uid = u["id"]
    if u["typ"] != "dokument":
        u["poprzednio"] = {k: u.get(k) for k in ("typ", "kadr", "kamera", "klatka_startowa", "prompt_delta") if k in u}
        u["typ"] = "dokument"
    opis = " ".join(str(u.get("poprzednio", {}).get(k, "")) for k in ("klatka_startowa", "prompt_delta"))
    u["szablon"] = szablon or u.get("szablon") or ("notatka" if re.search(r"notatk|kartk|karteczk|note", opis, re.I) else "porownanie_kw")
    if dane:
        u["dane"] = dane
    u.setdefault("czas_s", 5)
    png, meta = dokumenty.renderuj(ep, u, baza)
    arch = archiwizuj(os.path.join(baza, "klipy"), uid)
    zapisz_odcinek(ep, odc)
    log(baza, uid, "dokument", powod, 0.0, f"szablon {u['szablon']}; stary klip → {', '.join(arch) or 'brak'}")
    print(f"{uid}: warstwa czytelna {u['szablon']} → {os.path.relpath(png, ROOT)} {json.dumps(meta)}")


def plansza(ep, odc, u, baza, raport, powod):
    uid = u["id"]
    p = os.path.join(baza, "plansze", f"{uid}_ekran.png")
    dokumenty.plansza_ekranu(uid, u.get("co_widac") or u.get("klatka_startowa") or u.get("kwestia", ""), float(u.get("czas_s") or 5), p)
    u["poprzednio"] = {"typ": u["typ"]}; u["typ"] = "ekran"
    archiwizuj(os.path.join(baza, "klipy"), uid); zapisz_odcinek(ep, odc)
    log(baza, uid, "plansza", powod); print(f"{uid}: plansza zastępcza → {p}")


# ------------------------------------------------------------------ metody płatne (zlecenia)

def zapisz_zlecenie(baza, uid, metoda, zlecenie):
    p = os.path.join(baza, "zlecenia", f"{uid}_{metoda}.json")
    json.dump(zlecenie, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{uid}: zlecenie {metoda} ({zlecenie.get('koszt_usd', 0):.2f} USD) → {os.path.relpath(p, ROOT)}")
    return p


def prompt_klatki(u):
    dozw = str(u.get("dozwolony_tekst") or "")
    p = (f"Keep this exact room, furniture, light and camera angle of the reference. {u.get('prompt_delta', '').rstrip('.')}. "
         f"{BEZ_TEKSTU}")
    if dozw:
        p += f' The only text allowed anywhere is exactly "{dozw}", written small and clearly, nothing else.'
    return p + " Natural daylight, photorealistic, vertical 9:16 composition."


def zlecenie_klatka(ep, odc, u, baza, raport, powod):
    kamera = u.get("kamera") or "K9"
    z = {"ujecie": u["id"], "metoda": "klatka", "endpoint_id": ENDPOINTY["klatka"], "koszt_usd": KOSZT["klatka"],
         "input": {"prompt": prompt_klatki(u), "image_urls": [raw_url(f"pakiet/09_scenografia_v2/plansze/{kamera}.jpg")],
                   "image_size": {"width": 1080, "height": 1920}, "num_images": 1, "enhance_prompt_mode": "standard"},
         "nastepnie": f"poprawki.py {ep} {u['id']} zapisz-klatke <url wyniku>", "powod": powod}
    zapisz_zlecenie(baza, u["id"], "klatka", z)


def zapisz_klatke(ep, odc, u, baza, raport, zrodlo):
    import kontrola_ujec as kontrola
    uid = u["id"]
    n = 1 + len([f for f in os.listdir(os.path.join(baza, "plansze")) if f.startswith(f"{uid}_klatka_v")])
    cel = pobierz(zrodlo, os.path.join(baza, "plansze", f"{uid}_klatka_v{n}.jpg"))
    wpis, usd = kontrola.sprawdz_plik(kontrola.klient(), "sonnet", cel, u, 1, os.path.join(baza, "tmp"))
    raport[f"{uid}_klatka_v{n}"] = wpis; zapisz_raport(baza, raport)
    kontrola.zapisz_koszt(ep, f"Kontrola klatki {uid} v{n}", usd, "bedrock")
    log(baza, uid, "zapisz-klatke", f"QC: {wpis['werdykt']}", KOSZT["klatka"], os.path.basename(cel))
    if wpis["werdykt"] != "ok":
        print(f"{uid}: klatka v{n} ODRZUCONA ({wpis['werdykt']}): " + "; ".join(p["opis"] for p in wpis["problemy"][:4]))
        return print("   → nowa klatka (inny seed) tym samym zleceniem; wideo nie zamawiamy.")
    dozw = str(u.get("dozwolony_tekst") or "")
    prompt = (f"{u.get('prompt_delta', '').rstrip('.')}. Static camera with a very slow push-in; subtle natural light; "
              f"nothing new appears and every paper stays blank" + (f'; the note keeps reading exactly "{dozw}"' if dozw else "") + ".")
    z = {"ujecie": uid, "metoda": "i2v", "endpoint_id": ENDPOINTY["i2v"], "koszt_usd": KOSZT["i2v_5s"],
         "input": {"prompt": prompt, "image_url": zrodlo if re.match(r"https?://", zrodlo) else f"UPLOAD:{cel}",
                   "duration": "5", "negative_prompt": NEGATYW_WIDEO, "cfg_scale": 0.5},
         "nastepnie": f"poprawki.py {ep} {uid} zapisz-klip <url wideo> --tag broll"}
    print(f"{uid}: klatka v{n} OK ({usd:.3f} USD kontroli)")
    zapisz_zlecenie(baza, uid, "i2v", z)


def zapisz_klip(ep, odc, u, baza, raport, zrodlo, tag):
    import kontrola_ujec as kontrola
    uid, klipy = u["id"], os.path.join(baza, "klipy")
    tmp = pobierz(zrodlo, os.path.join(baza, "tmp", f"{uid}_{tag}_nowy.mp4"))
    arch = archiwizuj(klipy, uid)
    cel = os.path.join(klipy, f"{uid}_{tag}.mp4"); shutil.move(tmp, cel)
    ile = 2 if czas(cel) <= 5.5 else 3
    wpis, usd = kontrola.sprawdz_plik(kontrola.klient(), "sonnet", cel, u, ile, os.path.join(baza, "tmp"))
    raport[uid] = wpis; zapisz_raport(baza, raport)
    kontrola.zapisz_koszt(ep, f"Kontrola klipu {uid} ({tag})", usd, "bedrock")
    koszt = KOSZT["awatar_s"] * czas(cel) if tag == "avatar" else KOSZT["i2v_5s"]
    log(baza, uid, "zapisz-klip", f"QC: {wpis['werdykt']}", koszt, f"{os.path.basename(cel)}; stary → {', '.join(arch) or 'brak'}")
    print(f"{uid}: nowy klip {os.path.basename(cel)} – QC {wpis['werdykt']}" +
          ("" if wpis["werdykt"] == "ok" else ": " + "; ".join(p["opis"] for p in wpis["problemy"][:4])))


def zlecenie_awatar(ep, odc, u, baza, raport, powod):
    uid = u["id"]
    kadr = u.get("klatka_startowa", "")
    obraz = raw_url(f"pakiet/10_obsada_v2/postacie/{u.get('postac')}/{os.path.basename(kadr)}") if kadr and not kadr.startswith("DO_") else "UPLOAD:<czysta klatka startowa bez etykiet>"
    audio = f"UPLOAD:{os.path.relpath(os.path.join(baza, 'audio', f'{ep.lower()}_{uid}.mp3'), ROOT)}"
    z = {"ujecie": uid, "metoda": "awatar", "endpoint_id": ENDPOINTY["awatar"],
         "koszt_usd": round(KOSZT["awatar_s"] * float(u.get("czas_s") or 5), 2),
         "input": {"image_url": obraz, "audio_url": audio,
                   "prompt": f"{u.get('prompt_delta', '').rstrip('.')}. {BEZ_TEKSTU} Natural speaking gestures, steady framing."},
         "nastepnie": f"poprawki.py {ep} {uid} zapisz-klip <url wideo> --tag avatar", "powod": powod}
    zapisz_zlecenie(baza, uid, "awatar", z)


METODY = {"rozmyj": rozmyj, "kadruj": kadruj, "dokument": dokument, "plansza": plansza, "klatka": zlecenie_klatka, "awatar": zlecenie_awatar}


def auto(ep, odc, baza, raport):
    print(f"{'ujęcie':7}{'metoda':10}{'koszt':8}dlaczego")
    for uid, wpis in raport.items():
        if "_klatka_v" in uid:
            continue
        z = wpis.get("zalecenie") or {}
        m = z.get("metoda", "brak")
        print(f"{uid:7}{m:10}{z.get('koszt_usd', 0):<8.2f}{z.get('dlaczego', '')}")
        if m in METODY:
            METODY[m](ep, odc, ujecie(odc, uid), baza, raport, z.get("dlaczego", "wg kontroli"))


def main(a):
    if len(a) < 2:
        sys.exit(__doc__)
    ep = a[0].upper()
    odc, baza, raport = wczytaj(ep)
    if a[1] == "--auto":
        return auto(ep, odc, baza, raport)
    uid, metoda = a[1], a[2]
    reszta = [x for x in a[3:] if not x.startswith("--")]
    opcje = {a[i].lstrip("-"): a[i + 1] for i in range(3, len(a) - 1) if a[i].startswith("--")}
    u = ujecie(odc, uid)
    if metoda == "zapisz-klatke":
        return zapisz_klatke(ep, odc, u, baza, raport, reszta[0])
    if metoda == "zapisz-klip":
        return zapisz_klip(ep, odc, u, baza, raport, reszta[0], opcje.get("tag", "broll"))
    if metoda == "dokument":
        return dokument(ep, odc, u, baza, raport, reszta[0] if reszta else "ręcznie", opcje.get("szablon"))
    if metoda not in METODY:
        sys.exit(f"nieznana metoda {metoda}; dostępne: {', '.join(METODY)}, zapisz-klatke, zapisz-klip")
    METODY[metoda](ep, odc, u, baza, raport, reszta[0] if reszta else "ręcznie")


if __name__ == "__main__":
    main(sys.argv[1:])
