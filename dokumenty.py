"""Konwersje dokumentow. Wszystko lokalnie, bez zewnetrznych binariow."""
import io
import re
from pathlib import Path

import fitz  # PyMuPDF
from docx import Document
from docx.shared import Pt
from PIL import Image

import config

OBRAZY = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}

# Limity obrazu po stronie modelu (dokumentacja Claude Vision).
# Model i tak przeskaluje wiekszy obraz w dol, wiec wysylanie nadmiaru
# pikseli tylko kosztuje, a nic nie wnosi.
PROG_WIELU_OBRAZOW = 20     # powyzej tylu obrazow w zadaniu obowiazuje ostrzejszy limit
MAX_BOK_WIELE_OBRAZOW = 2000

# Strona bez warstwy tekstowej, ktora nie miesci sie w limicie, jest dzielona
# na dwie zachodzace czesci. Kazda idzie w pelnej rozdzielczosci, wiec model
# widzi mniej wiecej dwa razy wiecej szczegolu.
NAKLADKA = 0.08
PROG_TEKSTU = 200           # tyle znakow uznajemy za prawdziwa warstwe tekstowa


def strony_ze_skanow(sciezki: list[Path]) -> list[dict]:
    """Zamienia skany (PDF lub obrazy) na liste stron gotowych dla modelu.

    Kazda strona to obraz, tekst osadzony w pliku albo jedno i drugie.
    Dokumenty wygenerowane elektronicznie (wypisy, zaswiadczenia, wydruki KW)
    niosa dokladny tekst - wtedy nie ma po co zgadywac go z obrazu.
    """
    surowe: list[dict] = []
    for sciezka in sciezki:
        rozszerzenie = sciezka.suffix.lower()
        if rozszerzenie == ".pdf":
            surowe.extend(_strony_z_pdf(sciezka))
        elif rozszerzenie in OBRAZY:
            surowe.append(
                {"dokument": sciezka.name, "strona": 1, "obraz": Image.open(sciezka), "tekst": ""}
            )
        else:
            raise ValueError(f"Nieobslugiwany format: {sciezka.name}")

        if len(surowe) > config.MAX_STRON:
            raise ValueError(
                f"Za duzo stron ({len(surowe)}). Limit to {config.MAX_STRON}. "
                "Podziel sprawe albo usun zbedne zalaczniki."
            )
    return _przygotuj(surowe)


def _strony_z_pdf(sciezka: Path) -> list[dict]:
    wynik = []
    with fitz.open(sciezka) as pdf:
        skala = config.DPI / 72
        for numer, strona in enumerate(pdf, start=1):
            piksmapa = strona.get_pixmap(matrix=fitz.Matrix(skala, skala))
            wynik.append({
                "dokument": sciezka.name,
                "strona": numer,
                "obraz": Image.open(io.BytesIO(piksmapa.tobytes("png"))),
                "tekst": strona.get_text("text").strip(),
            })
    return wynik


def _przygotuj(surowe: list[dict]) -> list[dict]:
    """Dobiera rozdzielczosc i podzial stron do limitow jednego zadania.

    Kolejnosc ustepstw, gdy obrazow jest za duzo: najpierw rezygnujemy
    z dzielenia stron, potem z obrazow tych stron, ktore maja dokladny tekst,
    a dopiero na koncu zmniejszamy wszystkie obrazy.
    """
    z_tekstem = [s for s in surowe if len(s["tekst"]) >= PROG_TEKSTU]
    skany = [s for s in surowe if len(s["tekst"]) < PROG_TEKSTU]

    dzielimy = len(z_tekstem) + 2 * len(skany) <= PROG_WIELU_OBRAZOW
    obrazy_dla_tekstowych = True
    ile = len(z_tekstem) + (2 if dzielimy else 1) * len(skany)
    if ile > PROG_WIELU_OBRAZOW:
        obrazy_dla_tekstowych = False
        ile = len(skany)
    max_bok = config.MAX_BOK if ile <= PROG_WIELU_OBRAZOW else MAX_BOK_WIELE_OBRAZOW

    wynik: list[dict] = []
    for s in surowe:
        ma_tekst = len(s["tekst"]) >= PROG_TEKSTU
        wpis = {"dokument": s["dokument"], "strona": s["strona"], "tekst": s["tekst"]}
        if ma_tekst and not obrazy_dla_tekstowych:
            wynik.append(wpis)
            continue
        czesci = _fragmenty(s["obraz"], max_bok) if (dzielimy and not ma_tekst) else [(None, s["obraz"])]
        for nazwa, kawalek in czesci:
            nowy = dict(wpis)
            if nazwa:
                nowy["fragment"] = nazwa
            nowy["png"] = _na_png(kawalek, max_bok)
            wynik.append(nowy)
    return wynik


def _fragmenty(obraz: Image.Image, max_bok: int) -> list[tuple[str | None, Image.Image]]:
    """Dzieli strone na dwie zachodzace czesci wzdluz dluzszego boku.

    Dzielimy tylko wtedy, gdy strona i tak zostalaby pomniejszona - inaczej
    podzial nic nie wnosi, a podwaja koszt.
    """
    if max(obraz.size) <= max_bok:
        return [(None, obraz)]
    if obraz.height >= obraz.width:
        srodek, margines = obraz.height // 2, int(obraz.height * NAKLADKA)
        return [
            ("gora", obraz.crop((0, 0, obraz.width, min(obraz.height, srodek + margines)))),
            ("dol", obraz.crop((0, max(0, srodek - margines), obraz.width, obraz.height))),
        ]
    srodek, margines = obraz.width // 2, int(obraz.width * NAKLADKA)
    return [
        ("lewa", obraz.crop((0, 0, min(obraz.width, srodek + margines), obraz.height))),
        ("prawa", obraz.crop((max(0, srodek - margines), 0, obraz.width, obraz.height))),
    ]


def _na_png(obraz: Image.Image, max_bok: int | None = None) -> bytes:
    max_bok = max_bok or config.MAX_BOK
    obraz = obraz.convert("L")  # skany sa czarno-biale; odcienie szarosci = 3x mniejszy PNG
    if max(obraz.size) > max_bok:
        wspolczynnik = max_bok / max(obraz.size)
        nowy = (int(obraz.width * wspolczynnik), int(obraz.height * wspolczynnik))
        obraz = obraz.resize(nowy, Image.LANCZOS)
    bufor = io.BytesIO()
    obraz.save(bufor, format="PNG", optimize=True)
    return bufor.getvalue()


def wzor_na_tekst(sciezka: Path) -> str:
    """Czyta wzor aktu. Obsluguje .docx oraz zwykly tekst."""
    if sciezka.suffix.lower() == ".docx":
        dokument = Document(sciezka)
        akapity = [akapit.text for akapit in dokument.paragraphs]
        for tabela in dokument.tables:
            for wiersz in tabela.rows:
                akapity.append(" | ".join(komorka.text for komorka in wiersz.cells))
        return "\n".join(akapity)
    return sciezka.read_text(encoding="utf-8", errors="replace")


WZORZEC_POL = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}|\[\s*([A-ZĄĆĘŁŃÓŚŹŻ][^\[\]]{2,60}?)\s*\]")

# Konwencja kancelarii (wzory pisane w Wordzie, bez znacznikow {{ }}):
#   - legenda na poczatku pliku:  "aaa - zbywca (Jan Kowalski)"
#     kod trzyliterowy, opis, w nawiasie przyklad odmiany gramatycznej
#   - "??"  w tresci = miejsce do wypelnienia bez nazwy (nazywamy je z kontekstu)
#   - "//"  rozdziela warianty tresci, z ktorych zostaje jeden
#   - uwagi w nawiasach "(gdy ...)" to instrukcje dla notariusza, nie tresc aktu
WZORZEC_LEGENDY = re.compile(r"^\s*([a-z]{2}[a-z0-9])\s*[-–—]\s*(.+?)\s*$")
WZORZEC_KODU_LEGENDY = re.compile(r"(?<![a-zA-Z0-9])([a-z]{2}[a-z0-9])(?![a-zA-Z0-9])")
ZNACZNIK = "??"
SEPARATOR_WARIANTOW = "//"


def pola_ze_wzoru(tekst: str) -> list[str]:
    """Wyciaga pola do wypelnienia. Zachowuje kolejnosc wystapienia.

    Obslugiwane zapisy: {{nazwa}}, [NAZWA] oraz konwencja kancelarii
    (kody z legendy i znaczniki ??). Patrz analizuj_wzor().
    """
    return analizuj_wzor(tekst)["pola"]


def analizuj_wzor(tekst: str) -> dict:
    """Pelna analiza wzoru.

    Zwraca:
      pola      - nazwy pol w kolejnosci wystapienia (dla modelu i interfejsu)
      legenda   - {kod: {"opis": ..., "przyklad": ...}} z naglowka wzoru
      znaczniki - [{"nr": 1, "nazwa": "??1: ...", "kontekst": "..."}]
      warianty  - liczba linii z alternatywami "//"
      tresc     - wzor bez legendy (to trafia do generowania)
    """
    legenda, tresc = _legenda_ze_wzoru(tekst)
    pola: list[str] = []
    znaczniki: list[dict] = []
    licznik = 0

    for linia in tresc.split("\n"):
        pozycja = 0
        while pozycja < len(linia):
            klasyczne = WZORZEC_POL.search(linia, pozycja)
            kod = _nastepny_kod(linia, pozycja, legenda)
            znacznik = linia.find(ZNACZNIK, pozycja)
            kandydaci = [
                (klasyczne.start(), "klasyczne") if klasyczne else None,
                (kod.start(1), "kod") if kod else None,
                (znacznik, "znacznik") if znacznik != -1 else None,
            ]
            kandydaci = [k for k in kandydaci if k]
            if not kandydaci:
                break
            start, rodzaj = min(kandydaci)

            if rodzaj == "klasyczne":
                nazwa = (klasyczne.group(1) or klasyczne.group(2)).strip()
                pozycja = klasyczne.end()
            elif rodzaj == "kod":
                nazwa = f"{kod.group(1)}: {legenda[kod.group(1)]['opis']}"
                pozycja = kod.end(1)
            else:
                licznik += 1
                kontekst = _kontekst(linia, start)
                nazwa = f"{ZNACZNIK}{licznik}: {kontekst}"
                znaczniki.append({"nr": licznik, "nazwa": nazwa, "kontekst": kontekst})
                pozycja = start + len(ZNACZNIK)

            if nazwa and nazwa not in pola:
                pola.append(nazwa)

    return {
        "pola": pola,
        "legenda": legenda,
        "znaczniki": znaczniki,
        "warianty": sum(SEPARATOR_WARIANTOW in linia for linia in tresc.split("\n")),
        "tresc": tresc,
    }


def _legenda_ze_wzoru(tekst: str) -> tuple[dict, str]:
    """Legenda to ciag linii "kod - opis" na samym poczatku wzoru."""
    linie = tekst.split("\n")
    legenda: dict = {}
    koniec = 0
    for numer, linia in enumerate(linie):
        if not linia.strip():
            if legenda:
                koniec = numer
                break
            continue
        dopasowanie = WZORZEC_LEGENDY.match(linia)
        if not dopasowanie:
            koniec = numer
            break
        kod, reszta = dopasowanie.groups()
        przyklad = ""
        nawias = re.search(r"\(([^()]*)\)\s*$", reszta)
        if nawias:
            przyklad = nawias.group(1).strip()
            reszta = reszta[: nawias.start()].strip()
        legenda[kod] = {"opis": reszta, "przyklad": przyklad}
        koniec = numer + 1
    if not legenda:
        return {}, tekst
    return legenda, "\n".join(linie[koniec:])


def _nastepny_kod(linia: str, pozycja: int, legenda: dict):
    for dopasowanie in WZORZEC_KODU_LEGENDY.finditer(linia, pozycja):
        if dopasowanie.group(1) in legenda:
            return dopasowanie
    return None


def _kontekst(linia: str, pozycja: int, przed: int = 6, po: int = 3) -> str:
    """Krotki opis miejsca ?? na podstawie sasiednich slow."""
    # Cudzyslowy wycinamy - nazwa pola wraca od modelu w JSON-ie i kazdy
    # cudzyslow to ryzyko zepsutej skladni.
    lewo = _CUDZYSLOWY.sub("", linia[:pozycja]).replace(ZNACZNIK, "…").split()[-przed:]
    prawo = _CUDZYSLOWY.sub("", linia[pozycja + len(ZNACZNIK):]).replace(ZNACZNIK, "…").split()[:po]
    return " ".join(lewo + ["__"] + prawo)


_CUDZYSLOWY = re.compile("[\"'„”“»«]")


def tekst_na_docx(tekst: str, cel: Path) -> Path:
    """Zapisuje projekt aktu jako .docx. Puste linie rozdzielaja akapity."""
    dokument = Document()
    styl = dokument.styles["Normal"]
    styl.font.name = "Times New Roman"
    styl.font.size = Pt(12)

    for linia in tekst.split("\n"):
        tresc = linia.rstrip()
        akapit = dokument.add_paragraph()
        if not tresc:
            continue
        wyrownaj_srodek = tresc.isupper() and len(tresc) < 80
        przebieg = akapit.add_run(tresc.strip())
        if wyrownaj_srodek:
            przebieg.bold = True
            akapit.alignment = 1

    cel.parent.mkdir(parents=True, exist_ok=True)
    dokument.save(cel)
    return cel
