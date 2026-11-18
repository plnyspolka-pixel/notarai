"""Projekt aktu pisze sie do kilkunastu minut. Stan pracy lezy przy sprawie
(projekt-stan.json, w S3 razem ze sprawa), wiec:
- drugie urzadzenie i odswiezona strona widza, ze projekt sie pisze,
- nie da sie go zlecic drugi raz w trakcie,
- serwer konczy projekt takze po rozlaczeniu przegladarki.
Atrapa modelu, dane fikcyjne."""
import json
import threading
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import app as aplikacja
import config

STRUMIEN = {"Accept": "application/x-ndjson"}
SPRAWA = "def456def456"


@pytest.fixture
def klient(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SPRAWY", tmp_path)
    katalog = tmp_path / SPRAWA
    katalog.mkdir()
    (katalog / "wzor.txt").write_text("aaa - sprzedajaca\n\nAKT NOTARIALNY\naaa sprzedaje lokal za ?? zl.", "utf-8")
    (katalog / "sprawa.json").write_text(json.dumps({"id": SPRAWA, "nazwa": "Nowak", "skany": []}), "utf-8")
    return TestClient(aplikacja.app), katalog


def _linie(odp):
    return [json.loads(l) for l in odp.text.splitlines() if l.strip()]


def test_bez_projektu_stan_brak(klient):
    k, _ = klient
    assert k.get(f"/api/sprawy/{SPRAWA}/projekt/stan").json() == {"stan": "brak"}
    assert k.get(f"/api/sprawy/{SPRAWA}").json()["projekt_stan"] == {"stan": "brak"}


def test_w_trakcie_widac_stan_i_drugie_zlecenie_odrzucone(klient):
    k, _ = klient
    start, puszczaj = threading.Event(), threading.Event()

    def wolny_model(*a, **kw):
        start.set()
        puszczaj.wait(10)
        return "AKT NOTARIALNY\nIrena Nowak sprzedaje lokal za <<BRAK: cena>> zł."

    wynik = {}
    with patch("bedrock.sporzadz_projekt", side_effect=wolny_model):
        watek = threading.Thread(target=lambda: wynik.setdefault("odp", k.post(
            f"/api/sprawy/{SPRAWA}/projekt", headers=STRUMIEN, json={"pola": [], "polecenie": ""})))
        watek.start()
        assert start.wait(10)
        stan = k.get(f"/api/sprawy/{SPRAWA}/projekt/stan").json()
        assert stan["stan"] == "w_toku" and stan["od"] and stan["sekund"] >= 0
        assert k.get(f"/api/sprawy/{SPRAWA}").json()["projekt_stan"]["stan"] == "w_toku"
        drugie = k.post(f"/api/sprawy/{SPRAWA}/projekt", json={"pola": [], "polecenie": ""})
        assert drugie.status_code == 409 and "już się sporządza" in drugie.json()["detail"]
        puszczaj.set()
        watek.join(10)
    linie = _linie(wynik["odp"])
    assert linie[0] == {"postep": {"etap": "projekt", "gotowe": 0, "wszystkie": 1}}
    assert linie[-1]["wynik"]["brakujace"] == 1 and "sekund" in linie[-1]["wynik"]
    stan = k.get(f"/api/sprawy/{SPRAWA}/projekt/stan").json()
    assert stan["stan"] == "gotowy" and stan["do"] >= stan["od"]


def test_blad_modelu_zapisany_w_stanie(klient):
    k, _ = klient
    with patch("bedrock.sporzadz_projekt", side_effect=RuntimeError("awaria")):
        odp = k.post(f"/api/sprawy/{SPRAWA}/projekt", headers=STRUMIEN, json={"pola": [], "polecenie": ""})
    assert _linie(odp)[-1]["kod"] == 502
    stan = k.get(f"/api/sprawy/{SPRAWA}/projekt/stan").json()
    assert stan["stan"] == "blad" and stan["kod"] == 502
    # Po bledzie mozna sprobowac ponownie.
    with patch("bedrock.sporzadz_projekt", return_value="AKT"):
        assert k.post(f"/api/sprawy/{SPRAWA}/projekt", json={"pola": [], "polecenie": ""}).status_code == 200


def test_porzucony_stan_nie_blokuje_na_zawsze(klient):
    """Restart kontenera w trakcie pracy zostawia "w_toku" - po 2 h to juz nie blokuje."""
    k, katalog = klient
    dawno = (datetime.now() - timedelta(hours=3)).isoformat(timespec="seconds")
    (katalog / "projekt-stan.json").write_text(json.dumps({"stan": "w_toku", "od": dawno}), "utf-8")
    assert k.get(f"/api/sprawy/{SPRAWA}/projekt/stan").json()["stan"] == "przerwany"
    with patch("bedrock.sporzadz_projekt", return_value="AKT"):
        assert k.post(f"/api/sprawy/{SPRAWA}/projekt", json={"pola": [], "polecenie": ""}).status_code == 200


def test_zdjecie_do_plikow_nie_uruchamia_odczytu(klient):
    """Scena 05: zdjecie aparatem trafia do plikow sprawy i nic wiecej - bez
    odczytu modelem i bez zmiany odczytanych pol."""
    k, katalog = klient
    (katalog / "odczyt.json").write_text(json.dumps({"pola": [{"nazwa": "aaa", "wartosc": "Irena Nowak"}]}), "utf-8")
    przed = (katalog / "odczyt.json").read_text("utf-8")
    with patch("bedrock.odczytaj_sprawe") as odczyt, patch("bedrock.sporzadz_projekt") as projekt, \
            patch("bedrock.rozmawiaj") as rozmowa:
        odp = k.post(f"/api/sprawy/{SPRAWA}/pliki",
                     files=[("pliki", ("zdjecie-20261116-0904.jpg", b"\xff\xd8\xff\xe0JPEG", "image/jpeg"))])
    assert odp.status_code == 200 and [p["nazwa"] for p in odp.json()] == ["zdjecie-20261116-0904.jpg"]
    assert not odczyt.called and not projekt.called and not rozmowa.called
    assert (katalog / "odczyt.json").read_text("utf-8") == przed
    assert (katalog / "zalaczniki" / "zdjecie-20261116-0904.jpg").read_bytes().startswith(b"\xff\xd8")
