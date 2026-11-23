"""Backend skanu bezpieczenstwa (skan_bezpieczenstwa.py): echo IP oraz proxy
HIBP w modelu k-anonimowosci. HIBP przez atrape transportu - zero realnej sieci."""
import httpx
import pytest
from fastapi.testclient import TestClient

import app as aplikacja
import skan_bezpieczenstwa as skan


@pytest.fixture
def k(monkeypatch):
    skan.limit_hibp.wyczysc()
    monkeypatch.setattr(skan, "TRANSPORT", None)
    return TestClient(aplikacja.app)


def test_ip_zwraca_adres(k):
    odp = k.get("/api/skan/ip")
    assert odp.status_code == 200
    assert odp.json()["ip"]


def test_hibp_odrzuca_zly_prefiks(k):
    assert k.get("/api/skan/hibp-haslo", params={"prefiks": "XYZ"}).status_code == 400
    assert k.get("/api/skan/hibp-haslo", params={"prefiks": "ABCDEF"}).status_code == 400
    assert k.get("/api/skan/hibp-haslo", params={"prefiks": "ZZZZZ"}).status_code == 400


def test_hibp_przekazuje_wynik_i_wymusza_wielkie_litery(k, monkeypatch):
    trafione = []

    def obsluz(zadanie):
        trafione.append(str(zadanie.url))
        return httpx.Response(200, text="0018A45C4D1:3\nFEDCBA98765:9\n")

    monkeypatch.setattr(skan, "TRANSPORT", httpx.MockTransport(obsluz))
    odp = k.get("/api/skan/hibp-haslo", params={"prefiks": "abcde"})
    assert odp.status_code == 200
    assert "0018A45C4D1:3" in odp.text
    assert trafione and trafione[0].endswith("/range/ABCDE")


def test_do_backendu_trafia_tylko_prefiks_nie_haslo(k, monkeypatch):
    widziane = []

    def obsluz(zadanie):
        widziane.append(str(zadanie.url).rsplit("/", 1)[1])
        return httpx.Response(200, text="")

    monkeypatch.setattr(skan, "TRANSPORT", httpx.MockTransport(obsluz))
    k.get("/api/skan/hibp-haslo", params={"prefiks": "A1B2C"})
    assert widziane == ["A1B2C"]
    assert all(len(w) == 5 for w in widziane)


def test_hibp_gdy_usluga_pada(k, monkeypatch):
    monkeypatch.setattr(skan, "TRANSPORT", httpx.MockTransport(lambda z: httpx.Response(503)))
    assert k.get("/api/skan/hibp-haslo", params={"prefiks": "ABCDE"}).status_code == 502
