"""The computer agent: files, Word documents, Windows programs and web pages, driven by a fake model."""
import json
import time

import pytest
from docx import Document
from fastapi.testclient import TestClient

from worker.agent import Agent, Computer, act_kind, asked_for
from worker.api import create_app
from worker.autofill import Control
from worker.inference import Inference
from worker.init_vault import initialize
from worker.policy import EU_REGIONS, Policy
from worker.usage import UsageLedger


def script(*steps):
    replies = [json.dumps(s, ensure_ascii=False) for s in steps]
    seen = []

    def ask(system, question):
        seen.append(question)
        return replies.pop(0)
    return ask, seen


class FakeDesktop:
    def __init__(self):
        self.clicked, self.typed, self.title = [], {}, None
        self.fields = [Control("n", "text", "Numer aktu", "", []), Control("w", "button", "Wyślij", "", []),
                       Control("z", "button", "Zapisz", "", [])]

    def windows(self):
        return ["RejNET - Repertorium", "Dokument1 - Word"]

    def focus(self, title):
        self.title = title

    def controls(self):
        return self.fields

    def where(self):
        return "RejNET - Repertorium"

    def type(self, control, value):
        self.typed[control.label] = value

    def read(self, control):
        return self.typed.get(control.label, "")

    def click(self, control):
        self.clicked.append(control.label)


def a_docx(path, text):
    document = Document()
    document.add_paragraph(text)
    document.save(path)


def test_finds_reads_and_corrects_a_word_document(tmp_path):
    desk = tmp_path / "Pulpit"
    desk.mkdir()
    a_docx(desk / "akt Kowalski.docx", "Kraków, dnia 12 listopada 2026 roku")
    computer = Computer(tmp_path / "home", roots=lambda: [desk])
    ask, seen = script(
        {"po_co": "szukam aktu", "krok": "szukaj", "nazwa": "kowalski", "folder": ""},
        {"po_co": "czytam", "krok": "czytaj", "plik": str(desk / "akt Kowalski.docx")},
        {"po_co": "poprawiam datę", "krok": "zamien", "plik": str(desk / "akt Kowalski.docx"),
         "stare": "12 listopada", "nowe": "14 listopada"},
        {"krok": "koniec", "odpowiedz": "Poprawiłem datę na 14 listopada."})
    lines = []
    result = Agent(computer, ask, narrate=lines.append).run("popraw datę w akcie Kowalskiego na 14 listopada")
    assert result["answer"] == "Poprawiłem datę na 14 listopada." and len(result["steps"]) == 3
    assert "14 listopada 2026" in Document(str(desk / "akt Kowalski.docx")).paragraphs[0].text
    assert len(list((tmp_path / "home" / "kopie-przed-zmiana").iterdir())) == 1      # previous version kept
    assert "Kraków, dnia 12 listopada" in seen[2]                                     # the model saw the text
    assert lines[0].startswith("Krok 1: szukam aktu")


def test_office_rules_hold_back_a_document_change(tmp_path):
    class Rules:
        def check_document(self, name, text):
            from worker.rules import RuleViolation
            raise RuleViolation("brak „Notariusz pouczył strony”")
    path = tmp_path / "a.docx"
    a_docx(path, "Kraków 12")
    ask, _ = script({"krok": "zamien", "plik": str(path), "stare": "12", "nowe": "14"}, {"krok": "koniec", "odpowiedz": "x"})
    result = Agent(Computer(tmp_path / "h", roots=lambda: [tmp_path], rules=Rules()), ask).run("popraw datę")
    assert "Zasada kancelarii" in result["steps"][0]["wynik"]
    assert Document(str(path)).paragraphs[0].text == "Kraków 12"


def test_no_deleting_and_no_overwriting(tmp_path):
    (tmp_path / "x.txt").write_text("a")
    ask, _ = script({"krok": "usun_plik", "plik": str(tmp_path / "x.txt")},
                    {"krok": "nowy_plik", "plik": str(tmp_path / "x.txt"), "tekst": "b"}, {"krok": "koniec", "odpowiedz": "ok"})
    result = Agent(Computer(tmp_path / "h", roots=lambda: [tmp_path]), ask).run("zrób porządek")
    assert all(s["wynik"].startswith("BŁĄD") for s in result["steps"]) and (tmp_path / "x.txt").read_text() == "a"


def test_sending_needs_the_notarys_own_words(tmp_path):
    desktop = FakeDesktop()
    computer = Computer(tmp_path, desktop=lambda: desktop)
    steps = ({"krok": "wpisz", "okno": "RejNET", "pole": "Numer aktu", "wartosc": "1234/2026"},
             {"krok": "kliknij", "okno": "RejNET", "przycisk": "Wyślij"}, {"krok": "koniec", "odpowiedz": "Wysłane."})
    ask, _ = script(*steps)
    stopped = Agent(computer, ask).run("wpisz numer aktu 1234/2026 w RejNET")
    assert stopped["stopped"]["kind"] == "wyslanie" and desktop.clicked == [] and desktop.typed == {"Numer aktu": "1234/2026"}
    ask, _ = script(*steps)
    done = Agent(computer, ask).run("wpisz numer aktu 1234/2026 w RejNET i wyślij")
    assert done["answer"] == "Wysłane." and desktop.clicked == ["Wyślij"]
    assert act_kind("Zapisz") is None and act_kind("Usuń wpis") == "usuniecie"
    assert asked_for("sprawdź kupującego") == set() and asked_for("złóż wniosek") == {"wyslanie"}


class Bedrock:
    def __init__(self, replies):
        self.replies = replies

    def get_model_invocation_logging_configuration(self):
        return {}

    def get_inference_profile(self, inferenceProfileIdentifier):
        return {"models": [{"modelArn": f"arn:aws:bedrock:{r}::foundation-model/x"} for r in EU_REGIONS]}

    def converse(self, **kwargs):
        return {"output": {"message": {"content": [{"text": self.replies.pop(0)}]}}, "stopReason": "end_turn",
                "usage": {"inputTokens": 1, "outputTokens": 1}}


def wait(client, headers, job):
    for _ in range(200):
        answer = client.get(f"/v2/jobs/{job}", headers=headers).json()
        if answer.get("blocks") is not None:
            return answer["blocks"]
        time.sleep(0.05)
    raise AssertionError("job did not finish")


@pytest.fixture
def office(tmp_path):
    home = tmp_path / "home"
    token = initialize(home)
    desk = tmp_path / "Pulpit"
    desk.mkdir()
    desktop = FakeDesktop()
    replies = []
    bedrock = Bedrock(replies)
    inference = Inference(Policy("eu-central-1", "eu.anthropic.claude-sonnet-4-6"), lambda s: bedrock, UsageLedger(home))
    client = TestClient(create_app(home, inference=inference, computer_roots=[desk],
                                   fill_targets={"program": lambda: desktop, "strona": lambda: None}))
    return client, {"Authorization": "Bearer " + token}, desk, desktop, replies


def test_the_chat_acts_on_the_computer_and_asks_before_an_unrequested_send(office):
    client, admin, desk, desktop, replies = office
    (desk / "notatka.txt").write_text("Akt 1234/2026", encoding="utf-8")
    replies += [json.dumps({"po_co": "czytam notatkę", "krok": "czytaj", "plik": str(desk / "notatka.txt")}),
                json.dumps({"krok": "wpisz", "okno": "RejNET", "pole": "Numer aktu", "wartosc": "1234/2026"}),
                json.dumps({"krok": "kliknij", "okno": "RejNET", "przycisk": "Wyślij"}),
                json.dumps({"krok": "kliknij", "okno": "RejNET", "przycisk": "Wyślij"}),
                json.dumps({"krok": "koniec", "odpowiedz": "Wpisałem i wysłałem."})]
    blocks = client.post("/v2/chat", headers=admin, json={"text": "otwórz notatkę na pulpicie i wpisz numer do RejNET"}).json()["blocks"]
    job = next(b["id"] for b in blocks if b["type"] == "job")
    asked = wait(client, admin, job)
    assert asked[0]["type"] == "confirm" and "Wyślij" in asked[0]["text"] and desktop.clicked == []
    resumed = client.post("/v2/chat", headers=admin, json={"confirm": asked[0]["token"]}).json()["blocks"]
    job = next(b["id"] for b in resumed if b["type"] == "job")
    done = wait(client, admin, job)
    assert "Wpisałem i wysłałem." in done[0]["text"] and desktop.clicked == ["Wyślij"]
    lines = client.get("/v2/activity", headers=admin).json()["lines"]
    assert any("czytam notatkę" in l["text"] for l in lines)


def test_the_assistant_never_says_it_has_no_access(office):
    client, admin, desk, desktop, replies = office
    replies += ["AGENT: sprawdź, jakie programy są otwarte", json.dumps({"krok": "okna"}),
                json.dumps({"krok": "koniec", "odpowiedz": "Otwarte: RejNET i Word."})]
    blocks = client.post("/v2/chat", headers=admin, json={"text": "co mam teraz otwarte?"}).json()["blocks"]
    job = next(b["id"] for b in blocks if b["type"] == "job")
    assert "RejNET i Word" in wait(client, admin, job)[0]["text"]


# ---- 2.6.1: how the chat reaches the agent (the model's real answers, not the ideal one)
def test_spoken_sentences_reach_the_agent_by_code():
    from worker.chat import looks_like_computer_task, norm
    for sentence in ("proszę wejdź na stronę ekw.ms.gov.pl", "kliknij w przeglądarce przycisk dalej",
                     "Dobra, słuchaj, wejdź mi w przeglądarce na stronę ekw", "czy możesz otworzyć przeglądarkę",
                     "podłącz się do programu RejNET i obsłuż go"):
        assert looks_like_computer_task(norm(sentence)), sentence
    for sentence in ("czy zasiedzenie wymaga aktu?", "sprawdź KW WA1M/00012345/6", "otwórz stronę https://x.pl",
                     "a czy notariusz może odmówić"):
        assert not looks_like_computer_task(norm(sentence)), sentence


def test_an_agent_line_is_found_wherever_the_model_puts_it():
    from worker.chat import wants_the_computer
    assert wants_the_computer("ROZUMIEM: mam otworzyć RejNET.\n\nAGENT: uruchom RejNET\n\nDALEJ: wpisz akt")
    assert wants_the_computer("**AGENT:** uruchom notatnik")
    assert not wants_the_computer("ROZUMIEM: pytanie o pośrednika.\n\nAgent nieruchomości: biuro Dom.")
    assert not wants_the_computer("")


def test_the_agent_starts_although_the_model_answers_with_rozumiem_first(office):
    client, admin, desk, desktop, replies = office
    replies += ["ROZUMIEM: mam sprawdzić otwarte programy.\n\nAGENT: sprawdź otwarte okna\n\nDALEJ: otwórz Word",
                json.dumps({"krok": "okna"}), json.dumps({"krok": "koniec", "odpowiedz": "Otwarte: RejNET i Word."})]
    blocks = client.post("/v2/chat", headers=admin, json={"text": "a co ja mam teraz pootwierane?"}).json()["blocks"]
    assert not any("AGENT" in b.get("text", "") for b in blocks)
    job = next(b["id"] for b in blocks if b["type"] == "job")
    assert "RejNET i Word" in wait(client, admin, job)[0]["text"]


def test_the_agent_starts_also_when_a_case_is_chosen(office):
    client, admin, desk, desktop, replies = office
    made = client.post("/v2/chat", headers=admin, json={"text": "nowa sprawa testowa-2026"}).json()["blocks"]
    case = next(b["case"] for b in made if b["type"] == "case")
    ask = {"text": "jakie mam teraz pootwierane rzeczy?", "case": case}
    steps = [json.dumps({"krok": "okna"}), json.dumps({"krok": "koniec", "odpowiedz": "Otwarte: RejNET i Word."})]
    # an empty case cannot answer from documents, but the computer needs none
    replies += ["AGENT: sprawdź otwarte okna", *steps]
    blocks = client.post("/v2/chat", headers=admin, json=ask).json()["blocks"]
    job = next(b["id"] for b in blocks if b["type"] == "job")
    assert "RejNET i Word" in wait(client, admin, job)[0]["text"]
    # a case with documents: the model sees them and still hands the request to the agent
    saved = client.post("/v2/documents", headers=admin, json={
        "name": "umowa.txt", "expected_version": 0, "case": case, "content_b64": "YQ=="})
    assert saved.status_code == 200
    replies += ["ROZUMIEM: sprawdzę okna.\n\nAGENT: sprawdź otwarte okna", *steps]
    blocks = client.post("/v2/chat", headers=admin, json=ask).json()["blocks"]
    job = next(b["id"] for b in blocks if b["type"] == "job")
    assert "RejNET i Word" in wait(client, admin, job)[0]["text"]
    assert replies == []


def test_the_prompts_tell_the_model_about_the_computer_last():
    from worker.drafting import COMPUTER, NEXT_STEPS, SYSTEM_CHAT, SYSTEM_GENERAL
    assert "AGENT:" in COMPUTER and "przeglądar" in COMPUTER and "formularz" in COMPUTER
    assert "AGENT" not in SYSTEM_GENERAL + NEXT_STEPS + SYSTEM_CHAT          # one place, appended after the rest
