"""Testy izolowane: zadne prawdziwe polaczenie z AWS i brak danych kancelarii."""
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import autoryzacja
import polly_tts


@pytest.fixture
def dostep(monkeypatch):
    monkeypatch.setattr(polly_tts, "WLACZONE", True)
    monkeypatch.setattr(polly_tts, "REGION", "eu-central-1")
    monkeypatch.setattr(autoryzacja, "MULTI", True)
    polly_tts.limit.wyczysc()
    return SimpleNamespace(state=SimpleNamespace(kancelaria="fikcyjna", email="test@example.invalid", serwis=False))


def test_polskie_glosy_poprawne_silniki():
    assert set(polly_tts.GLOSY["Ola"]) == {"neural", "generative"}
    assert "generative" in polly_tts.GLOSY["Ewa"]
    assert polly_tts.GLOSY["Jacek"] == ("standard",)


def test_generuje_mp3_eu_i_nie_wysyla_ssml(dostep, monkeypatch):
    class Klient:
        def synthesize_speech(self, **args):
            assert args == {
                "Text": "§ 1. Projekt aktu.",
                "TextType": "text",
                "VoiceId": "Ola",
                "Engine": "generative",
                "LanguageCode": "pl-PL",
                "OutputFormat": "mp3",
            }
            return {"AudioStream": BytesIO(b"ID3-demo-audio")}
    monkeypatch.setattr(polly_tts, "_klient", lambda: Klient())
    wynik = polly_tts.synteza(polly_tts.Synteza(tekst="§ 1. Projekt aktu."), dostep)
    assert wynik.status_code == 200
    assert wynik.body == b"ID3-demo-audio"
    assert wynik.media_type == "audio/mpeg"
    assert "no-store" in wynik.headers["cache-control"]


@pytest.mark.parametrize("glos,silnik", [("Jacek", "generative"), ("Ola", "standard"), ("Unknown", "neural")])
def test_odrzuca_niedozwolony_glos(dostep, monkeypatch, glos, silnik):
    monkeypatch.setattr(polly_tts, "_klient", lambda: pytest.fail("Nie wolno wywolywac AWS"))
    with pytest.raises(HTTPException) as blad:
        polly_tts.synteza(polly_tts.Synteza(tekst="Fikcyjny fragment", glos=glos, silnik=silnik), dostep)
    assert blad.value.status_code == 422


def test_odrzuca_region_poza_frankfurtem(dostep, monkeypatch):
    monkeypatch.setattr(polly_tts, "REGION", "us-east-1")
    with pytest.raises(HTTPException) as blad:
        polly_tts.synteza(polly_tts.Synteza(tekst="Fragment"), dostep)
    assert blad.value.status_code == 503


def test_nie_pozwala_na_dostep_serwisowy(dostep):
    dostep.state.serwis = True
    with pytest.raises(HTTPException) as blad:
        polly_tts.synteza(polly_tts.Synteza(tekst="Fragment"), dostep)
    assert blad.value.status_code == 403


def test_brak_zalogowania_blokuje(dostep):
    dostep.state.email = ""
    with pytest.raises(HTTPException) as blad:
        polly_tts.konfiguracja(dostep)
    assert blad.value.status_code == 403


def test_brak_aktywacji_blokuje(dostep, monkeypatch):
    monkeypatch.setattr(polly_tts, "WLACZONE", False)
    with pytest.raises(HTTPException) as blad:
        polly_tts.synteza(polly_tts.Synteza(tekst="Fragment"), dostep)
    assert blad.value.status_code == 503


def test_dlugosc_tekstu_jest_ograniczona():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        polly_tts.Synteza(tekst="x" * (polly_tts.MAKS_ZNAKOW + 1))


def test_uprawnienie_zespolu():
    import stanowiska
    assert stanowiska.wymagane("POST", "/api/polly/synteza") == "projekt"
