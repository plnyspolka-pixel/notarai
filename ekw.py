"""Tresc ksiegi wieczystej z EKW - przez dostawce, na zadanie notariusza.

Przegladarka EKW (przegladarka-ekw.ms.gov.pl) nie ma API i odrzuca ruch
z serwerow kodem 403, wiec serwer notarai nie czyta jej sam. Dostawcy:

- **Finance You** (domyslny, gdy skonfigurowany): API partnerskie
  /api/public/partner-kw. Finance You sam dobiera zrodlo (Apify, EasyMKW/CMD)
  i oddaje piec dzialow jako tekst + HTML. W procedurze kancelarii dostawca
  tresci KW to Finance You; jego poddostawcy sa opisani w docs/ochrona-danych.md.
- **Apify** (zapasowy / samodzielny): aktor `regdata/ekw-ksiegi-wieczyste-scraper`,
  jedna ksiega = jeden platny wynik.

Zasady (SPEC A, docs/rejestry.md):
- jedna ksiega na zadanie, z odstepem; bez masowego pobierania i bez lokalnej
  kopii rejestru - tresc trafia tylko do sprawy, ktorej dotyczy;
- przy Apify po odczycie kasujemy u dostawcy zbior wynikow i magazyn zadania,
  zeby dane stron (dzial II zawiera imiona, czasem PESEL) nie lezaly tam dluzej;
- w logach tylko identyfikator sprawy, status i czas - bez numeru KW i tresci;
- to nie jest odpis urzedowy; notariusz porownuje ze zrodlem.

Konfiguracja (w chmurze z Secrets Manager): PIECZAPP_FINYOU_URL +
PIECZAPP_FINYOU_TOKEN (Finance You) albo PIECZAPP_APIFY_TOKEN (Apify). Bez
zadnego z nich modul jest nieaktywny i interfejs nie pokazuje przycisku.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from datetime import datetime
from pathlib import Path

import httpx

import config
import rejestry
import walidacja

log = logging.getLogger("pieczapp.ekw")

AKTOR = "regdata~ekw-ksiegi-wieczyste-scraper"
ADRES_API = "https://api.apify.com/v2"
PORTAL = "przegladarka-ekw.ms.gov.pl"
ZRODLO_APIFY = f"{PORTAL} (przez Apify {AKTOR.replace('~', '/')})"
ZRODLO_FINYOU = "Finance You (API partnerskie) - dostawca tresci KW"
ZRODLO = ZRODLO_APIFY  # zgodnosc wsteczna; aktualne zrodlo daje zrodlo()
# Dzialy w odpowiedzi Finance You (klucze kw_documents) -> oznaczenie dzialu.
SEKCJE_FINYOU = (
    ("dzial_1o", "I-O"),
    ("dzial_1s", "I-Sp"),
    ("dzial_2", "II"),
    ("dzial_3", "III"),
    ("dzial_4", "IV"),
)
ODSTEP_FINYOU_S = 5.0  # miedzy dopytaniami, gdy Finance You dopiero pobiera
CZAS_FINYOU_S = 60     # ile Finance You czeka w jednym zadaniu (maks. 50 s + zapas)
# Kolejnosc jak w wydruku z EKW. Klucz aktora -> oznaczenie dzialu.
DZIALY = (
    ("dzialIO", "I-O"),
    ("dzialISp", "I-Sp"),
    ("dzialII", "II"),
    ("dzialIII", "III"),
    ("dzialIV", "IV"),
)
ODSTEP_S = 2.0      # miedzy pobraniami - ograniczenie po naszej stronie
CZAS_S = 240        # tyle czekamy na aktora; portal bywa powolny
KATALOG = "ksiegi"  # dane/sprawy/<id>/ksiegi/<numer>.json i .txt

# Komunikaty aktora o ksiedze, ktorej nie ma w rejestrze (zapis ERRORS).
_NIE_ZNALEZIONO = re.compile(r"not found|does not exist|nie istnieje|nie znaleziono|brak ksi", re.I)

_blokada = threading.Lock()
_ostatnie = 0.0


class BladEKW(Exception):
    """Pobranie sie nie udalo. `kod` mowi dlaczego, komunikat jest dla notariusza.

    Kody: brak_tokenu, blad_tokenu, limit, nie_znaleziono, niepelny, niedostepny.
    Zaden komunikat nie zawiera tresci ksiegi ani danych stron.
    """

    def __init__(self, kod: str, komunikat: str):
        super().__init__(komunikat)
        self.kod = kod


def token() -> str:
    return os.getenv("PIECZAPP_APIFY_TOKEN", "").strip()


def finyou_adres() -> str:
    return os.getenv("PIECZAPP_FINYOU_URL", "").strip().rstrip("/")


def finyou_token() -> str:
    return os.getenv("PIECZAPP_FINYOU_TOKEN", "").strip()


def dostawca() -> str:
    """'finyou' | 'apify' | '' - Finance You ma pierwszenstwo, gdy skonfigurowane."""
    if finyou_adres() and finyou_token():
        return "finyou"
    if token():
        return "apify"
    return ""


def dostepne() -> bool:
    """Czy ta instalacja ma czym pobierac. Decyduje o przycisku w interfejsie."""
    return bool(dostawca())


def zrodlo() -> str:
    return ZRODLO_FINYOU if dostawca() == "finyou" else ZRODLO_APIFY


def normalizuj_numer(numer: str) -> str:
    """'wa4m/00160286/2 ' -> 'WA4M/00160286/2'. Zly numer = ValueError."""
    tekst = re.sub(r"\s+", "", (numer or "").upper())
    poprawny, komunikat = walidacja.ksiega_wieczysta(tekst)
    if not poprawny:
        raise ValueError(komunikat)
    return tekst


def nazwa_pliku(numer: str) -> str:
    return numer.replace("/", "_")


def _klient() -> httpx.Client:
    # Token w naglowku, nie w adresie: adres trafia do komunikatow bledow httpx.
    return httpx.Client(
        base_url=ADRES_API,
        headers={"Authorization": "Bearer " + token()},
        timeout=httpx.Timeout(CZAS_S + 30, connect=20),
    )


def _odczekaj() -> None:
    global _ostatnie
    with _blokada:
        przerwa = ODSTEP_S - (time.monotonic() - _ostatnie)
        if przerwa > 0:
            time.sleep(przerwa)
        _ostatnie = time.monotonic()


def _tekst_wpisow(dzial: dict) -> str:
    """Wpisy dzialu jako czytelny tekst - taki, jaki notariusz zna z wydruku."""
    wiersze: list[str] = []
    for wpis in dzial.get("entries") or []:
        if isinstance(wpis, dict):
            etykieta, wartosc = wpis.get("label"), wpis.get("value")
            if etykieta is not None or wartosc is not None:
                wiersze.append(f"{etykieta or ''}: {wartosc or ''}".strip(": ").strip())
            else:
                wiersze.append(json.dumps(wpis, ensure_ascii=False))
        elif wpis not in (None, ""):
            wiersze.append(str(wpis))
    if not wiersze and dzial.get("rawText"):
        wiersze.append(str(dzial["rawText"]).strip())
    return "\n".join(w for w in wiersze if w)


def _dzial(rekord: dict, klucz: str, oznaczenie: str) -> dict:
    dzial = rekord.get(klucz)
    if not isinstance(dzial, dict) or dzial.get("available") is False:
        raise BladEKW("niepelny", f"Nie udalo sie odczytac dzialu {oznaczenie} - ksiega odrzucona w calosci")
    pusty = dzial.get("empty") is True
    tekst = _tekst_wpisow(dzial)
    if not pusty and not tekst:
        raise BladEKW("niepelny", f"Dzial {oznaczenie} bez tresci i bez oznaczenia BRAK WPISOW - ksiega odrzucona")
    return {
        "oznaczenie": oznaczenie,
        "tytul": str(dzial.get("title") or f"DZIAL {oznaczenie}"),
        "pusty": pusty,
        "tekst": "BRAK WPISÓW" if pusty else tekst,
    }


def z_rekordu(rekord: dict, numer: str) -> dict:
    """Rekord aktora -> ksiega w ukladzie notarai. Kazdy dzial musi byc odczytany."""
    if not isinstance(rekord, dict) or rekord.get("success") is False:
        raise BladEKW("niedostepny", "Aktor nie potwierdzil odczytu ksiegi")
    zwrocony = re.sub(r"\s+", "", str(rekord.get("kwNumber") or "").upper())
    if zwrocony != numer:
        raise BladEKW("niedostepny", "Dostawca zwrocil inna ksiege niz zadana")
    if rekord.get("viewType") not in (None, "aktualna"):
        raise BladEKW("niedostepny", "Dostawca zwrocil inny widok niz aktualna tresc ksiegi")
    return {
        "numer_kw": numer,
        "kod_sadu": str(rekord.get("courtCode") or numer[:4]),
        "sad": str(rekord.get("courtName") or ""),
        "typ": str(rekord.get("propertyType") or ""),
        "widok": "aktualna",
        "dzialy": [_dzial(rekord, klucz, oznaczenie) for klucz, oznaczenie in DZIALY],
        "pobrano": datetime.now().isoformat(timespec="seconds"),
        "zrodlo": ZRODLO_APIFY,
        "dostawca": "apify",
    }


# ── Finance You jako dostawca ─────────────────────────────────────────────────

_WIERSZ_OKLADKI = re.compile(r"^\s*{}\s*\|\s*(.+?)\s*$", re.I | re.M)


def _z_okladki(tekst: str, etykieta: str) -> str:
    """Wartosc z wiersza okladki w formacie 'Etykieta | wartosc' (tekst z HTML EKW)."""
    m = re.search(_WIERSZ_OKLADKI.pattern.format(re.escape(etykieta)), tekst or "", re.I | re.M)
    return m.group(1).strip() if m else ""


def z_odpowiedzi_finyou(dane: dict, numer: str) -> dict:
    """Odpowiedz /api/public/partner-kw -> ksiega w ukladzie notarai."""
    if not isinstance(dane, dict):
        raise BladEKW("niedostepny", "Niezrozumiala odpowiedz Finance You")
    status = dane.get("status")
    if status == "not_found":
        raise BladEKW("nie_znaleziono", "Ksiegi o tym numerze nie ma w rejestrze")
    if status == "processing":
        raise BladEKW("niedostepny", "Finance You jeszcze pobiera ksiege - sprobuj za chwile")
    sekcje = dane.get("sections")
    if status != "ready" or not isinstance(sekcje, dict):
        powod = str(dane.get("error") or "brak tresci")[:300]
        raise BladEKW("niedostepny", f"Finance You nie oddalo ksiegi: {powod}")
    zwrocony = re.sub(r"\s+", "", str(dane.get("kw_number") or "").upper())
    if zwrocony != numer:
        raise BladEKW("niedostepny", "Dostawca zwrocil inna ksiege niz zadana")
    dzialy = []
    for klucz, oznaczenie in SEKCJE_FINYOU:
        s = sekcje.get(klucz)
        if not isinstance(s, dict):
            raise BladEKW("niepelny", f"Nie udalo sie odczytac dzialu {oznaczenie} - ksiega odrzucona w calosci")
        tekst = str(s.get("text") or "").strip()
        pusty = s.get("empty") is True
        if not pusty and not tekst:
            raise BladEKW("niepelny", f"Dzial {oznaczenie} bez tresci i bez oznaczenia BRAK WPISOW - ksiega odrzucona")
        dzialy.append({
            "oznaczenie": oznaczenie,
            "tytul": str(s.get("label") or f"DZIAL {oznaczenie}"),
            "pusty": pusty,
            "tekst": "BRAK WPISÓW" if pusty else tekst,
        })
    okladka = str((sekcje.get("okladka") or {}).get("text") or "")
    pierwotne = str(dane.get("provider") or "nieznane")
    return {
        "numer_kw": numer,
        "kod_sadu": numer[:4],
        "sad": _z_okladki(okladka, "Sąd rejonowy") or _z_okladki(okladka, "Sad rejonowy"),
        "typ": _z_okladki(okladka, "Typ księgi") or _z_okladki(okladka, "Typ ksiegi"),
        "widok": "aktualna",
        "dzialy": dzialy,
        "pobrano": datetime.now().isoformat(timespec="seconds"),
        "zrodlo": f"{ZRODLO_FINYOU}; zrodlo pierwotne: {pierwotne}",
        "dostawca": "finyou",
    }


def _klient_finyou() -> httpx.Client:
    return httpx.Client(
        base_url=finyou_adres(),
        headers={"Authorization": "Bearer " + finyou_token(), "Accept": "application/json"},
        timeout=httpx.Timeout(CZAS_FINYOU_S + 30, connect=20),
    )


def _odpowiedz_finyou(odp) -> dict:
    if odp.status_code in (401, 403):
        raise BladEKW("blad_tokenu", "Finance You odrzucilo token - sprawdz PIECZAPP_FINYOU_TOKEN")
    if odp.status_code == 429:
        raise BladEKW("limit", "Finance You: za duzo zapytan - sprobuj pozniej")
    if odp.status_code >= 500:
        raise BladEKW("niedostepny", f"Finance You odpowiedzialo kodem {odp.status_code}")
    try:
        dane = odp.json()
    except ValueError:
        raise BladEKW("niedostepny", "Niezrozumiala odpowiedz Finance You")
    if odp.status_code >= 400:
        raise BladEKW("niedostepny", f"Finance You: {str((dane or {}).get('error') or odp.status_code)[:200]}")
    return dane


def pobierz_finyou(numer: str, klient: httpx.Client | None = None) -> dict:
    """Jedna ksiega z Finance You. Gdy dostawca dopiero pobiera, dopytuje do CZAS_S."""
    numer = normalizuj_numer(numer)
    if not (finyou_adres() and finyou_token()):
        raise BladEKW("brak_tokenu", "Finance You nie jest skonfigurowane (PIECZAPP_FINYOU_URL / PIECZAPP_FINYOU_TOKEN)")
    _odczekaj()
    wlasny = klient is None
    k = klient or _klient_finyou()
    try:
        try:
            odp = k.post("/api/public/partner-kw", json={"kw": numer, "wait_seconds": 50})
        except httpx.TimeoutException:
            raise BladEKW("niedostepny", "Finance You nie odpowiedzialo w czasie - sprobuj pozniej")
        except httpx.HTTPError as blad:
            raise BladEKW("niedostepny", f"Brak polaczenia z Finance You ({type(blad).__name__})")
        dane = _odpowiedz_finyou(odp)
        koniec = time.monotonic() + CZAS_S
        while isinstance(dane, dict) and dane.get("status") == "processing" and time.monotonic() < koniec:
            time.sleep(ODSTEP_FINYOU_S)
            try:
                odp = k.get("/api/public/partner-kw", params={"kw": numer})
            except httpx.HTTPError as blad:
                raise BladEKW("niedostepny", f"Brak polaczenia z Finance You ({type(blad).__name__})")
            dane = _odpowiedz_finyou(odp)
        return z_odpowiedzi_finyou(dane, numer)
    finally:
        if wlasny:
            k.close()


def do_tekstu(ksiega: dict) -> str:
    """Caly odczyt jako tekst - do zapisu w sprawie i do wklejenia w materialy."""
    linie = [
        f"KSIĘGA WIECZYSTA {ksiega['numer_kw']}",
        f"Sąd: {ksiega.get('sad') or 'brak danych'}",
        f"Typ nieruchomości: {ksiega.get('typ') or 'brak danych'}",
        f"Treść aktualna, pobrano {ksiega['pobrano'].replace('T', ' ')} z {ksiega['zrodlo']}",
        "To nie jest odpis urzędowy - porównaj ze źródłem.",
    ]
    for dzial in ksiega["dzialy"]:
        linie += ["", dzial["tytul"], dzial["tekst"]]
    return "\n".join(linie) + "\n"


def podsumowanie(ksiega: dict) -> tuple[str, str]:
    """Status do sladu audytowego: 'wpis' gdy dzial III albo IV cos zawiera."""
    stany = {d["oznaczenie"]: ("brak wpisów" if d["pusty"] else "wpisy") for d in ksiega["dzialy"]}
    obciazona = any(not d["pusty"] for d in ksiega["dzialy"] if d["oznaczenie"] in ("III", "IV"))
    opis = ", ".join(f"dz. {o}: {s}" for o, s in stany.items())
    return ("wpis" if obciazona else "brak_wpisu"), opis


def _zapis_bledow(klient: httpx.Client, magazyn_id: str | None) -> str:
    if not magazyn_id:
        return ""
    try:
        odp = klient.get(f"/key-value-stores/{magazyn_id}/records/ERRORS")
    except httpx.HTTPError:
        return ""
    return odp.text[:2000] if odp.status_code == 200 else ""


def _posprzataj(klient: httpx.Client, zbior: str | None, magazyn_id: str | None) -> None:
    """Kasuje u dostawcy wyniki i magazyn zadania. Niepowodzenie tylko ostrzega."""
    for sciezka in (f"/datasets/{zbior}" if zbior else None,
                    f"/key-value-stores/{magazyn_id}" if magazyn_id else None):
        if not sciezka:
            continue
        try:
            odp = klient.delete(sciezka)
            if odp.status_code >= 400 and odp.status_code != 404:
                log.warning("EKW: nie udalo sie skasowac danych u dostawcy (%d)", odp.status_code)
        except httpx.HTTPError as blad:
            log.warning("EKW: nie udalo sie skasowac danych u dostawcy (%s)", type(blad).__name__)


def pobierz(numer: str, klient: httpx.Client | None = None) -> dict:
    """Jedna ksiega, aktualna tresc, wszystkie dzialy - od skonfigurowanego dostawcy."""
    if dostawca() == "finyou":
        return pobierz_finyou(numer, klient)
    return pobierz_apify(numer, klient)


def pobierz_apify(numer: str, klient: httpx.Client | None = None) -> dict:
    """Jedna ksiega przez aktora Apify. Czeka na wynik aktora."""
    numer = normalizuj_numer(numer)
    if not token():
        raise BladEKW("brak_tokenu", "Pobieranie z EKW nie jest wlaczone w tej instalacji (PIECZAPP_APIFY_TOKEN)")
    _odczekaj()
    wlasny = klient is None
    k = klient or _klient()
    zbior = magazyn_id = None
    try:
        try:
            odp = k.post(
                f"/acts/{AKTOR}/run-sync",
                params={"timeout": CZAS_S, "memory": 1024},
                json={"kwNumbers": [numer], "viewType": "aktualna",
                      "includeRawHtml": False, "maxConcurrency": 1},
            )
        except httpx.TimeoutException:
            raise BladEKW("niedostepny", "Portal EKW nie odpowiedzial w czasie - sprobuj pozniej")
        except httpx.HTTPError as blad:
            raise BladEKW("niedostepny", f"Brak polaczenia z dostawca ({type(blad).__name__})")
        if odp.status_code in (401, 403):
            raise BladEKW("blad_tokenu", "Dostawca odrzucil token - sprawdz PIECZAPP_APIFY_TOKEN")
        if odp.status_code in (402, 429):
            raise BladEKW("limit", "Wyczerpany limit albo saldo konta u dostawcy")
        if odp.status_code == 408:
            raise BladEKW("niedostepny", "Portal EKW nie odpowiedzial w czasie - sprobuj pozniej")
        if odp.status_code >= 400:
            raise BladEKW("niedostepny", f"Dostawca odpowiedzial kodem {odp.status_code}")
        try:
            zadanie = odp.json().get("data") or {}
        except ValueError:
            raise BladEKW("niedostepny", "Niezrozumiala odpowiedz dostawcy")
        zbior, magazyn_id = zadanie.get("defaultDatasetId"), zadanie.get("defaultKeyValueStoreId")
        rekordy: list = []
        if zbior:
            try:
                wyniki = k.get(f"/datasets/{zbior}/items", params={"clean": "true"})
                rekordy = wyniki.json() if wyniki.status_code == 200 else []
            except (httpx.HTTPError, ValueError):
                rekordy = []
        if not rekordy:
            bledy = _zapis_bledow(k, magazyn_id)
            if _NIE_ZNALEZIONO.search(bledy):
                raise BladEKW("nie_znaleziono", "Ksiegi o tym numerze nie ma w rejestrze")
            if zadanie.get("statusMessage") and _NIE_ZNALEZIONO.search(str(zadanie["statusMessage"])):
                raise BladEKW("nie_znaleziono", "Ksiegi o tym numerze nie ma w rejestrze")
            if "allowance" in bledy.lower() or "allowance" in str(zadanie.get("statusMessage") or "").lower():
                raise BladEKW("limit", "Wyczerpany limit bezplatnego planu u dostawcy")
            raise BladEKW("niedostepny",
                          f"Portal EKW nie oddal ksiegi (stan zadania: {zadanie.get('status') or 'nieznany'})")
        return z_rekordu(rekordy[0], numer)
    finally:
        _posprzataj(k, zbior, magazyn_id)
        if wlasny:
            k.close()


def zapisz(identyfikator: str, ksiega: dict) -> Path:
    """Tresc do sprawy (JSON + tekst) i wpis w sladzie audytowym."""
    katalog = config.SPRAWY / identyfikator / KATALOG
    katalog.mkdir(parents=True, exist_ok=True)
    nazwa = nazwa_pliku(ksiega["numer_kw"])
    (katalog / f"{nazwa}.json").write_text(json.dumps(ksiega, ensure_ascii=False, indent=2), encoding="utf-8")
    (katalog / f"{nazwa}.txt").write_text(do_tekstu(ksiega), encoding="utf-8")
    status, opis = podsumowanie(ksiega)
    rejestry.zapisz_sprawdzenie(identyfikator, rejestry.WynikSprawdzenia(
        rejestr="EKW", zapytanie=ksiega["numer_kw"], status=status,
        szczegoly=opis, zrodlo=ksiega.get("zrodlo") or zrodlo(), etykieta=ksiega["numer_kw"],
    ))
    return katalog / f"{nazwa}.json"


def wynik_bledu(numer: str, blad: BladEKW) -> rejestry.WynikSprawdzenia:
    """Nieudane pobranie tez zostaje w sladzie - jako dowod proby, nie wyniku."""
    status = "blad" if blad.kod in ("nie_znaleziono", "niepelny") else "niedostepny"
    return rejestry.WynikSprawdzenia(
        rejestr="EKW", zapytanie=numer, status=status, szczegoly=str(blad),
        zrodlo=zrodlo(), etykieta=numer,
    )


def wczytaj(identyfikator: str) -> list[dict]:
    """Ksiegi pobrane do sprawy, od najnowszej."""
    katalog = config.SPRAWY / identyfikator / KATALOG
    if not katalog.is_dir():
        return []
    ksiegi = []
    for plik in katalog.glob("*.json"):
        try:
            ksiegi.append(json.loads(plik.read_text("utf-8")))
        except (ValueError, OSError):
            log.warning("sprawa %s: uszkodzony zapis ksiegi", identyfikator)
    return sorted(ksiegi, key=lambda k: k.get("pobrano", ""), reverse=True)


# ── Tresc ksiegi jako zrodlo projektu aktu ───────────────────────────────────
# Pobrana ksiega trafia do modelu przy sporzadzaniu projektu, zeby notariusz nie
# przepisywal jej recznie. Model dostaje ja jako osobne zrodlo (prompty.blok_ksiag),
# a my porownujemy ja z polami odczytu - to podpowiedz, nie rozstrzygniecie.

_NUMER_KW = re.compile(r"\b([A-Z0-9]{4})\s*/\s*(\d{8})\s*/\s*(\d)\b", re.I)


def numery_w_tekscie(tekst: str) -> set[str]:
    """Numery KW wystepujace w tekscie, w postaci znormalizowanej."""
    return {f"{a}/{b}/{c}".upper() for a, b, c in _NUMER_KW.findall(tekst or "")}


def do_projektu(identyfikator: str, pola: list[dict], polecenie: str = "") -> list[dict]:
    """Ksiegi sprawy, ktore maja trafic do projektu.

    Gdy pola odczytu albo polecenie wymieniaja numery KW, bierzemy tylko ksiegi
    o tych numerach (np. pobrana przez pomylke inna ksiega nie trafi do aktu).
    Gdy zaden numer KW nie wystepuje - wszystkie ksiegi pobrane do tej sprawy.
    Przy kilku pobraniach tej samej ksiegi zostaje najnowsze.
    """
    ksiegi = wczytaj(identyfikator)
    if not ksiegi:
        return []
    znane = set()
    for pole in pola or []:
        znane |= numery_w_tekscie(str(pole.get("wartosc") or ""))
    znane |= numery_w_tekscie(polecenie)
    wynik, widziane = [], set()
    for k in ksiegi:  # od najnowszej
        numer = k.get("numer_kw")
        if not numer or numer in widziane or not isinstance(k.get("dzialy"), list):
            continue
        if znane and numer not in znane:
            continue
        widziane.add(numer)
        wynik.append(k)
    return wynik


def _bez_ogonkow(tekst: str) -> str:
    import unicodedata
    tekst = unicodedata.normalize("NFKD", (tekst or "").replace("ł", "l").replace("Ł", "L"))
    return "".join(z for z in tekst if not unicodedata.combining(z)).lower()


def _tekst_dzialu(ksiega: dict, oznaczenie: str) -> str:
    for d in ksiega.get("dzialy") or []:
        if d.get("oznaczenie") == oznaczenie:
            return "" if d.get("pusty") else str(d.get("tekst") or "")
    return ""


_POLE_WLASCICIEL = re.compile(r"wlasciciel|zbyw|sprzeda|darczyn|darujac", re.I)
_POLE_POWIERZCHNIA = re.compile(r"powierzchn|obszar|metraz", re.I)
_LICZBA = re.compile(r"\d+(?:[.,]\d+)?")


def _liczby(tekst: str) -> set[str]:
    wynik = set()
    tekst = re.sub(r"m\s*2\b|m²|\b\d+\s*/\s*\d+\b", " ", tekst or "")  # jednostka i udzialy to nie powierzchnia
    for l in _LICZBA.findall(tekst):
        try:
            wynik.add(f"{float(l.replace(',', '.')):g}")
        except ValueError:
            pass
    return wynik


def porownaj_z_polami(ksiegi: list[dict], pola: list[dict]) -> list[dict]:
    """Weryfikacja odczytu tresci ksiegi - heurystyka, ostroznie.

    Zwraca [{"pole", "ksiega", "stan": "potwierdza"|"rozbieznosc", "opis"}].
    Sprawdzamy tylko to, co da sie porownac pewnie: numer KW, wlasciciela
    (wszystkie slowa wartosci w dziale II) i powierzchnie (liczba w dziale I-O).
    Opis nie zawiera wartosci pol - idzie do interfejsu i do modelu, nie do logow.
    """
    wyniki: list[dict] = []
    if not ksiegi:
        return wyniki
    for pole in pola or []:
        nazwa, wartosc = str(pole.get("nazwa") or ""), str(pole.get("wartosc") or "").strip()
        if not wartosc or nazwa.startswith("STALE: zestawienie"):
            continue
        nazwa_n = _bez_ogonkow(nazwa)
        numery = numery_w_tekscie(wartosc)
        for k in ksiegi:
            numer = k["numer_kw"]
            if numery and numer in numery:
                wyniki.append({"pole": nazwa, "ksiega": numer, "stan": "potwierdza",
                               "opis": "numer księgi zgodny z pobraną treścią"})
                continue
            if len(ksiegi) > 1 and numery and numer not in numery:
                continue  # pole dotyczy innej ksiegi sprawy
            if _POLE_WLASCICIEL.search(nazwa_n):
                dz2 = _bez_ogonkow(_tekst_dzialu(k, "II"))
                slowa = [s for s in re.findall(r"[^\W\d_]{3,}", _bez_ogonkow(wartosc))]
                # Tylko imie i nazwisko (albo dwie osoby); adres w polu dalby falszywy alarm.
                if not dz2 or not slowa or len(slowa) > 5:
                    continue
                if all(s in dz2 for s in slowa):
                    wyniki.append({"pole": nazwa, "ksiega": numer, "stan": "potwierdza",
                                   "opis": "osoba wpisana w dziale II"})
                else:
                    wyniki.append({"pole": nazwa, "ksiega": numer, "stan": "rozbieznosc",
                                   "opis": "w dziale II księgi wpisany jest inny właściciel niż w polu odczytu"})
            elif _POLE_POWIERZCHNIA.search(nazwa_n):
                dz1 = _tekst_dzialu(k, "I-O")
                z_pola = _liczby(wartosc)
                if not dz1 or not z_pola:
                    continue
                if z_pola & _liczby(dz1):
                    wyniki.append({"pole": nazwa, "ksiega": numer, "stan": "potwierdza",
                                   "opis": "powierzchnia jak w dziale I-O"})
                else:
                    wyniki.append({"pole": nazwa, "ksiega": numer, "stan": "rozbieznosc",
                                   "opis": "w dziale I-O księgi jest inna powierzchnia niż w polu odczytu"})
    return wyniki
