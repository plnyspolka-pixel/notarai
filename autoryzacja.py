"""Autoryzacja per kancelaria (tryb SaaS) + panel administracyjny.

Tryb wielu kancelarii wlacza PIECZAPP_MULTI=true. Wtedy kazde zadanie /api/*
musi niesc naglowek:  Authorization: Bearer <token kancelarii>

Rejestr kancelarii: plik JSON {hash_sha256_tokenu: {"id","nazwa","aktywna"}}.
  - tryb lokalny: dane/kancelarie.json
  - tryb s3:      s3://BUCKET/PREFIKS/admin/kancelarie.json (szyfrowany)
Tokeny NIE sa przechowywane wprost - tylko ich hashe. Token widac raz,
przy utworzeniu kancelarii.

Panel admina (osobny token PIECZAPP_ADMIN_TOKEN, nie tokeny kancelarii):
  GET  /api/admin/kancelarie          lista
  POST /api/admin/kancelarie {nazwa}  utworzenie + jednorazowy token

Zero danych osobowych ani tokenow w logach.
"""
import hashlib
import json
import logging
import os
import re
import secrets
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import logowanie
import magazyn

log = logging.getLogger("pieczapp.autoryzacja")

MULTI = os.getenv("PIECZAPP_MULTI", "false").lower() == "true"
ADMIN_TOKEN = os.getenv("PIECZAPP_ADMIN_TOKEN", "")

# Sciezki bez tokenu kancelarii: strona, statyki, zdrowie, panel admina
# (panel ma wlasny token), logowanie i odzyskiwanie hasla oraz favicon.
_OTWARTE = ("/", "/static", "/zdrowie", "/api/admin", "/api/logowanie", "/favicon.ico")

_CACHE_S: float = 0.0
_CACHE: dict | None = None


def _sha(tekst: str) -> str:
    return hashlib.sha256(tekst.encode()).hexdigest()


def _plik_lokalny() -> Path:
    import config
    return config.DANE / "kancelarie.json"


def _klucz_s3() -> str:
    return f"{magazyn.PREFIKS}/admin/kancelarie.json"


def _wczytaj_rejestr() -> dict:
    """Rejestr kancelarii z cache (60 s), pliku lokalnego albo S3."""
    global _CACHE, _CACHE_S
    if _CACHE is not None and time.monotonic() - _CACHE_S < 60:
        return _CACHE
    dane: dict = {}
    if magazyn.TRYB == "s3":
        try:
            odp = magazyn._klient_s3().get_object(Bucket=magazyn.BUCKET, Key=_klucz_s3())
            dane = json.loads(odp["Body"].read().decode("utf-8"))
        except Exception as blad:  # brak pliku = brak kancelarii
            if type(blad).__name__ not in ("NoSuchKey", "ClientError"):
                raise
    else:
        plik = _plik_lokalny()
        if plik.exists():
            dane = json.loads(plik.read_text("utf-8"))
    _CACHE, _CACHE_S = dane, time.monotonic()
    return dane


def _zapisz_rejestr(dane: dict) -> None:
    global _CACHE, _CACHE_S
    tresc = json.dumps(dane, ensure_ascii=False, indent=2)
    if magazyn.TRYB == "s3":
        magazyn._klient_s3().put_object(
            Bucket=magazyn.BUCKET, Key=_klucz_s3(),
            Body=tresc.encode("utf-8"), **magazyn._szyfrowanie(),
        )
    else:
        _plik_lokalny().write_text(tresc, encoding="utf-8")
    _CACHE, _CACHE_S = dane, time.monotonic()


# --- Middleware -------------------------------------------------------------


def _kancelaria_z_naglowka(token: str):
    """Kancelaria z tokenu logowania albo z dawnego tokenu kancelarii.

    Token logowania (JWT) jest podpisany przez Cognito i niesie kancelarie
    uzytkownika. Dawny token kancelarii zostaje dla zadan automatycznych -
    jest wspolny dla calej kancelarii i nie wskazuje osoby.
    """
    if not token:
        return None
    if logowanie.wlaczone() and logowanie.czy_jwt(token):
        try:
            return logowanie.dane_z_tokenu(token)["kancelaria"]
        except logowanie.BladLogowania:
            return None
    wpis = _wczytaj_rejestr().get(_sha(token))
    if wpis and wpis.get("aktywna", True):
        return wpis["id"]
    return None


async def middleware(request: Request, call_next):
    """Token uzytkownika albo kancelarii -> kontekst. Tylko gdy PIECZAPP_MULTI."""
    sciezka = request.url.path
    if not MULTI or sciezka == "/" or any(
        sciezka.startswith(o) for o in _OTWARTE if o != "/"
    ):
        return await call_next(request)

    naglowek = request.headers.get("authorization", "")
    token = naglowek[7:] if naglowek.startswith("Bearer ") else ""
    kancelaria = _kancelaria_z_naglowka(token)
    if not kancelaria:
        return JSONResponse({"detail": "Zaloguj sie, zeby korzystac z aplikacji."}, 401)

    znacznik = magazyn.kancelaria_var.set(kancelaria)
    znacznik_p = magazyn.przechowywanie_var.set(_przechowywanie(kancelaria))
    try:
        request.state.kancelaria = kancelaria
        return await call_next(request)
    finally:
        magazyn.kancelaria_var.reset(znacznik)
        magazyn.przechowywanie_var.reset(znacznik_p)


def _przechowywanie(kancelaria: str) -> str:
    """Gdzie ta kancelaria trzyma pliki. Domyslnie w chmurze."""
    for wpis in _wczytaj_rejestr().values():
        if wpis["id"] == kancelaria:
            return wpis.get("przechowywanie", "chmura")
    return "chmura"


# --- Panel admina -----------------------------------------------------------

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _wymagaj_admina(request: Request) -> None:
    if not ADMIN_TOKEN:
        raise HTTPException(503, "Panel admina wylaczony: ustaw PIECZAPP_ADMIN_TOKEN")
    if not czy_admin(request):
        raise HTTPException(401, "Nieprawidlowy token administratora")


def czy_admin(request: Request) -> bool:
    """Czy zadanie niesie wazny token administratora. Bez wyjatku - do uzytku
    tam, gdzie brak tokenu nie jest bledem (np. sonda /zdrowie)."""
    if not ADMIN_TOKEN:
        return False
    naglowek = request.headers.get("authorization", "")
    token = naglowek[7:] if naglowek.startswith("Bearer ") else ""
    return secrets.compare_digest(_sha(token), _sha(ADMIN_TOKEN))


# --- logowanie uzytkownikow -------------------------------------------------

router_logowania = APIRouter(prefix="/api/logowanie", tags=["logowanie"])


class DaneLogowania(BaseModel):
    email: str
    haslo: str


class NoweHaslo(BaseModel):
    email: str
    haslo: str
    sesja: str


class ProsbaOKod(BaseModel):
    email: str


class HasloZKodem(BaseModel):
    email: str
    kod: str
    haslo: str


def _wymagaj_logowania() -> None:
    if not logowanie.wlaczone():
        raise HTTPException(503, "Logowanie nie jest skonfigurowane na tym serwerze.")


@router_logowania.post("")
def zaloguj(dane: DaneLogowania):
    _wymagaj_logowania()
    try:
        return logowanie.zaloguj(dane.email.strip().lower(), dane.haslo)
    except logowanie.BladLogowania as blad:
        raise HTTPException(401, str(blad))


@router_logowania.post("/nowe-haslo")
def nowe_haslo(dane: NoweHaslo):
    """Pierwsze logowanie: zamiana hasla z zaproszenia na wlasne."""
    _wymagaj_logowania()
    try:
        return logowanie.ustaw_nowe_haslo(dane.email.strip().lower(), dane.haslo, dane.sesja)
    except logowanie.BladLogowania as blad:
        raise HTTPException(400, str(blad))


@router_logowania.post("/kod")
def wyslij_kod(dane: ProsbaOKod):
    """Wysyla kod odzyskiwania. Odpowiedz jest zawsze taka sama, zeby nie
    zdradzac, czy konto o tym adresie istnieje."""
    _wymagaj_logowania()
    try:
        logowanie.wyslij_kod(dane.email.strip().lower())
    except logowanie.BladLogowania as blad:
        raise HTTPException(429, str(blad))
    return {"wyslano": True}


@router_logowania.post("/kod/potwierdz")
def potwierdz_kod(dane: HasloZKodem):
    _wymagaj_logowania()
    try:
        logowanie.ustaw_haslo_kodem(dane.email.strip().lower(), dane.kod.strip(), dane.haslo)
    except logowanie.BladLogowania as blad:
        raise HTTPException(400, str(blad))
    return {"zmieniono": True}


class NowyUzytkownik(BaseModel):
    email: str
    kancelaria: str


@router.post("/uzytkownicy", status_code=201)
def dodaj_uzytkownika(request: Request, dane: NowyUzytkownik):
    """Zaklada konto w kancelarii i wysyla zaproszenie z haslem tymczasowym."""
    _wymagaj_admina(request)
    _wymagaj_logowania()
    kancelaria = dane.kancelaria.strip()
    if kancelaria not in {w["id"] for w in _wczytaj_rejestr().values()}:
        raise HTTPException(404, "Nie znaleziono kancelarii o takim identyfikatorze")
    try:
        logowanie.utworz_uzytkownika(dane.email.strip().lower(), kancelaria)
    except logowanie.BladLogowania as blad:
        raise HTTPException(409, str(blad))
    return {"utworzono": True, "kancelaria": kancelaria}


class NowaKancelaria(BaseModel):
    nazwa: str
    # "chmura": pliki w S3 we Frankfurcie. "u-klienta": serwer niczego nie
    # zapisuje, pliki zostaja na dysku kancelarii. Decyzja zapada przy
    # zakladaniu konta, bo zmiana w trakcie zostawialaby sprawy w dwoch
    # miejscach naraz.
    przechowywanie: str = "chmura"


@router.get("/kancelarie")
def lista_kancelarii(request: Request):
    _wymagaj_admina(request)
    rejestr = _wczytaj_rejestr()
    return [
        {"id": w["id"], "nazwa": w["nazwa"], "aktywna": w.get("aktywna", True),
         "przechowywanie": w.get("przechowywanie", "chmura")}
        for w in rejestr.values()
    ]


@router.post("/kancelarie", status_code=201)
def dodaj_kancelarie(request: Request, dane: NowaKancelaria):
    _wymagaj_admina(request)
    nazwa = dane.nazwa.strip()
    if len(nazwa) < 2:
        raise HTTPException(400, "Nazwa kancelarii: minimum 2 znaki")

    id_k = re.sub(r"[^a-z0-9]+", "-", nazwa.lower()).strip("-")[:40] or "kancelaria"
    rejestr = _wczytaj_rejestr()
    zajete = {w["id"] for w in rejestr.values()}
    if id_k in zajete:
        id_k = f"{id_k}-{secrets.token_hex(3)}"

    if dane.przechowywanie not in ("chmura", "u-klienta"):
        raise HTTPException(400, "Przechowywanie: 'chmura' albo 'u-klienta'")

    token = secrets.token_hex(32)
    rejestr[_sha(token)] = {
        "id": id_k,
        "nazwa": nazwa,
        "aktywna": True,
        "przechowywanie": dane.przechowywanie,
    }
    _zapisz_rejestr(rejestr)
    log.info("kancelaria dodana: %s, pliki: %s", id_k, dane.przechowywanie)
    return {
        "id": id_k,
        "nazwa": nazwa,
        "przechowywanie": dane.przechowywanie,
        "token": token,
        "uwaga": "Zapisz token teraz - nie da sie go odczytac ponownie.",
    }


@router.delete("/kancelarie/{id_k}")
def dezaktywuj_kancelarie(request: Request, id_k: str):
    _wymagaj_admina(request)
    rejestr = _wczytaj_rejestr()
    trafiono = False
    for wpis in rejestr.values():
        if wpis["id"] == id_k:
            wpis["aktywna"] = False
            trafiono = True
    if not trafiono:
        raise HTTPException(404, "Nie znaleziono kancelarii")
    _zapisz_rejestr(rejestr)
    log.info("kancelaria dezaktywowana: %s", id_k)
    return {"id": id_k, "aktywna": False}
