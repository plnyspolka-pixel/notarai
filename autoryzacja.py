"""Autoryzacja per kancelaria (tryb SaaS) + panel administracyjny.

Tryb wielu kancelarii wlacza PIECZAPP_MULTI=true. Wtedy kazde zadanie /api/*
musi niesc naglowek:  Authorization: Bearer <token logowania albo pomocnika>
Token logowania (Cognito) niesie kancelarie osoby; innej drogi do spraw nie
ma. Wspolnego tokenu kancelarii juz nie ma: dawal pelny dostep do spraw
komukolwiek, kto go mial - takze administratorowi, ktory go wydawal.

Rejestr kancelarii: plik JSON {losowy_skrot: {"id","nazwa","aktywna",...}}.
  - tryb lokalny: dane/kancelarie.json
  - tryb s3:      s3://BUCKET/PREFIKS/admin/kancelarie.json (szyfrowany)

Panel admina (/admin): logowanie e-mailem z listy administratorow, a awaryjnie
osobny token PIECZAPP_ADMIN_TOKEN. Panel zaklada i wylacza kancelarie, ale
nie otwiera ich spraw. Do spraw administrator wchodzi wylacznie przez dostep
serwisowy, ktory wlasciciel kancelarii sam wlacza na okreslony czas
(umowa powierzenia § 5 ust. 4) - i tylko zalogowany imiennie, nie tokenem.

Zero danych osobowych ani tokenow w logach.
"""
import hashlib
import json
import logging
import os
import re
import secrets
import time
from datetime import date
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import logowanie
import magazyn
import platnosci
import tokenomia
import urzadzenia

log = logging.getLogger("pieczapp.autoryzacja")

MULTI = os.getenv("PIECZAPP_MULTI", "false").lower() == "true"
ADMIN_TOKEN = os.getenv("PIECZAPP_ADMIN_TOKEN", "")

# Sciezki bez logowania: strona, statyki, zdrowie, panel admina
# (panel ma wlasny token), logowanie i odzyskiwanie hasla, favicon oraz
# laczenie pomocnika (pomocnik nie ma jeszcze tokenu - po to sie laczy) i
# webhook Stripe (Stripe nie ma tokenu, zaufanie daje podpis). Rejestracja
# jest otwarta, bo to przez nia kancelaria dopiero dostaje konto.
_OTWARTE = ("/", "/static", "/zdrowie", "/admin", "/api/admin", "/api/logowanie", "/favicon.ico",
            "/api/pomocnik/parowanie", "/api/stripe/", "/rejestracja", "/api/rejestracja", "/dokumenty/",
            "/kalkulator", "/api/taksa", "/api/wizyty", "/api/teczka", "/api/leady", "/api/meta/",
            "/notariusze", "/api/notariusze",
            # webhooki agenta glosowego - wlasny token i limity (agent_glosowy.py)
            "/api/agent-glosowy",
            # sama strona; jej API (/api/poswiadczenia) wymaga logowania
            "/poswiadczenia")

# Po terminie abonamentu te sciezki zostaja otwarte: bez nich wlasciciel nie
# moglby zaplacic ani zobaczyc, kto z zespolu ma dostep.
_BEZ_ABONAMENTU = ("/api/abonament", "/api/zespol", "/api/kredyty")

# Bez zaakceptowanej umowy powierzenia nie przetwarzamy spraw (Regulamin
# § 6 ust. 4). Otwarte zostaje to, co potrzebne do jej zaakceptowania.
_BEZ_UMOWY = _BEZ_ABONAMENTU + ("/api/dokumenty", "/api/ustawienia")

# Token pomocnika otwiera tylko to, czego pomocnik potrzebuje. Wykradziony z
# komputera notariusza nie pozwala przegladac spraw.
_DLA_POMOCNIKA = "/api/pomocnik/"

# Dostep serwisowy: administrator wskazuje kancelarie tym naglowkiem. Nie
# siega po to, co nalezy do kancelarii jako klienta - zespol, abonament,
# akceptacje dokumentow, pomocnika - ani po sam dostep serwisowy, zeby nie
# mogl go sobie przedluzyc.
NAGLOWEK_SERWISU = "x-serwis-kancelaria"
_POZA_SERWISEM = ("/api/zespol", "/api/serwis", "/api/abonament", "/api/kredyty", "/api/dokumenty",
                  "/api/pomocnik", "/api/mapa", "/api/zapytania",
                  # Repertorium i zgloszenia AML - tajemnica notarialna, art. 18 PrNot.
                  "/api/ksiegi-kancelarii", "/api/giif")
_SERWIS_MAKS_GODZIN = 7 * 24

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
    kancelarii. Token pomocnika nie wskazuje osoby.

    Token logowania (JWT) jest podpisany przez Cognito i niesie kancelarie
    uzytkownika. Token pomocnika nalezy do jednego komputera i otwiera tylko
    kolejke pomocnika.
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
    # External B2B routes use a separate, narrowly scoped API key in each handler.
    # No Cognito session can grant partner permissions through these routes.
    if sciezka == "/hurtowe" or sciezka == "/mcp" or sciezka.startswith("/api/hurtowe/") or sciezka == "/api/hurtowe":
        return await call_next(request)
    if not MULTI or sciezka == "/" or any(
        sciezka.startswith(o) for o in _OTWARTE if o != "/"
    ):
        return await call_next(request)

    naglowek = request.headers.get("authorization", "")
    token = naglowek[7:] if naglowek.startswith("Bearer ") else ""
    id_serwisu = request.headers.get(NAGLOWEK_SERWISU, "").strip()
    if id_serwisu:
        # Administrator w sprawach kancelarii: tylko gdy ta kancelaria sama
        # wlaczyla dostep serwisowy i tylko do czasu, ktory wskazala.
        if sciezka.startswith(_POZA_SERWISEM):
            return JSONResponse({"detail": "Dostep serwisowy nie obejmuje zespolu, abonamentu, "
                                           "dokumentow ani pomocnika kancelarii."}, 403)
        email = _wejscie_serwisowe(token, id_serwisu, sciezka, request.method)
        if not email:
            return JSONResponse({"detail": "Kancelaria nie wlaczyla dostepu serwisowego "
                                           "albo juz wygasl."}, 403)
        kancelaria, komputer = id_serwisu, None
    else:
        kancelaria, komputer, email = _kancelaria_z_naglowka(token)
    if not kancelaria:
        return JSONResponse({"detail": "Zaloguj sie, zeby korzystac z aplikacji."}, 401)
    if komputer and not sciezka.startswith(_DLA_POMOCNIKA):
        return JSONResponse({"detail": "Token pomocnika sluzy tylko pomocnikowi."}, 403)
    if not sciezka.startswith(_BEZ_ABONAMENTU) and not _oplacona(kancelaria):
        return JSONResponse({"detail": "Abonament kancelarii wygasl. Wlasciciel moze go oplacic "
                                       "w oknie Abonament.", "abonament": True}, 402)
    # Dotyczy ludzi. Pomocnik to automatyzacja kancelarii, ktora i tak
    # zaczyna dzialac dopiero po zalogowaniu wlasciciela.
    if email and not sciezka.startswith(_BEZ_UMOWY) and not umowa_zawarta(kancelaria):
        return JSONResponse({"detail": "Wlasciciel kancelarii musi najpierw zaakceptowac Regulamin "
                                       "i umowe powierzenia.", "umowa": True}, 428)

    znacznik = magazyn.kancelaria_var.set(kancelaria)
    znacznik_p = magazyn.przechowywanie_var.set(_przechowywanie(kancelaria))
    try:
        request.state.kancelaria = kancelaria
        request.state.komputer = komputer
        request.state.email = email
        request.state.serwis = bool(id_serwisu)
        return await call_next(request)
    finally:
        magazyn.kancelaria_var.reset(znacznik)
        magazyn.przechowywanie_var.reset(znacznik_p)


def _oplacona(kancelaria: str) -> bool:
    """Bez skonfigurowanych platnosci nikogo nie blokujemy."""
    if not platnosci.wlaczone():
        return True
    _, wpis = _znajdz(_wczytaj_rejestr(), kancelaria)
    return wpis is None or platnosci.stan(wpis)["wazny"]


def umowa_zawarta(kancelaria: str) -> bool:
    _, wpis = _znajdz(_wczytaj_rejestr(), kancelaria)
    return bool(wpis and (wpis.get("umowa") or {}).get("zaakceptowano"))


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

# Stali administratorzy z parametru stosu (PIECZAPP_ADMINI, po przecinku).
# Nie da sie ich usunac z panelu, a konto zaklada sie samo przy pierwszym
# otwarciu /admin - wiec po wdrozeniu wystarczy otworzyc panel i odebrac
# zaproszenie. Token z Secrets Manager zostaje wylacznie na awarie.
STALI_ADMINI = [a.strip().lower() for a in os.getenv("PIECZAPP_ADMINI", "").split(",") if a.strip()]
_stali_zalozeni = False


def zaloz_stalych_adminow() -> None:
    """Raz na proces: konto w Cognito dla kazdego stalego administratora.
    Istniejace konto to nie blad - zaproszenie poszlo juz wczesniej."""
    global _stali_zalozeni
    if _stali_zalozeni or not STALI_ADMINI or not logowanie.wlaczone():
        return
    _stali_zalozeni = True
    for email in STALI_ADMINI:
        try:
            logowanie.utworz_uzytkownika(email, KANCELARIA_ADMINOW)
            log.info("zalozono konto stalego administratora")
        except logowanie.BladLogowania:
            pass   # konto juz jest
        except Exception as blad:  # noqa: BLE001 - panel ma dzialac i tak
            _stali_zalozeni = False
            log.warning("staly administrator: nie zalozono konta (%s)", type(blad).__name__)


def _wszyscy_admini() -> list[str]:
    return sorted(set(STALI_ADMINI) | set(_wczytaj_adminow()))


def _wczytaj_admin_json(nazwa: str) -> list:
    """Plik obszaru administracyjnego (lista). Brak pliku = pusta lista."""
    if magazyn.TRYB == "s3":
        try:
            odp = magazyn._klient_s3().get_object(
                Bucket=magazyn.BUCKET, Key=f"{magazyn.PREFIKS}/admin/{nazwa}")
            return json.loads(odp["Body"].read().decode("utf-8"))
        except Exception as blad:
            if type(blad).__name__ not in ("NoSuchKey", "ClientError"):
                raise
            return []
    import config
    plik = config.DANE / nazwa
    return json.loads(plik.read_text("utf-8")) if plik.exists() else []


def _zapisz_admin_json(nazwa: str, dane: list) -> None:
    tresc = json.dumps(dane, ensure_ascii=False, indent=2)
    if magazyn.TRYB == "s3":
        magazyn._klient_s3().put_object(
            Bucket=magazyn.BUCKET, Key=f"{magazyn.PREFIKS}/admin/{nazwa}",
            Body=tresc.encode("utf-8"), **magazyn._szyfrowanie(),
        )
    else:
        import config
        (config.DANE / nazwa).write_text(tresc, encoding="utf-8")


def _wczytaj_adminow() -> list[str]:
    return _wczytaj_admin_json("administratorzy.json")


def _zapisz_adminow(lista: list[str]) -> None:
    _zapisz_admin_json("administratorzy.json", sorted(set(lista)))


def _email_administratora(token: str) -> str:
    """E-mail administratora z podpisanego tokenu logowania albo pusty."""
    if not logowanie.wlaczone() or not logowanie.czy_jwt(token):
        return ""
    try:
        dane = logowanie.dane_z_tokenu(token)
    except logowanie.BladLogowania:
        return ""
    email = dane["email"].lower()
    if dane["kancelaria"] != KANCELARIA_ADMINOW or email not in _wszyscy_admini():
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
    # Zostaje dla zgodnosci: administrator zaprasza tylko pierwsza osobe,
    # zawsze jako wlasciciela.
    rola: str = ""


@router.post("/uzytkownicy", status_code=201)
def dodaj_uzytkownika(request: Request, dane: NowyUzytkownik):
    """Zaprasza wlasciciela do kancelarii, w ktorej nikt jeszcze nie ma konta.

    Tylko pierwsza osoba: gdyby administrator mogl dopisac konto do
    dzialajacej kancelarii, moglby dopisac siebie i czytac jej sprawy.
    Kolejne osoby zaprasza wlasciciel.
    """
    _wymagaj_admina(request)
    _wymagaj_logowania()
    kancelaria = dane.kancelaria.strip()
    rejestr = _wczytaj_rejestr()
    skrot, wpis = _znajdz(rejestr, kancelaria)
    if wpis is None:
        raise HTTPException(404, "Nie znaleziono kancelarii o takim identyfikatorze")
    if wpis.get("zespol"):
        raise HTTPException(409, "Kancelaria ma już zespół. Kolejne osoby zaprasza "
                                 "właściciel kancelarii.")
    osoba = _zapros(rejestr, skrot, dane.email, "wlasciciel")
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
         "oplacono_do": w.get("oplacono_do"),
         "umowa": (w.get("umowa") or {}).get("zaakceptowano"),
         "zespol": _zespol(w),
         "serwis_do": (_serwis_trwa(w) or {}).get("do"),
         "mapa": _stan_mapy(w)}
        for w in rejestr.values()
    ]


def _stan_mapy(wpis: dict) -> dict:
    """Publiczna lokalizacja kancelarii; bez danych spraw lub zapytan."""
    mapa = wpis.get("mapa") or {}
    return {"na_mapie": bool(wpis.get("na_mapie", False)),
            "polozenie": mapa.get("lat") is not None,
            "blad": mapa.get("blad")}


def nowy_identyfikator(rejestr: dict, nazwa: str) -> str:
    id_k = re.sub(r"[^a-z0-9]+", "-", nazwa.lower()).strip("-")[:40] or "kancelaria"
    zajete = {w["id"] for w in rejestr.values()} | set(magazyn.ZASTRZEZONE)
    if id_k in zajete:
        id_k = f"{id_k}-{secrets.token_hex(3)}"
    return id_k


@router.post("/kancelarie", status_code=201)
def dodaj_kancelarie(request: Request, dane: NowaKancelaria):
    _wymagaj_admina(request)
    nazwa = dane.nazwa.strip()
    if len(nazwa) < 2:
        raise HTTPException(400, "Nazwa kancelarii: minimum 2 znaki")

    rejestr = _wczytaj_rejestr()
    id_k = nowy_identyfikator(rejestr, nazwa)

    if dane.przechowywanie not in ("chmura", "u-klienta"):
        raise HTTPException(400, "Przechowywanie: 'chmura' albo 'u-klienta'")
    # Bledny adres odrzucamy, zanim cokolwiek powstanie.
    email = _poprawny_email(dane.email) if dane.email.strip() else ""
    if email:
        _wymagaj_logowania()

    # Klucz wpisu to losowy skrot bez zadnego tokenu za nim: do spraw
    # wchodzi sie wylacznie logujac sie, wiec administrator nie dostaje
    # niczego, czym moglby je otworzyc.
    skrot = _sha(secrets.token_hex(32))
    rejestr[skrot] = {
        "id": id_k,
        "nazwa": nazwa,
        "aktywna": True,
        "przechowywanie": dane.przechowywanie,
    }
    # Z platnosciami nowa kancelaria dostaje okres probny, potem placi sama.
    if platnosci.wlaczone():
        rejestr[skrot]["oplacono_do"] = platnosci.na_probe()
    _zapisz_rejestr(rejestr)
    if tokenomia.WLACZONA:
        tokenomia.zaloz_portfel_probny(id_k)
    log.info("kancelaria dodana: %s, pliki: %s", id_k, dane.przechowywanie)
    wynik = {
        "id": id_k,
        "nazwa": nazwa,
        "przechowywanie": dane.przechowywanie,
    }
    if email:
        # Kancelaria juz jest; nieudane zaproszenie mozna powtorzyc z panelu.
        try:
            _zapros(rejestr, skrot, email, "wlasciciel")
            wynik["zaproszono"] = email
        except HTTPException as blad:
            wynik["blad_zaproszenia"] = blad.detail
    return wynik


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
    """Zmienia role osobie z zespolu, np. gdy wlasciciel odchodzi.

    Dopisac nowej osoby nie mozna - zespol tworzy kancelaria sama.
    """
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
        raise HTTPException(404, "Tej osoby nie ma w zespole kancelarii.")
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


class TerminAbonamentu(BaseModel):
    # "RRRR-MM-DD" albo pusty: kancelaria bez abonamentu w Stripe (np. umowa
    # i faktura poza systemem) - wtedy nic jej nie blokujemy.
    oplacono_do: str = ""


@router.put("/kancelarie/{id_k}/abonament")
def ustaw_abonament(request: Request, id_k: str, dane: TerminAbonamentu):
    """Recznie: okres probny, przedluzenie po przelewie, zwolnienie z oplat."""
    _wymagaj_admina(request)
    rejestr = _wczytaj_rejestr()
    _, wpis = _znajdz(rejestr, id_k)
    if wpis is None:
        raise HTTPException(404, "Nie znaleziono kancelarii")
    if dane.oplacono_do:
        try:
            date.fromisoformat(dane.oplacono_do)
        except ValueError:
            raise HTTPException(400, "Data w postaci RRRR-MM-DD")
        wpis["oplacono_do"] = dane.oplacono_do
    else:
        wpis.pop("oplacono_do", None)
    _zapisz_rejestr(rejestr)
    log.info("kancelaria %s: abonament ustawiony recznie", id_k)
    return {"id": id_k, "oplacono_do": wpis.get("oplacono_do")}


class PotwierdzenieUsuniecia(BaseModel):
    potwierdzenie: str


@router.post("/kancelarie/{id_k}/usun-dane")
def usun_dane_kancelarii(request: Request, id_k: str, dane: PotwierdzenieUsuniecia):
    """Koniec uslugi: kasuje wszystko, co mamy o kancelarii, nieodwracalnie.

    Sprawy ze wszystkimi wersjami, zlecenia, komputery pomocnika, konta
    zespolu w Cognito i wpis w rejestrze. Dwa bezpieczniki: kancelaria musi
    byc najpierw wylaczona, a w tresci trzeba przepisac jej identyfikator.
    Wpis w rejestrze znika na koncu, wiec przerwane usuwanie mozna powtorzyc.
    """
    _wymagaj_admina(request)
    rejestr = _wczytaj_rejestr()
    skrot, wpis = _znajdz(rejestr, id_k)
    if wpis is None:
        raise HTTPException(404, "Nie znaleziono kancelarii")
    if wpis.get("aktywna", True):
        raise HTTPException(409, "Najpierw wylacz kancelarie.")
    if dane.potwierdzenie != id_k:
        raise HTTPException(400, "Potwierdzenie: przepisz identyfikator kancelarii.")

    konta = 0
    if logowanie.wlaczone():
        for osoba in _zespol(wpis):
            logowanie.usun_uzytkownika(osoba["email"])
            konta += 1
    komputery = 0
    if urzadzenia.dostepne():
        for komputer in urzadzenia.lista(id_k):
            komputery += urzadzenia.odlacz(id_k, komputer["id"])

    import config
    obiekty = magazyn.usun_kancelarie(id_k, config.DANE)

    # Rejestr art. 30 ust. 2 i dowod zawarcia umowy musza przetrwac
    # usuniecie danych: zostaje jeden wiersz bez tresci spraw.
    dopisz_do_historii(wpis, usunieto=_teraz())
    del rejestr[skrot]
    _zapisz_rejestr(rejestr)
    log.info("kancelaria %s: usunieto dane (obiekty %d, konta %d, komputery %d)",
             id_k, obiekty, konta, komputery)
    return {"id": id_k, "usunieto": _teraz(), "obiekty": obiekty,
            "konta": konta, "komputery": komputery}


# --- rejestr umow (art. 30 ust. 2 RODO) -------------------------------------
# Biezace kancelarie sa w rejestrze; zakonczone umowy - w historii, przez
# 5 lat od usuniecia danych (dowod zawarcia umowy powierzenia i jej konca).

HISTORIA_UMOW = "historia-umow.json"
_LATA_HISTORII = 5


def _wiersz_umowy(wpis: dict) -> dict:
    umowa = wpis.get("umowa") or {}
    dane = wpis.get("dane") or {}
    return {
        "id": wpis["id"], "nazwa": wpis["nazwa"],
        "notariusze": dane.get("notariusze", ""), "adres": dane.get("adres", ""),
        "nip": dane.get("nip", ""),
        "wlasciciel": ", ".join(_wlasciciele(wpis)),
        "zawarto": umowa.get("zaakceptowano"), "wersja_umowy": umowa.get("umowa"),
        "sposob": umowa.get("sposob"),
        "przechowywanie": wpis.get("przechowywanie", "chmura"),
        "aktywna": wpis.get("aktywna", True), "usunieto": None,
    }


def dopisz_do_historii(wpis: dict, usunieto: str) -> None:
    granica = str(date.today().year - _LATA_HISTORII)
    historia = [h for h in _wczytaj_admin_json(HISTORIA_UMOW) if (h.get("usunieto") or "9") >= granica]
    historia.append({**_wiersz_umowy(wpis), "aktywna": False, "usunieto": usunieto})
    _zapisz_admin_json(HISTORIA_UMOW, historia)


@router.get("/rejestr-umow")
def rejestr_umow(request: Request):
    """Wykaz administratorow, w imieniu ktorych przetwarzamy dane."""
    _wymagaj_admina(request)
    biezace = [_wiersz_umowy(w) for w in _wczytaj_rejestr().values()]
    return biezace + _wczytaj_admin_json(HISTORIA_UMOW)


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
    zalogowanych adresem e-mail - token pomocnika nie wskazuje osoby."""
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


# --- dostep serwisowy ----------------------------------------------------------
# Jedyna droga administratora do spraw kancelarii (umowa powierzenia § 5
# ust. 4). Wlacza ja wlasciciel kancelarii na wskazany czas i moze ja odwolac.
# Kazde wlaczenie zostaje w "serwis" we wpisie kancelarii razem z tym, kto z
# niego skorzystal - kancelaria widzi to w swoim oknie. W dziennikach
# aplikacji zostaje sam fakt, bez adresow e-mail.

router_serwisu = APIRouter(prefix="/api/serwis", tags=["serwis"])


def _serwis_trwa(wpis: dict) -> dict | None:
    """Wlaczony i niewygasly dostep serwisowy albo None."""
    ostatni = (wpis.get("serwis") or [None])[-1]
    if ostatni and not ostatni.get("odwolano") and ostatni["do"] > _teraz():
        return ostatni
    return None


def _zakres_zadania(sciezka: str, metoda: str) -> tuple[str, str, bool]:
    """(obszar danych, identyfikator sprawy albo "", czy zadanie cos zmienia)
    - z tego kancelaria widzi, w co obsluga zajrzala."""
    czesci = sciezka.split("/")   # ["", "api", obszar, identyfikator, ...]
    obszar = czesci[2] if len(czesci) > 2 else ""
    sprawa = czesci[3] if obszar == "sprawy" and len(czesci) > 3 else ""
    return obszar, sprawa, metoda not in ("GET", "HEAD", "OPTIONS")


def _wejscie_serwisowe(token: str, id_k: str, sciezka: str = "", metoda: str = "GET") -> str:
    """E-mail administratora, ktoremu kancelaria id_k otworzyla dostep, albo
    pusty. Token awaryjny nie wystarcza: dostep musi wskazywac osobe.

    Przy okazji dopisuje do wpisu zakres: obszary danych, otwarte sprawy
    i to, czy cos zmieniano. Rejestr zapisujemy tylko wtedy, gdy zakres
    sie poszerzyl, nie przy kazdym zadaniu."""
    email = _email_administratora(token)
    if not email:
        return ""
    rejestr = _wczytaj_rejestr()
    _, wpis = _znajdz(rejestr, id_k)
    if wpis is None or not wpis.get("aktywna", True):
        return ""
    trwa = _serwis_trwa(wpis)
    if trwa is None:
        return ""
    uzyli = trwa.setdefault("uzyli", [])
    osoba = next((u for u in uzyli if u["email"] == email), None)
    if osoba is None:
        osoba = {"email": email, "od": _teraz()}
        uzyli.append(osoba)
        log.info("kancelaria %s: administrator wszedl w ramach dostepu serwisowego", id_k)
    przed = json.dumps(osoba, sort_keys=True)
    obszar, sprawa, zmiana = _zakres_zadania(sciezka, metoda)
    obszary, sprawy = osoba.setdefault("obszary", []), osoba.setdefault("sprawy", [])
    if obszar and obszar not in obszary:
        obszary.append(obszar)
    if sprawa and sprawa not in sprawy:
        sprawy.append(sprawa)
    osoba["zmiany"] = bool(osoba.get("zmiany")) or zmiana
    if json.dumps(osoba, sort_keys=True) != przed:
        _zapisz_rejestr(rejestr)
    return email


def _opis_serwisu(wpis: dict) -> dict:
    trwa = _serwis_trwa(wpis)
    return {"wlaczony": trwa is not None, "do": trwa["do"] if trwa else None,
            "historia": [dict(s) for s in reversed(wpis.get("serwis") or [])]}


class WlaczenieSerwisu(BaseModel):
    godziny: int = 24


@router_serwisu.get("")
def stan_serwisu(request: Request):
    _, _, wpis, _ = _moja_kancelaria(request)
    return _opis_serwisu(wpis)


@router_serwisu.post("", status_code=201)
def wlacz_serwis(request: Request, dane: WlaczenieSerwisu):
    """Wlasciciel otwiera administratorowi sprawy kancelarii na dane.godziny.
    Ponowne wlaczenie zamyka poprzednie i liczy czas od nowa."""
    from datetime import datetime, timedelta
    rejestr, _, wpis, email = _moja_kancelaria(request)
    if email not in _wlasciciele(wpis):
        raise HTTPException(403, "Dostęp serwisowy włącza właściciel kancelarii.")
    if not 1 <= dane.godziny <= _SERWIS_MAKS_GODZIN:
        raise HTTPException(400, "Czas dostępu: od 1 godziny do 7 dni.")
    lista = wpis.setdefault("serwis", [])
    trwa = _serwis_trwa(wpis)
    if trwa:
        trwa["odwolano"] = _teraz()
    do = (datetime.now() + timedelta(hours=dane.godziny)).isoformat(timespec="seconds")
    lista.append({"wlaczyl": email, "od": _teraz(), "do": do, "odwolano": None, "uzyli": []})
    _zapisz_rejestr(rejestr)
    log.info("kancelaria %s: wlaczono dostep serwisowy na %d h", wpis["id"], dane.godziny)
    return _opis_serwisu(wpis)


@router_serwisu.delete("")
def odwolaj_serwis(request: Request):
    rejestr, _, wpis, email = _moja_kancelaria(request)
    if email not in _wlasciciele(wpis):
        raise HTTPException(403, "Dostęp serwisowy odwołuje właściciel kancelarii.")
    trwa = _serwis_trwa(wpis)
    if trwa:
        trwa["odwolano"] = _teraz()
        _zapisz_rejestr(rejestr)
        log.info("kancelaria %s: odwolano dostep serwisowy", wpis["id"])
    return _opis_serwisu(wpis)


# --- lista administratorow (panel) -------------------------------------------

@router.get("/administratorzy")
def lista_adminow(request: Request):
    _wymagaj_admina(request)
    naglowek = request.headers.get("authorization", "")
    return {"ja": _email_administratora(naglowek[7:]) if naglowek.startswith("Bearer ") else "",
            "administratorzy": _wszyscy_admini(), "stali": STALI_ADMINI}


@router.post("/administratorzy", status_code=201)
def dodaj_admina(request: Request, dane: Zaproszenie):
    """Konto do panelu: zaproszenie e-mailem, potem logowanie haslem."""
    _wymagaj_admina(request)
    _wymagaj_logowania()
    email = _poprawny_email(dane.email)
    lista = _wczytaj_adminow()
    if email in lista or email in STALI_ADMINI:
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
    if email not in _wszyscy_admini():
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
    if email in STALI_ADMINI:
        raise HTTPException(403, "Stalego administratora zmienia sie parametrem stosu "
                                 "Administratorzy, nie w panelu.")
    lista = _wczytaj_adminow()
    if email not in lista:
        raise HTTPException(404, "Tego adresu nie ma na liscie administratorow.")
    if logowanie.wlaczone():
        logowanie.usun_uzytkownika(email)
    _zapisz_adminow([a for a in lista if a != email])
    log.info("usunieto administratora")
    return {"usunieto": True}


# --- abonament (Stripe) ------------------------------------------------------
# Kancelaria ma w Stripe subskrypcje miesieczna. Termin trzymamy w jej wpisie
# rejestru ("oplacono_do"), dane Stripe w "stripe" (klient, subskrypcja,
# status), a oplacone faktury w "platnosci" - po identyfikatorze faktury
# poznajemy powtorzony webhook.

router_abonamentu = APIRouter(prefix="/api/abonament", tags=["abonament"])

# Subskrypcja w tych stanach jeszcze trwa - nowej nie zakladamy, tylko
# kierujemy do portalu (np. past_due: trzeba zmienic karte).
_TRWA = ("active", "trialing", "past_due", "unpaid", "incomplete")


def _subskrypcja(wpis: dict) -> dict:
    return dict(wpis.get("stripe") or {})


@router_abonamentu.get("")
def moj_abonament(request: Request):
    kancelaria = getattr(request.state, "kancelaria", None)
    if not kancelaria:
        # Lokalny tryb bez sesji SaaS: panel nie pokazuje abonamentu.
        return {"platnosci_wlaczone": False, "wymagany": False, "po_terminie": False,
                "dni_do_konca": None, "cena": platnosci.cena(), "moge_zaplacic": False,
                "subskrypcja": None, "konczy_sie": False, "historia": []}
    _, wpis = _znajdz(_wczytaj_rejestr(), kancelaria)
    if wpis is None:
        raise HTTPException(404, "Nie znaleziono kancelarii")
    email = getattr(request.state, "email", "")
    sub = _subskrypcja(wpis)
    return {**platnosci.stan(wpis), "platnosci_wlaczone": platnosci.wlaczone(),
            "cena": platnosci.cena(),
            "moge_zaplacic": bool(email) and email in _wlasciciele(wpis),
            "subskrypcja": sub.get("status") if sub.get("status") in _TRWA else None,
            "konczy_sie": bool(sub.get("anulowana")),
            "historia": [{k: p.get(k) for k in ("data", "kwota", "status", "oplacono_do", "faktura")}
                         for p in wpis.get("platnosci", [])[-12:]]}


def _wlasciciel_placi(request: Request) -> dict:
    if not platnosci.wlaczone():
        raise HTTPException(503, "Platnosci nie sa skonfigurowane na tym serwerze.")
    _, _, wpis, email = _moja_kancelaria(request)
    if email not in _wlasciciele(wpis):
        raise HTTPException(403, "Abonamentem zarzadza wlasciciel kancelarii.")
    return {"wpis": wpis, "email": email}


@router_abonamentu.post("", status_code=201)
def zaplac(request: Request):
    """Strona platnosci Stripe zakladajaca subskrypcje; gdy subskrypcja juz
    trwa - portal klienta, zeby nie obciazyc kancelarii dwa razy."""
    dane = _wlasciciel_placi(request)
    wpis, sub = dane["wpis"], _subskrypcja(dane["wpis"])
    try:
        if sub.get("klient") and sub.get("status") in _TRWA:
            return platnosci.utworz_portal(sub["klient"])
        return platnosci.utworz_checkout(wpis["id"], dane["email"], sub.get("klient", ""),
                                         wpis.get("oplacono_do"))
    except platnosci.BladPlatnosci as blad:
        raise HTTPException(502, str(blad))


@router_abonamentu.post("/portal", status_code=201)
def portal(request: Request):
    """Portal klienta Stripe: zmiana karty, faktury, rezygnacja."""
    sub = _subskrypcja(_wlasciciel_placi(request)["wpis"])
    if not sub.get("klient"):
        raise HTTPException(409, "Kancelaria nie ma jeszcze abonamentu w Stripe.")
    try:
        return platnosci.utworz_portal(sub["klient"])
    except platnosci.BladPlatnosci as blad:
        raise HTTPException(502, str(blad))


router_stripe = APIRouter(prefix="/api/stripe", tags=["stripe"])


def _kancelaria_stripe(rejestr: dict, id_k: str, klient: str) -> dict | None:
    """Po metadanych, a gdy ich brak - po kliencie Stripe zapisanym wczesniej."""
    if id_k:
        return _znajdz(rejestr, id_k)[1]
    if klient:
        return next((w for w in rejestr.values() if _subskrypcja(w).get("klient") == klient), None)
    return None


@router_stripe.post("/webhook")
async def webhook_stripe(request: Request):
    """Zdarzenia Stripe. Wierzymy tylko podpisowi - ta sciezka jest otwarta
    dla kazdego. 2xx konczy ponawianie; blad podpisu - 400."""
    global _CACHE
    tresc = await request.body()
    try:
        zdarzenie = platnosci.odczytaj_zdarzenie(tresc, request.headers.get("stripe-signature", ""))
    except platnosci.BladPodpisu as blad:
        log.warning("stripe: odrzucono webhook (%s)", blad)
        return JSONResponse({"odebrano": False}, 400)

    typ = zdarzenie["type"]
    obiekt = (zdarzenie.get("data") or {}).get("object") or {}
    # Zakup pakietu kredytow to platnosc jednorazowa - subskrypcji nie dotyka.
    if typ == "checkout.session.completed" and tokenomia.z_platnosci_stripe(obiekt):
        return {"odebrano": True}
    _CACHE = None          # druga kopia aplikacji mogla przed chwila zmienic rejestr
    rejestr = _wczytaj_rejestr()

    if typ == "checkout.session.completed":
        id_k = obiekt.get("client_reference_id") or (obiekt.get("metadata") or {}).get("kancelaria", "")
        klient = obiekt.get("customer") or ""
        subskrypcja = obiekt.get("subscription") or ""
    elif typ.startswith("invoice."):
        id_k, klient = platnosci.kancelaria_faktury(obiekt), obiekt.get("customer") or ""
        subskrypcja = platnosci.subskrypcja_faktury(obiekt)
    elif typ.startswith("customer.subscription."):
        id_k = (obiekt.get("metadata") or {}).get("kancelaria", "")
        klient, subskrypcja = obiekt.get("customer") or "", obiekt.get("id") or ""
    else:
        return {"odebrano": True}

    wpis = _kancelaria_stripe(rejestr, id_k, klient)
    if wpis is None:
        # Podpisane, ale nie nasze (np. inny produkt na tym koncie Stripe).
        log.warning("stripe: %s bez znanej kancelarii", typ)
        return {"odebrano": True}
    sub = wpis.setdefault("stripe", {})
    if klient:
        sub["klient"] = klient
    if subskrypcja:
        sub["subskrypcja"] = subskrypcja

    if typ == "checkout.session.completed":
        # Bez platnosci teraz = trwa okres probny; dokladny stan i tak
        # przyjdzie w customer.subscription.updated.
        platne = obiekt.get("payment_status")
        sub["status"] = {"paid": "active", "no_payment_required": "trialing"}.get(platne, "incomplete")
    elif typ.startswith("customer.subscription."):
        sub["status"] = "canceled" if typ.endswith(".deleted") else obiekt.get("status", "")
        sub["anulowana"] = bool(obiekt.get("cancel_at_period_end") or obiekt.get("cancel_at"))
        log.info("stripe: kancelaria %s, subskrypcja %s", wpis["id"], sub["status"])
    elif typ == "invoice.paid":
        historia = wpis.setdefault("platnosci", [])
        if any(p.get("faktura_id") == obiekt.get("id") for p in historia):
            return {"odebrano": True}
        koniec = platnosci.koniec_okresu(obiekt)
        # Starsza faktura doszla po nowszej - terminu nie cofamy.
        if koniec and koniec > (wpis.get("oplacono_do") or ""):
            wpis["oplacono_do"] = koniec
        if obiekt.get("amount_paid"):
            sub["status"] = "active"
            historia.append({"faktura_id": obiekt.get("id"), "status": "true", "data": _teraz(),
                             "kwota": f"{obiekt['amount_paid'] / 100:.2f}",
                             "faktura": obiekt.get("hosted_invoice_url"),
                             "oplacono_do": wpis.get("oplacono_do")})
        else:
            # Faktura zerowa (okres probny) - termin tak, wpis w historii nie.
            historia.append({"faktura_id": obiekt.get("id"), "status": "proba", "data": _teraz()})
        log.info("stripe: kancelaria %s oplacona do %s", wpis["id"], wpis.get("oplacono_do"))
        # Nowy okres abonamentu = nowa pula kredytow planu (raz na fakture).
        if tokenomia.WLACZONA:
            tokenomia.odnow_pule(wpis["id"], wpis.get("plan") or tokenomia.PLAN_DOMYSLNY,
                                 znacznik=obiekt.get("id", ""))
    elif typ == "invoice.payment_failed":
        # Stripe sam ponawia i wysyla e-mail; my tylko odnotowujemy.
        log.warning("stripe: kancelaria %s, nieudane obciazenie", wpis["id"])

    _zapisz_rejestr(rejestr)
    return {"odebrano": True}
