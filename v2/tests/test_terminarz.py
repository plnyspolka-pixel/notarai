"""Office calendar: dates read by code, entries encrypted in the vault, managed by talking."""
import datetime as dt

import pytest
from fastapi.testclient import TestClient

from worker.api import create_app
from worker.init_vault import initialize
from worker.terminarz import Calendar, parse_when

NOW = dt.datetime(2026, 11, 27, 15, 0)     # a Friday


@pytest.mark.parametrize("sentence, start, rest", [
    ("jutro 10:00 podpisanie aktu Kowalski", dt.datetime(2026, 11, 28, 10, 0), "podpisanie aktu Kowalski"),
    ("w piątek o 12 Nowak", dt.datetime(2026, 12, 4, 12, 0), "Nowak"),
    ("5 grudnia 9:30 odbiór wypisu", dt.datetime(2026, 12, 5, 9, 30), "odbiór wypisu"),
    ("12.01 o 11 umowa deweloperska", dt.datetime(2027, 1, 12, 11, 0), "umowa deweloperska"),
    ("3 marca 2027 akt poświadczenia dziedziczenia", dt.datetime(2027, 3, 3, 9, 0), "akt poświadczenia dziedziczenia"),
    ("dziś 16.30 telefon do banku", dt.datetime(2026, 11, 27, 16, 30), "telefon do banku"),
    ("w poniedziałek 8:15 Wiśniewski", dt.datetime(2026, 11, 30, 8, 15), "Wiśniewski"),
])
def test_polish_dates_are_read_by_code(sentence, start, rest):
    assert parse_when(sentence, NOW) == (start, rest)


def test_no_day_no_appointment():
    assert parse_when("płatności w umowie", NOW) is None
    assert parse_when("31.02 coś", NOW) is None


def office(tmp_path):
    home = tmp_path / "home"
    token = initialize(home)
    app = create_app(home)
    return TestClient(app), {"Authorization": "Bearer " + token}, home


def say(client, headers, text, case=None):
    return client.post("/v2/chat", headers=headers, json={"text": text, "case": case}).json()["blocks"]


def words(blocks):
    return "\n".join(b.get("text", "") for b in blocks)


def test_appointments_by_talking_listed_and_removed_with_a_yes(tmp_path):
    client, admin, home = office(tmp_path)
    tomorrow = (dt.date.today() + dt.timedelta(days=1)).strftime("%d.%m.%Y")
    added = say(client, admin, f"termin {tomorrow} 10:00 podpisanie aktu Kowalski", case="kowalski-2026")
    assert "Zapisałem w kalendarzu: jutro 10:00, podpisanie aktu Kowalski (sprawa „kowalski-2026”)" in words(added)
    say(client, admin, "dodaj termin dziś 23:59 telefon do banku")
    listed = say(client, admin, "kalendarz")
    assert "1. dziś 23:59  telefon do banku" in words(listed) and "[kowalski-2026]" in words(listed)
    assert "podpisanie aktu" in words(say(client, admin, "co mam jutro"))
    assert "Dziś: 23:59 telefon do banku" in words(client.post("/v2/chat", headers=admin, json={"hello": True}).json()["blocks"])
    items = client.get("/v2/calendar", headers=admin).json()["items"]
    assert [i["title"] for i in items] == ["telefon do banku", "podpisanie aktu Kowalski"]
    say(client, admin, "kalendarz")                       # numbers refer to the last listing
    asked = say(client, admin, "usuń termin 1")
    assert asked[0]["type"] == "confirm"
    client.post("/v2/chat", headers=admin, json={"confirm": asked[0]["token"]})
    assert [i["title"] for i in client.get("/v2/calendar", headers=admin).json()["items"]] == ["podpisanie aktu Kowalski"]
    assert b"Kowalski" not in (home / "vault.sqlite3").read_bytes()          # encrypted at rest


def test_a_question_about_a_term_in_a_case_is_not_an_appointment(tmp_path):
    client, admin, _ = office(tmp_path)
    assert "Kiedy?" not in words(say(client, admin, "termin płatności w umowie?"))
    assert "zdaniem" in words(say(client, admin, "dodaj termin"))
    assert client.get("/v2/calendar", headers=admin).json()["items"] == []


def test_devices_see_only_their_cases_and_readers_cannot_add(tmp_path):
    client, admin, _ = office(tmp_path)
    say(client, admin, "termin jutro 10:00 Kowalski", case="kowalski-2026")
    say(client, admin, "termin jutro 11:00 Nowak", case="nowak-2026")
    code = client.post("/v2/devices/invite", headers=admin,
                       json={"name": "t", "scope": "read", "cases": ["nowak-2026"]}).json()["code"]
    reader = {"Authorization": "Bearer " + client.post("/v2/devices/redeem", json={"code": code}).json()["token"]}
    assert [i["title"] for i in client.get("/v2/calendar", headers=reader).json()["items"]] == ["Nowak"]
    assert "tylko do odczytu" in words(say(client, reader, "termin jutro 12:00 coś"))


def test_an_appointment_heard_in_a_conversation_is_marked_for_checking(tmp_path):
    client, admin, home = office(tmp_path)
    from worker.local_secrets import read_secret
    from worker.vault import Vault
    calendar = Calendar(Vault(home, read_secret(home, "vault.key")), clock=lambda: NOW)
    entry = calendar.from_note("w poniedziałek o 10", "Rozmowa telefoniczna: Jan Nowak", "sekretariat")
    assert entry["start"] == "2026-11-30T10:00" and entry["source"] == "rozmowa"
    assert "do sprawdzenia" in entry["title"]
    assert calendar.from_note("jak najszybciej", "Rozmowa", "sekretariat") is None
