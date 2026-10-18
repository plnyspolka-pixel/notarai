"""Przegladarka do rejestrow: osobne okno, osobny profil, prawa polowa ekranu.

Osobny profil nie jest kaprysem. Od Chrome 136 sterowanie przegladarka na
domyslnym profilu jest zablokowane - tak Google utrudnia wykradanie ciasteczek.
Przy okazji wychodzi to notariuszowi na dobre: praca w rejestrach nie miesza
sie z jego prywatnym Chrome.

Okno stawiamy po prawej stronie ekranu, bo po lewej stoi notarai z poleceniem.
Notariusz widzi oba naraz i w kazdej chwili moze zlapac mysz - to jego sesja,
jego certyfikat i jego decyzja.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger("notarai.pomocnik.przegladarka")

PORT = 9222


def sciezka_przegladarki() -> str | None:
    kandydaci = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Microsoft/Edge/Application/msedge.exe",
    ]
    for kandydat in kandydaci:
        if kandydat.exists():
            return str(kandydat)
    return (shutil.which("chrome") or shutil.which("msedge")
            or shutil.which("chromium") or shutil.which("google-chrome"))


def katalog_profilu() -> Path:
    profil = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "notarai" / "przegladarka"
    profil.mkdir(parents=True, exist_ok=True)
    return profil


def uruchom(port: int = PORT, ekran: tuple[int, int] | None = None,
            adres: str = "about:blank", start=subprocess.Popen):
    """Otwiera przegladarke do rejestrow na prawej polowie ekranu."""
    exe = sciezka_przegladarki()
    if not exe:
        raise RuntimeError(
            "Nie znalazlem Chrome ani Edge. Zainstaluj jedna z tych przegladarek."
        )
    flagi = [
        exe,
        f"--remote-debugging-port={port}",
        "--remote-debugging-address=127.0.0.1",
        f"--user-data-dir={katalog_profilu()}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if ekran:
        szerokosc, wysokosc = ekran
        polowa = max(szerokosc // 2, 640)
        flagi += [f"--window-position={szerokosc - polowa},0",
                  f"--window-size={polowa},{wysokosc}"]
    flagi.append(adres)

    dodatkowe = {}
    if os.name == "nt":
        # Przegladarka ma przezyc zamkniecie pomocnika - to okno notariusza.
        dodatkowe["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    log.info("uruchamiam przegladarke do rejestrow na porcie %d", port)
    return start(flagi, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **dodatkowe)
