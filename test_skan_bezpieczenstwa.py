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
    skan.limit_luki.wyczysc()
    skan._kev_cache["ts"] = 0.0
    skan._kev_cache["dane"] = None
    monkeypatch.setattr(skan, "TRANSPORT", None)
    return TestClient(aplikacja.app)


KEV_PROBKA = {"vulnerabilities": [
    {"cveID": "CVE-2026-96951", "vendorProject": "Microsoft", "product": "Windows",
     "vulnerabilityName": "Windows Shell Security Feature Bypass", "dateAdded": "2026-10-13",
     "shortDescription": "Windows Shell contains a security feature bypass vulnerability."},
    {"cveID": "CVE-2026-11111", "vendorProject": "Microsoft", "product": "Office",
     "vulnerabilityName": "Office RCE", "dateAdded": "2026-01-01", "shortDescription": "Office."},
    {"cveID": "CVE-2026-22222", "vendorProject": "Adobe", "product": "Acrobat",
     "vulnerabilityName": "Acrobat", "dateAdded": "2026-02-02", "shortDescription": "Acrobat."},
    {"cveID": "CVE-2025-00001", "vendorProject": "Microsoft", "product": "Windows 10",
     "vulnerabilityName": "Older Windows bug", "dateAdded": "2025-09-01", "shortDescription": "Older."},
]}


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


def test_luki_tylko_windows_z_kev(k, monkeypatch):
    monkeypatch.setattr(skan, "TRANSPORT", httpx.MockTransport(lambda z: httpx.Response(200, json=KEV_PROBKA)))
    odp = k.get("/api/skan/luki")
    assert odp.status_code == 200
    d = odp.json()
    assert d["zrodlo"] == "CISA KEV"
    ids = [l["id"] for l in d["luki"]]
    # tylko Microsoft/Windows, bez Office i Adobe; najnowsze pierwsze
    assert ids == ["CVE-2026-96951", "CVE-2025-00001"]
    assert d["luki"][0]["url"].endswith("/CVE-2026-96951")
    assert "security feature bypass" in d["luki"][0]["opis"].lower()


def test_luki_filtr_po_dacie_konca_wsparcia(k, monkeypatch):
    monkeypatch.setattr(skan, "TRANSPORT", httpx.MockTransport(lambda z: httpx.Response(200, json=KEV_PROBKA)))
    d = k.get("/api/skan/luki", params={"po": "2025-10-14"}).json()
    ids = [l["id"] for l in d["luki"]]
    assert ids == ["CVE-2026-96951"]   # starsza (2025-09) odfiltrowana


def test_luki_snapshot_gdy_feed_pada(k, monkeypatch):
    monkeypatch.setattr(skan, "TRANSPORT", httpx.MockTransport(lambda z: httpx.Response(503)))
    d = k.get("/api/skan/luki").json()
    assert d["zrodlo"] == "snapshot"
    assert [l["id"] for l in d["luki"]] == [l["id"] for l in skan.KEV_FALLBACK]
