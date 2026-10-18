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


class BladTokenu(BladPolaczenia):
    """notarai nie przyjmuje juz tego tokenu - komputer odlaczono.

    To nie jest stan przejsciowy jak zerwane lacze: ponawianie nic nie da.
    Pomocnik ma wtedy sam wrocic do laczenia z kancelaria.
    """


class KodNieaktualny(BladPolaczenia):
    """Kod polaczenia wygasl albo nalezy do kogos innego. Trzeba wziac nowy."""


@dataclass
class Notarai:
    """Rozmowa z serwerem notarai. Bez tokenu tylko laczenie z kancelaria."""

    adres: str
    token: str = ""
    czas_s: float = 60.0

    def _zadanie(self, sciezka: str, dane: dict | None = None) -> dict | list:
        adres = self.adres.rstrip("/") + sciezka
        tresc = json.dumps(dane).encode("utf-8") if dane is not None else None
        naglowki = {
            "Content-Type": "application/json",
            "User-Agent": f"notarai-pomocnik/{WERSJA}",
        }
        if self.token:
            naglowki["Authorization"] = "Bearer " + self.token
        zadanie = urllib.request.Request(
            adres,
            data=tresc,
            method="POST" if dane is not None else "GET",
            headers=naglowki,
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
                raise BladTokenu(
                    "Ten komputer nie jest już połączony z kancelarią."
                ) from None
            if kod == 410:
                raise KodNieaktualny("Kod połączenia wygasł.") from None
            raise BladPolaczenia(f"notarai odpowiedzialo bledem {kod}.") from None
        except (urllib.error.URLError, TimeoutError, OSError) as blad:
            raise BladPolaczenia("Nie moge polaczyc sie z notarai.") from blad

    # --- laczenie z kancelaria ---

    def popros_o_kod(self, nazwa_komputera: str) -> dict:
        """{"kod", "sekret", "wazny_s"}. Kod notariusz potwierdza w notarai."""
        wynik = self._zadanie("/api/pomocnik/parowanie", {"nazwa": nazwa_komputera})
        return wynik if isinstance(wynik, dict) else {}

    def odbierz_token(self, kod: str, sekret: str) -> str | None:
        """Token, gdy notariusz potwierdzil. None, dopoki czeka."""
        wynik = self._zadanie(f"/api/pomocnik/parowanie/{kod}", {"sekret": sekret})
        return wynik.get("token") if isinstance(wynik, dict) else None

    def odlacz(self) -> None:
        self._zadanie("/api/pomocnik/odlacz", {})

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
        except BladTokenu:
            raise  # odlaczony - ponawianie nic nie da, wracamy do laczenia
        except BladPolaczenia as blad:
            log.warning("pomocnik: %s Ponawiam za %.0f s.", blad, PRZERWA_PO_BLEDZIE_S)
            spij(PRZERWA_PO_BLEDZIE_S)


PRZERWA_LACZENIA_S = 2.0


def polacz(notarai: Notarai, nazwa_komputera: str, pokaz_kod,
           dziala=lambda: True, spij=time.sleep) -> str | None:
    """Laczy ten komputer z kancelaria i zwraca jego token.

    Prosi o kod, przekazuje go `pokaz_kod` (okno pokazuje go i otwiera
    notarai w przegladarce), po czym czeka, az notariusz kliknie Polacz.
    Wygasly kod wymienia sam na nowy, zerwane lacze przeczekuje - notariusz
    nie musi niczego klikac ponownie. None, gdy `dziala()` przestanie byc
    prawda.
    """
    kod = sekret = ""
    while dziala():
        try:
            if not kod:
                odp = notarai.popros_o_kod(nazwa_komputera)
                kod, sekret = odp["kod"], odp["sekret"]
                pokaz_kod(kod)
            token = notarai.odbierz_token(kod, sekret)
            if token:
                log.info("pomocnik: komputer polaczony z kancelaria")
                return token
            spij(PRZERWA_LACZENIA_S)
        except KodNieaktualny:
            kod = sekret = ""
        except BladPolaczenia as blad:
            log.warning("laczenie: %s Ponawiam za %.0f s.", blad, PRZERWA_PO_BLEDZIE_S)
            spij(PRZERWA_PO_BLEDZIE_S)
    return None
