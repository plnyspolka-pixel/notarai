"""People of the office: the notary creates and blocks logins and limits what each person may do."""
from fastapi.testclient import TestClient

from worker.api import create_app
from worker.init_vault import initialize


class Account:
    signed_in = True

    def __init__(self, email):
        self.who = email

    def email(self):
        return self.who

    def client_factory(self, region=None):
        def factory(service):
            raise RuntimeError("no AWS in tests")
        return factory


class Function:
    """Stands in for notarai-v2-zespol: it trusts the account's token, as Cognito would."""
    def __init__(self, account, notaries):
        self.account, self.notaries, self.people, self.calls = account, set(notaries), {}, []

    def __call__(self, payload):
        self.calls.append(payload)
        me, action = self.account.who, payload["akcja"]
        if action == "kto":
            return {"ok": True, "email": me, "notariusz": me in self.notaries}
        if action == "lista":
            return {"ok": True, "osoby": [{"email": e, "notariusz": e in self.notaries, "aktywne": a}
                                          for e, a in sorted({**{n: True for n in self.notaries}, **self.people}.items())]}
        if me not in self.notaries:
            return {"ok": False, "komunikat": "Konta osób zakłada i zmienia tylko notariusz."}
        email = payload["email"]
        if action == "dodaj":
            new = email not in self.people
            self.people[email] = True
            return {"ok": True, "nowe": new}
        self.people[email] = action == "odblokuj"
        return {"ok": True}


def office(tmp_path, signed_in_as):
    home = tmp_path / "home"
    admin = {"Authorization": "Bearer " + initialize(home)}
    account = Account(signed_in_as)
    function = Function(account, {"notariusz@kancelaria.pl"})
    client = TestClient(create_app(home, account=account, allow_bedrock=False, team_invoke=function))
    return client, admin, account, function


def say(client, admin, sentence):
    response = client.post("/v2/chat", headers=admin, json={"text": sentence})
    assert response.status_code == 200, response.text
    return "\n".join(b.get("text", "") for b in response.json()["blocks"])


def test_the_notary_creates_limits_and_blocks_a_login(tmp_path):
    client, admin, account, function = office(tmp_path, "notariusz@kancelaria.pl")
    answer = say(client, admin, "dodaj osobę rarot@nowanet.pl")
    assert "Założyłem konto rarot@nowanet.pl" in answer and "hasłem tymczasowym" in answer
    assert function.people == {"rarot@nowanet.pl": True}
    assert "nie może teraz: wysyłanie poczty" in say(client, admin, "rarot@nowanet.pl nie może wysyłać poczty")
    listing = say(client, admin, "konta")
    assert "notariusz@kancelaria.pl: notariusz" in listing and "rarot@nowanet.pl: bez: wysyłanie poczty" in listing
    assert "może teraz: wysyłanie poczty" in say(client, admin, "nadaj rarot@nowanet.pl wysyłanie poczty")
    assert "Zablokowałem" in say(client, admin, "zablokuj rarot@nowanet.pl") and function.people["rarot@nowanet.pl"] is False
    assert "(zablokowane)" in say(client, admin, "osoby")
    assert "Odblokowałem" in say(client, admin, "odblokuj rarot@nowanet.pl")
    assert "Swojego konta" in say(client, admin, "zablokuj notariusz@kancelaria.pl")
    for call in function.calls:
        assert set(call) <= {"akcja", "email", "token"}          # no other data leaves the station


def test_the_secretariat_cannot_manage_accounts_and_keeps_to_its_permissions(tmp_path):
    client, admin, account, function = office(tmp_path, "notariusz@kancelaria.pl")
    say(client, admin, "dodaj osobę rarot@nowanet.pl")
    say(client, admin, "rarot@nowanet.pl nie może kalendarz")
    say(client, admin, "rarot@nowanet.pl nie może sprawy")
    account.who = "rarot@nowanet.pl"                      # the secretariat signs in on (a copy of) the station
    answer = say(client, admin, "dodaj osobę ktos@nowanet.pl")
    assert "tylko notariusz" in answer and "ktos@nowanet.pl" not in function.people
    refused = say(client, admin, "termin jutro 10:00 podpisanie aktu")
    assert "Notariusz nie dał Ci uprawnienia: kalendarz i komunikator" in refused
    saved = client.post("/v2/documents", headers=admin, json={"expected_version": 0, "name": "a.txt", "content_b64": "YQ=="})
    assert saved.status_code == 403 and "sprawy i dokumenty" in saved.text


def test_a_sentence_about_a_secretariat_station_gets_the_steps_not_advice(tmp_path):
    client, admin, account, function = office(tmp_path, "notariusz@kancelaria.pl")
    answer = say(client, admin, "stwórz stanowisko w kancelarii ale dla sekretariatu")
    assert "dodaj osobę" in answer and "połącz drugie stanowisko" in answer and "Jaki adres e-mail" in answer


def test_the_assistant_runs_program_commands_instead_of_advising(tmp_path):
    import json
    from worker.inference import Inference
    from worker.policy import EU_REGIONS, Policy
    from worker.usage import UsageLedger
    from worker.init_vault import initialize as init

    class Bedrock:
        replies = ["ROZUMIEM: chodzi o konto.\nPOLECENIE: dodaj osobę rarot@nowanet.pl\nPOLECENIE: zablokuj stary@nowanet.pl"]

        def get_model_invocation_logging_configuration(self):
            return {}

        def get_inference_profile(self, inferenceProfileIdentifier):
            return {"models": [{"modelArn": f"arn:aws:bedrock:{r}::foundation-model/x"} for r in EU_REGIONS]}

        def converse(self, **kwargs):
            return {"output": {"message": {"content": [{"text": self.replies.pop(0)}]}}, "stopReason": "end_turn",
                    "usage": {"inputTokens": 1, "outputTokens": 1}}

    home = tmp_path / "h2"
    admin = {"Authorization": "Bearer " + init(home)}
    account = Account("notariusz@kancelaria.pl")
    function = Function(account, {"notariusz@kancelaria.pl"})
    inference = Inference(Policy("eu-central-1", "eu.anthropic.claude-sonnet-4-6"), lambda s: Bedrock(), UsageLedger(home))
    client = TestClient(create_app(home, account=account, inference=inference, team_invoke=function))
    response = client.post("/v2/chat", headers=admin, json={"text": "Ania potrzebuje wejścia do NotarAI na swoim komputerze"})
    blocks = response.json()["blocks"]
    words = json.dumps(blocks, ensure_ascii=False)
    assert "Założyłem konto rarot@nowanet.pl" in words and function.people == {"rarot@nowanet.pl": True}
    assert "zablokuj stary@nowanet.pl" in words and "stary@nowanet.pl" not in function.people   # only offered
