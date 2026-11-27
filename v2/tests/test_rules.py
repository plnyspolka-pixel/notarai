"""Hard office rules: parsed from the notary's sentence, stored in the vault, enforced by code."""
from datetime import datetime

import pytest

from worker.init_vault import initialize
from worker.local_secrets import read_secret
from worker.rules import RuleViolation, Rules, describe, is_working_day, parse
from worker.vault import Vault


@pytest.fixture
def rules(tmp_path):
    home = tmp_path / "home"
    initialize(home)
    return Rules(Vault(home, read_secret(home, "vault.key"))), home


@pytest.mark.parametrize("sentence,rule", [
    ("każdy akt musi zawierać „Notariusz pouczył strony o treści art. 91 Prawa o notariacie”",
     {"rodzaj": "musi_zawierac", "tekst": "Notariusz pouczył strony o treści art. 91 Prawa o notariacie", "dotyczy": ""}),
    ("akty sprzedaży zawsze zawierają \"oświadczenie o braku zaległości podatkowych\"",
     {"rodzaj": "musi_zawierac", "tekst": "oświadczenie o braku zaległości podatkowych", "dotyczy": "sprzedaży"}),
    ("nigdy nie pisz „Szanowny Panie”", {"rodzaj": "nie_moze_zawierac", "tekst": "Szanowny Panie", "dotyczy": ""}),
    ("wysyłka wniosków tylko w dni robocze od 8 do 15", {"rodzaj": "godziny_wysylki", "od": 8, "do": 15}),
    ("przed wysłaniem pole „PESEL wnioskodawcy” musi być wypełnione w „Wniosek o wpis w KW”",
     {"rodzaj": "pole_wymagane", "tekst": "PESEL wnioskodawcy", "dotyczy": "Wniosek o wpis w KW"}),
    ("pseudonimizacja zawsze włączona", {"rodzaj": "pseudonimizacja"}),
    ("bądź miły dla klientów", None),
    ("akty mają być ładne", None),
])
def test_sentences_become_rules_only_when_code_can_check_them(sentence, rule):
    assert parse(sentence) == rule


def test_documents_are_checked_against_the_rules(rules):
    store, home = rules
    store.add({"rodzaj": "musi_zawierac", "tekst": "Notariusz pouczył strony o treści art. 91"}, "local-admin")
    store.add({"rodzaj": "musi_zawierac", "tekst": "braku zaległości podatkowych", "dotyczy": "sprzedaży"}, "local-admin")
    store.add({"rodzaj": "nie_moze_zawierac", "tekst": "Szanowny Panie"}, "local-admin")
    with pytest.raises(ValueError):
        store.add({"rodzaj": "nie_moze_zawierac", "tekst": "Szanowny Panie"}, "local-admin")
    with pytest.raises(ValueError):
        store.add({"rodzaj": "cokolwiek", "tekst": "x"}, "local-admin")
    good = "AKT NOTARIALNY. Umowa darowizny. NOTARIUSZ POUCZYŁ STRONY  o treści art. 91."
    store.check_document("darowizna.docx", good)
    with pytest.raises(RuleViolation) as error:
        store.check_document("umowa sprzedazy.docx", good + " Szanowny Panie!")
    message = str(error.value)
    assert "2. Każdy dokument (sprzedaży) musi zawierać" in message and "3. Żaden dokument" in message
    assert "1." not in message.split(":")[1][:3]
    store.check_document("umowa sprzedazy.docx", good + " Oświadczenie o braku zaległości podatkowych.")
    assert b"Szanowny" not in (home / "vault.sqlite3").read_bytes()          # stored encrypted
    removed = store.remove(3, "local-admin")
    assert removed["tekst"] == "Szanowny Panie" and len(store.all()) == 2
    with pytest.raises(ValueError):
        store.remove(9, "local-admin")


def test_sending_is_checked_against_the_rules(rules):
    store, _ = rules
    store.add({"rodzaj": "godziny_wysylki", "od": 8, "do": 15}, "local-admin")
    store.add({"rodzaj": "pole_wymagane", "tekst": "PESEL wnioskodawcy", "dotyczy": "wpis w KW"}, "local-admin")
    report = [{"field": "PESEL wnioskodawcy", "state": "filled", "value": "44051401359"}]
    tuesday_morning = datetime(2026, 12, 1, 10, 0)
    store.check_send("Wniosek o wpis w KW", report, tuesday_morning)
    with pytest.raises(RuleViolation):
        store.check_send("Wniosek o wpis w KW", report, datetime(2026, 12, 1, 15, 30))       # after hours
    with pytest.raises(RuleViolation):
        store.check_send("Wniosek o wpis w KW", report, datetime(2026, 11, 28, 10, 0))      # Saturday
    with pytest.raises(RuleViolation):
        store.check_send("Wniosek o wpis w KW", report, datetime(2026, 12, 24, 10, 0))      # Christmas Eve
    with pytest.raises(RuleViolation) as error:
        store.check_send("Wniosek o wpis w KW", [{"field": "PESEL wnioskodawcy", "state": "missing", "value": ""}],
                         tuesday_morning)
    assert "PESEL wnioskodawcy" in str(error.value)
    store.check_send("Zgłoszenie do CRBR", [], tuesday_morning)        # the field rule is for another form


def test_working_days_and_pseudonymisation_lock(rules):
    store, _ = rules
    assert not is_working_day(datetime(2027, 3, 29).date())      # Easter Monday 2027
    assert not is_working_day(datetime(2027, 5, 27).date())      # Corpus Christi 2027
    assert is_working_day(datetime(2027, 3, 30).date())
    store.check_setting(False)
    store.add({"rodzaj": "pseudonimizacja"}, "local-admin")
    with pytest.raises(RuleViolation):
        store.check_setting(False)
    store.check_setting(True)
    assert describe({"rodzaj": "pseudonimizacja"}) == "Pseudonimizacji nie można wyłączyć."


# ---------------------------------------------------------------- enforced through the whole worker
def _office(tmp_path):
    import json

    from fastapi.testclient import TestClient

    from worker.api import create_app
    from worker.inference import Inference
    from worker.policy import EU_REGIONS, Policy
    from worker.usage import UsageLedger

    class Bedrock:
        prompts = []

        def get_model_invocation_logging_configuration(self):
            return {}

        def get_inference_profile(self, inferenceProfileIdentifier):
            return {"models": [{"modelArn": f"arn:aws:bedrock:{r}::foundation-model/x"} for r in EU_REGIONS]}

        def converse(self, **kwargs):
            self.prompts.append(kwargs["messages"][0]["content"][-1]["text"])
            return {"output": {"message": {"content": [{"text": "# UMOWA SPRZEDAŻY\nSzanowny Panie, sprzedaję lokal."}]}},
                    "stopReason": "end_turn", "usage": {"inputTokens": 1, "outputTokens": 1}}

    home = tmp_path / "home"
    admin = {"Authorization": "Bearer " + initialize(home)}
    bedrock, opened = Bedrock(), []
    inference = Inference(Policy("eu-central-1", "eu.anthropic.claude-sonnet-4-6"), lambda s: bedrock, UsageLedger(home))
    client = TestClient(create_app(home, inference=inference, opener=opened.append))
    code = client.post("/v2/devices/invite", headers=admin, json={"name": "t", "scope": "write"}).json()["code"]
    phone = {"Authorization": "Bearer " + client.post("/v2/devices/redeem", json={"code": code}).json()["token"]}
    return client, admin, phone, bedrock, opened, home, json


def test_rules_are_set_in_the_chat_and_block_what_breaks_them(tmp_path):
    import base64

    client, admin, phone, bedrock, opened, home, json = _office(tmp_path)

    def say(headers, sentence, **extra):
        return client.post("/v2/chat", headers=headers, json={"text": sentence, "case": "k", **extra}).json()["blocks"]

    def texts(blocks):
        return "\n".join(b.get("text", "") for b in blocks)

    assert "nie ma jeszcze" in texts(say(admin, "zasady"))
    assert "w panelu stanowiska" in texts(say(phone, "zasada: nigdy „Szanowny Panie”"))
    assert "nie umiem sprawdzać kodem" in texts(say(admin, "zasada: pisz ładnie"))
    added = say(admin, "zasada: nigdy nie pisz „Szanowny Panie”")
    assert "Dodałem twardą zasadę: Żaden dokument nie może zawierać „Szanowny Panie”" in texts(added)
    assert added[-1] == {"type": "rules"}
    say(admin, "zasada: akty sprzedaży muszą zawierać „Notariusz pouczył strony o art. 91”")
    assert client.get("/v2/rules", headers=phone).json()[1] == {
        "number": 2, "text": "Każdy dokument (sprzedaży) musi zawierać „Notariusz pouczył strony o art. 91”."}
    assert "Usuń zasadę" not in json.dumps(say(phone, "zasady"), ensure_ascii=False)

    # A draft that breaks the rules is not stored; the model was asked for the required wording.
    client.post("/v2/documents", headers=admin, json={"name": "notatka.txt", "expected_version": 0, "case": "k",
                                                       "content_b64": base64.b64encode("Sprzedaż lokalu.".encode()).decode()})
    proposal = next(b for b in say(admin, "przygotuj umowę sprzedaży") if b["type"] == "proposal")
    assert "Notariusz pouczył strony o art. 91" in bedrock.prompts[-1]
    refused = client.post(f"/v2/drafts/{proposal['id']}/approve", headers=admin, json={"name": "umowa.docx"})
    assert refused.status_code == 409 and "łamie zasady kancelarii" in refused.json()["detail"]
    assert "1. Żaden dokument" in refused.json()["detail"] and "2. Każdy dokument (sprzedaży)" in refused.json()["detail"]
    assert all(d["name"] != "umowa.docx" for d in client.get("/v2/documents?include_names=true", headers=admin).json())
    fixed = ["# UMOWA SPRZEDAŻY", "Sprzedaję lokal.", "Notariusz pouczył strony o art. 91."]
    ok = client.post(f"/v2/drafts/{proposal['id']}/approve", headers=admin, json={"name": "umowa.docx", "paragraphs": fixed})
    assert ok.status_code == 200 and ok.json()["state"] == "verified"

    # Editing in Word cannot slip it in either; the working copy is kept.
    say(admin, "otwórz umowa w Wordzie")
    from docx import Document

    document = Document(opened[0])
    document.add_paragraph("Szanowny Panie, dopisek.")
    document.save(opened[0])
    blocked = texts(say(admin, "zapisz do sejfu"))
    assert "łamie zasady kancelarii" in blocked and "Kopia robocza została zachowana" in blocked and opened[0].exists()

    # Removing a rule asks first, and only the workstation may do it.
    assert "w panelu stanowiska" in texts(say(phone, "usuń zasadę 1"))
    confirm = next(b for b in say(admin, "usuń zasadę 1") if b["type"] == "confirm")
    assert len(client.get("/v2/rules", headers=admin).json()) == 2
    assert "Usunąłem zasadę" in texts(client.post("/v2/chat", headers=admin, json={"confirm": confirm["token"]}).json()["blocks"])
    assert "jako wersję 2" in texts(say(admin, "zapisz do sejfu"))


def test_pseudonymisation_rule_locks_the_setting(tmp_path):
    client, admin, phone, bedrock, opened, home, json = _office(tmp_path)

    def say(sentence):
        return "\n".join(b.get("text", "") for b in client.post("/v2/chat", headers=admin, json={"text": sentence}).json()["blocks"])

    assert "Dodałem twardą zasadę" in say("zasada: pseudonimizacja zawsze włączona")
    assert "nie pozwala wyłączyć pseudonimizacji" in say("wyłącz pseudonimizację")
    current = client.get("/v2/settings", headers=admin).json()
    current["ai"]["pseudonymize"] = False
    assert client.put("/v2/settings", headers=admin, json=current).status_code == 403
    assert client.get("/v2/settings", headers=admin).json()["ai"]["pseudonymize"] is True


def test_a_form_is_not_sent_against_the_rules():
    from types import SimpleNamespace

    from worker.autofill import Autofill, Control, FillError

    class Window:
        sent = False

        def controls(self):
            return [Control("pesel", "text", "PESEL wnioskodawcy", ""), Control("send", "button", "Wyślij")]

        def focus(self, title):
            pass

        def type(self, control, value):
            pass

        def read(self, control):
            return ""

        def click(self, control):
            self.sent = True

        def where(self):
            return "okno"

        def snapshot(self):
            return None

    class AlwaysClosed:
        @staticmethod
        def check_send(procedure, report):
            from worker.rules import RuleViolation

            raise RuleViolation("Nie wyślę, bo to łamie zasady kancelarii: 1. Formularze wysyłam tylko w dni robocze.")

    window = Window()
    autofill = Autofill({"program": lambda: window}, rules=AlwaysClosed())
    procedure = SimpleNamespace(nazwa="Wniosek", rodzaj="program", adres="okno", kroki=[
        SimpleNamespace(pole="PESEL wnioskodawcy", zrodlo="", dlaczego="", akcja=""),
        SimpleNamespace(pole="Wyślij", zrodlo="", dlaczego="", akcja="wyslij")])
    preview = autofill.fill(procedure, [{"value": "1"}, {"value": "kliknij"}], actor="a", case="k")
    with pytest.raises(FillError) as error:
        autofill.send(preview["token"], "a", "program")
    assert "dni robocze" in str(error.value) and not window.sent
