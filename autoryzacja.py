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

import magazyn

log = logging.getLogger("pieczapp.autoryzacja")

MULTI = os.getenv("PIECZAPP_MULTI", "false").lower() == "true"
ADMIN_TOKEN = os.getenv("PIECZAPP_ADMIN_TOKEN", "")

# Sciezki bez tokenu kancelarii: strona, statyki, zdrowie, panel admina
# (panel ma wlasny token) i favicon.
_OTWARTE = ("/", "/static", "/zdrowie", "/api/admin", "/favicon.ico")

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


async def middleware(request: Request, call_next):
    """Bearer kancelarii -> kontekst kancelarii. Tylko gdy PIECZAPP_MULTI."""
    sciezka = request.url.path
    if not MULTI or sciezka == "/" or any(
        sciezka.startswith(o) for o in _OTWARTE if o != "/"
    ):
        return await call_next(request)

    naglowek = request.headers.get("authorization", "")
    token = naglowek[7:] if naglowek.startswith("Bearer ") else ""
    wpis = _wczytaj_rejestr().get(_sha(token)) if token else None
    if not wpis or not wpis.get("aktywna", True):
        return JSONResponse({"detail": "Brak lub nieprawidlowy token kancelarii"}, 401)

    znacznik = magazyn.kancelaria_var.set(wpis["id"])
    try:
        request.state.kancelaria = wpis["id"]
        return await call_next(request)
    finally:
        magazyn.kancelaria_var.reset(znacznik)


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


class NowaKancelaria(BaseModel):
    nazwa: str


@router.get("/kancelarie")
def lista_kancelarii(request: Request):
    _wymagaj_admina(request)
    rejestr = _wczytaj_rejestr()
    return [
        {"id": w["id"], "nazwa": w["nazwa"], "aktywna": w.get("aktywna", True)}
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

    token = secrets.token_hex(32)
    rejestr[_sha(token)] = {"id": id_k, "nazwa": nazwa, "aktywna": True}
    _zapisz_rejestr(rejestr)
    log.info("kancelaria dodana: %s", id_k)
    return {
        "id": id_k,
        "nazwa": nazwa,
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
