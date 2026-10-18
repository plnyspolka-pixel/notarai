"""Komputery z pomocnikiem notarai: laczenie z kancelaria bez przepisywania tokenu.

Notariusz nie kopiuje zadnego tokenu. Wyglada to tak:
  1. Pomocnik uruchomiony pierwszy raz prosi serwer o kod polaczenia
     (POST /api/pomocnik/parowanie) i otwiera notarai w przegladarce na
     adresie z tym kodem.
  2. Notariusz, zalogowany jak zwykle, widzi "Polaczyc komputer X?" i klika
     Polacz (POST /api/urzadzenia/polacz).
  3. Pomocnik, ktory w tym czasie dopytuje o swoj kod, dostaje wlasny token
     i od tej chwili pracuje sam - takze po restarcie komputera.

Kazdy komputer ma osobny token, wiec mozna odlaczyc jeden bez ruszania
pozostalych, a token pomocnika otwiera wylacznie /api/pomocnik/* - z
wykradzionego nie da sie przegladac spraw.

Kod polaczenia mozna wyludzic linkiem ("kliknij i potwierdz"). Dlatego
potwierdzenie przechodzi tylko z tego samego adresu IP, z ktorego pomocnik
poprosil o kod - pomocnik i przegladarka notariusza siedza na jednym
komputerze albo w jednej sieci kancelarii.

Uklad kluczy w S3:
  admin/urzadzenia/{skrot_tokenu}.json   kto to jest - do sprawdzenia tokenu
  admin/parowania/{kod}.json             trwajace laczenie, zyje 10 minut
  {kancelaria}/pomocnicy/{id}.json       lista komputerow kancelarii i obecnosc

Tokenow nie przechowujemy wprost, tylko skroty. W logach nie ma ani tokenow,
ani kodow, ani nazw komputerow (bywa w nich imie wlasciciela).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import time
from datetime import datetime, timedelta, timezone

import magazyn

log = logging.getLogger("pieczapp.urzadzenia")

PREFIKS_TOKENU = "pom_"
WAZNOSC_KODU_S = int(os.getenv("PIECZAPP_KOD_SEKUND", "600"))
ODDECH_MINUT = int(os.getenv("PIECZAPP_POMOCNIK_MINUT", "3"))
# Bez litery O i cyfry 0, I i 1 - kod bywa przepisywany z ekranu.
_ALFABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_DLUGOSC_KODU = 8


class BladParowania(RuntimeError):
    """Komunikat nadaje sie do pokazania notariuszowi."""


def dostepne() -> bool:
    """Pomocnik ma sens tylko w chmurze - tam, gdzie serwer nie ma przegladarki."""
    return magazyn.TRYB == "s3"


def _sha(tekst: str) -> str:
    return hashlib.sha256(tekst.encode()).hexdigest()


def _teraz() -> datetime:
    return datetime.now(timezone.utc)


def _czas(tekst: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(tekst) if tekst else None
    except ValueError:
        return None


# --- S3 ---------------------------------------------------------------------


def _czytaj(klucz: str) -> dict | None:
    try:
        odp = magazyn._klient_s3().get_object(Bucket=magazyn.BUCKET, Key=klucz)
    except Exception as blad:  # noqa: BLE001
        if type(blad).__name__ in ("NoSuchKey", "ClientError"):
            return None
        raise
    return json.loads(odp["Body"].read().decode("utf-8"))


def _pisz(klucz: str, dane: dict) -> None:
    magazyn._klient_s3().put_object(
        Bucket=magazyn.BUCKET, Key=klucz,
        Body=json.dumps(dane, ensure_ascii=False).encode("utf-8"),
        **magazyn._szyfrowanie(),
    )


def _usun(*klucze: str) -> None:
    magazyn._klient_s3().delete_objects(
        Bucket=magazyn.BUCKET,
        Delete={"Objects": [{"Key": k} for k in klucze], "Quiet": True},
    )


def _klucz_tokenu(skrot: str) -> str:
    return f"{magazyn.PREFIKS}/admin/urzadzenia/{skrot}.json"


def _klucz_parowania(kod: str) -> str:
    return f"{magazyn.PREFIKS}/admin/parowania/{kod}.json"


def _klucz_pomocnika(kancelaria: str, identyfikator: str) -> str:
    return f"{magazyn.PREFIKS}/{kancelaria}/pomocnicy/{identyfikator}.json"


# --- kod polaczenia ---------------------------------------------------------


def normalizuj_kod(kod: str) -> str:
    """"k7m4-qp2x", "K7M4 QP2X" i "K7M4QP2X" to ten sam kod."""
    return "".join(z for z in (kod or "").upper() if z in _ALFABET)


def pokaz_kod(kod: str) -> str:
    return f"{kod[:4]}-{kod[4:]}"


def _nazwa_komputera(nazwa: str) -> str:
    czysta = " ".join((nazwa or "").split())[:60]
    return czysta or "Komputer bez nazwy"


def rozpocznij(nazwa: str, ip: str) -> dict:
    """Pomocnik prosi o kod. Sekret zna tylko on - nim odbierze token."""
    kod = "".join(secrets.choice(_ALFABET) for _ in range(_DLUGOSC_KODU))
    sekret = secrets.token_urlsafe(32)
    _pisz(_klucz_parowania(kod), {
        "nazwa": _nazwa_komputera(nazwa),
        "ip": ip,
        "sekret": _sha(sekret),
        "utworzono": _teraz().isoformat(timespec="seconds"),
        "kancelaria": None,
    })
    log.info("parowanie: wydano kod")
    return {"kod": pokaz_kod(kod), "sekret": sekret, "wazny_s": WAZNOSC_KODU_S}


def _parowanie(kod: str) -> dict:
    kod = normalizuj_kod(kod)
    if len(kod) != _DLUGOSC_KODU:
        raise BladParowania("Kod ma 8 znaków, np. K7M4-QP2X.")
    wpis = _czytaj(_klucz_parowania(kod))
    utworzono = _czas((wpis or {}).get("utworzono"))
    if not wpis or not utworzono or _teraz() - utworzono > timedelta(seconds=WAZNOSC_KODU_S):
        if wpis:
            _usun(_klucz_parowania(kod))
        raise BladParowania(
            "Ten kod wygasł albo nie istnieje. Pomocnik pokaże nowy - "
            "wystarczy go zostawić włączonego.")
    return wpis


def opis(kod: str) -> dict:
    """Co zobaczy notariusz, zanim kliknie Polacz."""
    return {"kod": pokaz_kod(normalizuj_kod(kod)), "nazwa": _parowanie(kod)["nazwa"]}


def potwierdz(kod: str, kancelaria: str, ip: str) -> dict:
    """Zalogowany notariusz przypisuje komputer do swojej kancelarii."""
    wpis = _parowanie(kod)
    if wpis.get("kancelaria"):
        raise BladParowania("Ten komputer jest już połączony.")
    if wpis.get("ip") and ip and wpis["ip"] != ip:
        log.warning("parowanie: odrzucone, inna siec niz pomocnika")
        raise BladParowania(
            "Kod pochodzi z innej sieci niż ta przeglądarka. Połącz pomocnika "
            "z przeglądarki na tym samym komputerze, na którym go uruchomiono. "
            "Jeśli ktoś przysłał Ci ten kod albo link - nie łącz.")
    wpis["kancelaria"] = kancelaria
    _pisz(_klucz_parowania(normalizuj_kod(kod)), wpis)
    log.info("parowanie: potwierdzone w kancelarii %s", kancelaria)
    return {"nazwa": wpis["nazwa"]}


def odbierz(kod: str, sekret: str) -> dict | None:
    """Pomocnik dopytuje o swoj kod. None, dopoki notariusz nie potwierdzi.

    Token powstaje dopiero tutaj, wiec ani przez chwile nie lezy w S3 wprost.
    """
    wpis = _parowanie(kod)
    if not secrets.compare_digest(wpis.get("sekret", ""), _sha(sekret or "")):
        raise BladParowania("Ten kod należy do innego pomocnika.")
    kancelaria = wpis.get("kancelaria")
    if not kancelaria:
        return None

    identyfikator = secrets.token_hex(4)
    token = PREFIKS_TOKENU + secrets.token_urlsafe(32)
    skrot = _sha(token)
    teraz = _teraz().isoformat(timespec="seconds")
    _pisz(_klucz_tokenu(skrot), {
        "id": identyfikator, "kancelaria": kancelaria, "nazwa": wpis["nazwa"],
        "utworzono": teraz,
    })
    _pisz(_klucz_pomocnika(kancelaria, identyfikator), {
        "id": identyfikator, "nazwa": wpis["nazwa"], "utworzono": teraz,
        "skrot": skrot, "widziany": None, "wersja": "",
    })
    _usun(_klucz_parowania(normalizuj_kod(kod)))
    log.info("parowanie: kancelaria %s, nowy komputer %s", kancelaria, identyfikator)
    return {"token": token, "id": identyfikator}


# --- token pomocnika --------------------------------------------------------

# Pomocnik pyta co kilka sekund. Bez pamieci kazde pytanie to odczyt z S3;
# z nia - jeden na 30 s. Odlaczenie na tej samej kopii aplikacji dziala od
# razu, na drugiej najpozniej po tym czasie.
_PAMIEC_S = 30.0
_pamiec: dict[str, tuple[float, dict]] = {}


def czy_token_pomocnika(token: str) -> bool:
    return (token or "").startswith(PREFIKS_TOKENU)


def z_tokenu(token: str) -> dict | None:
    """{"id", "kancelaria", "nazwa"} albo None dla nieznanego tokenu."""
    if not dostepne() or not czy_token_pomocnika(token):
        return None
    skrot = _sha(token)
    zapamietany = _pamiec.get(skrot)
    if zapamietany and time.monotonic() - zapamietany[0] < _PAMIEC_S:
        return zapamietany[1]
    wpis = _czytaj(_klucz_tokenu(skrot))
    if wpis:
        _pamiec[skrot] = (time.monotonic(), wpis)
    else:
        _pamiec.pop(skrot, None)
    return wpis


# --- lista komputerow i obecnosc --------------------------------------------

# Obecnosc zapisujemy najwyzej raz na pol minuty na komputer - pomocnik pyta
# co trzy sekundy, a zapis do S3 przy kazdym pytaniu kosztuje i nic nie daje.
_ZAPIS_OBECNOSCI_S = 30.0
_ostatni_zapis: dict[str, float] = {}


def odnotuj(kancelaria: str, identyfikator: str, wersja: str = "") -> None:
    if time.monotonic() - _ostatni_zapis.get(identyfikator, -1e9) < _ZAPIS_OBECNOSCI_S:
        return
    klucz = _klucz_pomocnika(kancelaria, identyfikator)
    wpis = _czytaj(klucz)
    if not wpis:
        return  # odlaczony w miedzyczasie - nie wskrzeszamy go
    wpis["widziany"] = _teraz().isoformat(timespec="seconds")
    if wersja:
        wpis["wersja"] = wersja
    _pisz(klucz, wpis)
    _ostatni_zapis[identyfikator] = time.monotonic()


def _polaczony(wpis: dict) -> bool:
    widziany = _czas(wpis.get("widziany"))
    return bool(widziany and _teraz() - widziany < timedelta(minutes=ODDECH_MINUT))


def lista(kancelaria: str) -> list[dict]:
    prefiks = f"{magazyn.PREFIKS}/{kancelaria}/pomocnicy/"
    wynik = []
    strony = magazyn._klient_s3().get_paginator("list_objects_v2").paginate(
        Bucket=magazyn.BUCKET, Prefix=prefiks)
    for strona in strony:
        for obiekt in strona.get("Contents", []):
            wpis = _czytaj(obiekt["Key"])
            if wpis:
                wynik.append({
                    "id": wpis["id"], "nazwa": wpis["nazwa"],
                    "utworzono": wpis.get("utworzono"), "widziany": wpis.get("widziany"),
                    "wersja": wpis.get("wersja", ""), "polaczony": _polaczony(wpis),
                })
    wynik.sort(key=lambda w: w.get("utworzono") or "")
    return wynik


def aktywny(kancelaria: str) -> bool:
    return any(w["polaczony"] for w in lista(kancelaria))


def odlacz(kancelaria: str, identyfikator: str) -> bool:
    """Token komputera przestaje dzialac. False, gdy takiego komputera nie ma."""
    klucz = _klucz_pomocnika(kancelaria, identyfikator)
    wpis = _czytaj(klucz)
    if not wpis:
        return False
    _usun(klucz, _klucz_tokenu(wpis["skrot"]))
    _pamiec.pop(wpis["skrot"], None)
    _ostatni_zapis.pop(identyfikator, None)
    log.info("kancelaria %s: odlaczono komputer %s", kancelaria, identyfikator)
    return True


# --- ograniczenie prob ------------------------------------------------------
# Prosba o kod jest otwarta (pomocnik nie ma jeszcze tokenu), wiec bez limitu
# kazdy moglby zasypac bucket parowaniami. Licznik w pamieci jednej kopii
# aplikacji wystarczy: chodzi o zalew, nie o pojedyncze proby.

_LIMIT = 20
_OKNO_S = 600.0
_proby: dict[str, list[float]] = {}


def wolno(ip: str) -> bool:
    teraz = time.monotonic()
    ostatnie = [t for t in _proby.get(ip, []) if teraz - t < _OKNO_S]
    if len(ostatnie) >= _LIMIT:
        _proby[ip] = ostatnie
        return False
    ostatnie.append(teraz)
    _proby[ip] = ostatnie
    return True
