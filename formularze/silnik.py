import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import yaml

log = logging.getLogger("pieczapp.formularze")

KATALOG = Path(__file__).parent
PORT_CDP = 9222

TRANSFORMACJE = {
    "": lambda w: w,
    "cyfry": lambda w: re.sub(r"\D", "", w),
    "wielkie": lambda w: w.upper(),
    "bez_spacji": lambda w: re.sub(r"\s+", "", w),
    "kw_bez_ukosnikow": lambda w: re.sub(r"[\s/]", "", w).upper(),
}


class BladMapowania(ValueError):
    pass


@dataclass
class PoleFormularza:
    nazwa: str          # nazwa w systemie urzedowym (dla czlowieka)
    zrodlo: str         # nazwa pola sprawy w pieczapp, np. "ggg: nr kw"
    selektor: str       # CSS/XPath elementu w przegladarce
    typ: str = "tekst"  # tekst | lista | pole_wyboru
    transformacja: str = ""
    wymagane: bool = False
    # Opis dla czlowieka i dla modelu: co dokladnie ma tu trafic. Przy
    # dobieraniu wartosci z tresci aktu to on rozstrzyga, ktora z dwoch
    # pasujacych danych wybrac (np. PESEL zbywcy, a nie nabywcy).
    opis: str = ""


@dataclass
class Mapowanie:
    system: str
    opis: str
    adres: str                       # prefiks URL - strona musi sie zgadzac, inaczej stop
    status: str                      # szkic | gotowe
    gotowosc: str                    # selektor elementu, ktory musi istniec (strona zaladowana)
    przycisk_wysylki: str            # selektor - NIGDY nie klikany; sluzy do kontroli
    pola: list[PoleFormularza]
    uwagi: str = ""

    def __post_init__(self):
        if self.status not in ("szkic", "gotowe"):
            raise BladMapowania(f"{self.system}: status musi byc 'szkic' albo 'gotowe'")
        for pole in self.pola:
            if pole.transformacja not in TRANSFORMACJE:
                raise BladMapowania(f"{self.system}: nieznana transformacja {pole.transformacja!r}")
            if pole.selektor.strip() == self.przycisk_wysylki.strip():
                raise BladMapowania(f"{self.system}: pole {pole.nazwa!r} wskazuje na przycisk wysylki")


@dataclass
class Krok:
    pole: str
    selektor: str
    typ: str
    wartosc: str | None
    wykonano: bool = False
    uwaga: str = ""


@dataclass
class Raport:
    system: str
    tryb: str
    kroki: list[Krok] = field(default_factory=list)
    zatrzymano_przed: str = ""
    bledy: list[str] = field(default_factory=list)

    @property
    def do_wpisania(self) -> int:
        return sum(1 for k in self.kroki if k.wartosc not in (None, ""))

    @property
    def brakujace(self) -> list[str]:
        return [k.pole for k in self.kroki if k.wartosc in (None, "")]


def dostepne_systemy() -> list[dict]:
    wynik = []
    for plik in sorted(KATALOG.glob("*.yaml")):
        try:
            m = wczytaj_mapowanie(plik.stem)
            wynik.append({"system": m.system, "opis": m.opis, "status": m.status, "pol": len(m.pola)})
        except BladMapowania as blad:
            wynik.append({"system": plik.stem, "opis": "", "status": "blad", "blad": str(blad)})
    return wynik


def wczytaj_mapowanie(system: str) -> Mapowanie:
    if not re.fullmatch(r"[a-z0-9_]+", system):
        raise BladMapowania("Nieprawidlowa nazwa systemu")
    plik = KATALOG / f"{system}.yaml"
    if not plik.exists():
        raise BladMapowania(f"Brak mapowania: {plik.name}")
    surowe = yaml.safe_load(plik.read_text("utf-8")) or {}
    try:
        pola = [PoleFormularza(**p) for p in surowe.pop("pola", [])]
        return Mapowanie(pola=pola, **surowe)
    except TypeError as blad:
        raise BladMapowania(f"{plik.name}: {blad}") from blad


def zaplanuj(mapowanie: Mapowanie, dane: dict[str, str | None]) -> Raport:
    """Tryb podgladu: co by zostalo wpisane. Nie dotyka przegladarki."""
    raport = Raport(system=mapowanie.system, tryb="podglad",
                    zatrzymano_przed=mapowanie.przycisk_wysylki)
    for pole in mapowanie.pola:
        surowa = dane.get(pole.zrodlo)
        wartosc = TRANSFORMACJE[pole.transformacja](str(surowa)) if surowa not in (None, "") else None
        uwaga = "BRAK w sprawie" if wartosc is None and pole.wymagane else ""
        raport.kroki.append(Krok(pole.nazwa, pole.selektor, pole.typ, wartosc, uwaga=uwaga))
    return raport


class Strona(Protocol):
    """Minimalny interfejs strony - Playwright albo atrapa w testach."""
    url: str
    def istnieje(self, selektor: str) -> bool: ...
    def wpisz(self, selektor: str, wartosc: str) -> None: ...
    def wybierz(self, selektor: str, wartosc: str) -> None: ...
    def zaznacz(self, selektor: str, tak: bool) -> None: ...


def wypelnij(mapowanie: Mapowanie, dane: dict, strona: Strona, tryb: str = "podglad") -> Raport:
    """Wypelnia pola na JUZ otwartej, zalogowanej stronie. Nigdy nie wysyla."""
    raport = zaplanuj(mapowanie, dane)
    raport.tryb = tryb
    if tryb != "faktyczny":
        return raport
    if mapowanie.status != "gotowe":
        raport.bledy.append("Mapowanie ma status 'szkic' - tryb faktyczny zablokowany")
        return raport
    if not strona.url.startswith(mapowanie.adres):
        raport.bledy.append("Otwarta strona nie jest formularzem tego systemu")
        return raport
    if not strona.istnieje(mapowanie.gotowosc):
        raport.bledy.append("Formularz nie jest gotowy (brak oczekiwanego elementu)")
        return raport

    for krok in raport.kroki:
        if krok.wartosc is None:
            continue
        if krok.selektor.strip() == mapowanie.przycisk_wysylki.strip():
            raise RuntimeError("Odmowa: proba dzialania na przycisku wysylki")
        try:
            if krok.typ == "tekst":
                strona.wpisz(krok.selektor, krok.wartosc)
            elif krok.typ == "lista":
                strona.wybierz(krok.selektor, krok.wartosc)
            elif krok.typ == "pole_wyboru":
                strona.zaznacz(krok.selektor, krok.wartosc.lower() in ("tak", "true", "1"))
            else:
                raise BladMapowania(f"Nieznany typ pola: {krok.typ}")
            krok.wykonano = True
        except Exception as blad:  # noqa: BLE001 - raport, nie wyjatek; bez tresci danych
            krok.uwaga = f"blad: {type(blad).__name__}"
            raport.bledy.append(f"{krok.pole}: {type(blad).__name__}")

    log.info("formularz %s: wpisano %d/%d pol, bledy=%d, zatrzymano przed wysylka",
             mapowanie.system, sum(k.wykonano for k in raport.kroki), len(raport.kroki), len(raport.bledy))
    return raport


class StronaPlaywright:
    """Adapter na strone Playwright. Podlaczenie do przegladarki uruchomionej
    przez notariusza z --remote-debugging-port (patrz uruchom_przegladarke.bat)."""

    def __init__(self, page):
        self._p = page

    @property
    def url(self) -> str:
        return self._p.url

    def istnieje(self, selektor: str) -> bool:
        return self._p.locator(selektor).count() > 0

    def wpisz(self, selektor: str, wartosc: str) -> None:
        self._p.locator(selektor).first.fill(wartosc)

    def wybierz(self, selektor: str, wartosc: str) -> None:
        self._p.locator(selektor).first.select_option(label=wartosc)

    def zaznacz(self, selektor: str, tak: bool) -> None:
        self._p.locator(selektor).first.set_checked(tak)


def _sciezka_przegladarki() -> str | None:
    import os
    import shutil
    kandydaci = [
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Microsoft", "Edge", "Application", "msedge.exe"),
    ]
    for k in kandydaci:
        if os.path.exists(k):
            return k
    return shutil.which("chrome") or shutil.which("chromium") or shutil.which("msedge") or shutil.which("google-chrome")


def czy_mozna_sterowac() -> bool:
    """Czy ta instalacja ma czym sterowac.

    W kancelarii pieczapp dziala na komputerze notariusza i ma jego Chrome.
    W chmurze notarai dziala w kontenerze, gdzie zadnej przegladarki nie ma i
    nie bedzie - tam wpisywanie przejmuje pomocnik na komputerze notariusza.
    Bez tego sprawdzenia serwer probowal uruchomic przegladarke u siebie i
    odpowiadal notariuszowi "zainstaluj Chrome", co bylo mylace: Chrome ma,
    tylko nie tam.
    """
    return bool(_sciezka_przegladarki())


def uruchom_przegladarke(port: int = PORT_CDP) -> None:
    """Startuje osobna przegladarke z profilem pieczapp i portem CDP na localhost.

    Odpowiednik uruchom_przegladarke.bat, ale z aplikacji - zeby jeden przycisk
    wystarczyl. Profil jest osobny, wiec nie miesza sie z prywatnym Chrome.
    """
    import os
    import subprocess

    exe = _sciezka_przegladarki()
    if not exe:
        raise RuntimeError("Nie znaleziono Chrome ani Edge. Zainstaluj jedna z tych przegladarek.")
    profil = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "pieczapp", "przegladarka")
    os.makedirs(profil, exist_ok=True)
    flagi = [exe, f"--remote-debugging-port={port}", "--remote-debugging-address=127.0.0.1",
             f"--user-data-dir={profil}", "--no-first-run", "--no-default-browser-check", "about:blank"]
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(flagi, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kwargs)
    log.info("uruchomiono przegladarke do formularzy")


def aktywna_strona(port: int = PORT_CDP, uruchom: bool = True):
    """Zwraca (playwright, strona). Gdy przegladarka nie dziala, uruchamia ja."""
    import time
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    przegladarka = None
    for proba in range(20):
        try:
            przegladarka = pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}", timeout=3000)
            break
        except Exception:  # noqa: BLE001
            if proba == 0 and uruchom:
                try:
                    uruchom_przegladarke(port)
                except RuntimeError as blad:
                    pw.stop()
                    raise
            time.sleep(1)
    if przegladarka is None:
        pw.stop()
        raise RuntimeError(
            "Nie udalo sie uruchomic przegladarki do formularzy. "
            "Sprobuj recznie: uruchom_przegladarke.bat"
        )
    konteksty = przegladarka.contexts
    strony = [s for k in konteksty for s in k.pages]
    if not strony:
        kontekst = konteksty[0] if konteksty else przegladarka.new_context()
        strony = [kontekst.new_page()]
    return pw, StronaPlaywright(strony[-1])
