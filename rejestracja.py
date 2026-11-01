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
    # Klucz wpisu to losowy skrot; do spraw wchodzi sie tylko logujac sie.
    rejestr[autoryzacja._sha(secrets.token_hex(32))] = wpis
    autoryzacja._zapisz_rejestr(rejestr)
    log.info("rejestracja: nowa kancelaria %s, pliki: %s", id_k, dane.przechowywanie)
    return odpowiedz


# --- dokumenty po zalogowaniu ---------------------------------------------

router_dokumentow = APIRouter(prefix="/api/dokumenty", tags=["dokumenty"])


def _ja(request: Request) -> tuple[dict, str, dict, str, bool]:
    rejestr, skrot, wpis, email = autoryzacja._moja_kancelaria(request)
    zespol = wpis.get("zespol") or []
    # Kancelarie zalozone przed zespolami nie maja wlasciciela, a bez niego
    # nikt nie moze zaakceptowac umowy i sprawy sa zablokowane na zawsze.
    # Jedyna osoba w zespole jest wtedy wlascicielem - zapisujemy to na stale.
    if (email and not autoryzacja._wlasciciele(wpis)
            and len(zespol) == 1 and zespol[0].get("email") == email):
        zespol[0]["rola"] = "wlasciciel"
        autoryzacja._zapisz_rejestr(rejestr)
        log.info("kancelaria %s: jedyna osoba w zespole zostala wlascicielem", wpis.get("id"))
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
        "dane_pelne": _dane_pelne(wpis),
        "do_akceptacji": _do_akceptacji(wpis, email, wlasciciel),
        "dokumenty": [{"nazwa": n, "tytul": dokumenty_prawne.tytul(n),
                       "wersja": dokumenty_prawne.wersja(n),
                       "wewnetrzny": n in dokumenty_prawne.WEWNETRZNE} for n in dokumenty_prawne.DOKUMENTY],
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
    # Dane kancelarii sa zapisane na stale. Po zmianie dokumentow wystarczy
    # akceptacja - dane podaje sie tylko wtedy, gdy ich jeszcze nie ma albo
    # sa niepelne; zmienia sie je osobno (POST /api/dokumenty/dane).
    if not _dane_pelne(wpis):
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


def _dane_pelne(wpis: dict) -> bool:
    """Czy zapisane dane kancelarii przechodza te same wymagania co przy
    rejestracji - wtedy nie trzeba ich podawac ponownie."""
    try:
        _sprawdz_dane(DaneKancelarii(**(wpis.get("dane") or {})))
    except HTTPException:
        return False
    return True


@router_dokumentow.post("/dane")
def zmien_dane(dane: DaneKancelarii, request: Request):
    """Wlasciciel poprawia dane kancelarii (np. nowy adres) bez ponownej
    akceptacji dokumentow. Umowa i komplet pokazuja zawsze dane biezace."""
    rejestr, _, wpis, _, wlasciciel = _ja(request)
    if not wlasciciel:
        raise HTTPException(403, "Dane kancelarii zmienia właściciel kancelarii.")
    wpis["dane"] = {**_sprawdz_dane(dane), "zmieniono": autoryzacja._teraz()}
    autoryzacja._zapisz_rejestr(rejestr)
    log.info("kancelaria %s: zmieniono dane kancelarii", wpis["id"])
    return wpis["dane"]


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
                   "u-klienta": "pliki na komputerze kancelarii (folder wskazany przez kancelarię)"}


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


def _pola_kancelarii(wpis: dict) -> dict:
    """Dane kancelarii wspolne dla dokumentow wypelnianych przez aplikacje."""
    dane, umowa = wpis.get("dane") or {}, wpis.get("umowa") or {}
    chmura = wpis.get("przechowywanie", "chmura") == "chmura"
    return {
        "kancelaria": wpis["nazwa"], "notariusze": dane.get("notariusze"),
        "adres": dane.get("adres"), "nip": dane.get("nip") or "-",
        "email": ", ".join(autoryzacja._wlasciciele(wpis)),
        "data": _data(autoryzacja._teraz())[:10],
        "zawarto": (_data(umowa.get("zawarto") or umowa["zaakceptowano"])[:10]
                    if umowa.get("zaakceptowano") else "jeszcze niezawarta"),
        "iod": "nie wyznaczono albo według dokumentacji kancelarii",
        "przechowywanie": _PRZECHOWYWANIE.get(wpis.get("przechowywanie", "chmura")),
        "kalendarz": ("tak - kancelaria przechowuje pliki w chmurze, kalendarz i spis telefonów są dostępne"
                      if chmura else "nie - w trybie „Pliki na komputerze kancelarii” kalendarz i spis telefonów "
                                     "są wyłączone; wpisu nie trzeba dodawać"),
        "uzytkownicy": str(len(autoryzacja._zespol(wpis))),
    }


_TYLKO_WLASCICIEL = ("<p><em>Zestawienie osób z zespołu widzi tylko właściciel kancelarii.</em></p>")


def _potwierdzenia_instrukcji(wpis: dict) -> str:
    osoby = "".join(
        f"<tr><td>{html.escape(o['email'])}</td><td>"
        + (html.escape(f"{_data((o.get('instrukcja') or {}).get('data'))}, wersja "
                       f"{(o.get('instrukcja') or {}).get('wersja', '')}")
           if (o.get("instrukcja") or {}).get("data") else "jeszcze nie potwierdziła / nie potwierdził")
        + "</td></tr>"
        for o in autoryzacja._zespol(wpis))
    return ("<h2>Potwierdzenia instrukcji korzystania z AI</h2>"
            f"<table><tr><th>Osoba</th><th>Potwierdzenie</th></tr>{osoby}</table>")


def _upowaznienia(wpis: dict, osoby: list[dict]) -> str:
    """Jedna ramka na osobe: dane z konta, reszte kancelaria dopisuje."""
    notariusze = (wpis.get("dane") or {}).get("notariusze", "")
    czesci = []
    for i, o in enumerate(osoby, 1):
        od = _data(o.get("dolaczyl") or o.get("zaproszono"))[:10] or "...................."
        rola = "właściciel konta kancelarii" if o.get("rola") == "wlasciciel" else "członek zespołu"
        wiersze = [
            ("Konto w notarai (e-mail)", o.get("email", "")),
            ("Rola w aplikacji", rola),
            ("Imię i nazwisko", "........................................................"),
            ("Stanowisko", "........................................................"),
            ("Upoważnienie od dnia", od),
            ("Upoważnienie do dnia", "do odwołania, najpóźniej do usunięcia konta"),
        ]
        tabela = "".join(f"<tr><th>{html.escape(k)}</th><td>{html.escape(v)}</td></tr>" for k, v in wiersze)
        czesci.append(
            f'<div class="upowaznienie"><h3>Upoważnienie {i}</h3>'
            f"<table>{tabela}</table>"
            f'<p class="podpis">Administrator: {html.escape(notariusze)} '
            "....................................... (podpis albo e-mail)</p>"
            '<p class="podpis">Oświadczam, że zapoznałam / zapoznałem się z treścią upoważnienia i przyjmuję '
            "zobowiązania z pkt 3. ....................................... (podpis albo odpowiedź e-mailem)</p>"
            "</div>")
    if not czesci:
        return "<p>W zespole kancelarii nie ma jeszcze żadnych kont.</p>"
    return "".join(czesci)


def _wypelnienie(nazwa: str, wpis: dict, email: str = "",
                 wlasciciel: bool = False) -> tuple[dict | None, str, str]:
    """(pola do wstawienia, ramka przed trescia, dodatek po tresci) - dane
    tej kancelarii. Zestawienia osob z zespolu dostaje tylko wlasciciel;
    czlonek zespolu widzi wlasne upowaznienie."""
    if nazwa == "umowa":
        return None, _ramka_umowy(wpis), ""
    if nazwa == "dpia":
        dpia = wpis.get("dpia") or {}
        return {
            **_pola_kancelarii(wpis),
            "data": _data(dpia.get("przyjeto") or autoryzacja._teraz())[:10],
            "przyjeto": (f"{_data(dpia['przyjeto'])}, {dpia.get('email', '')}" if dpia.get("przyjeto")
                         else "jeszcze nie przyjęto"),
        }, "", ""
    if nazwa == "zasady-ai":
        return _pola_kancelarii(wpis), "", (_potwierdzenia_instrukcji(wpis) if wlasciciel else _TYLKO_WLASCICIEL)
    if nazwa == "upowaznienia":
        zespol = autoryzacja._zespol(wpis)
        osoby = zespol if wlasciciel else [o for o in zespol if o.get("email") == email]
        return _pola_kancelarii(wpis), "", _upowaznienia(wpis, osoby)
    if nazwa in dokumenty_prawne.WEWNETRZNE:
        return _pola_kancelarii(wpis), "", ""
    return None, "", ""


# Kolejnosc w komplecie: najpierw to, co kancelaria zawarla, potem to, co
# przyjela u siebie, instrukcje dla zespolu, na koncu dokumenty wewnetrzne.
KOMPLET = ("regulamin", "umowa", "prywatnosc", "dpia", "instrukcja", "kancelaria",
           *dokumenty_prawne.WEWNETRZNE)


def _strona_tytulowa(wpis: dict, wlasciciel: bool) -> str:
    umowa, dpia = wpis.get("umowa") or {}, wpis.get("dpia") or {}
    stan = {
        "regulamin": (f"zaakceptowany {_data(umowa['zaakceptowano'])}, wersja {umowa.get('regulamin', '')}"
                      if umowa.get("zaakceptowano") else "jeszcze niezaakceptowany"),
        "umowa": (f"zawarta {_data(umowa.get('zawarto') or umowa['zaakceptowano'])}, wersja {umowa.get('umowa', '')}"
                  if umowa.get("zaakceptowano") else "jeszcze niezawarta"),
        "dpia": (f"przyjęta {_data(dpia['przyjeto'])}" if dpia.get("przyjeto")
                 else "czeka na przyjęcie przez notariusza"),
        "instrukcja": "potwierdza ją każda osoba w zespole przy pierwszym logowaniu",
        **{n: "dokument wewnętrzny: przyjmij w kancelarii i przechowuj" for n in dokumenty_prawne.WEWNETRZNE},
    }
    wiersze = "".join(
        f"<tr><td>{i}.</td><td>{html.escape(dokumenty_prawne.tytul(n))}</td>"
        f"<td>{html.escape(dokumenty_prawne.wersja(n))}</td>"
        f"<td>{html.escape(stan.get(n, 'do wiadomości'))}</td></tr>"
        for i, n in enumerate(KOMPLET, 1))
    potwierdzenia = _potwierdzenia_instrukcji(wpis) if wlasciciel else ""
    return (
        f"<h1>Dokumenty kancelarii: {html.escape(wpis['nazwa'])}</h1>"
        f"<p>Komplet dokumentów prawnych usługi notarai, z danymi kancelarii, "
        f"stan na {html.escape(_data(autoryzacja._teraz())[:10])}. Wszystko zawarto "
        "i przyjęto w aplikacji, bez podpisu. Zachowaj ten plik w dokumentacji RODO kancelarii.</p>"
        f"<table><tr><th>Lp.</th><th>Dokument</th><th>Wersja</th><th>Stan</th></tr>{wiersze}</table>"
        f"{potwierdzenia}"
    )


@router_dokumentow.get("/komplet", response_class=HTMLResponse)
def komplet(request: Request):
    """Wszystkie dokumenty kancelarii w jednym pliku: strona tytulowa ze
    stanem akceptacji, potem kazdy dokument od nowej strony przy wydruku."""
    _, _, wpis, email, wlasciciel = _ja(request)
    czesci = [f'<section class="dok">{_strona_tytulowa(wpis, wlasciciel)}</section>']
    for nazwa in KOMPLET:
        pola, przed, po = _wypelnienie(nazwa, wpis, email, wlasciciel)
        czesci.append(f'<section class="dok">{przed}{dokumenty_prawne.html_dokumentu(nazwa, pola)}{po}</section>')
    log.info("kancelaria %s: pobrano komplet dokumentow", wpis["id"])
    return (
        '<!doctype html><html lang="pl"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Dokumenty kancelarii - notarai</title><style>{dokumenty_prawne.STYL}"
        ".dok+.dok{border-top:2px solid #ccc;margin-top:48px;padding-top:24px}"
        "@media print{.dok+.dok{break-before:page;border:0;margin:0;padding:0}}</style></head>"
        f"<body>{''.join(czesci)}</body></html>"
    )


@router_dokumentow.get("/{nazwa}", response_class=HTMLResponse)
def dokument(nazwa: str, request: Request):
    """Dokument jako strona HTML, z danymi tej kancelarii. Przegladarka
    pobiera go przez api() (z tokenem), nie zwyklym odnosnikiem."""
    if nazwa not in dokumenty_prawne.DOKUMENTY:
        raise HTTPException(404, "Nie ma takiego dokumentu.")
    _, _, wpis, email, wlasciciel = _ja(request)
    pola, przed, po = _wypelnienie(nazwa, wpis, email, wlasciciel)
    return dokumenty_prawne.strona(nazwa, pola, przed=przed, po=po)
