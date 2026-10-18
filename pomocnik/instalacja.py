"""Pomocnik instaluje sie sam - pobrany plik wystarczy uruchomic.

Notariusz nie przechodzi przez zaden instalator z dziesiecioma ekranami.
Pierwsze uruchomienie pobranego pliku:
  1. zamyka poprzednia wersje pomocnika, jesli dziala (to jest tez aktualizacja),
  2. kopiuje sie do %LOCALAPPDATA%\\Programs\\notarai,
  3. dodaje skrot w menu Start i w autostarcie - po restarcie komputera
     pomocnik startuje sam, zminimalizowany,
  4. wpisuje sie do "Aplikacje i funkcje" Windows, zeby dalo sie go
     normalnie odinstalowac,
  5. uruchamia zainstalowana kopie i konczy prace.

Wszystko w profilu uzytkownika - bez uprawnien administratora i bez okna
"Czy zezwolic tej aplikacji na wprowadzanie zmian".
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

log = logging.getLogger("notarai.pomocnik.instalacja")

NAZWA_PLIKU = "notarai-pomocnik.exe"
NAZWA_SKROTU = "notarai pomocnik.lnk"
KLUCZ_ODINSTALOWANIA = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\notarai-pomocnik"
FLAGA_W_TLE = "--w-tle"
FLAGA_ODINSTALUJ = "--odinstaluj"
_BEZ_OKNA = 0x08000000  # CREATE_NO_WINDOW


def katalog_programu() -> Path:
    baza = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(baza) / "Programs" / "notarai"


def plik_programu() -> Path:
    return katalog_programu() / NAZWA_PLIKU


def katalog_menu_start() -> Path:
    baza = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(baza) / "Microsoft" / "Windows" / "Start Menu" / "Programs"


def katalog_autostartu() -> Path:
    return katalog_menu_start() / "Startup"


def spakowany() -> bool:
    """Czy dzialamy jako plik .exe, a nie z kodu (python -m pomocnik)."""
    return bool(getattr(sys, "frozen", False))


def trzeba_zainstalowac(biezacy: Path) -> bool:
    try:
        return biezacy.resolve() != plik_programu().resolve()
    except OSError:
        return True


def _powershell(polecenie: str) -> None:
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", polecenie],
                   check=True, creationflags=_BEZ_OKNA, timeout=60)


def _ps(tekst: str) -> str:
    return "'" + str(tekst).replace("'", "''") + "'"


def utworz_skrot(skrot: Path, cel: Path, argumenty: str = "") -> None:
    skrot.parent.mkdir(parents=True, exist_ok=True)
    _powershell(
        f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut({_ps(skrot)});"
        f"$s.TargetPath={_ps(cel)};$s.Arguments={_ps(argumenty)};"
        f"$s.WorkingDirectory={_ps(cel.parent)};$s.Description='notarai - pomocnik';$s.Save()")


def zamknij_inne_kopie() -> None:
    """Poprzednia wersja trzyma plik - bez zamkniecia nie da sie go podmienic.

    Plik .exe z PyInstallera to dwa procesy: rozpakowujacy i wlasciwy. Oszczedzamy
    oba nasze - zabicie rozpakowujacego zabiloby i nas.
    """
    subprocess.run(["taskkill", "/F", "/IM", NAZWA_PLIKU,
                    "/FI", f"PID ne {os.getpid()}", "/FI", f"PID ne {os.getppid()}"],
                   capture_output=True, creationflags=_BEZ_OKNA, timeout=30)


def uruchom_niezaleznie(polecenie: list[str] | str) -> None:
    """Proces, ktory przezyje zamkniecie pomocnika.

    PyInstaller trzyma pomocnika w obiekcie zadania Windows: gdy pomocnik sie
    konczy, system zamyka tez wszystko, co z niego wystartowalo. Sprzatanie po
    odinstalowaniu i nowo zainstalowana kopia musza z tego zadania wyjsc.
    """
    flagi = _BEZ_OKNA | 0x01000000 | 0x00000200  # BREAKAWAY_FROM_JOB, NEW_PROCESS_GROUP
    try:
        subprocess.Popen(polecenie, creationflags=flagi, close_fds=True)
    except OSError:  # zadanie nie pozwala wyjsc - lepsze to niz nic
        subprocess.Popen(polecenie, creationflags=_BEZ_OKNA, close_fds=True)


def wpisz_do_aplikacji_windows(wersja: str) -> None:
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, KLUCZ_ODINSTALOWANIA) as klucz:
        program = str(plik_programu())
        for nazwa, wartosc in {
            "DisplayName": "notarai - pomocnik",
            "DisplayVersion": wersja,
            "Publisher": "notarai.pl",
            "DisplayIcon": program,
            "InstallLocation": str(katalog_programu()),
            "UninstallString": f'"{program}" {FLAGA_ODINSTALUJ}',
        }.items():
            winreg.SetValueEx(klucz, nazwa, 0, winreg.REG_SZ, wartosc)
        winreg.SetValueEx(klucz, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(klucz, "NoRepair", 0, winreg.REG_DWORD, 1)


def zainstaluj(zrodlo: Path, wersja: str) -> Path:
    """Kopiuje pomocnika na stale miejsce i zwraca sciezke zainstalowanej kopii."""
    zamknij_inne_kopie()
    cel = plik_programu()
    cel.parent.mkdir(parents=True, exist_ok=True)
    # Zamknieta przed chwila poprzednia wersja albo antywirus sprawdzajacy
    # stary plik potrafia trzymac go jeszcze kilka sekund.
    for proba in range(8):
        try:
            shutil.copy2(zrodlo, cel)
            break
        except PermissionError:
            if proba == 7:
                raise PermissionError(
                    "Plik pomocnika jest zablokowany - zwykle przez program "
                    "antywirusowy albo działającą kopię pomocnika.") from None
            time.sleep(1)
    utworz_skrot(katalog_menu_start() / NAZWA_SKROTU, cel)
    utworz_skrot(katalog_autostartu() / NAZWA_SKROTU, cel, FLAGA_W_TLE)
    try:
        wpisz_do_aplikacji_windows(wersja)
    except OSError as blad:  # brak wpisu nie przeszkadza w pracy
        log.warning("instalacja: bez wpisu w Aplikacjach (%s)", type(blad).__name__)
    log.info("instalacja: pomocnik %s zainstalowany", wersja)
    return cel


def polecenie_sprzatania(katalog: Path) -> str:
    return f'cmd /c ping -n 4 127.0.0.1 >nul & rmdir /s /q "{katalog}"'


def odinstaluj() -> None:
    """Skroty i wpis znikaja od razu, sam plik chwile po zamknieciu."""
    zamknij_inne_kopie()  # dzialajacy pomocnik trzyma plik i nie dalby go usunac
    for skrot in (katalog_menu_start() / NAZWA_SKROTU, katalog_autostartu() / NAZWA_SKROTU):
        skrot.unlink(missing_ok=True)
    try:
        import winreg
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, KLUCZ_ODINSTALOWANIA)
    except OSError:
        pass
    # Uruchomiony plik nie usunie sam siebie - robi to cmd po naszym wyjsciu.
    # Przerwa przez ping, bo `timeout` bez konsoli konczy sie od razu bledem.
    # Gotowy wiersz polecenia, nie lista: z listy Python zamienia cudzyslowy
    # na \", ktorych cmd nie rozumie, i rmdir dostaje zla sciezke.
    uruchom_niezaleznie(polecenie_sprzatania(katalog_programu()))
    log.info("instalacja: pomocnik odinstalowany")
