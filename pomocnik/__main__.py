"""Uruchomienie pomocnika: python -m pomocnik albo notarai-pomocnik.exe

Pobrany .exe przy pierwszym uruchomieniu instaluje sie sam (instalacja.py)
i przekazuje prace zainstalowanej kopii. Z autostartu Windows przychodzi
z flaga --w-tle: wtedy okno startuje zminimalizowane.

Dziennik pomocnika zapisujemy obok ustawien, zeby przy zgloszeniu usterki bylo
co przeczytac. Rodzaje czynnosci i liczby, nigdy numery ani wartosci pol.
"""
import logging
import os
import sys
from pathlib import Path

from pomocnik import instalacja
from pomocnik.klient import WERSJA
from pomocnik.okno import uruchom


def _dziennik() -> Path:
    katalog = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "notarai"
    katalog.mkdir(parents=True, exist_ok=True)
    return katalog / "pomocnik.log"


def _pokaz_blad(tresc: str) -> None:  # pragma: no cover - okno systemowe
    import ctypes
    ctypes.windll.user32.MessageBoxW(None, tresc, "notarai - pomocnik", 0x10)


def main() -> None:
    uchwyty = [logging.FileHandler(_dziennik(), encoding="utf-8")]
    if sys.stderr:  # w .exe bez konsoli stderr nie istnieje
        uchwyty.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, handlers=uchwyty,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if instalacja.FLAGA_ODINSTALUJ in sys.argv:
        instalacja.odinstaluj()
        return
    if instalacja.spakowany() and instalacja.trzeba_zainstalowac(Path(sys.executable)):
        try:
            cel = instalacja.zainstaluj(Path(sys.executable), WERSJA)
        except Exception as blad:  # noqa: BLE001
            logging.getLogger("notarai.pomocnik").error("instalacja nieudana: %r", blad)
            _pokaz_blad("Nie udało się zainstalować pomocnika.\n\n"
                        f"{type(blad).__name__}: {blad}\n\n"
                        "Zamknij wszystkie okna pomocnika i uruchom plik ponownie.")
            return
        instalacja.uruchom_niezaleznie([str(cel)])
        return
    uruchom(w_tle=instalacja.FLAGA_W_TLE in sys.argv)


if __name__ == "__main__":
    main()
