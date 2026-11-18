"""Konwersje dokumentow. Wszystko lokalnie, bez zewnetrznych binariow."""
import io
import logging
import re
from copy import deepcopy
from difflib import SequenceMatcher
from pathlib import Path

import fitz  # PyMuPDF
from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt
from PIL import Image

import config

log = logging.getLogger("pieczapp.dokumenty")

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


def udzial_warstwy_tekstowej(strony: list[dict]) -> float:
    """Ulamek stron sprawy z warstwa tekstowa PDF (co najmniej PROG_TEKSTU znakow).

    Bez renderowania - sam tekst z PDF, wiec dla kilkuset stron trwa chwile.
    Obrazy (zdjecia, TIFF) nie maja warstwy tekstowej. Sluzy automatycznemu
    doborowi dokladnosci odczytu (ustawienia_kancelarii.dokladnosc_odczytu).
    """
    if not strony:
        return 0.0
    z_tekstem = 0
    otwarte: dict[Path, fitz.Document] = {}
    try:
        for strona in strony:
            sciezka = Path(strona["sciezka"])
            if sciezka.suffix.lower() != ".pdf":
                continue
            pdf = otwarte.get(sciezka)
            if pdf is None:
                pdf = otwarte[sciezka] = fitz.open(sciezka)
            if len(pdf[strona["strona"] - 1].get_text("text").strip()) >= PROG_TEKSTU:
                z_tekstem += 1
    finally:
        for pdf in otwarte.values():
            pdf.close()
    return z_tekstem / len(strony)


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


# Miejsca do uzupelnienia przez notariusza. W Wordzie maja byc nie do
# przeoczenia takze na wydruku: zakreslacz i pogrubienie, inny kolor dla
# braku danych i dla wariantu do wyboru. Tresc znacznika zostaje bez zmian.
ZNACZNIK_PROJEKTU = re.compile(r"(<<(?:BRAK|WYBOR):.*?>>)")


def _wyroznij_znacznik(przebieg, kawalek: str) -> None:
    from docx.enum.text import WD_COLOR_INDEX
    if kawalek.startswith("<<BRAK:"):
        przebieg.font.highlight_color = WD_COLOR_INDEX.YELLOW
    elif kawalek.startswith("<<WYBOR:"):
        przebieg.font.highlight_color = WD_COLOR_INDEX.TURQUOISE
    else:
        return
    przebieg.bold = True


def tekst_na_docx(tekst: str, cel: Path, wzor: Path | None = None) -> Path:
    """Zapisuje projekt aktu jako .docx. Puste linie rozdzielaja akapity.

    Gdy wzor jest plikiem Word, projekt powstaje NA TYM PLIKU: strona
    i marginesy, naglowki i stopki, style, czcionka, kapitaliki i odstepy sa
    wzoru, a kazdy akapit projektu dostaje formatowanie najbardziej podobnego
    akapitu wzoru (_docx_na_wzorze). Dzieki temu plik otwiera sie w Wordzie
    tak, jak kancelaria pisze swoje akty, zamiast w Times New Roman 12.
    Bez wzoru Word (albo gdy wzor to .txt) - zapis domyslny jak dotad.
    """
    if wzor is not None and Path(wzor).suffix.lower() == ".docx" and Path(wzor).exists():
        try:
            return _docx_na_wzorze(tekst, cel, Path(wzor))
        except Exception as blad:  # noqa: BLE001 - projekt musi powstac, choc bez szaty wzoru
            log.warning("formatowanie projektu ze wzoru nieudane (%s), zapis domyslny",
                        type(blad).__name__)

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
        for kawalek in ZNACZNIK_PROJEKTU.split(tresc.strip()):
            if not kawalek:
                continue
            przebieg = akapit.add_run(kawalek)
            if wyrownaj_srodek:
                przebieg.bold = True
            _wyroznij_znacznik(przebieg, kawalek)
        if wyrownaj_srodek:
            akapit.alignment = 1

    _oznacz_jako_ai(dokument)
    cel.parent.mkdir(parents=True, exist_ok=True)
    dokument.save(cel)
    return cel


# --- Projekt na pliku wzoru --------------------------------------------------
# Model pisze projekt akapit po akapicie wedlug wzoru, wiec akapity projektu
# odpowiadaja akapitom wzoru (z wypelnionymi miejscami). Dopasowujemy je po
# podobienstwie tekstu, idac przez wzor do przodu, i kopiujemy formatowanie
# akapitu (wyrownanie, wciecia, odstepy, styl) oraz dominujace formatowanie
# znakow (czcionka, rozmiar, kapitaliki, pogrubienie). Akapit bez pary dostaje
# formatowanie dominujace w calym wzorze - nigdy obce.

OKNO_DOPASOWANIA = 60      # ile akapitow wzoru w przod porownujemy z akapitem projektu
PROG_DOPASOWANIA = 0.45    # ponizej tego podobienstwa akapit uznajemy za nowy
_DLUGOSC_POROWNANIA = 160  # poczatek akapitu wystarcza, zeby go rozpoznac
_ZACZYNA_NUMEREM = re.compile(r"^\s*(\d+[.)]|§\s*\d+|[a-z][.)]|[IVX]+[.)])\s")
_PLACEHOLDERY = re.compile(r"\?\?|\{\{[^{}]*\}\}|\[[^\[\]]*\]")
_W_RPR_DO_USUNIECIA = ("w:highlight", "w:shd", "w:rPrChange")


def _norm(tekst: str) -> str:
    tekst = _PLACEHOLDERY.sub(" ", tekst.lower())
    return re.sub(r"\s+", " ", tekst).strip()[:_DLUGOSC_POROWNANIA]


def _tekst_elementu(element) -> str:
    return "".join(t.text or "" for t in element.iter(qn("w:t")))


def _czysty_rpr(rpr):
    """Kopia formatowania znakow bez zakreslen wzoru (nasze znaczniki maja wlasne)."""
    if rpr is None:
        return None
    kopia = deepcopy(rpr)
    for nazwa in _W_RPR_DO_USUNIECIA:
        for el in kopia.findall(qn(nazwa)):
            kopia.remove(el)
    return kopia


def _dominujace_rpr(elementy_p) -> object | None:
    """Formatowanie znakow, ktore we wskazanych akapitach obejmuje najwiecej tekstu."""
    liczniki: dict[str, tuple[int, object]] = {}
    for p in elementy_p:
        for r in p.iter(qn("w:r")):
            ile = len(_tekst_elementu(r).strip())
            if not ile:
                continue
            rpr = r.find(qn("w:rPr"))
            klucz = str(rpr.xml) if rpr is not None else ""
            stary = liczniki.get(klucz, (0, rpr))
            liczniki[klucz] = (stary[0] + ile, rpr)
    if not liczniki:
        return None
    _, rpr = max(liczniki.values(), key=lambda w: w[0])
    return _czysty_rpr(rpr)


def _dominujace_ppr(elementy_p):
    """Formatowanie akapitu najczestsze (wg liczby znakow) we wzorze."""
    liczniki: dict[str, tuple[int, object]] = {}
    for p in elementy_p:
        ile = len(_tekst_elementu(p).strip())
        if not ile:
            continue
        ppr = p.find(qn("w:pPr"))
        klucz = str(ppr.xml) if ppr is not None else ""
        stary = liczniki.get(klucz, (0, ppr))
        liczniki[klucz] = (stary[0] + ile, ppr)
    if not liczniki:
        return None
    _, ppr = max(liczniki.values(), key=lambda w: w[0])
    return ppr


class _Szablon:
    """Akapity wzoru do dopasowywania akapitow projektu, w kolejnosci."""

    def __init__(self, dokument):
        self.akapity: list[tuple[str, object, str]] = []   # (znormalizowany, w:p, tekst)
        for akapit in dokument.paragraphs:
            tekst = akapit.text.strip()
            if tekst:
                self.akapity.append((_norm(tekst), akapit._p, tekst))
        self.ostatni = 0
        elementy = [a[1] for a in self.akapity]
        self.domyslny_ppr = _dominujace_ppr(elementy)
        self.domyslny_rpr = _dominujace_rpr(elementy)

    def dopasuj(self, tekst: str) -> tuple[object, str] | None:
        """(w:p wzoru, jego tekst) najbardziej podobny do akapitu projektu albo None."""
        szukany = _norm(tekst)
        if not szukany or not self.akapity:
            return None
        poczatek = max(0, self.ostatni - 5)
        koniec = min(len(self.akapity), self.ostatni + OKNO_DOPASOWANIA)
        najlepszy, wynik = None, PROG_DOPASOWANIA
        for i in range(poczatek, koniec):
            wzorzec = self.akapity[i][0]
            if wzorzec == szukany:
                najlepszy, wynik = i, 1.0
                break
            m = SequenceMatcher(None, szukany, wzorzec, autojunk=False)
            if m.real_quick_ratio() < wynik or m.quick_ratio() < wynik:
                continue
            r = m.ratio()
            if r > wynik:
                najlepszy, wynik = i, r
        if najlepszy is None:
            return None
        self.ostatni = najlepszy + 1
        return self.akapity[najlepszy][1], self.akapity[najlepszy][2]


def _skopiuj_ppr(akapit, ppr, tresc: str, tekst_wzoru: str) -> None:
    if ppr is None:
        return
    kopia = deepcopy(ppr)
    # Podzial sekcji nalezy do wzoru, nie do akapitu projektu.
    for el in kopia.findall(qn("w:sectPr")):
        kopia.remove(el)
    # Numeracja automatyczna Worda + numer wpisany w tresci = podwojny numer.
    numpr = kopia.find(qn("w:numPr"))
    if numpr is not None and _ZACZYNA_NUMEREM.match(tresc) and not _ZACZYNA_NUMEREM.match(tekst_wzoru):
        kopia.remove(numpr)
    istniejacy = akapit._p.find(qn("w:pPr"))
    if istniejacy is not None:
        akapit._p.remove(istniejacy)
    akapit._p.insert(0, kopia)


def _docx_na_wzorze(tekst: str, cel: Path, wzor: Path) -> Path:
    dokument = Document(wzor)
    szablon = _Szablon(dokument)

    # Tresc wzoru znika, zostaja ustawienia sekcji (strona, marginesy,
    # naglowki, stopki), style, czcionki i numeracja.
    body = dokument.element.body
    for element in list(body):
        if element.tag != qn("w:sectPr"):
            body.remove(element)

    for linia in tekst.split("\n"):
        tresc = linia.rstrip()
        akapit = dokument.add_paragraph()
        if not tresc:
            continue
        para = szablon.dopasuj(tresc)
        if para is not None:
            element, tekst_wzoru = para
            _skopiuj_ppr(akapit, element.find(qn("w:pPr")), tresc, tekst_wzoru)
            rpr = _dominujace_rpr([element])
            if rpr is None:
                rpr = szablon.domyslny_rpr
        else:
            _skopiuj_ppr(akapit, szablon.domyslny_ppr, tresc, "")
            rpr = szablon.domyslny_rpr
        naglowek = para is None and tresc.isupper() and len(tresc) < 80
        for kawalek in ZNACZNIK_PROJEKTU.split(tresc.strip()):
            if not kawalek:
                continue
            przebieg = akapit.add_run(kawalek)
            if rpr is not None:
                przebieg._r.insert(0, deepcopy(rpr))
            if naglowek:
                przebieg.bold = True
            _wyroznij_znacznik(przebieg, kawalek)
        if naglowek:
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
