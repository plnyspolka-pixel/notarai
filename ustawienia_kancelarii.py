"""Ustawienia ogolne kancelarii: to, co notariusz ustawia raz, zamiast klikac
przy kazdej sprawie.

  - domyslna dokladnosc odczytu (auto / max / high / medium) - od niej zaczyna
    przelacznik "Dokladnosc odczytu" przy kazdej nowej sprawie, na kazdym
    urzadzeniu; "auto" dobiera dokladnosc do dokumentow (dokladnosc_odczytu),
  - wzor nazwy pliku Word z projektem (nazwy.nazwa_pliku), np.
    "{zbywca} - {nabywca} - {czynnosc} - {miejscowosc}".

Plik kancelarii "ustawienia" (magazyn.PLIKI_KANCELARII): w chmurze lezy w S3
razem z kalendarzem i zasadami, lokalnie w dane/. Same preferencje, zero
danych osobowych. Zmienia je notariusz (wlasciciel kancelarii), tak jak
nieprzekraczalne zasady; w trybie lokalnym - kazdy.
"""
import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

import dokumenty
import magazyn
import nazwy

log = logging.getLogger("pieczapp.ustawienia")

router = APIRouter(prefix="/api/ustawienia/ogolne", tags=["ustawienia"])

PLIK = "ustawienia"

# Wartosci przelacznika. "auto" nie trafia do modelu - dokladnosc_odczytu()
# zamienia je na konkretny wysilek po obejrzeniu dokumentow sprawy.
DOKLADNOSCI = ("auto", "max", "high", "medium")
OPISY_DOKLADNOSCI = {
    "auto": "Automatyczna: dokumenty elektroniczne (PDF z tekstem) czytam szybko, "
            "skany i zdjecia - z wysoka dokladnoscia.",
    "max": "Maksymalna: model najdluzej analizuje kazda strone. Najwolniej i najdrozej.",
    "high": "Wysoka: zwykle wystarcza przy czytelnych skanach.",
    "medium": "Szybka: najszybciej i najtaniej, do prostych spraw z wyraznymi dokumentami.",
}
MAX_DLUGOSC_WZORU = 200


def domyslne() -> dict:
    return {"dokladnosc": "auto", "nazwa_pliku": nazwy.DOMYSLNY_WZOR_NAZWY}


def _oczysc(dane: dict) -> dict:
    """Tylko znane klucze i poprawne wartosci; reszta wraca do domyslnych."""
    wynik = domyslne()
    if dane.get("dokladnosc") in DOKLADNOSCI:
        wynik["dokladnosc"] = dane["dokladnosc"]
    wzor = dane.get("nazwa_pliku")
    if isinstance(wzor, str) and wzor.strip():
        wynik["nazwa_pliku"] = wzor.strip()[:MAX_DLUGOSC_WZORU]
    return wynik


def wczytaj() -> dict:
    """Ustawienia kancelarii; przy bledzie odczytu - domyslne (odczyt sprawy
    nie moze sie wywrocic przez plik ustawien)."""
    try:
        dane = magazyn.wczytaj_plik_kancelarii(PLIK, {})
    except Exception as blad:  # noqa: BLE001
        log.warning("ustawienia kancelarii nieodczytane (%s), biore domyslne", type(blad).__name__)
        dane = {}
    return _oczysc(dane if isinstance(dane, dict) else {})


def zapisz(zmiany: dict) -> dict:
    """Zapis tylko podanych kluczy; nieznane wartosci sa odrzucane (400)."""
    if "dokladnosc" in zmiany and zmiany["dokladnosc"] not in DOKLADNOSCI:
        raise ValueError("Nieznana dokladnosc odczytu. Dozwolone: " + ", ".join(DOKLADNOSCI) + ".")
    if "nazwa_pliku" in zmiany:
        wzor = str(zmiany["nazwa_pliku"] or "").strip()
        if not wzor:
            zmiany["nazwa_pliku"] = nazwy.DOMYSLNY_WZOR_NAZWY
        elif len(wzor) > MAX_DLUGOSC_WZORU:
            raise ValueError(f"Wzor nazwy pliku jest za dlugi (najwyzej {MAX_DLUGOSC_WZORU} znakow).")
        else:
            nieznane = nazwy.nieznane_pola_wzoru(wzor)
            if nieznane:
                raise ValueError("Nieznane pola we wzorze nazwy: " + ", ".join("{" + p + "}" for p in nieznane)
                                 + ". Dostepne: " + ", ".join("{" + p + "}" for p in nazwy.POLA_NAZWY) + ".")
            zmiany["nazwa_pliku"] = wzor

    def zmiana(dane: dict) -> dict:
        for klucz in ("dokladnosc", "nazwa_pliku"):
            if klucz in zmiany:
                dane[klucz] = zmiany[klucz]
        return _oczysc(dane)

    wynik = magazyn.zmien_plik_kancelarii(PLIK, zmiana, {})
    log.info("ustawienia kancelarii zapisane: dokladnosc=%s", wynik["dokladnosc"])
    return wynik


# ---------------------------------------------------------------------------
# Dokladnosc odczytu dla konkretnej sprawy
# ---------------------------------------------------------------------------
def dokladnosc_odczytu(zadana: str, strony: list[dict]) -> tuple[str, str]:
    """(wysilek dla modelu, powod wyboru).

    `zadana` to wartosc z przelacznika przy sprawie; pusta albo nieznana
    oznacza domyslna kancelarii. "auto" rozstrzygamy po dokumentach: gdy kazda
    strona ma warstwe tekstowa PDF (wydruki z EKW, rejestru gruntow, pisma
    z systemow), model dostaje dokladne znaki i wystarczy odczyt szybki;
    skany i zdjecia czytamy z wysoka dokladnoscia. Maksymalna zostaje do
    wyboru recznego - trudne sprawy notariusz poznaje sam.

    Powod: "wybrana" (przelacznik), "domyslna" (ustawienie kancelarii),
    "auto_elektroniczne" albo "auto_skany".
    """
    if zadana in DOKLADNOSCI:
        wybor, powod = zadana, "wybrana"
    else:
        wybor, powod = wczytaj()["dokladnosc"], "domyslna"
    if wybor != "auto":
        return wybor, powod
    try:
        udzial = dokumenty.udzial_warstwy_tekstowej(strony)
    except Exception as blad:  # noqa: BLE001 - uszkodzony plik wyjdzie przy odczycie
        log.warning("auto-dokladnosc: nie sprawdzono warstwy tekstowej (%s)", type(blad).__name__)
        udzial = 0.0
    if strony and udzial >= 1.0:
        return "medium", "auto_elektroniczne"
    return "high", "auto_skany"


def opis_wyboru(wysilek: str, powod: str) -> str:
    """Zdanie dla notariusza po odczycie - skad sie wziela ta dokladnosc."""
    nazwa = {"max": "maksymalna", "high": "wysoka", "medium": "szybka"}.get(wysilek, wysilek)
    if powod == "auto_elektroniczne":
        return f"Dokładność {nazwa}: wszystkie strony to dokumenty elektroniczne z tekstem."
    if powod == "auto_skany":
        return f"Dokładność {nazwa}: w sprawie są skany lub zdjęcia bez warstwy tekstowej."
    if powod == "domyslna":
        return f"Dokładność {nazwa} (ustawienie kancelarii)."
    return f"Dokładność {nazwa}."


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
class Zmiany(BaseModel):
    dokladnosc: str | None = None
    nazwa_pliku: str | None = None


def _moge_zmieniac(request: Request) -> bool:
    # Te same reguly co dla zasad kancelarii: wlasciciel; bez logowania - kazdy.
    import personalizacja
    return personalizacja._moge_zmieniac_zasady(request)


@router.get("")
def pobierz(request: Request):
    return {
        **wczytaj(),
        "moge_zmieniac": _moge_zmieniac(request),
        "u_klienta": magazyn.u_klienta(),
        "pola_nazwy": nazwy.POLA_NAZWY,
        "domyslny_wzor_nazwy": nazwy.DOMYSLNY_WZOR_NAZWY,
        "przyklad_nazwy": nazwy.przyklad_nazwy(wczytaj()["nazwa_pliku"]),
    }


@router.put("")
def zmien(request: Request, dane: Zmiany):
    if not _moge_zmieniac(request):
        raise HTTPException(403, "Ustawienia kancelarii zmienia notariusz - właściciel kancelarii.")
    if magazyn.u_klienta():
        raise HTTPException(409, "Ta kancelaria trzyma pliki u siebie - ustawienia zostają w tej przeglądarce.")
    zmiany = {k: v for k, v in dane.model_dump().items() if v is not None}
    if not zmiany:
        raise HTTPException(400, "Nic do zapisania.")
    try:
        wynik = zapisz(zmiany)
    except ValueError as blad:
        raise HTTPException(400, str(blad))
    except magazyn.KonfliktZapisu as blad:
        raise HTTPException(409, str(blad))
    return {**wynik, "przyklad_nazwy": nazwy.przyklad_nazwy(wynik["nazwa_pliku"])}
