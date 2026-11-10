"""Generuje ikony i splash aplikacji klienta (mobilna/assets) ze znaku notarai.

Zrodlo: static/notarai-symbol.svg (ten sam ksztalt), przekolorowany pod
kolory aplikacji z mobilna/src/theme.ts: tlo granat, znak bialy, akcent
(w oryginale cyjan) zloty. SVG renderuje PyMuPDF (fitz, jest w
requirements), skladanie i skalowanie - Pillow.

Uruchom z katalogu repo:  .venv\\Scripts\\python scripts\\generuj_ikony_aplikacji.py
"""
from __future__ import annotations

import io
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parent.parent
CEL = REPO / "mobilna" / "assets"

GRANAT = "#0d193c"
GRANAT_CIEMNY = "#050a30"
ZLOTO = "#e4c47a"
ZLOTO_JASNE = "#efd79d"
BIEL = "#ffffff"
BIEL_2 = "#dbe3f6"

# Ksztalty z static/notarai-symbol.svg (viewBox 0 0 132 132); kolor wedlug roli.
KSZTALTY = [
    ('<path d="M16 16h104c0 13-9 23-23 23H29c-10 0-17 6-21 16C0 39 7 16 16 16Z" fill="{glowny}"/>'),
    ('<path d="M31 45h76c-1 12-9 19-21 19H43c-13 0-18 9-23 18-8-16 0-37 11-37Z" fill="{drugi}"/>'),
    ('<path d="M45 70h25l-4 33-21 24V70Z" fill="{glowny}"/>'),
    ('<path d="M74 70h19v32c0 4-2 7-6 10l-13 9V70Z" fill="{akcent}"/>'),
    ('<path d="M97 70h13v26c0 5-3 8-7 11l-6 4V70Z" fill="{akcent2}"/>'),
    ('<rect x="105" y="112" width="14" height="14" rx="3" fill="{akcent}"/>'),
    ('<rect x="119" y="98" width="9" height="9" rx="2" fill="{akcent2}"/>'),
]


def svg_znaku(glowny: str, drugi: str, akcent: str, akcent2: str) -> str:
    tresc = "".join(k.format(glowny=glowny, drugi=drugi, akcent=akcent, akcent2=akcent2) for k in KSZTALTY)
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 132 132">{tresc}</svg>'


def renderuj(svg: str, px: int = 2048) -> Image.Image:
    """SVG -> RGBA przyciety do zawartosci (przezroczyste tlo)."""
    dok = fitz.open(stream=svg.encode("utf-8"), filetype="svg")
    strona = dok[0]
    skala = px / strona.rect.width
    pix = strona.get_pixmap(matrix=fitz.Matrix(skala, skala), alpha=True)
    obraz = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGBA")
    return obraz.crop(obraz.getbbox())


def wklej_na_srodku(tlo: Image.Image, znak: Image.Image, udzial: float) -> Image.Image:
    """Wkleja znak tak, by dluzszy bok zajmowal `udzial` boku tla."""
    bok = tlo.width
    skala = (bok * udzial) / max(znak.size)
    maly = znak.resize((round(znak.width * skala), round(znak.height * skala)), Image.LANCZOS)
    x = (bok - maly.width) // 2
    y = (bok - maly.height) // 2
    wynik = tlo.copy()
    wynik.alpha_composite(maly, (x, y))
    return wynik


def gradient(bok: int, gora: str, dol: str) -> Image.Image:
    """Pionowy gradient (lekko ukosny) - tlo ikony."""
    g = Image.new("RGBA", (bok, bok))
    a, b = Image.new("RGBA", (1, 1), gora).getpixel((0, 0)), Image.new("RGBA", (1, 1), dol).getpixel((0, 0))
    rys = ImageDraw.Draw(g)
    for y in range(bok):
        t = y / (bok - 1)
        kolor = tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(4))
        rys.line([(0, y), (bok, y)], fill=kolor)
    return g


def zaokraglony(obraz: Image.Image, promien: float) -> Image.Image:
    maska = Image.new("L", obraz.size, 0)
    ImageDraw.Draw(maska).rounded_rectangle([0, 0, obraz.width - 1, obraz.height - 1],
                                            radius=round(obraz.width * promien), fill=255)
    wynik = Image.new("RGBA", obraz.size, (0, 0, 0, 0))
    wynik.paste(obraz, (0, 0), maska)
    return wynik


def main() -> None:
    CEL.mkdir(parents=True, exist_ok=True)
    na_ciemnym = renderuj(svg_znaku(BIEL, BIEL_2, ZLOTO, ZLOTO_JASNE))
    jednobarwny = renderuj(svg_znaku(BIEL, BIEL, BIEL, BIEL))
    tlo_ikony = gradient(1024, GRANAT, GRANAT_CIEMNY)

    # iOS / ogolna: pelne tlo bez przezroczystosci (App Store odrzuca alfe).
    ikona = wklej_na_srodku(tlo_ikony, na_ciemnym, 0.62).convert("RGB")
    ikona.save(CEL / "icon.png", optimize=True)

    # Android adaptive icon 512x512: tlo osobno, znak w strefie bezpiecznej (srodkowe ~61%).
    gradient(512, GRANAT, GRANAT_CIEMNY).convert("RGB").save(CEL / "android-icon-background.png", optimize=True)
    pusty = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    wklej_na_srodku(pusty, na_ciemnym, 0.44).save(CEL / "android-icon-foreground.png", optimize=True)
    # Monochromatyczna (Android 13 themed icons): system nadaje kolor, liczy sie tylko alfa.
    pusty432 = Image.new("RGBA", (432, 432), (0, 0, 0, 0))
    wklej_na_srodku(pusty432, jednobarwny, 0.44).save(CEL / "android-icon-monochrome.png", optimize=True)

    # Splash: znak na przezroczystym tle, tlo granatowe daje app.json (splash.backgroundColor).
    pusty1024 = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    wklej_na_srodku(pusty1024, na_ciemnym, 0.42).save(CEL / "splash-icon.png", optimize=True)

    # Favicon web: zaokraglony granatowy kafelek, czytelny na jasnej i ciemnej karcie.
    kafel = zaokraglony(wklej_na_srodku(gradient(192, GRANAT, GRANAT_CIEMNY), na_ciemnym, 0.70), 0.22)
    kafel.resize((48, 48), Image.LANCZOS).save(CEL / "favicon.png", optimize=True)

    for plik in sorted(CEL.glob("*.png")):
        with Image.open(plik) as im:
            print(f"{plik.relative_to(REPO)}  {im.size[0]}x{im.size[1]}  {im.mode}")


if __name__ == "__main__":
    main()
