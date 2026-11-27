"""Voice notes: stored in the case, transcribed on this computer, then read by the assistant."""
import base64

import pytest
from fastapi.testclient import TestClient

from worker.api import create_app
from worker.init_vault import initialize


def make(tmp_path, transcriber=None):
    home = tmp_path / "home"
    admin = {"Authorization": "Bearer " + initialize(home)}
    return TestClient(create_app(home, transcriber=transcriber)), admin, home


def device(client, admin, scope="write", cases=None):
    code = client.post("/v2/devices/invite", headers=admin, json={"name": "t", "scope": scope, "cases": cases}).json()["code"]
    return {"Authorization": "Bearer " + client.post("/v2/devices/redeem", json={"code": code}).json()["token"]}


AUDIO = base64.b64encode(b"\x1aE\xdf\xa3 fake webm audio").decode()


def test_a_voice_note_becomes_text_in_the_case(tmp_path):
    heard = []
    client, admin, home = make(tmp_path, transcriber=lambda audio: heard.append(audio) or
                               "Klient przyniesie odpis księgi w piątek. Sprzedający Jan Kowalski.")
    phone = device(client, admin)
    saved = client.post("/v2/voice", headers=phone, json={"audio_b64": AUDIO, "case": "kowalski-2026"})
    assert saved.status_code == 200, saved.text
    result = saved.json()
    assert result["text"].startswith("Klient przyniesie odpis") and heard == [base64.b64decode(AUDIO)]
    names = [d["name"] for d in result["documents"]]
    assert names[0].startswith("notatka-glosowa-") and names[0].endswith(".webm") and names[1].endswith(".txt")
    note = client.get("/v2/documents/" + result["documents"][1]["id"], headers=phone).json()
    assert "przepisana automatycznie" in base64.b64decode(note["content_b64"]).decode()
    assert b"Kowalski" not in (home / "vault.sqlite3").read_bytes()
    # Recordings from a dictaphone or a messenger keep their format.
    m4a = client.post("/v2/voice", headers=phone, json={"audio_b64": AUDIO, "name": "Nagranie 12.m4a", "case": "kowalski-2026"})
    assert [d["name"] for d in m4a.json()["documents"]] == ["Nagranie 12.m4a", "Nagranie 12 - tekst.txt"]
    # A recording already in the case (e.g. added from mail) is transcribed on request.
    client.post("/v2/documents", headers=phone, json={"name": "dyktafon-kowalski.ogg", "expected_version": 0,
                                                      "case": "kowalski-2026", "content_b64": AUDIO})
    blocks = client.post("/v2/chat", headers=phone, json={"text": "przepisz nagranie dyktafon", "case": "kowalski-2026"}).json()["blocks"]
    assert blocks[0]["text"].startswith("Przepisałem nagranie:") and blocks[1]["items"][0]["name"] == "dyktafon-kowalski - tekst.txt"
    # The assistant reads transcripts like any other case document.
    listed = {d["name"] for d in client.get("/v2/documents?include_names=true&case=kowalski-2026", headers=phone).json()}
    assert {"dyktafon-kowalski.ogg", "dyktafon-kowalski - tekst.txt", "Nagranie 12 - tekst.txt"} <= listed


def test_refusals_and_limits(tmp_path):
    client, admin, _ = make(tmp_path, transcriber=lambda audio: "tekst")
    reader = device(client, admin, "read")
    assert client.post("/v2/voice", headers=reader, json={"audio_b64": AUDIO}).status_code == 403
    limited = device(client, admin, "write", cases=["moja"])
    assert client.post("/v2/voice", headers=limited, json={"audio_b64": AUDIO, "case": "obca"}).status_code == 404
    assert client.post("/v2/voice", headers=limited, json={"audio_b64": AUDIO}).status_code == 404
    assert client.post("/v2/voice", headers=admin, json={"audio_b64": AUDIO, "name": "skrypt.exe"}).status_code == 400
    assert client.post("/v2/voice", headers=admin, json={"audio_b64": "***"}).status_code == 400
    assert client.post("/v2/voice", headers=admin, json={"audio_b64": ""}).status_code == 400
    assert client.post("/v2/voice", json={"audio_b64": AUDIO}).status_code == 401
    text = client.post("/v2/documents", headers=admin, json={
        "name": "akt.txt", "expected_version": 0, "case": "s", "content_b64": "YQ=="})
    blocks = client.post("/v2/chat", headers=admin, json={"text": "przepisz akt", "case": "s"}).json()["blocks"]
    assert blocks[0]["text"] == "To nie jest nagranie."


def test_without_speech_recognition_the_recording_is_still_kept(tmp_path, monkeypatch):
    from worker import transcribe

    monkeypatch.setattr(transcribe, "available", lambda: False)
    client, admin, _ = make(tmp_path)
    result = client.post("/v2/voice", headers=admin, json={"audio_b64": AUDIO, "case": "s"}).json()
    assert result["text"] is None and len(result["documents"]) == 1 and "nie jest skonfigurowane" in result["detail"]

    def broken(audio):
        raise RuntimeError("decoder crashed")
    client, admin, _ = make(tmp_path / "b", transcriber=broken)
    result = client.post("/v2/voice", headers=admin, json={"audio_b64": AUDIO, "case": "s"}).json()
    assert result["text"] == "" and len(result["documents"]) == 1 and "Nie udało się rozpoznać mowy" in result["detail"]
