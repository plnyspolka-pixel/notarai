"""Klient pomocnika: odbiera zlecenia z notarai i wykonuje je na tym komputerze.

Pomocnik nie wystawia zadnego portu i nikt sie do niego nie laczy. To on pyta
notarai o robote - polaczenie idzie zawsze na zewnatrz, wiec zapora domowa i
kancelaryjna nie maja z nim nic wspolnego, a strona z internetu nie ma jak go
zawolac (od Chrome 142 siegniecie strony do localhost wymaga zreszta osobnej
zgody, a w 145 dzieli sie na dwa uprawnienia).

Samo pytanie o robote jest dla serwera znakiem, ze pomocnik zyje - dzieki temu
przycisk sprawdzenia w notarai zapala sie i gasnie sam.

Do logow trafiaja rodzaje zlecen i liczby krokow. Nigdy numery ani wartosci pol.
"""
from __future__ import annotations

import json
import logging
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

log = logging.getLogger("notarai.pomocnik.klient")

WERSJA = "0.1"
PRZERWA_S = 3.0
PRZERWA_PO_BLEDZIE_S = 15.0


class BladPolaczenia(RuntimeError):
    """Nie udalo sie porozumiec z notarai. Tresc widzi notariusz."""


@dataclass
class Notarai:
    """Rozmowa z serwerem notarai. Token kancelarii jak w przegladarce."""

    adres: str
    token: str
    czas_s: float = 60.0

    def _zadanie(self, sciezka: str, dane: dict | None = None) -> dict | list:
        adres = self.adres.rstrip("/") + sciezka
        tresc = json.dumps(dane).encode("utf-8") if dane is not None else None
        zadanie = urllib.request.Request(
            adres,
            data=tresc,
            method="POST" if dane is not None else "GET",
            headers={
                "Authorization": "Bearer " + self.token,
                "Content-Type": "application/json",
                "User-Agent": f"notarai-pomocnik/{WERSJA}",
            },
        )
        # Kontekst domyslny bierze certyfikaty z magazynu Windows, wiec dziala
        # takze tam, gdzie antywirus podglada polaczenia, podstawiajac wlasny
        # certyfikat (u notariuszy to raczej regula niz wyjatek).
        kontekst = ssl.create_default_context()
        try:
            with urllib.request.urlopen(zadanie, timeout=self.czas_s, context=kontekst) as odp:
                return json.loads(odp.read().decode("utf-8") or "null")
        except urllib.error.HTTPError as blad:
            kod = blad.code
            blad.close()  # HTTPError trzyma otwarty strumien odpowiedzi
            if kod == 401:
                raise BladPolaczenia(
                    "notarai nie przyjelo tokenu kancelarii. Wklej go ponownie."
                ) from None
            raise BladPolaczenia(f"notarai odpowiedzialo bledem {kod}.") from None
        except (urllib.error.URLError, TimeoutError, OSError) as blad:
            raise BladPolaczenia("Nie moge polaczyc sie z notarai.") from blad

    def zlecenia(self) -> list[dict]:
        wynik = self._zadanie(f"/api/pomocnik/zlecenia?wersja={WERSJA}")
        return wynik if isinstance(wynik, list) else []

    def odeslij(self, identyfikator: str, raport: dict) -> dict:
        wynik = self._zadanie(f"/api/pomocnik/zlecenia/{identyfikator}/wynik", raport)
        return wynik if isinstance(wynik, dict) else {}


def wykonaj(zlecenie: dict, wykonawcy: dict) -> dict:
    """Kieruje zlecenie do wlasciwego wykonawcy.

    Nieznanego rodzaju nie udajemy, ze wykonalismy. Lepiej, zeby notariusz
    zobaczyl "nie umiem tego zrobic", niz zeby zlecenie po cichu zniknelo.
    """
    rodzaj = zlecenie.get("rodzaj", "")
    wykonawca = wykonawcy.get(rodzaj)
    if not wykonawca:
        log.warning("zlecenie %s: nieznany rodzaj %r", zlecenie.get("id"), rodzaj)
        return {"bledy": [f"Ten pomocnik nie obsluguje zlecen rodzaju '{rodzaj}'. "
                          "Zaktualizuj pomocnika."]}
    return wykonawca(zlecenie)


def jeden_obieg(notarai: Notarai, wykonawcy: dict) -> int:
    """Jedno pytanie o robote i wykonanie tego, co przyszlo.

    Blad jednego zlecenia nie przerywa pozostalych: notariusz woli dostac trzy
    wyniki z czterech niz zero.
    """
    zlecenia = notarai.zlecenia()
    zrobione = 0
    for zlecenie in zlecenia:
        identyfikator = zlecenie.get("id", "")
        try:
            raport = wykonaj(zlecenie, wykonawcy)
        except Exception as blad:  # noqa: BLE001 - bez tresci zlecenia w komunikacie
            log.error("zlecenie %s: %s", identyfikator, type(blad).__name__)
            raport = {"bledy": [f"Pomocnik nie dokonczyl: {type(blad).__name__}"]}
        try:
            notarai.odeslij(identyfikator, raport)
            zrobione += 1
        except BladPolaczenia as blad:
            log.error("zlecenie %s: nie odeslano wyniku (%s)", identyfikator, blad)
    if zlecenia:
        log.info("obieg: zlecen=%d odeslanych=%d", len(zlecenia), zrobione)
    return zrobione


def pracuj(notarai: Notarai, wykonawcy: dict, przerwa_s: float = PRZERWA_S,
           dziala=lambda: True, spij=time.sleep) -> None:
    """Petla pomocnika. Konczy sie, gdy `dziala()` przestanie byc prawda.

    Zerwane lacze nie jest bledem, tylko stanem przejsciowym - notariusz
    zamyka laptopa, traci wi-fi, wraca. Czekamy dluzej i pytamy dalej.
    """
    while dziala():
        try:
            jeden_obieg(notarai, wykonawcy)
            spij(przerwa_s)
        except BladPolaczenia as blad:
            log.warning("pomocnik: %s Ponawiam za %.0f s.", blad, PRZERWA_PO_BLEDZIE_S)
            spij(PRZERWA_PO_BLEDZIE_S)
