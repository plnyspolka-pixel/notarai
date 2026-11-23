#!/usr/bin/env python3
"""Warstwa czytelna serii „Komputerku…": wszystko, co widz ma PRZECZYTAĆ, renderujemy sami (PIL).
Modele obrazu i wideo nie potrafią pisać po polsku, więc żaden czytelny tekst nie powstaje w generatorze
(zasada ZERO TEKSTU, patrz README „Kontrola jakości i poprawki").

Szablony (ujęcie typu `dokument` w odcinki/EPxx.json, pole `szablon` + `dane`):
  porownanie_kw   dwa odczyty treści tej samej KW (starszy/nowszy) z podświetloną różnicą
  notatka         karteczka z krótką notatką roboczą (np. „1 XII")
  projekt_i_ksiega  fragment projektu aktu i wydruk odpisu KW z rozbieżnym numerem lokalu
  plansza_ekranu  plansza zastępcza za nagranie ekranu aplikacji (ujęcie `ekran` bez pliku)

Użycie:
  dokumenty.py EP04 u9           renderuje ujęcie wg JSON → wyjscie/EP04/plansze/u9_dokument.png (+ .json z punktem zbliżenia)
  dokumenty.py EP04 --plansze    odświeża plansze zastępcze wszystkich ujęć `ekran` (u5_ekran.png itd.)
  dokumenty.py demo <katalog>    przykładowe PNG do obejrzenia
Renderuje w 2160×3840 (2× 9:16), montaż robi powolne zbliżenie (zoompan) na punkt `fokus`.
Nie woła żadnego API, koszt 0 USD.
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

TU = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(TU, ".."))
DEJAVU = "/usr/share/fonts/truetype/dejavu/"
F, FB, FM = (DEJAVU + n for n in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSansMono.ttf"))
FO = next((DEJAVU + n for n in ("DejaVuSans-Oblique.ttf", "DejaVuSans-BoldOblique.ttf", "DejaVuSans-Bold.ttf") if os.path.exists(DEJAVU + n)), FB)
SYGNET = os.path.join(ROOT, "pakiet", "01_marki", "oryginalny_sygnet_512px.png")
NAVY, CYAN, BLUE = (7, 29, 73), (0, 207, 255), (43, 82, 217)
INK, MUTED, PAPER, LINE, MARKER = (13, 25, 60), (100, 115, 146), (250, 250, 247), (214, 220, 232), (255, 232, 120)
W, H = 2160, 3840


def font(p, s):
    return ImageFont.truetype(p, s)


def zawin(dr, tekst, f, maxw):
    """Zawija tekst do szerokości w pikselach (nie w znakach – wtedy nic nie wystaje poza kadr)."""
    linie = []
    for akapit in str(tekst).split("\n"):
        biezaca = ""
        for slowo in akapit.split(" "):
            proba = (biezaca + " " + slowo).strip()
            if dr.textlength(proba, font=f) <= maxw or not biezaca:
                biezaca = proba
            else:
                linie.append(biezaca)
                biezaca = slowo
        linie.append(biezaca)
    return linie


def tekst(dr, xy, t, f, fill, maxw=None, ls=1.3):
    x, y = xy
    for l in (zawin(dr, t, f, maxw) if maxw else str(t).split("\n")):
        dr.text((x, y), l, font=f, fill=fill)
        y += int(f.size * ls)
    return y


def cien(tlo, box, promien=40, alfa=120):
    x0, y0, x1, y1 = box
    warstwa = Image.new("RGBA", tlo.size, (0, 0, 0, 0))
    ImageDraw.Draw(warstwa).rectangle([x0 + 18, y0 + 28, x1 + 18, y1 + 28], fill=(0, 0, 0, alfa))
    warstwa = warstwa.filter(ImageFilter.GaussianBlur(promien))
    tlo.alpha_composite(warstwa)


# ---------------------------------------------------------------- arkusz KW

def arkusz_kw(d, szer=1700, wys=1500):
    """Jeden odczyt treści KW jako kartka – układ skrócony, duża czcionka (czytelna na telefonie po zbliżeniu).
    Zwraca (obraz, y środka wyróżnionego wiersza albo None)."""
    im = Image.new("RGB", (szer, wys), PAPER)
    dr = ImageDraw.Draw(im)
    dr.rectangle([0, 0, szer, 120], fill=NAVY)
    dr.text((60, 36), "NotarAI  ·  odczyt treści księgi wieczystej", font=font(FB, 42), fill=(255, 255, 255))
    znak = "DEMO · dane testowe"
    dr.text((szer - 60 - dr.textlength(znak, font=font(FB, 38)), 40), znak, font=font(FB, 38), fill=CYAN)
    y = 170
    dr.text((60, y), f"KW nr {d['numer']}", font=font(FB, 64), fill=INK); y += 86
    dr.text((60, y), f"numer demonstracyjny  ·  stan na {d['stan_na']}", font=font(F, 42), fill=MUTED); y += 58
    dr.text((60, y), f"źródło: {d['zrodlo']}  ·  plik: {d['plik']}", font=font(FM, 36), fill=MUTED); y += 80
    hl_y = None
    for dzial in d["dzialy"]:
        dr.rectangle([60, y, szer - 60, y + 70], fill=(232, 236, 245))
        dr.text((80, y + 14), dzial["naglowek"], font=font(FB, 40), fill=INK); y += 86
        for w in dzial["wiersze"]:
            wyroznij = bool(w.get("wyroznij"))
            f_w = font(FB if wyroznij else F, 52 if wyroznij else 48)
            linie = zawin(dr, w["wartosc"], f_w, szer - 60 - 80 - 380)
            h = 68 * len(linie) + 18
            if wyroznij:
                dr.rectangle([60, y - 8, szer - 60, y + h - 6], fill=MARKER)
                hl_y = y + h // 2
            dr.text((80, y + 2), w["etykieta"], font=font(F, 42), fill=MUTED)
            yy = y
            for l in linie:
                dr.text((80 + 380, yy), l, font=f_w, fill=INK); yy += 68
            y += h
            dr.line([60, y - 4, szer - 60, y - 4], fill=LINE, width=2)
        y += 24
    dr.text((60, wys - 70), "Dokument demonstracyjny do materiału szkoleniowego. Numer księgi i dane nie istnieją.",
            font=font(F, 30), fill=MUTED)
    wm = Image.new("RGBA", (szer, wys), (0, 0, 0, 0))
    ImageDraw.Draw(wm).text((int(szer * 0.14), int(wys * 0.36)), "DEMO", font=font(FB, 420), fill=(13, 25, 60, 18))
    im = Image.alpha_composite(im.convert("RGBA"), wm.rotate(22, resample=Image.BICUBIC)).convert("RGB")
    return im, hl_y


DEMO_KW = {
    "numer": "XX1X/00000001/1",
    "zrodlo": "dostawca EKW skonfigurowany w NotarAI",
    "plik": "KW_odczyt.pdf",
    "polozenie": "Przykładowo, ul. Przykładowa 7 lok. 12",
    "powierzchnia": "48,20 m²",
    "wlasciciel": "Borowska Anna – udział 1/1",
    "hipoteka": "Brak wpisów.",
}


def dzialy_kw(d, wzmianka=None):
    dzial3 = [{"etykieta": "Wpisy", "wartosc": "Brak wpisów."}]
    if wzmianka:
        dzial3.append({"etykieta": "Wzmianka", "wartosc": wzmianka, "wyroznij": True})
    else:
        dzial3.append({"etykieta": "Wzmianki", "wartosc": "Brak wzmianek."})
    return [
        {"naglowek": "DZIAŁ I-O – OZNACZENIE NIERUCHOMOŚCI", "wiersze": [
            {"etykieta": "Położenie", "wartosc": f"{d['polozenie']}, lokal mieszkalny, {d['powierzchnia']}"}]},
        {"naglowek": "DZIAŁ II – WŁASNOŚĆ", "wiersze": [{"etykieta": "Właściciel", "wartosc": d["wlasciciel"]}]},
        {"naglowek": "DZIAŁ III – PRAWA, ROSZCZENIA I OGRANICZENIA", "wiersze": dzial3},
        {"naglowek": "DZIAŁ IV – HIPOTEKA", "wiersze": [{"etykieta": "Wpisy", "wartosc": d["hipoteka"]}]},
    ]


def porownanie_kw(dane, wyjscie):
    """Dwa odczyty jednej KW, jeden pod drugim; zbliżenie na wyróżniony wiersz nowszego odczytu."""
    d = {**DEMO_KW, **(dane or {})}
    stary = {**d, "stan_na": d.get("stan_stary", "12.11.2026, 14:03"), "plik": d.get("plik_stary", "KW_2026-11-12.pdf"),
             "dzialy": dzialy_kw(d)}
    nowy = {**d, "stan_na": d.get("stan_nowy", "13.11.2026, 08:41"), "plik": d.get("plik_nowy", "KW_2026-11-13.pdf"),
            "dzialy": dzialy_kw(d, d.get("wzmianka", "DZ.KW./XX1X/00001234/26 – wpłynęła 13.11.2026, 08:12. Treść do ustalenia."))}
    tlo = Image.new("RGBA", (W, H), NAVY + (255,))
    dr = ImageDraw.Draw(tlo)
    dr.text((230, 120), "Ta sama księga, dwa odczyty", font=font(FB, 72), fill=(255, 255, 255))
    a1, _ = arkusz_kw(stary)
    a2, hl = arkusz_kw(nowy)
    x, y1 = (W - a1.width) // 2, 360
    y2 = y1 + a1.height + 220
    for a, y, etykieta in ((a1, y1, d.get("etykieta_stary", "WCZORAJ")), (a2, y2, d.get("etykieta_nowy", "DZIŚ"))):
        cien(tlo, (x, y, x + a.width, y + a.height))
        dr.rectangle([x, y - 84, x + 460, y], fill=BLUE)
        dr.text((x + 34, y - 70), etykieta, font=font(FB, 46), fill=(255, 255, 255))
        tlo.paste(a, (x, y))
    tlo.convert("RGB").save(wyjscie, optimize=True)
    fokus = [0.5, (y2 + (hl or 900)) / H]
    meta = {"fokus": fokus, "zoom": 1.3, "szablon": "porownanie_kw"}
    json.dump(meta, open(os.path.splitext(wyjscie)[0] + ".json", "w"))
    return meta


# ---------------------------------------------------------------- notatka

def notatka(dane, wyjscie):
    d = {"tekst": "1 XII", "podpis": "", **(dane or {})}
    tlo = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    dr = ImageDraw.Draw(tlo)
    for y in range(H):  # blat orzechowy – gradient
        t = y / H
        dr.line([(0, y), (W, y)], fill=(int(96 - 36 * t), int(60 - 24 * t), int(38 - 16 * t), 255))
    teczka = Image.new("RGBA", (W + 400, 1500), (0, 0, 0, 0))
    ImageDraw.Draw(teczka).rounded_rectangle([0, 0, W + 400, 1500], radius=40, fill=(199, 170, 126, 255))
    teczka = teczka.rotate(3, resample=Image.BICUBIC, expand=True)
    karteczka = Image.new("RGBA", (1300, 1300), (0, 0, 0, 0))
    dk = ImageDraw.Draw(karteczka)
    dk.rectangle([0, 0, 1300, 1300], fill=(255, 224, 92, 255))
    dk.rectangle([0, 0, 1300, 160], fill=(252, 214, 70, 255))
    f_t = font(FO, 360 if len(d["tekst"]) <= 6 else 220)
    tw = dk.textlength(d["tekst"], font=f_t)
    dk.text(((1300 - tw) / 2, 380), d["tekst"], font=f_t, fill=(31, 58, 147))
    if d["podpis"]:
        dk.text((120, 900), d["podpis"], font=font(FO, 80), fill=(31, 58, 147))
    karteczka = karteczka.rotate(-6, resample=Image.BICUBIC, expand=True)
    kx, ky = (W - karteczka.width) // 2, 1500
    cien(tlo, (kx + 60, ky + 60, kx + karteczka.width - 60, ky + karteczka.height - 60), 60, 150)
    tlo.alpha_composite(karteczka, (kx, ky))
    tlo.alpha_composite(teczka, (-200, -520))
    tlo.convert("RGB").save(wyjscie, optimize=True)
    meta = {"fokus": [0.5, 0.52], "zoom": 1.3, "szablon": "notatka"}
    json.dump(meta, open(os.path.splitext(wyjscie)[0] + ".json", "w"))
    return meta


# ---------------------------------------------------------------- projekt aktu i odpis KW

def projekt_i_ksiega(dane, wyjscie):
    """Kartka projektu aktu (fragment § 1) i wydruk odpisu księgi: ten sam lokal, inny numer.
    Bez marki programu: to papier na stole notariusza, nie ekran aplikacji."""
    d = {"projekt": "lokal mieszkalny nr 12", "ksiega": "lokal mieszkalny nr 21", "stan_na": "15:52", **(dane or {})}
    tlo = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    dr = ImageDraw.Draw(tlo)
    for y in range(H):  # blat orzechowy
        t = y / H
        dr.line([(0, y), (W, y)], fill=(int(96 - 36 * t), int(60 - 24 * t), int(38 - 16 * t), 255))

    def kartka(szer, wys, wiersze, wyroznij, kolor_wyr, kolko=False):
        im = Image.new("RGBA", (szer, wys), PAPER + (255,))
        k = ImageDraw.Draw(im)
        y, box = 110, None
        for styl, t in wiersze:
            f = font(FB, 64) if styl == "n" else font(F, 54)
            if styl == "x":
                lw = k.textlength(t, font=font(FB, 60))
                box = (90, y - 14, 90 + lw + 40, y + 86)
                k.rectangle(box, fill=kolor_wyr)
                k.text((110, y), t, font=font(FB, 60), fill=INK)
                y += 110
                continue
            for l in zawin(k, t, f, szer - 200):
                k.text((100, y), l, font=f, fill=INK if styl == "n" else (40, 46, 70))
                y += 84 if styl == "n" else 76
            y += 30
        if kolko and box:
            x0, y0, x1, y1 = box
            for o in range(0, 12, 3):
                k.ellipse([x0 - 40 - o, y0 - 30 - o, x1 + 40 + o, y1 + 30 + o], outline=(200, 30, 40, 255), width=6)
        k.text((100, wys - 90), "DEMO · dane fikcyjne", font=font(F, 36), fill=MUTED)
        return im, box

    proj, _ = kartka(1760, 1000, [
        ("n", "PROJEKT AKTU NOTARIALNEGO"),
        ("t", "§ 1. Sprzedający oświadcza, że jest właścicielem samodzielnego lokalu:"),
        ("x", d["projekt"]),
        ("t", "dla którego Sąd Rejonowy prowadzi księgę wieczystą o numerze podanym w odpisie."),
        ("t", "§ 2. Strony oświadczają, że…"),
    ], None, (255, 232, 120, 255), kolko=True)
    ksi, _ = kartka(1760, 900, [
        ("n", "ODPIS KSIĘGI WIECZYSTEJ"),
        ("t", f"wydruk z dnia dzisiejszego, godz. {d['stan_na']}"),
        ("t", "Dział I-O · Oznaczenie nieruchomości"),
        ("x", d["ksiega"]),
        ("t", "Dział II · Własność: zgodnie z projektem"),
    ], None, (255, 232, 120, 255))
    proj = proj.rotate(-2.5, resample=Image.BICUBIC, expand=True)
    ksi = ksi.rotate(2, resample=Image.BICUBIC, expand=True)
    for im, (x, y) in ((ksi, (230, 2050)), (proj, (150, 900))):
        cien(tlo, (x + 40, y + 40, x + im.width - 40, y + im.height - 40), 50, 140)
        tlo.alpha_composite(im, (x, y))
    tlo.convert("RGB").save(wyjscie, optimize=True)
    meta = {"fokus": [0.5, 0.5], "zoom": 1.3, "szablon": "projekt_i_ksiega"}
    json.dump(meta, open(os.path.splitext(wyjscie)[0] + ".json", "w"))
    return meta


# ---------------------------------------------------------------- plansza ekranu

def plansza_ekranu(uid, co_widac, czas_s, wyjscie):
    w, h = 1080, 1920
    im = Image.new("RGB", (w, h), NAVY)
    dr = ImageDraw.Draw(im)
    if os.path.exists(SYGNET):
        s = Image.open(SYGNET).convert("RGBA"); s.thumbnail((190, 190))
        im.paste(s, ((w - s.width) // 2, 230), s)
    x0, y0, x1, y1 = 90, 470, w - 90, 1500
    dr.rectangle([x0, y0, x1, y1], outline=BLUE, width=3)
    dr.rectangle([x0, y0, x1, y0 + 78], fill=BLUE)
    dr.text((x0 + 30, y0 + 22), "NotarAI  ·  nagranie ekranu aplikacji", font=font(FB, 32), fill=(255, 255, 255))
    tekst(dr, (x0 + 40, y0 + 130), co_widac, font(F, 38), (255, 255, 255), maxw=x1 - x0 - 80, ls=1.35)
    y = y1 - 170
    y = tekst(dr, (x0 + 40, y), "PLANSZA ZASTĘPCZA – do podmiany na realne nagranie ekranu", font(FB, 30), CYAN, maxw=x1 - x0 - 80)
    tekst(dr, (x0 + 40, y + 6), "(konto demo, dane testowe; interfejsu nie generujemy)", font(F, 26), (190, 200, 225), maxw=x1 - x0 - 80)
    dr.text((x0 + 40, 1640), f"{uid} · {czas_s:g} s", font=font(F, 30), fill=(150, 165, 200))
    im.save(wyjscie, optimize=True)
    return {"szablon": "plansza_ekranu"}


SZABLONY = {"porownanie_kw": porownanie_kw, "notatka": notatka, "projekt_i_ksiega": projekt_i_ksiega}


def renderuj(ep, u, baza):
    """Renderuje ujęcie `dokument` (albo planszę `ekran`) do wyjscie/EPxx/plansze; zwraca (ścieżka png, meta)."""
    plansze = os.path.join(baza, "plansze"); os.makedirs(plansze, exist_ok=True)
    uid = u["id"]
    if u["typ"] == "ekran":
        p = os.path.join(plansze, f"{uid}_ekran.png")
        return p, plansza_ekranu(uid, u.get("co_widac", ""), float(u.get("czas_s") or 5), p)
    szablon = u.get("szablon") or "porownanie_kw"
    if szablon not in SZABLONY:
        sys.exit(f"{uid}: nieznany szablon {szablon!r}; dostępne: {', '.join(SZABLONY)}")
    p = os.path.join(plansze, f"{uid}_dokument.png")
    return p, SZABLONY[szablon](u.get("dane"), p)


def main(a):
    if not a:
        sys.exit(__doc__)
    if a[0] == "demo":
        kat = a[1] if len(a) > 1 else "."
        os.makedirs(kat, exist_ok=True)
        porownanie_kw(None, os.path.join(kat, "demo_porownanie_kw.png"))
        notatka(None, os.path.join(kat, "demo_notatka.png"))
        plansza_ekranu("u5", "Lista spraw w kokpicie NotarAI; widoczne dwie odrębne sprawy z fikcyjnymi etykietami.", 7,
                       os.path.join(kat, "demo_plansza_ekranu.png"))
        return print(f"demo → {kat}")
    ep = a[0].upper()
    odc = json.load(open(os.path.join(ROOT, "odcinki", f"{ep}.json"), encoding="utf-8"))
    baza = os.path.join(ROOT, "wyjscie", ep)
    if "--plansze" in a:
        for u in odc["ujecia"]:
            if u["typ"] == "ekran":
                print(renderuj(ep, u, baza)[0])
        return
    szukane = set(x for x in a[1:] if x.startswith("u"))
    for u in odc["ujecia"]:
        if u["id"] in szukane:
            p, meta = renderuj(ep, u, baza)
            print(p, json.dumps(meta))


if __name__ == "__main__":
    main(sys.argv[1:])
