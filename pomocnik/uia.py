"""Okno programu widziane przez Windows UI Automation (tylko Windows).

UI Automation to interfejs dostepnosci Windows - z niego korzystaja czytniki
ekranu dla niewidomych. Program nie musi nic o nas wiedziec: kazdy zwykly
program Windows (WinForms, WPF, Delphi/VCL, Win32, Office) wystawia przez
niego swoje przyciski, pola i listy z nazwami. Dlatego to nasza droga
uniwersalna do dowolnego programu kancelaryjnego.

Biblioteka `uiautomation` jest ladowana dopiero tutaj, zeby reszta pomocnika
(i testy na Linuksie) jej nie potrzebowala. Kontrolki trzymamy w pamieci pod
numerami - model widzi tylko numer, role i nazwe.

Znane ograniczenia (sprawdzane na zywo, docs/czeka-na-dostep.md):
  - programy rysujace wlasne kontrolki bez dostepnosci (stare Clarion, czesc
    gier i terminali) pokaza malo albo nic; wtedy pomocnik mowi to wprost,
    zamiast klikac w ciemno,
  - pomocnik dziala z uprawnieniami uzytkownika; program uruchomiony "jako
    administrator" jest dla niego niewidoczny (izolacja UIPI w Windows).
"""
from __future__ import annotations

import ctypes
import logging
import os
import subprocess
import time
from pathlib import Path

log = logging.getLogger("notarai.pomocnik.uia")

# Kontrolki, ktorymi da sie cos zrobic albo ktore niosa tresc pola.
ROLE = {
    "ButtonControl": "przycisk", "EditControl": "pole", "ComboBoxControl": "lista",
    "ListItemControl": "pozycja", "MenuItemControl": "menu", "TabItemControl": "zakladka",
    "CheckBoxControl": "pole wyboru", "RadioButtonControl": "opcja",
    "TreeItemControl": "galaz", "DataItemControl": "wiersz", "HyperlinkControl": "odnosnik",
    "SplitButtonControl": "przycisk", "DocumentControl": "dokument",
}
TEKSTOWE = {"TextControl", "HeaderItemControl", "StatusBarControl"}
KLAWISZE_UIA = {
    "tab": "{Tab}", "shift+tab": "{Shift}{Tab}", "gora": "{Up}", "dol": "{Down}",
    "lewo": "{Left}", "prawo": "{Right}", "esc": "{Esc}", "pageup": "{PageUp}",
    "pagedown": "{PageDown}", "home": "{Home}", "end": "{End}",
}
GLEBOKOSC = 14
CZAS_STARTU_S = 30


def _plik_procesu(pid: int) -> str:
    """Nazwa .exe procesu - bez psutil, prosto z jadra Windows."""
    jadro = ctypes.windll.kernel32
    uchwyt = jadro.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not uchwyt:
        return ""
    try:
        bufor = ctypes.create_unicode_buffer(1024)
        rozmiar = ctypes.c_ulong(len(bufor))
        if jadro.QueryFullProcessImageNameW(uchwyt, 0, bufor, ctypes.byref(rozmiar)):
            return Path(bufor.value).name.lower()
        return ""
    finally:
        jadro.CloseHandle(uchwyt)


class BrakOkna(RuntimeError):
    """Program nie ma otwartego okna. Tresc widzi notariusz."""


class OknoUIA:
    def __init__(self, nazwa: str, proces: str, auto=None):
        if auto is None:
            import uiautomation as auto  # noqa: PLC0415 - tylko Windows, tylko tutaj
        self.auto = auto
        self.nazwa = nazwa
        self.proces = proces.lower()
        self._mapa: dict[int, object] = {}
        self._pid_cache: dict[int, str] = {}

    # --- okna programu ---

    def _exe(self, pid: int) -> str:
        if pid not in self._pid_cache:
            self._pid_cache[pid] = _plik_procesu(pid)
        return self._pid_cache[pid]

    def okna(self) -> list:
        wynik = []
        for okno in self.auto.GetRootControl().GetChildren():
            try:
                if self._exe(okno.ProcessId) == self.proces and not okno.IsOffscreen:
                    wynik.append(okno)
            except Exception:  # noqa: BLE001 - okno zniknelo w trakcie
                continue
        return wynik

    @property
    def tytul(self) -> str:
        okna = self.okna()
        return (okna[0].Name or "")[:200] if okna else ""

    # --- co widac ---

    def elementy(self, limit: int = 150) -> list[dict]:
        self._mapa = {}
        wynik: list[dict] = []
        for okno in self.okna():
            for kontrolka, _ in self.auto.WalkControl(okno, includeTop=False, maxDepth=GLEBOKOSC):
                if len(wynik) >= limit:
                    return wynik
                try:
                    typ = kontrolka.ControlTypeName
                    if typ not in ROLE or kontrolka.IsOffscreen or not kontrolka.IsEnabled:
                        continue
                    opis = (kontrolka.Name or kontrolka.AutomationId or "").strip()
                    if typ == "EditControl" and not opis:
                        opis = "pole bez nazwy"
                    if not opis:
                        continue
                    nr = len(wynik) + 1
                    self._mapa[nr] = kontrolka
                    wynik.append({
                        "nr": nr, "rola": ROLE[typ], "opis": opis[:120],
                        "haslo": bool(getattr(kontrolka, "IsPassword", False)),
                        "proces": self.proces,
                    })
                except Exception:  # noqa: BLE001 - kontrolka zniknela w trakcie
                    continue
        return wynik

    def tekst(self, limit: int = 4000) -> str:
        czesci: list[str] = []
        for okno in self.okna():
            czesci.append(okno.Name or "")
            for kontrolka, _ in self.auto.WalkControl(okno, includeTop=False, maxDepth=GLEBOKOSC):
                try:
                    if kontrolka.ControlTypeName in TEKSTOWE and kontrolka.Name:
                        czesci.append(kontrolka.Name)
                    elif kontrolka.ControlTypeName == "EditControl" and not getattr(
                            kontrolka, "IsPassword", False):
                        wzorzec = kontrolka.GetPattern(self.auto.PatternId.ValuePattern)
                        if wzorzec and wzorzec.Value:
                            czesci.append(f"[{kontrolka.Name or 'pole'}: {wzorzec.Value}]")
                except Exception:  # noqa: BLE001
                    continue
                if sum(map(len, czesci)) > limit:
                    break
        return "\n".join(c for c in czesci if c)[:limit]

    # --- czynnosci ---

    def _kontrolka(self, nr: int):
        try:
            return self._mapa[int(nr)]
        except (KeyError, ValueError):
            raise RuntimeError("kontrolka zniknela") from None

    def _na_wierzch(self, kontrolka) -> None:
        try:
            kontrolka.GetTopLevelControl().SetActive()
        except Exception:  # noqa: BLE001 - nie kazde okno da sie aktywowac
            pass

    def kliknij(self, nr: int) -> None:
        k = self._kontrolka(nr)
        self._na_wierzch(k)
        p = self.auto.PatternId
        for wzorzec, czynnosc in ((p.InvokePattern, "Invoke"), (p.SelectionItemPattern, "Select"),
                                  (p.TogglePattern, "Toggle"),
                                  (p.ExpandCollapsePattern, "Expand")):
            obiekt = k.GetPattern(wzorzec)
            if obiekt:
                getattr(obiekt, czynnosc)()
                return
        k.Click(simulateMove=False)

    def wpisz(self, nr: int, tekst: str) -> None:
        k = self._kontrolka(nr)
        if getattr(k, "IsPassword", False):
            raise RuntimeError("pole hasla")
        self._na_wierzch(k)
        wartosc = k.GetPattern(self.auto.PatternId.ValuePattern)
        if wartosc and not getattr(wartosc, "IsReadOnly", False):
            wartosc.SetValue(tekst)
            return
        k.SetFocus()
        # SendKeys traktuje {} jako klawisze specjalne - wpisujemy je doslownie.
        self.auto.SendKeys(tekst.replace("{", "{{}").replace("}", "{}}"), interval=0.01)

    def wybierz(self, nr: int, tekst: str) -> None:
        k = self._kontrolka(nr)
        self._na_wierzch(k)
        rozwin = k.GetPattern(self.auto.PatternId.ExpandCollapsePattern)
        if rozwin:
            rozwin.Expand()
        pozycja = k.ListItemControl(Name=tekst, searchDepth=3)
        if not pozycja.Exists(2):
            raise RuntimeError("brak pozycji na liscie")
        pozycja.GetPattern(self.auto.PatternId.SelectionItemPattern).Select()

    def klawisz(self, nazwa: str) -> None:
        okna = self.okna()
        if okna:
            self._na_wierzch(okna[0])
        self.auto.SendKeys(KLAWISZE_UIA[nazwa])


def otworz(program, czekaj_s: float = CZAS_STARTU_S, auto=None) -> OknoUIA:
    """Okno programu z lokalnego spisu. Uruchamia program, gdy nie dziala.

    Sciezke bierzemy z wlasnego rozpoznania na tym komputerze, nigdy od
    serwera - notarai nie moze kazac pomocnikowi uruchomic dowolnego pliku.
    """
    okno = OknoUIA(program.nazwa, program.proces, auto=auto)
    if okno.okna():
        return okno
    if not program.plik or not os.path.isfile(program.plik):
        raise BrakOkna(f"Nie znalazlem pliku programu {program.nazwa}. Otworz go recznie.")
    subprocess.Popen([program.plik], cwd=str(Path(program.plik).parent))  # noqa: S603
    koniec = time.monotonic() + czekaj_s
    while time.monotonic() < koniec:
        time.sleep(1)
        if okno.okna():
            time.sleep(1)  # program dociaga okno glowne
            return okno
    raise BrakOkna(f"{program.nazwa} nie otworzyl okna w {int(czekaj_s)} s. Otworz go recznie.")
