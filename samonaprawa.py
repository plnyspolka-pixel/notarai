"""Samonaprawa - wykrywanie bledow aplikacji i zglaszanie ich do naprawy.

Petla (opis calosci: docs/samonaprawa.md):
  1. aplikacja wykrywa blad (kazdy log.error w bloku except i nieobsluzony
     wyjatek), liczy jego odcisk i zapisuje znacznik w CloudWatch,
  2. nowy odcisk wysyla zdarzenie na domyslna szyne EventBridge (zrodlo
     "notarai.samonaprawa"), rola zadania ma tylko events:PutEvents,
  3. potok w AWS (stos notarai-samonaprawa, CodeBuild, scripts/samonaprawa/potok.py):
     agent szuka przyczyny, pisze poprawke i test regresji, bramki
     (scripts/samonaprawa/bramki.py) i drugi agent sprawdzaja, potem wdrozenie
     i obserwacja - a przy nawrocie bledu automatyczne cofniecie.
     Zadnej zaleznosci od GitHuba w czasie dzialania.

RODO: do znacznika i do zdarzenia idzie tylko to, co daje dziennik.opis_bledu()
(typ wyjatku, kod i komunikat AWS, miejsca w kodzie) po dziennik.maskuj().
Zadnej tresci wyjatku spoza AWS, tresci sprawy ani identyfikatorow kancelarii.

Modul nigdy nie rzuca wyjatku i nie blokuje obslugi zadania: wysylka
zdarzenia idzie w osobnym watku z krotkim limitem czasu.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import sys
import threading
import time
import traceback
from pathlib import Path

import config
import dziennik

log = logging.getLogger("pieczapp.samonaprawa")

# Po tym slowie potok samonaprawy i filtr metryki CloudWatch znajduja zgloszenia.
ZNACZNIK = "samonaprawa"
# Zdarzenie dla EventBridge (regula w stosie notarai-samonaprawa lapie dokladnie to).
ZRODLO_ZDARZEN = "notarai.samonaprawa"
TYP_ZDARZENIA = "zgloszenie"
# Ten sam odcisk zglaszamy najwyzej raz na tyle sekund (na kontener).
# Potok i tak laczy zgloszenia w jeden rekord na odcisk (DynamoDB).
PRZERWA_ZGLOSZEN = int(os.getenv("PIECZAPP_SAMONAPRAWA_PRZERWA", str(6 * 3600)))
# Bledy, ktorych nie naprawia sie kodem: chwilowe zaklocenia AWS, limity.
# Zliczamy je i alarmujemy, ale nie budzimy agenta naprawczego.
_PRZEJSCIOWE_KODY = {
    "throttlingexception", "toomanyrequestsexception", "servicequotaexceededexception",
    "serviceunavailableexception", "internalserverexception", "modelnotreadyexception",
    "modeltimeoutexception", "modelstreamerrorexception", "requesttimeout",
    "slowdown", "provisionedthroughputexceededexception",
}
_PRZEJSCIOWE_TYPY = {
    "Przeciazenie", "ReadTimeoutError", "ConnectTimeoutError", "EndpointConnectionError",
    "ConnectionClosedError", "ConnectError", "ReadTimeout", "ConnectTimeout",
    "TimeoutError", "ConnectionResetError", "BrokenPipeError", "ClientDisconnect",
    "CancelledError",
}
# Bledy uzytkownika (zly plik, brak uprawnien) - to nie awaria aplikacji.
_POMIJANE_TYPY = {"HTTPException", "RequestValidationError", "KeyboardInterrupt", "SystemExit"}

_blokada = threading.Lock()
_ostatnie: dict[str, float] = {}       # odcisk -> czas ostatniej wysylki zdarzenia
_licznik: dict[str, int] = {}          # odcisk -> wystapienia w tym kontenerze
_ZNAK = "_samonaprawa_zgloszony"


def wersja() -> str:
    """Tag obrazu (krotki SHA commita) - workflow po nim widzi, czy blad wrocil po poprawce."""
    return os.getenv("PIECZAPP_WERSJA", "lokalna")


def _nasze_ramki(blad: BaseException) -> list[traceback.FrameSummary]:
    ramki = traceback.extract_tb(blad.__traceback__)
    korzen = config.KORZEN.resolve()
    nasze = []
    for r in ramki:
        sciezka = Path(r.filename)
        try:
            if sciezka.resolve().is_relative_to(korzen) and ".venv" not in sciezka.parts \
                    and "site-packages" not in sciezka.parts:
                nasze.append(r)
        except (OSError, ValueError):
            continue
    return nasze


def _kod_aws(blad: BaseException) -> str:
    odpowiedz = getattr(blad, "response", None)
    if isinstance(odpowiedz, dict):
        return str(odpowiedz.get("Error", {}).get("Code", "") or "")
    return ""


def odcisk(blad: BaseException) -> str:
    """Staly identyfikator rodzaju bledu: typ, kod AWS i nasze funkcje na stosie.

    Bez numerow linii, zeby ten sam blad mial ten sam odcisk po niezwiazanej
    zmianie w pliku. Bez tresci komunikatu (moglaby zawierac dane).
    """
    ramki = _nasze_ramki(blad)[-dziennik.RAMEK:]
    czesci = [type(blad).__name__, _kod_aws(blad).lower()]
    czesci += [f"{Path(r.filename).name}:{r.name}" for r in ramki]
    przyczyna = blad.__cause__ or blad.__context__
    if przyczyna is not None and przyczyna is not blad:
        czesci.append("<" + type(przyczyna).__name__)
    return hashlib.sha256("|".join(czesci).encode()).hexdigest()[:12]


def rodzaj(blad: BaseException) -> str:
    """"kod" (do naprawy), "przejsciowy" (AWS/siec) albo "pomijany" (blad uzytkownika)."""
    nazwa = type(blad).__name__
    if nazwa in _POMIJANE_TYPY:
        return "pomijany"
    if nazwa in _PRZEJSCIOWE_TYPY or _kod_aws(blad).lower() in _PRZEJSCIOWE_KODY:
        return "przejsciowy"
    przyczyna = blad.__cause__
    if przyczyna is not None and (type(przyczyna).__name__ in _PRZEJSCIOWE_TYPY
                                  or _kod_aws(przyczyna).lower() in _PRZEJSCIOWE_KODY):
        return "przejsciowy"
    return "kod"


def opis(blad: BaseException) -> dict:
    """Zgloszenie bez danych osobowych - to samo idzie do logu i do zdarzenia EventBridge."""
    ramki = _nasze_ramki(blad)[-dziennik.RAMEK:]
    return {
        "odcisk": odcisk(blad),
        "rodzaj": rodzaj(blad),
        "typ": type(blad).__name__,
        "kod_aws": _kod_aws(blad),
        "opis": dziennik.maskuj(dziennik.opis_bledu(blad))[:1500],
        "miejsca": [f"{Path(r.filename).name}:{r.lineno} {r.name}" for r in reversed(ramki)],
        "wersja": wersja(),
        "czas": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def zdarzenia_wlaczone() -> bool:
    """Zdarzenia do EventBridge wlacza szablon ECS (PIECZAPP_SAMONAPRAWA_ZDARZENIA=true).
    Lokalnie i w testach zwykle wylaczone: bez poswiadczen AWS nie ma dokad wysylac."""
    return os.getenv("PIECZAPP_SAMONAPRAWA_ZDARZENIA", "").lower() in ("1", "true", "tak")


def wlaczona() -> bool:
    return os.getenv("PIECZAPP_SAMONAPRAWA", "true").lower() not in ("false", "0", "nie", "wylaczona")


def koduj_ladunek(zgloszenie: dict) -> str:
    """Zgloszenie jako base64 (JSON): bezpieczne do wstawienia w szablon wejscia
    EventBridge (cudzyslowy i znaki sterujace w opisie nie psuja JSON-a)."""
    return base64.b64encode(json.dumps(zgloszenie, ensure_ascii=False, sort_keys=True).encode("utf-8")).decode("ascii")


def wpis_zdarzenia(zgloszenie: dict) -> dict:
    """Wpis dla events.put_events: detail = zgloszenie (to samo, co opis()) + ladunek_b64."""
    szczegoly = dict(zgloszenie)
    szczegoly["ladunek_b64"] = koduj_ladunek(zgloszenie)
    return {"Source": ZRODLO_ZDARZEN, "DetailType": TYP_ZDARZENIA, "EventBusName": "default",
            "Detail": json.dumps(szczegoly, ensure_ascii=False)}


def _klient_zdarzen():
    import boto3
    from botocore.config import Config
    return boto3.client("events", region_name=config.REGION,
                        config=Config(connect_timeout=3, read_timeout=5, retries={"max_attempts": 2}))


def _wyslij(zgloszenie: dict) -> None:
    """put_events na domyslna szyne. Bledy wysylki tylko do logu."""
    try:
        odp = _klient_zdarzen().put_events(Entries=[wpis_zdarzenia(zgloszenie)])
        if odp.get("FailedEntryCount"):
            log.warning("samonaprawa: EventBridge odrzucil zgloszenie %s", zgloszenie["odcisk"])
    except Exception as e:  # noqa: BLE001 - wysylka nie moze zepsuc obslugi zadania
        log.warning("samonaprawa: wysylka zgloszenia nieudana (%s)", type(e).__name__)


def zglos(blad: BaseException | None, miejsce: str = "") -> dict | None:
    """Rejestruje blad. Zwraca zgloszenie albo None (pominiety / juz zgloszony).

    Ten sam obiekt wyjatku zglaszamy raz, nawet gdy przechodzi przez kilka
    log.error (endpoint, watek w tle, globalna obsluga bledow).
    """
    try:
        if blad is None or not wlaczona() or getattr(blad, _ZNAK, False):
            return None
        try:
            setattr(blad, _ZNAK, True)
        except (AttributeError, TypeError):
            pass
        zgloszenie = opis(blad)
        if zgloszenie["rodzaj"] == "pomijany":
            return None
        if miejsce:
            zgloszenie["endpoint"] = dziennik.maskuj(miejsce)[:120]
        with _blokada:
            ile = _licznik.get(zgloszenie["odcisk"], 0) + 1
            _licznik[zgloszenie["odcisk"]] = ile
            teraz = time.monotonic()
            poprzednio = _ostatnie.get(zgloszenie["odcisk"])
            wysylac = (zgloszenie["rodzaj"] == "kod" and zdarzenia_wlaczone()
                       and (poprzednio is None or teraz - poprzednio >= PRZERWA_ZGLOSZEN))
            if wysylac:
                _ostatnie[zgloszenie["odcisk"]] = teraz
        zgloszenie["wystapien_w_kontenerze"] = ile
        # Znacznik dla potoku (obserwacja po wdrozeniu) i filtra metryki CloudWatch.
        # Uwaga: ten wpis przechodzi jeszcze przez maskowanie dziennika.
        log.error("%s %s", ZNACZNIK, json.dumps(
            {k: zgloszenie[k] for k in ("odcisk", "rodzaj", "typ", "kod_aws", "wersja", "miejsca", "opis")}
            | {"endpoint": zgloszenie.get("endpoint", "")}, ensure_ascii=False))
        if wysylac:
            threading.Thread(target=_wyslij, args=(dict(zgloszenie),), daemon=True,
                             name="samonaprawa-wysylka").start()
        return zgloszenie
    except Exception:  # noqa: BLE001 - samonaprawa nie moze sama byc awaria
        return None


def anonimizuj(tekst: str) -> str:
    """Opis prosby bez danych klientow: PESEL, e-mail, pliki, osoby, numery."""
    import klauzule
    return klauzule.pseudonimizuj(dziennik.maskuj(tekst or ""))[:2000]


def zglos_prosbe(opis: str) -> dict:
    """Prosba kancelarii o zmiane w programie (asystent kancelarii) -> samonaprawa.

    Agent naprawczy dostaje ja jak zgloszenie reczne; zmiane zachowania robi
    jako ustawienie kancelarii (domyslnie po staremu), w strefach zakazanych
    zawsze jako pull request do wlasciciela. Zwraca {"odcisk", "wyslano"}.
    """
    tekst = anonimizuj(opis)
    odcisk_prosby = hashlib.sha256(kategorie_plaskie(tekst).encode()).hexdigest()[:12]
    zgloszenie = {"odcisk": odcisk_prosby, "rodzaj": "reczne", "typ": "prosba kancelarii",
                  "kod_aws": "", "opis": "", "miejsca": [], "uwagi": tekst,
                  "wersja": wersja(), "czas": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    wyslano = zdarzenia_wlaczone() and wlaczona()
    # Znacznik w CloudWatch: przeglad co 30 min podejmuje prosbe takze bez zdarzenia.
    log.error("%s %s", ZNACZNIK, json.dumps(
        {k: zgloszenie[k] for k in ("odcisk", "rodzaj", "typ", "wersja", "miejsca", "uwagi")}, ensure_ascii=False))
    if wyslano:
        threading.Thread(target=_wyslij, args=(zgloszenie,), daemon=True, name="samonaprawa-prosba").start()
    return {"odcisk": odcisk_prosby, "wyslano": wyslano, "tekst": tekst}


def kategorie_plaskie(tekst: str) -> str:
    import kategorie
    return kategorie.bez_ogonkow(tekst).lower().strip()


class _Wychwytywacz(logging.Handler):
    """Kazdy log.error/exception z aktywnym wyjatkiem trafia do zglos().

    Aplikacja loguje bledy w blokach except (log.error(..., opis_bledu(blad))),
    wiec wyjatek jest w sys.exc_info() - nie trzeba zmieniac kazdego miejsca.
    """

    def emit(self, rekord: logging.LogRecord) -> None:
        if rekord.name == log.name or rekord.levelno < logging.ERROR:
            return
        blad = rekord.exc_info[1] if rekord.exc_info else None
        if blad is None:
            blad = sys.exc_info()[1]
        if blad is not None:
            zglos(blad)


_wychwytywacz: _Wychwytywacz | None = None


def zainstaluj(logger: logging.Logger | None = None) -> None:
    """Podpina wychwytywanie bledow pod logger aplikacji. Ponowne wywolanie nic nie zmienia."""
    global _wychwytywacz
    cel = logger or logging.getLogger("pieczapp")
    if _wychwytywacz is not None and _wychwytywacz in cel.handlers:
        return
    _wychwytywacz = _Wychwytywacz(level=logging.ERROR)
    cel.addHandler(_wychwytywacz)


def stan() -> dict:
    """Licznik bledow w tym kontenerze (panel administratora)."""
    with _blokada:
        return {"wlaczona": wlaczona(), "zglaszanie_do_aws": zdarzenia_wlaczone(),
                "wersja": wersja(), "odciski": dict(_licznik)}


def _reset_do_testow() -> None:
    with _blokada:
        _ostatnie.clear()
        _licznik.clear()
