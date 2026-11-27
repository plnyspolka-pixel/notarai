"""Chat-first front door: sentences in, blocks out. The model is a fake."""
import base64
import json

import pytest
from fastapi.testclient import TestClient

from worker.api import create_app
from worker.chat import norm, parse_amount
from worker.devices import DeviceRegistry
from worker.inference import Inference
from worker.init_vault import initialize
from worker.policy import EU_REGIONS, Policy
from worker.usage import UsageLedger


class Bedrock:
    def __init__(self):
        self.prompts = []

    def get_model_invocation_logging_configuration(self):
        return {}

    def get_inference_profile(self, inferenceProfileIdentifier):
        return {"models": [{"modelArn": f"arn:aws:bedrock:{r}::foundation-model/x"} for r in EU_REGIONS]}

    def converse(self, **kwargs):
        prompt = kwargs["messages"][0]["content"][0]["text"]
        self.prompts.append(prompt)
        reply = "Sprzedaje [OSOBA_1]." if "PYTANIE" in prompt else "# UMOWA\n[OSOBA_1] sprzedaje lokal."
        return {"output": {"message": {"content": [{"text": reply}]}}, "stopReason": "end_turn",
                "usage": {"inputTokens": 10, "outputTokens": 5}}


@pytest.fixture
def office(tmp_path):
    home = tmp_path / "home"
    token = initialize(home)
    bedrock = Bedrock()
    opened = []
    switch = {"on": True}
    inference = Inference(Policy("eu-central-1", "eu.anthropic.claude-sonnet-4-6"), lambda s: bedrock,
                          UsageLedger(home), pseudonymize=lambda: switch["on"])
    client = TestClient(create_app(home, inference=inference, opener=opened.append))
    admin = {"Authorization": "Bearer " + token}
    return client, admin, home, bedrock, opened, tmp_path


def say(client, headers, text=None, **extra):
    body = {"text": text or "", **extra}
    response = client.post("/v2/chat", headers=headers, json=body)
    assert response.status_code == 200, response.text
    return response.json()["blocks"]


def texts(blocks):
    return "\n".join(b.get("text", "") for b in blocks if b["type"] in {"text", "confirm"})


def kinds(blocks):
    return [b["type"] for b in blocks]


def device(client, admin, scope="write", cases=None):
    code = client.post("/v2/devices/invite", headers=admin, json={"name": "telefon", "scope": scope, "cases": cases}).json()["code"]
    return {"Authorization": "Bearer " + client.post("/v2/devices/redeem", json={"code": code}).json()["token"]}


def test_amounts_and_normalisation():
    assert parse_amount("za 500 tys. zł") == 500_000
    assert parse_amount("1,2 mln") == 1_200_000
    assert parse_amount("350 000,50 zł") == pytest.approx(350000.5)
    assert parse_amount("350.000 zł") == 350_000
    assert parse_amount("bez kwoty") is None
    assert norm("Zrób KOPIĘ, łódź") == "zrob kopie, lodz"


def test_a_notary_works_through_a_case_by_talking(office):
    client, admin, home, bedrock, _, _ = office
    phone = device(client, admin)
    hello = say(client, phone, hello=True)
    assert "kodu odzyskiwania" in texts(hello) and "buttons" in kinds(hello)
    assert "sprawy" in norm(texts(say(client, phone, "sprawy")))
    assert say(client, phone, "nowa sprawa kowalski-2026")[0] == {"type": "case", "case": "kowalski-2026"}
    saved = say(client, phone, "notatka: Sprzedający Jan Kowalski, PESEL 44051401359, zbywa lokal nr 5.", case="kowalski-2026")
    assert "documents" in kinds(saved)
    listed = say(client, phone, "pokaż dokumenty", case="kowalski-2026")
    assert listed[1]["items"][0]["name"].startswith("notatka-")
    remembered = say(client, phone, "strony: Jan Kowalski, Anna Nowak", case="kowalski-2026")
    assert remembered[0] == {"type": "names", "names": ["Jan Kowalski", "Anna Nowak"]}

    assert "Najpierw wybierz sprawę" in texts(say(client, phone, "strony: Jan Kowalski"))
    # Remembered in the vault for the case: no need to repeat the names, on any device.
    answer = say(client, device(client, admin, "read"), "Kto sprzedaje?", case="kowalski-2026")
    assert texts(answer) == "Sprzedaje Jan Kowalski."
    assert "44051401359" not in bedrock.prompts[-1] and "Kowalski" not in bedrock.prompts[-1]

    draft = say(client, phone, "Przygotuj umowę sprzedaży lokalu", case="kowalski-2026")
    proposal = next(b for b in draft if b["type"] == "proposal")
    assert proposal["paragraphs"] == ["# UMOWA", "Jan Kowalski sprzedaje lokal."]
    assert len(client.get("/v2/documents", headers=phone).json()) == 1          # nothing stored yet
    approved = client.post(f"/v2/drafts/{proposal['id']}/approve", headers=phone, json={"name": "umowa.docx"})
    assert approved.json()["state"] == "verified"
    opened = say(client, phone, "otwórz umowa", case="kowalski-2026")
    assert opened[0]["type"] == "open"

    fee = say(client, phone, "policz taksę od sprzedaży lokalu mieszkalnego za 500 tys.")
    assert "RAZEM" in texts(fee) and "nie model" in texts(fee)
    ask = say(client, phone, "taksa 500 tys.")
    assert ask[1]["type"] == "buttons" and ask[1]["items"][0]["say"].startswith("taksa ")
    assert "RAZEM" in texts(say(client, phone, ask[1]["items"][0]["say"]))
    assert "wartość" in texts(say(client, phone, "taksa od darowizny"))

    assert "Wybierz sprawę" in texts(say(client, phone, "Kto sprzedaje?"))
    assert "przygotuj" in norm(texts(say(client, phone, "pomoc")))


def test_the_workstation_is_run_by_talking_too(office):
    client, admin, home, _, opened, tmp_path = office
    assert "BRAK" in texts(say(client, admin, "stan"))
    assert "kod odzyskiwania" in norm(texts(say(client, admin, "zrób kopię")))
    code = next(b for b in say(client, admin, "kod odzyskiwania") if b["type"] == "secret")
    assert code["print"] and len(code["text"]) > 50
    assert "już istnieje" in texts(say(client, admin, "kod odzyskiwania"))
    assert "katalog kopii" in texts(say(client, admin, "zrób kopię"))
    usb = tmp_path / "usb"
    usb.mkdir()
    assert "Kopie będą trafiać" in texts(say(client, admin, f"katalog kopii {usb}"))
    assert "Kopia zapisana na dysku" in texts(say(client, admin, "zrób kopię")) and len(list(usb.iterdir())) == 1
    assert "nie istnieje" in texts(say(client, admin, f"katalog kopii {tmp_path / 'brak'}"))

    invited = say(client, admin, "dodaj telefon tylko do odczytu dla sprawy kowalski-2026")
    assert "tylko odczyt, sprawy: kowalski-2026" in texts(invited)
    pairing = next(b for b in invited if b["type"] == "secret")["text"]
    paired = client.post("/v2/devices/redeem", json={"code": pairing}).json()
    assert paired["scope"] == "read" and paired["cases"] == ["kowalski-2026"]
    assert "Telefon: tylko odczyt, sprawy: kowalski-2026" in texts(say(client, admin, "urządzenia"))
    asked = say(client, admin, "cofnij telefon")
    assert asked[0]["type"] == "confirm" and len(client.get("/v2/devices", headers=admin).json()) == 1
    assert client.get("/v2/cases", headers={"Authorization": "Bearer " + paired["token"]}).status_code == 200
    done = say(client, admin, confirm=asked[0]["token"])
    assert "Cofnąłem dostęp" in texts(done)
    assert client.get("/v2/cases", headers={"Authorization": "Bearer " + paired["token"]}).status_code == 401
    assert "wygasło" in texts(say(client, admin, confirm=asked[0]["token"]))        # single use

    client.post("/v2/documents", headers=admin, json={
        "name": "umowa.txt", "expected_version": 0, "case": "kowalski-2026", "content_b64": "YQ=="})
    assert "Otworzyłem umowa.txt" in texts(say(client, admin, "otwórz umowa w Wordzie"))
    opened[0].write_text("zmienione")
    assert "zmieniony, niezapisany" in texts(say(client, admin, "otwarte"))
    assert "jako wersję 2" in texts(say(client, admin, "zapisz do sejfu"))
    journal = texts(say(client, admin, "kto czytał umowa?"))
    assert "otworzył do edycji umowa.txt" in journal and "zapisał umowa.txt (wersja 2)" in journal
    assert "kontrola po zapisie" not in journal

    assert "wyłączona" in texts(say(client, admin, "wyłącz pseudonimizację"))
    assert json.loads((home / "settings.json").read_text())["ai"]["pseudonymize"] is False
    assert "włączona" in texts(say(client, admin, "włącz maskowanie danych"))
    assert "danych konta" in texts(say(client, admin, "włącz asystenta"))
    assert "Brakuje adresu" in texts(say(client, admin, "włącz dostęp spoza kancelarii"))
    assert "Kopii zapasowej" not in texts(say(client, admin, "stan"))


def test_devices_cannot_use_workstation_commands_or_other_cases(office):
    client, admin, home, bedrock, opened, _ = office
    client.post("/v2/documents", headers=admin, json={
        "name": "tajne.txt", "expected_version": 0, "case": "obca", "content_b64": base64.b64encode(b"TAJNE").decode()})
    client.post("/v2/documents", headers=admin, json={
        "name": "moje.txt", "expected_version": 0, "case": "moja", "content_b64": "YQ=="})
    phone = device(client, admin, "read", cases=["moja"])
    before = len(bedrock.prompts)
    for command in ("kod odzyskiwania", "dodaj telefon", "wyłącz pseudonimizację", "urządzenia",
                    "otwórz moje w Wordzie", "dziennik", "zrób kopię"):
        blocks = say(client, phone, command, case="moja")
        assert not {"secret", "confirm", "qr"} & set(kinds(blocks)), command
    assert DeviceRegistry(home).list()[0]["name"] == "telefon" and len(DeviceRegistry(home).list()) == 1
    assert opened == [] and not (home / "settings.json").exists() and not (home / "vault.key.recovery").exists()
    # Those sentences fell through to an ordinary question about the device's own case.
    assert all("TAJNE" not in prompt for prompt in bedrock.prompts[before:]) and len(bedrock.prompts) > before
    assert "Nie ma takiej sprawy" in texts(say(client, phone, "dokumenty", case="obca"))
    assert say(client, phone, "sprawy")[1]["items"] == [{"label": "moja", "say": "sprawa moja"}]
    assert "tajne" not in json.dumps(say(client, phone, "dokumenty"))
    assert "tajne" not in json.dumps(say(client, phone, "otwórz tajne", case="moja"))
    assert "tylko do odczytu" in texts(say(client, phone, "przygotuj umowę", case="moja"))
    assert "tylko do odczytu" in texts(say(client, phone, "notatka: x", case="moja"))
    assert "tylko do odczytu" in texts(say(client, phone, "strony: Jan Kowalski", case="moja"))
    # Another identity cannot use someone else's confirmation.
    code = DeviceRegistry(home).invite("drugi", "write")["code"]
    client.post("/v2/devices/redeem", json={"code": code})
    asked = say(client, admin, "cofnij drugi")
    assert "wygasło" in texts(say(client, phone, confirm=asked[0]["token"]))
    assert client.post("/v2/chat", json={"text": "stan"}).status_code == 401


def test_model_problems_arrive_as_a_sentence_not_an_error(tmp_path):
    home = tmp_path / "home"
    admin = {"Authorization": "Bearer " + initialize(home)}
    client = TestClient(create_app(home))
    client.post("/v2/documents", headers=admin, json={
        "name": "a.txt", "expected_version": 0, "case": "s", "content_b64": "YQ=="})
    assert "wyłączone" in texts(say(client, admin, "Kto sprzedaje?", case="s"))
    assert "nie ma dokumentów" in texts(say(client, admin, "Kto sprzedaje?", case="pusta"))


def test_the_workspace_is_the_notarys_own(office):
    client, admin, home, _, _, _ = office
    phone = device(client, admin)
    assert client.get("/v2/layout", headers=phone).json() == {"show": False, "tiles": []}     # simple by default
    offered = say(client, phone, "narzędzia")
    labels = [item["label"] for item in offered[1]["items"]]
    assert "+ Taksa" in labels and "+ Zrób kopię" not in labels                   # workstation tools stay there
    added = say(client, phone, "dodaj kafelek Taksa")
    assert added[0]["layout"] == {"show": True, "tiles": [{"label": "Taksa", "say": "taksa"}]}
    say(client, phone, "dodaj kafelek Pełnomocnictwo KW: przygotuj pełnomocnictwo do wniosku wieczystoksięgowego")
    say(client, phone, "dodaj kafelek Taksa")                                        # no duplicates
    layout = client.get("/v2/layout", headers=phone).json()
    assert [t["label"] for t in layout["tiles"]] == ["Pełnomocnictwo KW", "Taksa"]
    assert layout["tiles"][0]["say"].startswith("przygotuj pełnomocnictwo")
    assert say(client, phone, "ukryj kafelki")[0]["layout"]["show"] is False
    assert say(client, phone, "pokaż kafelki")[0]["layout"]["show"] is True
    assert "Nie znam" in texts(say(client, phone, "dodaj kafelek Zrób kopię"))
    assert len(say(client, phone, "usuń kafelek taksa")[0]["layout"]["tiles"]) == 1
    # Dragging on the page stores the new order through the same layout.
    moved = client.post("/v2/layout", headers=phone, json={"show": True, "tiles": [
        {"label": "B", "say": "dokumenty"}, {"label": "A", "say": "sprawy"}, {"label": "b", "say": "x"}, {"label": "", "say": "x"}]})
    assert [t["label"] for t in moved.json()["tiles"]] == ["B", "A"]
    assert client.post("/v2/layout", headers=phone, json={"tiles": [{"label": str(i), "say": "x"} for i in range(41)]}).status_code == 400
    # Layouts are per device; the panel has its own, with workstation tools.
    assert client.get("/v2/layout", headers=device(client, admin)).json()["tiles"] == []
    assert "+ Zrób kopię" in [i["label"] for i in say(client, admin, "narzędzia")[1]["items"]]
    assert say(client, admin, "dodaj kafelek Zrób kopię")[0]["layout"]["tiles"] == [{"label": "Zrób kopię", "say": "zrób kopię"}]
    assert say(client, phone, "wyczyść pulpit")[0]["layout"] == {"show": False, "tiles": []}
