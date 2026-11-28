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


# ---- dictation read with understanding (owner's decision 28.11.2026)
def test_the_polish_keeps_every_number_and_falls_back_to_what_was_heard():
    from worker.dictation_polish import polish

    heard = "kazałem mu w rynecie zarejestrować akt z 14 listopada kwota 450000 złotych no"
    seen = []

    def good(system, text):
        seen.append(text)
        return "Kazałem mu w RejNET zarejestrować akt z 14 listopada, kwota 450000 złotych."
    assert polish(good, heard, ["rejnet"]) == ("Kazałem mu w RejNET zarejestrować akt z 14 listopada, kwota 450000 złotych.", True)
    assert "rejnet" in seen[0] and "TEKST USŁYSZANY" in seen[0]
    assert polish(lambda s, t: "Zarejestruj akt z 14 listopada, kwota 540000 złotych.", heard) == (heard, False)   # a number changed
    assert polish(lambda s, t: "", heard) == (heard, False)
    assert polish(lambda s, t: heard + " " + "i jeszcze dopisz sto innych rzeczy " * 5, heard) == (heard, False)   # something added
    assert polish(lambda s, t: 1 / 0, heard) == (heard, False)                                                   # the model failed
    assert polish(good, "tak") == ("tak", False)                                                                  # too short to bother


def test_at_the_end_of_a_dictation_the_text_is_what_was_meant(tmp_path):
    from worker.inference import Inference
    from worker.policy import EU_REGIONS, Policy
    from worker.usage import UsageLedger

    def heard_wrong(source, on_text):
        while source.get(timeout=5) is not None:
            pass
        on_text(["sprawdź w rynecie akty z 2026 roku no"], "")

    class Bedrock:
        asked = []

        def get_model_invocation_logging_configuration(self):
            return {}

        def get_inference_profile(self, inferenceProfileIdentifier):
            return {"models": [{"modelArn": f"arn:aws:bedrock:{r}::foundation-model/x"} for r in EU_REGIONS]}

        def converse(self, **kwargs):
            Bedrock.asked.append(kwargs["messages"][0]["content"][-1]["text"])
            return {"output": {"message": {"content": [{"text": "Sprawdź w RejNET akty z 2026 roku."}]}}, "stopReason": "end_turn",
                    "usage": {"inputTokens": 1, "outputTokens": 1}}
    home = tmp_path / "home"
    admin = {"Authorization": "Bearer " + initialize(home)}
    inference = Inference(Policy("eu-central-1", "eu.anthropic.claude-sonnet-4-6"), lambda s: Bedrock(), UsageLedger(home))
    client = TestClient(create_app(home, inference=inference, dictation_stream=heard_wrong))
    ident = client.post("/v2/dictation", headers=admin).json()["id"]
    client.post(f"/v2/dictation/{ident}", headers=admin, json={"pcm_b64": PIECE})
    assert Bedrock.asked == []                                          # nothing is polished while the notary still speaks
    final = client.post(f"/v2/dictation/{ident}", headers=admin, json={"end": True}).json()
    assert final["text"] == "Sprawdź w RejNET akty z 2026 roku." and final["heard"] == "sprawdź w rynecie akty z 2026 roku no"
    assert len(Bedrock.asked) == 1
    said = client.post("/v2/chat", headers=admin, json={"text": "wyłącz poprawianie dyktowania"}).json()["blocks"][0]["text"]
    assert "dokładnie to, co usłyszało" in said
    ident = client.post("/v2/dictation", headers=admin).json()["id"]
    client.post(f"/v2/dictation/{ident}", headers=admin, json={"pcm_b64": PIECE})
    final = client.post(f"/v2/dictation/{ident}", headers=admin, json={"end": True}).json()
    assert final["text"] == "sprawdź w rynecie akty z 2026 roku no" and "heard" not in final and len(Bedrock.asked) == 1
