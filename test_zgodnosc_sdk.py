"""Zgodnosc zadan do Bedrock z wersja SDK, ktora jedzie na produkcje.

Zgloszenie 23.11.2026: "Sporzadz projekt" -> "Blad modelu (ParamValidationError)".
boto3 przypiete w requirements.txt (1.35.90) nie znalo bloku cachePoint, a testy
tego nie widzialy, bo atrapa klienta przyjmowala dowolne parametry.

Tu kazda sciezka, ktora buduje zadanie do modelu, przechodzi przez walidacje
botocore z modelu API zainstalowanej wersji. CI instaluje boto3 z requirements.txt
(ta sama wersja co obraz aplikacji - Dockerfile), wiec zadanie, ktorego SDK na
produkcji nie przyjmie, wywraca testy, zanim trafi na master.
"""
import os
import re
from importlib.metadata import version
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import bedrock
import dokumenty
from conftest import sprawdz_zgodnosc_z_api_bedrock

MODELE = [
    "eu.anthropic.claude-opus-4-6-v1",       # myslenie adaptacyjne + output_config
    "eu.anthropic.claude-sonnet-4-5-20250929-v1:0",  # myslenie z budzetem
    "eu.anthropic.claude-opus-5",
]


def _strumien_ok(**kw):
    return {"stream": iter([
        {"contentBlockDelta": {"delta": {"text": "=== STRONA 1 ===\nTYP: t\n---\nok"}}},
        {"messageStop": {"stopReason": "end_turn"}},
        {"metadata": {"usage": {"inputTokens": 1, "outputTokens": 1}}},
    ])}


@pytest.fixture
def klient(monkeypatch):
    """Klient, ktory przed "wyslaniem" waliduje zadanie jak prawdziwe botocore."""
    k = MagicMock()

    def converse_stream(**kw):
        sprawdz_zgodnosc_z_api_bedrock("ConverseStream", kw)
        return _strumien_ok(**kw)
    k.converse_stream.side_effect = converse_stream
    monkeypatch.setattr(bedrock, "_klient", lambda: k)
    monkeypatch.setattr(bedrock, "_cache_wylaczony", False)
    monkeypatch.setattr(bedrock.config, "CACHE_PROMPTU", True)
    return k


def _punkty_cache(k) -> int:
    return sum(1 for t in k.converse_stream.call_args.kwargs["messages"]
               for b in t["content"] if "cachePoint" in b)


@pytest.mark.parametrize("model", MODELE)
@pytest.mark.parametrize("myslenie", [True, False])
def test_projekt_z_cache_przechodzi_walidacje_sdk(klient, monkeypatch, model, myslenie):
    monkeypatch.setattr(bedrock.config, "MODEL", model)
    monkeypatch.setattr(bedrock.config, "MYSLENIE", myslenie)
    bedrock.sporzadz_projekt("WZOR [IMIE]", [{"nazwa": "imie", "wartosc": "Jan"}], "umowa")
    # punkt cache dotarl do zadania i SDK go przyjelo (bez cichego obejscia)
    assert _punkty_cache(klient) == 1
    assert bedrock._cache_wylaczony is False


def test_rozmowa_z_historia_i_cache_przechodzi_walidacje_sdk(klient):
    bedrock.rozmawiaj("KONTEKST", [{"rola": "uzytkownik", "tresc": "a"},
                                   {"rola": "asystent", "tresc": "b"}], "pytanie")
    assert _punkty_cache(klient) >= 1


def test_transkrypcja_z_obrazami_przechodzi_walidacje_sdk(klient, monkeypatch):
    monkeypatch.setattr(dokumenty, "obrazy_strony",
                        lambda s: {"calosc": b"\x89PNG", "pasy": [b"\x89PNG"], "tekst": ""})
    bedrock.transkrybuj_paczke([{"dokument": "a.pdf", "strona": 1}])
    tresc = klient.converse_stream.call_args.kwargs["messages"][-1]["content"]
    assert any("image" in b for b in tresc)


@pytest.mark.skipif(not os.getenv("CI"), reason="tylko w CI: lokalnie moze byc inna wersja boto3")
def test_ci_testuje_wersje_boto3_z_obrazu():
    """W CI testujemy dokladnie te wersje boto3, ktora instaluje Dockerfile."""
    przypiete = re.search(r"^boto3==(\S+)$", Path("requirements.txt").read_text(), re.M)
    assert przypiete, "boto3 musi byc przypiete (==) w requirements.txt"
    assert version("boto3") == przypiete.group(1)


def test_dockerfile_instaluje_zaleznosci_z_requirements():
    dockerfile = Path("Dockerfile").read_text()
    assert "requirements.txt" in dockerfile and "pip install" in dockerfile


def test_tura_z_narzedziami_asystenta_przechodzi_walidacje_sdk(monkeypatch):
    """Asystent kancelarii: Converse z toolConfig i blokami toolUse/toolResult."""
    import asystent_kancelarii
    k = MagicMock()

    def converse(**kw):
        sprawdz_zgodnosc_z_api_bedrock("Converse", kw)
        return {"output": {"message": {"role": "assistant", "content": [{"text": "ok"}]}},
                "stopReason": "end_turn", "usage": {"inputTokens": 1, "outputTokens": 1}}
    k.converse.side_effect = converse
    monkeypatch.setattr(bedrock, "_klient", lambda: k)
    tury = [
        {"role": "user", "content": [{"text": "zostawiaj znak zapytania"}]},
        {"role": "assistant", "content": [{"toolUse": {"toolUseId": "t1", "name": "pokaz_ustawienia", "input": {}}}]},
        {"role": "user", "content": [{"toolResult": {"toolUseId": "t1", "content": [{"json": {"ogolne": {}}}]}}]},
    ]
    for model in MODELE:
        monkeypatch.setattr(bedrock.config, "MODEL", model)
        assert bedrock.tura_z_narzedziami(asystent_kancelarii.SYSTEM, tury,
                                          asystent_kancelarii.NARZEDZIA)["powod"] == "end_turn"
