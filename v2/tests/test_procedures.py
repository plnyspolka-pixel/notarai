"""Teaching by showing: narrated recording -> procedure -> values for a case. The model is a fake."""
import base64
import json

import pytest
from fastapi.testclient import TestClient

from worker.api import create_app
from worker.inference import Inference
from worker.init_vault import initialize
from worker.policy import EU_REGIONS, Policy
from worker.usage import UsageLedger

JPEG = b"\xff\xd8\xff\xe0" + b"synthetic-frame"
LEARNED = {"program": "Portal Wnioski KW", "cel": "Wniosek o wpis własności", "kroki": [
    {"pole": "Numer księgi wieczystej", "zrodlo": "numer KW z aktu", "dlaczego": "wpis dotyczy tej księgi"},
    {"pole": "PESEL wnioskodawcy", "zrodlo": "PESEL nabywcy z aktu", "dlaczego": ""},
    {"pole": "Wyślij", "zrodlo": "kliknij", "dlaczego": "dopiero po sprawdzeniu"},
]}
NARRATION = "Najpierw wpisuję numer księgi wieczystej z aktu, bo wpis dotyczy tej księgi. Potem PESEL nabywcy."


class Bedrock:
    def __init__(self):
        self.calls, self.learn_reply = [], "Oto procedura:\n```json\n" + json.dumps(LEARNED, ensure_ascii=False) + "\n```"

    def get_model_invocation_logging_configuration(self):
        return {}

    def get_inference_profile(self, inferenceProfileIdentifier):
        return {"models": [{"modelArn": f"arn:aws:bedrock:{r}::foundation-model/x"} for r in EU_REGIONS]}

    def converse(self, **kwargs):
        content = kwargs["messages"][0]["content"]
        self.calls.append(content)
        prompt = content[-1]["text"]
        if "KOMENTARZ NOTARIUSZA" in prompt:
            reply = self.learn_reply
        else:
            reply = json.dumps({"wartosci": [
                {"pole": "numer księgi wieczystej", "wartosc": "[KW_1]", "skad": "notatka.txt"},
                {"pole": "PESEL wnioskodawcy", "wartosc": "[PESEL_1]", "skad": "notatka.txt"},
                {"pole": "Wyślij", "wartosc": "kliknij"},
                {"pole": "Pole spoza procedury", "wartosc": "zmyślone"}]}, ensure_ascii=False)
        return {"output": {"message": {"content": [{"text": reply}]}}, "stopReason": "end_turn",
                "usage": {"inputTokens": 5, "outputTokens": 5}}


@pytest.fixture
def office(tmp_path):
    home = tmp_path / "home"
    admin = {"Authorization": "Bearer " + initialize(home)}
    bedrock = Bedrock()
    inference = Inference(Policy("eu-central-1", "eu.anthropic.claude-sonnet-4-6"), lambda s: bedrock, UsageLedger(home))
    client = TestClient(create_app(home, inference=inference, transcriber=lambda audio: "Rozpoznany komentarz. " + NARRATION))
    return client, admin, home, bedrock


def say(client, headers, text, **extra):
    return client.post("/v2/chat", headers=headers, json={"text": text, **extra}).json()["blocks"]


def texts(blocks):
    return "\n".join(b.get("text", "") for b in blocks if b["type"] == "text")


def lesson(**extra):
    return {"name": "Wniosek o wpis w KW", "narration": NARRATION,
            "frames": [base64.b64encode(JPEG).decode()] * 3, **extra}


def phone(client, admin, scope="write", cases=None):
    code = client.post("/v2/devices/invite", headers=admin, json={"name": "t", "scope": scope, "cases": cases}).json()["code"]
    return {"Authorization": "Bearer " + client.post("/v2/devices/redeem", json={"code": code}).json()["token"]}


def test_show_once_then_fill_for_any_case(office):
    client, admin, home, bedrock = office
    asked = say(client, admin, "nagraj procedurę Wniosek o wpis w KW")
    assert asked[1] == {"type": "record", "name": "Wniosek o wpis w KW", "transcribes": True}
    assert "nie nagrywaj prawdziwych danych" in texts(asked)
    heard = client.post("/v2/procedures/transcribe", headers=admin, json={"recording_b64": base64.b64encode(b"webm").decode()})
    assert heard.json()["text"].startswith("Rozpoznany komentarz.")

    learned = client.post("/v2/procedures/learn", headers=admin,
                          json=lesson(recording_b64=base64.b64encode(b"WEBM-BYTES").decode()))
    assert learned.status_code == 200, learned.text
    proposal = learned.json()
    sent = bedrock.calls[-1]
    assert [part["image"]["source"]["bytes"] for part in sent[:3]] == [JPEG] * 3 and sent[0]["image"]["format"] == "jpeg"
    assert proposal["procedure"]["nazwa"] == "Wniosek o wpis w KW" and len(proposal["procedure"]["kroki"]) == 3
    assert client.get("/v2/documents?case=procedury", headers=admin).json() == []          # nothing stored yet

    corrected = proposal["procedure"]
    corrected["kroki"][1]["dlaczego"] = "sąd identyfikuje wnioskodawcę po numerze PESEL"
    saved = client.post(f"/v2/procedures/{proposal['id']}/approve", headers=admin, json=corrected)
    assert saved.json() == {"name": "Wniosek o wpis w KW", "version": 1, "steps": 3}
    assert client.post(f"/v2/procedures/{proposal['id']}/approve", headers=admin, json=corrected).status_code == 409
    stored = {d["name"] for d in client.get("/v2/documents?include_names=true&case=procedury", headers=admin).json()}
    assert stored == {"wniosek-o-wpis-w-kw.procedura.json", "wniosek-o-wpis-w-kw.nagranie.webm"}
    assert b"WEBM-BYTES" not in (home / "vault.sqlite3").read_bytes()

    listed = say(client, admin, "procedury")
    assert listed[1]["items"] == [{"label": "Wniosek o wpis w KW", "say": "wypełnij Wniosek o wpis w KW"}]
    described = texts(say(client, admin, "pokaż procedurę wniosek o wpis"))
    assert "2. PESEL wnioskodawcy: PESEL nabywcy z aktu (bo: sąd identyfikuje" in described

    client.post("/v2/documents", headers=admin, json={
        "name": "notatka.txt", "expected_version": 0, "case": "kowalski-2026",
        "content_b64": base64.b64encode("Nabywca Jan Kowalski, PESEL 44051401359, księga WA1M/00012345/6.".encode()).decode()})
    assert "Dla której sprawy" in texts(say(client, admin, "wypełnij wniosek o wpis w KW"))
    device = phone(client, admin)                                    # a paired phone can use what the office taught
    sheet = say(client, device, "wypełnij wniosek o wpis w KW", case="kowalski-2026")
    fill = next(b for b in sheet if b["type"] == "fill")
    assert [(i["field"], i["value"]) for i in fill["items"]] == [
        ("Numer księgi wieczystej", "WA1M/00012345/6"), ("PESEL wnioskodawcy", "44051401359"), ("Wyślij", "kliknij")]
    assert fill["items"][1]["why"].startswith("sąd identyfikuje") and fill["missing"] == 0
    prompt = bedrock.calls[-1][-1]["text"]
    assert "44051401359" not in prompt and "WA1M" not in prompt and "pole: Numer księgi wieczystej" in prompt

    # Teaching again under the same name makes a new version, not a second procedure.
    again = client.post("/v2/procedures/learn", headers=admin, json=lesson()).json()
    assert client.post(f"/v2/procedures/{again['id']}/approve", headers=admin, json=again["procedure"]).json()["version"] == 2
    assert len(say(client, admin, "procedury")[1]["items"]) == 1
    usage = {row["purpose"] for row in client.get("/v2/usage", headers=admin).json()}
    assert {"learn", "fill"} <= usage


def test_limits_and_who_may_teach(office):
    client, admin, _, bedrock = office
    device = phone(client, admin)
    assert client.post("/v2/procedures/learn", headers=device, json=lesson()).status_code == 403
    assert client.post("/v2/procedures/transcribe", headers=device, json={"recording_b64": "YQ=="}).status_code == 403
    assert "w panelu stanowiska" in texts(say(client, device, "nagraj procedurę"))
    assert client.post("/v2/procedures/learn", headers=admin, json=lesson(narration="krótko")).status_code == 409
    assert client.post("/v2/procedures/learn", headers=admin,
                       json=lesson(frames=[base64.b64encode(b"GIF89a not a jpeg").decode()])).status_code == 502
    assert client.post("/v2/procedures/learn", headers=admin, json=lesson(frames=["***"])).status_code == 400
    calls = len(bedrock.calls)
    bedrock.learn_reply = "Nie potrafię."
    refused = client.post("/v2/procedures/learn", headers=admin, json=lesson())
    assert refused.status_code == 409 and "Nagraj krócej" in refused.json()["detail"] and len(bedrock.calls) == calls + 1
    bedrock.learn_reply = json.dumps({"kroki": []})
    assert client.post("/v2/procedures/learn", headers=admin, json=lesson()).status_code == 409
    assert "Nie znam jeszcze żadnej procedury" in texts(say(client, admin, "procedury"))
    assert "Nie ma takiej procedury" in texts(say(client, admin, "wypełnij nieznana", case="x"))
    # A device limited to chosen cases does not see or use the office's procedures.
    limited = phone(client, admin, cases=["kowalski-2026"])
    assert "fill" not in [b["type"] for b in say(client, limited, "procedury", case="kowalski-2026")]
    assert "Znam te procedury" not in texts(say(client, limited, "procedury", case="kowalski-2026"))


def test_without_a_local_transcriber_the_notary_types(tmp_path, monkeypatch):
    from worker import transcribe

    monkeypatch.setattr(transcribe, "available", lambda: False)
    home = tmp_path / "home"
    admin = {"Authorization": "Bearer " + initialize(home)}
    client = TestClient(create_app(home))
    answer = client.post("/v2/procedures/transcribe", headers=admin, json={"recording_b64": "YQ=="})
    assert answer.status_code == 409 and "Wpisz komentarz ręcznie" in answer.json()["detail"]
    assert say(client, admin, "nagraj procedurę")[1]["transcribes"] is False
    assert "Znam procedur: 0" in texts(say(client, admin, "programy"))
