"""Jakie programy stoja na komputerze notariusza i jak sie z nimi polaczyc.

Notariusz nie mowi nam, z jakiego programu kancelaryjnego korzysta, i nie
powinien musiec. Pomocnik zaglada do tego samego spisu, z ktorego Windows
buduje "Aplikacje i funkcje", wybiera z niego programy kancelaryjne i biurowe,
a dla kazdego sam ustala, ktora droga da sie z nim rozmawiac.

Drabinka metod, od najpewniejszej:

  baza    program trzyma dane w bazie, do ktorej jest sterownik ODBC albo plik
          bazy w katalogu programu. Najlepsza droga do CZYTANIA (repertorium,
          lista czynnosci) - tylko do odczytu, nigdy zapis obok programu.
  pliki   program ma katalog wymiany (eksport / import). Czytamy, co wyeksportuje.
  com     program wystawia automatyzacje COM (Word, Excel) - pewne sterowanie
          bez patrzenia na ekran.
  okna    Windows UI Automation - ten sam mechanizm, z ktorego korzystaja czytniki
          ekranu dla niewidomych. Dziala w kazdym zwyklym programie Windows, bez
          znajomosci jego kodu. To nasza droga uniwersalna.

Czego swiadomie nie ma: klikania "w punkt x,y" na zrzucie ekranu. W ksiedze
notarialnej zgadywanie wspolrzednych to roznica miedzy pomylka a jej brakiem,
ta sama zasada co w pomocnik/klikamy.py.

Prywatnosc: spis wychodzacy do notarai niesie nazwy programow, wydawcow
i nazwy metod. Nigdy nazw plikow, nazw zrodel ODBC (bywa w nich nazwisko
notariusza) ani sciezek z profilu uzytkownika.

Wszystko, co dotyka rejestru i dysku, jest wstrzykiwane, zeby dalo sie to
sprawdzic na Linuksie bez Windowsa.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath

log = logging.getLogger("notarai.pomocnik.programy")

# Po czym poznajemy program kancelaryjny. Nie znamy z gory wszystkich programow
# na rynku i nie musimy: wystarczy, ze nazwa albo wydawca o tym mowi. Notariusz
# moze tez wskazac program sam - wtedy kategoria nie ma znaczenia.
KANCELARYJNE = re.compile(r"notar|kancelari|repertor|rejent|akt[ay]? notar", re.I)
BIUROWE = re.compile(r"microsoft (office|word|excel|outlook)|microsoft 365|"
                     r"libreoffice|openoffice|wps office", re.I)
# Pomijamy to, co tylko zaszumia liste: aktualizacje, sterowniki, srodowiska.
SZUM = re.compile(r"update|aktualizac|redistributable|runtime|driver|sterownik|"
                  r"\.net|visual c\+\+|language pack|pakiet jezykowy|sdk", re.I)

ROZSZERZENIA_BAZ = {".mdb", ".accdb", ".fdb", ".gdb", ".db", ".sqlite", ".dbf", ".mdf"}
KATALOGI_WYMIANY = re.compile(r"^(eksport|export|import|wymiana|exchange|out|in)$", re.I)
# Gdzie programy biurowe maja automatyzacje COM. Dla programu kancelaryjnego
# ProgID-u nie zgadujemy - szukamy go w rejestrze po nazwie wydawcy.
COM_BIUROWE = {"word": ("Word.Application",), "excel": ("Excel.Application",),
               "outlook": ("Outlook.Application",),
               "office": ("Word.Application", "Excel.Application"),
               "microsoft 365": ("Word.Application", "Excel.Application"),
               "libreoffice": ("com.sun.star.ServiceManager",)}

METODY = ("baza", "pliki", "com", "okna")
# Kolejnosc zalezy od tego, co trzeba zrobic. Czytac najpewniej z bazy,
# dzialac najpewniej przez COM, a okna sa zawsze ostatnia, ale pewna deska.
KOLEJNOSC = {
    "odczyt": ("baza", "pliki", "com", "okna"),
    "praca": ("com", "okna"),
}
# Co pomocnik w tej wersji umie juz wykonac. Pozostale metody wykrywamy i
# pokazujemy, ale nie udajemy, ze dzialaja, dopoki nie przejda proby na zywo
# (docs/czeka-na-dostep.md).
WYKONYWALNE = ("okna",)


@dataclass
class Program:
    nazwa: str
    wydawca: str = ""
    wersja: str = ""
    katalog: str = ""          # zostaje na komputerze - nie wysylamy
    plik: str = ""             # glowny .exe - zostaje na komputerze
    kategoria: str = "inny"    # kancelaryjny | biurowy | inny
    metody: dict = field(default_factory=dict)   # metoda -> krotki opis bez danych

    @property
    def identyfikator(self) -> str:
        """Stala nazwa, po ktorej serwer wskazuje program. Bez sciezek."""
        return re.sub(r"[^a-z0-9]+", "-", self.nazwa.lower()).strip("-")[:60]

    @property
    def proces(self) -> str:
        # Sciezki sa windowsowe nawet wtedy, gdy logike sprawdzamy na Linuksie.
        return PureWindowsPath(self.plik).name.lower() if self.plik else ""

    def publiczny(self) -> dict:
        """To, co wolno wyslac do notarai."""
        return {
            "id": self.identyfikator,
            "nazwa": self.nazwa[:120],
            "wydawca": self.wydawca[:120],
            "wersja": self.wersja[:40],
            "kategoria": self.kategoria,
            "metody": {m: self.metody[m] for m in METODY if m in self.metody},
            "zalecana": {cel: wybierz_metode(self, cel)[0] for cel in KOLEJNOSC},
        }


# --- rejestr Windows -------------------------------------------------------

_KLUCZE_ODINSTALOWANIA = (
    r"Software\Microsoft\Windows\CurrentVersion\Uninstall",
    r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
)


def _winreg():  # pragma: no cover - tylko Windows
    import winreg
    return winreg


def wpisy_odinstalowania(winreg=None) -> list[dict]:  # pragma: no cover - tylko Windows
    """Surowe wpisy "Aplikacje i funkcje" z HKLM i HKCU."""
    winreg = winreg or _winreg()
    wynik = []
    for galaz in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for sciezka in _KLUCZE_ODINSTALOWANIA:
            try:
                klucz = winreg.OpenKey(galaz, sciezka)
            except OSError:
                continue
            with klucz:
                for i in range(winreg.QueryInfoKey(klucz)[0]):
                    try:
                        with winreg.OpenKey(klucz, winreg.EnumKey(klucz, i)) as podklucz:
                            wpis = {}
                            for nazwa in ("DisplayName", "Publisher", "DisplayVersion",
                                          "InstallLocation", "DisplayIcon", "SystemComponent"):
                                try:
                                    wpis[nazwa] = winreg.QueryValueEx(podklucz, nazwa)[0]
                                except OSError:
                                    pass
                            wynik.append(wpis)
                    except OSError:
                        continue
    return wynik


def sterowniki_odbc(winreg=None) -> list[dict]:  # pragma: no cover - tylko Windows
    """Zrodla danych ODBC: [{"zrodlo": nazwa, "sterownik": nazwa sterownika}].

    Nazwa zrodla zostaje na komputerze (patrz naglowek) - sluzy tylko do
    dopasowania do programu.
    """
    winreg = winreg or _winreg()
    wynik = []
    for galaz in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            klucz = winreg.OpenKey(galaz, r"Software\ODBC\ODBC.INI\ODBC Data Sources")
        except OSError:
            continue
        with klucz:
            for i in range(winreg.QueryInfoKey(klucz)[1]):
                try:
                    zrodlo, sterownik, _ = winreg.EnumValue(klucz, i)
                    wynik.append({"zrodlo": str(zrodlo), "sterownik": str(sterownik)})
                except OSError:
                    continue
    return wynik


def progid_com(winreg=None, limit: int = 20000) -> list[str]:  # pragma: no cover
    """ProgID-y zarejestrowanych serwerow automatyzacji ("Firma.Aplikacja")."""
    winreg = winreg or _winreg()
    wynik = []
    try:
        klucz = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "")
    except OSError:
        return wynik
    with klucz:
        for i in range(min(winreg.QueryInfoKey(klucz)[0], limit)):
            try:
                nazwa = winreg.EnumKey(klucz, i)
            except OSError:
                break
            if "." not in nazwa or nazwa.startswith("."):
                continue
            try:
                with winreg.OpenKey(klucz, nazwa + r"\CLSID"):
                    wynik.append(nazwa)
            except OSError:
                continue
    return wynik


# --- czysta logika (testowana na kazdym systemie) ---------------------------

def kategoria(nazwa: str, wydawca: str = "") -> str:
    tekst = f"{nazwa} {wydawca}"
    if KANCELARYJNE.search(tekst):
        return "kancelaryjny"
    if BIUROWE.search(tekst):
        return "biurowy"
    return "inny"


def _plik_z_ikony(ikona: str) -> str:
    """DisplayIcon bywa postaci '"C:\\...\\prog.exe",0'. Wyciagamy sama sciezke."""
    sciezka = (ikona or "").split(",")[0].strip().strip('"')
    return sciezka if sciezka.lower().endswith(".exe") else ""


def glowny_plik(katalog: str, ikona: str = "", istnieje=os.path.isfile,
                pliki_exe=None) -> str:
    """Najbardziej prawdopodobny glowny .exe programu.

    Najpierw ikona z wpisu (instalator wskazuje nia zwykle program, nie
    deinstalator), potem najwiekszy .exe w katalogu, ktory nie jest
    deinstalatorem ani aktualizatorem.
    """
    z_ikony = _plik_z_ikony(ikona)
    if z_ikony and istnieje(z_ikony) and not re.search(r"unins|uninst|setup|update",
                                                        PureWindowsPath(z_ikony).name, re.I):
        return z_ikony
    if not katalog:
        return ""
    if pliki_exe is None:
        def pliki_exe(k):
            try:
                return [(str(p), p.stat().st_size) for p in Path(k).glob("*.exe")]
            except OSError:
                return []
    kandydaci = [(s, r) for s, r in pliki_exe(katalog)
                 if not re.search(r"unins|uninst|setup|update|crash|report|helper",
                                  PureWindowsPath(s).name, re.I)]
    return max(kandydaci, key=lambda k: k[1])[0] if kandydaci else ""


def _slowa(program: Program) -> set[str]:
    """Slowa, po ktorych laczymy program ze zrodlem ODBC albo ProgID-em."""
    tekst = f"{program.nazwa} {program.wydawca}".lower()
    pomijane = {"sp", "z", "o", "oo", "s", "a", "spolka", "the", "inc", "ltd", "gmbh",
                "wersja", "version", "program", "system", "for", "dla", "pro"}
    return {s for s in re.findall(r"[a-ząćęłńóśźż0-9]{3,}", tekst) if s not in pomijane}


def wykryj_metody(program: Program, odbc: list[dict], progid: list[str],
                  zawartosc_katalogu=None) -> dict:
    """Ktore metody sa dostepne dla tego programu. Opisy bez nazw i sciezek."""
    metody: dict[str, str] = {}
    slowa = _slowa(program)

    # baza: zrodlo ODBC o nazwie albo sterowniku pasujacym do programu,
    # albo plik bazy w katalogu programu
    pasujace = [o for o in odbc
                if slowa & set(re.findall(r"[a-ząćęłńóśźż0-9]{3,}",
                                          f"{o.get('zrodlo', '')} {o.get('sterownik', '')}".lower()))]
    pliki: list[str] = []
    katalogi: list[str] = []
    if program.katalog and zawartosc_katalogu is not None:
        pliki, katalogi = zawartosc_katalogu(program.katalog)
    bazy = sorted({Path(p).suffix.lower() for p in pliki
                   if Path(p).suffix.lower() in ROZSZERZENIA_BAZ})
    if pasujace:
        sterowniki = sorted({o.get("sterownik", "") for o in pasujace if o.get("sterownik")})
        metody["baza"] = "ODBC: " + (", ".join(sterowniki)[:120] or "sterownik bez nazwy")
    elif bazy:
        metody["baza"] = "plik bazy w katalogu programu (" + ", ".join(bazy) + ")"

    wymiana = sorted({k.lower() for k in katalogi if KATALOGI_WYMIANY.match(k)})
    if wymiana:
        metody["pliki"] = "katalog wymiany: " + ", ".join(wymiana)

    nazwa = program.nazwa.lower()
    for klucz, znane in COM_BIUROWE.items():
        obecne = [p for p in znane if p in progid]
        if klucz in nazwa and obecne:
            metody["com"] = ", ".join(obecne)
            break
    else:
        wlasne = [p for p in progid if p.split(".")[0].lower() in slowa]
        if wlasne:
            metody["com"] = ", ".join(sorted(wlasne)[:3])

    if program.plik:
        metody["okna"] = "Windows UI Automation"
    return metody


def wybierz_metode(program: Program, cel: str = "praca") -> tuple[str, str]:
    """(metoda, uzasadnienie). Najlepsza dostepna, ktora pomocnik umie wykonac.

    Gdy lepsza metoda jest wykryta, ale jeszcze niewykonywalna, mowimy o tym
    wprost - notariusz i my wiemy wtedy, co da sie usprawnic po probie na zywo.
    """
    kolejnosc = KOLEJNOSC.get(cel, KOLEJNOSC["praca"])
    dostepne = [m for m in kolejnosc if m in program.metody]
    if not dostepne:
        return "", "Nie znalazlem zadnej drogi do tego programu. Czy jest zainstalowany?"
    wykonywalne = [m for m in dostepne if m in WYKONYWALNE]
    if not wykonywalne:
        return "", (f"Program da sie polaczyc przez: {', '.join(dostepne)}, ale tej "
                    "drogi pomocnik jeszcze nie obsluguje.")
    wybrana = wykonywalne[0]
    lepsze = dostepne[:dostepne.index(wybrana)]
    if lepsze:
        return wybrana, (f"Pracuje przez {wybrana}. Wykrylem tez {', '.join(lepsze)} - "
                         "pewniejsza droge, ktora wlaczymy po probie na zywo.")
    return wybrana, f"Pracuje przez {wybrana}."


def z_wpisow(wpisy: list[dict], odbc: list[dict], progid: list[str],
             zawartosc_katalogu=None, istnieje=os.path.isfile, pliki_exe=None,
             tylko_istotne: bool = True) -> list[Program]:
    """Buduje liste programow z surowych wpisow rejestru."""
    widziane: set[str] = set()
    programy: list[Program] = []
    for wpis in wpisy:
        nazwa = str(wpis.get("DisplayName") or "").strip()
        if not nazwa or wpis.get("SystemComponent") == 1 or SZUM.search(nazwa):
            continue
        wydawca = str(wpis.get("Publisher") or "").strip()
        rodzaj = kategoria(nazwa, wydawca)
        if tylko_istotne and rodzaj == "inny":
            continue
        program = Program(
            nazwa=nazwa, wydawca=wydawca, wersja=str(wpis.get("DisplayVersion") or ""),
            katalog=str(wpis.get("InstallLocation") or "").strip().strip('"'),
            kategoria=rodzaj,
        )
        if program.identyfikator in widziane:
            continue
        widziane.add(program.identyfikator)
        program.plik = glowny_plik(program.katalog, str(wpis.get("DisplayIcon") or ""),
                                   istnieje=istnieje, pliki_exe=pliki_exe)
        program.metody = wykryj_metody(program, odbc, progid, zawartosc_katalogu)
        programy.append(program)
    # Kancelaryjne na gorze - to po nie notariusz przychodzi.
    programy.sort(key=lambda p: (p.kategoria != "kancelaryjny", p.nazwa.lower()))
    return programy


def _zawartosc(katalog: str, glebokosc: int = 2, limit: int = 2000) -> tuple[list[str], list[str]]:
    """Pliki i nazwy podkatalogow programu - plytko, z limitem."""
    pliki: list[str] = []
    katalogi: list[str] = []
    baza = Path(katalog)
    try:
        for korzen, podkatalogi, nazwy in os.walk(baza):
            poziom = len(Path(korzen).relative_to(baza).parts)
            katalogi.extend(podkatalogi)
            pliki.extend(nazwy)
            if poziom >= glebokosc:
                podkatalogi.clear()
            if len(pliki) > limit:
                break
    except (OSError, ValueError):
        pass
    return pliki, katalogi


def rozpoznaj(tylko_istotne: bool = True) -> list[Program]:  # pragma: no cover - Windows
    """Pelne rozpoznanie na tym komputerze."""
    if os.name != "nt":
        return []
    programy = z_wpisow(wpisy_odinstalowania(), sterowniki_odbc(), progid_com(),
                        zawartosc_katalogu=_zawartosc, tylko_istotne=tylko_istotne)
    log.info("programy: rozpoznano=%d kancelaryjnych=%d", len(programy),
             sum(p.kategoria == "kancelaryjny" for p in programy))
    return programy


def znajdz(programy: list[Program], identyfikator: str) -> Program | None:
    return next((p for p in programy if p.identyfikator == identyfikator), None)
