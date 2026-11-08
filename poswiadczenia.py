"""Poswiadczenie kopii: zdjecie albo skan dokumentu -> opis do repertorium A.

Przy poswiadczeniu zgodnosci odpisu (kopii, wyciagu) albo daty okazania
dokumentu notariusz wpisuje do repertorium A krotka tresc czynnosci, np.
"Poswiadczenie zgodnosci odpisu z okazanym dokumentem - faktury VAT
nr 1/2026 z dnia 5 listopada 2026 r., wystawionej przez ABC sp. z o.o.,
dotyczacej sprzedazy uslug transportowych (2 strony)".

Ten modul robi z tego jeden ruch: telefon (aparat) albo kserokopiarka
(skan do PDF) -> POST /api/poswiadczenia/opis -> model w Bedrock (region UE)
rozpoznaje dokumenty i ich cechy -> kod sklada tresc do repertorium i liczy
taksa (§ 13 pkt 2 albo 3, od kazdej rozpoczetej strony).

Jeden plik skanu moze zawierac kilka dokumentow (kopiarka skanuje plik
dokumentow naraz) - model dzieli strony na dokumenty, a kazdy dostaje
osobny wpis.

RODO: pliki zapisujemy tylko na czas odczytu w katalogu tymczasowym i
usuwamy zaraz po nim. Ani obrazow, ani odczytanej tresci nie zapisujemy
i nie logujemy - do logow trafia liczba stron i dokumentow.
"""
import logging
import os
import re
import shutil
import tempfile
from datetime import date
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

import bedrock
import dokumenty
import dziennik
import prompty
import taksa

log = logging.getLogger("pieczapp.poswiadczenia")

# Odczyt naglowka dokumentu nie potrzebuje Opusa z maksymalnym mysleniem:
# notariusz czeka przy kopiarce. Jak w kalkulatorze - osobny profil EU,
# zeby nie dlawic limitu modelu od odczytu spraw. Pusto = config.MODEL.
MODEL_DOMYSLNY = "eu.anthropic.claude-sonnet-4-6"


def _model_z_env(wartosc: str | None) -> str:
    model = (MODEL_DOMYSLNY if wartosc is None else wartosc).strip()
    if model and not model.startswith("eu."):
        raise RuntimeError(f"PIECZAPP_POSWIADCZENIA_MODEL '{model}' nie jest profilem EU (prefiks 'eu.').")
    return model


MODEL = _model_z_env(os.getenv("PIECZAPP_POSWIADCZENIA_MODEL"))

# Jedno wywolanie modelu = najwyzej tyle stron (Bedrock: 20 obrazow w zadaniu).
MAX_STRON = bedrock.MAX_OBRAZOW
MAX_PLIK = 30 * 1024 * 1024
ROZSZERZENIA = dokumenty.OBRAZY | {".pdf", ".webp"}

# Rodzaj poswiadczenia -> (poczatek tresci w repertorium, pozycja taksy).
RODZAJE = {
    "odpis": ("Poświadczenie zgodności odpisu z okazanym dokumentem", "poswiadczenie_odpisu"),
    "kopia": ("Poświadczenie zgodności kopii z okazanym dokumentem", "poswiadczenie_odpisu"),
    "wyciag": ("Poświadczenie zgodności wyciągu z okazanym dokumentem", "poswiadczenie_odpisu"),
    "data": ("Poświadczenie daty okazania dokumentu", "poswiadczenie_daty"),
}

router = APIRouter(prefix="/api/poswiadczenia", tags=["poswiadczenia"])


# --- skladanie opisu ---------------------------------------------------------

def _strony_slownie(n: int) -> str:
    if n == 1:
        return "1 strona"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f"{n} strony"
    return f"{n} stron"


def _tekst(wartosc, maks: int = 400) -> str:
    """Pole od modelu jako jedna linia tekstu, bez 'null', 'brak' i podobnych."""
    if wartosc is None:
        return ""
    tekst = re.sub(r"\s+", " ", str(wartosc)).strip().strip(",;")
    return "" if tekst.lower() in {"null", "none", "brak", "-", "nie dotyczy", "nieustalony"} else tekst[:maks]


def opis_repertorium(dokument: dict, rodzaj: str, stron: int) -> str:
    """Krotka tresc czynnosci do repertorium A.

    Poczatek (rodzaj czynnosci) i liczba stron pochodza z kodu, nie z modelu:
    to one decyduja o taksie i nie moga sie rozjechac z tym, co policzono.
    Model daje przedmiot w dopelniaczu ("faktury VAT nr ... z dnia ...").
    """
    poczatek = RODZAJE.get(rodzaj, RODZAJE["odpis"])[0]
    przedmiot = _tekst(dokument.get("przedmiot_dopelniacz"), 600)
    if not przedmiot:
        czesci = [_tekst(dokument.get("nazwa")) or "dokumentu"]
        if _tekst(dokument.get("numer")):
            czesci.append("nr " + _tekst(dokument["numer"]))
        if _tekst(dokument.get("data_slownie")):
            czesci.append("z dnia " + _tekst(dokument["data_slownie"]))
        przedmiot = " ".join(czesci)
    if przedmiot.endswith(".") and not re.search(r"\b(r|nr|ul|al|pl|os|sp|o\.o|s\.a)\.$", przedmiot):
        przedmiot = przedmiot[:-1]   # kropka konczaca zdanie, nie skrot "r." / "sp. z o.o."
    return f"{poczatek} – {przedmiot} ({_strony_slownie(stron)})"


def _zakres(dokument: dict, wszystkich: int) -> tuple[int, int]:
    """Strony dokumentu [od, do] w numeracji 1..wszystkich, poprawione."""
    try:
        od = int(dokument.get("strona_od") or 1)
        do = int(dokument.get("strona_do") or od)
    except (TypeError, ValueError):
        return 1, wszystkich
    od = min(max(1, od), wszystkich)
    return od, min(max(od, do), wszystkich)


def _uporzadkuj(odpowiedz: dict, wszystkich: int) -> list[dict]:
    """Dokumenty od modelu -> rozlaczne zakresy pokrywajace wszystkie strony.

    Model bywa nieprecyzyjny w granicach. Liczba stron decyduje o taksie,
    wiec kazda strona musi nalezec do dokladnie jednego dokumentu: zakresy
    sortujemy, nakladki obcinamy, a luke doklejamy do poprzedniego dokumentu.
    """
    surowe = [d for d in (odpowiedz.get("dokumenty") or []) if isinstance(d, dict)]
    if not surowe:
        surowe = [{"strona_od": 1, "strona_do": wszystkich}]
    surowe.sort(key=lambda d: _zakres(d, wszystkich))
    wynik: list[dict] = []
    nastepna = 1
    for d in surowe:
        od, do = _zakres(d, wszystkich)
        od = max(od, nastepna)
        if od > wszystkich or do < od:
            continue
        if wynik and od > nastepna:          # luka - strony bez dokumentu
            wynik[-1]["strona_do"] = od - 1
        elif not wynik and od > 1:
            od = 1
        wynik.append({**d, "strona_od": od, "strona_do": do})
        nastepna = do + 1
    if not wynik:
        wynik = [{**surowe[0], "strona_od": 1, "strona_do": wszystkich}]
    wynik[-1]["strona_do"] = wszystkich
    return wynik


def _lista(wartosc, maks: int = 8) -> list[str]:
    if not isinstance(wartosc, list):
        return []
    return [t for t in (_tekst(x, 200) for x in wartosc[:maks]) if t]


def zloz_wynik(odpowiedz: dict, wszystkich: int, rodzaj: str, dzien: date | None = None) -> dict:
    """Odpowiedz modelu -> wpisy do repertorium z taksa. Bez wywolan modelu."""
    pozycja = RODZAJE.get(rodzaj, RODZAJE["odpis"])[1]
    wpisy = []
    for nr, d in enumerate(_uporzadkuj(odpowiedz, wszystkich), start=1):
        stron = d["strona_do"] - d["strona_od"] + 1
        kalkulacja = taksa.oblicz({"data": (dzien or date.today()).isoformat(),
                                   "stale": [{"id": pozycja, "dokumentow": 1, "stron_dokumentu": stron}]})
        wpisy.append({
            "nr": nr,
            "strona_od": d["strona_od"], "strona_do": d["strona_do"], "stron": stron,
            "nazwa": _tekst(d.get("nazwa"), 200),
            "numer": _tekst(d.get("numer"), 120),
            "data": _tekst(d.get("data"), 10) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", _tekst(d.get("data"), 10)) else "",
            "data_slownie": _tekst(d.get("data_slownie"), 80),
            "wystawca": _tekst(d.get("wystawca"), 200),
            "dotyczy": _tekst(d.get("dotyczy"), 300),
            "postac": _tekst(d.get("postac"), 120),
            "jezyk": _tekst(d.get("jezyk"), 40) or "polski",
            "cechy": _lista(d.get("cechy")),
            "niepewne": _lista(d.get("niepewne")),
            "opis": opis_repertorium(d, rodzaj, stron),
            "taksa_netto": kalkulacja["pozycje"][0]["netto"] if kalkulacja["pozycje"] else 0.0,
            "taksa_brutto": kalkulacja["razem"],
        })
    return {
        "rodzaj": rodzaj if rodzaj in RODZAJE else "odpis",
        "stron": wszystkich,
        "dokumenty": wpisy,
        "razem_brutto": round(sum(w["taksa_brutto"] for w in wpisy), 2),
    }


# --- odczyt ------------------------------------------------------------------

def _tresc_dla_modelu(strony: list[dict]) -> list[dict]:
    """Strony jako obrazy (cala strona; naglowek dokumentu jest czytelny bez
    pasow) plus warstwa tekstowa PDF, gdy jest."""
    tresc: list[dict] = []
    for nr, strona in enumerate(strony, start=1):
        obrazy = dokumenty.obrazy_strony(strona)
        tresc.append({"text": f"=== STRONA {nr} z {len(strony)} ==="})
        tresc.append({"image": {"format": "png", "source": {"bytes": obrazy["calosc"]}}})
        if obrazy["tekst"]:
            tresc.append({"text": f"STRONA {nr} - WARSTWA TEKSTOWA PDF:\n" + obrazy["tekst"][:6000]})
    tresc.append({"text": prompty.polecenie_poswiadczenia(len(strony))})
    return tresc


def odczytaj(sciezki: list[Path], rodzaj: str = "odpis") -> dict:
    """Pliki jednego okazania (zdjecia stron albo skan PDF) -> wpisy do repertorium."""
    strony = dokumenty.opisz_strony(sciezki)
    if not strony:
        raise ValueError("Brak stron do odczytu.")
    if len(strony) > MAX_STRON:
        raise ValueError(f"Za dużo stron naraz ({len(strony)}). Jednorazowo najwyżej {MAX_STRON} "
                         "- podziel skan na części.")
    surowa = bedrock._rozmowa(prompty.POSWIADCZENIE, _tresc_dla_modelu(strony),
                              max_tokenow=8000, myslenie=False, model=MODEL or None)
    wynik = zloz_wynik(bedrock._wczytaj_json(surowa), len(strony), rodzaj)
    log.info("poswiadczenie: stron=%d dokumentow=%d", len(strony), len(wynik["dokumenty"]))
    return wynik


def _rozszerzenie(nazwa: str | None, typ: str | None) -> str:
    rozszerzenie = Path(nazwa or "").suffix.lower()
    if rozszerzenie in ROZSZERZENIA:
        return rozszerzenie
    return {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
            "application/pdf": ".pdf"}.get((typ or "").lower(), rozszerzenie)


# --- API ---------------------------------------------------------------------

@router.get("")
def informacje():
    return {"rodzaje": [{"id": k, "nazwa": v[0]} for k, v in RODZAJE.items()],
            "max_stron": MAX_STRON}


@router.post("/opis")
def opisz(pliki: list[UploadFile] = File(...), rodzaj: str = Form("odpis")):
    """Zdjecia stron albo skan z kopiarki -> propozycja wpisu do repertorium A.

    Pliki leza na dysku tylko na czas odczytu (katalog tymczasowy, usuwany
    w finally). Kolejnosc plikow = kolejnosc stron.
    """
    if rodzaj not in RODZAJE:
        raise HTTPException(400, "Nieznany rodzaj poświadczenia.")
    katalog = Path(tempfile.mkdtemp(prefix="notarai-posw-"))
    try:
        sciezki = []
        for nr, plik in enumerate(pliki, start=1):
            rozszerzenie = _rozszerzenie(plik.filename, plik.content_type)
            if rozszerzenie not in ROZSZERZENIA:
                raise HTTPException(415, "Obsługiwane są zdjęcia (JPG, PNG, WEBP, TIFF) i PDF.")
            dane = plik.file.read(MAX_PLIK + 1)
            if len(dane) > MAX_PLIK:
                raise HTTPException(413, f"Plik jest większy niż {MAX_PLIK // 1024 // 1024} MB.")
            # Nazwa z telefonu bywa nazwiskiem - na dysku tylko numer.
            sciezka = katalog / f"{nr:03d}{'.png' if rozszerzenie == '.webp' else rozszerzenie}"
            if rozszerzenie == ".webp":
                _webp_na_png(dane, sciezka)
            else:
                sciezka.write_bytes(dane)
            sciezki.append(sciezka)
        try:
            return odczytaj(sciezki, rodzaj)
        except bedrock.Przeciazenie as blad:
            raise HTTPException(503, str(blad))
        except (bedrock.NiepoprawnyJson, ValueError) as blad:
            raise HTTPException(422, str(blad))
        except Exception as blad:  # noqa: BLE001 - obraz uszkodzony, blad AWS
            log.error("poswiadczenie: blad odczytu (%s)", dziennik.opis_bledu(blad))
            raise HTTPException(500, "Nie udało się odczytać dokumentu. Zrób wyraźniejsze zdjęcie "
                                     "albo spróbuj ponownie.")
    finally:
        shutil.rmtree(katalog, ignore_errors=True)


def _webp_na_png(dane: bytes, cel: Path) -> None:
    import io

    from PIL import Image
    with Image.open(io.BytesIO(dane)) as obraz:
        obraz.convert("L").save(cel, format="PNG")
