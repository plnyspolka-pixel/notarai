"""Tresc spraw moze isc tylko do modeli zatwierdzonych (zerowa retencja).

Pilnuje trzech warstw: lista w config, hak na kliencie Bedrock (kazde wywolanie)
i szablon IAM. Dopisanie modelu wymaga zmiany wszystkich trzech swiadomie.
"""
import re
from pathlib import Path

import boto3
import pytest

import bedrock
import config

ZATWIERDZONE = {"eu.anthropic.claude-opus-4-6-v1", "eu.anthropic.claude-sonnet-4-6"}
SZABLON_IAM = Path(__file__).parent / "infra" / "notarai-s3.yaml"


def test_lista_zatwierdzonych_modeli():
    assert config.ZATWIERDZONE_MODELE == ZATWIERDZONE


def test_domyslne_modele_w_kodzie_sa_zatwierdzone():
    import anonimizacja, kalkulator, poswiadczenia, tokenomia
    domyslne = {tokenomia.MODEL_GLOWNY, tokenomia.MODEL_KALKULATORA, kalkulator.MODEL_DOMYSLNY,
                poswiadczenia.MODEL_DOMYSLNY, anonimizacja.MODEL_DOMYSLNY}
    assert domyslne <= ZATWIERDZONE


@pytest.mark.parametrize("model", [
    "eu.anthropic.claude-opus-5", "eu.anthropic.claude-sonnet-5", "global.anthropic.claude-fable-5",
    "us.anthropic.claude-opus-4-6-v1", "anthropic.claude-opus-4-6-v1", "", None,
])
def test_hak_odrzuca_model_niezatwierdzony(model):
    with pytest.raises(bedrock.ModelNiezatwierdzony):
        bedrock._pilnuj_modelu({"modelId": model})


@pytest.mark.parametrize("model", sorted(ZATWIERDZONE))
def test_hak_przepuszcza_model_zatwierdzony(model):
    bedrock._pilnuj_modelu({"modelId": model})


def test_hak_jest_podpiety_do_prawdziwego_klienta(monkeypatch):
    """Wywolanie niezatwierdzonego modelu pada przed wyslaniem (zadnej sieci)."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setattr(bedrock, "_klient_bedrock", None)
    monkeypatch.setattr(config, "PROFIL_AWS", "")
    klient = bedrock._klient()
    try:
        with pytest.raises(bedrock.ModelNiezatwierdzony):
            klient.converse(modelId="eu.anthropic.claude-opus-5",
                            messages=[{"role": "user", "content": [{"text": "x"}]}])
    finally:
        monkeypatch.setattr(bedrock, "_klient_bedrock", None)


def test_szablon_iam_nie_ma_wzorca_ani_obcych_modeli():
    tresc = SZABLON_IAM.read_text(encoding="utf-8")
    blok = tresc[tresc.index("Sid: BedrockProfileEU"):tresc.index("Sid: TranscribeStenogramyEU")]
    assert "inference-profile/eu.*" not in blok and "foundation-model/*" not in blok
    profile = set(re.findall(r"inference-profile/(eu\.[a-z0-9.\-]+)", blok))
    assert profile == ZATWIERDZONE
    bazowe = {m.removeprefix("eu.") for m in ZATWIERDZONE}
    assert set(re.findall(r"foundation-model/([a-z0-9.\-]+)", blok)) == bazowe
