"""Aplikacja nie startuje z regionem AWS ani modelem spoza Unii Europejskiej."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent


def _start(**env):
    srodowisko = {k: v for k, v in os.environ.items() if k not in ("AWS_REGION", "PIECZAPP_MODEL")}
    srodowisko.update(env)
    return subprocess.run([sys.executable, "-c", "import config"], cwd=ROOT, env=srodowisko,
                          capture_output=True, text=True)


@pytest.mark.parametrize("region", ["eu-central-1", "eu-west-1", "eu-west-3", "eu-north-1"])
def test_regiony_ue_startuja(region):
    assert _start(AWS_REGION=region).returncode == 0


@pytest.mark.parametrize("region", [
    "us-east-1", "us-west-2", "ap-southeast-1",
    "eu-west-2",     # Londyn - poza UE mimo prefiksu eu-
    "eu-central-2",  # Zurych - poza UE mimo prefiksu eu-
])
def test_region_spoza_ue_blokuje_start(region):
    wynik = _start(AWS_REGION=region)
    assert wynik.returncode != 0
    assert "nie lezy w Unii Europejskiej" in wynik.stderr


def test_model_spoza_profilu_eu_blokuje_start():
    wynik = _start(AWS_REGION="eu-central-1", PIECZAPP_MODEL="us.anthropic.claude-opus-4-6-v1")
    assert wynik.returncode != 0
    assert "nie jest profilem EU" in wynik.stderr
