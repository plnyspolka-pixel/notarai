"""Wspólne narzędzia fabryki odcinków: ścieżki, czas Warszawy, odczyt plików z innych gałęzi.

Fabryka czyta materiały z kilku gałęzi, które nie są jeszcze scalone (scenografia, kolejka
publikacji, katalog spraw). Zamiast zgadywać, czyta je przez `git show origin/<gałąź>:<ścieżka>`;
gdy plik jest już w bieżącym drzewie, pierwszeństwo ma drzewo robocze.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

KORZEN = Path(__file__).resolve().parents[2]
WARSZAWA = ZoneInfo("Europe/Warsaw")

# Gałęzie źródłowe (do czasu scalenia z master). Nadpisywalne zmiennymi środowiska.
GALEZ_SCENOGRAFIA = os.getenv("FABRYKA_GALEZ_SCENOGRAFIA", "scenografia/blender-v1")
GALEZ_SERIAL = os.getenv("FABRYKA_GALEZ_SERIAL", "strona/serial-komputerku")
GALEZ_KATALOG = os.getenv("FABRYKA_GALEZ_KATALOG", "research/notarial-casebook-court-ministry-2026-11")

BIBLIA = "marketing/komputerku/BIBLIA_V6.md"
KATALOG_SPRAW = "docs/research/notarial-casebook-2026"
KOLEJKA = "serial/odcinki.json"


def katalog_sezonu(sezon: int) -> Path:
    return KORZEN / f"marketing/komputerku/sezon-{sezon}"


def katalog_odcinkow(sezon: int) -> Path:
    return katalog_sezonu(sezon) / "odcinki"


def katalog_kart(sezon: int) -> Path:
    return katalog_sezonu(sezon) / "03_PRODUKCJA"


def teraz() -> datetime:
    return datetime.now(WARSZAWA)


def czas(s: str) -> datetime:
    """ISO z jawną strefą albo bez (wtedy Warszawa)."""
    d = datetime.fromisoformat(s)
    return d if d.tzinfo else d.replace(tzinfo=WARSZAWA)


def czytaj(sciezka: str, galez: str | None = None) -> str | None:
    """Plik z drzewa roboczego, a gdy go nie ma - z origin/<galez>. None, gdy nie ma nigdzie."""
    p = KORZEN / sciezka
    if p.exists():
        return p.read_text(encoding="utf-8")
    if not galez:
        return None
    try:
        return subprocess.run(
            ["git", "-C", str(KORZEN), "show", f"origin/{galez}:{sciezka}"],
            check=True, capture_output=True, text=True,
        ).stdout
    except subprocess.CalledProcessError:
        return None


def czytaj_json(sciezka: str, galez: str | None = None):
    t = czytaj(sciezka, galez)
    return None if t is None else json.loads(t)


def zapisz_json(sciezka: Path, dane) -> Path:
    sciezka.parent.mkdir(parents=True, exist_ok=True)
    sciezka.write_text(json.dumps(dane, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return sciezka


def id_odcinka(sezon: int, odcinek: int) -> str:
    return f"s{sezon:02d}e{odcinek:02d}"


def utc(d: datetime) -> datetime:
    return d.astimezone(timezone.utc)
