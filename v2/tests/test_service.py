"""Service mode: a sentence asks for a change; it leaves the computer without personal data."""
import json

from fastapi.testclient import TestClient

from worker.api import create_app
from worker.init_vault import initialize


def office(tmp_path, sent):
    home = tmp_path / "home"
    admin = {"Authorization": "Bearer " + initialize(home)}
    client = TestClient(create_app(home, service_send=sent.append))
    return client, admin, home


def say(client, admin, text, case=None):
    return client.post("/v2/chat", headers=admin, json={"text": text, "case": case}).json()["blocks"]


def test_a_change_request_leaves_without_names_or_numbers(tmp_path):
    sent = []
    client, admin, home = office(tmp_path, sent)
    say(client, admin, "nowa sprawa kowalski-2026")
    say(client, admin, "strony: Jan Kowalski, Anna Nowak", case="kowalski-2026")
    reply = say(client, admin, "popraw program: przy akcie Kowalskiego (PESEL 44051401359) przycisk Wyślij ma być większy")
    assert reply[0]["text"].startswith("Przyjąłem prośbę Z-")
    assert sent and "Kowalsk" not in json.dumps(sent, ensure_ascii=False) and "44051401359" not in json.dumps(sent)
    assert sent[0]["tresc"].endswith("przycisk Wyślij ma być większy") and set(sent[0]) == {"id", "tresc", "stanowisko", "wersja"}
    listing = say(client, admin, "moje zgłoszenia")[0]["text"]
    assert sent[0]["id"] in listing and "wysłane, w przygotowaniu" in listing


def test_an_update_that_closes_the_request_says_so_once(tmp_path):
    sent = []
    client, admin, home = office(tmp_path, sent)
    say(client, admin, "zmień program: po zapisaniu aktu otwieraj go w Wordzie")
    ident = sent[0]["id"]
    client.app.state.desk = None
    from worker.service import ServiceDesk
    desk = ServiceDesk(home, None, lambda: None, "eu-central-1", lambda: "Gabinet", lambda: "2.4.2", send=sent.append)
    assert [i["id"] for i in desk.delivered([{"id": ident, "opis": "Zapisany akt otwiera się w Wordzie."}])] == [ident]
    assert desk.delivered([{"id": ident, "opis": "x"}]) == []
    assert "DZIAŁA" in say(client, admin, "moje zgłoszenia")[0]["text"]


def test_without_a_sign_in_the_request_is_kept_and_the_reason_said(tmp_path):
    home = tmp_path / "home"
    admin = {"Authorization": "Bearer " + initialize(home)}
    client = TestClient(create_app(home))
    reply = say(client, admin, "popraw program: kalendarz ma pokazywać cały tydzień")
    assert "Zaloguj stanowisko" in reply[0]["text"]
    assert "nie wysłane" in say(client, admin, "tryb serwisowy")[0]["text"]
