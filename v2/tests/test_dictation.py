"""Live dictation: sound pieces in, text out while speaking; private to the device that dictates."""
import base64

from fastapi.testclient import TestClient

from worker.api import create_app
from worker.cloud_speech import Dictation, transcribe_stream
from worker.init_vault import initialize

PIECE = base64.b64encode(b"\x00\x01" * 4000).decode()


def growing(source, on_text):
    words = []
    while True:
        piece = source.get(timeout=5)
        if piece is None:
            break
        words.append("słowo")
        on_text([], " ".join(words))
    on_text([" ".join(words) + "."], "")


def office(tmp_path, **kwargs):
    home = tmp_path / "home"
    admin = {"Authorization": "Bearer " + initialize(home)}
    client = TestClient(create_app(home, **kwargs))
    code = client.post("/v2/devices/invite", headers=admin, json={"name": "t", "scope": "read"}).json()["code"]
    phone = {"Authorization": "Bearer " + client.post("/v2/devices/redeem", json={"code": code}).json()["token"]}
    return client, admin, phone


def test_text_grows_while_speaking_and_settles_at_the_end(tmp_path):
    client, admin, phone = office(tmp_path, dictation_stream=growing)
    ident = client.post("/v2/dictation", headers=admin).json()["id"]
    for _ in range(3):
        client.post(f"/v2/dictation/{ident}", headers=admin, json={"pcm_b64": PIECE})
    import time
    for _ in range(50):
        live = client.post(f"/v2/dictation/{ident}", headers=admin, json={}).json()
        if live["text"].count("słowo") == 3:
            break
        time.sleep(0.02)
    assert live == {"text": "słowo słowo słowo", "done": False, "error": None}
    assert client.post(f"/v2/dictation/{ident}", headers=phone, json={}).status_code == 404     # not yours
    final = client.post(f"/v2/dictation/{ident}", headers=admin, json={"end": True}).json()
    assert final == {"text": "słowo słowo słowo.", "done": True, "error": None}


def test_a_reading_phone_may_dictate_a_question_and_cancel_it(tmp_path):
    client, _, phone = office(tmp_path, dictation_stream=growing)
    ident = client.post("/v2/dictation", headers=phone).json()["id"]
    assert client.delete(f"/v2/dictation/{ident}", headers=phone).json() == {"ok": True}
    assert client.post(f"/v2/dictation/{ident}", headers=phone, json={}).status_code == 404


def test_without_any_speech_setup_the_reason_is_said(tmp_path):
    client, admin, _ = office(tmp_path)
    response = client.post("/v2/dictation", headers=admin)
    assert response.status_code == 409 and ("zaloguj" in response.json()["detail"] or "gdzie są dane" in response.json()["detail"])


def test_speech_on_this_computer_gives_the_text_at_the_end(tmp_path):
    client, admin, _ = office(tmp_path, transcriber=lambda audio: "Tekst z tego komputera." if audio[:4] == b"RIFF" else "")
    ident = client.post("/v2/dictation", headers=admin).json()["id"]
    client.post(f"/v2/dictation/{ident}", headers=admin, json={"pcm_b64": PIECE})
    assert client.post(f"/v2/dictation/{ident}", headers=admin, json={"end": True}).json()["text"] == "Tekst z tego komputera."


def test_a_failed_stream_says_so_plainly():
    def broken(source, on_text):
        raise RuntimeError("HTTP/2 refused with internal details")
    dictation = Dictation(broken)
    dictation.done.wait(2)
    assert dictation.error == "Połączenie z rozpoznawaniem mowy przerwane. Spróbuj ponownie."


def test_dictation_stays_in_the_eu():
    import pytest
    with pytest.raises(ValueError):
        transcribe_stream(lambda: {}, "us-east-1")
