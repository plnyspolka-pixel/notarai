"""Rejestracja kancelarii i dokumenty akceptowane w aplikacji - bez papieru.

Notariusz zaklada konto sam: jeden formularz (/rejestracja) z danymi
kancelarii i akceptacja Regulaminu wraz z umowa powierzenia (Regulamin § 6).
Hasla tymczasowego nie pokazujemy w przegladarce - Cognito wysyla je
e-mailem, wiec konto otworzy tylko ktos, kto ma dostep do tej skrzynki.

Co zapisujemy jako dowod (rejestr kancelarii, zaszyfrowany w S3): wersje
dokumentow, czas, e-mail i adres IP akceptujacego. Adres IP i e-mail nigdy
nie trafiaja do logow.

Po zalogowaniu (/api/dokumenty):
  - wlasciciel kancelarii zalozonej przez administratora akceptuje umowe
    przy pierwszym logowaniu; do tego czasu middleware nie wpuszcza do spraw,
  - kazda osoba potwierdza instrukcje AI (art. 4 AI Act),
  - wlasciciel przyjmuje ocene skutkow (DPIA) wypelniona danymi kancelarii,
  - kazdy moze pobrac dokumenty z danymi swojej kancelarii.

Rejestracje wlacza PIECZAPP_REJESTRACJA=true.
"""
import html
import logging
import os
import re
import secrets
import threading
import time
from collections import deque

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

import autoryzacja
import dokumenty_prawne
import logowanie
import platnosci
import walidacja

log = logging.getLogger("pieczapp.rejestracja")

WLACZONA = os.getenv("PIECZAPP_REJESTRACJA", "false").lower() == "true"

# Kazda rejestracja wysyla e-mail z Cognito, wiec formularz nie moze sluzyc
# do zasypywania obcych skrzynek. Limity na proces (sa dwie kopie aplikacji).
_NA_ADRES_IP = int(os.getenv("PIECZAPP_REJESTRACJE_NA_IP", "3"))         # na godzine
_NA_DOBE = int(os.getenv("PIECZAPP_REJESTRACJE_NA_DOBE", "30"))
_proby_ip: dict[str, deque] = {}
_proby_wszystkie: deque = deque()
_blokada = threading.Lock()


def _limit(adres_ip: str) -> None:
    teraz = time.monotonic()
    with _blokada:
        while _proby_wszystkie and teraz - _proby_wszystkie[0] > 86400:
            _proby_wszystkie.popleft()
        proby = _proby_ip.setdefault(adres_ip, deque())
        while proby and teraz - proby[0] > 3600:
            proby.popleft()
        if len(proby) >= _NA_ADRES_IP or len(_proby_wszystkie) >= _NA_DOBE:
            raise HTTPException(429, "Za dużo rejestracji naraz. Spróbuj za godzinę albo napisz "
                                     "na kontakt@notarai.pl.")
        proby.append(teraz)
        _proby_wszystkie.append(teraz)


def _wyczysc_limity() -> None:
    """Dla testow."""
    _proby_ip.clear()
    _proby_wszystkie.clear()


def _wersje() -> dict:
    return {"regulamin": dokumenty_prawne.wersja("regulamin"),
            "umowa": dokumenty_prawne.wersja("umowa")}


def _zapis_akceptacji(email: str, adres_ip: str, sposob: str) -> dict:
    return {**_wersje(), "zaakceptowano": autoryzacja._teraz(), "email": email,
            "ip": adres_ip, "sposob": sposob}


class DaneKancelarii(BaseModel):
    notariusze: str = ""
    adres: str = ""
    nip: str = ""


def _sprawdz_dane(dane: DaneKancelarii) -> dict:
    notariusze = " ".join(dane.notariusze.split())
    adres = " ".join(dane.adres.split())
    nip = re.sub(r"[\s-]", "", dane.nip)
    if len(notariusze) < 5:
        raise HTTPException(400, "Podaj imię i nazwisko notariusza (w spółce - wszystkich notariuszy).")
    if len(adres) < 8:
        raise HTTPException(400, "Podaj adres kancelarii: ulica, numer, kod i miejscowość.")
    if nip and not walidacja.nip(nip)[0]:
        raise HTTPException(400, "NIP ma błędną sumę kontrolną.")
    if len(notariusze) > 300 or len(adres) > 300:
        raise HTTPException(400, "Za długi tekst.")
    return {"notariusze": notariusze, "adres": adres, "nip": nip}


# --- rejestracja (otwarta) -------------------------------------------------

router = APIRouter(prefix="/api/rejestracja", tags=["rejestracja"])


class Rejestracja(DaneKancelarii):
    nazwa: str
    email: str
    przechowywanie: str = "chmura"
    akceptuje: bool = False
    # Pole niewidoczne dla czlowieka. Wypelnia je tylko automat.
    strona: str = ""


@router.get("")
def informacje():
    return {"wlaczona": WLACZONA and logowanie.wlaczone(), **_wersje(),
            "cena": platnosci.cena(), "okres_probny_dni": platnosci.OKRES_PROBNY_DNI}


@router.post("", status_code=201)
def zarejestruj(dane: Rejestracja, request: Request):
    if not WLACZONA or not logowanie.wlaczone():
        raise HTTPException(503, "Rejestracja jest wyłączona. Napisz na kontakt@notarai.pl.")
    adres_ip = autoryzacja.adres_klienta(request)
    _limit(adres_ip)
    odpowiedz = {"zarejestrowano": True,
                 "komunikat": "Wysłaliśmy e-mail z hasłem tymczasowym. Zaloguj się nim "
                              "na app.notarai.pl i ustaw własne hasło."}
    if dane.strona:
        return odpowiedz   # automat: udajemy sukces, niczego nie zakladamy

    if not dane.akceptuje:
        raise HTTPException(400, "Zaakceptuj Regulamin i umowę powierzenia.")
    nazwa = " ".join(dane.nazwa.split())
    if not 2 <= len(nazwa) <= 120:
        raise HTTPException(400, "Nazwa kancelarii: od 2 do 120 znaków.")
    if dane.przechowywanie not in ("chmura", "u-klienta"):
        raise HTTPException(400, "Wybierz, gdzie mają być pliki.")
    email = autoryzacja._poprawny_email(dane.email)
    firma = _sprawdz_dane(dane)

    rejestr = autoryzacja._wczytaj_rejestr()
    id_k = autoryzacja.nowy_identyfikator(rejestr, nazwa)
    # Najpierw konto: jesli adres jest zajety, nie zostaje osierocona kancelaria.
    try:
        logowanie.utworz_uzytkownika(email, id_k)
    except logowanie.BladLogowania:
        raise HTTPException(409, "Ten adres ma już konto w notarai. Zaloguj się albo użyj "
                                 "„Nie pamiętam hasła”.")
    teraz = autoryzacja._teraz()
    wpis = {
        "id": id_k, "nazwa": nazwa, "aktywna": True, "przechowywanie": dane.przechowywanie,
        "dane": firma,
        "umowa": _zapis_akceptacji(email, adres_ip, "formularz rejestracji"),
        "zespol": [{"email": email, "rola": "wlasciciel", "zaproszono": teraz, "dolaczyl": None}],
    }
    if platnosci.wlaczone():
        wpis["oplacono_do"] = platnosci.na_probe()
    # Token kancelarii jest wymagany przez budowe rejestru; nikt go nie widzi.
    rejestr[autoryzacja._sha(secrets.token_hex(32))] = wpis
    autoryzacja._zapisz_rejestr(rejestr)
    log.info("rejestracja: nowa kancelaria %s, pliki: %s", id_k, dane.przechowywanie)
    return odpowiedz


# --- dokumenty po zalogowaniu ---------------------------------------------

router_dokumentow = APIRouter(prefix="/api/dokumenty", tags=["dokumenty"])


def _ja(request: Request) -> tuple[dict, str, dict, str, bool]:
    rejestr, skrot, wpis, email = autoryzacja._moja_kancelaria(request)
    return rejestr, skrot, wpis, email, email in autoryzacja._wlasciciele(wpis)


def _do_akceptacji(wpis: dict, email: str, wlasciciel: bool) -> list[str]:
    """Czego ta osoba jeszcze nie zaakceptowala. Umowe akceptuje wlasciciel
    raz; nowa wersja dokumentow nie blokuje pracy (Regulamin § 14), ale
    aplikacja o nia prosi."""
    braki = []
    umowa = wpis.get("umowa") or {}
    if wlasciciel and (not umowa.get("zaakceptowano") or umowa.get("umowa") != _wersje()["umowa"]
                       or umowa.get("regulamin") != _wersje()["regulamin"]):
        braki.append("umowa")
    osoba = autoryzacja._osoba(wpis, email) or {}
    if (osoba.get("instrukcja") or {}).get("wersja") != dokumenty_prawne.wersja("instrukcja"):
        braki.append("instrukcja")
    if wlasciciel and (wpis.get("dpia") or {}).get("wersja") != dokumenty_prawne.wersja("dpia"):
        braki.append("dpia")
    return braki


@router_dokumentow.get("")
def stan_dokumentow(request: Request):
    _, _, wpis, email, wlasciciel = _ja(request)
    umowa = wpis.get("umowa") or {}
    return {
        "jestem_wlascicielem": wlasciciel,
        "umowa_zawarta": bool(umowa.get("zaakceptowano")),
        "umowa": {k: umowa.get(k) for k in ("zaakceptowano", "umowa", "regulamin", "sposob")},
        "dpia": {k: (wpis.get("dpia") or {}).get(k) for k in ("przyjeto", "wersja")},
        "dane": wpis.get("dane") or {},
        "do_akceptacji": _do_akceptacji(wpis, email, wlasciciel),
        "dokumenty": [{"nazwa": n, "tytul": dokumenty_prawne.tytul(n),
                       "wersja": dokumenty_prawne.wersja(n)} for n in dokumenty_prawne.DOKUMENTY],
    }


class Akceptacja(DaneKancelarii):
    akceptuje: bool = False


@router_dokumentow.post("/umowa")
def akceptuj_umowe(dane: Akceptacja, request: Request):
    """Wlasciciel akceptuje Regulamin z umowa powierzenia - przy pierwszym
    logowaniu albo po zmianie wersji."""
    rejestr, _, wpis, email, wlasciciel = _ja(request)
    if not wlasciciel:
        raise HTTPException(403, "Umowę akceptuje właściciel kancelarii.")
    if not dane.akceptuje:
        raise HTTPException(400, "Zaznacz akceptację Regulaminu i umowy powierzenia.")
    obecne = wpis.get("dane") or {}
    if dane.notariusze or dane.adres or not obecne.get("notariusze"):
        wpis["dane"] = _sprawdz_dane(dane)
    poprzednia = wpis.get("umowa") or {}
    zapis = _zapis_akceptacji(email, autoryzacja.adres_klienta(request), "akceptacja w aplikacji")
    # Data zawarcia zostaje pierwotna; kolejne akceptacje to zmiany wersji.
    if poprzednia.get("zaakceptowano"):
        zapis["zawarto"] = poprzednia.get("zawarto") or poprzednia["zaakceptowano"]
    wpis["umowa"] = zapis
    autoryzacja._zapisz_rejestr(rejestr)
    log.info("kancelaria %s: zaakceptowano umowe %s", wpis["id"], zapis["umowa"])
    return {"zaakceptowano": zapis["zaakceptowano"]}


@router_dokumentow.post("/instrukcja")
def potwierdz_instrukcje(request: Request):
    rejestr, _, wpis, email, _ = _ja(request)
    osoba = autoryzacja._osoba(wpis, email)
    if osoba is None:
        raise HTTPException(404, "Nie ma Cię w zespole tej kancelarii.")
    osoba["instrukcja"] = {"wersja": dokumenty_prawne.wersja("instrukcja"), "data": autoryzacja._teraz()}
    autoryzacja._zapisz_rejestr(rejestr)
    return osoba["instrukcja"]


@router_dokumentow.post("/dpia")
def przyjmij_dpia(request: Request):
    rejestr, _, wpis, email, wlasciciel = _ja(request)
    if not wlasciciel:
        raise HTTPException(403, "Ocenę skutków przyjmuje właściciel kancelarii (notariusz).")
    wpis["dpia"] = {"wersja": dokumenty_prawne.wersja("dpia"), "przyjeto": autoryzacja._teraz(),
                    "email": email}
    autoryzacja._zapisz_rejestr(rejestr)
    return {"przyjeto": wpis["dpia"]["przyjeto"]}


_PRZECHOWYWANIE = {"chmura": "pliki w chmurze (AWS, Frankfurt)",
                   "u-klienta": "pliki u kancelarii (folder na komputerze kancelarii)"}


def _data(iso: str | None) -> str:
    if not iso:
        return ""
    return f"{iso[8:10]}.{iso[5:7]}.{iso[0:4]}" + (f", godz. {iso[11:16]}" if len(iso) > 11 else "")


def _ramka_umowy(wpis: dict) -> str:
    """Dane stron i potwierdzenie zawarcia - to, co na papierze bylo
    naglowkiem i podpisami."""
    umowa, dane = wpis.get("umowa") or {}, wpis.get("dane") or {}
    if not umowa.get("zaakceptowano"):
        return ('<div class="zawarcie"><p><strong>Umowa nie została jeszcze zawarta.</strong> '
                'Właściciel kancelarii akceptuje ją w aplikacji.</p></div>')
    wiersze = [
        ("Administrator (notariusz)", dane.get("notariusze", "")),
        ("Kancelaria", wpis["nazwa"]),
        ("Adres kancelarii", dane.get("adres", "")),
        ("NIP", dane.get("nip", "") or "-"),
        ("E-mail Administratora (§ 14)", ", ".join(autoryzacja._wlasciciele(wpis))),
        ("Podmiot przetwarzający", "Fundacja Krzewienia Edukacji Finansowej im. Pieczaka, "
                                   "ul. Wilhelma Orlika Ruckemana 4/18, 20-244 Lublin, KRS 0001140846"),
        ("Data zawarcia", _data(umowa.get("zawarto") or umowa.get("zaakceptowano"))),
        ("Sposób zawarcia", f"{umowa.get('sposob', '')}, przez {umowa.get('email', '')}"),
        ("Zaakceptowana wersja", f"umowa {umowa.get('umowa', '')}, regulamin {umowa.get('regulamin', '')}"
                                 + (f", zaakceptowana {_data(umowa['zaakceptowano'])}"
                                    if umowa.get("zawarto") else "")),
    ]
    tabela = "".join(f"<tr><th>{html.escape(k)}</th><td>{html.escape(v)}</td></tr>" for k, v in wiersze)
    return (f'<div class="zawarcie"><h2>Strony i potwierdzenie zawarcia</h2>'
            f"<table>{tabela}</table>"
            "<p>Umowa zawarta w formie elektronicznej (art. 28 ust. 9 RODO) przez akceptację "
            "w aplikacji notarai, bez podpisu.</p></div>")


@router_dokumentow.get("/{nazwa}", response_class=HTMLResponse)
def dokument(nazwa: str, request: Request):
    """Dokument jako strona HTML, z danymi tej kancelarii. Przegladarka
    pobiera go przez api() (z tokenem), nie zwyklym odnosnikiem."""
    if nazwa not in dokumenty_prawne.DOKUMENTY:
        raise HTTPException(404, "Nie ma takiego dokumentu.")
    _, _, wpis, _, _ = _ja(request)
    dane = wpis.get("dane") or {}
    if nazwa == "umowa":
        return dokumenty_prawne.strona(nazwa, przed=_ramka_umowy(wpis))
    if nazwa == "dpia":
        dpia = wpis.get("dpia") or {}
        pola = {
            "kancelaria": wpis["nazwa"], "notariusze": dane.get("notariusze"),
            "data": _data(dpia.get("przyjeto") or autoryzacja._teraz())[:10],
            "iod": "nie wyznaczono albo według dokumentacji kancelarii",
            "przechowywanie": _PRZECHOWYWANIE.get(wpis.get("przechowywanie", "chmura")),
            "uzytkownicy": str(len(autoryzacja._zespol(wpis))),
            "przyjeto": (f"{_data(dpia['przyjeto'])}, {dpia.get('email', '')}" if dpia.get("przyjeto")
                         else "jeszcze nie przyjęto"),
        }
        return dokumenty_prawne.strona(nazwa, pola)
    return dokumenty_prawne.strona(nazwa)
