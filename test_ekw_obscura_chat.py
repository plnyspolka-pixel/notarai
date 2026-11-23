"""Zwykle polecenie w czacie sprawy korzysta z kontrolowanego przeplywu EKW."""
from fastapi.testclient import TestClient
from fastapi import HTTPException
import pytest

import app as notarai
import bedrock
import config

KW = "WA4M/00160286/2"


@pytest.fixture
def klient(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SPRAWY", tmp_path)
    katalog = tmp_path / "abc123"
    katalog.mkdir()
    (katalog / "kontekst.txt").write_text("Dane sprawy z KW " + KW, encoding="utf-8")
    return TestClient(notarai.app)


def _ksiega():
    return {"numer_kw": KW, "zrodlo": "Obscura MCP stealth",
            "dzialy": [{"oznaczenie": x, "pusty": x != "IV"} for x in
                       ("I-O", "I-Sp", "II", "III", "IV")]}


def test_tekst_uruchamia_audytowana_sciezke_ekw(klient, monkeypatch):
    wywolania = []
    def pobierz(identyfikator, zadanie):
        wywolania.append((identyfikator, zadanie.numer_kw, zadanie.potwierdzam))
        return {"ksiega": _ksiega()}
    monkeypatch.setattr(notarai, "pobierz_ksiege", pobierz)
    monkeypatch.setattr(bedrock, "rozmawiaj", lambda *a, **k: pytest.fail("LLM must not fake registry results"))
    odp = klient.post("/api/sprawy/abc123/rozmowa", json={"tresc": "Sprawdź hipotekę w tej sprawie"})
    assert odp.status_code == 200
    assert wywolania == [("abc123", KW, True)]
    assert "Dział IV: są wpisy" in odp.json()["odpowiedz"]
    assert "Rozmowa" not in odp.json()["odpowiedz"]


def test_waf_odmowa_bez_falszywego_sukcesu(klient, monkeypatch):
    def odmowa(*args):
        raise HTTPException(502, "Portal EKW zablokowal automatyczny odczyt")
    monkeypatch.setattr(notarai, "pobierz_ksiege", odmowa)
    odp = klient.post("/api/sprawy/abc123/rozmowa", json={"tresc": f"Sprawdź KW {KW}"})
    assert odp.status_code == 200
    assert "Nie udalo sie sprawdzic KW" in odp.json()["odpowiedz"]
    assert "Pobrano aktualną" not in odp.json()["odpowiedz"]
