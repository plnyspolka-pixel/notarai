"""Uruchomienie pomocnika: python -m pomocnik

Dziennik pomocnika zapisujemy obok ustawien, zeby przy zgloszeniu usterki bylo
co przeczytac. Rodzaje czynnosci i liczby, nigdy numery ani wartosci pol.
"""
import logging
import os
from pathlib import Path

from pomocnik.okno import uruchom


def _dziennik() -> Path:
    katalog = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "notarai"
    katalog.mkdir(parents=True, exist_ok=True)
    return katalog / "pomocnik.log"


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(_dziennik(), encoding="utf-8"),
                  logging.StreamHandler()],
    )
    uruchom()


if __name__ == "__main__":
    main()
