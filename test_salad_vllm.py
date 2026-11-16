"""Testy jednostkowe tools/agent_factory/salad_vllm.py - bez sieci i bez kluczy.

Tylko dane syntetyczne; nie czyta `dane/`, `.env` ani prawdziwych kluczy.
"""
from datetime import datetime, timedelta, timezone

import pytest

from tools.agent_factory.salad_vllm import (
    SaladError,
    create_body,
    gpu_classes,
    group_path,
    load_keys,
)

KEYS = {"SALAD_API_KEY": "klucz-testowy", "SALAD_ORG": "org-test", "SALAD_PROJECT": "projekt-test"}


# ------------------------------------------------------------------ group_path

@pytest.mark.parametrize("name", [
    "koder-test",        # brak przedrostka notarai-koder
    "notarai-koder!",    # niedozwolony znak
    "Notarai-koder-x",   # wielka litera - razi wzorzec nazwy
    "notarai_koder",     # podkreślenie
])
def test_group_path_odrzucenie(name):
    with pytest.raises(SaladError):
        group_path(KEYS, name)


def test_group_path_poprawna():
    sciezka = group_path(KEYS, "notarai-koder-7")
    assert sciezka == "/organizations/org-test/projects/projekt-test/containers/notarai-koder-7"


# ------------------------------------------------------------------ create_body

class Args:
    model = "syntetyczny/model-8B"
    parser = "syntetyczny_xml"
    image = "vllm/syntetyczny:1"
    context = 32768
    priority = "high"
    vllm_args = "--reasoning-parser syntetyczny"


def test_create_body_command_i_deadline():
    deadline = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    body = create_body("notarai-koder-1", "gpu-test", Args(), deadline)

    cmd = body["container"]["command"]
    assert "--host" in cmd and cmd[cmd.index("--host") + 1] == "::"
    assert "--port" in cmd and cmd[cmd.index("--port") + 1] == "8000"
    assert "--served-model-name" in cmd and cmd[cmd.index("--served-model-name") + 1] == "koder"
    assert "--tool-call-parser" in cmd
    assert cmd[cmd.index("--tool-call-parser") + 1] == "syntetyczny_xml"

    assert body["name"] == "notarai-koder-1"
    assert body["container"]["resources"]["gpu_classes"] == ["gpu-test"]
    # KODER_DEADLINE w formacie ISO
    from datetime import datetime as dt
    assert dt.fromisoformat(body["container"]["environment_variables"]["KODER_DEADLINE"]) == deadline


def test_create_body_networking():
    deadline = datetime.now(timezone.utc) + timedelta(hours=2)
    body = create_body("notarai-koder-1", "gpu-test", Args(), deadline)
    net = body["networking"]
    assert net["auth"] is True
    assert net["client_request_timeout"] == 100000
    assert net["server_response_timeout"] == 100000
    assert net["port"] == 8000


# ------------------------------------------------------------------ load_keys

def test_load_keys_brak_klucza(monkeypatch):
    for z in ("SALAD_API_KEY", "SALAD_ORG", "SALAD_PROJECT", "NOTARAI_SALAD_ENV"):
        monkeypatch.delenv(z, raising=False)
    with pytest.raises(SaladError):
        load_keys()


def test_load_keys_plik_i_priorytet_srodowiska(monkeypatch, tmp_path):
    plik = tmp_path / "salad.test.env"
    plik.write_text(
        "SALAD_API_KEY=klucz-z-pliku\n"
        "SALAD_ORG=org-z-pliku\n"
        "SALAD_PROJECT=projekt-z-pliku\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("NOTARAI_SALAD_ENV", str(plik))
    monkeypatch.delenv("SALAD_API_KEY", raising=False)
    # środowisko ma pierwszeństwo przed plikiem
    monkeypatch.setenv("SALAD_API_KEY", "ze_srodowiska_api")

    keys = load_keys()
    assert keys["SALAD_API_KEY"] == "ze_srodowiska_api"
    assert keys["SALAD_ORG"] == "org-z-pliku"
    assert keys["SALAD_PROJECT"] == "projekt-z-pliku"


def test_load_keys_wszystko_z_pliku(monkeypatch, tmp_path):
    plik = tmp_path / "tylko.env"
    plik.write_text(
        "SALAD_API_KEY=tylko_plik\nSALAD_ORG=org-x\nSALAD_PROJECT=projekt-x\n",
        encoding="utf-8",
    )
    for z in ("SALAD_API_KEY", "SALAD_ORG", "SALAD_PROJECT"):
        monkeypatch.delenv(z, raising=False)
    monkeypatch.setenv("NOTARAI_SALAD_ENV", str(plik))
    keys = load_keys()
    assert keys == {"SALAD_API_KEY": "tylko_plik", "SALAD_ORG": "org-x",
                    "SALAD_PROJECT": "projekt-x"}


# ------------------------------------------------------------------ gpu_classes

def test_gpu_classes(monkeypatch):
    import tools.agent_factory.salad_vllm as mod
    items = {
        "items": [
            {"id": "a", "name": "AMD RX 7900 XTX (24GB)",
             "prices": [{"priority": "high", "price": "2.50"},
                        {"priority": "low", "price": "1.00"}]},
            {"id": "b", "name": "RTX 5090 (32 GB)",
             "prices": [{"priority": "high", "price": "3.20"}]},
            # bez ceny dla priorytetu "high" - musi być pominięte
            {"id": "c", "name": "RTX 4090 (24 GB)",
             "prices": [{"priority": "low", "price": "1.80"}]},
            # bez podanego VRAM - pominięte
            {"id": "d", "name": "MysticCard", "prices": [{"priority": "high", "price": "9.99"}]},
        ]
    }
    def api_podmiana(keys, method, path, body=None, allow404=False):
        return items

    monkeypatch.setattr(mod, "api", api_podmiana)
    out = mod.gpu_classes(KEYS, "high")

    assert [c["name"] for c in out] == ["RTX 5090 (32 GB)", "AMD RX 7900 XTX (24GB)"]
    assert [c["vram"] for c in out] == [32, 24]          # sortowanie malejąco po VRAM
    assert [c["usd_h"] for c in out] == [3.20, 2.50]
    assert [c["id"] for c in out] == ["b", "a"]
    assert (mod.api is not None)  # sanity
