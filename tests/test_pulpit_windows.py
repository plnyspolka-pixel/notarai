"""Proba na prawdziwym Windows: pomocnik prowadzi Notatnik przez winapp CLI.

Uruchamia ja tylko workflow pomocnik-windows.yml (NOTARAI_TEST_WINAPP=1), bo
potrzebuje Windowsa, winapp.exe i pulpitu. Sprawdza to, czego atrapa
w test_pomocnik_pulpit.py sprawdzic nie moze: prawdziwy ksztalt JSON z winapp,
polskie znaki i znaki powloki w obie strony (tekst idzie jako argument
procesu), odczyt IsPassword i to, ze winapp z PATH jest plikiem .exe.
"""
import os
import subprocess
import time

import pytest

from pomocnik import pulpit

pytestmark = pytest.mark.skipif(
    not (os.name == "nt" and os.environ.get("NOTARAI_TEST_WINAPP") == "1"),
    reason="tylko Windows z winapp (workflow pomocnik-windows.yml)",
)

TEKST = 'Zażółć gęślą jaźń & 100% "cudzysłów" ^ | <a>'


@pytest.fixture
def winapp():
    winapp = pulpit.Winapp()
    assert winapp.sciezka and winapp.sciezka.lower().endswith(".exe"), winapp.sciezka
    subprocess.Popen(["notepad.exe"])
    for _ in range(60):
        try:
            if winapp("status", "--app", "notepad").get("hwnd"):
                break
        except pulpit.BladWinapp:
            pass
        time.sleep(0.5)
    yield winapp
    subprocess.run(["taskkill", "/IM", "notepad.exe", "/F"], capture_output=True, check=False)


def test_notatnik_jak_program_kancelaryjny(winapp):
    okno = pulpit.OknoProgramu.polacz("notepad", winapp=winapp, dozwolone={"notepad"})
    elementy = okno.elementy()
    spis = [(e["rola"], e["opis"]) for e in elementy]
    pole = next((e for e in elementy if e["rola"].split()[0] in ("Edit", "Document")), None)
    assert pole is not None, f"brak pola tekstu wsrod: {spis}"
    assert okno.typ_pola(pole["selektor"]) == "text"

    okno.wpisz(pole["selektor"], TEKST)

    hwnd, typ, slug = pulpit._rozbierz(pole["selektor"])
    odczyt = winapp("get-value", "--window", hwnd, "--type", typ, pozycyjne=(slug,))
    assert odczyt.get("text", "").strip() == TEKST
    okno.zakoncz()
