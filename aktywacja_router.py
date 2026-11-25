"""Endpointy aktywacji rejestrów chronionych (GOV-03). Tylko indywidualne sesje.

Użytkownik: status, wniosek, challenge, złożenie z podpisem, wgranie własnego klucza,
odwołanie. Administrator: przyznanie na podstawie udokumentowanej decyzji instytucji
oraz potwierdzenie statusu zawodowego w KRN. Weryfikacja podpisu kwalifikowanego wymaga
skonfigurowanego weryfikatora (PIECZAPP_WERYFIKATOR_PODPISU); bez niego składanie
wniosków zwraca 503 - nigdy nie przepuszcza niezweryfikowanego podpisu.
"""
import base64
import hashlib
import os
import time

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

import aktywacja_rejestrow as ar
import autoryzacja
import stanowiska

router = APIRouter(prefix="/api/aktywacja", tags=["aktywacja rejestrów"])
_ak = None
_sejf = None
WERYFIKATOR = None  # wstrzykiwany przez moduł weryfikatora podpisu (QTSP); None = wyłączone


def _zbuduj():
    global _ak, _sejf
    if _ak is None:
        import aktywacja_aws as aws
        m = aws.DynamoMagazyn()
        _sejf = aws.SejfSecretsManager()
        _ak = ar.Aktywacje(_WeryfikatorProxy(), ar.KrnReczne(m), _sejf, magazyn=m)
    return _ak


class _WeryfikatorProxy:
    def zweryfikuj(self, podpis):
        if WERYFIKATOR is None:
            raise HTTPException(503, "Weryfikacja podpisu kwalifikowanego nie jest jeszcze skonfigurowana.")
        return WERYFIKATOR.zweryfikuj(podpis)


def _osoba(request):
    if not autoryzacja.MULTI or getattr(request.state, "komputer", None) or getattr(request.state, "serwis", False):
        raise HTTPException(403, "Wymagana indywidualna sesja członka kancelarii.")
    k, e = getattr(request.state, "kancelaria", None), getattr(request.state, "email", None)
    if not k or not e:
        raise HTTPException(401, "Zaloguj się.")
    os_ = autoryzacja._osoba_w_kancelarii(k, e)
    if not os_ or "rejestry" not in stanowiska.uprawnienia(os_):
        raise HTTPException(403, "Brak uprawnień do rejestrów.")
    naglowek = request.headers.get("authorization", "")
    sesja = hashlib.sha256(naglowek.encode()).hexdigest()
    return k, e, sesja


def _blad(fn):
    try:
        return fn()
    except ar.BladAktywacji as ex:
        raise HTTPException(400, str(ex)) from None


@router.get("/{usluga}")
def status(usluga: str, request: Request):
    k, e, _ = _osoba(request)
    if usluga not in ar.CHRONIONE:
        raise HTTPException(404, "Nieznana usługa.")
    return {"usluga": usluga, "status": _zbuduj().status(k, e, usluga)}


@router.post("/{usluga}/wniosek")
def wniosek(usluga: str, request: Request):
    k, e, _ = _osoba(request)
    _blad(lambda: _zbuduj().przygotuj_wniosek(k, e, usluga))
    return {"status": ar.WNIOSEK}


@router.post("/{usluga}/challenge")
def challenge(usluga: str, request: Request):
    k, e, s = _osoba(request)
    return {"challenge": _blad(lambda: _zbuduj().wystaw_challenge(s, k, e, usluga)), "wazny_s": ar.TTL_CHALLENGE_S}


class Zlozenie(BaseModel):
    challenge: str = Field(min_length=20, max_length=128)
    podpis_base64: str = Field(min_length=10, max_length=200_000)
    zgoda_na_zakres: bool = False


@router.post("/{usluga}/zloz")
def zloz(usluga: str, dane: Zlozenie, request: Request):
    k, e, s = _osoba(request)
    try:
        podpis = base64.b64decode(dane.podpis_base64, validate=True)
    except ValueError:
        raise HTTPException(400, "Niepoprawny podpis.") from None
    _blad(lambda: _zbuduj().zloz_z_podpisem(s, k, e, usluga, dane.challenge, podpis, dane.zgoda_na_zakres))
    return {"status": ar.ZLOZONY}


class Klucz(BaseModel):
    wartosc: str = Field(min_length=8, max_length=20_000)


@router.post("/{usluga}/klucz")
def wgraj_klucz(usluga: str, dane: Klucz, request: Request):
    """Notariusz wgrywa SWÓJ klucz po przyznaniu dostępu; wartość trafia wprost do Secrets Manager."""
    k, e, _ = _osoba(request)
    ak = _zbuduj()
    if ak.status(k, e, usluga) not in (ar.PRZYZNANY, ar.SKONFIGUROWANY):
        raise HTTPException(400, "Klucz można wgrać dopiero po przyznaniu dostępu.")
    _sejf.zapisz_klucz(k, e, usluga, dane.wartosc)
    if ak.status(k, e, usluga) == ar.PRZYZNANY:
        _blad(lambda: ak.skonfigurowano(k, e, usluga))
    else:
        _blad(lambda: ak.rotacja_klucza(k, e, usluga))
    return {"status": ar.SKONFIGUROWANY}


@router.post("/{usluga}/odwolaj")
def odwolaj(usluga: str, request: Request):
    k, e, _ = _osoba(request)
    _blad(lambda: _zbuduj().odwolaj(k, e, usluga))
    return {"status": ar.ODWOLANY}


class Przyznanie(BaseModel):
    kancelaria: str = Field(min_length=1, max_length=128)
    email: str = Field(min_length=3, max_length=254)
    usluga: str = Field(min_length=2, max_length=32)
    instytucja: str = Field(min_length=2, max_length=200)
    numer_decyzji: str = Field(min_length=1, max_length=100)
    data_decyzji: str = Field(min_length=10, max_length=10)
    hash_dokumentu: str = Field(min_length=32, max_length=128)
    wazna_do_epoch: float


@router.post("/admin/przyznaj")
def przyznaj(dane: Przyznanie, request: Request):
    autoryzacja._wymagaj_admina(request)
    d = ar.Decyzja(dane.instytucja, dane.numer_decyzji, dane.data_decyzji, dane.hash_dokumentu, dane.wazna_do_epoch)
    _blad(lambda: _zbuduj().przyznaj(dane.kancelaria, dane.email, dane.usluga, d))
    return {"status": ar.PRZYZNANY}


class Krn(BaseModel):
    identyfikator_podpisujacego: str = Field(min_length=3, max_length=200)
    czynny: bool = True


@router.post("/admin/krn")
def krn(dane: Krn, request: Request):
    autoryzacja._wymagaj_admina(request)
    _zbuduj()
    _ak._krn._m.krn_potwierdz(ar._h(dane.identyfikator_podpisujacego), dane.czynny)
    return {"ok": True}
