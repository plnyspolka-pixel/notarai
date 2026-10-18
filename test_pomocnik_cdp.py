"""Testy sterowania przegladarka - na prawdziwym Chrome, nie na atrapie.

Formularze rejestrow reaguja na zdarzenia wejscia, a nie na samo ustawienie
wartosci, wiec atrapa niczego by tu nie dowiodla. Test uruchamia przegladarke
z osobnym profilem i sprawdza, co strona faktycznie zobaczyla.

Bez zainstalowanego Chrome ani Edge testy sa pomijane.
"""
import json
import os
import shutil
import subprocess
import time
import urllib.request

import pytest

from pomocnik import cdp

PORT = 9333  # inny niz roboczy 9222, zeby test nie wchodzil w droge pomocnikowi

STRONA = """<!doctype html>
<html lang="pl"><meta charset="utf-8"><title>Atrapa formularza rejestru</title>
<body>
  <form id="wniosek" onsubmit="return false">
    <input id="pesel" name="pesel">
    <input id="kw" name="kw">
    <select id="rodzaj">
      <option value="">wybierz</option>
      <option value="S">Sprzedaz</option>
      <option value="D">Darowizna</option>
    </select>
    <input type="checkbox" id="zgoda">
    <div id="uwagi" contenteditable="true"></div>
    <input id="tylko-odczyt" readonly>
    <input id="uparty">
  </form>
  <!-- Formularze rejestrow siedza w ramkach - KRZ tak wlasnie ma. -->
  <iframe id="ramka" style="width:320px;height:120px" srcdoc="
    <!doctype html><meta charset=utf-8><body>
      <input id='w-ramce'>
      <button id='szukaj-w-ramce'>Wyszukaj</button>
    </body>"></iframe>
  <form id="reszta" onsubmit="return false">
    <button id="wyslij" type="submit">Wyslij wniosek</button>
  </form>
<script>
  // Strona notuje zdarzenia tak, jak robilby to framework rejestru.
  window.__zdarzenia = [];
  for (const el of document.querySelectorAll("input, select, div[contenteditable]")) {
    for (const nazwa of ["input", "change"]) {
      el.addEventListener(nazwa, () => window.__zdarzenia.push(el.id + ":" + nazwa));
    }
  }
  // Pole, ktore kasuje wszystko, co ktos w nie wpisze - tak zachowuja sie
  // rubryki wyliczane przez formularz z innych pol.
  const uparty = document.getElementById("uparty");
  for (const nazwa of ["input", "change"]) {
    uparty.addEventListener(nazwa, () => { uparty.value = ""; });
  }
  window.__wyslano = false;
  document.getElementById("wyslij").addEventListener("click", () => { window.__wyslano = true; });
</script>
</body></html>
"""


def _sciezka_przegladarki():
    kandydaci = [
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                     "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                     "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                     "Microsoft", "Edge", "Application", "msedge.exe"),
    ]
    for kandydat in kandydaci:
        if os.path.exists(kandydat):
            return kandydat
    return shutil.which("chrome") or shutil.which("msedge") or shutil.which("google-chrome")


@pytest.fixture(scope="module")
def strona(tmp_path_factory):
    exe = _sciezka_przegladarki()
    if not exe:
        pytest.skip("Brak Chrome ani Edge - test sterowania przegladarka pominiety")

    katalog = tmp_path_factory.mktemp("przegladarka")
    plik = katalog / "formularz.html"
    plik.write_text(STRONA, encoding="utf-8")
    profil = katalog / "profil"  # osobny profil: od Chrome 136 domyslny jest zablokowany

    proces = subprocess.Popen(
        [exe, f"--remote-debugging-port={PORT}", "--remote-debugging-address=127.0.0.1",
         f"--user-data-dir={profil}", "--no-first-run", "--no-default-browser-check",
         "--headless=new", plik.as_uri()],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(40):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=1)
                break
            except OSError:
                time.sleep(0.5)
        else:
            pytest.skip("Przegladarka nie wystartowala w czasie - test pominiety")

        polaczenie, adapter = cdp.polacz("file://", port=PORT)
        try:
            yield adapter
        finally:
            polaczenie.zamknij()
    finally:
        proces.terminate()
        try:
            proces.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proces.kill()  # Chrome lubi sie ociagac z zamknieciem


def _zdarzenia(strona) -> list[str]:
    return strona._p.oblicz("window.__zdarzenia") or []


def test_wpisuje_tekst_i_strona_to_widzi(strona):
    strona.wpisz("#pesel", "85031512331")
    assert strona._p.oblicz("document.querySelector('#pesel').value") == "85031512331"
    zdarzenia = _zdarzenia(strona)
    assert "pesel:input" in zdarzenia, "strona musi zobaczyc pisanie, nie samo podstawienie wartosci"
    assert "pesel:change" in zdarzenia


def test_nadpisuje_poprzednia_wartosc(strona):
    strona.wpisz("#kw", "WA1M/00000001/1")
    strona.wpisz("#kw", "WA1M/00000002/2")
    assert strona._p.oblicz("document.querySelector('#kw').value") == "WA1M/00000002/2"


def test_wybiera_z_listy_po_nazwie(strona):
    strona.wybierz("#rodzaj", "Darowizna")
    assert strona._p.oblicz("document.querySelector('#rodzaj').value") == "D"
    assert "rodzaj:change" in _zdarzenia(strona)


def test_zaznacza_i_nie_odznacza_dwa_razy(strona):
    strona.zaznacz("#zgoda", True)
    assert strona._p.oblicz("document.querySelector('#zgoda').checked") is True
    strona.zaznacz("#zgoda", True)  # powtorzenie nie moze przelaczyc z powrotem
    assert strona._p.oblicz("document.querySelector('#zgoda').checked") is True


def test_wpisuje_do_pola_edytowalnego(strona):
    strona.wpisz("#uwagi", "Akt z dnia 21 wrzesnia")
    assert strona._p.oblicz("document.querySelector('#uwagi').textContent") == "Akt z dnia 21 wrzesnia"


def test_istnieje_rozroznia_pola(strona):
    assert strona.istnieje("#pesel") is True
    assert strona.istnieje("#nie-ma-takiego") is False


def test_brak_pola_konczy_sie_czytelnym_bledem(strona):
    with pytest.raises(cdp.BladPrzegladarki) as blad:
        strona.wpisz("#nie-ma-takiego", "cokolwiek")
    assert "ramce" in str(blad.value), "komunikat ma podpowiadac najczestsza przyczyne"


def test_brak_pozycji_na_liscie_konczy_sie_bledem(strona):
    with pytest.raises(cdp.BladPrzegladarki):
        strona.wybierz("#rodzaj", "Zamiana")


def test_pole_tylko_do_odczytu_dostaje_wartosc_zapasowa(strona):
    """Rejestry blokuja klawiature w rubrykach wypelnianych po wyborze z listy.
    Pisanie tam nic nie daje, wiec podstawiamy wartosc wprost."""
    strona.wpisz("#tylko-odczyt", "WA1M/00000003/3")
    assert strona.odczytaj("#tylko-odczyt") == "WA1M/00000003/3"


def test_pole_ktore_odrzuca_wpis_konczy_sie_bledem(strona):
    """Gdy formularz sam kasuje wartosc, pomocnik ma to zglosic, a nie udawac,
    ze wpisal. Notariusz musi wiedziec, ze rubryka zostala pusta."""
    with pytest.raises(cdp.BladPrzegladarki) as blad:
        strona.wpisz("#uparty", "cokolwiek")
    assert "nie przyjelo" in str(blad.value)


class TestRamek:
    """Formularz rejestru zwykle siedzi w iframe. Kod wykonany w dokumencie
    glownym nie widzi jego pol w ogole - i to wyglada jak brak pola, a nie jak
    zle miejsce szukania."""

    def test_dokument_glowny_nie_widzi_pola_z_ramki(self, strona):
        assert strona.istnieje("#w-ramce") is False

    def test_znajduje_ramke_po_zawartosci(self, strona):
        ramka = strona.ramka_z("#w-ramce", sekundy=10)
        assert ramka.istnieje("#w-ramce") is True

    def test_wpisuje_do_pola_w_ramce(self, strona):
        ramka = strona.ramka_z("#w-ramce", sekundy=10)
        ramka.wpisz("#w-ramce", "44051401359")
        assert ramka.odczytaj("#w-ramce") == "44051401359"

    def test_elementy_ramki_to_elementy_ramki(self, strona):
        ramka = strona.ramka_z("#w-ramce", sekundy=10)
        opisy = [e["opis"] for e in ramka.elementy()]
        assert any("Wyszukaj" in o for o in opisy)
        assert not any("Wyslij wniosek" in o for o in opisy), \
            "ramka nie moze zwracac elementow dokumentu glownego"

    def test_brak_formularza_konczy_sie_czytelnym_bledem(self, strona):
        with pytest.raises(cdp.BladPrzegladarki, match="ani w zadnej ramce"):
            strona.ramka_z("#czegos-takiego-nie-ma", sekundy=1)


def test_nic_nie_zostalo_wyslane(strona):
    """Najwazniejszy test calego pomocnika: wypelnia, ale nie wysyla."""
    assert strona._p.oblicz("window.__wyslano") is False
