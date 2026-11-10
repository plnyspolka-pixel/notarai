"""Mapa notariuszy: polozenie kancelarii i wyszukiwarka najblizszej.

Kazda kancelaria podaje adres przy rejestracji (trafia do umowy powierzenia).
Z tego adresu wyznaczamy wspolrzedne geograficzne i pokazujemy kancelarie na
publicznej mapie (/notariusze), na ktorej klient znajdzie najblizsza.

Geokoder: Nominatim (OpenStreetMap) przez HTTPS, z identyfikacja uslugi
w User-Agent i nie czesciej niz raz na sekunde - tak wymaga jego regulamin
(operations.osmfoundation.org/policies/nominatim). Wysylamy wylacznie adres
kancelarii, czyli dane firmowe dostepne publicznie takze w rejestrze izby
notarialnej; nigdy dane klientow ani adresy e-mail zespolu. Adres nie trafia
do logow - logujemy identyfikator kancelarii i typ bledu.

Wspolrzedne zapisujemy w rejestrze kancelarii pod kluczem "mapa":
  {"adres", "lat", "lon", "dokladnosc": "adres" | "miejscowosc", "sprawdzono"}
  albo {"adres", "blad", "sprawdzono"}, gdy geokoder adresu nie zna.
Klucz "na_mapie" (domyslnie False) mowi, czy kancelaria jest publikowana.
Zmienia go wylacznie wlasciciel kancelarii.
"""
import logging
import math
import os
import re
import threading
import time

import json
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

import autoryzacja
import dziennik
import platnosci
import rekomendacje

log = logging.getLogger("pieczapp.notariusze")

# Pusta wartosc wylacza geokodowanie (np. stanowisko lokalne bez internetu).
GEOKODER = os.getenv("PIECZAPP_GEOKODER", "https://nominatim.openstreetmap.org/search")
KONTAKT = os.getenv("PIECZAPP_KONTAKT", "kontakt@notarai.pl")
ODSTEP_S = 1.1   # regulamin Nominatim: najwyzej jedno zapytanie na sekunde
CZAS_S = 10.0

_blokada = threading.Lock()
_ostatnie = 0.0
_transport: httpx.BaseTransport | None = None   # testy podstawiaja httpx.MockTransport

_PREFIKS_ULICY = re.compile(r"^(ul\.|al\.|pl\.|os\.|ulica|aleja|plac|osiedle)\s+", re.IGNORECASE)
_KOD_POCZTOWY = re.compile(r"\b\d{2}-\d{3}\b")


def wlaczone() -> bool:
    return bool(GEOKODER)


def _odczekaj() -> None:
    """Odstep miedzy zapytaniami do geokodera, wspolny dla calego procesu."""
    global _ostatnie
    with _blokada:
        przerwa = ODSTEP_S - (time.monotonic() - _ostatnie)
        if przerwa > 0:
            time.sleep(przerwa)
        _ostatnie = time.monotonic()


def _warianty(adres: str) -> list[tuple[str, str]]:
    """Kolejne proby dla geokodera: pelny adres, adres bez skrotu "ul." i kodu
    pocztowego (Nominatim czesto sie o nie potyka), na koniec sama miejscowosc
    - wtedy polozenie jest przyblizone i tak je oznaczamy."""
    adres = " ".join(adres.split())
    czesci = [c.strip() for c in adres.split(",") if c.strip()]
    warianty = [(adres, "adres")]
    uproszczony = ", ".join(_PREFIKS_ULICY.sub("", _KOD_POCZTOWY.sub("", c)).strip() for c in czesci)
    uproszczony = " ".join(uproszczony.replace(" ,", ",").split())
    if uproszczony and uproszczony != adres:
        warianty.append((uproszczony, "adres"))
    if len(czesci) > 1:
        miejscowosc = _KOD_POCZTOWY.sub("", czesci[-1]).strip()
    else:
        dopasowanie = re.search(r"\d{2}-\d{3}\s+(.+)$", adres)
        miejscowosc = dopasowanie.group(1).strip() if dopasowanie else ""
    if miejscowosc and all(miejscowosc != w[0] for w in warianty):
        warianty.append((miejscowosc, "miejscowosc"))
    return warianty


def _zapytaj(tekst: str) -> list:
    _odczekaj()
    with httpx.Client(timeout=CZAS_S, follow_redirects=True, transport=_transport) as klient:
        odp = klient.get(
            GEOKODER,
            params={"q": tekst, "format": "jsonv2", "limit": 1, "countrycodes": "pl"},
            headers={"User-Agent": f"notarai.pl ({KONTAKT})", "Accept-Language": "pl"},
        )
    odp.raise_for_status()
    wynik = odp.json()
    return wynik if isinstance(wynik, list) else []


def geokoduj(adres: str) -> dict | None:
    """Wspolrzedne adresu albo None, gdy geokoder go nie zna.
    Bledy sieci przepuszcza - decyduje wywolujacy."""
    for tekst, dokladnosc in _warianty(adres):
        wyniki = _zapytaj(tekst)
        if wyniki:
            return {"lat": round(float(wyniki[0]["lat"]), 6),
                    "lon": round(float(wyniki[0]["lon"]), 6),
                    "dokladnosc": dokladnosc}
    return None


def ustal_polozenie(wpis: dict, wymus: bool = False) -> dict | None:
    """Uzupelnia wpis["mapa"] wspolrzednymi adresu kancelarii.

    Nie rzuca: awaria geokodera zostaje zapisana jako "blad" i nie przerywa
    rejestracji ani zmiany danych. Ten sam adres nie jest geokodowany
    ponownie, chyba ze wymus=True. Zapis rejestru nalezy do wywolujacego.
    """
    adres = (wpis.get("dane") or {}).get("adres", "")
    if not wlaczone() or not adres:
        return None
    stare = wpis.get("mapa") or {}
    if not wymus and stare.get("adres") == adres and stare.get("lat") is not None:
        return stare
    mapa = {"adres": adres, "sprawdzono": autoryzacja._teraz()}
    try:
        wynik = geokoduj(adres)
    except Exception as blad:
        wynik = None
        mapa["blad"] = "geokoder niedostepny"
        log.warning("kancelaria %s: geokoder niedostepny (%s)", wpis.get("id"), dziennik.opis_bledu(blad))
    if wynik:
        mapa.update(wynik)
        log.info("kancelaria %s: polozenie ustalone (%s)", wpis.get("id"), wynik["dokladnosc"])
    elif "blad" not in mapa:
        mapa["blad"] = "adres nieznany geokoderowi"
        log.info("kancelaria %s: geokoder nie zna adresu", wpis.get("id"))
    wpis["mapa"] = mapa
    return mapa


def odleglosc_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Odleglosc w linii prostej po kuli ziemskiej (haversine)."""
    promien = 6371.0088
    f1, f2 = math.radians(lat1), math.radians(lat2)
    df, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 2 * promien * math.asin(math.sqrt(a))


def publikowana(wpis: dict) -> bool:
    """Czy kancelaria jest na publicznej mapie: aktywna, nie wylaczyla
    publikacji i ma polozenie. Celowo NIE zalezy od abonamentu: miejsce na
    mapie nie moze byc czyms, co kancelaria kupuje (zakaz reklamy notariuszy).
    Za pieniadze jest oprogramowanie, nie widocznosc."""
    mapa = wpis.get("mapa") or {}
    return bool(wpis.get("aktywna", True) and wpis.get("na_mapie", False) and mapa.get("lat") is not None)


def _wizytowka(wpis: dict) -> dict:
    """To, co kancelaria publikuje - bez identyfikatora, e-maili i NIP."""
    dane, mapa = wpis.get("dane") or {}, wpis["mapa"]
    return {"nazwa": wpis["nazwa"], "notariusze": dane.get("notariusze", ""),
            "adres": dane.get("adres", ""), "lat": mapa["lat"], "lon": mapa["lon"],
            "dokladnosc": mapa.get("dokladnosc", "adres")}


def stan_mapy(wpis: dict) -> dict:
    """Krotki stan dla panelu administratora."""
    mapa = wpis.get("mapa") or {}
    return {"na_mapie": wpis.get("na_mapie", False), "polozenie": mapa.get("lat") is not None,
            "blad": mapa.get("blad")}


# --- publiczna wyszukiwarka --------------------------------------------------

router = APIRouter(prefix="/api/notariusze", tags=["notariusze"])


PLIK_POLOZEN = Path(__file__).resolve().parent / "seo" / "polozenia.json"
_POLOZENIA: tuple[float, dict] = (-1.0, {})


def polozenia_wykazu() -> dict[int, dict]:
    """Wspolrzedne kancelarii z publicznego wykazu (seo/kancelarie.json),
    wyznaczone wsadowo przez seo/geokoduj_wykaz.py. Brak pliku = pusto."""
    global _POLOZENIA
    try:
        zmiana = PLIK_POLOZEN.stat().st_mtime
    except FileNotFoundError:
        return {}
    if zmiana != _POLOZENIA[0]:
        dane = json.loads(PLIK_POLOZEN.read_text("utf-8"))
        _POLOZENIA = (zmiana, {int(k): v for k, v in dane.get("polozenia", {}).items() if v.get("lat") is not None})
    return _POLOZENIA[1]


def _z_wykazu(k: dict, poz: dict) -> dict:
    return {"id": k["id"], "nazwa": k["nazwa"], "notariusze": k.get("notariusze", ""),
            "adres": k.get("adres", ""), "lat": poz["lat"], "lon": poz["lon"],
            "dokladnosc": poz.get("dokladnosc", "adres"), "telefony": k.get("telefony", []),
            "miejscowosc": k.get("slug", ""), "brak_kontaktu": bool(k.get("brak_kontaktu")),
            "online": False, "zrodlo": "wykaz"}


@router.get("")
def lista(lat: float | None = None, lon: float | None = None):
    """Kancelarie na mapie. Z lat/lon w neutralnej kolejnosci od najblizszej
    (pasma odleglosci + rotacja, rekomendacje.py), z odlegloscia w km.

    Zrodla: caly publiczny wykaz notariuszy z polozeniem (polozenia_wykazu)
    oraz kancelarie z notarai, ktore wlaczyly publikacje, a nie ma ich
    w wykazie. Kancelaria z notarai NIE dostaje lepszego miejsca: dostaje
    tylko znacznik "online" (zgloszenie trafia od razu do aplikacji)."""
    if (lat is None) != (lon is None):
        raise HTTPException(400, "Podaj lat i lon razem.")
    if lat is not None and not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise HTTPException(400, "Wspolrzedne poza zakresem.")
    import wizyty
    rejestr = autoryzacja._wczytaj_rejestr().values()
    polozenia = polozenia_wykazu()
    kancelarie: list[dict] = []
    powiazane: dict[str, int] = {}
    if polozenia:
        baza = wizyty.baza()["kancelarie"]
        kancelarie = [_z_wykazu(baza[i], poz) for i, poz in polozenia.items() if i in baza]
        powiazane = {id_k: i for i, id_k in wizyty.kancelarie_notarai().items()}
    po_id = {k["id"]: k for k in kancelarie}
    for w in rejestr:
        if not publikowana(w):
            continue
        z_wykazu = po_id.get(powiazane.get(w["id"], -1))
        if z_wykazu:
            z_wykazu["online"] = True
        else:
            kancelarie.append({**_wizytowka(w), **({"online": True, "zrodlo": "notarai"} if polozenia else {})})
    if lat is not None:
        for k in kancelarie:
            k["odleglosc_km"] = round(odleglosc_km(lat, lon, k["lat"], k["lon"]), 1)
    # Neutralna kolejnosc: pasma odleglosci, w pasmie codzienna rotacja
    # (rekomendacje.py). Bez alfabetu, ktory stale faworyzuje nazwy na "A".
    kancelarie = rekomendacje.kolejnosc(kancelarie, kontekst="mapa", klucz_id="nazwa")
    return {"kancelarie": kancelarie, "zasady": rekomendacje.WERSJA}


# --- ustawienia kancelarii (po zalogowaniu) ----------------------------------

router_kancelarii = APIRouter(prefix="/api/mapa", tags=["mapa"])


class Widocznosc(BaseModel):
    na_mapie: bool


def _stan_wlasny(wpis: dict) -> dict:
    mapa = wpis.get("mapa") or {}
    return {"na_mapie": wpis.get("na_mapie", False), "publikowana": publikowana(wpis),
            "geokoder": wlaczone(),
            **{k: mapa.get(k) for k in ("adres", "lat", "lon", "dokladnosc", "blad", "sprawdzono")}}


def _wlasciciel(request: Request) -> tuple[dict, dict]:
    rejestr, _, wpis, email = autoryzacja._moja_kancelaria(request)
    if email not in autoryzacja._wlasciciele(wpis):
        raise HTTPException(403, "Mapa notariuszy: ustawienia zmienia wlasciciel kancelarii.")
    return rejestr, wpis


@router_kancelarii.get("")
def moja_mapa(request: Request):
    _, _, wpis, _ = autoryzacja._moja_kancelaria(request)
    return _stan_wlasny(wpis)


@router_kancelarii.put("")
def ustaw_widocznosc(request: Request, dane: Widocznosc):
    rejestr, wpis = _wlasciciel(request)
    wpis["na_mapie"] = dane.na_mapie
    autoryzacja._zapisz_rejestr(rejestr)
    log.info("kancelaria %s: na mapie notariuszy: %s", wpis["id"], dane.na_mapie)
    return _stan_wlasny(wpis)


@router_kancelarii.post("/odswiez")
def odswiez_polozenie(request: Request):
    """Ponowne wyznaczenie polozenia, np. po poprawieniu adresu albo awarii geokodera."""
    rejestr, wpis = _wlasciciel(request)
    if not wlaczone():
        raise HTTPException(503, "Wyznaczanie polozenia jest wylaczone na tym serwerze.")
    if not (wpis.get("dane") or {}).get("adres"):
        raise HTTPException(400, "Najpierw podaj adres kancelarii.")
    ustal_polozenie(wpis, wymus=True)
    autoryzacja._zapisz_rejestr(rejestr)
    return _stan_wlasny(wpis)


# --- panel administratora ----------------------------------------------------

router_admina = APIRouter(prefix="/api/admin/mapa", tags=["admin"])


@router_admina.post("")
def uzupelnij_mape(request: Request, wszystkie: bool = False):
    """Wyznacza polozenie kancelariom, ktore go nie maja: zalozonym przed
    mapa albo po awarii geokodera. `wszystkie=true` wyznacza od nowa."""
    autoryzacja._wymagaj_admina(request)
    if not wlaczone():
        raise HTTPException(503, "Wyznaczanie polozenia jest wylaczone na tym serwerze.")
    rejestr = autoryzacja._wczytaj_rejestr()
    wynik = {"ustalono": 0, "aktualne": 0, "bez_adresu": 0, "bez_polozenia": []}
    for wpis in rejestr.values():
        adres = (wpis.get("dane") or {}).get("adres")
        mapa = wpis.get("mapa") or {}
        if not adres:
            wynik["bez_adresu"] += 1
            continue
        if not wszystkie and mapa.get("lat") is not None and mapa.get("adres") == adres:
            wynik["aktualne"] += 1
            continue
        nowa = ustal_polozenie(wpis, wymus=True) or {}
        if nowa.get("lat") is not None:
            wynik["ustalono"] += 1
        else:
            wynik["bez_polozenia"].append(wpis["nazwa"])
    autoryzacja._zapisz_rejestr(rejestr)
    log.info("mapa notariuszy uzupelniona: %s ustalono, %s bez polozenia",
             wynik["ustalono"], len(wynik["bez_polozenia"]))
    return wynik
