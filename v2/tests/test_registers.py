"""Land registers and the debtors' register from the chat: confirmed, in the background, into the case."""
import json
import base64
import time

from fastapi.testclient import TestClient

from worker.api import create_app
from worker.init_vault import initialize
from worker.registers import RegisterError, Registers, land_register_numbers, pesels_in

BOOK = {"ok": True, "zrodlo": "test", "tekst": "DZIAŁ IV\\nHIPOTEKA 300 000 ZŁ",
        "ksiega": {"numer_kw": "WA4M/00160286/2", "sad": "SAD REJONOWY TESTOWY",
                   "dzialy": [{"oznaczenie": "I-O", "pusty": False, "tekst": "Działka 1"},
                              {"oznaczenie": "III", "pusty": True, "tekst": "BRAK WPISÓW"},
                              {"oznaczenie": "IV", "pusty": False, "tekst": "Hipoteka umowna 300 000 ZŁ"}]}}


class FakeRegisters:
    def __init__(self):
        self.asked = []

    def land_register(self, number):
        self.asked.append(number)
        if number.endswith("/9"):
            raise RegisterError("Numer księgi jest nieprawidłowy.")
        return BOOK

    def debtors(self, pesel, label="", visible=False, seen=None):
        self.asked.append(pesel)
        return {"maska": pesel[:4] + "*******", "status": "brak_wpisu", "zrodlo": "https://krz.ms.gov.pl/",
                "zrzuty": [(f"krz_prowadzaca_{pesel[:4]}.png", b"\\x89PNG")]}


def office(tmp_path):
    home = tmp_path / "home"
    admin = {"Authorization": "Bearer " + initialize(home)}
    fake = FakeRegisters()
    return TestClient(create_app(home, registers=fake)), admin, fake


def say(client, headers, text, case=None, **extra):
    return client.post("/v2/chat", headers=headers, json={"text": text, "case": case, **extra}).json()["blocks"]


def finish(client, headers, blocks):
    job = next(b for b in blocks if b["type"] == "job")["id"]
    for _ in range(100):
        answer = client.get(f"/v2/jobs/{job}", headers=headers).json()
        if answer["done"]:
            return answer["blocks"]
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def test_numbers_and_pesels_are_found_and_validated():
    assert land_register_numbers("Księga wa4m/00160286/2 i WA4M/00160286/2, PESEL 44051401359") == ["WA4M/00160286/2"]
    assert pesels_in("44051401359, 44051401358, 123") == ["44051401359"]


def test_a_land_register_is_fetched_after_a_yes_and_lands_in_the_case(tmp_path):
    client, admin, fake = office(tmp_path)
    # no case chosen: the program does not send the notary to pick one; it names a case after the number
    assert "do sprawy „kw-wa4m-00160286-2”" in say(client, admin, "sprawdź KW WA4M/00160286/2")[0]["text"]
    asked = say(client, admin, "sprawdź KW WA4M/00160286/2", case="kowalski-2026")
    assert asked[0]["type"] == "confirm" and "płatne" in asked[0]["text"] and fake.asked == []
    started = client.post("/v2/chat", headers=admin, json={"confirm": asked[0]["token"], "case": "kowalski-2026"}).json()["blocks"]
    result = finish(client, admin, started)
    assert fake.asked == ["WA4M/00160286/2"]
    assert "Dział III: brak wpisów" in result[0]["text"] and "Dział IV: Hipoteka umowna 300 000 ZŁ" in result[0]["text"]
    stored = result[1]["items"][0]
    assert stored["name"].startswith("KW WA4M-00160286-2")
    content = base64.b64decode(client.get(f"/v2/documents/{stored['id']}", headers=admin).json()["content_b64"])
    assert "HIPOTEKA" in content.decode()
    assert "Porównaj z dokumentami sprawy" in [i["label"] for i in result[2]["items"]]


def test_without_a_number_the_case_documents_offer_one(tmp_path):
    client, admin, _ = office(tmp_path)
    client.post("/v2/documents", headers=admin, json={"id": None, "expected_version": 0, "name": "umowa.txt", "case": "s",
                                                       "content_b64": base64.b64encode(b"Lokal w KW WA4M/00160286/2.").decode()})
    offered = say(client, admin, "sprawdź księgę", case="s")
    assert [i["say"] for i in offered[1]["items"]] == ["sprawdź KW WA4M/00160286/2"]


def test_krz_checks_every_pesel_of_the_case_and_masks_them(tmp_path):
    client, admin, fake = office(tmp_path)
    client.post("/v2/documents", headers=admin, json={"id": None, "expected_version": 0, "name": "strony.txt", "case": "s",
                                                       "content_b64": base64.b64encode(b"Jan Kowalski PESEL 44051401359").decode()})
    asked = say(client, admin, "sprawdź strony w KRZ", case="s")
    assert asked[0]["type"] == "confirm" and "4405*******" in asked[0]["text"] and "44051401359" not in asked[0]["text"]
    started = client.post("/v2/chat", headers=admin, json={"confirm": asked[0]["token"], "case": "s"}).json()["blocks"]
    result = finish(client, admin, started)
    assert fake.asked == ["44051401359"] and "4405*******: brak wpisu" in result[0]["text"]
    assert "44051401359" not in result[0]["text"]
    assert [i["name"] for i in result[1]["items"]][1] == "krz_prowadzaca_4405.png"


def test_readers_and_strangers_cannot_start_or_see_a_search(tmp_path):
    client, admin, _ = office(tmp_path)
    code = client.post("/v2/devices/invite", headers=admin, json={"name": "t", "scope": "read"}).json()["code"]
    reader = {"Authorization": "Bearer " + client.post("/v2/devices/redeem", json={"code": code}).json()["token"]}
    assert "tylko do odczytu" in say(client, reader, "sprawdź KW WA4M/00160286/2", case="s")[0]["text"]
    asked = say(client, admin, "sprawdź KW WA4M/00160286/2", case="s")
    started = client.post("/v2/chat", headers=admin, json={"confirm": asked[0]["token"], "case": "s"}).json()["blocks"]
    job = next(b for b in started if b["type"] == "job")["id"]
    assert client.get(f"/v2/jobs/{job}", headers=reader).status_code == 404


def test_a_bad_number_is_refused_before_anything_is_paid_for():
    service = Registers(lambda: None, "eu-central-1", invoke=lambda payload: (_ for _ in ()).throw(AssertionError("called")))
    try:
        service.land_register("WA4M/00160286/9")
    except RegisterError as error:
        assert "nieprawidłowy" in str(error)
    else:
        raise AssertionError("accepted")


def test_the_v1_portal_knowledge_loads_in_v2():
    from worker import domain
    portal = domain.krz_portal()
    assert portal.ADRES == "https://krz.ms.gov.pl/" and hasattr(portal, "StronaPlaywright")
    assert portal.rozpoznaj("Nie znaleziono podmiotów")[0] in {"brak_wpisu", "blad"}


def test_the_program_proposes_what_to_do_next_from_what_it_sees(tmp_path):
    client, admin, _ = office(tmp_path)
    client.post("/v2/documents", headers=admin, json={"id": None, "expected_version": 0, "name": "umowa.txt", "case": "s",
                                                       "content_b64": base64.b64encode(
                                                           b"Lokal w KW WA4M/00160286/2, sprzedajacy PESEL 44051401359.").decode()})
    items = client.get("/v2/suggestions", headers=admin, params={"case": "s"}).json()["items"]
    assert [i["say"] for i in items] == ["sprawdź KW WA4M/00160286/2", "sprawdź strony w KRZ",
                                         "przygotuj projekt aktu na podstawie dokumentów sprawy"]
    assert all(i["why"] for i in items)
    hello = client.post("/v2/chat", headers=admin, json={"hello": True, "case": "s"}).json()["blocks"]
    assert any(b.get("text", "").startswith("Proponuję teraz") for b in hello) or any(
        "Przewodnik" in b.get("text", "") for b in hello)
    assert client.get("/v2/suggestions", headers=admin, params={"case": "../x"}).status_code == 404


def test_the_assistant_says_how_it_understood():
    from worker.chat import answer_blocks, understood
    answer = "ROZUMIEM: pytasz o sprzedającego; sprawdzę umowę przedwstępną.\nSprzedaje Jan.\nDALEJ: sprawdź KW"
    assert understood(answer) == ("Sprzedaje Jan.\nDALEJ: sprawdź KW", "pytasz o sprzedającego; sprawdzę umowę przedwstępną.")
    blocks = answer_blocks(answer)
    assert blocks[0]["text"] == "Sprzedaje Jan." and blocks[2]["items"][0]["say"] == "sprawdź KW"


def test_the_case_is_found_from_the_number_in_its_documents(tmp_path):
    client, admin, fake = office(tmp_path)
    note = base64.b64encode("Umowa przedwstępna, KW WA4M/00160286/2".encode()).decode()
    client.post("/v2/documents", headers=admin, json={"expected_version": 0, "name": "umowa.txt",
                                                     "content_b64": note, "case": "kowalski-2026"})
    asked = say(client, admin, "sprawdź KW WA4M/00160286/2")
    assert "do sprawy „kowalski-2026”" in asked[0]["text"]
    offered = say(client, admin, "sprawdź księgę")
    assert "WA4M/00160286/2 (kowalski-2026)" in [i["label"] for i in offered[1]["items"]]
    assert "procedury" not in client.get("/v2/cases", headers=admin).json()


def test_krz_runs_hidden_and_offers_the_window_only_when_that_fails(tmp_path):
    client, admin, fake = office(tmp_path)
    asked = say(client, admin, "sprawdź KRZ 44051401359")
    assert asked[0]["type"] == "confirm" and "w tle, bez otwierania okna" in asked[0]["text"]

    def broken(pesel, label="", visible=False, seen=None):
        if not visible:
            raise RuntimeError("strona nie odpowiedziała")
        fake.asked.append(("okno", pesel))
        return {"maska": pesel[:4] + "*******", "status": "brak_wpisu", "zrodlo": "https://krz.ms.gov.pl/", "zrzuty": []}
    fake.debtors = broken
    started = client.post("/v2/chat", headers=admin, json={"confirm": asked[0]["token"]}).json()["blocks"]
    failed = finish(client, admin, started)
    assert "w tle się nie udało" in failed[0]["text"] and failed[1]["items"][0]["say"] == "sprawdź KRZ w oknie 44051401359"
    again = say(client, admin, failed[1]["items"][0]["say"])
    assert "otworzy krz.ms.gov.pl" in again[0]["text"]
    started = client.post("/v2/chat", headers=admin, json={"confirm": again[0]["token"]}).json()["blocks"]
    assert "brak wpisu" in finish(client, admin, started)[0]["text"] and fake.asked == [("okno", "44051401359")]



def test_the_window_sees_the_krz_page_while_the_search_runs(tmp_path):
    client, admin, fake = office(tmp_path)

    def watched(pesel, label="", visible=False, seen=None):
        seen(b"\xff\xd8\xff-strona-krz")
        return {"maska": pesel[:4] + "*******", "status": "brak_wpisu", "zrodlo": "https://krz.ms.gov.pl/", "zrzuty": []}
    fake.debtors = watched
    asked = say(client, admin, "sprawdź KRZ 44051401359")
    started = client.post("/v2/chat", headers=admin, json={"confirm": asked[0]["token"]}).json()["blocks"]
    finish(client, admin, started)
    lines = client.get("/v2/activity", headers=admin).json()["lines"]
    pictures = [l for l in lines if l.get("image")]
    assert pictures and base64.b64decode(pictures[-1]["image"]).startswith(b"\xff\xd8\xff")
    assert "44051401359" not in json.dumps(lines)
