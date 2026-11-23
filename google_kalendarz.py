"""Opcjonalny, minimalizujacy dane most NotarAI <-> Google Calendar.

Google widzi tylko neutralne bloki czasu. Szczegoly czynnosci, strony, sprawy
i telefony pozostaja w kalendarzu kancelarii. Refresh token tylko w AWS
Secrets Manager (lokalnie: pamiec procesu), nigdy w pliku S3 ani w przegladarce.

Wersja bez webhookow: synchronizacja przy otwarciu kalendarza i na zadanie.
"""
import hashlib
import hmac
import logging
import os
import re
import secrets
import time
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

import autoryzacja
import kalendarz
import korespondencja
import magazyn
import skrzynki

log = logging.getLogger("pieczapp.google_kalendarz")
router = APIRouter(prefix="/api/google-kalendarz", tags=["google-kalendarz"])
PLIK = "google_kalendarz"
STREFA = ZoneInfo("Europe/Warsaw")
API = "https://www.googleapis.com/calendar/v3"
TOKEN_URL = "https://oauth2.googleapis.com/token"
ZAKRES = "https://www.googleapis.com/auth/calendar.events openid email"
OKNO_WSTECZ = 30
OKNO_NAPRZOD = 365


class BladGoogle(Exception):
    pass


class SejfGoogle(korespondencja.SejfSkrzynki):
    def nazwa(self, kancelaria: str) -> str:
        return "notarai-google-kalendarz-" + re.sub(r"[^A-Za-z0-9_+=.@-]", "-", kancelaria)


sejf = SejfGoogle()
sejf_lokalny = korespondencja.SejfPamieci()


def _sejf():
    return sejf if magazyn.TRYB == "s3" else sejf_lokalny


def _klient_id():
    return os.getenv("PIECZAPP_OAUTH_GOOGLE_KLIENT", "")


def _klient_sekret():
    return os.getenv("PIECZAPP_OAUTH_GOOGLE_SEKRET", "")


def _adres_powrotu():
    baza = os.getenv("PIECZAPP_ADRES", "").rstrip("/") or (
        "http://127.0.0.1:" + os.getenv("PIECZAPP_PORT", "8000"))
    if autoryzacja.MULTI and not baza.startswith("https://"):
        raise BladGoogle("Adres publiczny aplikacji musi korzystać z HTTPS.")
    return baza + "/api/google-kalendarz/powrot"


def _stan():
    return magazyn.wczytaj_plik_kancelarii(PLIK, {})


def _zapisz(funkcja):
    return magazyn.zmien_plik_kancelarii(PLIK, funkcja, {})


def _wlasciciel(request: Request):
    if magazyn.u_klienta():
        raise HTTPException(409, "Ta kancelaria przechowuje pliki u siebie. Synchronizacja serwerowa jest wyłączona.")
    if getattr(request.state, "serwis", False):
        raise HTTPException(403, "Dostęp serwisowy nie obejmuje łączenia kalendarzy.")
    if autoryzacja.MULTI:
        _, _, biuro, email = autoryzacja._moja_kancelaria(request)
        autoryzacja._wymagaj_wlasciciela(biuro, email)


def _skonfigurowany():
    return bool(_klient_id() and _klient_sekret())


def _wymagaj_polaczenia():
    if not _stan().get("polaczono"):
        raise HTTPException(409, "Najpierw połącz Google Calendar.")


def _google_token(dane: dict):
    try:
        odp = httpx.post(TOKEN_URL, data={
            "client_id": _klient_id(), "client_secret": _klient_sekret(), **dane}, timeout=20)
        wynik = odp.json()
    except (httpx.HTTPError, ValueError):
        raise BladGoogle("Nie udało się połączyć z Google.") from None
    if odp.status_code != 200:
        raise BladGoogle("Google odmówił autoryzacji. Połącz konto ponownie.")
    return wynik


def _token():
    k = magazyn.kancelaria()
    dane = _sejf().wczytaj(k)
    refresh = dane.get("refresh_token")
    if not refresh:
        raise BladGoogle("Brak tokenu Google. Połącz kalendarz ponownie.")
    wynik = _google_token({"grant_type": "refresh_token", "refresh_token": refresh})
    if wynik.get("refresh_token") and wynik["refresh_token"] != refresh:
        _sejf().zapisz(k, {"refresh_token": wynik["refresh_token"]})
    return wynik["access_token"]


def _zadanie(token: str, metoda: str, adres: str, **kw):
    try:
        odp = httpx.request(metoda, API + adres,
                            headers={"Authorization": "Bearer " + token}, timeout=25, **kw)
    except httpx.HTTPError:
        raise BladGoogle("Google Calendar jest chwilowo niedostępny.") from None
    if odp.status_code == 404 and metoda in ("GET", "DELETE"):
        return None
    if odp.status_code not in (200, 201, 204):
        raise BladGoogle("Google Calendar odrzucił operację (" + str(odp.status_code) + ").")
    return odp.json() if odp.content else {}


def _czas(event: dict):
    """Tylko pojedyncze wydarzenia w jednym dniu; bez przesylania opisow."""
    poczatek = event.get("start") or {}
    koniec = event.get("end") or {}
    if poczatek.get("date") and koniec.get("date"):
        if (datetime.fromisoformat(koniec["date"]) -
                datetime.fromisoformat(poczatek["date"])).days != 1:
            return None
        return poczatek["date"], "08:30", "18:00"
    if not poczatek.get("dateTime") or not koniec.get("dateTime"):
        return None
    try:
        a = datetime.fromisoformat(poczatek["dateTime"].replace("Z", "+00:00"))
        b = datetime.fromisoformat(koniec["dateTime"].replace("Z", "+00:00"))
        # Google pozwala przeslac czas z osobnym polem timeZone, bez offsetu.
        if a.tzinfo is None:
            a = a.replace(tzinfo=STREFA)
        if b.tzinfo is None:
            b = b.replace(tzinfo=STREFA)
        a, b = a.astimezone(STREFA), b.astimezone(STREFA)
    except ValueError:
        return None
    if a.date() != b.date() or b <= a or b.hour == 0 and b.minute == 0:
        return None
    return a.date().isoformat(), a.strftime("%H:%M"), b.strftime("%H:%M")


def _podpis(wpis: dict):
    return hashlib.sha256("|".join(str(wpis.get(k, "")) for k in ("data", "godzina", "koniec"))
                          .encode("utf-8")).hexdigest()[:20]


def _podpis_google(event: dict):
    czas = _czas(event)
    if not czas:
        return ""
    return hashlib.sha256("|".join(czas).encode("utf-8")).hexdigest()[:20]


def _cialo(wpis: dict, z_id: bool = False):
    d, a, b = wpis["data"], wpis["godzina"], wpis.get("koniec") or kalendarz._koniec(wpis)
    wynik = {"summary": "Zajęte - NotarAI", "start": {"dateTime": f"{d}T{a}:00", "timeZone": "Europe/Warsaw"},
             "end": {"dateTime": f"{d}T{b}:00", "timeZone": "Europe/Warsaw"}}
    if z_id:
        wynik["extendedProperties"] = {"private": {"notarai_id": wpis["id"]}}
    return wynik


def _wydarzenia(token):
    teraz = datetime.now(STREFA)
    od = (teraz - timedelta(days=OKNO_WSTECZ)).isoformat()
    do = (teraz + timedelta(days=OKNO_NAPRZOD)).isoformat()
    wszystkie = {}
    nastepna = None
    while True:
        parametry = {"timeMin": od, "timeMax": do, "singleEvents": "true",
                     "maxResults": 1000, "showDeleted": "false"}
        if nastepna:
            parametry["pageToken"] = nastepna
        dane = _zadanie(token, "GET", "/calendars/primary/events", params=parametry)
        for w in dane.get("items") or []:
            if w.get("id") and w.get("status") != "cancelled" and w.get("transparency") != "transparent":
                wszystkie[w["id"]] = w
        nastepna = dane.get("nextPageToken")
        if not nastepna:
            return wszystkie


def _sync(token):
    stan = _stan()
    mapy = dict(stan.get("mapowania") or {})
    google = _wydarzenia(token)
    lokalne = {w["id"]: w for w in kalendarz.lista()}
    obsluzone_g = set()
    obsluzone_l = set()
    wynik = {"dodano_w_google": 0, "dodano_w_notarai": 0, "zmieniono": 0,
             "usunieto": 0, "konflikty": 0, "pominieto": 0}
    poczatek = (datetime.now(STREFA) - timedelta(days=OKNO_WSTECZ)).date().isoformat()
    koniec = (datetime.now(STREFA) + timedelta(days=OKNO_NAPRZOD)).date().isoformat()

    for id_l, zapis in list(mapy.items()):
        id_g = zapis.get("google_id")
        if not id_g:
            del mapy[id_l]
            continue
        lok = lokalne.get(id_l)
        ev = google.get(id_g)
        # Wydarzenie przeniesione poza okres listowania wciaz moze istniec.
        if not ev and lok and poczatek <= lok.get("data", "") <= koniec:
            ev = _zadanie(token, "GET", "/calendars/primary/events/" + quote(id_g, safe=""))
        if not ev and lok and not (poczatek <= lok.get("data", "") <= koniec):
            continue  # Nie zgadujemy czy usunieto wpis spoza okna.
        obsluzone_g.add(id_g)
        obsluzone_l.add(id_l)
        if not lok and ev:
            _zadanie(token, "DELETE", "/calendars/primary/events/" + quote(id_g, safe=""))
            wynik["usunieto"] += 1
            del mapy[id_l]
            continue
        if not ev:
            if lok:
                kalendarz.usun(id_l)
                wynik["usunieto"] += 1
            del mapy[id_l]
            continue
        cz = _czas(ev)
        if not cz:
            wynik["pominieto"] += 1
            continue
        nowy_l = _podpis(lok)
        nowy_g = _podpis_google(ev)
        stary_l = zapis.get("lokalny")
        stary_g = zapis.get("google")
        l_zmieniony = nowy_l != stary_l
        g_zmieniony = nowy_g != stary_g
        if l_zmieniony and g_zmieniony:
            wynik["konflikty"] += 1
            continue
        if g_zmieniony:
            try:
                kalendarz.zmien(id_l, {**lok, "data": cz[0], "godzina": cz[1], "koniec": cz[2]})
            except ValueError:
                wynik["konflikty"] += 1
                continue
            wynik["zmieniono"] += 1
            nowy_l = nowy_g
        elif l_zmieniony:
            ev = _zadanie(token, "PATCH", "/calendars/primary/events/" + quote(id_g, safe=""),
                          json=_cialo(lok))
            nowy_g = _podpis_google(ev)
            wynik["zmieniono"] += 1
        mapy[id_l] = {**zapis, "lokalny": nowy_l, "google": nowy_g}

    for id_g, ev in google.items():
        if id_g in obsluzone_g:
            continue
        cz = _czas(ev)
        if not cz:
            wynik["pominieto"] += 1
            continue
        # Odzyskanie skojarzenia po utracie metadanych, bez duplikowania.
        id_l = ((ev.get("extendedProperties") or {}).get("private") or {}).get("notarai_id")
        if id_l and id_l in lokalne and id_l not in obsluzone_l:
            lok = lokalne[id_l]
            mapy[id_l] = {"google_id": id_g, "pochodzenie": "notarai",
                          "lokalny": _podpis(lok), "google": _podpis_google(ev)}
            obsluzone_l.add(id_l)
            continue
        try:
            lok = kalendarz.dodaj({"data": cz[0], "godzina": cz[1], "koniec": cz[2],
                                   "tytul": "Zajęte w Google"})
        except ValueError:
            wynik["konflikty"] += 1
            continue
        mapy[lok["id"]] = {"google_id": id_g, "pochodzenie": "google",
                           "lokalny": _podpis(lok), "google": _podpis_google(ev)}
        obsluzone_l.add(lok["id"])
        wynik["dodano_w_notarai"] += 1

    for id_l, lok in lokalne.items():
        if id_l in obsluzone_l or not lok.get("godzina"):
            continue
        if not (poczatek <= lok["data"] <= koniec):
            continue
        ev = _zadanie(token, "POST", "/calendars/primary/events", json=_cialo(lok, z_id=True))
        mapy[id_l] = {"google_id": ev["id"], "pochodzenie": "notarai",
                      "lokalny": _podpis(lok), "google": _podpis_google(ev)}
        wynik["dodano_w_google"] += 1

    # Dane medyczne, dane sprawy i telefony nie pojawiaja sie w mapowaniach.
    def zapis(d):
        d["mapowania"] = mapy
        d["odswiezono"] = datetime.now(STREFA).isoformat(timespec="seconds")
        d["wynik"] = wynik
    _zapisz(zapis)
    return wynik


@router.get("/stan")
def stan_polaczenia(request: Request):
    _wlasciciel(request)
    s = _stan()
    return {"dostepne": _skonfigurowany(), "polaczono": bool(s.get("polaczono")),
            "email": s.get("email", ""), "odswiezono": s.get("odswiezono", ""),
            "wynik": s.get("wynik") or {}}


@router.get("/start")
def rozpocznij(request: Request):
    _wlasciciel(request)
    if not _skonfigurowany():
        raise HTTPException(503, "Google Calendar nie jest jeszcze skonfigurowany na serwerze.")
    if autoryzacja.MULTI and not os.getenv("PIECZAPP_ADMIN_TOKEN"):
        raise HTTPException(503, "Brak trwałego klucza podpisującego sesje OAuth.")
    if _stan().get("polaczono"):
        raise HTTPException(409, "Kalendarz jest już połączony. Najpierw go odłącz.")
    weryfikator, wyzwanie = skrzynki.pkce()
    nonce = secrets.token_urlsafe(20)
    limit = time.time() + 900
    # Jednorazowy weryfikator PKCE jest sekretem: wyłącznie Secrets Manager.
    _sejf().zapisz(magazyn.kancelaria(), {"oczekuje": {
        "nonce": nonce, "weryfikator": weryfikator, "do": limit}})
    state = korespondencja._podpisz({"k": magazyn.kancelaria(), "n": nonce, "do": limit, "p": "google-kalendarz"})
    adres = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
        "client_id": _klient_id(), "redirect_uri": _adres_powrotu(),
        "response_type": "code", "scope": ZAKRES, "state": state,
        "access_type": "offline", "prompt": "consent select_account",
        "code_challenge": wyzwanie, "code_challenge_method": "S256",
    })
    return {"adres": adres}


@router.get("/powrot")
def oauth_powrot(code: str = "", state: str = "", error: str = ""):
    # Ta trasa nie ma sesji Cognito: stan podpisany, odczyt jednorazowy z biura.
    if error or not code:
        return RedirectResponse("/#google-kalendarz=blad", status_code=303)
    try:
        dane = korespondencja._sprawdz_podpis(state)
        if dane.get("p") != "google-kalendarz" or not re.fullmatch(r"[a-z0-9-]{1,60}|lokalna", dane.get("k", "")):
            raise BladGoogle("Nieprawidłowy stan logowania.")
        znacznik = magazyn.kancelaria_var.set(dane["k"])
        try:
            ocz = _sejf().wczytaj(magazyn.kancelaria()).get("oczekuje") or {}
            if not ocz or ocz.get("do", 0) < time.time() or not hmac.compare_digest(
                    ocz.get("nonce", ""), dane["n"]):
                raise BladGoogle("Sesja logowania wygasła lub została już użyta.")
            verifier = ocz["weryfikator"]
            # Po użyciu nie przechowujemy ani podpisanego stanu, ani weryfikatora.
            _sejf().zapisz(magazyn.kancelaria(), {})
            tokeny = _google_token({"grant_type": "authorization_code", "code": code,
                                   "redirect_uri": _adres_powrotu(), "code_verifier": verifier})
            if not tokeny.get("refresh_token"):
                raise BladGoogle("Google nie wydał dostępu offline. Spróbuj połączyć ponownie.")
            # Tylko e-mail wlasciciela konta; bez wydarzen i kontaktow.
            email = ""
            try:
                odp = httpx.get("https://www.googleapis.com/oauth2/v3/userinfo",
                                headers={"Authorization": "Bearer " + tokeny["access_token"]}, timeout=15)
                if odp.status_code == 200:
                    email = str(odp.json().get("email") or "")[:200]
            except (httpx.HTTPError, ValueError):
                pass
            _sejf().zapisz(magazyn.kancelaria(), {"refresh_token": tokeny["refresh_token"]})
            _zapisz(lambda d: d.update({"polaczono": datetime.now(STREFA).isoformat(),
                                       "email": email, "mapowania": {}}))
        finally:
            magazyn.kancelaria_var.reset(znacznik)
    except (BladGoogle, korespondencja.BladSkrzynki, ValueError, KeyError):
        log.warning("google kalendarz: odmowa lub nieudane polaczenie")
        return RedirectResponse("/#google-kalendarz=blad", status_code=303)
    return RedirectResponse("/#google-kalendarz=polaczono", status_code=303)


@router.post("/synchronizuj")
def synchronizuj(request: Request):
    _wlasciciel(request)
    _wymagaj_polaczenia()
    blokada = secrets.token_hex(12)
    def zablokuj(d):
        b = d.get("blokada") or {}
        if b.get("do", 0) > time.time():
            raise HTTPException(409, "Trwa już synchronizacja kalendarza.")
        d["blokada"] = {"id": blokada, "do": time.time() + 180}
    _zapisz(zablokuj)
    try:
        return _sync(_token())
    except BladGoogle as blad:
        raise HTTPException(502, str(blad)) from None
    finally:
        def odblokuj(d):
            if (d.get("blokada") or {}).get("id") == blokada:
                d.pop("blokada", None)
        _zapisz(odblokuj)


@router.delete("/polaczenie")
def odlacz(request: Request):
    _wlasciciel(request)
    s = _stan()
    for id_l, mapa in (s.get("mapowania") or {}).items():
        if mapa.get("pochodzenie") == "google":
            kalendarz.usun(id_l)
    # Nadpisanie pustym sekretem pozwala podłączyć konto ponownie od razu;
    # AWS Secrets Manager po delete_secret trzymałby nazwę przez 7 dni.
    _sejf().zapisz(magazyn.kancelaria(), {})
    _zapisz(lambda d: d.clear())
    return {"polaczono": False}
