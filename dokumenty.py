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

# Pasy zachodza na siebie, zeby wiersz tabeli lub numer przeciety granica
# pasa byl w calosci przynajmniej w jednym z nich.
NAKLADKA = 0.12

# Strona PDF z warstwa tekstowa dluzsza niz tyle znakow to dokument
# elektroniczny (np. wydruk KW z EKW, wypis z rejestru gruntow z systemu).
PROG_TEKSTU = 200


def opisz_strony(sciezki: list[Path]) -> list[dict]:
    """Lista stron sprawy bez renderowania obrazow.

    Obrazy powstaja dopiero przy odczycie konkretnej strony (obrazy_strony),
    bo 300 stron w 300 dpi trzymanych naraz w pamieci to kilka GB.
    """
    strony: list[dict] = []
    for sciezka in sciezki:
        rozszerzenie = sciezka.suffix.lower()
        if rozszerzenie == ".pdf":
            with fitz.open(sciezka) as pdf:
                ile = pdf.page_count
            strony.extend(
                {"dokument": sciezka.name, "strona": n, "sciezka": sciezka}
                for n in range(1, ile + 1)
            )
        elif rozszerzenie in OBRAZY:
            strony.append({"dokument": sciezka.name, "strona": 1, "sciezka": sciezka})
        else:
            raise ValueError(f"Nieobslugiwany format: {sciezka.name}")
        if len(strony) > config.MAX_STRON:
            raise ValueError(
                f"Za duzo stron ({len(strony)}). Limit to {config.MAX_STRON} "
                "(zmienna PIECZAPP_MAX_STRON)."
            )
    return strony


def obrazy_strony(strona: dict) -> dict:
    """Renderuje jedna strone: obraz calej strony, pasy w pelnej rozdzielczosci
    i warstwe tekstowa PDF (jesli jest)."""
    obraz, tekst = _wczytaj_strone(strona)
    return {
        "calosc": _na_png(_dopasuj(obraz)),
        "pasy": [_na_png(_dopasuj(pas)) for pas in _pasy(obraz)],
        "tekst": tekst if len(tekst) >= PROG_TEKSTU else "",
    }


def _wczytaj_strone(strona: dict) -> tuple[Image.Image, str]:
    sciezka = Path(strona["sciezka"])
    if sciezka.suffix.lower() != ".pdf":
        with Image.open(sciezka) as obraz:
            return obraz.convert("L"), ""
    with fitz.open(sciezka) as pdf:
        s = pdf[strona["strona"] - 1]
        skala = config.DPI / 72
        piksmapa = s.get_pixmap(matrix=fitz.Matrix(skala, skala), colorspace=fitz.csGRAY)
        obraz = Image.frombytes("L", (piksmapa.width, piksmapa.height), piksmapa.samples)
        return obraz, s.get_text("text").strip()


def _pasy(obraz: Image.Image) -> list[Image.Image]:
    """Dzieli strone na poziome pasy na cala szerokosc.

    Pasy, nie kafelki: wiersz tabeli musi zostac w jednym kawalku, inaczej
    numer dzialki i jej powierzchnia trafilyby do roznych obrazow.
    Wysokosc pasa dobieramy tak, by po dopasowaniu do limitow modelu pas
    nie byl juz dalej pomniejszany.
    """
    szer, wys = obraz.size
    skala = min(1.0, config.MAX_BOK / szer)
    wys_pasa = int(min(config.MAX_BOK, config.MAX_PIKSELI / (szer * skala)) / skala)
    if wys_pasa >= wys:
        return []  # cala strona miesci sie w limicie, pasy nic nie wnosza
    krok = int(wys_pasa * (1 - NAKLADKA))
    pasy, gora = [], 0
    while True:
        dol = min(wys, gora + wys_pasa)
        pasy.append(obraz.crop((0, max(0, dol - wys_pasa), szer, dol)))
        if dol >= wys:
            return pasy
        gora += krok


def _dopasuj(obraz: Image.Image) -> Image.Image:
    """Pomniejsza obraz do tego, co model faktycznie widzi."""
    szer, wys = obraz.size
    skala = min(1.0, config.MAX_BOK / max(szer, wys), (config.MAX_PIKSELI / (szer * wys)) ** 0.5)
    if skala < 1.0:
        obraz = obraz.resize((max(1, int(szer * skala)), max(1, int(wys * skala))), Image.LANCZOS)
    return obraz


def _na_png(obraz: Image.Image) -> bytes:
    bufor = io.BytesIO()
    obraz.convert("L").save(bufor, format="PNG", optimize=True)  # skany sa czarno-biale
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

    _oznacz_jako_ai(dokument)
    cel.parent.mkdir(parents=True, exist_ok=True)
    dokument.save(cel)
    return cel


# Informacja w metadanych pliku, czytelna maszynowo (art. 50 ust. 2 AI Act).
# Zostaje w pliku po edycji w Wordzie, dopoki ktos jej swiadomie nie usunie.
OZNACZENIE_AI = ("Projekt przygotowany z udziałem sztucznej inteligencji (notarai). "
                 "Wymaga weryfikacji i akceptacji notariusza.")


def _oznacz_jako_ai(dokument) -> None:
    from datetime import datetime, timezone
    wlasciwosci = dokument.core_properties
    wlasciwosci.author = "notarai"
    wlasciwosci.last_modified_by = "notarai"
    wlasciwosci.title = "Projekt dokumentu - do weryfikacji notariusza"
    wlasciwosci.category = "Projekt wygenerowany przez AI"
    wlasciwosci.keywords = "AI-generated; notarai; projekt"
    wlasciwosci.comments = OZNACZENIE_AI
    wlasciwosci.created = datetime.now(timezone.utc).replace(tzinfo=None)
