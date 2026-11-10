"""Tokenomia notarai: kredyty za akcje, licznik kosztow, portfel kancelarii.

Zasada: kancelaria placi kredytami za akcje, ktore kosztuja nas pieniadze
(wywolania modelu w Bedrock, platne zrodla danych). Cena akcji w kredytach
wynika z jej kosztu operacyjnego, a nie odwrotnie:

    kredyty = zaokraglij_w_gore(max(
        koszt_P90     * (1 + NARZUT) / CENA_KREDYTU,            # (a)
        koszt_sredni  * (1 + NARZUT) / NAJNIZSZA_CENA_KREDYTU,  # (b)
    ))

- (a) przy cenie katalogowej narzut 100% trzyma sie nawet dla 90% najdrozszych
  wykonan (mysleniu modelu zdarza sie zuzyc wielokrotnosc typowej liczby
  tokenow),
- (b) kancelaria z najwiekszym rabatem (najtanszy plan albo pakiet) i tak
  placi srednio co najmniej 2 x koszt,
- koszt zawiera narzut na nieudane proby, za ktore kancelaria nie placi,
- NARZUT - co najmniej 100% (cena >= 2 x koszt).

Wersja 1 cennika liczyla (a) od najnizszej ceny kredytu. Symulacja
(scripts/symulacja_tokenomii.py) pokazala, ze to ok. 5 x koszt typowej sprawy -
bezpiecznie, ale za drogo wobec wartosci dla kancelarii. Patrz docs/tokenomia.md.

Kazde wywolanie modelu jest liczone (bedrock._rozmowa -> dolicz), wiec obok
ceny w kredytach zapisujemy rzeczywisty koszt i marze. Z tych zapisow
`kalibracja()` wylicza nowy cennik, gdy szacunki rozjada sie z praktyka.

Portfel kancelarii lezy w obszarze administracyjnym (nie przy sprawach),
bo dotyczy rozliczen, a nie danych klientow - dziala takze dla kancelarii,
ktore trzymaja pliki u siebie. Zapis warunkowy (If-Match), jak pliki
kancelarii w magazyn.py. Zero danych osobowych: w historii tylko akcja,
liczba jednostek, kredyty, koszt i identyfikator sprawy.

Wlaczenie: PIECZAPP_TOKENOMIA=true. Bez tego licznik nadal liczy koszty
(logi i panel admina), ale niczego nie pobiera ani nie blokuje.
"""
from __future__ import annotations

import contextvars
import json
import logging
import math
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException

log = logging.getLogger("pieczapp.tokenomia")

WLACZONA = os.getenv("PIECZAPP_TOKENOMIA", "false").lower() == "true"

# --- koszty jednostkowe -------------------------------------------------------

# USD za 1 mln tokenow (wejscie, wyjscie) - cennik Anthropic dla modeli Claude.
# Kolejnosc ma znaczenie: pierwszy pasujacy fragment identyfikatora wygrywa.
CENY_MODELI_USD: list[tuple[str, float, float]] = [
    ("claude-opus-5-5", 4.0, 20.0),
    ("claude-opus-5", 5.0, 25.0),
    ("claude-opus-4", 5.0, 25.0),        # 4.6, 4.7, 4.8
    ("claude-fable-5", 10.0, 50.0),
    ("claude-sonnet-5", 2.0, 10.0),      # 5 i 5.5
    ("claude-sonnet-4", 3.0, 15.0),      # 4.5, 4.6
    ("claude-haiku-5", 0.10, 0.50),
    ("claude-haiku-4", 1.0, 5.0),
]
# Odczyt z pamieci podrecznej promptu i jej zapis wzgledem zwyklego wejscia.
MNOZNIK_CACHE_ODCZYT = 0.10
MNOZNIK_CACHE_ZAPIS = 1.25
# Profil "eu." w Bedrock to wnioskowanie geograficzne. Przyjmujemy doplate
# 10% wzgledem cennika globalnego - sprawdz aktualna stawke na stronie cennika
# Bedrock i popraw zmienna, jesli sie zmieni.
PREMIA_REGIONALNA = float(os.getenv("PIECZAPP_PREMIA_REGIONALNA", "1.10"))
KURS_USD_PLN = float(os.getenv("PIECZAPP_KURS_USD", "3.70"))
# Narzut na proby nieudane i ponowione (zestawienie probuje do 3 razy, paczka
# stron tez), za ktore kancelaria nie placi - ten koszt ponosimy my.
NARZUT_NA_BLEDY = float(os.getenv("PIECZAPP_NARZUT_NA_BLEDY", "0.15"))

# Minimalny narzut na kazdej akcji (1.0 = 100%, cena = 2 x koszt).
NARZUT = float(os.getenv("PIECZAPP_NARZUT", "1.0"))
# Cena katalogowa kredytu (zl netto) i najnizsza cena, po jakiej kredyt
# sprzedajemy w jakimkolwiek planie albo pakiecie (patrz PLANY, PAKIETY).
CENA_KREDYTU_ZL = 1.00
NAJNIZSZA_CENA_KREDYTU_ZL = 0.80
# Kredyty liczymy z dokladnoscia do pol kredytu.
KROK_KREDYTU = 0.5


def ceny_modelu(model: str) -> tuple[float, float]:
    """(USD wejscie, USD wyjscie) za 1 mln tokenow. Nieznany model liczymy
    jak najdrozszy, zeby pomylka w cenniku nie dawala straty."""
    for fragment, wejscie, wyjscie in CENY_MODELI_USD:
        if fragment in (model or ""):
            return wejscie, wyjscie
    return max(c[1] for c in CENY_MODELI_USD), max(c[2] for c in CENY_MODELI_USD)


def koszt_tokenow_zl(model: str, wejscie: int, wyjscie: int,
                     cache_odczyt: int = 0, cache_zapis: int = 0) -> float:
    """Koszt jednego wywolania w zl (z premia regionalna)."""
    c_we, c_wy = ceny_modelu(model)
    usd = (wejscie * c_we + cache_odczyt * c_we * MNOZNIK_CACHE_ODCZYT
           + cache_zapis * c_we * MNOZNIK_CACHE_ZAPIS + wyjscie * c_wy) / 1_000_000
    return usd * PREMIA_REGIONALNA * KURS_USD_PLN


# --- akcje i ich profile kosztow -----------------------------------------------

MODEL_GLOWNY = os.getenv("PIECZAPP_MODEL", "eu.anthropic.claude-opus-4-6-v1")
MODEL_KALKULATORA = os.getenv("PIECZAPP_KALKULATOR_MODEL", "eu.anthropic.claude-sonnet-4-6")


@dataclass(frozen=True)
class Akcja:
    """Akcja platna kredytami. Profil to tokeny na JEDNA jednostke akcji
    (strone, ture, krok...): (wejscie P50, wyjscie P50, wejscie P90, wyjscie P90).

    Profile sa szacunkiem z budowy promptow (bedrock.py, prompty.py) i z
    rozmiaru obrazow (dokumenty.py: strona A4 = obraz calosci + 4 pasy,
    ok. 7 650 tokenow obrazu). Kalibracja z rzeczywistych zapisow je zastepuje.
    """
    kod: str
    nazwa: str
    jednostka: str
    profil: tuple[int, int, int, int] = (0, 0, 0, 0)
    koszt_zewnetrzny_zl: float = 0.0     # platne zrodlo danych (EKW): srednio na jednostke
    koszt_zewnetrzny_p90_zl: float | None = None   # ... i w 90% przypadkow najwyzej tyle
    model: str = ""
    darmowa: bool = False                # akcje zgodnosci (staranność) nie kosztuja kredytow
    stala_cena: float | None = None      # cena uslugowa niezalezna od kosztu (np. nadanie)

    def koszt_zl(self, percentyl: int = 90) -> float:
        we50, wy50, we90, wy90 = self.profil
        we, wy = (we90, wy90) if percentyl >= 90 else (we50, wy50)
        tokeny = koszt_tokenow_zl(self.model or MODEL_GLOWNY, we, wy)
        zewnetrzny = self.koszt_zewnetrzny_zl
        if percentyl >= 90 and self.koszt_zewnetrzny_p90_zl is not None:
            zewnetrzny = self.koszt_zewnetrzny_p90_zl
        return (tokeny * (1 + NARZUT_NA_BLEDY)) + zewnetrzny

    def koszt_sredni_zl(self) -> float:
        """Srednia przy rozkladzie log-normalnym wyznaczonym przez P50 i P90:
        sigma = ln(P90/P50) / 1.2816, srednia = P50 * exp(sigma^2 / 2)."""
        we50, wy50, we90, wy90 = self.profil

        def srednia(p50: int, p90: int) -> float:
            if p50 <= 0:
                return 0.0
            sigma = math.log(max(p90, p50) / p50) / 1.2816
            return p50 * math.exp(sigma * sigma / 2)
        tokeny = koszt_tokenow_zl(self.model or MODEL_GLOWNY, int(srednia(we50, we90)),
                                  int(srednia(wy50, wy90)))
        return tokeny * (1 + NARZUT_NA_BLEDY) + self.koszt_zewnetrzny_zl

    def kredyty(self) -> float:
        if self.darmowa:
            return 0.0
        z_kosztu = max(self.koszt_zl(90) * (1 + NARZUT) / CENA_KREDYTU_ZL,
                       self.koszt_sredni_zl() * (1 + NARZUT) / NAJNIZSZA_CENA_KREDYTU_ZL)
        if self.stala_cena is not None:
            z_kosztu = max(z_kosztu, self.stala_cena)
        return max(KROK_KREDYTU, math.ceil(z_kosztu / KROK_KREDYTU - 1e-9) * KROK_KREDYTU)


# Wysilek odczytu ("Dokladnosc odczytu" w interfejsie) zmienia glownie liczbe
# tokenow myslenia, czyli wyjscie - dlatego osobne ceny strony. Wejscie strony
# to obrazy (ok. 7 650 tokenow) + warstwa tekstowa i polecenie (ok. 850) + jej
# transkrypcja czytana jeszcze raz w zestawieniu danych (ok. 2 000).
AKCJE: dict[str, Akcja] = {a.kod: a for a in [
    Akcja("odczyt_strony_max", "Odczyt strony skanu (dokladnosc maksymalna)", "strona",
          (10_500, 2_500, 11_500, 6_000)),
    Akcja("odczyt_strony_high", "Odczyt strony skanu (dokladnosc wysoka)", "strona",
          (10_500, 1_800, 11_500, 4_000)),
    Akcja("odczyt_strony_medium", "Odczyt strony skanu (dokladnosc standardowa)", "strona",
          (10_500, 1_200, 11_500, 2_500)),
    # Zestawienie danych ze wszystkich stron + pytania wstepne asystenta.
    # Czesc zalezna od liczby stron (transkrypcje na wejsciu) siedzi w cenie strony.
    Akcja("zalozenie_sprawy", "Zestawienie danych i pytania wstepne", "sprawa",
          (14_000, 9_000, 20_000, 26_000)),
    # Tura rozmowy rosnie z dlugoscia rozmowy. Cena za ture do 30 tys. tokenow
    # kontekstu; dluzsza rozmowa liczy sie jako kilka tur (patrz jednostki_rozmowy).
    Akcja("rozmowa_tura", "Tura rozmowy o sprawie", "tura",
          (14_000, 2_500, 30_000, 7_000)),
    # Projekt do 40 tys. znakow wzoru, z podsumowaniem ustalen rozmowy.
    Akcja("projekt", "Projekt aktu (wzor do 40 tys. znakow)", "projekt",
          (34_000, 22_000, 44_000, 44_000)),
    Akcja("projekt_dodatek", "Projekt aktu - kazde dalsze 10 tys. znakow wzoru", "10 tys. znakow",
          (4_000, 4_500, 5_000, 9_000)),
    Akcja("formularz", "Dopasowanie pol formularza urzedowego do aktu", "formularz",
          (12_000, 3_000, 22_000, 9_000)),
    Akcja("asystent_krok", "Krok asystenta w przegladarce (pomocnik)", "krok",
          (3_500, 300, 5_000, 700)),
    # Tresc KW przez Finance You: najpierw Apify (0,005-0,010 USD za ksiege +
    # 0,025 USD za uruchomienie, finyou src/lib/apify-ekw.server.ts), awaryjnie
    # EasyMKW (2 kredyty EasyMKW za ksiege). Srednio ok. 0,35 zl przy ~10%
    # przypadkow na EasyMKW. Cena to wartosc dla kancelarii (cena minimalna),
    # nie koszt: notariusz dostaje piec dzialow w sprawie bez przepisywania.
    Akcja("ekw_ksiega", "Tresc ksiegi wieczystej z EKW", "ksiega",
          koszt_zewnetrzny_zl=float(os.getenv("PIECZAPP_KOSZT_EKW_ZL", "0.35")),
          koszt_zewnetrzny_p90_zl=float(os.getenv("PIECZAPP_KOSZT_EKW_ZAPASOWY_ZL", "2.20")),
          stala_cena=float(os.getenv("PIECZAPP_CENA_KW", "5"))),
    # Odsloniecie danych kontaktowych klienta z zapytania ze strony notarai.pl
    # (wizyty.py). Koszt dla nas ~0 (e-mail SES); cena uslugowa, ta sama dla
    # kazdego zapytania - niezalezna od czynnosci i jej wartosci (neutralnosc).
    Akcja("kontakt_klienta", "Odsloniecie kontaktu klienta z zapytania", "zapytanie",
          stala_cena=float(os.getenv("PIECZAPP_CENA_KONTAKTU", "5"))),
    Akcja("kalkulator_tura", "Tura kalkulatora taksy dla klienta", "tura",
          (4_000, 400, 8_000, 1_500), model=MODEL_KALKULATORA),
    Akcja("krz_sprawdzenie", "Sprawdzenie w KRZ", "sprawdzenie", darmowa=True),
    Akcja("przesylka", "Nadanie przesylki przez e-Nadawce", "przesylka", stala_cena=0.5),
]}

# Kontekst, ktory miesci sie w cenie jednej tury rozmowy (tokeny).
TURA_KONTEKST_TOKENOW = 30_000
# Zgrubnie: 1 token ~ 3 znaki tekstu polskiego.
ZNAKOW_NA_TOKEN = 3
PROJEKT_ZNAKOW_W_CENIE = 40_000


def jednostki_rozmowy(znakow_kontekstu: int) -> int:
    """Ile tur kosztuje tura przy takim kontekscie (kontekst sprawy + historia)."""
    tokeny = znakow_kontekstu / ZNAKOW_NA_TOKEN
    return max(1, math.ceil(tokeny / TURA_KONTEKST_TOKENOW))


def jednostki_projektu(znakow_wzoru: int) -> int:
    """Dodatkowe jednostki 'projekt_dodatek' ponad wzor mieszczacy sie w cenie."""
    return max(0, math.ceil((znakow_wzoru - PROJEKT_ZNAKOW_W_CENIE) / 10_000))


def akcja_odczytu(wysilek: str) -> str:
    return f"odczyt_strony_{wysilek}" if f"odczyt_strony_{wysilek}" in AKCJE else "odczyt_strony_max"


def cennik() -> list[dict]:
    return [{"kod": a.kod, "nazwa": a.nazwa, "jednostka": a.jednostka, "kredyty": a.kredyty(),
             "koszt_p50_zl": round(a.koszt_zl(50), 4), "koszt_sredni_zl": round(a.koszt_sredni_zl(), 4),
             "koszt_p90_zl": round(a.koszt_zl(90), 4)}
            for a in AKCJE.values()]


# --- plany i pakiety ------------------------------------------------------------

# Abonament: cena miesieczna netto i pula kredytow odnawiana co okres.
# Kredyty z puli nie przechodza na kolejny miesiac; dokupione - waza 12 miesiecy.
# Pule dobrane do zuzycia: typowa sprawa to ok. 65-80 kr. (symulacja), wiec
# Start ~4 sprawy, Kancelaria ~9, Pro ~25, Kancelaria+ ~60 spraw miesiecznie.
# Plan "kancelaria" odpowiada obecnej cenie abonamentu w Stripe (600 zl).
PLANY: dict[str, dict] = {
    "start": {"nazwa": "Start", "cena_zl": 290, "pula": 300, "uzytkownikow": 2, "gb": 20, "kontakty": 2},
    "kancelaria": {"nazwa": "Kancelaria", "cena_zl": 600, "pula": 700, "uzytkownikow": 6, "gb": 100, "kontakty": 5},
    "pro": {"nazwa": "Pro", "cena_zl": 1500, "pula": 1875, "uzytkownikow": 20, "gb": 300, "kontakty": 15},
    "pro_plus": {"nazwa": "Kancelaria+", "cena_zl": 3600, "pula": 4500, "uzytkownikow": 50, "gb": 1000, "kontakty": 40},
}
# Pakiety kredytow (platnosc jednorazowa). Najwiekszy pakiet = najnizsza cena kredytu.
PAKIETY: dict[str, dict] = {
    "100": {"kredyty": 100, "cena_zl": 100},
    "500": {"kredyty": 500, "cena_zl": 450},
    "2000": {"kredyty": 2000, "cena_zl": 1600},
}
PLAN_DOMYSLNY = os.getenv("PIECZAPP_PLAN_DOMYSLNY", "kancelaria")
# Debet: tyle kredytow ponizej zera kancelaria moze zejsc, zeby nie przerwac
# czynnosci w srodku (jak karencja abonamentu w platnosci.py).
DEBET_KREDYTOW = float(os.getenv("PIECZAPP_DEBET_KREDYTOW", "30"))
# Kredyty na start dla nowej kancelarii (okres probny) - raz na NIP.
KREDYTY_PROBNE = float(os.getenv("PIECZAPP_KREDYTY_PROBNE", "150"))
# Waznosc partii kredytow (dni) wg zrodla. Pakiety: 12 miesiecy (do Regulaminu).
WAZNOSC_DNI = {"pakiet": 365, "reczne": 365, "proba": 30, "nagroda": 90, "zwrot": 90, "polecenie": 180}
# Plan bez wpisu w portfelu (np. przed pierwsza faktura) - limity jak "start".
PLAN_BEZ_ABONAMENTU = "start"


def najnizsza_cena_kredytu() -> float:
    """Efektywna cena kredytu w kazdym planie i pakiecie - minimum."""
    ceny = [p["cena_zl"] / p["pula"] for p in PLANY.values()]
    ceny += [p["cena_zl"] / p["kredyty"] for p in PAKIETY.values()]
    return min(ceny)


# --- licznik kosztow biezacej akcji ---------------------------------------------


@dataclass
class Licznik:
    wejscie: int = 0
    wyjscie: int = 0
    cache_odczyt: int = 0
    cache_zapis: int = 0
    wywolan: int = 0
    koszt_zl: float = 0.0
    _blokada: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def dodaj(self, model: str, uzycie: dict) -> None:
        we = int(uzycie.get("inputTokens") or 0)
        wy = int(uzycie.get("outputTokens") or 0)
        co = int(uzycie.get("cacheReadInputTokens") or uzycie.get("cacheReadInputTokenCount") or 0)
        cz = int(uzycie.get("cacheWriteInputTokens") or uzycie.get("cacheWriteInputTokenCount") or 0)
        koszt = koszt_tokenow_zl(model, we, wy, co, cz)
        with self._blokada:
            self.wejscie += we
            self.wyjscie += wy
            self.cache_odczyt += co
            self.cache_zapis += cz
            self.wywolan += 1
            self.koszt_zl += koszt


_licznik: contextvars.ContextVar[Licznik | None] = contextvars.ContextVar("tokenomia_licznik", default=None)


def dolicz(model: str, uzycie: dict) -> None:
    """Woła bedrock._rozmowa po kazdym wywolaniu modelu."""
    licznik = _licznik.get()
    if licznik is not None and uzycie:
        licznik.dodaj(model, uzycie)


# --- portfel kancelarii ------------------------------------------------------------

HISTORIA_MAKS = 500
_BLOKADA = threading.Lock()
_PROB = 5


class BrakKredytow(HTTPException):
    """Saldo nie pokrywa akcji (poza dopuszczalnym debetem). HTTP 402 - takze
    z pracy w tle (_wykonaj w app.py przekazuje HTTPException przegladarce)."""

    def __init__(self, potrzeba: float, saldo: float):
        self.potrzeba, self.saldo = potrzeba, saldo
        super().__init__(402, (
            f"Brak kredytów: ta czynność kosztuje {potrzeba:g} kr., saldo {saldo:g} kr. "
            "Dokup pakiet w oknie Abonament albo poczekaj na odnowienie puli."))

    def __str__(self) -> str:
        return self.detail


def _teraz() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _miesiac() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _pusty_portfel() -> dict:
    return {"plan": None, "pula": 0.0, "partie": [], "przetworzone": [],
            "historia": [], "miesiace": {}, "liczniki": {}}


def _dzis() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _za_dni(dni: int) -> str:
    from datetime import timedelta
    return (datetime.now(timezone.utc).date() + timedelta(days=dni)).isoformat()


def _wazne(portfel: dict) -> list[dict]:
    dzis = _dzis()
    return [p for p in portfel.get("partie", []) if p.get("wygasa", "9999") >= dzis and p["kredyty"] > 0]


def _normalizuj(portfel: dict) -> None:
    """Stary format (pole "doladowane") -> partia; wygasle partie -> historia."""
    stare = float(portfel.pop("doladowane", 0) or 0)
    portfel.setdefault("partie", [])
    portfel.setdefault("liczniki", {})
    if stare > 0:
        portfel["partie"].append({"kredyty": stare, "zrodlo": "pakiet", "wygasa": _za_dni(365)})
    elif stare < 0:
        portfel["pula"] = round(float(portfel.get("pula", 0)) + stare, 2)
    dzis = _dzis()
    for partia in [p for p in portfel["partie"] if p.get("wygasa", "9999") < dzis and p["kredyty"] > 0]:
        _wpis(portfel, {"akcja": "wygasniecie", "kredyty": -partia["kredyty"], "zrodlo": partia["zrodlo"]})
    portfel["partie"] = _wazne(portfel)


def _klucz(kancelaria: str, katalog: str = "kredyty") -> str:
    import magazyn
    return f"{magazyn.PREFIKS}/admin/{katalog}/{kancelaria}.json"


def _plik(kancelaria: str, katalog: str = "kredyty") -> Path:
    import config
    sciezka = config.DANE / katalog
    sciezka.mkdir(parents=True, exist_ok=True)
    return sciezka / f"{kancelaria}.json"


def _czytaj_s3(kancelaria: str, katalog: str = "kredyty") -> tuple[dict | None, str]:
    import magazyn
    try:
        odp = magazyn._klient_s3().get_object(Bucket=magazyn.BUCKET, Key=_klucz(kancelaria, katalog))
    except Exception as blad:  # noqa: BLE001
        if type(blad).__name__ == "NoSuchKey" or magazyn._kod_bledu(blad) in ("NoSuchKey", "404"):
            return None, ""
        raise
    return json.loads(odp["Body"].read().decode("utf-8")), odp.get("ETag", "")


def wczytaj_portfel(kancelaria: str, katalog: str = "kredyty") -> dict | None:
    """Portfel albo None - kancelaria bez portfela nie placi kredytami.
    `katalog` pozwala trzymac tak samo inne dane rozliczeniowe (akademia)."""
    import magazyn
    if magazyn.TRYB == "s3":
        return _czytaj_s3(kancelaria, katalog)[0]
    plik = _plik(kancelaria, katalog)
    with _BLOKADA:
        return json.loads(plik.read_text("utf-8")) if plik.exists() else None


def zmien_portfel(kancelaria: str, zmiana, utworz: bool = False, katalog: str = "kredyty", pusty=None):
    """Odczyt - zmiana - zapis warunkowy. `zmiana(portfel)` zmienia w miejscu.
    Bez portfela i bez `utworz` zwraca None, niczego nie zapisujac."""
    import magazyn
    portfel = katalog == "kredyty"
    nowy = (pusty or _pusty_portfel) if portfel else (pusty or dict)
    if magazyn.TRYB != "s3":
        plik = _plik(kancelaria, katalog)
        with _BLOKADA:
            dane = json.loads(plik.read_text("utf-8")) if plik.exists() else None
            if dane is None:
                if not utworz:
                    return None
                dane = nowy()
            if portfel:
                _normalizuj(dane)
            wynik = zmiana(dane)
            tymczasowy = plik.with_suffix(".tmp")
            tymczasowy.write_text(json.dumps(dane, ensure_ascii=False, indent=1), encoding="utf-8")
            tymczasowy.replace(plik)
        return wynik
    for _ in range(_PROB):
        dane, etag = _czytaj_s3(kancelaria, katalog)
        if dane is None:
            if not utworz:
                return None
            dane = nowy()
        if portfel:
            _normalizuj(dane)
        wynik = zmiana(dane)
        warunek = {"IfMatch": etag} if etag else {"IfNoneMatch": "*"}
        try:
            magazyn._klient_s3().put_object(
                Bucket=magazyn.BUCKET, Key=_klucz(kancelaria, katalog),
                Body=json.dumps(dane, ensure_ascii=False).encode("utf-8"),
                **warunek, **magazyn._szyfrowanie())
        except Exception as blad:  # noqa: BLE001
            if magazyn._kod_bledu(blad) in ("PreconditionFailed", "ConditionalRequestConflict", "412", "409"):
                continue
            raise
        return wynik
    raise magazyn.KonfliktZapisu("Portfel kredytow zmienial sie rownoczesnie. Sprobuj za chwile.")


def dokupione(portfel: dict) -> float:
    """Wazne kredyty spoza puli abonamentu (pakiety, nagrody, zwroty)."""
    stare = float(portfel.get("doladowane", 0) or 0)       # przed migracja formatu
    return round(sum(p["kredyty"] for p in _wazne(portfel)) + stare, 2)


def saldo(portfel: dict) -> float:
    return round(float(portfel.get("pula", 0)) + dokupione(portfel), 2)


def _dodaj_partie(portfel: dict, kredyty: float, zrodlo: str, dni: int | None = None) -> None:
    portfel.setdefault("partie", []).append({
        "kredyty": round(kredyty, 2), "zrodlo": zrodlo,
        "wygasa": _za_dni(dni if dni is not None else WAZNOSC_DNI.get(zrodlo, 365))})


def _wpis(portfel: dict, wpis: dict) -> None:
    portfel.setdefault("historia", []).append({"czas": _teraz(), **wpis})
    del portfel["historia"][:-HISTORIA_MAKS]


def _zaksieguj_miesiac(portfel: dict, akcja: str, kredyty: float, koszt: float) -> None:
    m = portfel.setdefault("miesiace", {}).setdefault(_miesiac(), {})
    a = m.setdefault(akcja, {"ile": 0, "kredyty": 0.0, "koszt_zl": 0.0})
    a["ile"] += 1
    a["kredyty"] = round(a["kredyty"] + kredyty, 2)
    a["koszt_zl"] = round(a["koszt_zl"] + koszt, 4)


def _pobierz(portfel: dict, kredyty: float) -> None:
    """Najpierw pula abonamentu (przepada co okres), potem partie od tej, ktora
    wygasa najwczesniej (nagrody i proba przed pakietami). Brak - dlug w puli,
    potracany z kolejnej puli."""
    _normalizuj(portfel)
    reszta = kredyty
    z_puli = min(max(0.0, float(portfel.get("pula", 0))), reszta)
    portfel["pula"] = round(float(portfel.get("pula", 0)) - z_puli, 2)
    reszta = round(reszta - z_puli, 2)
    for partia in sorted(portfel["partie"], key=lambda p: p.get("wygasa", "9999")):
        if reszta <= 0:
            break
        z_partii = min(partia["kredyty"], reszta)
        partia["kredyty"] = round(partia["kredyty"] - z_partii, 2)
        reszta = round(reszta - z_partii, 2)
    portfel["partie"] = [p for p in portfel["partie"] if p["kredyty"] > 0]
    if reszta > 0:
        portfel["pula"] = round(portfel["pula"] - reszta, 2)


def _jednorazowo(portfel: dict, znacznik: str) -> bool:
    """True, gdy zdarzenie o tym znaczniku jeszcze nie bylo zaksiegowane."""
    przetworzone = portfel.setdefault("przetworzone", [])
    if znacznik in przetworzone:
        return False
    przetworzone.append(znacznik)
    del przetworzone[:-200]
    return True


def doladuj(kancelaria: str, kredyty: float, powod: str, znacznik: str = "",
            zrodlo: str = "pakiet", dni: int | None = None) -> dict | None:
    """Dopisuje partie kredytow. `znacznik` (np. id sesji Stripe) chroni przed
    podwojnym zaksiegowaniem powtorzonego webhooka. Ujemna korekta (reczna)
    zdejmuje kredyty jak zwykle pobranie."""
    def zmiana(p):
        if znacznik and not _jednorazowo(p, znacznik):
            return p
        if kredyty >= 0:
            _dodaj_partie(p, kredyty, zrodlo, dni)
        else:
            _pobierz(p, -kredyty)
        _wpis(p, {"akcja": "doladowanie", "kredyty": kredyty, "powod": powod, "zrodlo": zrodlo})
        return p
    log.info("tokenomia: kancelaria %s, doladowanie %g kr. (%s)", kancelaria, kredyty, powod)
    return zmien_portfel(kancelaria, zmiana, utworz=True)


def odnow_pule(kancelaria: str, plan: str, znacznik: str = "") -> dict | None:
    """Nowy okres abonamentu: pula = pula planu (niewykorzystana przepada)."""
    if plan not in PLANY:
        plan = PLAN_DOMYSLNY

    def zmiana(p):
        if znacznik and not _jednorazowo(p, znacznik):
            return p
        p["plan"] = plan
        # Dlug (ujemna pula) potracamy z nowej puli, zeby nie zniknal.
        p["pula"] = round(float(PLANY[plan]["pula"]) + min(0.0, float(p.get("pula", 0))), 2)
        _wpis(p, {"akcja": "odnowienie_puli", "kredyty": PLANY[plan]["pula"], "plan": plan})
        return p
    log.info("tokenomia: kancelaria %s, odnowiona pula planu %s", kancelaria, plan)
    return zmien_portfel(kancelaria, zmiana, utworz=True)


REJESTR_PROB = "_proby"


def _nip_uzyty(nip: str) -> bool:
    """True, gdy ten NIP dostal juz kredyty probne. Zapamietujemy skrot NIP-u,
    nie numer. Chroni przed zakladaniem kolejnych kont dla kredytow."""
    import hashlib
    skrot = hashlib.sha256(("notarai-proba:" + nip).encode()).hexdigest()[:24]

    def zmiana(p):
        uzyte = p.setdefault("nip", [])
        if skrot in uzyte:
            return True
        uzyte.append(skrot)
        return False
    return zmien_portfel(REJESTR_PROB, zmiana, utworz=True)


def zaloz_portfel_probny(kancelaria: str, nip: str = "") -> dict | None:
    """Portfel nowej kancelarii z partia probna (wygasa po 30 dniach, a nie
    znika przy pierwszej fakturze). Kredyty probne raz na NIP."""
    nip = "".join(c for c in (nip or "") if c.isdigit())
    probne = KREDYTY_PROBNE if not (nip and _nip_uzyty(nip)) else 0.0
    if nip and not probne:
        log.info("tokenomia: kancelaria %s bez kredytow probnych (NIP juz je dostal)", kancelaria)

    def zmiana(p):
        if probne and _jednorazowo(p, "proba"):
            _dodaj_partie(p, probne, "proba")
            _wpis(p, {"akcja": "kredyty_probne", "kredyty": probne})
        return p
    return zmien_portfel(kancelaria, zmiana, utworz=True)


def plan_kancelarii(portfel: dict | None) -> dict:
    return PLANY.get((portfel or {}).get("plan") or PLAN_BEZ_ABONAMENTU, PLANY[PLAN_BEZ_ABONAMENTU])


def licznik_miesiaca(portfel: dict, nazwa: str) -> int:
    return int(((portfel.get("liczniki") or {}).get(_miesiac()) or {}).get(nazwa, 0))


def _zwieksz_licznik(portfel: dict, nazwa: str) -> int:
    m = portfel.setdefault("liczniki", {}).setdefault(_miesiac(), {})
    m[nazwa] = int(m.get(nazwa, 0)) + 1
    for stary in sorted(portfel["liczniki"])[:-13]:
        del portfel["liczniki"][stary]
    return m[nazwa]


# --- akcja: sprawdzenie salda, pomiar, pobranie ----------------------------------


def _kancelaria() -> str:
    import magazyn
    return magazyn.kancelaria()


def egzekwowana(kancelaria: str) -> dict | None:
    """Portfel, jesli tokenomia obowiazuje te kancelarie; inaczej None."""
    if not WLACZONA or kancelaria in ("", "lokalna"):
        return None
    return wczytaj_portfel(kancelaria)


# Kredyty zarezerwowane przez trwajace akcje (w tym procesie). Bez tego dziesiec
# odczytow uruchomionych naraz przeszloby sprawdzenie salda kazdy osobno.
# Druga kopia aplikacji ma wlasne rezerwacje - przed reszta chroni debet.
_REZERWACJE: dict[str, float] = {}
_BLOKADA_REZERWACJI = threading.Lock()


def zarezerwowane(kancelaria: str) -> float:
    with _BLOKADA_REZERWACJI:
        return _REZERWACJE.get(kancelaria, 0.0)


def _rezerwuj(kancelaria: str, kredyty: float) -> None:
    portfel = egzekwowana(kancelaria)
    if portfel is None or kredyty <= 0:
        return
    with _BLOKADA_REZERWACJI:
        dostepne = saldo(portfel) - _REZERWACJE.get(kancelaria, 0.0)
        if dostepne - kredyty < -DEBET_KREDYTOW:
            raise BrakKredytow(kredyty, round(dostepne, 2))
        _REZERWACJE[kancelaria] = _REZERWACJE.get(kancelaria, 0.0) + kredyty


def _zwolnij(kancelaria: str, kredyty: float) -> None:
    with _BLOKADA_REZERWACJI:
        reszta = round(_REZERWACJE.get(kancelaria, 0.0) - kredyty, 2)
        if reszta > 0:
            _REZERWACJE[kancelaria] = reszta
        else:
            _REZERWACJE.pop(kancelaria, None)


def sprawdz(kod: str, ilosc: float = 1) -> float:
    """Rzuca BrakKredytow, gdy saldo (minus rezerwacje, plus debet) nie pokrywa
    akcji. Zwraca cene. Niczego nie rezerwuje."""
    cena = AKCJE[kod].kredyty() * ilosc
    kancelaria = _kancelaria()
    portfel = egzekwowana(kancelaria)
    if portfel is not None and cena > 0:
        dostepne = saldo(portfel) - zarezerwowane(kancelaria)
        if dostepne - cena < -DEBET_KREDYTOW:
            raise BrakKredytow(cena, round(dostepne, 2))
    return cena


def wycena(pozycje: list[tuple[str, float]]) -> dict:
    """Ile beda kosztowac pozycje i czy saldo wystarczy - przed klikniecem."""
    kredyty = round(sum(AKCJE[k].kredyty() * n for k, n in pozycje if k in AKCJE), 2)
    kancelaria = _kancelaria()
    portfel = egzekwowana(kancelaria)
    if portfel is None:
        return {"kredyty": kredyty, "egzekwowana": False, "wystarczy": True, "saldo_po": None}
    dostepne = saldo(portfel) - zarezerwowane(kancelaria)
    return {"kredyty": kredyty, "egzekwowana": True, "saldo_po": round(dostepne - kredyty, 2),
            "wystarczy": dostepne - kredyty >= -DEBET_KREDYTOW}


class akcja:
    """Kontekst akcji platnej:

        with tokenomia.akcja("projekt", ilosc=1, sprawa=identyfikator) as a:
            a.dodaj("projekt_dodatek", 2)    # opcjonalnie dalsze pozycje
            ... wywolania modelu ...

    Na wejsciu sprawdza saldo, w srodku liczy tokeny, po sukcesie pobiera
    kredyty i zapisuje koszt. Po bledzie nic nie pobiera (koszt nieudanej
    proby jest wliczony w NARZUT_NA_BLEDY)."""

    def __init__(self, kod: str, ilosc: float = 1, sprawa: str = ""):
        self.pozycje: list[tuple[str, float]] = [(kod, ilosc)]
        self.sprawa = sprawa
        self.licznik = Licznik()
        self.kancelaria = ""
        self.pobrano = 0.0

    def dodaj(self, kod: str, ilosc: float) -> None:
        if ilosc > 0:
            self.pozycje.append((kod, ilosc))

    def cena(self) -> float:
        return round(sum(AKCJE[k].kredyty() * n for k, n in self.pozycje), 2)

    def __enter__(self):
        self.kancelaria = _kancelaria()
        self._rezerwacja = self.cena()
        _rezerwuj(self.kancelaria, self._rezerwacja)
        self._znacznik = _licznik.set(self.licznik)
        self._start = time.monotonic()
        return self

    def __exit__(self, typ, wartosc, slad):
        _licznik.reset(self._znacznik)
        try:
            if typ is None:
                self.zaksieguj()
        finally:
            _zwolnij(self.kancelaria, self._rezerwacja)
        return False

    def zaksieguj(self) -> None:
        kredyty = round(sum(AKCJE[k].kredyty() * n for k, n in self.pozycje), 2)
        zewnetrzny = sum(AKCJE[k].koszt_zewnetrzny_zl * n for k, n in self.pozycje)
        koszt = round(self.licznik.koszt_zl + zewnetrzny, 4)
        glowna = self.pozycje[0][0]
        przychod = kredyty * CENA_KREDYTU_ZL
        log.info("tokenomia: %s x%g sprawa=%s wywolan=%d we=%d wy=%d koszt=%.3f zl kredyty=%g",
                 glowna, sum(n for _, n in self.pozycje), self.sprawa or "-", self.licznik.wywolan,
                 self.licznik.wejscie, self.licznik.wyjscie, koszt, kredyty)
        if przychod and koszt and przychod < koszt * (1 + NARZUT):
            log.warning("tokenomia: %s ponizej progu narzutu (koszt %.3f zl, cena %.2f zl)",
                        glowna, koszt, przychod)
        _zapisz_pomiar(glowna, sum(n for _, n in self.pozycje), self.licznik, koszt, kredyty)
        if egzekwowana(self.kancelaria) is None:
            return

        def zmiana(p):
            _pobierz(p, kredyty)
            _wpis(p, {"akcja": glowna, "ilosc": sum(n for _, n in self.pozycje), "kredyty": -kredyty,
                      "koszt_zl": koszt, "sprawa": self.sprawa})
            _zaksieguj_miesiac(p, glowna, kredyty, koszt)
            return p
        zmien_portfel(self.kancelaria, zmiana)
        self.pobrano = kredyty


def obciaz(kod: str, ilosc: float, sprawa: str = "") -> float:
    """Pobranie za akcje bez wywolan modelu (np. nadane przesylki), gdy liczbe
    jednostek znamy dopiero po wykonaniu. Zwraca pobrane kredyty."""
    if ilosc <= 0:
        return 0.0
    a = akcja(kod, ilosc, sprawa)
    a.kancelaria = _kancelaria()
    a.zaksieguj()
    return a.pobrano


# --- ochrona przed kosztami bez platnika -------------------------------------------

# Publiczny kalkulator taksy wola model bez logowania. Limity na IP nie
# wystarcza przy rozproszonym ruchu automatow: 1500 tur na dobe x 2 kopie x
# ~0,11 zl to do ok. 10 tys. zl miesiecznie. Dzienny budzet (na proces) to
# twardy sufit - po nim kalkulator odsyla do formularza, ktory liczy bez modelu.
BUDZET_PUBLICZNY_ZL = float(os.getenv("PIECZAPP_BUDZET_PUBLICZNY_ZL", "40"))
_BUDZET: dict[str, float] = {}


def budzet_publiczny_ok() -> bool:
    with _BLOKADA:
        return _BUDZET.get(_dzis(), 0.0) < BUDZET_PUBLICZNY_ZL


def dolicz_publiczny(koszt_zl: float) -> None:
    with _BLOKADA:
        dzis = _dzis()
        for dzien in [d for d in _BUDZET if d != dzis]:
            del _BUDZET[dzien]
        _BUDZET[dzis] = _BUDZET.get(dzis, 0.0) + koszt_zl


# Asystent w przegladarce: pomocnik konczy po 20 krokach, ale serwer nie moze
# wierzyc pomocnikowi - zapetlony albo podmieniony program drenowalby kredyty.
MAKS_KROKOW_ZLECENIA = int(os.getenv("PIECZAPP_MAKS_KROKOW_ZLECENIA", "30"))
_KROKI: dict[str, int] = {}


def krok_zlecenia(zlecenie: str) -> int:
    """Kolejny numer kroku zlecenia (w procesie). Powyzej limitu - 429."""
    with _BLOKADA:
        _KROKI[zlecenie] = _KROKI.get(zlecenie, 0) + 1
        if len(_KROKI) > 5000:
            for stary in list(_KROKI)[:1000]:
                del _KROKI[stary]
        numer = _KROKI[zlecenie]
    if numer > MAKS_KROKOW_ZLECENIA:
        raise HTTPException(429, f"Asystent przekroczyl {MAKS_KROKOW_ZLECENIA} krokow w tym zleceniu. "
                                 "Zlec je od nowa z dokladniejszym celem.")
    return numer


# Ta sama ksiega w tej samej sprawie w ciagu doby: drugi raz bez oplaty
# (odswiezenie przed czynnoscia, pomylka w kliknieciu). Skrot, nie numer KW.
PONOWNE_KW_GODZIN = 24


def kw_juz_oplacona(sprawa: str, numer: str) -> bool:
    import hashlib
    portfel = egzekwowana(_kancelaria())
    if portfel is None:
        return False
    skrot = hashlib.sha256(f"{sprawa}|{numer}".encode()).hexdigest()[:16]
    czas = (portfel.get("kw") or {}).get(skrot)
    if not czas:
        return False
    return (datetime.now(timezone.utc) - datetime.fromisoformat(czas)).total_seconds() < PONOWNE_KW_GODZIN * 3600


def zapamietaj_kw(sprawa: str, numer: str) -> None:
    import hashlib
    skrot = hashlib.sha256(f"{sprawa}|{numer}".encode()).hexdigest()[:16]

    def zmiana(p):
        kw = p.setdefault("kw", {})
        kw[skrot] = _teraz()
        for stary in sorted(kw, key=kw.get)[:-200]:
            del kw[stary]
    if egzekwowana(_kancelaria()) is not None:
        zmien_portfel(_kancelaria(), zmiana)


# --- odsloniecie kontaktu klienta (wizyty.py) ----------------------------------------

PLATNY_KONTAKT = os.getenv("PIECZAPP_PLATNY_KONTAKT", "true").lower() == "true"
REKLAMACJE_W_MIESIACU = int(os.getenv("PIECZAPP_REKLAMACJE_W_MIESIACU", "5"))
REKLAMACJA_DNI = 7


def kontakt_platny(kancelaria: str) -> bool:
    """Czy ta kancelaria odslania kontakty klientow za kredyty."""
    return PLATNY_KONTAKT and egzekwowana(kancelaria) is not None


def odslon_kontakt(kancelaria: str, zapytanie: str, duplikat: bool = False) -> dict:
    """Odsloniecie jednego zapytania, atomowo w portfelu: najpierw pula
    odslonien z planu, potem kredyty. Duplikat (ten sam klient odsloniety
    niedawno) - bez oplaty i bez zuzycia puli. 402, gdy brak kredytow."""
    cena = AKCJE["kontakt_klienta"].kredyty()

    def zmiana(p):
        if duplikat:
            tryb, kredyty = "duplikat", 0.0
        elif licznik_miesiaca(p, "kontakt_klienta") < plan_kancelarii(p)["kontakty"]:
            tryb, kredyty = "pula", 0.0
            _zwieksz_licznik(p, "kontakt_klienta")
        else:
            dostepne = saldo(p) - zarezerwowane(kancelaria)
            if dostepne - cena < -DEBET_KREDYTOW:
                raise BrakKredytow(cena, round(dostepne, 2))
            tryb, kredyty = "platne", cena
            _pobierz(p, cena)
            _zaksieguj_miesiac(p, "kontakt_klienta", cena, 0.0)
        _wpis(p, {"akcja": "kontakt_klienta", "ilosc": 1, "kredyty": -kredyty, "koszt_zl": 0.0,
                  "sprawa": f"zapytanie {zapytanie}", "tryb": tryb})
        return {"tryb": tryb, "kredyty": kredyty}
    wynik = zmien_portfel(kancelaria, zmiana)
    log.info("tokenomia: kancelaria %s odslonila kontakt (%s, %g kr.)", kancelaria, wynik["tryb"], wynik["kredyty"])
    return wynik


def zwrot_kontaktu(kancelaria: str, zapytanie: str, odsloniecie: dict, powod: str) -> dict:
    """Reklamacja odsloniecia (falszywy numer, spam): zwrot kredytow albo
    miejsca w puli. Najwyzej REKLAMACJE_W_MIESIACU w miesiacu."""
    def zmiana(p):
        if licznik_miesiaca(p, "reklamacje") >= REKLAMACJE_W_MIESIACU:
            raise HTTPException(429, f"W tym miesiacu wykorzystano juz {REKLAMACJE_W_MIESIACU} reklamacji. "
                                     "Napisz do nas: kontakt@notarai.pl.")
        _zwieksz_licznik(p, "reklamacje")
        if odsloniecie.get("tryb") == "platne" and odsloniecie.get("kredyty"):
            _dodaj_partie(p, float(odsloniecie["kredyty"]), "zwrot")
            zwrot = float(odsloniecie["kredyty"])
        else:
            if odsloniecie.get("tryb") == "pula":
                m = p.setdefault("liczniki", {}).setdefault(_miesiac(), {})
                m["kontakt_klienta"] = max(0, int(m.get("kontakt_klienta", 0)) - 1)
            zwrot = 0.0
        _wpis(p, {"akcja": "reklamacja_kontaktu", "kredyty": zwrot, "sprawa": f"zapytanie {zapytanie}",
                  "powod": powod})
        return {"zwrot": zwrot, "tryb": odsloniecie.get("tryb")}
    return zmien_portfel(kancelaria, zmiana)


def limit_zespolu(kancelaria: str, osob: int) -> None:
    """Plan okresla liczbe osob z kontem. 402, gdy zaproszenie by go przekroczylo."""
    portfel = egzekwowana(kancelaria)
    if portfel is None:
        return
    plan = plan_kancelarii(portfel)
    if osob >= plan["uzytkownikow"]:
        raise HTTPException(402, f"Plan {plan['nazwa']} obejmuje {plan['uzytkownikow']} osob. "
                                 "Wyzszy plan wlaczysz w oknie Abonament.")


# --- pomiary i kalibracja -----------------------------------------------------------
# Pomiary (bez kancelarii i bez spraw) zbieramy w pamieci procesu: wystarcza
# do kalibracji po kilkuset akcjach; trwala wersje daje "miesiace" w portfelach.

_POMIARY: dict[str, list[tuple[float, int, int, float]]] = {}
_POMIARY_MAKS = 2000


def _zapisz_pomiar(kod: str, ilosc: float, licznik: Licznik, koszt: float, kredyty: float) -> None:
    if ilosc <= 0:
        return
    with _BLOKADA:
        lista = _POMIARY.setdefault(kod, [])
        lista.append((koszt / ilosc, int(licznik.wejscie / ilosc), int(licznik.wyjscie / ilosc),
                      kredyty / ilosc))
        del lista[:-_POMIARY_MAKS]


def _percentyl(wartosci: list[float], p: float) -> float:
    if not wartosci:
        return 0.0
    w = sorted(wartosci)
    return w[min(len(w) - 1, int(math.ceil(p / 100 * len(w))) - 1)]


def kalibracja(pomiary: dict[str, list[tuple[float, int, int, float]]] | None = None,
               minimum: int = 20) -> list[dict]:
    """Porownanie cennika z praktyka: koszt P50/P90 z pomiarow, zrealizowany
    narzut i cena, jaka wynika z pomiarow. `ok` = narzut >= NARZUT przy P90."""
    pomiary = _POMIARY if pomiary is None else pomiary
    wynik = []
    for kod, lista in sorted(pomiary.items()):
        if kod not in AKCJE or len(lista) < minimum:
            continue
        koszty = [k for k, _, _, _ in lista]
        p90 = _percentyl(koszty, 90)
        cena = AKCJE[kod].kredyty()
        sredni = sum(koszty) / len(koszty)
        wymagane = max(p90 * (1 + NARZUT) / CENA_KREDYTU_ZL,
                       sredni * (1 + NARZUT) / NAJNIZSZA_CENA_KREDYTU_ZL)
        zalecana = max(KROK_KREDYTU, math.ceil(wymagane / KROK_KREDYTU - 1e-9) * KROK_KREDYTU)
        # Narzut zrealizowany w gorszym z dwoch warunkow cennika.
        narzuty = [cena * CENA_KREDYTU_ZL / p90 - 1 if p90 else None,
                   cena * NAJNIZSZA_CENA_KREDYTU_ZL / sredni - 1 if sredni else None]
        narzuty = [n for n in narzuty if n is not None]
        narzut = min(narzuty) if narzuty else None
        wynik.append({"akcja": kod, "pomiarow": len(lista),
                      "koszt_p50_zl": round(_percentyl(koszty, 50), 4),
                      "koszt_sredni_zl": round(sredni, 4), "koszt_p90_zl": round(p90, 4),
                      "tokeny_we_p90": int(_percentyl([w for _, w, _, _ in lista], 90)),
                      "tokeny_wy_p90": int(_percentyl([w for _, _, w, _ in lista], 90)),
                      "kredyty": cena, "zalecane_kredyty": zalecana,
                      "narzut_p90": None if narzut is None else round(narzut, 2),
                      "ok": narzut is None or narzut >= NARZUT - 1e-9})
    return wynik


def podsumowanie_miesiaca(portfel: dict, miesiac: str | None = None) -> dict:
    akcje = (portfel.get("miesiace") or {}).get(miesiac or _miesiac(), {})
    kredyty = sum(a["kredyty"] for a in akcje.values())
    koszt = sum(a["koszt_zl"] for a in akcje.values())
    return {"miesiac": miesiac or _miesiac(), "akcje": akcje, "kredyty": round(kredyty, 2),
            "koszt_zl": round(koszt, 2),
            "narzut": round(kredyty * NAJNIZSZA_CENA_KREDYTU_ZL / koszt - 1, 2) if koszt else None}


# --- API: kancelaria i administrator ------------------------------------------------

from fastapi import APIRouter, Request  # noqa: E402
from pydantic import BaseModel  # noqa: E402

router = APIRouter(prefix="/api/kredyty", tags=["kredyty"])
router_admina = APIRouter(prefix="/api/admin", tags=["admin"])


def saldo_kancelarii() -> float | None:
    """Saldo biezacej kancelarii albo None, gdy nie placi kredytami."""
    portfel = egzekwowana(_kancelaria())
    return None if portfel is None else saldo(portfel)


def _widok_portfela(portfel: dict | None) -> dict:
    return {
        "wlaczona": WLACZONA,
        "egzekwowana": portfel is not None,
        "saldo": None if portfel is None else saldo(portfel),
        "pula": None if portfel is None else portfel.get("pula", 0),
        "doladowane": None if portfel is None else dokupione(portfel),
        "partie": [] if portfel is None else sorted(_wazne(portfel), key=lambda p: p["wygasa"]),
        "niskie": portfel is not None and saldo(portfel) < max(20.0, 0.15 * plan_kancelarii(portfel)["pula"]),
        "kontakty_w_planie": None if portfel is None else {
            "w_planie": plan_kancelarii(portfel)["kontakty"],
            "wykorzystane": licznik_miesiaca(portfel, "kontakt_klienta")},
        "plan": None if portfel is None else portfel.get("plan"),
        "debet": DEBET_KREDYTOW,
        "cena_kredytu_zl": CENA_KREDYTU_ZL,
        "cennik": [{k: c[k] for k in ("kod", "nazwa", "jednostka", "kredyty")} for c in cennik()],
        "plany": PLANY,
        "pakiety": PAKIETY,
        "miesiac": podsumowanie_miesiaca(portfel) if portfel else None,
        "historia": (portfel or {}).get("historia", [])[-50:],
    }


@router.get("")
def moje_kredyty():
    return _widok_portfela(egzekwowana(_kancelaria()))


class PozycjaWyceny(BaseModel):
    kod: str
    ilosc: float = 1


class ZadanieWyceny(BaseModel):
    pozycje: list[PozycjaWyceny]


@router.post("/wycena")
def wycen(dane: ZadanieWyceny):
    """Koszt czynnosci przed jej uruchomieniem (np. odczyt N stron) - zeby
    notariusz nie dowiadywal sie o cenie po fakcie."""
    if not dane.pozycje or len(dane.pozycje) > 20:
        raise HTTPException(400, "Podaj od 1 do 20 pozycji")
    nieznane = [p.kod for p in dane.pozycje if p.kod not in AKCJE]
    if nieznane or any(not 0 <= p.ilosc <= 10_000 for p in dane.pozycje):
        raise HTTPException(400, "Nieznana czynnosc albo zla liczba jednostek")
    return wycena([(p.kod, p.ilosc) for p in dane.pozycje])


class ZakupPakietu(BaseModel):
    pakiet: str


@router.post("/pakiet", status_code=201)
def kup_pakiet(request: Request, dane: ZakupPakietu):
    """Strona platnosci Stripe za pakiet kredytow (platnosc jednorazowa)."""
    import autoryzacja
    import platnosci
    if dane.pakiet not in PAKIETY:
        raise HTTPException(400, "Nie ma takiego pakietu")
    _, _, wpis, email = autoryzacja._moja_kancelaria(request)
    if email not in autoryzacja._wlasciciele(wpis):
        raise HTTPException(403, "Kredyty kupuje wlasciciel kancelarii.")
    pakiet = PAKIETY[dane.pakiet]
    try:
        return platnosci.utworz_checkout_kredytow(
            wpis["id"], email, (wpis.get("stripe") or {}).get("klient", ""),
            dane.pakiet, pakiet["kredyty"], pakiet["cena_zl"])
    except platnosci.BladPlatnosci as blad:
        raise HTTPException(502, str(blad))


def z_platnosci_stripe(sesja: dict) -> bool:
    """checkout.session.completed za pakiet. True = to byl zakup kredytow
    (webhook nie dotyka wtedy subskrypcji)."""
    meta = sesja.get("metadata") or {}
    if meta.get("typ") != "kredyty":
        return False
    pakiet = PAKIETY.get(meta.get("pakiet", ""))
    if pakiet and meta.get("kancelaria") and sesja.get("payment_status") == "paid":
        doladuj(meta["kancelaria"], float(pakiet["kredyty"]), f"pakiet {meta['pakiet']}",
                znacznik=sesja.get("id", ""))
    return True


class Doladowanie(BaseModel):
    kredyty: float
    powod: str = "recznie"


@router_admina.post("/kancelarie/{id_k}/kredyty")
def admin_doladuj(request: Request, id_k: str, dane: Doladowanie):
    import autoryzacja
    autoryzacja._wymagaj_admina(request)
    if autoryzacja._znajdz(autoryzacja._wczytaj_rejestr(), id_k)[1] is None:
        raise HTTPException(404, "Nie znaleziono kancelarii")
    if not -10_000 <= dane.kredyty <= 10_000 or dane.kredyty == 0:
        raise HTTPException(400, "Podaj liczbe kredytow od -10000 do 10000")
    portfel = doladuj(id_k, dane.kredyty, dane.powod[:80] or "recznie")
    return {"id": id_k, "saldo": saldo(portfel)}


@router_admina.get("/tokenomia")
def admin_tokenomia(request: Request):
    """Cennik z kosztami, kalibracja z pomiarow i wynik miesiaca kancelarii."""
    import autoryzacja
    autoryzacja._wymagaj_admina(request)
    kancelarie = []
    for wpis in autoryzacja._wczytaj_rejestr().values():
        portfel = wczytaj_portfel(wpis["id"])
        if portfel:
            kancelarie.append({"id": wpis["id"], "nazwa": wpis.get("nazwa"), "saldo": saldo(portfel),
                               "plan": portfel.get("plan"), "miesiac": podsumowanie_miesiaca(portfel)})
    return {"wlaczona": WLACZONA, "narzut_min": NARZUT, "kurs_usd": KURS_USD_PLN,
            "premia_regionalna": PREMIA_REGIONALNA, "najnizsza_cena_kredytu": najnizsza_cena_kredytu(),
            "cennik": cennik(), "kalibracja": kalibracja(minimum=5), "kancelarie": kancelarie}
