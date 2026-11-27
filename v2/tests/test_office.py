"""Two workstations of one office: joined once with a code, then one NotarAI."""
import base64
import time

import pytest
from fastapi.testclient import TestClient

import worker.office as office_module
from worker.api import create_app
from worker.init_vault import initialize
from worker.office import OfficeError


@pytest.fixture
def two(tmp_path, monkeypatch):
    printed = []
    monkeypatch.setattr(office_module, "windows_print", lambda name, data, printer=None: printed.append((name, data, printer)))
    monkeypatch.setattr(office_module, "windows_printers", lambda: ["HP Gabinet"])
    stations = {}

    def transport(address, path, body):
        link = stations[address].app.state.office
        return (link.handle_pair if path == "pair" else link.handle_sync)(body)

    made = {}
    for name, address in (("Gabinet", "10.0.0.1:47321"), ("Sekretariat", "10.0.0.2:47321")):
        home = tmp_path / name
        token = initialize(home)
        client = TestClient(create_app(home, office_transport=transport, office_address=lambda a=address: a))
        stations[address] = client
        headers = {"Authorization": "Bearer " + token}
        client.post("/v2/chat", headers=headers, json={"text": f"nazwij stanowisko {name}"})
        made[name] = (client, headers)
    return made, printed


def say(station, text, case=None, **extra):
    client, headers = station
    return client.post("/v2/chat", headers=headers, json={"text": text, "case": case, **extra}).json()["blocks"]


def sync(*stations):
    for client, _ in stations:
        client.app.state.office.sync_once()


def words(blocks):
    return "\n".join(b.get("text", "") for b in blocks)


def join(two):
    (made, _) = two
    code = next(b for b in say(made["Gabinet"], "połącz drugie stanowisko") if b["type"] == "code")["text"]
    assert code.startswith("dołącz do kancelarii 10.0.0.1:47321 ")
    joined = say(made["Sekretariat"], code)
    assert "Połączyłem stanowisko „Sekretariat” ze stanowiskiem „Gabinet”" in words(joined)
    return made["Gabinet"], made["Sekretariat"]


def upload(station, name, data, case="kowalski-2026", doc_id=None, version=0):
    client, headers = station
    return client.post("/v2/documents", headers=headers, json={"id": doc_id, "expected_version": version, "name": name,
                                                              "content_b64": base64.b64encode(data).decode(), "case": case}).json()


def test_documents_calendar_messages_and_deletions_travel_both_ways(two):
    gabinet, sekretariat = join(two)
    doc = upload(gabinet, "umowa.txt", b"wersja Gabinetu")
    say(gabinet, "termin jutro 10:00 akt Kowalski", case="kowalski-2026")
    say(sekretariat, "napisz do Gabinet: klient Kowalski będzie jutro o 12:00")
    sync(gabinet, sekretariat)
    client, headers = sekretariat
    got = client.get(f"/v2/documents/{doc['id']}", headers=headers).json()
    assert base64.b64decode(got["content_b64"]) == b"wersja Gabinetu"
    assert [i["title"] for i in client.get("/v2/calendar", headers=headers).json()["items"]] == ["akt Kowalski"]
    listing = say(gabinet, "wiadomości")
    assert "Sekretariat → Gabinet: klient Kowalski będzie jutro o 12:00" in words(listing)
    assert "Dodaj do kalendarza" in [i["label"] for b in listing if b["type"] == "buttons" for i in b["items"]]
    # the Secretariat edits, the Cabinet receives the next version under the same document
    upload(sekretariat, "umowa.txt", b"poprawka Sekretariatu", doc_id=doc["id"], version=1)
    sync(gabinet)
    client, headers = gabinet
    assert base64.b64decode(client.get(f"/v2/documents/{doc['id']}", headers=headers).json()["content_b64"]) == \
        b"poprawka Sekretariatu"
    # a deletion goes over too
    say(gabinet, "kalendarz")
    say(gabinet, "usuń termin 1", confirm=None)
    asked = say(gabinet, "usuń termin 1")
    if asked and asked[0]["type"] == "confirm":
        gabinet[0].post("/v2/chat", headers=gabinet[1], json={"confirm": asked[0]["token"]})
    sync(sekretariat)
    assert sekretariat[0].get("/v2/calendar", headers=sekretariat[1]).json()["items"] == []


def test_two_edits_of_one_document_never_overwrite_each_other(two):
    gabinet, sekretariat = join(two)
    doc = upload(gabinet, "akt.txt", b"v1")
    sync(sekretariat)
    upload(gabinet, "akt.txt", b"Gabinet v2", doc_id=doc["id"], version=1)
    upload(sekretariat, "akt.txt", b"Sekretariat v2", doc_id=doc["id"], version=1)
    sync(gabinet, sekretariat)
    client, headers = gabinet
    names = [d["name"] for d in client.get("/v2/documents", headers=headers, params={"include_names": True}).json()]
    assert "(konflikt) akt.txt" in names
    assert base64.b64decode(client.get(f"/v2/documents/{doc['id']}", headers=headers).json()["content_b64"]) == b"Gabinet v2"


def test_printing_and_the_screen_of_the_other_station(two):
    (made, printed) = two
    gabinet, sekretariat = join(two)
    upload(sekretariat, "umowa.txt", b"do druku")
    started = say(sekretariat, "wydrukuj umowa.txt w gabinet", case="kowalski-2026")
    job = next(b for b in started if b["type"] == "job")["id"]
    sync(gabinet, sekretariat)
    for _ in range(50):
        answer = sekretariat[0].get(f"/v2/jobs/{job}", headers=sekretariat[1]).json()
        if answer["done"]:
            break
        time.sleep(0.1)
    assert "Wydrukowano umowa.txt na stanowisku Gabinet." in words(answer["blocks"])
    assert printed == [("umowa.txt", b"do druku", None)]
    # the screen: refused until the Cabinet allows it there
    gabinet[0].app.state.office._screen = lambda: b"\xff\xd8JPEG"
    ask = lambda: next(b for b in say(sekretariat, "pokaż ekran gabinet") if b["type"] == "job")["id"]
    first = ask()
    sync(gabinet, sekretariat)
    time.sleep(1.2)
    assert "nie zezwala na podgląd ekranu" in words(sekretariat[0].get(f"/v2/jobs/{first}", headers=sekretariat[1]).json()["blocks"])
    say(gabinet, "zezwól na podgląd ekranu")
    second = ask()
    sync(gabinet, sekretariat)
    time.sleep(1.2)
    shown = sekretariat[0].get(f"/v2/jobs/{second}", headers=sekretariat[1]).json()["blocks"]
    assert shown[1]["type"] == "image" and base64.b64decode(shown[1]["image"]) == b"\xff\xd8JPEG"
    assert "drukarki: HP Gabinet" in words(say(sekretariat, "stanowiska"))


def test_strangers_replays_and_used_codes_are_refused(two):
    gabinet, sekretariat = join(two)
    link_a, link_b = gabinet[0].app.state.office, sekretariat[0].app.state.office
    envelope = link_b.seal({"from": "Sekretariat", "revisions": 0, "notes": 0})
    link_a.handle_sync(envelope)
    with pytest.raises(OfficeError):
        link_a.handle_sync(envelope)                     # the same envelope twice
    with pytest.raises(OfficeError):
        link_a.handle_sync(b"\\x00" * 64)                # not sealed with the office key
    code = link_a.invite().split()[1]
    other = sekretariat[0].app.state.office
    import hashlib
    import hmac
    import json
    proof = hmac.new(code.encode(), b"notarai-office-join", hashlib.sha256).hexdigest()
    link_a.handle_pair(json.dumps({"name": "X", "address": "10.0.0.9:1", "proof": proof}).encode())
    with pytest.raises(OfficeError):
        link_a.handle_pair(json.dumps({"name": "Y", "address": "10.0.0.8:1", "proof": proof}).encode())
    assert other.joined


def test_the_station_name_signs_messages_and_is_part_of_the_guide(two):
    (made, _) = two
    blocks = say(made["Gabinet"], "napisz do Sekretariat: oddzwonić do Nowaka")
    assert words(blocks).startswith("Wysłałem do „Sekretariat”: oddzwonić do Nowaka")
    assert "Gabinet → Sekretariat" in words(say(made["Gabinet"], "wiadomości"))


def test_the_office_network_server_accepts_only_sealed_envelopes(two):
    gabinet, sekretariat = join(two)
    lan = TestClient(gabinet[0].app.state.office_lan_app())
    envelope = sekretariat[0].app.state.office.seal({"from": "Sekretariat", "revisions": 0, "notes": 0})
    answer = lan.post("/office/sync", content=envelope)
    assert answer.status_code == 200 and sekretariat[0].app.state.office.open(answer.content)["from"] == "Gabinet"
    assert lan.post("/office/sync", content=b"plain text").status_code == 403
    assert lan.post("/office/other", content=envelope).status_code == 404
    assert lan.get("/v2/status").status_code == 404                     # nothing of the worker is exposed there


def test_a_message_from_the_other_station_is_proposed_until_read(two):
    gabinet, sekretariat = join(two)
    say(gabinet, "napisz do Sekretariat: proszę przygotować wypisy dla Kowalskiego")
    sync(sekretariat)
    client, headers = sekretariat
    items = client.get("/v2/suggestions", headers=headers).json()["items"]
    assert items[0] == {"label": "Nowe wiadomości (1)", "say": "wiadomości", "why": "od: Gabinet"}
    say(sekretariat, "wiadomości")
    assert all(i["say"] != "wiadomości" for i in client.get("/v2/suggestions", headers=headers).json()["items"])
    assert client.get("/v2/status", headers=headers).json()["station"] == "Sekretariat"
