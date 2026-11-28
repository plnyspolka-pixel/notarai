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

    def ask(system, question, images=()):
        seen.append(question)
        pictures.append(images)
        return replies.pop(0)
    pictures = ask.pictures = []
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
    assert "krok 1 · szukam plików „kowalski” · po co: szukam aktu" in lines[0]         # the exact live log
    assert "krok 1 · wynik" in lines[1] and "akt Kowalski.docx" not in lines[0]
    assert "zamieniam „12 listopada” na „14 listopada”" in lines[4]


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

    prompts = []

    def converse(self, **kwargs):
        Bedrock.prompts.append(kwargs["messages"][0]["content"][-1]["text"])
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


# ---- 2.7.0: the screen, a click on a point, the command line, a phone with consent, Edge or Chrome
JPEG = b"\xff\xd8\xff" + b"0" * 64


def test_the_agent_looks_at_the_screen_and_clicks_a_point(tmp_path):
    clicks, typed = [], []
    computer = Computer(tmp_path, desktop=lambda: FakeDesktop(), grabber=lambda: (JPEG, 2.0, (960, 540)),
                        pointer=lambda x, y, double: clicks.append((x, y, double)), typist=typed.append,
                        label_at=lambda x, y: "Wyślij" if (x, y) == (400, 200) else "")
    ask, _ = script({"krok": "ekran", "okno": ""},                                          # fields first: refused by code
                    {"krok": "okno", "okno": "RejNET"},
                    {"krok": "kliknij_punkt", "x": 10, "y": 10, "co": "pole"},              # no screenshot yet: refused
                    {"krok": "ekran", "okno": ""},
                    {"krok": "kliknij_punkt", "x": 5, "y": 5, "co": "Zapisz"},              # has a name in the window: refused
                    {"krok": "kliknij_punkt", "x": 100, "y": 50, "co": "pole Numer"},
                    {"krok": "pisz", "tekst": "1234/2026"},
                    {"krok": "ekran", "okno": "RejNET"},
                    {"krok": "kliknij_punkt", "x": 200, "y": 100, "co": "OK"},                 # Windows calls it „Wyślij”
                    {"krok": "koniec", "odpowiedz": "x"})
    lines = []
    result = Agent(computer, ask, narrate=lines.append).run("wpisz numer w programie")
    assert "Najpierw odczytaj okno" in result["steps"][0]["wynik"] and result["steps"][2]["wynik"].startswith("BŁĄD")
    assert "użyj kroku kliknij" in result["steps"][4]["wynik"]
    assert clicks == [(200, 100, False)] and typed == ["1234/2026"]          # image pixels times the scale
    assert result["stopped"]["kind"] == "wyslanie"                           # the model's own label „OK” did not hide it
    assert [len(images) for images in ask.pictures] == [0, 0, 0, 0, 1, 0, 0, 0, 1]   # a picture is shown once, right after it is taken
    assert any("[ZRZUT EKRANU] robię zrzut ekranu" in line and "zrzut ekranu idzie do asystenta" in line for line in lines)
    assert any("[pola okna] odczytuję pola" in line for line in lines) and any("cofnięte" in line for line in lines)


def test_the_station_can_switch_the_screen_and_the_command_line_off(tmp_path):
    computer = Computer(tmp_path, grabber=lambda: (JPEG, 1.0, (10, 10)), allowed=lambda: {"screen": False, "commands": False},
                        which=lambda name: str(tmp_path / "tool.exe"), runner=lambda *a, **k: 1 / 0)
    ask, _ = script({"krok": "ekran"}, {"krok": "polecenie", "program": "tool", "argumenty": []}, {"krok": "koniec", "odpowiedz": "x"})
    result = Agent(computer, ask).run("zobacz ekran")
    assert all("wyłączon" in step["wynik"] for step in result["steps"]) and ask.pictures == [(), (), ()]


def test_the_command_line_runs_one_program_and_never_a_shell(tmp_path, monkeypatch):
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "tajne")
    ran = []

    class Done:
        returncode, stdout, stderr = 0, "zażółć ok".encode("utf-8"), b""

    def runner(argv, **options):
        ran.append((argv, options))
        return Done()
    tool = tmp_path / "cli-anything-libreoffice.exe"
    tool.write_bytes(b"MZ")
    places = {"cli-anything-libreoffice": str(tool), "powershell": r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
              "cmd": r"C:\Windows\System32\cmd.exe", "skrypt": str(tmp_path / "skrypt.bat")}
    computer = Computer(tmp_path, runner=runner, which=places.get)
    assert "kodem 0" in computer.command("cli-anything-libreoffice", ["document", "info", "--json"])
    argv, options = ran[0]
    assert argv == [str(tool), "document", "info", "--json"] and options["shell"] is False
    assert not any(key.startswith("AWS_") for key in options["env"])
    for program in ("powershell", "cmd", "skrypt", "nie-ma-takiego"):
        with pytest.raises(Exception) as refused:
            computer.command(program, ["-c", "x"])
        assert refused.type.__name__ == "AgentError"
    with pytest.raises(Exception):
        computer.command("cli-anything-libreoffice", {"a": 1})
    assert len(ran) == 1

    steps = ({"krok": "polecenie", "program": "cli-anything-libreoffice", "argumenty": ["page", "delete", "--index", "2"]},
             {"krok": "koniec", "odpowiedz": "Usunięte."})
    ask, _ = script(*steps)
    stopped = Agent(computer, ask).run("uporządkuj dokument")
    assert stopped["stopped"]["kind"] == "usuniecie" and len(ran) == 1
    ask, _ = script(*steps)
    assert Agent(computer, ask).run("usuń drugą stronę dokumentu")["answer"] == "Usunięte." and len(ran) == 2


def pair(client, admin, sentence):
    blocks = client.post("/v2/chat", headers=admin, json={"text": sentence}).json()["blocks"]
    code = next(b["text"] for b in blocks if b["type"] == "secret")
    return {"Authorization": "Bearer " + client.post("/v2/devices/redeem", json={"code": code}).json()["token"]}, blocks


def test_a_phone_drives_the_computer_only_with_consent(office):
    client, admin, desk, desktop, replies = office
    phone, _ = pair(client, admin, "dodaj telefon")
    replies += ["AGENT: otwórz Worda"]                     # the assistant hands it over; the chat still refuses
    refused = client.post("/v2/chat", headers=phone, json={"text": "otwórz Worda na komputerze"}).json()["blocks"]
    assert "nie ma zgody" in refused[0]["text"] and not any(b["type"] == "job" for b in refused)

    asked = client.post("/v2/chat", headers=admin, json={"text": "pozwól telefonowi Telefon sterować komputerem"}).json()["blocks"]
    assert asked[0]["type"] == "confirm"
    client.post("/v2/chat", headers=admin, json={"confirm": asked[0]["token"]})
    listed = client.post("/v2/chat", headers=admin, json={"text": "urządzenia"}).json()["blocks"]
    assert "steruje komputerem" in listed[0]["text"]
    replies += [json.dumps({"krok": "okna"}), json.dumps({"krok": "koniec", "odpowiedz": "Otwarte: RejNET i Word."})]
    blocks = client.post("/v2/chat", headers=phone, json={"text": "sprawdź, jakie okna są otwarte na komputerze"}).json()["blocks"]
    job = next(b["id"] for b in blocks if b["type"] == "job")
    assert "RejNET i Word" in wait(client, phone, job)[0]["text"]

    client.post("/v2/chat", headers=admin, json={"text": "zabroń Telefon sterować komputerem"})
    replies += ["AGENT: otwórz Worda"]
    again = client.post("/v2/chat", headers=phone, json={"text": "otwórz Worda na komputerze"}).json()["blocks"]
    assert "nie ma zgody" in again[0]["text"]
    # the phone cannot give itself the consent
    replies += ["Zgodę daje się na komputerze kancelarii.", "AGENT: otwórz Worda"]
    client.post("/v2/chat", headers=phone, json={"text": "pozwól telefonowi Telefon sterować komputerem"})
    assert "nie ma zgody" in client.post("/v2/chat", headers=phone, json={"text": "otwórz Worda na komputerze"}).json()["blocks"][0]["text"]

    paired, said = pair(client, admin, "dodaj telefon z dostępem do komputera o nazwie Szef")
    assert "może zlecać pracę na tym komputerze" in said[0]["text"]
    replies += [json.dumps({"krok": "koniec", "odpowiedz": "Gotowe."})]
    blocks = client.post("/v2/chat", headers=paired, json={"text": "otwórz Worda na komputerze"}).json()["blocks"]
    assert "Gotowe." in wait(client, paired, next(b["id"] for b in blocks if b["type"] == "job"))[0]["text"]
    limited = client.post("/v2/chat", headers=admin, json={"text": "dodaj telefon tylko do odczytu z dostępem do komputera"}).json()["blocks"]
    assert "tylko urządzenie z odczytem i zapisem" in limited[0]["text"]


def test_the_office_chooses_the_browser_and_the_switches(office):
    client, admin, desk, desktop, replies = office
    from worker.settings import load

    def said(sentence):
        return client.post("/v2/chat", headers=admin, json={"text": sentence}).json()["blocks"][0]["text"]
    assert "Google Chrome" in said("używaj Chrome")
    assert "Microsoft Edge" in said("przeglądarka Edge")
    assert "nie robi już zrzutów" in said("wyłącz zrzuty ekranu agenta")
    assert "nie uruchamia już programów" in said("wyłącz wiersz poleceń agenta")
    assert "może patrzeć na ekran" in said("włącz zrzuty ekranu agenta")


def test_each_browser_keeps_its_own_profile(tmp_path, monkeypatch):
    import worker.web_fill as web_fill

    monkeypatch.delenv("NOTARAI_V2_BROWSER", raising=False)
    monkeypatch.setattr(web_fill.os, "name", "nt")
    assert web_fill._default_executable("chrome") == (None, "chrome")
    assert web_fill._default_executable("edge") == (None, "msedge") == web_fill._default_executable("cokolwiek")


# ---- 2.8.0: the map of a program, long work that can be continued, login and signature stay with the notary
def test_the_agent_remembers_the_map_of_a_program(tmp_path):
    desktop = FakeDesktop()
    desktop.fields.append(Control("p", "text", "PESEL 44051401359", "", []))
    computer = Computer(tmp_path, desktop=lambda: desktop)
    ask, _ = script({"krok": "okno", "okno": "RejNET"},
                    {"krok": "notatka", "program": "RejNET - Repertorium", "tekst": "Nowy wpis: menu Rejestry, potem Repertorium A, przycisk Dodaj"},
                    {"krok": "notatka", "program": "RejNET", "tekst": "klient ma PESEL 44051401359"},
                    {"krok": "koniec", "odpowiedz": "Poznałem."})
    result = Agent(computer, ask).run("poznaj program RejNET")
    assert result["steps"][2]["wynik"].startswith("BŁĄD")                       # no numbers of people in the map
    described = computer.map.describe()
    assert "PROGRAM repertorium" in described and "Numer aktu" in described and "Zapisz" in described
    assert "menu Rejestry" in described and "44051401359" not in described
    # a later task starts with the map in front of the model
    ask, seen = script({"krok": "koniec", "odpowiedz": "x"})
    Agent(Computer(tmp_path, desktop=lambda: desktop), ask).run("zarejestruj akt")
    assert "MAPA PROGRAMU" in seen[0] and "menu Rejestry" in seen[0]
    assert computer.map.forget("repertorium") and computer.map.describe() == ""


def test_login_signature_and_password_are_never_done_by_the_agent(tmp_path):
    desktop = FakeDesktop()
    desktop.fields += [Control("l", "button", "Zaloguj certyfikatem", "", []), Control("s", "button", "Podpisz", "", []),
                       Control("h", "text", "Hasło", "", [])]
    computer = Computer(tmp_path, desktop=lambda: desktop)
    for step, kind in (({"krok": "kliknij", "okno": "RejNET", "przycisk": "Zaloguj certyfikatem"}, "logowanie"),
                       ({"krok": "kliknij", "okno": "RejNET", "przycisk": "Podpisz"}, "podpis"),
                       ({"krok": "wpisz", "okno": "RejNET", "pole": "Hasło", "wartosc": "x"}, "logowanie")):
        ask, _ = script(step)
        # even when the sentence asks for it and a „Tak” allowed it
        stopped = Agent(computer, ask).run("zaloguj się, podpisz i wyślij", allowed={"podpis", "logowanie"})
        assert stopped["stopped"]["kind"] == kind
    assert desktop.clicked == [] and desktop.typed == {}
    assert act_kind("Sign in") == "logowanie" and act_kind("Sign document") == "podpis"


def test_long_work_stops_as_something_to_continue(tmp_path):
    computer = Computer(tmp_path, desktop=lambda: FakeDesktop())
    ask, seen = script(*[{"krok": "szukaj", "nazwa": f"akt{n}", "folder": str(tmp_path)} for n in range(5)])
    result = Agent(computer, ask, max_steps=5).run("zrób dużo")
    assert result["stopped"]["kind"] == "limit" and len(result["stopped"]["history"]) == 5
    ask, seen = script({"krok": "koniec", "odpowiedz": "Skończone."})
    assert Agent(computer, ask).run("zrób dużo", history=result["stopped"]["history"])["answer"] == "Skończone."
    assert seen[0].count("KROK") == 5                                          # the continued run knows what was done
    from worker.agent import MAX_STEPS
    assert MAX_STEPS >= 60


class FakeBrowser:
    def __init__(self):
        self.calls, self.opened = [], True

    def is_open(self):
        return self.opened

    def show(self):
        self.calls.append("show")
        return True

    def hide(self):
        self.calls.append("hide")
        return True

    def snapshot(self):
        return JPEG

    def controls(self):
        return [Control("z", "button", "Zaloguj certyfikatem", "", []), Control("n", "text", "Numer aktu", "", [])]

    def on_page(self, function, timeout=0):
        return "https://rejestry.example.pl/akty/nowy", "Rejestry", "Zaloguj się", ["Zaloguj certyfikatem"]

    def click(self, control):
        self.calls.append("click " + control.label)


@pytest.fixture
def web_office(tmp_path):
    home = tmp_path / "home"
    token = initialize(home)
    browser, replies = FakeBrowser(), []
    inference = Inference(Policy("eu-central-1", "eu.anthropic.claude-sonnet-4-6"), lambda s: Bedrock(replies), UsageLedger(home))
    client = TestClient(create_app(home, inference=inference, computer_roots=[tmp_path],
                                   fill_targets={"program": lambda: FakeDesktop(), "strona": lambda: browser}))
    return client, {"Authorization": "Bearer " + token}, browser, replies


def test_the_browser_works_out_of_sight_and_comes_forward_for_the_notarys_part(web_office):
    client, admin, browser, replies = web_office
    replies += [json.dumps({"krok": "widok"}), json.dumps({"krok": "web_kliknij", "co": "Zaloguj certyfikatem"})]
    blocks = client.post("/v2/chat", headers=admin, json={"text": "wejdź na stronę rejestrów i zarejestruj akt"}).json()["blocks"]
    asked = wait(client, admin, next(b["id"] for b in blocks if b["type"] == "job"))
    kinds = [b["type"] for b in asked]
    assert "logowanie" in asked[0]["text"] and "image" in kinds and kinds[-1] == "confirm"
    assert browser.calls == ["show"]                                            # shown only now, nothing clicked
    replies += [json.dumps({"krok": "koniec", "odpowiedz": "Akt przygotowany do podpisu."})]
    resumed = client.post("/v2/chat", headers=admin, json={"confirm": asked[-1]["token"]}).json()["blocks"]
    done = wait(client, admin, next(b["id"] for b in resumed if b["type"] == "job"))
    assert "przygotowany do podpisu" in done[0]["text"] and browser.calls == ["show", "hide"]

    def said(sentence):
        return client.post("/v2/chat", headers=admin, json={"text": sentence}).json()["blocks"]
    assert "na wierzchu" in said("pokaż przeglądarkę")[0]["text"] and browser.calls[-1] == "show"
    assert "w tle" in said("schowaj przeglądarkę")[0]["text"] and browser.calls[-1] == "hide"
    assert "rejestry.example.pl" in said("mapy programów")[0]["text"]          # the site was mapped while working
    assert "na widoku" in said("pracuj na widoku")[0]["text"]
    assert "w tle" in said("pracuj w tle")[0]["text"]


def test_poznaj_program_starts_a_mapping_run_and_the_limit_offers_to_continue(web_office):
    client, admin, browser, replies = web_office
    replies += [json.dumps({"krok": "koniec", "odpowiedz": "Poznałem 3 ekrany."})]
    blocks = client.post("/v2/chat", headers=admin, json={"text": "poznaj program RejNET"}).json()["blocks"]
    assert "Poznałem 3 ekrany." in wait(client, admin, next(b["id"] for b in blocks if b["type"] == "job"))[0]["text"]
    import worker.agent as agent_module
    replies += [json.dumps({"krok": "szukaj", "nazwa": f"akt{n}", "folder": ""}) for n in range(agent_module.MAX_STEPS)]
    blocks = client.post("/v2/chat", headers=admin, json={"text": "otwórz program i zrób wszystko"}).json()["blocks"]
    stopped = wait(client, admin, next(b["id"] for b in blocks if b["type"] == "job"))
    assert "jeszcze nie skończyłem" in stopped[0]["text"] and stopped[-1]["label"] == "Kontynuuj"


def test_the_browser_object_is_complete_before_any_page_is_opened(tmp_path):
    from worker.web_fill import Browser

    browser = Browser(tmp_path / "profil")
    browser.background(lambda: True)
    assert browser.is_open() is False and browser._hidden() is True and browser._pool is not None
    assert browser.hide() is False or browser.is_open()          # nothing to move yet, and no exception


def test_a_login_screen_stops_the_run_and_the_whole_window_is_read(tmp_path):
    class Program(FakeDesktop):
        def controls(self, deep=False):
            self.deep = deep
            menu = [Control("m", "button", "Rejestry (menu)", "", []), Control("t", "button", "Repertorium A (zakładka)", "", [])]
            return self.fields + (menu if deep else [])
    desktop = Program()
    computer = Computer(tmp_path, desktop=lambda: desktop)
    lines = []
    ask, seen = script({"krok": "okno", "okno": "RejNET"}, {"krok": "kliknij", "okno": "RejNET", "przycisk": "Rejestry (menu)"},
                       {"krok": "koniec", "odpowiedz": "x"})
    result = Agent(computer, ask, narrate=lines.append).run("otwórz rejestry w RejNET")
    assert desktop.deep is True and desktop.clicked == ["Rejestry (menu)"] and result["stopped"] is None
    assert "Rejestry (menu)" in seen[1] and "Repertorium A (zakładka)" in computer.map.describe()
    assert any("okno „RejNET”: klikam „Rejestry (menu)”" in line for line in lines)

    desktop.fields.append(Control("h", "text", "Hasło", "", []))
    ask, _ = script({"krok": "okno", "okno": "RejNET"}, {"krok": "wpisz", "okno": "RejNET", "pole": "Numer aktu", "wartosc": "1"})
    stopped = Agent(computer, ask, narrate=lines.append).run("zarejestruj akt w RejNET")["stopped"]
    assert stopped["kind"] == "logowanie" and stopped["where"] == "RejNET - Repertorium" and desktop.typed == {}
    assert any("ekran logowania" in line for line in lines)


# ---- 2.8.1: classic Windows programs (Delphi/VCL) read by their window classes when UI Automation shows too little
class _Rect:
    def __init__(self, left, top, right, bottom):
        self.left, self.top, self.right, self.bottom = left, top, right, bottom


class _Classic:
    """One window of a classic program, as pywinauto's win32 backend shows it."""
    def __init__(self, class_name, text="", rect=(0, 0, 10, 10), friendly="", style=0, texts=()):
        self._class, self._text, self._rect, self._friendly, self._style, self._texts = class_name, text, rect, friendly, style, list(texts)
        self.typed, self.clicked, self.selected = None, 0, None

    def class_name(self): return self._class
    def friendly_class_name(self): return self._friendly or self._class
    def is_visible(self): return True
    def is_enabled(self): return True
    def rectangle(self): return _Rect(*self._rect)
    def window_text(self): return self.typed if self.typed is not None else self._text
    def has_style(self, style): return bool(self._style & style)
    def texts(self): return [self._text, *self._texts]
    def set_edit_text(self, value): self.typed = value
    def click(self): self.clicked += 1
    def select(self, index): self.selected = index


class _MenuItem:
    def __init__(self, text, entries=()):
        self._text, self._entries = text, list(entries)

    def text(self): return self._text
    def is_enabled(self): return True
    def sub_menu(self): return self if self._entries else None
    def items(self): return self._entries


class _ClassicWindow:
    def __init__(self, elements, menu):
        self._elements, self._menu, self.chosen = elements, menu, []

    def descendants(self): return self._elements
    def menu(self): return _MenuItem("", self._menu)
    def menu_select(self, path): self.chosen.append(path)


def test_a_delphi_program_is_read_by_its_fields_not_by_screenshots():
    from types import SimpleNamespace
    from worker.win_fill import Desktop, legacy_type

    assert legacy_type("TEdit") == "Edit" and legacy_type("TMaskEdit") == "Edit" and legacy_type("TDBEdit") == "Edit"
    assert legacy_type("TComboBox") == "ComboBox" and legacy_type("TBitBtn") == "Button" and legacy_type("TCheckBox") == "CheckBox"
    assert legacy_type("TPanel") is None and legacy_type("TDBGrid") is None

    number = _Classic("TEdit", "", (200, 100, 400, 122))
    password = _Classic("TEdit", "tajne", (200, 300, 400, 322), style=0x20)
    save = _Classic("TBitBtn", "&Zapisz", (200, 200, 300, 230))
    tabs = _Classic("TPageControl", "", (0, 40, 800, 60), friendly="TabControl", texts=["Akty", "Strony"])
    elements = [_Classic("TStaticText", "Numer aktu:", (60, 102, 190, 120)), number, _Classic("TEdit", "", (200, 140, 400, 162)),
                _Classic("TMaskEdit", "", (500, 400, 700, 422)), save, tabs, _Classic("TPanel", "", (0, 0, 800, 600))]
    classic = _ClassicWindow(elements, [_MenuItem("&Rejestry", [_MenuItem("Repertorium &A\tCtrl+A"), _MenuItem("Nowy wpis")])])
    # UI Automation sees the window but none of its fields: what a Delphi program often gives
    uia_window = SimpleNamespace(descendants=lambda: [], element_info=SimpleNamespace(handle=77, process_id=5),
                                 window_text=lambda: "RejNET", set_focus=lambda: None)
    desktop = Desktop(backend=SimpleNamespace(windows=lambda **kw: [uia_window]),
                      legacy=SimpleNamespace(window=lambda handle: classic if handle == 77 else None))
    desktop.focus("RejNET")
    found = desktop.controls(deep=True)
    labels = [(c.kind, c.label) for c in found]
    assert desktop.read_by == "klasyczne okna Windows"
    assert ("text", "Numer aktu") in labels and ("text", "Numer aktu (2)") in labels and ("button", "Zapisz") in labels
    assert ("text", "pole bez nazwy 1") in labels
    assert ("button", "Rejestry > Repertorium A (menu)") in labels and ("button", "Strony (zakładka)") in labels
    by = {c.label: c for c in found}
    desktop.type(by["Numer aktu"], "12/2026")
    desktop.click(by["Zapisz"])
    desktop.click(by["Rejestry > Nowy wpis (menu)"])
    desktop.click(by["Strony (zakładka)"])
    assert number.typed == "12/2026" and save.clicked == 1 and classic.chosen == ["&Rejestry->Nowy wpis"] and tabs.selected == 1
    assert desktop.read(by["Numer aktu"]) == "12/2026" and desktop.password_field is False
    assert desktop.controls() == []                                   # form filling from procedures is unchanged
    elements.append(password)
    desktop.controls(deep=True)
    assert desktop.password_field is True                             # a login screen of a classic program is seen too


def test_a_stuck_agent_asks_learns_from_the_answer_and_uses_it_next_time(office):
    client, admin, desk, desktop, replies = office
    replies += [json.dumps({"krok": "pytanie", "problem": "W RejNET nie widzę pola Numer aktu",
                            "opcje": ["Zakładka Repertorium", "Zakładka Akty"]}),
                "- W RejNET pole Numer aktu jest na zakładce Repertorium; najpierw ją kliknij.",
                json.dumps({"krok": "koniec", "odpowiedz": "Wpisałem numer na zakładce Repertorium."})]
    blocks = client.post("/v2/chat", headers=admin, json={"text": "wpisz numer aktu w RejNET w programie"}).json()["blocks"]
    asked = wait(client, admin, next(b["id"] for b in blocks if b["type"] == "job"))
    assert "Utknąłem: W RejNET nie widzę pola Numer aktu" in asked[0]["text"]
    options = [i["label"] for i in asked[1]["items"]]
    assert options == ["Zakładka Repertorium", "Zakładka Akty", "Przerwij"]
    answered = client.post("/v2/chat", headers=admin, json={"text": asked[1]["items"][0]["say"]}).json()["blocks"]
    assert "📘 Nauczyłem się: W RejNET pole Numer aktu jest na zakładce Repertorium" in answered[0]["text"]
    done = wait(client, admin, next(b["id"] for b in answered if b["type"] == "job"))
    assert "Wpisałem numer na zakładce Repertorium." in done[0]["text"]
    assert "Notariusz odpowiedział na Twoje pytanie" in Bedrock.prompts[-1]
    # the next task starts with what was learned
    replies += [json.dumps({"krok": "koniec", "odpowiedz": "Gotowe."})]
    again = client.post("/v2/chat", headers=admin, json={"text": "otwórz RejNET w programie i sprawdź repertorium"}).json()["blocks"]
    wait(client, admin, next(b["id"] for b in again if b["type"] == "job"))
    assert "LEKCJE KANCELARII" in Bedrock.prompts[-1] and "zakładce Repertorium" in Bedrock.prompts[-1]


def test_three_failures_in_a_row_stop_the_agent_and_a_lesson_is_proposed_after_a_bumpy_run(office):
    client, admin, desk, desktop, replies = office
    bad = json.dumps({"krok": "czytaj", "plik": str(desk / "brak.docx")})
    replies += [bad, bad, bad, json.dumps({"krok": "czytaj", "plik": str(desk / "brak.docx")})]
    blocks = client.post("/v2/chat", headers=admin, json={"text": "przeczytaj plik brak.docx na pulpicie"}).json()["blocks"]
    asked = wait(client, admin, next(b["id"] for b in blocks if b["type"] == "job"))
    assert "kilka kolejnych kroków się nie udało" in asked[0]["text"]
    assert "Spróbuj innym sposobem" in [i["label"] for i in asked[1]["items"]]
    (desk / "akt.txt").write_text("Akt", encoding="utf-8")
    replies += ["- Pliki aktów na pulpicie mają rozszerzenie TXT, nie DOCX.",
                json.dumps({"krok": "czytaj", "plik": str(desk / "akt.txt")}),
                json.dumps({"krok": "koniec", "odpowiedz": "Przeczytałem akt.txt."})]
    answered = client.post("/v2/chat", headers=admin, json={"text": "to jest plik akt.txt"}).json()["blocks"]
    assert "📘 Nauczyłem się: Pliki aktów na pulpicie" in answered[0]["text"]
    done = wait(client, admin, next(b["id"] for b in answered if b["type"] == "job"))
    assert "Przeczytałem akt.txt." in done[0]["text"]



def test_stop_stops_the_agent_before_its_next_step(office):
    import threading
    client, admin, desk, desktop, replies = office
    gate = threading.Event()
    real = Bedrock.converse

    def slow(self, **kwargs):
        gate.wait(5)
        return real(self, **kwargs)
    Bedrock.converse = slow
    try:
        replies += [json.dumps({"krok": "okna"})] * 5 + [json.dumps({"krok": "koniec", "odpowiedz": "x"})]
        blocks = client.post("/v2/chat", headers=admin, json={"text": "otwórz RejNET w programie i wpisz numer"}).json()["blocks"]
        job = next(b["id"] for b in blocks if b["type"] == "job")
        stopped = client.post("/v2/chat", headers=admin, json={"text": "stop"}).json()["blocks"]
        assert "Zatrzymałem" in stopped[0]["text"]
        gate.set()
        assert "Zatrzymałem pracę na komputerze" in wait(client, admin, job)[0]["text"]
        assert len(replies) >= 5                       # no further steps were asked for after „stop”
    finally:
        Bedrock.converse = real


def test_closing_the_window_stops_the_agent(office):
    client, admin, desk, desktop, replies = office
    replies += [json.dumps({"krok": "koniec", "odpowiedz": "nie powinno dojść"})]
    from worker import chat as chat_module
    original = chat_module.WINDOW_GONE
    chat_module.WINDOW_GONE = -1                         # as if nobody had asked for the job for minutes
    try:
        blocks = client.post("/v2/chat", headers=admin, json={"text": "otwórz RejNET w programie i wpisz numer"}).json()["blocks"]
        job = next(b["id"] for b in blocks if b["type"] == "job")
        assert "Zatrzymałem pracę na komputerze" in wait(client, admin, job)[0]["text"]
    finally:
        chat_module.WINDOW_GONE = original
    assert client.post("/v2/agent/stop", headers=admin).status_code == 200


def test_no_remote_help_and_no_second_copy(tmp_path):
    started = []
    computer = Computer(tmp_path, desktop=lambda: FakeDesktop(), starter=started.append)
    for target in ("quickassist", "C:\\Program Files\\TeamViewer\\TeamViewer.exe", "AnyDesk.exe", "mstsc",
                   "Szybka pomoc", "Usługa zdalnej pomocy technicznej"):
        with pytest.raises(Exception) as refused:
            computer.start(target)
        assert "pomocy zdalnej" in str(refused.value)
    with pytest.raises(Exception) as twice:
        computer.start("RejNET")
    assert "już działa" in str(twice.value) and started == []
    computer.start("C:\\Akty\\umowa.docx")
    assert started == ["C:\\Akty\\umowa.docx"]


def test_the_program_itself_says_which_command_line_tools_are_here(office, monkeypatch, tmp_path):
    client, admin, desk, desktop, replies = office
    (tmp_path / "cli-anything-libreoffice.exe").write_bytes(b"MZ")
    monkeypatch.setenv("PATH", str(tmp_path))
    said = client.post("/v2/chat", headers=admin, json={"text": "jakie masz narzedzia wiersza polecen"}).json()["blocks"][0]["text"]
    assert "cli-anything-libreoffice" in said and "włączony" in said and "[pola okna]" in said
    monkeypatch.setenv("PATH", str(tmp_path / "pusto"))
    said = client.post("/v2/chat", headers=admin, json={"text": "czy jest tu CLI-Anything albo winapp?"}).json()["blocks"][0]["text"]
    assert "Nie znalazłem narzędzi cli-anything ani winapp" in said and replies == []      # no model call at all
    from worker.chat import answer_blocks
    assert answer_blocks("ROZUMIEM: x\n\nMogę **otwierać programy** i więcej.\n\n---")[0]["text"] == "Mogę otwierać programy i więcej."


# ---- 2.8.5: the agent's question in a small window on top; its answer comes back into the chat
def test_a_question_waits_under_a_one_time_address_and_is_answered_once():
    from worker.attention import Attention

    opened = []
    attention = Attention(opener=opened.append)
    token = attention.ask("local-admin", "Utknąłem: które pole to data aktu?",
                          [("pierwsze", {"text": "odpowiedź dla agenta: pierwsze"}), ("Przerwij", {"text": "odpowiedź dla agenta: przerwij"})],
                          free="odpowiedź dla agenta: ", url=lambda t: "http://127.0.0.1:1/v2/attention/" + t)
    assert opened == ["http://127.0.0.1:1/v2/attention/" + token]
    assert attention.shown(token) == {"text": "Utknąłem: które pole to data aktu?", "actions": ["pierwsze", "Przerwij"], "free": True}
    assert attention.shown("zgadywany") is None and not attention.answer("zgadywany", choice=0)
    assert not attention.answer(token, choice=7) and attention.answer(token, words="  to   drugie pole ")
    assert not attention.answer(token, choice=0)                                   # one answer for one question
    assert attention.collect("local-admin") == [{"text": "odpowiedź dla agenta: to drugie pole"}]
    assert attention.collect("local-admin") == [] and attention.collect("ktoś inny") == []
    off = Attention(opener=opened.append, enabled=lambda: False)
    assert off.ask("local-admin", "x", [("a", {"text": "a"})]) is None and len(opened) == 1


def test_the_login_stop_opens_the_small_window_and_its_answer_resumes_the_work(tmp_path):
    home = tmp_path / "home"
    admin = {"Authorization": "Bearer " + initialize(home)}
    browser, replies, opened = FakeBrowser(), [], []
    inference = Inference(Policy("eu-central-1", "eu.anthropic.claude-sonnet-4-6"), lambda s: Bedrock(replies), UsageLedger(home))
    client = TestClient(create_app(home, inference=inference, computer_roots=[tmp_path], attention_opener=opened.append,
                                   fill_targets={"program": lambda: FakeDesktop(), "strona": lambda: browser}))
    assert client.get("/v2/agent/inbox", headers=admin).json() == {"turns": []}      # the window's poll: the worker learns its address
    replies += [json.dumps({"krok": "widok"}), json.dumps({"krok": "web_kliknij", "co": "Zaloguj certyfikatem"})]
    blocks = client.post("/v2/chat", headers=admin, json={"text": "wejdź na stronę rejestrów i zarejestruj akt"}).json()["blocks"]
    asked = wait(client, admin, next(b["id"] for b in blocks if b["type"] == "job"))
    assert len(opened) == 1 and "/v2/attention/" in opened[0]
    path = opened[0].split("testserver", 1)[1]
    assert "NotarAI potrzebuje Twojej decyzji" in client.get(path).text
    shown = client.get(path + "/dane").json()
    assert "logowanie" in shown["text"] and shown["actions"] == ["Zalogowałem się, kontynuuj"] and shown["free"] is False
    assert client.get(path + "/dane", headers={"host": "notarai.example"}).status_code == 403      # this computer only
    assert client.post(path, json={"choice": 0}, headers={"origin": "http://zla.example"}).status_code == 403
    assert client.post(path, json={"choice": 0}).status_code == 200 and client.post(path, json={"choice": 0}).status_code == 410
    turns = client.get("/v2/agent/inbox", headers=admin).json()["turns"]
    assert turns == [{"confirm": asked[-1]["token"]}]
    replies += [json.dumps({"krok": "koniec", "odpowiedz": "Akt przygotowany."})]
    resumed = client.post("/v2/chat", headers=admin, json=turns[0]).json()["blocks"]
    assert "Akt przygotowany." in wait(client, admin, next(b["id"] for b in resumed if b["type"] == "job"))[0]["text"]
    assert "wyłączone" in client.post("/v2/chat", headers=admin, json={"text": "wyłącz okienko z pytaniem agenta"}).json()["blocks"][0]["text"]


# ---- KRZ: the program finds the act and its parties itself
def test_krz_finds_the_act_on_the_computer_and_proposes_whom_to_check(office):
    client, admin, desk, desktop, replies = office
    a_docx(desk / "akt Jagiełło sprzedaż.docx", "Stawił się Jan Jagiełło, syn Adama i Ewy, zamieszkały w Krakowie, PESEL 44051401359, "
                                                 "oraz Anna Nowak-Jagiełło, PESEL 02070803628.")
    (desk / "notatka jagiello.txt").write_text("zadzwonić w piątek", encoding="utf-8")       # the name fits, no parties in it
    for sentence in ("sprawdzić krz Jagiełło.", "sprawdź strony w KRZ dla sprawy Jagiełło"):
        blocks = client.post("/v2/chat", headers=admin, json={"text": sentence}).json()["blocks"]
        asked = next(b for b in blocks if b["type"] == "confirm")
        assert "Jan Jagiełło 4405*******" in asked["text"] and "Anna Nowak-Jagiełło 0207*******" in asked["text"]
        assert "akt Jagiełło sprzedaż.docx" in asked["text"] and "44051401359" not in asked["text"]
    assert replies == []                                                # found by the program, no model, no question back
    nothing = client.post("/v2/chat", headers=admin, json={"text": "sprawdź KRZ Wiśniewski"}).json()["blocks"][0]["text"]
    assert "nie znalazłem" in nothing and "wisniewski" in nothing and "podaj numer PESEL" not in nothing


def test_krz_reads_the_parties_from_a_case_in_the_vault_first(office):
    import base64
    client, admin, desk, desktop, replies = office
    body = "Umowa darowizny. Darczyńca: Maria Jagiełło, PESEL 44051401359."
    client.post("/v2/documents", headers=admin, json={"name": "umowa.txt", "expected_version": 0, "case": "darowizna-2026",
                                                      "content_b64": base64.b64encode(body.encode()).decode()})
    blocks = client.post("/v2/chat", headers=admin, json={"text": "sprawdź w KRZ strony z aktu Jagiełło"}).json()["blocks"]
    asked = next(b for b in blocks if b["type"] == "confirm")
    assert "Maria Jagiełło 4405*******" in asked["text"] and "darowizna-2026" in asked["text"]


# ---- 2.8.5: the agent works under the notary's own windows; the front of the screen only with their word
class QuietDesktop(FakeDesktop):
    def __init__(self, can_capture=True, can_click=True):
        super().__init__()
        self.can_capture, self.can_click, self.log, self.quiet = can_capture, can_click, [], False

    def focus(self, title):
        self.log.append("wybrane bez wyciągania" if self.quiet else "NA WIERZCH")

    def capture(self):
        return (JPEG, 1.5, (800, 600), (300, 200)) if self.can_capture else None

    def click_at(self, x, y, double=False):
        self.log.append(("klik komunikatem", x, y))
        return self.can_click

    def send_text(self, value):
        self.log.append(("znaki komunikatem", value))
        return True

    def to_front(self):
        self.log.append("NA WIERZCH")
        return 4242

    def give_back(self, before):
        self.log.append(("oddane", before))


def test_in_the_background_nothing_comes_to_the_front(tmp_path):
    desktop, mouse, keyboard, grabbed = QuietDesktop(), [], [], []
    computer = Computer(tmp_path, desktop=lambda: desktop, allowed=lambda: {"background": True},
                        grabber=lambda: grabbed.append(1) or (JPEG, 1.0, (10, 10)),
                        pointer=lambda x, y, d: mouse.append((x, y)), typist=keyboard.append, label_at=lambda x, y: "")
    ask, _ = script({"krok": "okno", "okno": "RejNET"}, {"krok": "wpisz", "okno": "RejNET", "pole": "Numer aktu", "wartosc": "1/2026"},
                    {"krok": "ekran", "okno": "RejNET"}, {"krok": "kliknij_punkt", "x": 100, "y": 40, "co": "siatka"},
                    {"krok": "pisz", "tekst": "abc"}, {"krok": "kliknij", "okno": "RejNET", "przycisk": "Zapisz"},
                    {"krok": "koniec", "odpowiedz": "Zrobione w tle."})
    result = Agent(computer, ask).run("wpisz akt w RejNET")
    assert result["answer"] == "Zrobione w tle." and result["stopped"] is None
    assert "NA WIERZCH" not in desktop.log and mouse == [] and keyboard == [] and grabbed == []
    assert ("klik komunikatem", 150, 60) in desktop.log and ("znaki komunikatem", "abc") in desktop.log
    assert desktop.typed == {"Numer aktu": "1/2026"} and desktop.clicked == ["Zapisz"]
    assert "zrobiony w tle" in result["steps"][2]["wynik"]


def test_the_front_of_the_screen_is_taken_only_with_the_notarys_word_and_given_back(tmp_path):
    desktop, mouse = QuietDesktop(can_capture=False), []
    computer = Computer(tmp_path, desktop=lambda: desktop, allowed=lambda: {"background": True},
                        grabber=lambda: (JPEG, 2.0, (960, 540)), pointer=lambda x, y, d: mouse.append((x, y)),
                        typist=lambda v: None, label_at=lambda x, y: "")
    steps = ({"krok": "okno", "okno": "RejNET"}, {"krok": "ekran", "okno": "RejNET"},
             {"krok": "kliknij_punkt", "x": 10, "y": 10, "co": "siatka"}, {"krok": "koniec", "odpowiedz": "ok"})
    ask, _ = script(*steps)
    lines = []
    waiting = Agent(computer, ask, narrate=lines.append).run("kliknij w siatkę")
    assert waiting["stopped"]["kind"] == "wierzch" and "zrzut ekranu" in waiting["stopped"]["label"]
    assert "NA WIERZCH" not in desktop.log and mouse == [] and len(waiting["steps"]) == 1       # the step was not done
    assert any("wstrzymany: wymaga okna na wierzchu" in line for line in lines)
    ask, _ = script(*steps[1:])
    done = Agent(computer, ask).run("kliknij w siatkę", allowed={"wierzch"}, history=waiting["stopped"]["history"])
    assert done["answer"] == "ok" and mouse == [(20, 20)]
    assert desktop.log.count("NA WIERZCH") == 2 and desktop.log.count(("oddane", 4242)) == 2   # each time given back at once
    # „klawisze” needs the keyboard: the same rule
    ask, _ = script({"krok": "klawisze", "okno": "RejNET", "klawisze": "^s"})
    assert Agent(computer, ask).run("zapisz")["stopped"]["kind"] == "wierzch"


def test_the_chat_asks_before_the_window_comes_to_the_front(web_office):
    client, admin, browser, replies = web_office
    replies += [json.dumps({"krok": "klawisze", "okno": "RejNET", "klawisze": "{F5}"})]
    blocks = client.post("/v2/chat", headers=admin, json={"text": "otwórz okno programu RejNET i odśwież"}).json()["blocks"]
    asked = wait(client, admin, next(b["id"] for b in blocks if b["type"] == "job"))
    assert "nie zabieram Ci ekranu" in asked[0]["text"] and asked[-1]["label"] == "Tak, na chwilę"


def test_a_window_is_chosen_without_being_brought_forward():
    from types import SimpleNamespace
    from worker.win_fill import Desktop

    focused = []
    window = SimpleNamespace(window_text=lambda: "RejNET", set_focus=lambda: focused.append(1),
                             element_info=SimpleNamespace(handle=1, process_id=1), descendants=lambda: [])
    desktop = Desktop(backend=SimpleNamespace(windows=lambda **kw: [window]), legacy=SimpleNamespace(window=lambda handle: None))
    desktop.quiet = True
    desktop.focus("RejNET")
    assert focused == []
    stuck = Control(SimpleNamespace(click_input=lambda: focused.append("mysz")), "button", "Siatka", "", [])
    with pytest.raises(Exception) as refused:
        desktop.click(stuck)                                            # only the mouse would do it: not in the background
    assert "w tle" in str(refused.value) and focused == []
    desktop.quiet = False
    desktop.focus("RejNET")
    desktop.click(stuck)
    assert focused == [1, "mysz"]                                       # form filling from procedures works as before


# ---- 2.8.8: no going in circles; a log of every run; the way that worked is remembered and only gets shorter
def test_going_in_circles_is_stopped_by_code(tmp_path):
    desktop = FakeDesktop()
    computer = Computer(tmp_path, desktop=lambda: desktop)
    lines = []
    ask, _ = script({"krok": "okno", "okno": "RejNET"}, {"krok": "okno", "okno": "RejNET"},          # the same read again: refused
                    *[{"krok": "kliknij", "okno": "RejNET", "przycisk": "Zapisz"}] * 3)
    result = Agent(computer, ask, narrate=lines.append).run("zapisz wpis w RejNET")
    assert "Ten sam odczyt" in result["steps"][1]["wynik"]
    assert result["stopped"]["kind"] == "pytanie" and "kręcę się w kółko" in result["stopped"]["label"]
    assert desktop.clicked == ["Zapisz"] * 3 and any("kręcę się w kółko" in line for line in lines)
    # a cycle of several steps is seen too; entering several acts (different values) is not a circle
    cycle = [{"krok": "kliknij", "okno": "RejNET", "przycisk": "Zapisz"}, {"krok": "okno", "okno": "RejNET"}]
    ask, _ = script(*cycle * 3)
    assert "te same 2 kroki" in Agent(computer, ask).run("zapisz")["stopped"]["label"]
    acts = [s for n in range(4) for s in ({"krok": "wpisz", "okno": "RejNET", "pole": "Numer aktu", "wartosc": f"{n}/2026"},
                                          {"krok": "kliknij", "okno": "RejNET", "przycisk": "Zapisz"})]
    ask, _ = script(*acts, {"krok": "koniec", "odpowiedz": "Cztery akty."})
    assert Agent(computer, ask).run("wpisz cztery akty")["answer"] == "Cztery akty."


def test_every_run_leaves_a_log_without_values(tmp_path):
    from worker.agent import RunLog
    desktop = FakeDesktop()
    computer = Computer(tmp_path, desktop=lambda: desktop)
    ask, _ = script({"krok": "okno", "okno": "RejNET"},
                    {"krok": "wpisz", "okno": "RejNET", "pole": "Numer aktu", "wartosc": "Jan Kowalski 44051401359"},
                    {"krok": "kliknij", "okno": "RejNET", "przycisk": "Nie ma takiego"},
                    {"krok": "kliknij", "okno": "RejNET", "przycisk": "Zapisz"}, {"krok": "koniec", "odpowiedz": "ok"})
    Agent(computer, ask).run("zarejestruj w RejNET akt Kowalskiego nr 1234/2026")
    path, lines = RunLog.recent(tmp_path)[0]
    raw = open(path, encoding="utf-8").read()
    assert "Kowalski" not in raw and "44051401359" not in raw and "1234" not in raw
    assert lines[0]["zadanie"] == "zarejestruj w … akt … nr ####/####"
    assert [(l["krok"], l["co"], l["stan"]) for l in lines if "krok" in l] == [
        ("okno", "", "ok"), ("wpisz", "Numer aktu", "ok"), ("kliknij", "Nie ma takiego", "blad"), ("kliknij", "Zapisz", "ok")]
    assert lines[-1]["koniec"] == "gotowe" and lines[-1]["krokow"] == 4 and lines[-1]["bledow"] == 1


def test_the_way_that_worked_is_remembered_and_only_gets_shorter(tmp_path):
    desktop = FakeDesktop()
    def do(*steps):
        computer = Computer(tmp_path, desktop=lambda: desktop)
        ask, seen = script(*steps, {"krok": "koniec", "odpowiedz": "ok"})
        Agent(computer, ask).run("zarejestruj akt w RejNET")
        return computer.map.describe(), seen
    long_way = ({"krok": "okno", "okno": "RejNET"}, {"krok": "kliknij", "okno": "RejNET", "przycisk": "Zapisz"},
                {"krok": "wpisz", "okno": "RejNET", "pole": "Numer aktu", "wartosc": "1/2026"},
                {"krok": "kliknij", "okno": "RejNET", "przycisk": "Zapisz"})
    described, _ = do(*long_way)
    assert "SPRAWDZONA DROGA „zarejestruj” (3 kroków, udana 1 razy): kliknij Zapisz -> wpisz Numer aktu -> kliknij Zapisz" in described
    assert "1/2026" not in described
    described, seen = do({"krok": "wpisz", "okno": "RejNET", "pole": "Numer aktu", "wartosc": "2/2026"},
                         {"krok": "kliknij", "okno": "RejNET", "przycisk": "Zapisz"})
    assert "SPRAWDZONA DROGA" in seen[0]                                   # the next run starts with the proven way
    assert "(2 kroków, udana 2 razy): wpisz Numer aktu -> kliknij Zapisz" in described
    described, _ = do(*long_way)                                           # a longer success does not replace the short way
    assert "(2 kroków, udana 3 razy)" in described


def test_the_question_comes_with_a_sound_repeated_while_it_waits():
    from worker.attention import Attention

    played, timers = [], []

    class Timer:
        def __init__(self, seconds, function, args=()):
            self.go = lambda: function(*args)
            timers.append(self)

        def start(self):
            pass
    switch = {"on": True}
    attention = Attention(opener=lambda url: None, sound=lambda: played.append(1), sound_on=lambda: switch["on"], timer=Timer)
    token = attention.ask("local-admin", "Utknąłem", [("Przerwij", {"text": "x"})])
    assert played == [1] and len(timers) == 1
    timers[0].go()
    assert played == [1, 1]                                    # still waiting: the sound again
    attention.answer(token, choice=0)
    timers[-1].go()
    assert played == [1, 1]                                    # answered: silence
    switch["on"] = False
    attention.ask("local-admin", "Utknąłem", [("Przerwij", {"text": "x"})])
    assert played == [1, 1]


def test_the_notary_can_read_what_the_agent_did(office):
    client, admin, desk, desktop, replies = office
    replies += [json.dumps({"krok": "okno", "okno": "RejNET"}),
                json.dumps({"krok": "wpisz", "okno": "RejNET", "pole": "Numer aktu", "wartosc": "tajne 44051401359"}),
                json.dumps({"krok": "koniec", "odpowiedz": "ok"})]
    blocks = client.post("/v2/chat", headers=admin, json={"text": "otwórz program RejNET i wpisz numer aktu Kowalskiego"}).json()["blocks"]
    wait(client, admin, next(b["id"] for b in blocks if b["type"] == "job"))
    said = client.post("/v2/chat", headers=admin, json={"text": "dziennik agenta"}).json()["blocks"][0]["text"]
    assert "koniec: gotowe; kroków 2" in said and "dziennik-agenta" in said and "44051401359" not in said and "Kowalski" not in said
    assert "sygnał" in client.post("/v2/chat", headers=admin, json={"text": "włącz dźwięk pytania agenta"}).json()["blocks"][0]["text"]


# ---- drop-down lists and what a click changed (the agent said „lista nie reaguje” while it had opened)
class ListDesktop(FakeDesktop):
    def __init__(self):
        super().__init__()
        self.kind = Control("r", "select", "Rodzaj czynności", "sprzedaż", [])
        self.fields.append(self.kind)
        self.chosen = None

    def options(self, control):
        return ["sprzedaż", "darowizna", "pełnomocnictwo"]

    def choose(self, control, value):
        from worker.autofill import FillError
        if value not in self.options(control):
            raise FillError("Lista nie przyjęła wartości. Dostępne pozycje: " + " | ".join(self.options(control)) + ".")
        self.chosen = value

    def read(self, control):
        return self.chosen or super().read(control)

    def click(self, control):
        super().click(control)
        if control.label == "Zapisz":                       # the program answers with a new button and a changed field
            self.fields.append(Control("d", "button", "Drukuj", "", []))
            self.fields[0] = Control("n", "text", "Numer aktu", "zapisano", [])


def test_a_dropdown_list_is_set_by_value_and_a_click_reports_what_changed(tmp_path):
    desktop = ListDesktop()
    computer = Computer(tmp_path, desktop=lambda: desktop)
    computer.instant = True
    ask, seen = script({"krok": "okno", "okno": "RejNET"},
                       {"krok": "kliknij", "okno": "RejNET", "przycisk": "Rodzaj czynności"},
                       {"krok": "wpisz", "okno": "RejNET", "pole": "Rodzaj czynności", "wartosc": "zamiana"},
                       {"krok": "wpisz", "okno": "RejNET", "pole": "Rodzaj czynności", "wartosc": "darowizna"},
                       {"krok": "kliknij", "okno": "RejNET", "przycisk": "Zapisz"},
                       {"krok": "kliknij", "okno": "RejNET", "przycisk": "Wyślij"},
                       {"krok": "koniec", "odpowiedz": "ok"})
    result = Agent(computer, ask).run("ustaw rodzaj czynności na darowiznę, zapisz i wyślij")
    steps = [s["wynik"] for s in result["steps"]]
    assert "to lista rozwijana" in steps[1] and "sprzedaż | darowizna | pełnomocnictwo" in steps[1] and desktop.clicked[:1] != ["Rodzaj czynności"]
    assert steps[2].startswith("BŁĄD") and "Dostępne pozycje: sprzedaż | darowizna" in steps[2]
    assert desktop.chosen == "darowizna" and "darowizna" in steps[3]
    assert "pojawiło się: [button] Drukuj" in seen[5] and "zmieniło się: [text] Numer aktu = „zapisano”" in seen[5]
    assert "nic się nie zmieniło" in seen[6] and "nie musi znaczyć" in seen[6]


def test_positions_of_a_classic_list_are_matched_whatever_the_spelling():
    from types import SimpleNamespace
    from worker.win_fill import Desktop

    picked = []

    def select(text):
        if text not in {"Sprzedaż", "Darowizna"}:
            raise ValueError("no such item")
        picked.append(text)
    box = SimpleNamespace(select=select, item_texts=lambda: ["Sprzedaż", "Darowizna"])
    desktop = Desktop(backend=SimpleNamespace(windows=lambda **kw: []), legacy=SimpleNamespace())
    control = Control(box, "select", "Rodzaj", "", [])
    assert desktop.options(control) == ["Sprzedaż", "Darowizna"]
    desktop.choose(control, "darowizna")
    desktop.choose(control, "sprzedaz")
    assert picked == ["Darowizna", "Sprzedaż"]
    with pytest.raises(Exception) as refused:
        desktop.choose(control, "zamiana")
    assert "Dostępne pozycje: Sprzedaż | Darowizna" in str(refused.value)


# ---- things the program draws itself (a side panel): the menu first, then a point the notary showed once
class PanelDesktop(FakeDesktop):
    """A program whose left panel is painted: only its window and a few named buttons are visible to Windows."""
    def __init__(self, takes_messages=True):
        super().__init__()
        self.takes, self.sent, self.title_now, self.log, self.quiet = takes_messages, [], "RejNET", [], False

    def where(self):
        return self.title_now

    def program(self):
        return "rejnet"                               # the file of the program: the same on every screen

    def rect(self):
        return 100, 50, 1100, 850                     # 1000 x 800

    def click_at(self, x, y, double=False):
        self.sent.append((x, y))
        if self.takes:
            self.title_now = "RejNET - Repertorium A"
        return True

    def to_front(self):
        self.log.append("NA WIERZCH")
        return 1

    def give_back(self, before):
        self.log.append("oddane")


def test_a_painted_panel_is_learned_from_one_click_and_pressed_by_name(tmp_path):
    desktop = PanelDesktop()
    computer = Computer(tmp_path, desktop=lambda: desktop, clicks=lambda rect, seconds: (300, 450))
    computer.instant = True
    assert "Zapamiętałem „Repertorium A”" in computer.learn_point("RejNET", "Repertorium A")
    assert computer.map.points("RejNET") == {"Repertorium A": {"x": 0.2, "y": 0.5}}
    assert "NAUCZONE PUNKTY" in computer.map.describe() and "Repertorium A" in computer.map.describe()
    ask, seen = script({"krok": "punkt", "okno": "RejNET", "nazwa": "repertorium a"}, {"krok": "koniec", "odpowiedz": "W module."})
    result = Agent(computer, ask).run("wejdź do repertorium A w RejNET")
    assert desktop.sent == [(200, 400)] and "w tle" in result["steps"][0]["wynik"]          # the share of the window, in its pixels
    assert "NAUCZONE PUNKTY" in seen[0]
    ask, _ = script({"krok": "punkt", "okno": "RejNET", "nazwa": "Księga"}, {"krok": "koniec", "odpowiedz": "x"})
    assert "Nie znam punktu" in Agent(computer, ask).run("wejdź")["steps"][0]["wynik"]
    with pytest.raises(Exception) as late:
        Computer(tmp_path, desktop=lambda: desktop, clicks=lambda rect, seconds: None).learn_point("RejNET", "Coś")
    assert "Nie zobaczyłem kliknięcia" in str(late.value)


def test_a_learned_point_that_ignores_messages_needs_the_front_for_a_moment(tmp_path):
    desktop, mouse = PanelDesktop(takes_messages=False), []
    quiet = Computer(tmp_path, desktop=lambda: desktop, allowed=lambda: {"background": True},
                     clicks=lambda rect, seconds: (300, 450), pointer=lambda x, y, d: mouse.append((x, y)))
    quiet.instant = True
    quiet.learn_point("RejNET", "Repertorium A")
    ask, _ = script({"krok": "punkt", "okno": "RejNET", "nazwa": "Repertorium A"})
    waiting = Agent(quiet, ask).run("wejdź do repertorium")
    assert waiting["stopped"]["kind"] == "wierzch" and mouse == []
    ask, _ = script({"krok": "punkt", "okno": "RejNET", "nazwa": "Repertorium A"}, {"krok": "koniec", "odpowiedz": "ok"})
    done = Agent(quiet, ask).run("wejdź do repertorium", allowed={"wierzch"})
    assert done["answer"] == "ok" and mouse == [(300, 450)] and desktop.log == ["NA WIERZCH", "oddane"]


def test_the_agent_asks_to_be_shown_and_repeats_the_whole_sequence(tmp_path):
    home = tmp_path / "home"
    admin = {"Authorization": "Bearer " + initialize(home)}
    desktop, replies, opened = PanelDesktop(takes_messages=False), [], []      # its title stays the same on every screen
    shown_clicks = iter([(300, 450), (600, 250), (700, 650), None])
    inference = Inference(Policy("eu-central-1", "eu.anthropic.claude-sonnet-4-6"), lambda s: Bedrock(replies), UsageLedger(home))
    client = TestClient(create_app(home, inference=inference, computer_roots=[tmp_path], attention_opener=opened.append,
                                   computer_parts={"clicks": lambda rect, seconds: next(shown_clicks), "label_at": lambda x, y: ""},
                                   fill_targets={"program": lambda: desktop, "strona": lambda: None}))
    client.get("/v2/agent/inbox", headers=admin)
    replies += [json.dumps({"krok": "pytanie", "problem": "nie widzę modułu Repertorium A, jest tylko narysowany w panelu",
                            "opcje": ["Spróbuj przez menu"], "punkt": "Repertorium A", "okno": "RejNET"})]
    blocks = client.post("/v2/chat", headers=admin, json={"text": "otwórz w programie RejNET repertorium A"}).json()["blocks"]
    asked = wait(client, admin, next(b["id"] for b in blocks if b["type"] == "job"))
    offer = next(i for b in asked if b["type"] == "buttons" for i in b["items"] if i["label"].startswith("Pokażę"))
    assert offer["say"] == "pokażę drogę Repertorium A w oknie RejNET"
    replies += [json.dumps({"krok": "pokaz", "okno": "RejNET", "nazwa": "Repertorium A"}),
                json.dumps({"krok": "koniec", "odpowiedz": "Jestem w Repertorium A."})]
    shown = client.post("/v2/chat", headers=admin, json={"text": offer["say"]}).json()["blocks"]
    assert "Nagrywam pokaz „Repertorium A”" in shown[0]["text"] and any(b["type"] == "buttons" for b in shown)
    assert "Koniec pokazu" in client.get(opened[-1].split("testserver", 1)[1] + "/dane").json()["actions"]
    learned = wait(client, admin, next(b["id"] for b in shown if b["type"] == "job"))
    assert "3 kliknięć" in learned[0]["text"]
    assert "Jestem w Repertorium A." in wait(client, admin, next(b["id"] for b in learned if b["type"] == "job"))[0]["text"]
    assert desktop.sent == [(200, 400), (500, 200), (600, 600)]                 # the same three places, in the window's own pixels
    assert "Nie nagrywam teraz" in client.post("/v2/chat", headers=admin, json={"text": "koniec pokazu"}).json()["blocks"][0]["text"]


def test_a_shown_way_checks_the_screen_and_stops_where_the_notary_typed(tmp_path):
    class Program(PanelDesktop):
        def click_at(self, x, y, double=False):
            self.sent.append((x, y))
            self.title_now = {(200, 400): "RejNET - Repertorium A", (500, 200): "RejNET - Nowy wpis"}.get((x, y), self.title_now)
            return True
    desktop = Program()
    titles = iter(["RejNET", "RejNET - Repertorium A", "RejNET - Nowy wpis", "RejNET - Nowy wpis"])
    clicks = iter([(300, 450), (600, 250), (700, 650, True), None])

    def notary(rect, seconds):                    # each click of the notary moves the program on, as it would
        spot = next(clicks)
        if spot is not None:
            desktop.click_at(round((spot[0] - 100)), round((spot[1] - 50)))
        return spot
    computer = Computer(tmp_path, desktop=lambda: desktop, clicks=notary, label_at=lambda x, y: "Nowy wpis" if x == 600 else "")
    computer.instant = True
    assert "3 kliknięć" in computer.record_show("RejNET", "Nowy wpis w repertorium")
    described = computer.map.describe()
    assert "POKAZANA DROGA „Nowy wpis w repertorium” (krok pokaz, 3 kliknięć, po drodze notariusz wpisywał wartości)" in described
    desktop.sent.clear()
    desktop.title_now = "RejNET"
    first = computer.replay_show("RejNET", "nowy wpis")
    assert desktop.sent == [(200, 400), (500, 200)] and "wykonałem kroki 1-2 z 3" in first and '"od": 3' in first
    assert "Odtworzyłem pokaz" in computer.replay_show("RejNET", "nowy wpis", start=3) and desktop.sent[-1] == (600, 600)
    desktop.title_now = "RejNET - Ustawienia"                                   # a different screen than at the show
    with pytest.raises(Exception) as wrong:
        computer.replay_show("RejNET", "nowy wpis")
    assert "ekran jest inny niż przy pokazie" in str(wrong.value) and len(desktop.sent) == 3
