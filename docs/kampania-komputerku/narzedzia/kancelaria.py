#!/usr/bin/env python3
"""Kancelaria serii „Komputerku…” — powtarzalna scenografia i wprowadzanie postaci.

Źródła prawdy:
  pakiet/09_scenografia_v2/scenografia.json   pokój, materiały, światło, kamery K1..K9
  pakiet/10_obsada_v2/postacie/<slug>/postac.json   jedna postać

Skrypt NIE woła API sam (klucze są w konektorach fal / panelu fu). Składa
deterministyczne zlecenia (JSON) z tych samych klocków, a wyniki zapisuje
z powrotem do plików. Ten sam plik wejściowy = to samo zlecenie.

Polecenia:
  plan [--kamera K3] [-o plik.png]        plan z góry (wszystkie kamery albo jedna podświetlona)
  zlecenie plansza <K1..K9|materialy>     JSON dla fal-ai/nano-banana-pro/edit
  zlecenie postac <slug> <ref|arkusz|kadr:K2>
  zapisz plansza <id> <url>               pobiera obraz do repo i wpisuje fal_url
  zapisz postac <slug> <ref|arkusz|kadr:K2> <url>
  zapisz plan <K> <url>                   fal_url wgranego planu kamery
  nowa-postac <slug>                      szablon postac.json do wypełnienia
  podglad [plansze|postacie]              arkusz kontrolny JPG
  heygen <slug>                           body: utworzenie photo avatara + render ujęcia
  status                                  co jest gotowe, co brakuje
"""
import json, math, os, sys, urllib.request, io

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCENO_DIR = os.path.join(ROOT, "pakiet", "09_scenografia_v2")
SCENO = os.path.join(SCENO_DIR, "scenografia.json")
OBSADA_DIR = os.path.join(ROOT, "pakiet", "10_obsada_v2")
POSTACIE = os.path.join(OBSADA_DIR, "postacie")
ENDPOINT = "fal-ai/nano-banana-pro/edit"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save(p, d):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
        f.write("\n")


def kam(s, kid):
    for k in s["kamery"]:
        if k["id"] == kid:
            return k
    sys.exit(f"brak kamery {kid}")


def postac_path(slug):
    return os.path.join(POSTACIE, slug, "postac.json")


# ---------------------------------------------------------------- plan
def plan(kamera=None, out=None):
    from PIL import Image, ImageDraw, ImageFont
    s = load(SCENO)
    W, D = s["pokoj"]["szerokosc_cm"], s["pokoj"]["glebokosc_cm"]
    sc, m = 2.0, 120
    img = Image.new("RGBA", (int(W * sc + 2 * m), int(D * sc + 2 * m + 60)), "#F5F7FC")
    d = ImageDraw.Draw(img)
    f, fb, fs = ImageFont.truetype(FONT, 18), ImageFont.truetype(FONT_B, 26), ImageFont.truetype(FONT, 15)
    X = lambda x: m + x * sc
    Y = lambda y: m + (D - y) * sc
    d.text((m, 30), f"{s['wersja']} — plan z góry (północ u góry)" + (f" — kamera {kamera}" if kamera else ""), fill="#071D49", font=fb)
    d.rectangle([X(0), Y(D), X(W), Y(0)], fill="white", outline="#0D193C", width=6)
    for z in sorted(s["strefy"], key=lambda z: z["id"] != "dywan"):
        x0, y0, x1, y1 = z["rect"]
        d.rectangle([X(x0), Y(y1), X(x1), Y(y0)], fill=z["kolor"], outline="#C9D6EA" if z["id"] == "dywan" else "#2B52D9", width=2)
    for z in s["strefy"]:
        x0, y0, x1, y1 = z["rect"]
        if z["id"] in ("dywan",):
            continue
        cx, cy = (X(x0) + X(x1)) / 2, (Y(y0) + Y(y1)) / 2
        txt = z["nazwa"]
        if z["id"] == "okna":
            d.text((X(x1) + 8, cy), "OKNA", fill="#071D49", font=f, anchor="lm")
            continue
        if z["id"] == "biblioteka":
            d.text((X(x0) - 8, cy), "BIBLIOTEKA", fill="#071D49", font=f, anchor="rm")
            continue
        d.text((cx, cy), txt if len(txt) < 26 else txt.split(":")[0], fill="#071D49", font=fs, anchor="mm")
    d.text((X(W / 2), Y(D) - 14), "N  (ściana z obrazem, drzwi w narożniku NW)", fill="#647392", font=fs, anchor="ms")
    d.text((X(W / 2), Y(0) + 30), "S", fill="#647392", font=fs, anchor="ms")
    over = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(over)
    for k in s["kamery"]:
        if kamera and k["id"] != kamera:
            continue
        x, y = k["pozycja"]
        az = math.radians(k["azymut"])
        fov = 2 * math.atan(12 / k["obiektyw_mm"])  # pion 9:16: krótszy bok matrycy FF
        L = 260 if kamera else 110
        pts = [(X(x), Y(y))]
        for a in (az - fov / 2, az + fov / 2):
            pts.append((X(x + L * math.sin(a)), Y(y + L * math.cos(a))))
        col = "#1C1CC0" if kamera else "#2B52D9"
        od.polygon(pts, fill=(43, 82, 217, 45) if not kamera else (28, 28, 192, 80), outline=col, width=3)
        od.ellipse([X(x) - 9, Y(y) - 9, X(x) + 9, Y(y) + 9], fill=col)
        od.text((X(x) + 12, Y(y) + 10), f"{k['id']} {k['obiektyw_mm']}mm", fill=col, font=fb if kamera else f)
    img = Image.alpha_composite(img, over).convert("RGB")
    d = ImageDraw.Draw(img)
    d.text((m, img.height - 40), "Schemat scenograficzny (cm). Źródło: scenografia.json, rysuje narzedzia/kancelaria.py", fill="#647392", font=fs)
    out = out or os.path.join(SCENO_DIR, f"plan{('_' + kamera) if kamera else ''}.png")
    img.save(out)
    print(out)


# ---------------------------------------------------------------- prompty
def blok(s, *names):
    return " ".join(s["bloki_promptu"][n] for n in names)


def url_planszy(s, pid):
    p = s["plansze"].get(pid)
    if not p or not p.get("fal_url"):
        sys.exit(f"plansza {pid} nie ma jeszcze fal_url (najpierw wygeneruj i zapisz)")
    return p["fal_url"]


def zlecenie_plansza(pid):
    s = load(SCENO)
    styl_ref = s.get("referencja_stylu_fal_url")
    if pid == "K1":
        k = kam(s, "K1")
        plan_url = s["plan_fal_url"].get("K1")
        if not plan_url:
            sys.exit("brak plan_fal_url.K1 (kancelaria.py plan --kamera K1, wgraj, zapisz plan K1 <url>)")
        prompt = (
            "Image 1 is ONLY a mood and photographic-quality reference for a warm Polish notary office; do NOT copy its layout, furniture or people. "
            "Image 2 is the floor plan of the room seen from above (north at the top) with the camera position and its field of view marked in dark blue; compose the photograph exactly from that camera. "
            f"Shot: {k['widac']} Vertical 9:16, {k['obiektyw_mm']}mm lens, camera height {k['wysokosc_cm']} cm, level horizon, straight verticals. "
            f"The room: {blok(s, 'pokoj', 'materialy', 'swiatlo')} Empty room, no people. {blok(s, 'styl', 'negatyw')} Do not draw the plan, labels or arrows."
        )
        refs = [styl_ref, plan_url]
    elif pid == "materialy":
        prompt = (
            "Create a clean product-style material reference board, 16:9, of the furniture and materials of the office in image 1, "
            "photographed on a plain warm light-grey studio background in a tidy 4 x 2 grid with even soft light: "
            "(1) corner of the dark-walnut executive desk with panelled front and leather desk pad, (2) cognac leather high-back chair, "
            "(3) cream upholstered visitor chair with walnut legs, (4) satin-brass dome desk lamp, (5) satin-brass wall sconce, "
            "(6) section of a black steel-framed window with small panes and a sheer off-white linen curtain, "
            "(7) square sample of honey-oak herringbone parquet with a corner of the navy-and-cream wool rug, "
            "(8) grey multifunction office printer standing on a low dark-walnut sideboard. "
            f"Every object must match image 1 exactly in colour, wood tone and finish. {blok(s, 'materialy')} No text, no labels, no numbers, no logos."
        )
        refs = [url_planszy(s, "K1")]
    else:
        k = kam(s, pid)
        plan_url = s["plan_fal_url"].get(pid)
        if not plan_url:
            sys.exit(f"brak plan_fal_url.{pid}")
        prompt = (
            "Image 1 is the approved master wide shot of THE office; image 2 is the material reference board of its furniture and finishes; "
            "image 3 is the floor plan seen from above (north at the top) with the camera for THIS shot marked in dark blue. "
            "Generate a new photograph of the SAME room from the camera marked in image 3. Architecture, furniture, materials, colours, window shape and light must be identical to images 1 and 2. "
            f"Shot: {k['widac']} Vertical 9:16, {k['obiektyw_mm']}mm lens, camera height {k['wysokosc_cm']} cm, level horizon. "
            f"{blok(s, 'uklad', 'materialy', 'swiatlo')} Empty, no people. {blok(s, 'styl', 'negatyw')} Do not draw the plan, labels or arrows."
        )
        refs = [url_planszy(s, "K1"), url_planszy(s, "materialy"), plan_url]
    aspect = "16:9" if pid == "materialy" else "9:16"
    return {"endpoint_id": ENDPOINT, "input": {"prompt": prompt, "image_urls": refs, "aspect_ratio": aspect,
                                               "resolution": "2K", "output_format": "png", "num_images": 1}}


def opis_postaci(p):
    w = p["wyglad"]
    return (f"{p['imie']}, {p['wiek']}, {p['rola_en']}. Face: {w['twarz']}. Hair: {w['wlosy']}. Build: {w['sylwetka']}. "
            f"Always wears: {p['stroj']['opis']}. ")


def zlecenie_postac(slug, krok):
    s = load(SCENO)
    p = load(postac_path(slug))
    pl = p["pliki"]
    neg = s["bloki_promptu"]["negatyw"]
    if krok == "ref":
        k1 = url_planszy(s, "K1")
        prompt = (
            "Photograph of a NEW fictional person who does not resemble any real or famous person: "
            f"{opis_postaci(p)}"
            f"They stand in the office from image 1 near the {p['strefa_opis_en']}, waist-up, 50mm lens, vertical 9:16, looking at camera, relaxed neutral expression, mouth closed, "
            "both hands visible and free (not touching furniture). An ordinary believable person with natural skin, slight asymmetry and real-life imperfections, not a model. "
            f"{blok(s, 'swiatlo', 'styl')} {neg}"
        )
        refs, n, ar = [k1], 3, "9:16"
    elif krok == "arkusz":
        prompt = (
            f"Character reference sheet of the person from image 1 ({p['imie']}): three views side by side on a plain warm light-grey studio background - "
            "front view, three-quarter view, left profile - waist-up, the same person in every panel. Keep the face, hairstyle, glasses (if any), outfit, colours and accessories exactly as in image 1. "
            f"{opis_postaci(p)}Neutral relaxed expression, soft even light matching image 2, photorealistic, 50mm. No text, no labels, no logos."
        )
        refs, n, ar = [pl["ref"]["fal_url"], url_planszy(s, "K1")], 1, "16:9"
    elif krok.startswith("kadr:"):
        kid = krok.split(":", 1)[1]
        cam = kid.rstrip("m")  # K2m = zbliżenie (medium) z kamery K2
        k = kam(s, cam)
        kd = next((x for x in p["kadry"] if x["kamera"] == kid), None)
        if not kd:
            sys.exit(f"postać {slug} nie ma kadru dla {kid} w postac.json")
        prompt = (
            f"Place the person from image 2 into the exact scene of image 1. The person must be identical to images 2 and 3: same face, hair, outfit and accessories ({opis_postaci(p)}). "
            + ("Keep the camera position, framing, lens, furniture, materials and light of image 1 unchanged; only add the person with correct real-world scale and perspective. "
               if not kid.endswith("m") else
               "Move the camera closer along the same viewing direction as image 1: a medium shot of the person from the waist up, 85mm look, the head in the upper third and the person filling about two thirds of the frame height. "
               "The background is the same part of the office as in image 1 (same furniture, materials, colours and light), softly out of focus. ")
            + 
            f"Pose and action: {kd['poza_en']} "
            "Face fully visible, sharp and well lit, mouth closed. Hands free and relaxed, not gripping or resting on objects, so the person can gesture later. "
            f"{blok(s, 'styl')} {neg}"
        )
        refs, n, ar = [url_planszy(s, cam), pl["ref"]["fal_url"], pl["arkusz"]["fal_url"]], 2, "9:16"
    else:
        sys.exit("krok: ref | arkusz | kadr:K?")
    return {"endpoint_id": ENDPOINT, "input": {"prompt": prompt, "image_urls": refs, "aspect_ratio": ar,
                                               "resolution": "2K", "output_format": "png", "num_images": n}}


# ---------------------------------------------------------------- zapis
def pobierz(url, path):
    from PIL import Image
    with urllib.request.urlopen(url) as r:
        im = Image.open(io.BytesIO(r.read())).convert("RGB")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.save(path, quality=88)
    return im.size


def zapisz(rodzaj, args):
    if rodzaj == "plan":
        s = load(SCENO)
        s["plan_fal_url"][args[0]] = args[1]
        save(SCENO, s)
    elif rodzaj == "plansza":
        pid, url = args
        s = load(SCENO)
        rel = f"plansze/{pid}.jpg"
        size = pobierz(url, os.path.join(SCENO_DIR, rel))
        s["plansze"][pid] = {"plik": rel, "fal_url": url, "rozmiar": list(size), "zatwierdzona": None}
        save(SCENO, s)
    elif rodzaj == "postac":
        slug, krok, url = args
        p = load(postac_path(slug))
        name = krok.replace(":", "_")
        rel = f"{name}.jpg"
        size = pobierz(url, os.path.join(POSTACIE, slug, rel))
        if krok.startswith("kadr:"):
            kid = krok.split(":", 1)[1]
            for kd in p["kadry"]:
                if kd["kamera"] == kid:
                    kd.update({"plik": rel, "fal_url": url, "zatwierdzony": None})
        else:
            p["pliki"][krok] = {"plik": rel, "fal_url": url, "zatwierdzony": None}
        save(postac_path(slug), p)
    else:
        sys.exit("zapisz plansza|postac|plan")
    print("ok")


# ---------------------------------------------------------------- podgląd
def podglad(co="plansze"):
    from PIL import Image, ImageDraw, ImageFont
    s = load(SCENO)
    items = []
    if co == "plansze":
        for pid, v in s["plansze"].items():
            if pid.startswith("_") or not v:
                continue
            items.append((f"{pid} {kam(s, pid)['nazwa'] if pid != 'materialy' else 'karta materiałów'}", os.path.join(SCENO_DIR, v["plik"])))
        out = os.path.join(SCENO_DIR, "PODGLAD_plansze.jpg")
    else:
        for slug in sorted(os.listdir(POSTACIE)):
            p = load(postac_path(slug))
            for kd in p["kadry"]:
                if kd.get("plik"):
                    items.append((f"{p['imie']} {kd['kamera']}", os.path.join(POSTACIE, slug, kd["plik"])))
        out = os.path.join(OBSADA_DIR, "PODGLAD_postacie.jpg")
    if not items:
        sys.exit("nic do pokazania")
    tw, th, cols = 360, 640, 5
    rows = math.ceil(len(items) / cols)
    sheet = Image.new("RGB", (cols * tw, rows * (th + 34)), "white")
    d = ImageDraw.Draw(sheet)
    f = ImageFont.truetype(FONT, 18)
    for i, (label, path) in enumerate(items):
        im = Image.open(path).convert("RGB")
        im.thumbnail((tw, th))
        x, y = (i % cols) * tw, (i // cols) * (th + 34)
        sheet.paste(im, (x + (tw - im.width) // 2, y + 34))
        d.text((x + 6, y + 6), label, fill="#071D49", font=f)
    sheet.save(out, quality=85)
    print(out)


# ---------------------------------------------------------------- HeyGen
def heygen(slug):
    p = load(postac_path(slug))
    glowny = next((k for k in p["kadry"] if k.get("glowny")), None)
    if not glowny or not glowny.get("fal_url"):
        sys.exit("brak zatwierdzonego kadru głównego (kadry[].glowny = true z fal_url)")
    print(json.dumps({
        "1_utworz_photo_avatar": {"path": "/v3/avatars", "method": "POST",
                                  "json": {"type": "photo", "name": f"NotarAI Komputerku v2 - {p['imie']}",
                                           "file": {"type": "url", "url": glowny["fal_url"]}}},
        "2_sprawdz_silniki": {"path": "/v3/avatars/looks/<look_id>", "method": "GET",
                              "oczekiwane": "supported_api_engines zawiera heygen-avatar-6-turbo i avatar_v"},
        "3_render_ujecia": {"path": "/v3/videos", "method": "POST",
                            "json": {"type": "avatar", "avatar_id": p.get("heygen", {}).get("avatar_id") or "<look_id>",
                                     "audio_url": "<mp3 kwestii z ElevenLabs>",
                                     "engine": {"type": p["ruch"]["silnik_domyslny"]},
                                     "motion_prompt": p["ruch"]["motion_prompt_baza"] + " <akcja z odcinka>",
                                     "aspect_ratio": "9:16", "resolution": "1080p"}},
    }, ensure_ascii=False, indent=2))


def nowa_postac(slug):
    path = postac_path(slug)
    if os.path.exists(path):
        sys.exit(f"{path} już istnieje")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    save(path, {
        "slug": slug, "imie": "", "wiek": 0, "rola": "", "rola_en": "",
        "wyglad": {"twarz": "", "wlosy": "", "sylwetka": ""},
        "stroj": {"opis": "", "kolory": {}},
        "rekwizyty": [], "charakter": "", "relacje": "",
        "strefa": "", "strefa_opis_en": "",
        "kadry": [{"kamera": "K?", "glowny": True, "poza_en": ""}],
        "glos": {"opis_voice_design_en": "", "elevenlabs_voice_id": None},
        "ruch": {"silnik_domyslny": "heygen-avatar-6-turbo", "silnik_gest": "avatar_v",
                 "motion_prompt_baza": "", "gesty_typowe": [], "unikac": []},
        "heygen": {"avatar_id": None},
        "pliki": {"ref": None, "arkusz": None},
        "status": "szkic"
    })
    print(path)


def status():
    s = load(SCENO)
    print(f"{s['wersja']}:")
    for pid, v in s["plansze"].items():
        if pid.startswith("_"):
            continue
        print(f"  plansza {pid:10s} {'OK ' + v['plik'] if v else '—'}{'  (zatwierdzona)' if v and v.get('zatwierdzona') else ''}")
    if os.path.isdir(POSTACIE):
        for slug in sorted(os.listdir(POSTACIE)):
            p = load(postac_path(slug))
            kadry = ", ".join(f"{k['kamera']}{'✓' if k.get('fal_url') else '—'}" for k in p["kadry"])
            print(f"  postać {slug:8s} ref {'✓' if p['pliki'].get('ref') else '—'}  arkusz {'✓' if p['pliki'].get('arkusz') else '—'}  kadry {kadry}  "
                  f"głos {'✓' if p['glos'].get('elevenlabs_voice_id') else '—'}  heygen {'✓' if p['heygen'].get('avatar_id') else '—'}  [{p['status']}]")


def main(a):
    if not a:
        print(__doc__); return
    c = a[0]
    if c == "plan":
        k = a[a.index("--kamera") + 1] if "--kamera" in a else None
        o = a[a.index("-o") + 1] if "-o" in a else None
        plan(k, o)
    elif c == "zlecenie" and a[1] == "plansza":
        print(json.dumps(zlecenie_plansza(a[2]), ensure_ascii=False, indent=2))
    elif c == "zlecenie" and a[1] == "postac":
        print(json.dumps(zlecenie_postac(a[2], a[3]), ensure_ascii=False, indent=2))
    elif c == "zapisz":
        zapisz(a[1], a[2:])
    elif c == "podglad":
        podglad(a[1] if len(a) > 1 else "plansze")
    elif c == "heygen":
        heygen(a[1])
    elif c == "nowa-postac":
        nowa_postac(a[1])
    elif c == "status":
        status()
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
