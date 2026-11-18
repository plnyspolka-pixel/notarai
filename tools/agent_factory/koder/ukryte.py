"""Ukryte testy karty (W6 z laboratorium): ocena, której agent nie widzi.

Agent, który sam widzi testy, potrafi je „obejść”, a zgłaszając wynik często mija się
z prawdą (laboratorium: STAN-WIEDZY.md, D2 i C2). Dlatego obok testu z karty
(`sprawdzenie`, widoczny dla agenta) każda karta toru `koder` ma ukryty katalog:

    docs/agent-tasks/ukryte/<id>/
        test_*.py        ukryte testy akceptacyjne (pisze Claude, nie agent)
        *.patch          łatki sabotażu: celowo błędne rozwiązania

Agent dostaje kopię repozytorium bez tego katalogu (i bez .git). Ocena działa na osobnej
kopii, więc ukryte testy nigdy nie trafiają do commita agenta.

Rodzaj karty (`rodzaj:` w nagłówku) decyduje o kontroli:

| rodzaj   | przed pracą agenta (na kodzie bazowym)                  | po pracy agenta                                  |
|----------|---------------------------------------------------------|--------------------------------------------------|
| zmiana   | ukryte testy OBLEWAJĄ; każda łatka -> dalej oblewają    | ukryte testy PRZECHODZĄ                           |
| refaktor | ukryte testy PRZECHODZĄ; każda łatka -> OBLEWAJĄ        | ukryte testy PRZECHODZĄ                           |
| testy    | każda łatka daje się nałożyć                            | test z karty OBLEWA każdą łatkę (wykrywa błąd)   |

Karta, która nie przejdzie kontroli „przed”, jest wadliwa (test, który przechodzi bez
zmiany, niczego nie sprawdza) - agent jej nie dostaje, karta wraca do Claude.

Polecenia (wynik zawsze JSON na stdout):
  przed KARTA KATALOG_BAZOWY
  po    KARTA KATALOG_PRACY_AGENTA

Testy uruchamia kontener `koder-agent` bez sieci; KODER_OCENA=lokalnie uruchamia je
bezpośrednio (testy i próby na własnym komputerze).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

try:  # uruchomienie jako skrypt (zadanie.sh) albo import z testów
    import karta as _karta
except ImportError:  # pragma: no cover - ścieżka pakietowa
    from tools.agent_factory.koder import karta as _karta

LIMIT_SEKUND = 300
OBLANE = (1, 2)  # pytest: 1 = testy oblane, 2 = błąd zbierania (np. brak nowej funkcji)


def uruchom(katalog: Path, argv: list[str]) -> int:
    """Uruchamia polecenie testów w katalogu: w kontenerze bez sieci albo lokalnie."""
    argv = [*argv, "-p", "no:cacheprovider"]
    if os.environ.get("KODER_OCENA") == "lokalnie":
        cmd = [sys.executable if argv[0] == "python" else argv[0], *argv[1:]]
        cwd = str(katalog)
    else:
        uid = f"{getattr(os, 'getuid', lambda: 1000)()}:{getattr(os, 'getgid', lambda: 1000)()}"
        cmd = ["docker", "run", "--rm", "--network", "none", "--cap-drop", "ALL",
               "--security-opt", "no-new-privileges", "--memory", "4g", "-u", uid,
               "-v", f"{katalog}:/repo", "-w", "/repo", "koder-agent", *argv]
        cwd = None
    try:
        return subprocess.run(cmd, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              stdin=subprocess.DEVNULL, timeout=LIMIT_SEKUND).returncode
    except subprocess.TimeoutExpired:
        return 124


def _kopia(zrodlo: Path, robocze: Path, nazwa: str) -> Path:
    cel = Path(tempfile.mkdtemp(prefix=f"{nazwa}-", dir=robocze))
    shutil.copytree(zrodlo, cel, dirs_exist_ok=True)
    return cel


def _naloz(katalog: Path, latka: Path) -> bool:
    env = {**os.environ, "GIT_CEILING_DIRECTORIES": str(katalog.parent)}
    r = subprocess.run(["git", "apply", "--whitespace=nowarn", str(latka.resolve())], cwd=katalog,
                       env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return r.returncode == 0


def _ukryte_testy(karta: dict, katalog: Path) -> int:
    """Kopiuje ukryte testy do katalogu i je uruchamia; zwraca kod wyjścia pytest."""
    zrodlo = _karta.katalog_ukrytych(karta)
    cel = katalog / f"_ukryte_{karta['id'].replace('-', '_')}"
    cel.mkdir()
    for plik in zrodlo.glob("*.py"):
        shutil.copy2(plik, cel / plik.name)
    return uruchom(katalog, ["python", "-m", "pytest", "-q", cel.name])


def _sprawdzenie(karta: dict, katalog: Path) -> int:
    return uruchom(katalog, str(karta["sprawdzenie"]).split())


def przed(karta: dict, baza: Path, robocze: Path) -> dict:
    rodzaj = _karta.rodzaj(karta)
    latki = _karta.latki(karta)
    szczegoly = []
    if rodzaj in ("zmiana", "refaktor"):
        rc = _ukryte_testy(karta, _kopia(baza, robocze, "baza"))
        oczekiwane = "oblewają" if rodzaj == "zmiana" else "przechodzą"
        dobrze = rc in OBLANE if rodzaj == "zmiana" else rc == 0
        szczegoly.append({"co": "kod bazowy", "kod_pytest": rc, "oczekiwane": oczekiwane, "ok": dobrze})
        if not dobrze:
            powod = ("ukryte testy przechodzą bez żadnej zmiany - niczego nie sprawdzają"
                     if rodzaj == "zmiana" else "ukryte testy nie przechodzą na kodzie bazowym (rc=%d)" % rc)
            return {"ok": False, "powod": powod, "szczegoly": szczegoly}
    for latka in latki:
        kat = _kopia(baza, robocze, "sabotaz")
        if not _naloz(kat, latka):
            szczegoly.append({"co": latka.name, "ok": False, "blad": "łatka nie pasuje do kodu bazowego"})
            return {"ok": False, "powod": f"łatka {latka.name} nie pasuje do kodu bazowego", "szczegoly": szczegoly}
        if rodzaj == "testy":
            szczegoly.append({"co": latka.name, "ok": True})
            continue
        rc = _ukryte_testy(karta, kat)
        dobrze = rc in OBLANE
        szczegoly.append({"co": latka.name, "kod_pytest": rc, "oczekiwane": "oblewają", "ok": dobrze})
        if not dobrze:
            return {"ok": False, "powod": f"ukryte testy przepuszczają celowo błędne rozwiązanie {latka.name}",
                    "szczegoly": szczegoly}
    return {"ok": True, "powod": "", "szczegoly": szczegoly}


def po(karta: dict, praca: Path, robocze: Path) -> dict:
    rodzaj = _karta.rodzaj(karta)
    if rodzaj in ("zmiana", "refaktor"):
        rc = _ukryte_testy(karta, _kopia(praca, robocze, "ocena"))
        return {"ukryte_zaliczone": rc == 0, "kod_pytest": rc, "wykryte": None}
    wyniki = []
    for latka in _karta.latki(karta):
        kat = _kopia(praca, robocze, "mutacja")
        if not _naloz(kat, latka):
            wyniki.append({"latka": latka.name, "wykryta": False, "blad": "łatka nie pasuje do pracy agenta"})
            continue
        rc = _sprawdzenie(karta, kat)
        wyniki.append({"latka": latka.name, "wykryta": rc in OBLANE, "kod_pytest": rc})
    wykryte = sum(w["wykryta"] for w in wyniki)
    return {"ukryte_zaliczone": bool(wyniki) and wykryte == len(wyniki),
            "wykryte": f"{wykryte}/{len(wyniki)}", "szczegoly": wyniki}


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[0] not in ("przed", "po"):
        print(__doc__)
        return 2
    karta = _karta.wczytaj(Path(argv[1]))
    robocze = Path(os.environ.get("TMP", tempfile.gettempdir())) / "ocena"
    robocze.mkdir(parents=True, exist_ok=True)
    wynik = (przed if argv[0] == "przed" else po)(karta, Path(argv[2]), robocze)
    print(json.dumps({"id": karta["id"], "rodzaj": _karta.rodzaj(karta), **wynik}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
