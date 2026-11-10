"""Wersja web aplikacji klienta pod /aplikacja: statyczny eksport Expo
(mobilna/dist) serwowany przez app.py z powrotem do index.html dla tras
routera, bez logowania takze w trybie wielu kancelarii."""
import pytest
from fastapi.testclient import TestClient

import app as aplikacja
import autoryzacja

INDEKS = '<!doctype html><title>notarai</title><script src="/aplikacja/_expo/static/js/web/entry-abc.js"></script>'


@pytest.fixture
def dist(tmp_path, monkeypatch):
    katalog = tmp_path / "dist"
    (katalog / "_expo" / "static" / "js" / "web").mkdir(parents=True)
    (katalog / "index.html").write_text(INDEKS, "utf-8")
    (katalog / "_expo" / "static" / "js" / "web" / "entry-abc.js").write_text("console.log(1)", "utf-8")
    (katalog / "_expo" / "static" / "js" / "web" / "[id]-def.js").write_text("console.log(2)", "utf-8")
    (katalog / "favicon.ico").write_bytes(b"\x00\x00\x01\x00")
    (tmp_path / "tajne.txt").write_text("poza dist", "utf-8")
    monkeypatch.setattr(aplikacja, "APLIKACJA_WEB", katalog)
    return katalog


@pytest.fixture
def klient():
    return TestClient(aplikacja.app)


def test_bez_zbudowanej_wersji_404(tmp_path, monkeypatch, klient):
    monkeypatch.setattr(aplikacja, "APLIKACJA_WEB", tmp_path / "brak")
    assert klient.get("/aplikacja/").status_code == 404
    assert klient.get("/aplikacja/wizyty").status_code == 404


@pytest.mark.parametrize("sciezka", ["/aplikacja", "/aplikacja/", "/aplikacja/wizyty",
                                     "/aplikacja/kancelaria/demo-lublin", "/aplikacja/rezerwacja?id=1"])
def test_trasy_routera_dostaja_index(dist, klient, sciezka):
    odp = klient.get(sciezka)
    assert odp.status_code == 200
    assert odp.text == INDEKS
    assert odp.headers["cache-control"] == "no-cache"


def test_pliki_z_hashem_na_dlugo(dist, klient):
    odp = klient.get("/aplikacja/_expo/static/js/web/entry-abc.js")
    assert odp.status_code == 200 and odp.text == "console.log(1)"
    assert "immutable" in odp.headers["cache-control"]
    # expo-router nazywa paczki tras dynamicznych z nawiasami: [id]-hash.js
    assert klient.get("/aplikacja/_expo/static/js/web/%5Bid%5D-def.js").text == "console.log(2)"
    ikona = klient.get("/aplikacja/favicon.ico")
    assert ikona.status_code == 200 and "immutable" not in ikona.headers["cache-control"]


def test_brakujacy_plik_to_404_a_nie_index(dist, klient):
    assert klient.get("/aplikacja/_expo/static/js/web/entry-stary.js").status_code == 404
    assert klient.get("/aplikacja/assets/ikona.png").status_code == 404
    assert klient.get("/aplikacja/logo.png").status_code == 404


def test_nie_wychodzi_poza_dist(dist, klient):
    for sciezka in ("/aplikacja/..%2Ftajne.txt", "/aplikacja/%2E%2E/tajne.txt", "/aplikacja/../tajne.txt"):
        odp = klient.get(sciezka)
        assert "poza dist" not in odp.text


def test_otwarta_bez_logowania_w_trybie_wielu_kancelarii(dist, klient, monkeypatch):
    monkeypatch.setattr(autoryzacja, "MULTI", True)
    assert klient.get("/aplikacja/wizyty").status_code == 200
    assert klient.get("/aplikacja/_expo/static/js/web/entry-abc.js").status_code == 200
    # Otwarte jest API klienta, nie wszystko, co zaczyna sie od /api/klient
    assert klient.get("/api/klienci").status_code == 401
    assert klient.get("/api/sprawy").status_code == 401


def test_linki_do_aplikacji_na_stronie_i_mapie():
    from pathlib import Path
    korzen = Path(__file__).parent
    strona = (korzen / "strona" / "index.html").read_text("utf-8")
    assert 'href="https://app.notarai.pl/aplikacja/">Umów wizytę w aplikacji' in strona
    mapa = (korzen / "static" / "notariusze.html").read_text("utf-8")
    assert 'href="/aplikacja/">Umów wizytę w aplikacji' in mapa
