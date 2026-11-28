"""Always-on microphones: segments -> conversations -> stenogram of a deed, or a note of a conversation."""
import base64
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from worker.api import create_app
from worker.docx_writer import build, extract
from worker.init_vault import initialize
from worker.listening import NOTES_CASE, Listening
from worker.local_secrets import read_secret
from worker.vault import Vault

DEED = ["# AKT NOTARIALNY", "UMOWA SPRZEDAŻY",
        "Stawający Jan Kowalski oświadcza, że jest właścicielem lokalu mieszkalnego położonego w Warszawie przy ulicy Długiej.",
        "Stawający sprzedaje Annie Nowak opisany lokal mieszkalny za cenę pięciuset tysięcy złotych, a ona ten lokal kupuje.",
        "Notariusz pouczył strony o treści artykułu dziewięćdziesiątego pierwszego Prawa o notariacie.",
        "Akt ten został odczytany, przyjęty i podpisany."]
READING = [   # what the microphone hears while the deed is read, with recognition mistakes
    "stawający jan kowalski oświadcza że jest właścicielem lokalu mieszkalnego położonego w warszawie przy ulicy długiej",
    "stawający sprzedaje annie nowak opisany lokal mieszkalny za cenę pięciuset tysięcy złotych a ona ten lokal kupuje",
    "notariusz pouczył strony o treści artykułu dziewięćdziesiątego pierwszego prawa o notariacie akt ten został odczytany",
]
VISIT = ["dzień dobry chciałabym się umówić na podpisanie umowy darowizny mieszkania dla córki",
         "może być w przyszły wtorek o dziesiątej mój telefon to sześćset sto dwieście nazywam się Ewa Lis"]


class Clock:
    def __init__(self):
        self.now = 1_800_000_000.0

    def __call__(self):
        return self.now


class Inference:
    enabled = True

    def __init__(self):
        self.calls = []

    def ask(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(text=json.dumps({"rodzaj": "wizyta", "podsumowanie": "Pani chce umówić darowiznę mieszkania dla córki.",
                                                "osoby": ["Ewa Lis"], "termin": "wtorek 10:00", "kontakt": "600 100 200",
                                                "do_zrobienia": ["wpisać termin"]}, ensure_ascii=False))


@pytest.fixture
def ears(tmp_path):
    home = tmp_path / "home"
    initialize(home)
    vault = Vault(home, read_secret(home, "vault.key"))
    vault.put(None, 0, "umowa.docx", build(DEED), case="kowalski-2026")
    vault.put(None, 0, "inna.docx", build(["# TESTAMENT", "Ja niżej podpisana oświadczam swoją ostatnią wolę co do całego majątku."]), case="lis-2026")
    # A voice note with the same words as a later visit is not a deed: it must not turn the visit into a stenogram.
    vault.put(None, 0, "notatka-glosowa-20261127-1200.txt", " ".join(VISIT).encode(), case="lis-2026")
    settings = SimpleNamespace(enabled=True, paused=False, gap_seconds=120)
    clock, inference = Clock(), Inference()
    listening = Listening(vault, lambda audio, suffix: audio.decode(), lambda: inference, lambda: settings,
                          clock=clock, extract=extract)
    return listening, vault, settings, clock, inference


def feed(listening, clock, source, texts, start, step=20):
    for index, text in enumerate(texts):
        assert listening.accept(source, text.encode(), ".webm", start + index * step, step)
        clock.now = start + (index + 1) * step


def test_a_deed_read_aloud_becomes_its_stenogram(ears):
    listening, vault, settings, clock, inference = ears
    feed(listening, clock, "Gabinet", READING, clock.now)
    assert listening.tick() == []                     # still within the quiet gap: the reading may go on
    clock.now += 121
    filed = listening.tick()
    assert len(filed) == 1 and filed[0]["kind"] == "stenopis" and filed[0]["case"] == "kowalski-2026"
    assert filed[0]["deed"] == "umowa.docx" and filed[0]["score"] >= 0.3
    stored = vault.get(filed[0]["id"])[2].decode()
    assert "Stenopis odczytania aktu „umowa.docx” (wersja 1)" in stored and "mikrofon: Gabinet" in stored
    assert "pouczył strony" in stored and inference.calls == []       # matched by code, no model involved


def test_a_visit_becomes_a_note_with_date_and_contact(ears):
    listening, vault, settings, clock, inference = ears
    feed(listening, clock, "Sekretariat", VISIT, clock.now)
    clock.now += 200
    filed = listening.tick()
    assert filed[0]["case"] == NOTES_CASE and filed[0]["name"].startswith("rozmowa-") and filed[0]["name"].endswith("-Sekretariat.txt")
    stored = vault.get(filed[0]["id"])[2].decode()
    assert stored.startswith("Rozmowa z klientem") and "Termin: wtorek 10:00" in stored and "Kontakt: 600 100 200" in stored
    assert "darowizny mieszkania dla córki" in stored                  # the transcript is kept with the note
    assert inference.calls[0]["purpose"] == "listen"


def test_microphones_are_kept_apart_and_gaps_split_conversations(ears):
    listening, vault, settings, clock, inference = ears
    start = clock.now
    feed(listening, clock, "Gabinet", READING[:2], start)
    feed(listening, clock, "Sekretariat", VISIT, start)
    listening.tick()
    feed(listening, clock, "Gabinet", READING[2:], start + 1000)     # long after: a new conversation
    clock.now = start + 2000
    filed = listening.tick()
    kinds = sorted((f["kind"], f["case"]) for f in filed)
    # The later part of the reading is its own conversation, and is recognised as the same deed.
    assert kinds == [("stenopis", "kowalski-2026"), ("stenopis", "kowalski-2026"), ("wizyta", NOTES_CASE)]


def test_silence_noise_pause_and_switch_off(ears):
    listening, vault, settings, clock, inference = ears
    feed(listening, clock, "Sekretariat", ["halo", "tak"], clock.now)
    clock.now += 500
    assert listening.tick() == []                                     # too few words to be anything
    settings.paused = True
    assert not listening.accept("Sekretariat", b"tekst", ".webm", clock.now, 20)
    settings.paused, settings.enabled = False, False
    assert not listening.accept("Sekretariat", b"tekst", ".webm", clock.now, 20)
    settings.enabled = True
    inference.enabled = False
    feed(listening, clock, "Sekretariat", VISIT, clock.now)
    filed = listening.flush()
    assert "Bez podsumowania" in vault.get(filed[0]["id"])[2].decode()


def test_transcription_failures_do_not_stop_listening(ears):
    listening, vault, settings, clock, inference = ears

    def flaky(audio, suffix):
        if audio == b"zepsute":
            raise RuntimeError("decoder")
        return audio.decode()
    listening._transcribe = flaky
    listening.accept("Gabinet", b"zepsute", ".webm", clock.now, 20)
    feed(listening, clock, "Gabinet", READING, clock.now + 20)
    assert listening.flush()[0]["kind"] == "stenopis"


def test_microphone_devices_only_send_sound(tmp_path):
    home = tmp_path / "home"
    admin = {"Authorization": "Bearer " + initialize(home)}
    client = TestClient(create_app(home, transcriber=lambda audio: audio.decode()))

    def say(sentence, headers=admin, **extra):
        blocks = client.post("/v2/chat", headers=headers, json={"text": sentence, **extra}).json()["blocks"]
        return blocks, "\n".join(b.get("text", "") for b in blocks)

    blocks, reply = say("dodaj mikrofon Sekretariat")
    code = next(b for b in blocks if b["type"] == "secret")["text"]
    assert "nie ma dostępu do dokumentów" in reply
    mic = client.post("/v2/devices/redeem", json={"code": code}).json()
    assert mic["scope"] == "listen"
    headers = {"Authorization": "Bearer " + mic["token"]}
    for method, path in (("get", "/v2/documents"), ("get", "/v2/cases"), ("get", "/v2/status"), ("get", "/v2/rules"),
                         ("post", "/v2/chat"), ("get", "/v2/documents/11111111-1111-4111-8111-111111111111")):
        assert getattr(client, method)(path, headers=headers, **({"json": {"text": "dokumenty"}} if method == "post" else {})).status_code == 403
    segment = {"audio_b64": base64.b64encode(" ".join(VISIT).encode()).decode(), "started_ms": 0, "duration_ms": 20000}
    assert client.post("/v2/listen", headers=headers, json=segment).json() == {"accepted": False, "enabled": False, "paused": False}
    assert client.get("/v2/listen/state", headers=headers).json()["source"] == "Sekretariat"

    confirm = next(b for b in say("włącz nasłuch")[0] if b["type"] == "confirm")
    assert "RODO" in confirm["text"]
    say("", confirm=confirm["token"])
    assert client.post("/v2/listen", headers=headers, json=segment).json()["accepted"] is True
    phone_code = client.post("/v2/devices/invite", headers=admin, json={"name": "telefon", "scope": "write"}).json()["code"]
    phone = {"Authorization": "Bearer " + client.post("/v2/devices/redeem", json={"code": phone_code}).json()["token"]}
    assert client.post("/v2/listen", headers=phone, json=segment).status_code == 403     # only microphones send sound
    assert "Sekretariat: ostatni dźwięk" in say("nasłuch")[1]
    assert "wstrzymany" in say("wstrzymaj nasłuch")[1].lower()
    assert client.post("/v2/listen", headers=headers, json=segment).json()["paused"] is True
    say("wznów nasłuch")
    assert "Zapisałem ostatnie rozmowy: 1" in say("wyłącz nasłuch")[1]
    notes = say("notatki z rozmów")[0]
    assert notes[1]["items"][0]["name"].startswith("rozmowa-") and notes[1]["items"][0]["name"].endswith("Sekretariat.txt")
