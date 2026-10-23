"""Autoryzacja per kancelaria (tryb SaaS) + panel administracyjny.

Tryb wielu kancelarii wlacza PIECZAPP_MULTI=true. Wtedy kazde zadanie /api/*
musi niesc naglowek:  Authorization: Bearer <token kancelarii>

Rejestr kancelarii: plik JSON {hash_sha256_tokenu: {"id","nazwa","aktywna"}}.
  - tryb lokalny: dane/kancelarie.json
  - tryb s3:      s3://BUCKET/PREFIKS/admin/kancelarie.json (szyfrowany)
Tokeny NIE sa przechowywane wprost - tylko ich hashe. Token widac raz,
przy utworzeniu kancelarii.

Panel admina (/admin): logowanie e-mailem z listy administratorow, a awaryjnie
osobny token PIECZAPP_ADMIN_TOKEN (nie tokeny kancelarii):
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

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import logowanie
import magazyn
import urzadzenia

log = logging.getLogger("pieczapp.autoryzacja")

MULTI = os.getenv("PIECZAPP_MULTI", "false").lower() == "true"
ADMIN_TOKEN = os.getenv("PIECZAPP_ADMIN_TOKEN", "")

# Sciezki bez tokenu kancelarii: strona, statyki, zdrowie, panel admina
# (panel ma wlasny token), logowanie i odzyskiwanie hasla, favicon oraz
# laczenie pomocnika (pomocnik nie ma jeszcze tokenu - po to sie laczy).
_OTWARTE = ("/", "/static", "/zdrowie", "/admin", "/api/admin", "/api/logowanie", "/favicon.ico",
            "/api/pomocnik/parowanie")

# Token pomocnika otwiera tylko to, czego pomocnik potrzebuje. Wykradziony z
# komputera notariusza nie pozwala przegladac spraw.
_DLA_POMOCNIKA = "/api/pomocnik/"

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


def _kancelaria_z_naglowka(token: str) -> tuple[str | None, str | None, str]:
    """(kancelaria, identyfikator komputera z pomocnikiem albo None, e-mail).

    E-mail jest tylko przy tokenie logowania - po nim poznajemy wlasciciela
    kancelarii. Dawny token i token pomocnika nie wskazuja osoby.

    Token logowania (JWT) jest podpisany przez Cognito i niesie kancelarie
    uzytkownika. Token pomocnika nalezy do jednego komputera. Dawny token
    kancelarii zostaje dla zadan automatycznych - jest wspolny dla calej
    kancelarii i nie wskazuje osoby.
    """
    if not token:
        return None, None, ""
    if logowanie.wlaczone() and logowanie.czy_jwt(token):
        try:
            dane = logowanie.dane_z_tokenu(token)
        except logowanie.BladLogowania:
            return None, None, ""
        # Wylaczenie kancelarii ma odciac takze zalogowanych - token
        # tozsamosci jest wazny jeszcze kilka godzin.
        if not _aktywna(dane["kancelaria"]):
            return None, None, ""
        return dane["kancelaria"], None, dane["email"].lower()
    if urzadzenia.czy_token_pomocnika(token):
        komputer = urzadzenia.z_tokenu(token)
        if komputer and _aktywna(komputer["kancelaria"]):
            return komputer["kancelaria"], komputer["id"], ""
        return None, None, ""
    wpis = _wczytaj_rejestr().get(_sha(token))
    if wpis and wpis.get("aktywna", True):
        return wpis["id"], None, ""
    return None, None, ""


def _aktywna(kancelaria: str) -> bool:
    """Wylaczenie kancelarii odcina takze jej pomocnikow."""
    for wpis in _wczytaj_rejestr().values():
        if wpis["id"] == kancelaria:
            return wpis.get("aktywna", True)
    return False


def adres_klienta(request: Request) -> str:
    """Adres IP, z ktorego przyszlo zadanie.

    Za ALB prawdziwy adres jest w X-Forwarded-For. Bierzemy ostatni wpis -
    ten dopisal ALB; wczesniejsze moze podstawic kazdy klient.
    """
    przekazany = request.headers.get("x-forwarded-for", "")
    if przekazany:
        return przekazany.split(",")[-1].strip()
    return request.client.host if request.client else ""


async def middleware(request: Request, call_next):
    """Token uzytkownika albo kancelarii -> kontekst. Tylko gdy PIECZAPP_MULTI."""
    sciezka = request.url.path
    if not MULTI or sciezka == "/" or any(
        sciezka.startswith(o) for o in _OTWARTE if o != "/"
    ):
        return await call_next(request)

    naglowek = request.headers.get("authorization", "")
    token = naglowek[7:] if naglowek.startswith("Bearer ") else ""
    kancelaria, komputer, email = _kancelaria_z_naglowka(token)
    if not kancelaria:
        return JSONResponse({"detail": "Zaloguj sie, zeby korzystac z aplikacji."}, 401)
    if komputer and not sciezka.startswith(_DLA_POMOCNIKA):
        return JSONResponse({"detail": "Token pomocnika sluzy tylko pomocnikowi."}, 403)

    znacznik = magazyn.kancelaria_var.set(kancelaria)
    znacznik_p = magazyn.przechowywanie_var.set(_przechowywanie(kancelaria))
    try:
        request.state.kancelaria = kancelaria
        request.state.komputer = komputer
        request.state.email = email
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
    if not ADMIN_TOKEN and not logowanie.wlaczone():
        raise HTTPException(503, "Panel admina wylaczony: ustaw PIECZAPP_ADMIN_TOKEN")
    if not czy_admin(request):
        raise HTTPException(401, "Brak uprawnien administratora")


def czy_admin(request: Request) -> bool:
    """Czy zadanie pochodzi od administratora: zalogowanego adresem e-mail
    z listy administratorow albo z tokenem awaryjnym z Secrets Manager.
    Bez wyjatku - do uzytku tam, gdzie brak uprawnien nie jest bledem
    (np. sonda /zdrowie)."""
    naglowek = request.headers.get("authorization", "")
    token = naglowek[7:] if naglowek.startswith("Bearer ") else ""
    if not token:
        return False
    if ADMIN_TOKEN and secrets.compare_digest(_sha(token), _sha(ADMIN_TOKEN)):
        return True
    return bool(_email_administratora(token))


# --- administratorzy notarai ------------------------------------------------
# Administrator loguje sie do /admin adresem e-mail i haslem, jak notariusz.
# Token z Secrets Manager zostaje na awarie (np. pierwszy administrator albo
# zgubione haslo). Konto administratora nalezy do obszaru, ktory nie jest
# kancelaria, wiec nie otwiera zadnych spraw - tylko panel.

KANCELARIA_ADMINOW = "_administracja"   # id kancelarii nie zaczyna sie od "_"


def _plik_adminow() -> Path:
    import config
    return config.DANE / "administratorzy.json"


def _wczytaj_adminow() -> list[str]:
    if magazyn.TRYB == "s3":
        try:
            odp = magazyn._klient_s3().get_object(
                Bucket=magazyn.BUCKET, Key=f"{magazyn.PREFIKS}/admin/administratorzy.json")
            return json.loads(odp["Body"].read().decode("utf-8"))
        except Exception as blad:  # brak pliku = brak administratorow
            if type(blad).__name__ not in ("NoSuchKey", "ClientError"):
                raise
            return []
    plik = _plik_adminow()
    return json.loads(plik.read_text("utf-8")) if plik.exists() else []


def _zapisz_adminow(lista: list[str]) -> None:
    tresc = json.dumps(sorted(set(lista)), ensure_ascii=False, indent=2)
    if magazyn.TRYB == "s3":
        magazyn._klient_s3().put_object(
            Bucket=magazyn.BUCKET, Key=f"{magazyn.PREFIKS}/admin/administratorzy.json",
            Body=tresc.encode("utf-8"), **magazyn._szyfrowanie(),
        )
    else:
        _plik_adminow().write_text(tresc, encoding="utf-8")


def _email_administratora(token: str) -> str:
    """E-mail administratora z podpisanego tokenu logowania albo pusty."""
    if not logowanie.wlaczone() or not logowanie.czy_jwt(token):
        return ""
    try:
        dane = logowanie.dane_z_tokenu(token)
    except logowanie.BladLogowania:
        return ""
    email = dane["email"].lower()
    if dane["kancelaria"] != KANCELARIA_ADMINOW or email not in _wczytaj_adminow():
        return ""
    return email


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


# Token odnawiania zyje w ciasteczku HttpOnly: JavaScript go nie widzi, wiec
# nie wyciagnie go nawet wstrzykniety skrypt. Sciezka ogranicza go do
# /api/logowanie, wiec nie leci z kazdym zadaniem. SameSite=Strict - obca
# strona nie wywola odnowienia w imieniu notariusza.
CIASTKO = "notarai_odnowienie"
_DNI_ODNOWIENIA = int(os.getenv("PIECZAPP_ODNOWIENIE_DNI", "30"))


def _ustaw_ciastko(request: Request, odpowiedz: Response, wartosc: str) -> None:
    if not wartosc:
        return
    https = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    odpowiedz.set_cookie(
        CIASTKO, wartosc, max_age=_DNI_ODNOWIENIA * 86400, path="/api/logowanie",
        httponly=True, secure=https, samesite="strict",
    )


def _dla_przegladarki(request: Request, odpowiedz: Response, wynik: dict) -> dict:
    """Token odnawiania do ciasteczka, reszta do JSON-a."""
    wynik = dict(wynik)
    _ustaw_ciastko(request, odpowiedz, wynik.pop("odnowienie", ""))
    return wynik


@router_logowania.post("")
def zaloguj(dane: DaneLogowania, request: Request, odpowiedz: Response):
    _wymagaj_logowania()
    try:
        wynik = logowanie.zaloguj(dane.email.strip().lower(), dane.haslo)
    except logowanie.BladLogowania as blad:
        raise HTTPException(401, str(blad))
    _odnotuj_dolaczenie(wynik.get("token", ""))
    return _dla_przegladarki(request, odpowiedz, wynik)


@router_logowania.post("/nowe-haslo")
def nowe_haslo(dane: NoweHaslo, request: Request, odpowiedz: Response):
    """Pierwsze logowanie: zamiana hasla z zaproszenia na wlasne."""
    _wymagaj_logowania()
    try:
        wynik = logowanie.ustaw_nowe_haslo(dane.email.strip().lower(), dane.haslo, dane.sesja)
    except logowanie.BladLogowania as blad:
        raise HTTPException(400, str(blad))
    _odnotuj_dolaczenie(wynik.get("token", ""))
    return _dla_przegladarki(request, odpowiedz, wynik)


@router_logowania.post("/odnow")
def odnow(request: Request, odpowiedz: Response):
    """Nowy token tozsamosci bez hasla. Przegladarka wola to sama."""
    _wymagaj_logowania()
    try:
        wynik = logowanie.odnow(request.cookies.get(CIASTKO, ""))
    except logowanie.BladLogowania as blad:
        odpowiedz = JSONResponse({"detail": str(blad)}, 401)
        odpowiedz.delete_cookie(CIASTKO, path="/api/logowanie")
        return odpowiedz
    return _dla_przegladarki(request, odpowiedz, wynik)


@router_logowania.post("/wyloguj")
def wyloguj(request: Request):
    """Wylogowanie naprawde konczy sesje - takze na pozostalych kartach."""
    if logowanie.wlaczone():
        logowanie.wyloguj(request.cookies.get(CIASTKO, ""))
    odpowiedz = JSONResponse({"wylogowano": True})
    odpowiedz.delete_cookie(CIASTKO, path="/api/logowanie")
    return odpowiedz


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
    # Pusta: pierwsza osoba w kancelarii zostaje wlascicielem, kolejne -
    # czlonkami zespolu. Wlasciciel zaprasza dalej sam, bez administratora.
    rola: str = ""


@router.post("/uzytkownicy", status_code=201)
def dodaj_uzytkownika(request: Request, dane: NowyUzytkownik):
    """Zaklada konto w kancelarii i wysyla zaproszenie z haslem tymczasowym."""
    _wymagaj_admina(request)
    _wymagaj_logowania()
    kancelaria = dane.kancelaria.strip()
    rejestr = _wczytaj_rejestr()
    skrot, wpis = _znajdz(rejestr, kancelaria)
    if wpis is None:
        raise HTTPException(404, "Nie znaleziono kancelarii o takim identyfikatorze")
    if dane.rola and dane.rola not in _ROLE:
        raise HTTPException(400, "Rola: 'wlasciciel' albo 'czlonek'")
    rola = dane.rola or ("czlonek" if _wlasciciele(wpis) else "wlasciciel")
    osoba = _zapros(rejestr, skrot, dane.email, rola)
    return {"utworzono": True, "kancelaria": kancelaria, "rola": osoba["rola"]}


class NowaKancelaria(BaseModel):
    nazwa: str
    # "chmura": pliki w S3 we Frankfurcie. "u-klienta": serwer niczego nie
    # zapisuje, pliki zostaja na dysku kancelarii. Decyzja zapada przy
    # zakladaniu konta, bo zmiana w trakcie zostawialaby sprawy w dwoch
    # miejscach naraz.
    przechowywanie: str = "chmura"
    # Adres notariusza. Podany - od razu zakladamy mu konto wlasciciela
    # i wysylamy zaproszenie, wiec cale wdrozenie to jeden formularz.
    email: str = ""


@router.get("/kancelarie")
def lista_kancelarii(request: Request):
    _wymagaj_admina(request)
    rejestr = _wczytaj_rejestr()
    return [
        {"id": w["id"], "nazwa": w["nazwa"], "aktywna": w.get("aktywna", True),
         "przechowywanie": w.get("przechowywanie", "chmura"),
         "zespol": _zespol(w)}
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
    # Bledny adres odrzucamy, zanim cokolwiek powstanie.
    email = _poprawny_email(dane.email) if dane.email.strip() else ""
    if email:
        _wymagaj_logowania()

    token = secrets.token_hex(32)
    rejestr[_sha(token)] = {
        "id": id_k,
        "nazwa": nazwa,
        "aktywna": True,
        "przechowywanie": dane.przechowywanie,
    }
    _zapisz_rejestr(rejestr)
    log.info("kancelaria dodana: %s, pliki: %s", id_k, dane.przechowywanie)
    wynik = {
        "id": id_k,
        "nazwa": nazwa,
        "przechowywanie": dane.przechowywanie,
        "token": token,
        "uwaga": "Zapisz token teraz - nie da sie go odczytac ponownie.",
    }
    if email:
        # Kancelaria juz jest; nieudane zaproszenie mozna powtorzyc z panelu.
        try:
            _zapros(rejestr, _sha(token), email, "wlasciciel")
            wynik["zaproszono"] = email
        except HTTPException as blad:
            wynik["blad_zaproszenia"] = blad.detail
    return wynik


@router.post("/kancelarie/{id_k}/token")
def nowy_token_kancelarii(request: Request, id_k: str):
    """Wydaje nowy token kancelarii. Stary przestaje dzialac natychmiast.

    Tokenow nie przechowujemy wprost, tylko ich skroty, wiec zgubionego nie da
    sie odczytac - ani nam, ani komus, kto dostalby sie do rejestru. Jedyne
    wyjscie to wydac nowy, i dlatego to musi byc zwykla czynnosc, a nie
    awaryjna. Kancelaria zostaje ta sama: identyfikator sie nie zmienia, wiec
    wszystkie sprawy zostaja na miejscu.
    """
    _wymagaj_admina(request)
    rejestr = _wczytaj_rejestr()
    stary_skrot = next((s for s, w in rejestr.items() if w["id"] == id_k), None)
    if stary_skrot is None:
        raise HTTPException(404, "Nie znaleziono kancelarii")

    wpis = rejestr.pop(stary_skrot)
    token = secrets.token_hex(32)
    rejestr[_sha(token)] = wpis
    _zapisz_rejestr(rejestr)
    log.info("kancelaria %s: wydano nowy token, stary uniewazniony", id_k)
    return {
        "id": id_k,
        "nazwa": wpis["nazwa"],
        "token": token,
        "uwaga": "Zapisz token teraz - nie da sie go odczytac ponownie. "
                 "Poprzedni przestal dzialac.",
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


class Rola(BaseModel):
    rola: str


@router.put("/kancelarie/{id_k}/zespol/{email}")
def ustaw_role(request: Request, id_k: str, email: str, dane: Rola):
    """Nadaje role osobie, ktora ma juz konto - np. zalozone przed zespolami."""
    _wymagaj_admina(request)
    if dane.rola not in _ROLE:
        raise HTTPException(400, "Rola: 'wlasciciel' albo 'czlonek'")
    rejestr = _wczytaj_rejestr()
    _, wpis = _znajdz(rejestr, id_k)
    if wpis is None:
        raise HTTPException(404, "Nie znaleziono kancelarii")
    email = _poprawny_email(email)
    osoba = _osoba(wpis, email)
    if osoba is None:
        osoba = {"email": email, "zaproszono": None, "dolaczyl": None}
        wpis.setdefault("zespol", []).append(osoba)
    osoba["rola"] = dane.rola
    _zapisz_rejestr(rejestr)
    return {"email": email, "rola": dane.rola}


@router.post("/kancelarie/{id_k}/zespol/{email}/ponow")
def admin_ponow(request: Request, id_k: str, email: str):
    _wymagaj_admina(request)
    _wymagaj_logowania()
    _, wpis = _znajdz(_wczytaj_rejestr(), id_k)
    if wpis is None:
        raise HTTPException(404, "Nie znaleziono kancelarii")
    _ponow(wpis, email)
    return {"wyslano": True}


@router.put("/kancelarie/{id_k}/aktywna")
def przywroc_kancelarie(request: Request, id_k: str):
    """Odwrotnosc wylaczenia. Sprawy przez caly czas zostaja na miejscu."""
    _wymagaj_admina(request)
    rejestr = _wczytaj_rejestr()
    _, wpis = _znajdz(rejestr, id_k)
    if wpis is None:
        raise HTTPException(404, "Nie znaleziono kancelarii")
    wpis["aktywna"] = True
    _zapisz_rejestr(rejestr)
    log.info("kancelaria przywrocona: %s", id_k)
    return {"id": id_k, "aktywna": True}


# --- zespol kancelarii -------------------------------------------------------
# Kto ma konto w kancelarii, trzymamy w jej wpisie rejestru: Cognito nie
# pozwala filtrowac uzytkownikow po wlasnym atrybucie. Wlasciciel zaprasza
# i usuwa osoby sam - administrator jest potrzebny tylko przy zalozeniu
# kancelarii. Adresy e-mail nigdy nie trafiaja do logow.

_ROLE = ("wlasciciel", "czlonek")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _teraz() -> str:
    from datetime import datetime
    return datetime.now().isoformat(timespec="seconds")


def _poprawny_email(email: str) -> str:
    email = (email or "").strip().lower()
    if not _EMAIL.match(email):
        raise HTTPException(400, "To nie wyglada na adres e-mail.")
    return email


def _znajdz(rejestr: dict, id_k: str) -> tuple[str | None, dict | None]:
    for skrot, wpis in rejestr.items():
        if wpis["id"] == id_k:
            return skrot, wpis
    return None, None


def _zespol(wpis: dict) -> list[dict]:
    return [dict(o) for o in wpis.get("zespol", [])]


def _osoba(wpis: dict, email: str) -> dict | None:
    return next((o for o in wpis.get("zespol", []) if o["email"] == email), None)


def _wlasciciele(wpis: dict) -> list[str]:
    return [o["email"] for o in wpis.get("zespol", []) if o.get("rola") == "wlasciciel"]


def _zapros(rejestr: dict, skrot: str, email: str, rola: str) -> dict:
    """Zaklada konto w Cognito, wysyla zaproszenie, dopisuje do zespolu."""
    email = _poprawny_email(email)
    wpis = rejestr[skrot]
    if _osoba(wpis, email):
        raise HTTPException(409, "Ta osoba jest juz w zespole. Mozesz ponowic zaproszenie.")
    try:
        logowanie.utworz_uzytkownika(email, wpis["id"])
    except logowanie.BladLogowania:
        raise HTTPException(409, "Ten adres ma juz konto w notarai.")
    osoba = {"email": email, "rola": rola, "zaproszono": _teraz(), "dolaczyl": None}
    wpis.setdefault("zespol", []).append(osoba)
    _zapisz_rejestr(rejestr)
    log.info("kancelaria %s: zaproszono osobe (%s)", wpis["id"], rola)
    return osoba


def _ponow(wpis: dict, email: str) -> None:
    email = _poprawny_email(email)
    if _osoba(wpis, email) is None:
        raise HTTPException(404, "Tej osoby nie ma w zespole.")
    try:
        logowanie.ponow_zaproszenie(email)
    except logowanie.BladLogowania as blad:
        raise HTTPException(409, str(blad))


def _odnotuj_dolaczenie(token: str) -> None:
    """Pierwsze udane logowanie zamienia "zaproszony" na "w zespole".

    Konta zalozone przed zespolami dopisujemy przy pierwszym logowaniu jako
    czlonkow - wlasciciela wskazuje administrator. Blad nie moze zablokowac
    logowania, wiec go tylko odnotowujemy.
    """
    if not token or not logowanie.czy_jwt(token):
        return
    try:
        dane = logowanie.dane_z_tokenu(token)
        rejestr = _wczytaj_rejestr()
        _, wpis = _znajdz(rejestr, dane["kancelaria"])
        if wpis is None:
            return
        email = dane["email"].lower()
        osoba = _osoba(wpis, email)
        if osoba is None:
            osoba = {"email": email, "rola": "czlonek", "zaproszono": None, "dolaczyl": None}
            wpis.setdefault("zespol", []).append(osoba)
        if osoba.get("dolaczyl"):
            return
        osoba["dolaczyl"] = _teraz()
        _zapisz_rejestr(rejestr)
    except Exception as blad:  # noqa: BLE001
        log.info("zespol: nie odnotowano logowania (%s)", type(blad).__name__)


router_zespolu = APIRouter(prefix="/api/zespol", tags=["zespol"])


def _moja_kancelaria(request: Request) -> tuple[dict, str, dict, str]:
    """(rejestr, skrot, wpis kancelarii, moj e-mail). Tylko dla osob
    zalogowanych adresem e-mail - dawny token nie wskazuje osoby."""
    email = getattr(request.state, "email", "")
    if not email:
        raise HTTPException(403, "Zespolem zarzadza sie po zalogowaniu adresem e-mail.")
    rejestr = _wczytaj_rejestr()
    skrot, wpis = _znajdz(rejestr, request.state.kancelaria)
    if wpis is None:
        raise HTTPException(404, "Nie znaleziono kancelarii")
    return rejestr, skrot, wpis, email


def _wymagaj_wlasciciela(wpis: dict, email: str) -> None:
    if email not in _wlasciciele(wpis):
        raise HTTPException(403, "Zapraszac i usuwac osoby moze wlasciciel kancelarii.")


class Zaproszenie(BaseModel):
    email: str


@router_zespolu.get("")
def moj_zespol(request: Request):
    _, _, wpis, email = _moja_kancelaria(request)
    return {"ja": email, "kancelaria": wpis["nazwa"],
            "jestem_wlascicielem": email in _wlasciciele(wpis),
            "osoby": _zespol(wpis)}


@router_zespolu.post("", status_code=201)
def zapros_do_zespolu(request: Request, dane: Zaproszenie):
    _wymagaj_logowania()
    rejestr, skrot, wpis, email = _moja_kancelaria(request)
    _wymagaj_wlasciciela(wpis, email)
    return _zapros(rejestr, skrot, dane.email, "czlonek")


@router_zespolu.post("/{adres}/ponow")
def ponow_w_zespole(request: Request, adres: str):
    _wymagaj_logowania()
    _, _, wpis, email = _moja_kancelaria(request)
    _wymagaj_wlasciciela(wpis, email)
    _ponow(wpis, adres)
    return {"wyslano": True}


@router_zespolu.delete("/{adres}")
def usun_z_zespolu(request: Request, adres: str):
    """Usuwa konto osoby. Sprawy kancelarii zostaja - naleza do kancelarii."""
    _wymagaj_logowania()
    rejestr, _, wpis, email = _moja_kancelaria(request)
    _wymagaj_wlasciciela(wpis, email)
    adres = _poprawny_email(adres)
    if adres == email:
        raise HTTPException(400, "Nie mozesz usunac wlasnego konta.")
    osoba = _osoba(wpis, adres)
    if osoba is None:
        raise HTTPException(404, "Tej osoby nie ma w zespole.")
    if osoba.get("rola") == "wlasciciel":
        raise HTTPException(403, "Wlasciciela usuwa administrator.")
    logowanie.usun_uzytkownika(adres)
    wpis["zespol"].remove(osoba)
    _zapisz_rejestr(rejestr)
    log.info("kancelaria %s: usunieto osobe z zespolu", wpis["id"])
    return {"usunieto": True}


# --- lista administratorow (panel) -------------------------------------------

@router.get("/administratorzy")
def lista_adminow(request: Request):
    _wymagaj_admina(request)
    naglowek = request.headers.get("authorization", "")
    return {"ja": _email_administratora(naglowek[7:]) if naglowek.startswith("Bearer ") else "",
            "administratorzy": _wczytaj_adminow()}


@router.post("/administratorzy", status_code=201)
def dodaj_admina(request: Request, dane: Zaproszenie):
    """Konto do panelu: zaproszenie e-mailem, potem logowanie haslem."""
    _wymagaj_admina(request)
    _wymagaj_logowania()
    email = _poprawny_email(dane.email)
    lista = _wczytaj_adminow()
    if email in lista:
        raise HTTPException(409, "Ten adres jest juz administratorem.")
    try:
        logowanie.utworz_uzytkownika(email, KANCELARIA_ADMINOW)
    except logowanie.BladLogowania:
        raise HTTPException(409, "Ten adres ma juz konto w notarai. "
                                 "Administrator potrzebuje osobnego adresu.")
    _zapisz_adminow(lista + [email])
    log.info("dodano administratora")
    return {"email": email}


@router.post("/administratorzy/{email}/ponow")
def ponow_adminowi(request: Request, email: str):
    _wymagaj_admina(request)
    _wymagaj_logowania()
    email = _poprawny_email(email)
    if email not in _wczytaj_adminow():
        raise HTTPException(404, "Tego adresu nie ma na liscie administratorow.")
    try:
        logowanie.ponow_zaproszenie(email)
    except logowanie.BladLogowania as blad:
        raise HTTPException(409, str(blad))
    return {"wyslano": True}


@router.delete("/administratorzy/{email}")
def usun_admina(request: Request, email: str):
    _wymagaj_admina(request)
    email = _poprawny_email(email)
    naglowek = request.headers.get("authorization", "")
    if email == _email_administratora(naglowek[7:] if naglowek.startswith("Bearer ") else ""):
        raise HTTPException(400, "Nie mozesz usunac wlasnego konta administratora.")
    lista = _wczytaj_adminow()
    if email not in lista:
        raise HTTPException(404, "Tego adresu nie ma na liscie administratorow.")
    if logowanie.wlaczone():
        logowanie.usun_uzytkownika(email)
    _zapisz_adminow([a for a in lista if a != email])
    log.info("usunieto administratora")
    return {"usunieto": True}
