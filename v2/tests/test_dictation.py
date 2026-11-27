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
    assert live == {"text": "słowo słowo słowo", "done": False, "error": None, "login": False}
    assert client.post(f"/v2/dictation/{ident}", headers=phone, json={}).status_code == 404     # not yours
    final = client.post(f"/v2/dictation/{ident}", headers=admin, json={"end": True}).json()
    assert final == {"text": "słowo słowo słowo.", "done": True, "error": None, "login": False}


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
    assert dictation.error.startswith("Szybkie dyktowanie nie łączy się z Frankfurtem") and dictation.cause == "RuntimeError"


def test_dictation_stays_in_the_eu():
    import pytest
    with pytest.raises(ValueError):
        transcribe_stream(lambda: {}, "us-east-1")


def test_a_broken_stream_still_gives_text_the_second_way(tmp_path):
    def broken(source, on_text):
        raise ConnectionError("HTTP/2 blocked")
    client, admin, _ = office(tmp_path, dictation_stream=broken, transcriber=lambda audio: "Tekst drugą drogą.")
    ident = client.post("/v2/dictation", headers=admin).json()["id"]
    import time
    time.sleep(0.2)
    live = client.post(f"/v2/dictation/{ident}", headers=admin, json={"pcm_b64": base64.b64encode(b"\x00\x01" * 20000).decode()}).json()
    assert "Szybkie dyktowanie nie łączy się" in live["error"] and live["login"] is False
    final = client.post(f"/v2/dictation/{ident}", headers=admin, json={"end": True}).json()
    assert final == {"text": "Tekst drugą drogą.", "done": True, "error": None, "second_way": True}


def test_without_a_sign_in_dictation_says_so_before_starting(tmp_path):
    class NotSignedIn:
        signed_in = False

        def client_factory(self, region):
            return lambda service: None
    client, admin, _ = office(tmp_path, account=NotSignedIn())
    response = client.post("/v2/dictation", headers=admin)
    assert response.status_code == 409 and "zaloguj" in response.json()["detail"]
    said = client.post("/v2/chat", headers=admin, json={"text": "sprawdź mowę"}).json()["blocks"]
    assert "✗ Logowanie: stanowisko NIE jest zalogowane" in said[0]["text"]
    assert said[1]["items"][0]["say"] == "zaloguj"
