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

Kredyty sa jedynym sposobem zakupu notarai - nie ma abonamentu. Nowa
kancelaria dostaje KREDYTY_PROBNE na przetestowanie wszystkich funkcji,
potem dokupuje pakiety przez Finance You / TPay (platnosci.py). Wylaczenie tylko awaryjne:
PIECZAPP_TOKENOMIA=false - licznik nadal liczy koszty (logi i panel admina),
ale niczego nie pobiera ani nie blokuje.
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

WLACZONA = os.getenv("PIECZAPP_TOKENOMIA", "true").lower() == "true"

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
# sprzedajemy w jakimkolwiek pakiecie (patrz PAKIETY).
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
    koszt_zewnetrzny_zl: float = 0.0     # platne zrodlo danych (EKW) na jednostke
    model: str = ""
    darmowa: bool = False                # akcje zgodnosci (staranność) nie kosztuja kredytow
    stala_cena: float | None = None      # cena uslugowa niezalezna od kosztu (np. nadanie)

    def koszt_zl(self, percentyl: int = 90) -> float:
        we50, wy50, we90, wy90 = self.profil
        we, wy = (we90, wy90) if percentyl >= 90 else (we50, wy50)
        tokeny = koszt_tokenow_zl(self.model or MODEL_GLOWNY, we, wy)
        return (tokeny * (1 + NARZUT_NA_BLEDY)) + self.koszt_zewnetrzny_zl

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
    # Szacowana cena zakupu tresci jednej KW u dostawcy (Finance You / Apify).
    Akcja("ekw_ksiega", "Tresc ksiegi wieczystej z EKW", "ksiega",
          koszt_zewnetrzny_zl=float(os.getenv("PIECZAPP_KOSZT_EKW_ZL", "1.80"))),
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


# --- pakiety ---------------------------------------------------------------------

# Jedyny sposob zakupu: jednorazowy pakiet kredytow (ceny netto, VAT doliczany
# przy platnosci). Dokupione kredyty nie przepadaja co miesiac. Typowa sprawa
# to ok. 65-80 kr. (symulacja), wiec pakiety to ok. 1 / 6 / 25 spraw.
# Najwiekszy pakiet = najnizsza cena kredytu (NAJNIZSZA_CENA_KREDYTU_ZL).
PAKIETY: dict[str, dict] = {
    "100": {"kredyty": 100, "cena_zl": 100},
    "500": {"kredyty": 500, "cena_zl": 450},
    "2000": {"kredyty": 2000, "cena_zl": 1600},
}
# Debet: tyle kredytow ponizej zera kancelaria moze zejsc, zeby nie przerwac
# czynnosci w srodku aktu.
DEBET_KREDYTOW = float(os.getenv("PIECZAPP_DEBET_KREDYTOW", "30"))
# Kredyty startowe dla nowej kancelarii: ok. dwie pelne sprawy (odczyt
# ~14 stron, zestawienie, kilka tur rozmowy, projekt aktu, KW, formularz),
# czyli kazda platna funkcja da sie sprawdzic co najmniej raz. Koszt dla nas:
# ok. 45 zl na kancelarie (koszt AI typowej sprawy ok. 22 zl).
KREDYTY_PROBNE = float(os.getenv("PIECZAPP_KREDYTY_PROBNE", "150"))


def najnizsza_cena_kredytu() -> float:
    """Efektywna cena kredytu w kazdym pakiecie - minimum."""
    return min(p["cena_zl"] / p["kredyty"] for p in PAKIETY.values())


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
    # "pula" to kredyty startowe (i dawna pula abonamentu), "doladowane" -
    # kupione w pakietach i dopisane przez administratora.
    return {"pula": 0.0, "doladowane": 0.0, "przetworzone": [],
            "historia": [], "miesiace": {}, "zamowienia": {}}


def _klucz(kancelaria: str) -> str:
    import magazyn
    return f"{magazyn.PREFIKS}/admin/kredyty/{kancelaria}.json"


def _plik(kancelaria: str) -> Path:
    import config
    katalog = config.DANE / "kredyty"
    katalog.mkdir(parents=True, exist_ok=True)
    return katalog / f"{kancelaria}.json"


def _czytaj_s3(kancelaria: str) -> tuple[dict | None, str]:
    import magazyn
    try:
        odp = magazyn._klient_s3().get_object(Bucket=magazyn.BUCKET, Key=_klucz(kancelaria))
    except Exception as blad:  # noqa: BLE001
        if type(blad).__name__ == "NoSuchKey" or magazyn._kod_bledu(blad) in ("NoSuchKey", "404"):
            return None, ""
        raise
    return json.loads(odp["Body"].read().decode("utf-8")), odp.get("ETag", "")


def wczytaj_portfel(kancelaria: str) -> dict | None:
    """Portfel albo None - kancelaria bez portfela nie placi kredytami."""
    import magazyn
    if magazyn.TRYB == "s3":
        return _czytaj_s3(kancelaria)[0]
    plik = _plik(kancelaria)
    with _BLOKADA:
        return json.loads(plik.read_text("utf-8")) if plik.exists() else None


def zmien_portfel(kancelaria: str, zmiana, utworz: bool = False):
    """Odczyt - zmiana - zapis warunkowy. `zmiana(portfel)` zmienia w miejscu.
    Bez portfela i bez `utworz` zwraca None, niczego nie zapisujac."""
    import magazyn
    if magazyn.TRYB != "s3":
        plik = _plik(kancelaria)
        with _BLOKADA:
            dane = json.loads(plik.read_text("utf-8")) if plik.exists() else None
            if dane is None:
                if not utworz:
                    return None
                dane = _pusty_portfel()
            wynik = zmiana(dane)
            tymczasowy = plik.with_suffix(".tmp")
            tymczasowy.write_text(json.dumps(dane, ensure_ascii=False, indent=1), encoding="utf-8")
            tymczasowy.replace(plik)
        return wynik
    for _ in range(_PROB):
        dane, etag = _czytaj_s3(kancelaria)
        if dane is None:
            if not utworz:
                return None
            dane = _pusty_portfel()
        wynik = zmiana(dane)
        warunek = {"IfMatch": etag} if etag else {"IfNoneMatch": "*"}
        try:
            magazyn._klient_s3().put_object(
                Bucket=magazyn.BUCKET, Key=_klucz(kancelaria),
                Body=json.dumps(dane, ensure_ascii=False).encode("utf-8"),
                **warunek, **magazyn._szyfrowanie())
        except Exception as blad:  # noqa: BLE001
            if magazyn._kod_bledu(blad) in ("PreconditionFailed", "ConditionalRequestConflict", "412", "409"):
                continue
            raise
        return wynik
    raise magazyn.KonfliktZapisu("Portfel kredytow zmienial sie rownoczesnie. Sprobuj za chwile.")


def saldo(portfel: dict) -> float:
    return round(float(portfel.get("pula", 0)) + float(portfel.get("doladowane", 0)), 2)


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
    """Najpierw kredyty startowe, potem dokupione."""
    z_puli = min(max(0.0, float(portfel.get("pula", 0))), kredyty)
    portfel["pula"] = round(float(portfel.get("pula", 0)) - z_puli, 2)
    portfel["doladowane"] = round(float(portfel.get("doladowane", 0)) - (kredyty - z_puli), 2)


def _jednorazowo(portfel: dict, znacznik: str) -> bool:
    """True, gdy zdarzenie o tym znaczniku jeszcze nie bylo zaksiegowane."""
    przetworzone = portfel.setdefault("przetworzone", [])
    if znacznik in przetworzone:
        return False
    przetworzone.append(znacznik)
    del przetworzone[:-200]
    return True


def doladuj(kancelaria: str, kredyty: float, powod: str, znacznik: str = "") -> dict | None:
    """Dopisuje dokupione kredyty. `znacznik` (np. numer zamowienia) chroni przed
    podwojnym zaksiegowaniem powtorzonego powiadomienia."""
    def zmiana(p):
        if znacznik and not _jednorazowo(p, znacznik):
            return p
        p["doladowane"] = round(float(p.get("doladowane", 0)) + kredyty, 2)
        _wpis(p, {"akcja": "doladowanie", "kredyty": kredyty, "powod": powod})
        return p
    log.info("tokenomia: kancelaria %s, doladowanie %g kr. (%s)", kancelaria, kredyty, powod)
    return zmien_portfel(kancelaria, zmiana, utworz=True)


def zaloz_portfel_probny(kancelaria: str) -> dict | None:
    def zmiana(p):
        if _jednorazowo(p, "proba"):
            p["pula"] = round(float(p.get("pula", 0)) + KREDYTY_PROBNE, 2)
            _wpis(p, {"akcja": "kredyty_probne", "kredyty": KREDYTY_PROBNE})
        return p
    return zmien_portfel(kancelaria, zmiana, utworz=True)


# --- akcja: sprawdzenie salda, pomiar, pobranie ----------------------------------


def _kancelaria() -> str:
    import magazyn
    return magazyn.kancelaria()


def egzekwowana(kancelaria: str) -> dict | None:
    """Portfel, jesli tokenomia obowiazuje te kancelarie; inaczej None.
    Kancelaria bez portfela (np. zalozona przed tokenomia) dostaje przy
    pierwszej czynnosci portfel z kredytami startowymi - nikt nie pracuje
    poza kredytami."""
    if not WLACZONA or kancelaria in ("", "lokalna"):
        return None
    return wczytaj_portfel(kancelaria) or zaloz_portfel_probny(kancelaria)


def aktywna(kancelaria: str) -> bool:
    """Kancelaria z dodatnim saldem (albo poza tokenomia). Zastepuje dawny
    "oplacony abonament" tam, gdzie liczy sie, czy kancelaria jest klientem
    (archiwum gieldy, rezerwacje klientow)."""
    portfel = egzekwowana(kancelaria)
    return portfel is None or saldo(portfel) > 0


def sprawdz(kod: str, ilosc: float = 1) -> float:
    """Rzuca BrakKredytow, gdy saldo z debetem nie pokrywa akcji. Zwraca cene."""
    cena = AKCJE[kod].kredyty() * ilosc
    portfel = egzekwowana(_kancelaria())
    if portfel is not None and cena > 0 and saldo(portfel) - cena < -DEBET_KREDYTOW:
        raise BrakKredytow(cena, saldo(portfel))
    return cena


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
            sprawdz(kod, ilosc)
            self.pozycje.append((kod, ilosc))

    def __enter__(self):
        self.kancelaria = _kancelaria()
        kod, ilosc = self.pozycje[0]
        sprawdz(kod, ilosc)
        self._znacznik = _licznik.set(self.licznik)
        self._start = time.monotonic()
        return self

    def __exit__(self, typ, wartosc, slad):
        _licznik.reset(self._znacznik)
        if typ is not None:
            return False
        self.zaksieguj()
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


# Nazwa pozycji na fakturze za pakiet. Kredyty to bon jednego przeznaczenia
# (art. 2 pkt 41 i art. 8a ustawy o VAT): wiadomo, na jakie uslugi i gdzie sie
# je wymieni, wiec sprzedaz pakietu jest sprzedaza uslugi w dniu zaplaty, a
# faktura - zwykla faktura (nie zaliczkowa). Dopoki Uslugodawca jest zwolniony
# podmiotowo z VAT, faktura ma adnotacje ADNOTACJA_ZW. Szczegoly: docs/tokenomia.md.
TYTUL_FAKTURY = ("Bon jednego przeznaczenia - pakiet {kredyty} kredytów na usługi "
                 "platformy notarai (oprogramowanie w modelu SaaS dla kancelarii notarialnej)")
ADNOTACJA_ZW = "Sprzedaż zwolniona z VAT na podstawie art. 113 ust. 1 ustawy o podatku od towarów i usług"
ZAMOWIENIA_MAKS = 200


def tytul_faktury(kredyty: float) -> str:
    return TYTUL_FAKTURY.format(kredyty=f"{kredyty:g}")


def _zakupy(portfel: dict | None) -> list[dict]:
    zam = (portfel or {}).get("zamowienia") or {}
    return [{k: z.get(k) for k in ("pakiet", "kredyty", "netto", "brutto", "status", "utworzono", "oplacono",
                                   "faktura")}
            | {"zamowienie": n} for n, z in zam.items() if z.get("status") in ("oplacone", "zwrot")][-24:]


def _widok_portfela(portfel: dict | None, moge_kupic: bool = False) -> dict:
    import platnosci
    return {
        "wlaczona": WLACZONA,
        "egzekwowana": portfel is not None,
        "saldo": None if portfel is None else saldo(portfel),
        "pula": None if portfel is None else portfel.get("pula", 0),
        "doladowane": None if portfel is None else portfel.get("doladowane", 0),
        "debet": DEBET_KREDYTOW,
        "kredyty_probne": KREDYTY_PROBNE,
        "cena_kredytu_zl": CENA_KREDYTU_ZL,
        "vat": float(platnosci.VAT),
        "cennik": [{k: c[k] for k in ("kod", "nazwa", "jednostka", "kredyty")} for c in cennik()],
        "pakiety": {kod: {**p, "brutto_zl": float(platnosci.brutto(p["cena_zl"]))} for kod, p in PAKIETY.items()},
        "platnosci_wlaczone": platnosci.wlaczone(),
        "moge_kupic": moge_kupic,
        "miesiac": podsumowanie_miesiaca(portfel) if portfel else None,
        "historia": (portfel or {}).get("historia", [])[-50:],
        "zakupy": _zakupy(portfel),
    }


def _czy_wlasciciel(request: Request) -> bool:
    import autoryzacja
    email = getattr(request.state, "email", "")
    if not email or getattr(request.state, "serwis", False):
        return False
    _, wpis = autoryzacja._znajdz(autoryzacja._wczytaj_rejestr(), getattr(request.state, "kancelaria", ""))
    return bool(wpis) and email in autoryzacja._wlasciciele(wpis)


@router.get("")
def moje_kredyty(request: Request):
    kancelaria = _kancelaria()
    portfel = egzekwowana(kancelaria)
    if portfel and _uzgodnij_oczekujace(kancelaria, portfel):
        portfel = wczytaj_portfel(kancelaria)
    return _widok_portfela(portfel, _czy_wlasciciel(request))


class ZakupPakietu(BaseModel):
    pakiet: str


@router.post("/pakiet", status_code=201)
def kup_pakiet(request: Request, dane: ZakupPakietu):
    """Zamowienie pakietu w Finance You (konto TPay Fundacji). Zapisujemy je
    w portfelu przed przekierowaniem - kredyty dopisze dopiero potwierdzony
    stan "paid" z Finance You, w kwocie z zamowienia."""
    import secrets

    import autoryzacja
    import platnosci
    if dane.pakiet not in PAKIETY:
        raise HTTPException(400, "Nie ma takiego pakietu")
    _, _, wpis, email = autoryzacja._moja_kancelaria(request)
    if email not in autoryzacja._wlasciciele(wpis):
        raise HTTPException(403, "Kredyty kupuje właściciel kancelarii.")
    if not platnosci.wlaczone():
        raise HTTPException(503, "Płatności nie są skonfigurowane na tym serwerze.")
    pakiet = PAKIETY[dane.pakiet]
    numer = secrets.token_hex(8)
    kwota = platnosci.brutto(pakiet["cena_zl"])
    zamowienie = {"pakiet": dane.pakiet, "kredyty": pakiet["kredyty"], "netto": f"{pakiet['cena_zl']:.2f}",
                  "brutto": str(kwota), "status": "nowe", "utworzono": _teraz()}

    def zapisz(p):
        zam = p.setdefault("zamowienia", {})
        zam[numer] = zamowienie
        for stary in list(zam)[:-ZAMOWIENIA_MAKS]:
            del zam[stary]
        return p
    zmien_portfel(wpis["id"], zapisz, utworz=True)
    dane_firmy = wpis.get("dane") or {}
    nabywca = {"nazwa": wpis.get("nazwa") or wpis["id"], "email": email,
               "nip": (dane_firmy.get("nip") or "").replace("-", "") or None,
               **platnosci.adres_nabywcy(dane_firmy.get("adres", ""))}
    try:
        wynik = platnosci.utworz_zamowienie(f"{wpis['id']}:{numer}", pakiet["kredyty"], kwota,
                                            tytul_faktury(pakiet["kredyty"]), nabywca)
    except platnosci.BladPlatnosci as blad:
        zmien_portfel(wpis["id"], lambda p: p["zamowienia"][numer].update(status="blad"))
        raise HTTPException(502, str(blad))
    zmien_portfel(wpis["id"], lambda p: p["zamowienia"][numer].update(transakcja=wynik.get("transakcja")))
    return {"adres": wynik["adres"], "zamowienie": numer}


def uzgodnij_zamowienie(kancelaria: str, numer: str) -> str | None:
    """Czyta stan zamowienia z Finance You i ksieguje zmiane: oplacone =
    kredyty pakietu (raz), zwrot = odebranie kredytow (raz). Zwraca status
    z Finance You albo None, gdy nie ma czego uzgadniac."""
    import platnosci
    portfel = wczytaj_portfel(kancelaria)
    zamowienie = ((portfel or {}).get("zamowienia") or {}).get(numer)
    if zamowienie is None or zamowienie.get("status") == "blad":
        return None
    stan = platnosci.pobierz_zamowienie(f"{kancelaria}:{numer}")
    if stan is None:
        return None
    status = stan.get("status")
    faktura = stan.get("faktura")

    if status == "paid":
        if int(stan.get("kwota_grosz") or 0) != int(platnosci.grosze(zamowienie["brutto"]) * 100) \
                or int(stan.get("zaplacono_grosz") or 0) < int(platnosci.grosze(zamowienie["brutto"]) * 100) \
                or int(stan.get("kredyty") or 0) != int(zamowienie["kredyty"]):
            log.warning("tokenomia: zamowienie %s - kwota albo pakiet nie zgadza sie z Finance You", numer)
            return status

        def oplac(p):
            z = p["zamowienia"][numer]
            if faktura:
                z["faktura"] = faktura
            if not _jednorazowo(p, f"platnosc:{numer}"):
                return p
            z.update(status="oplacone", oplacono=stan.get("oplacono") or _teraz(),
                     tytul=stan.get("transakcja") or z.get("transakcja"))
            p["doladowane"] = round(float(p.get("doladowane", 0)) + float(z["kredyty"]), 2)
            _wpis(p, {"akcja": "doladowanie", "kredyty": float(z["kredyty"]), "powod": f"pakiet {z['pakiet']}",
                      "zamowienie": numer})
            return p
        zmien_portfel(kancelaria, oplac)
        log.info("tokenomia: kancelaria %s, oplacony pakiet %s", kancelaria, zamowienie["pakiet"])
    elif status == "refunded":
        def zwrot(p):
            z = p["zamowienia"][numer]
            if z.get("status") != "oplacone" or not _jednorazowo(p, f"zwrot:{numer}"):
                return p
            z.update(status="zwrot")
            p["doladowane"] = round(float(p.get("doladowane", 0)) - float(z["kredyty"]), 2)
            _wpis(p, {"akcja": "zwrot", "kredyty": -float(z["kredyty"]), "zamowienie": numer})
            return p
        zmien_portfel(kancelaria, zwrot)
        log.warning("tokenomia: kancelaria %s, zwrot pakietu %s", kancelaria, zamowienie["pakiet"])
    elif status == "failed" and zamowienie.get("status") == "nowe":
        zmien_portfel(kancelaria, lambda p: p["zamowienia"][numer].update(status="blad"))
    return status


def _uzgodnij_oczekujace(kancelaria: str, portfel: dict, maks: int = 3) -> bool:
    """Gdy ping z Finance You zginie: przy otwarciu okna "Kredyty" sprawdzamy
    swieze, nieoplacone zamowienia (z ostatnich 3 dni, najwyzej kilka)."""
    import platnosci
    if not platnosci.wlaczone():
        return False
    granica = datetime.fromtimestamp(time.time() - 3 * 86400, timezone.utc).isoformat(timespec="seconds")
    oczekujace = [n for n, z in (portfel.get("zamowienia") or {}).items()
                  if z.get("status") == "nowe" and (z.get("utworzono") or "") >= granica][-maks:]
    zmiana = False
    for numer in oczekujace:
        try:
            zmiana |= uzgodnij_zamowienie(kancelaria, numer) in ("paid", "failed")
        except platnosci.BladPlatnosci:
            break
    return zmiana


router_platnosci = APIRouter(prefix="/api/finyou", tags=["platnosci"])


class PingPlatnosci(BaseModel):
    zamowienie: str


@router_platnosci.post("/platnosc")
def ping_platnosci(dane: PingPlatnosci):
    """Sygnal z Finance You, ze zamowienie zmienilo stan. Sciezka otwarta,
    wiec niczego z niej nie bierzemy poza numerem - stan czytamy sami
    tokenem partnera. Zawsze 200 (Finance You nie ponawia)."""
    import platnosci
    kancelaria, _, numer = dane.zamowienie.rpartition(":")
    if not kancelaria or not numer or len(dane.zamowienie) > 130:
        return {"odebrano": False}
    try:
        status = uzgodnij_zamowienie(kancelaria, numer)
    except platnosci.BladPlatnosci:
        status = None
    return {"odebrano": True, "uzgodniono": status is not None}


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
                               "miesiac": podsumowanie_miesiaca(portfel)})
    return {"wlaczona": WLACZONA, "narzut_min": NARZUT, "kurs_usd": KURS_USD_PLN,
            "premia_regionalna": PREMIA_REGIONALNA, "najnizsza_cena_kredytu": najnizsza_cena_kredytu(),
            "cennik": cennik(), "kalibracja": kalibracja(minimum=5), "kancelarie": kancelarie}


@router_admina.get("/sprzedaz")
def admin_sprzedaz(request: Request, miesiac: str = ""):
    """Oplacone pakiety (uzgodnienie sprzedazy): nabywca z rejestru kancelarii,
    nazwa pozycji, kwoty, numer faktury z Finance You (KSeF). `miesiac` = RRRR-MM."""
    import autoryzacja
    from decimal import Decimal
    autoryzacja._wymagaj_admina(request)
    miesiac = miesiac or _miesiac()
    wiersze = []
    for wpis in autoryzacja._wczytaj_rejestr().values():
        portfel = wczytaj_portfel(wpis["id"])
        for numer, z in ((portfel or {}).get("zamowienia") or {}).items():
            if z.get("status") not in ("oplacone", "zwrot") or not (z.get("oplacono") or "").startswith(miesiac):
                continue
            dane = wpis.get("dane") or {}
            wiersze.append({
                "zamowienie": numer, "transakcja_tpay": z.get("tytul"), "faktura": z.get("faktura"),
                "oplacono": z.get("oplacono"),
                "status": z["status"], "kancelaria": wpis["id"], "nabywca": wpis.get("nazwa"),
                "nip": dane.get("nip", ""), "adres": dane.get("adres", ""),
                "email": ", ".join(autoryzacja._wlasciciele(wpis)),
                "pozycja": tytul_faktury(float(z["kredyty"])), "netto": z["netto"],
                "vat": str(Decimal(z["brutto"]) - Decimal(z["netto"])), "brutto": z["brutto"],
                "adnotacja": ADNOTACJA_ZW if Decimal(z["brutto"]) == Decimal(z["netto"]) else ""})
    return {"miesiac": miesiac, "sprzedaz": sorted(wiersze, key=lambda w: w["oplacono"] or "")}
