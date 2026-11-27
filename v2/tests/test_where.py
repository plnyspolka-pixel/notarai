"""Where the office's data lives: chosen by the office in the chat, enforced by settings."""
import json
import time

from fastapi.testclient import TestClient

from worker.api import create_app
from worker.init_vault import initialize
from worker.settings import load
from worker.speech_model import ModelDownload


def office(tmp_path):
    home = tmp_path / "home"
    token = initialize(home)
    (home / "settings.json").write_text(json.dumps(
        {"replica": {"enabled": False, "bucket": "notarai-v2-kopie", "region": "eu-central-1"}}))
    return TestClient(create_app(home)), {"Authorization": "Bearer " + token}, home


def say(client, admin, text):
    return client.post("/v2/chat", headers=admin, json={"text": text}).json()["blocks"]


def words(blocks):
    return "\n".join(b.get("text", "") for b in blocks)


def test_the_summary_names_every_place_and_offers_the_choices(tmp_path):
    client, admin, _ = office(tmp_path)
    blocks = say(client, admin, "gdzie są dane")
    said = words(blocks)
    assert "sejfie na tym komputerze" in said and "Frankfurt" in said and "wyłączona" in said
    labels = [i["label"] for b in blocks if b["type"] == "buttons" for i in b["items"]]
    assert {"Na tym komputerze", "We Frankfurcie, bez zapisu", "Co godzinę", "Raz na dobę"} <= set(labels)


def test_copies_to_frankfurt_need_a_yes_then_follow_the_chosen_rhythm(tmp_path):
    client, admin, home = office(tmp_path)
    asked = say(client, admin, "kopia we frankfurcie co 6 godzin")
    assert asked[0]["type"] == "confirm" and not load(home).replica.enabled
    client.post("/v2/chat", headers=admin, json={"confirm": asked[0]["token"]})
    assert load(home).replica.enabled and load(home).replica.every_hours == 6
    assert "co godzinę" in words(say(client, admin, "kopia we frankfurcie co godzinę"))
    assert load(home).replica.every_hours == 1
    say(client, admin, "trzymaj kopie bez usuwania")
    assert load(home).replica.keep_days == 0
    assert "Bez usuwania" in json.dumps(say(client, admin, "gdzie są dane"), ensure_ascii=False)
    say(client, admin, "kopia we frankfurcie wyłącz")
    assert not load(home).replica.enabled


def test_speech_moves_between_frankfurt_and_this_computer(tmp_path, monkeypatch):
    import worker.transcribe as local_speech
    monkeypatch.setattr(local_speech, "available", lambda: False)
    client, admin, home = office(tmp_path)
    assert "brakuje modułu" in words(say(client, admin, "mowa na tym komputerze"))
    assert load(home).speech.where == "chmura"
    monkeypatch.setattr(local_speech, "available", lambda: True)
    started = []
    monkeypatch.setattr(ModelDownload, "start", lambda self, model: started.append(model))
    blocks = say(client, admin, "mowa na tym komputerze")
    assert load(home).speech.where == "lokalnie" and started == ["small"]
    assert {"type": "progress", "source": "speech/model"} in blocks
    assert client.get("/v2/speech/model", headers=admin).json()["state"] == "brak"
    say(client, admin, "mowa we frankfurcie")
    assert load(home).speech.where == "chmura"


def test_the_model_download_reports_progress_then_readiness(tmp_path):
    gate = []

    folder = tmp_path / "models--Systran--faster-whisper-tiny"
    folder.mkdir(parents=True)
    (folder / "model.bin").write_bytes(b"0" * (2**20 * 10))    # as if 10 MB had already arrived

    def downloader(model, root):
        while not gate:
            time.sleep(0.01)
    warmed = []
    download = ModelDownload(tmp_path, downloader=downloader, warm=warmed.append)
    download.start("tiny")
    for _ in range(500):
        now = download.progress()
        if "10 z" in now["text"]:
            break
        time.sleep(0.02)
    assert now["state"] == "pobieranie" and 0 < now["percent"] < 100 and "10 z ok. 75 MB" in now["text"]
    gate.append(True)
    for _ in range(100):
        if download.progress()["state"] == "gotowy":
            break
        time.sleep(0.02)
    assert download.progress()["percent"] == 100 and warmed == ["tiny"]

    def broken(model, root):
        raise OSError("no internet")
    failing = ModelDownload(tmp_path / "b", downloader=broken, warm=warmed.append)
    failing.start("base")
    for _ in range(100):
        if failing.progress()["state"] == "blad":
            break
        time.sleep(0.02)
    assert "Nie udało się" in failing.progress()["text"]


def test_only_the_office_panel_sees_the_choices(tmp_path):
    client, admin, _ = office(tmp_path)
    code = client.post("/v2/devices/invite", headers=admin, json={"name": "t", "scope": "write"}).json()["code"]
    phone = {"Authorization": "Bearer " + client.post("/v2/devices/redeem", json={"code": code}).json()["token"]}
    assert client.get("/v2/speech/model", headers=phone).status_code == 403
    say(client, phone, "mowa na tym komputerze")
    assert load(tmp_path / "home").speech.where == "chmura"
