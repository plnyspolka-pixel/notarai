"""Klikamy na pulpicie: model prowadzi program kancelaryjny Windows (np. Rejent).

To ta sama petla co w przegladarce (pomocnik/klikamy.py), tylko zamiast strony
jest okno programu, a reka pomocnika jest winapp CLI Microsoftu
(`winapp ui inspect/invoke/set-value`, UI Automation). Klasa OknoProgramu ma
ten sam ksztalt co strona z cdp.py, wiec silnik Klikamy i jego blokady
(podpis, platnosci, usuwanie, wysylka tylko za jednorazowa zgoda) dzialaja tu
bez zmian. Ponizej dochodza blokady wlasciwe dla pulpitu:

  - pomocnik steruje wylacznie programem, na ktory notariusz zgodzil sie na tym
    komputerze (pomocnik.json: programy_pulpitu); serwer nie moze tej listy
    poszerzyc,
  - powloki, przegladarki, poczta, menedzery hasel, programy do podpisu
    i narzedzia systemu sa zakazane zawsze, nawet z listy notariusza,
  - program rozpoznajemy po nazwie procesu i dalej celujemy w jego PID, a nie
    w tytul okna - inaczej okno przegladarki zatytulowane "Rejent" mogloby
    udawac program,
  - kazde klikniecie i wpis celuje w konkretne okno (-w) i typ kontrolki
    (--type), wiec winapp nie przeskoczy do innego okna ani do rodzica,
  - przycisk o nic nie mowiacej nazwie ("OK", "Tak") oceniamy razem z trescia
    okna dialogowego, w ktorym siedzi: "Tak" pod pytaniem "Usunac akt?" to
    usuniecie,
  - nieodwracalne czynnosci programu (zamkniecie roku, przywrocenie kopii,
    nadpisanie bazy) sa zakazane na pulpicie zawsze,
  - do pola hasla (IsPassword) nie wpisujemy nic; gdy nie da sie tego sprawdzic,
    tez nie wpisujemy,
  - telemetria winapp jest wylaczona przy kazdym wywolaniu.

Do logow trafiaja nazwy polecen winapp i kody bledow. Nigdy nazwy elementow,
wartosci pol ani tytuly okien - w programie kancelaryjnym to dane stron.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path

from pomocnik.klikamy import OdmowaKlikniecia

log = logging.getLogger("notarai.pomocnik.pulpit")

PREFIKS_ADRESU = "pulpit://"
CZAS_WINAPP_S = 30
GLEBOKOSC = 12          # okna programow kancelaryjnych bywaja gleboko zagniezdzone
MAKS_ELEMENTOW = 150
MAKS_TEKSTU = 6000
MAKS_KONTEKSTU = 800
MAKS_WPISU = 2000
KLUCZ_USTAWIEN = "programy_pulpitu"

# Programy, ktorymi pomocnik nie steruje nigdy. Powloka albo eksplorator to
# klucze do calego komputera, przegladarka ma osobna, pilnowana droge (cdp.py),
# poczta wysyla w swiat, a podpis i hasla sa wylacznie reka notariusza.
ZAKAZANE_PROGRAMY = frozenset({
    # system i powloki
    "cmd", "powershell", "powershell_ise", "pwsh", "windowsterminal", "wt",
    "conhost", "openconsole", "explorer", "regedit", "taskmgr", "mmc", "msiexec",
    "control", "systemsettings", "rundll32", "wscript", "cscript", "mstsc",
    "notarai-pomocnik", "winapp", "python", "pythonw",
    # przegladarki - maja wlasna droge przez cdp.py
    "chrome", "msedge", "firefox", "opera", "brave", "iexplore", "vivaldi",
    # poczta i komunikatory
    "outlook", "olk", "thunderbird", "hxoutlook", "teams", "ms-teams", "slack",
    # hasla
    "keepass", "keepassxc", "1password", "bitwarden",
    # podpis kwalifikowany i karty
    "szafir", "szafirhost", "procertumcardmanager", "procertumsmartsign",
    "cryptocardmanager", "sigillum", "sigillumsign", "cencert", "eurocert",
})

# Czynnosci programu kancelaryjnego, ktorych nie cofnie zadne "Anuluj".
ZABRONIONE_PULPIT = re.compile(
    r"zamkni[ęe]\w*\s+(roku|ksi[ąa]g|ksi[ęe]g|okresu|repertorium)|"
    r"zamknij\s+(rok|ksi[ęe]g|okres|repertorium|program)|"
    r"przywr[óo][ćc]|odtw[óo]rz|nadpisz|odinstaluj|formatuj|"
    r"wyczy[śs][ćc]\s+baz|kopi[aęei]\s+zapasow|backup|restore|overwrite|uninstall|"
    r"wyj[śs]cie\b|\bexit\b",
    re.I,
)

# Nazwy, ktore same nic nie mowia - o skutku decyduje okno, w ktorym sa.
GENERYCZNE = re.compile(
    r"^\s*(ok|tak|yes|dalej|kontynuuj|zastosuj|wykonaj|start|uruchom|"
    r"potwierd[zź]|gotowe|next|continue|apply|run|go)?\s*[.!>]*\s*$",
    re.I,
)

# Kontrolki, na ktorych model moze dzialac, nawet gdy winapp nie oznaczy ich
# jako isInvokable/isEditable.
TYPY_DZIALAN = frozenset({
    "Button", "SplitButton", "Edit", "ComboBox", "CheckBox", "RadioButton",
    "MenuItem", "TabItem", "ListItem", "TreeItem", "Hyperlink", "DataItem",
    "Spinner", "Slider", "Document",
})
TYPY_TEKSTU = frozenset({"Text", "StatusBar", "Header", "HeaderItem"})

OPISY_BLEDOW = {
    "brak_winapp": "Na tym komputerze nie ma winapp CLI, wiec nie mam czym "
                   "sterowac programem. Zainstaluj winapp i uruchom pomocnika ponownie.",
    "timeout": "Program nie odpowiedzial na czas.",
    "zla_odpowiedz": "Nie zrozumialem odpowiedzi winapp.",
    "element_not_found": "Element zniknal albo sie zmienil. Odczytam okno jeszcze raz.",
    "ambiguous_selector": "W oknie jest kilka takich samych elementow.",
    "no_target": "Nie znalazlem okna programu.",
}


class BladWinapp(RuntimeError):
    """winapp nie wykonal polecenia.

    Tresc to wylacznie kod i opis po ludzku. Komunikat winapp potrafi zawierac
    nazwe elementu albo tytul okna, czyli dane stron - tego tu nie przenosimy.
    """

    def __init__(self, kod: str):
        self.kod = kod
        super().__init__(OPISY_BLEDOW.get(kod, f"winapp zglosil blad ({kod})."))


class OdmowaPulpitu(OdmowaKlikniecia):
    """Pomocnik nie podejmie sie tego programu albo tej czynnosci."""


# --- ustawienia na komputerze notariusza --------------------------------------


def _plik_ustawien() -> Path:
    from pomocnik.okno import plik_ustawien  # okno importuje zadania, a te nas
    return plik_ustawien()


def nazwa_programu(nazwa: str) -> str:
    """Nazwa procesu bez '.exe', malymi literami. Pusty napis, gdy niepoprawna."""
    czysta = (nazwa or "").strip().lower()
    if czysta.endswith(".exe"):
        czysta = czysta[:-4]
    return czysta if re.fullmatch(r"[a-z0-9][a-z0-9 ._-]{0,59}", czysta) else ""


def _wczytaj(plik: Path) -> dict:
    try:
        dane = json.loads(plik.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return dane if isinstance(dane, dict) else {}


def dozwolone_programy(plik: Path | None = None) -> set[str]:
    """Programy, na ktore notariusz zgodzil sie na tym komputerze."""
    dane = _wczytaj(plik or _plik_ustawien())
    lista = dane.get(KLUCZ_USTAWIEN) or []
    return {n for n in (nazwa_programu(str(p)) for p in lista if isinstance(p, str)) if n}


def zezwol_na_program(nazwa: str, plik: Path | None = None) -> str:
    """Dopisuje program do listy tego komputera. Zakazanych nie dopisze nigdy."""
    czysta = nazwa_programu(nazwa)
    if not czysta:
        raise ValueError("Podaj nazwe procesu programu, np. Rejent albo Rejent.exe.")
    if czysta in ZAKAZANE_PROGRAMY:
        raise ValueError("Tym programem pomocnik nie steruje.")
    plik = plik or _plik_ustawien()
    dane = _wczytaj(plik)
    obecne = dozwolone_programy(plik)
    dane[KLUCZ_USTAWIEN] = sorted(obecne | {czysta})
    plik.write_text(json.dumps(dane, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("pulpit: dopisano program do dozwolonych (razem %d)", len(dane[KLUCZ_USTAWIEN]))
    return czysta


def cofnij_zgode(nazwa: str, plik: Path | None = None) -> None:
    plik = plik or _plik_ustawien()
    dane = _wczytaj(plik)
    dane[KLUCZ_USTAWIEN] = sorted(dozwolone_programy(plik) - {nazwa_programu(nazwa)})
    plik.write_text(json.dumps(dane, ensure_ascii=False, indent=2), encoding="utf-8")


def sprawdz_program(nazwa: str, dozwolone: set[str]) -> str:
    czysta = nazwa_programu(nazwa)
    if not czysta:
        raise OdmowaPulpitu("Zlecenie nie mowi, ktorym programem sterowac.")
    if czysta in ZAKAZANE_PROGRAMY:
        raise OdmowaPulpitu("Tym programem pomocnik nie steruje - to droga do calego "
                            "komputera, poczty albo podpisu.")
    if czysta not in dozwolone:
        raise OdmowaPulpitu(
            f"Na tym komputerze nie zezwolono na sterowanie programem {czysta}. "
            "Zgode daje notariusz przy tym komputerze, nie zdalnie."
        )
    return czysta


# --- winapp CLI ---------------------------------------------------------------


def _architektura() -> str:
    import platform
    return "win-arm64" if platform.machine().lower() in ("arm64", "aarch64") else "win-x64"


def _tylko_exe(sciezka: str | Path | None) -> str | None:
    """Wolno uruchomic wylacznie winapp.exe, nigdy nakladke .cmd/.bat/.ps1.

    Nakladka z npm przepuszcza argumenty przez cmd.exe, a w argumentach jest
    tekst wpisywany do programu - "&" albo "%" w nazwisku stalyby sie
    poleceniem. Dla nakladki szukamy prawdziwego pliku obok, w node_modules.
    """
    if not sciezka:
        return None
    plik = Path(sciezka)
    if plik.suffix.lower() == ".exe" and plik.is_file():
        return str(plik)
    if plik.suffix.lower() in (".cmd", ".bat", ".ps1", ""):
        prawdziwy = (plik.parent / "node_modules" / "@microsoft" / "winappcli" / "bin"
                     / _architektura() / "winapp.exe")
        if prawdziwy.is_file():
            return str(prawdziwy)
    log.warning("pulpit: pominieto winapp, ktory nie jest plikiem .exe")
    return None


def znajdz_winapp() -> str | None:
    """NOTARAI_WINAPP, kopia obok pomocnika, a na koncu winapp z PATH."""
    kandydaci = [
        os.environ.get("NOTARAI_WINAPP", ""),
        Path(os.environ.get("LOCALAPPDATA", Path.home())) / "notarai" / "winapp" / "winapp.exe",
        shutil.which("winapp"),
    ]
    for kandydat in kandydaci:
        if kandydat and Path(kandydat).exists():
            exe = _tylko_exe(kandydat)
            if exe:
                return exe
    return None


def _dekoduj(dane: bytes | str | None) -> str:
    """winapp pisze UTF-8; gdyby konsola podsunela strone kodowa, czytamy cp1250.

    Zle odczytana nazwa przycisku konczy sie znakiem zastepczym, a takiego
    przycisku nie klikamy (OknoProgramu.kliknij) - "Usu?" nie moze przejsc
    jako cos niewinnego.
    """
    if dane is None:
        return ""
    if isinstance(dane, str):
        return dane
    try:
        return dane.decode("utf-8-sig")
    except UnicodeDecodeError:
        return dane.decode("cp1250", errors="replace")


def _kod_bledu(stderr: str) -> str:
    dopasowanie = re.search(r"\{.*\}", stderr or "", re.S)
    if not dopasowanie:
        return ""
    try:
        blad = json.loads(dopasowanie.group(0)).get("error") or {}
    except (ValueError, AttributeError):
        return ""
    kod = str(blad.get("code", "")) if isinstance(blad, dict) else ""
    return kod if re.fullmatch(r"[a-z0-9_]{1,60}", kod) else ""


class Winapp:
    """Wywolania `winapp ui ... --json`.

    Argumenty zawsze lista (bez powloki), a selektor i wartosc za `--`, zeby
    wpisywany tekst zaczynajacy sie od minusa nie zostal wziety za opcje.
    """

    def __init__(self, sciezka: str | None = None, uruchom=subprocess.run,
                 czas_s: int = CZAS_WINAPP_S, przebieg: str | None = None):
        self.sciezka = sciezka if sciezka is not None else znajdz_winapp()
        self._uruchom = uruchom
        self.czas_s = czas_s
        # Wspolny identyfikator trzyma pulpit dla nas miedzy kolejnymi krokami.
        self.przebieg = przebieg or f"notarai-pomocnik-{uuid.uuid4().hex[:12]}"

    def __call__(self, polecenie: str, *opcje: str, pozycyjne: tuple = ()) -> dict:
        if not self.sciezka:
            raise BladWinapp("brak_winapp")
        argumenty = [self.sciezka, "ui", polecenie, *map(str, opcje), "--json"]
        if pozycyjne:
            argumenty += ["--", *map(str, pozycyjne)]
        srodowisko = dict(os.environ)
        srodowisko["WINAPP_CLI_TELEMETRY_OPTOUT"] = "1"
        srodowisko["WINAPP_UI_WORKFLOW_ID"] = self.przebieg
        try:
            wynik = self._uruchom(
                argumenty, capture_output=True, timeout=self.czas_s, env=srodowisko,
                stdin=subprocess.DEVNULL, check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except FileNotFoundError:
            raise BladWinapp("brak_winapp") from None
        except subprocess.TimeoutExpired:
            log.warning("winapp ui %s: przekroczony czas", polecenie)
            raise BladWinapp("timeout") from None

        wyjscie = _dekoduj(wynik.stdout)
        if wynik.returncode != 0:
            # search i wait-for przy braku trafienia koncza sie kodem 1, ale
            # z pelna odpowiedzia na stdout - to wynik, nie blad.
            if wynik.returncode == 1 and polecenie in ("search", "wait-for") and wyjscie.strip():
                try:
                    return json.loads(wyjscie)
                except ValueError:
                    pass
            kod = _kod_bledu(_dekoduj(wynik.stderr)) or f"kod_{wynik.returncode}"
            log.warning("winapp ui %s: %s", polecenie, kod)
            raise BladWinapp(kod)
        try:
            dane = json.loads(wyjscie or "{}")
        except ValueError:
            log.warning("winapp ui %s: odpowiedz nie jest JSON-em", polecenie)
            raise BladWinapp("zla_odpowiedz") from None
        return dane if isinstance(dane, dict) else {}


# --- okno programu w ksztalcie strony dla Klikamy -----------------------------


def _selektor(hwnd, typ: str, selektor_winapp: str) -> str:
    return f"{hwnd}|{typ}|{selektor_winapp}"


def _rozbierz(selektor: str) -> tuple[str, str, str]:
    hwnd, typ, slug = (str(selektor).split("|", 2) + ["", "", ""])[:3]
    return hwnd, typ, slug


class OknoProgramu:
    """Okna jednego procesu widziane przez UI Automation - "strona" dla Klikamy."""

    def __init__(self, winapp, program: str, pid: int):
        self.winapp = winapp
        self.program = program
        self.pid = int(pid)
        self._mapa: dict[str, dict] = {}
        self._tekst = ""
        self._hasla: dict[str, str] = {}

    @classmethod
    def polacz(cls, program: str, winapp=None, dozwolone: set[str] | None = None):
        """Sprawdza zgode, znajduje proces po nazwie i zapamietuje jego PID."""
        czysta = sprawdz_program(program, dozwolone if dozwolone is not None
                                 else dozwolone_programy())
        winapp = winapp or Winapp()
        stan = winapp("status", "--app", czysta)
        proces = nazwa_programu(str(stan.get("processName", "")))
        pid = stan.get("processId")
        # -a dopasowuje tez tytul okna. Program musi byc tym procesem, nie
        # oknem, ktore tylko sie tak nazywa.
        if proces != czysta or not isinstance(pid, int) or pid <= 0:
            raise OdmowaPulpitu(
                f"Nie znalazlem uruchomionego programu {czysta}. Otworz go i sprobuj ponownie."
            )
        if not stan.get("hwnd"):
            raise OdmowaPulpitu(f"Program {czysta} jeszcze nie pokazal okna.")
        log.info("pulpit: polaczono z programem z listy dozwolonych")
        return cls(winapp, czysta, pid)

    @property
    def url(self) -> str:
        return f"{PREFIKS_ADRESU}{self.program}/"

    # -- odczyt --

    def _drzewo(self) -> dict:
        return self.winapp("inspect", "--app", str(self.pid), "--depth", str(GLEBOKOSC),
                           "--hide-offscreen")

    def elementy(self, limit: int = MAKS_ELEMENTOW) -> list[dict]:
        drzewo = self._drzewo()
        okna = [o for o in (drzewo.get("windows") or []) if isinstance(o, dict)]
        elementy: list[dict] = []
        teksty: list[str] = []
        self._mapa, self._hasla = {}, {}
        wiele_okien = len(okna) > 1

        for nr_okna, okno in enumerate(okna, start=1):
            hwnd = okno.get("hwnd")
            tytul = str(okno.get("title") or "")
            napisy_okna: list[str] = []
            dzialania_okna: list[dict] = []
            self._zbierz(okno.get("elements") or [], napisy_okna, dzialania_okna)
            teksty.append(f"[Okno {nr_okna}] {tytul}".rstrip())
            teksty.extend(napisy_okna)
            kontekst = " ".join([tytul, *napisy_okna])[:MAKS_KONTEKSTU]
            for e in dzialania_okna:
                if len(elementy) >= limit:
                    break
                nazwa = e["nazwa"]
                rola = e["typ"] + (f" w oknie {nr_okna}" if wiele_okien else "")
                selektor = _selektor(hwnd, e["typ"], e["selektor"])
                element = {
                    "nr": len(elementy) + 1,
                    "rola": rola,
                    "opis": nazwa or "(bez nazwy)",
                    "selektor": selektor,
                    "kontekst": kontekst if GENERYCZNE.match(nazwa) else "",
                }
                elementy.append(element)
                self._mapa[selektor] = element
        self._tekst = "\n".join(t for t in teksty if t)[:MAKS_TEKSTU]
        return elementy

    def _zbierz(self, wezly: list, napisy: list[str], dzialania: list[dict]) -> None:
        for wezel in wezly:
            if not isinstance(wezel, dict):
                continue
            typ = str(wezel.get("type") or "")
            if typ == "TitleBar":
                continue  # Zamknij/Minimalizuj okna programu - nie dla modelu
            nazwa = str(wezel.get("name") or "").strip()
            wartosc = wezel.get("value")
            wlaczony = wezel.get("isEnabled", True) is not False
            widoczny = not wezel.get("isOffscreen", False)
            if typ in TYPY_TEKSTU and nazwa:
                napisy.append(nazwa)
            elif isinstance(wartosc, str) and wartosc.strip() and nazwa:
                napisy.append(f"{nazwa}: {wartosc.strip()}")
            dziala = (wezel.get("isInvokable") or wezel.get("isEditable")
                      or typ in TYPY_DZIALAN)
            if dziala and wlaczony and widoczny and wezel.get("selector"):
                dzialania.append({"typ": typ or "Element", "nazwa": nazwa,
                                  "selektor": str(wezel["selector"])})
            self._zbierz(wezel.get("children") or [], napisy, dzialania)

    def tekst_strony(self, limit: int = MAKS_TEKSTU) -> str:
        return self._tekst[:limit]

    def _z_migawki(self, selektor: str) -> dict:
        element = self._mapa.get(selektor)
        if element is None:
            raise OdmowaPulpitu("Tego elementu nie ma w oknie, ktore odczytalem. "
                                "Odczytam okno jeszcze raz.")
        return element

    def typ_pola(self, selektor: str) -> str:
        """'password', 'text' albo 'nieznany' (wtedy tez nie wpisujemy)."""
        if selektor in self._hasla:
            return self._hasla[selektor]
        self._z_migawki(selektor)
        hwnd, typ, slug = _rozbierz(selektor)
        try:
            wynik = self.winapp("get-property", "--window", hwnd, "--type", typ,
                                "--property", "IsPassword", pozycyjne=(slug,))
            wartosc = str((wynik.get("properties") or {}).get("IsPassword", "")).lower()
            rodzaj = "password" if wartosc == "true" else (
                "text" if wartosc == "false" else "nieznany")
        except BladWinapp:
            rodzaj = "nieznany"
        self._hasla[selektor] = rodzaj
        return rodzaj

    def odcisk_formularzy(self) -> str:
        """Skrot calego stanu okien - po zgodzie na wysylke nic nie moze sie zmienic."""
        drzewo = self._drzewo()
        skrot = hashlib.sha256()

        def dodaj(wezly):
            for w in wezly or []:
                if isinstance(w, dict):
                    skrot.update(json.dumps(
                        [w.get("selector"), w.get("type"), w.get("name"), w.get("value")],
                        ensure_ascii=False).encode("utf-8"))
                    dodaj(w.get("children"))

        for okno in drzewo.get("windows") or []:
            if isinstance(okno, dict):
                skrot.update(str(okno.get("hwnd")).encode())
                dodaj(okno.get("elements"))
        return skrot.hexdigest()

    # -- czynnosci --

    def kliknij(self, selektor: str) -> None:
        element = self._z_migawki(selektor)
        opis = " ".join(filter(None, [element.get("opis", ""), element.get("kontekst", "")]))
        if "�" in element.get("opis", ""):
            raise OdmowaPulpitu("Nie umiem odczytac nazwy tego przycisku, wiec go nie klikne.")
        if ZABRONIONE_PULPIT.search(opis):
            raise OdmowaPulpitu(
                f"Nie kliknę „{element.get('opis', '')[:100]}”. Tej czynnosci programu "
                "nie da sie cofnac - wykonuje ja notariusz osobiscie."
            )
        hwnd, typ, slug = _rozbierz(selektor)
        # --type wylacza przeskok do rodzica: winapp dziala dokladnie na tym elemencie.
        self.winapp("invoke", "--window", hwnd, "--type", typ, pozycyjne=(slug,))

    def wpisz(self, selektor: str, wartosc: str) -> None:
        self._z_migawki(selektor)
        rodzaj = self.typ_pola(selektor)
        if rodzaj == "password":
            raise OdmowaPulpitu("To pole hasla. Haslo i PIN karty wpisujesz wylacznie Ty.")
        if rodzaj != "text":
            raise OdmowaPulpitu("Nie umiem sprawdzic, czy to nie pole hasla, wiec nic "
                                "w nim nie wpisze.")
        hwnd, typ, slug = _rozbierz(selektor)
        self.winapp("set-value", "--window", hwnd, "--type", typ,
                    pozycyjne=(slug, str(wartosc)[:MAKS_WPISU]))

    def wybierz(self, selektor: str, wartosc: str) -> None:
        """Pozycja listy rozwijanej: najpierw wprost, potem przez rozwiniecie listy."""
        self._z_migawki(selektor)
        hwnd, typ, slug = _rozbierz(selektor)
        try:
            self.winapp("set-value", "--window", hwnd, "--type", typ,
                        pozycyjne=(slug, str(wartosc)[:MAKS_WPISU]))
            return
        except BladWinapp:
            pass
        self.winapp("invoke", "--window", hwnd, "--type", typ, "--action", "expand",
                    pozycyjne=(slug,))
        wynik = self.winapp("search", "--window", hwnd, "--root", slug,
                            "--type", "ListItem", pozycyjne=(str(wartosc)[:200],))
        szukane = str(wartosc).strip().casefold()
        trafienia = [m for m in wynik.get("matches") or []
                     if isinstance(m, dict)
                     and str(m.get("name", "")).strip().casefold() == szukane]
        if len(trafienia) != 1:
            raise OdmowaPulpitu("Nie znalazlem jednoznacznie takiej pozycji na liscie.")
        self.winapp("invoke", "--window", hwnd, "--type", "ListItem", "--action", "select",
                    pozycyjne=(str(trafienia[0].get("selector", "")),))

    def otworz(self, adres: str) -> None:
        raise OdmowaPulpitu("To program na komputerze, a nie strona - adresow tu nie otwieram.")

    def zakoncz(self) -> None:
        """Oddaje pulpit innym (winapp ui yield). Brak winapp tu juz nie przeszkadza."""
        try:
            self.winapp("yield")
        except BladWinapp:
            pass
