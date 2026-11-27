"""Filling forms by itself: matching, verification, multi-page forms, sending only after approval.

Web pages are filled in a real headless Chromium; Windows programs with a fake UI tree here and
a real WinForms window in the Windows CI job (test_windows_fill.py).
"""
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest

from worker.autofill import Autofill, Control, FillError, choose_option, match, score
from worker.win_fill import label_controls

FORM = """<!doctype html><html lang="pl"><head><meta charset="utf-8"><title>Wniosek</title></head><body>
<form action="/wyslano.html" method="get">
  <h1>Wniosek o wpis w księdze wieczystej</h1>
  <label for="kw">Numer księgi wieczystej</label> <input id="kw" name="kw">
  <div><span>PESEL wnioskodawcy:</span> <input name="pesel"></div>
  <p>Rodzaj wpisu</p><select name="rodzaj"><option></option><option>Własność</option><option>Hipoteka</option></select>
  <input aria-label="Opłata sądowa" name="oplata">
  <label><input type="checkbox" name="zgoda"> Oświadczam, że dane są prawdziwe</label>
  <iframe src="/ramka.html" width="400" height="80"></iframe>
  <button type="button" onclick="document.getElementById('druga').hidden=false">Dalej</button>
  <section id="druga" hidden><label>Miejscowość <input name="miasto"></label></section>
  <button type="submit">Wyślij wniosek</button>
</form></body></html>"""
FRAME = """<!doctype html><meta charset="utf-8"><label for="t">Telefon kontaktowy</label><input id="t">"""
SENT = """<!doctype html><meta charset="utf-8"><title>Przyjęto</title><p>Wniosek przyjęto.</p>"""


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    root = tmp_path_factory.mktemp("site")
    (root / "wniosek.html").write_text(FORM, encoding="utf-8")
    (root / "ramka.html").write_text(FRAME, encoding="utf-8")
    (root / "wyslano.html").write_text(SENT, encoding="utf-8")
    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Quiet, directory=str(root)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture
def browser(tmp_path):
    pytest.importorskip("playwright")
    from worker.web_fill import Browser, _default_executable

    executable, channel = _default_executable()
    if executable is None and channel != "msedge":
        pytest.skip("no browser on this machine")
    web = Browser(tmp_path / "profile", headless=True)
    yield web
    web.close()


def step(pole, zrodlo="", akcja=""):
    return SimpleNamespace(pole=pole, zrodlo=zrodlo, dlaczego="", akcja=akcja)


PROCEDURE = SimpleNamespace(nazwa="Wniosek o wpis w KW", rodzaj="strona", adres="", kroki=[
    step("Numer księgi wieczystej"), step("PESEL wnioskodawcy"), step("Rodzaj wpisu"),
    step("Opłata sądowa"), step("Oświadczam, że dane są prawdziwe"), step("Telefon kontaktowy"),
    step("Pole, którego nie ma"), step("Dalej", "kliknij"), step("Miejscowość"),
    step("Wyślij wniosek", "wyślij")])
VALUES = [{"value": v} for v in ("WA1M/00012345/6", "44051401359", "własność", "200 zł", "tak", "600 100 200",
                                 "x", "kliknij", "Warszawa", "kliknij")]


def test_labels_and_options_are_matched_like_a_person_would():
    assert score("PESEL wnioskodawcy:", "PESEL wnioskodawcy") == 1.0
    assert score("Numer KW", "Numer księgi wieczystej") < 0.8
    assert choose_option(["", "Własność", "Hipoteka"], "własność") == "Własność"
    assert choose_option(["Tak", "Nie"], "może") is None
    controls = [Control(1, "text", "Imię"), Control(2, "text", "Imię ojca"), Control(3, "button", "Imię")]
    assert match(controls, "Imię", {"text"}, set()).ref == 1
    assert match(controls, "Imię", {"text"}, {id(controls[0])}).ref == 2
    assert match(controls, "Nazwisko", {"text"}, set()) is None


def test_a_web_form_is_filled_verified_and_sent_only_after_approval(site, browser):
    browser.open(site + "/wniosek.html")
    receipts = []
    autofill = Autofill({"strona": lambda: browser}, receipts=lambda *a: receipts.append(a))
    preview = autofill.fill(PROCEDURE, VALUES, actor="local-admin", case="kowalski-2026")
    states = {r["field"]: r["state"] for r in preview["report"]}
    assert states == {"Numer księgi wieczystej": "filled", "PESEL wnioskodawcy": "filled", "Rodzaj wpisu": "filled",
                      "Opłata sądowa": "filled", "Oświadczam, że dane są prawdziwe": "filled",
                      "Telefon kontaktowy": "filled", "Pole, którego nie ma": "missing", "Dalej": "clicked",
                      "Miejscowość": "filled"}
    assert preview["send"] == "Wyślij wniosek" and preview["image"][:3] == b"\xff\xd8\xff"
    assert preview["where"].endswith("/wniosek.html")                 # nothing was sent
    with pytest.raises(FillError):
        autofill.send(preview["token"], "inne-urzadzenie", "strona")
    sent = autofill.send(preview["token"], "local-admin", "strona")
    assert sent["state"] == "sent" and "/wyslano.html?" in sent["where"] and "pesel=44051401359" in sent["where"]
    assert "rodzaj=W%C5%82asno%C5%9B%C4%87" in sent["where"] and "zgoda=on" in sent["where"]
    with pytest.raises(FillError):
        autofill.send(preview["token"], "local-admin", "strona")       # one approval, one press
    assert [r[1:] for r in receipts] == [("fill", "Wniosek o wpis w KW", "strona", "partial"),
                                         ("send", "Wniosek o wpis w KW", "strona", "started"),
                                         ("send", "Wniosek o wpis w KW", "strona", "sent")]


def test_a_change_after_the_preview_blocks_sending(site, browser):
    browser.open(site + "/wniosek.html")
    autofill = Autofill({"strona": lambda: browser})
    preview = autofill.fill(PROCEDURE, VALUES, actor="local-admin", case="k")
    pesel = next(c for c in browser.controls() if c.label.startswith("PESEL"))
    browser.type(pesel, "02070803628")                              # the notary corrected a field by hand
    with pytest.raises(FillError) as error:
        autofill.send(preview["token"], "local-admin", "strona")
    assert "zmienił się od podglądu" in str(error.value)
    assert browser.where().endswith("/wniosek.html")


def test_only_https_pages_are_opened(browser):
    for bad in ("file:///etc/passwd", "javascript:alert(1)", "http://example.com/"):
        with pytest.raises(FillError):
            browser.open(bad)


class FakeElement:
    def __init__(self, kind, name, rect, value=""):
        self.kind, self.name, self.rect, self.value, self.pressed = kind, name, rect, value, 0


def test_windows_fields_get_the_label_next_to_them():
    items = [
        {"type": "Text", "name": "Nazwisko:", "rect": (10, 10, 90, 30)},
        {"type": "Edit", "name": "", "rect": (100, 10, 300, 30)},
        {"type": "Text", "name": "Numer aktu", "rect": (10, 50, 120, 70)},
        {"type": "Edit", "name": "", "rect": (10, 72, 200, 92)},
        {"type": "Edit", "name": "Uwagi", "rect": (10, 120, 300, 200)},
        {"type": "Button", "name": "Zapisz", "rect": (10, 210, 80, 230)},
        {"type": "Pane", "name": "", "rect": (0, 0, 400, 300)},
    ]
    assert [(i["kind"], i["label"]) for i in label_controls(items)] == [
        ("text", "Nazwisko"), ("text", "Numer aktu"), ("text", "Uwagi"), ("button", "Zapisz")]


def test_a_program_window_is_filled_through_the_same_plan():
    class Window:
        def __init__(self):
            self.fields = {"Nazwisko": "", "Repertorium": "", "Wyślij do sądu": None}
            self.sent = False

        def controls(self):
            out = [Control(name, "text", name, value) for name, value in self.fields.items() if value is not None]
            return out + [Control("send", "button", "Wyślij do sądu")]

        def focus(self, title):
            assert title == "Program kancelaryjny"

        def type(self, control, value):
            self.fields[control.ref] = value.upper() if control.ref == "Repertorium" else value

        def read(self, control):
            return self.fields[control.ref]

        def click(self, control):
            self.sent = True

        def where(self):
            return "Program kancelaryjny - wysłano" if self.sent else "Program kancelaryjny"

        def snapshot(self):
            return None

    window = Window()
    procedure = SimpleNamespace(nazwa="Rejestr", rodzaj="program", adres="Program kancelaryjny", kroki=[
        step("Nazwisko"), step("Repertorium"), step("Wyślij do sądu", "wyślij")])
    autofill = Autofill({"program": lambda: window})
    preview = autofill.fill(procedure, [{"value": "Kowalski"}, {"value": "a 123/2026"}, {"value": "kliknij"}],
                            actor="local-admin", case="k")
    assert [(r["field"], r["state"]) for r in preview["report"]] == [("Nazwisko", "filled"), ("Repertorium", "filled")]
    assert not window.sent
    assert autofill.send(preview["token"], "local-admin", "program")["state"] == "sent" and window.sent
    with pytest.raises(FillError):
        Autofill({}).fill(procedure, [], actor="a", case="k")


def test_the_notary_says_fill_and_approves_sending_in_the_chat(site, browser, tmp_path):
    import base64
    import json

    from fastapi.testclient import TestClient

    from worker.api import create_app
    from worker.inference import Inference
    from worker.init_vault import initialize
    from worker.policy import EU_REGIONS, Policy
    from worker.procedures import CASE, SUFFIX
    from worker.usage import UsageLedger
    from worker.vault import Vault
    from worker.local_secrets import read_secret

    class Bedrock:
        def get_model_invocation_logging_configuration(self):
            return {}

        def get_inference_profile(self, inferenceProfileIdentifier):
            return {"models": [{"modelArn": f"arn:aws:bedrock:{r}::foundation-model/x"} for r in EU_REGIONS]}

        def converse(self, **kwargs):
            prompt = kwargs["messages"][0]["content"][-1]["text"]
            assert "Dalej" not in prompt and "Wyślij wniosek" not in prompt      # buttons need no values
            values = [{"pole": "Numer księgi wieczystej", "wartosc": "[KW_1]"}, {"pole": "PESEL wnioskodawcy", "wartosc": "[PESEL_1]"},
                      {"pole": "Rodzaj wpisu", "wartosc": "własność"}, {"pole": "Miejscowość", "wartosc": "Warszawa"}]
            return {"output": {"message": {"content": [{"text": json.dumps({"wartosci": values}, ensure_ascii=False)}]}},
                    "stopReason": "end_turn", "usage": {"inputTokens": 1, "outputTokens": 1}}

    home = tmp_path / "home"
    admin = {"Authorization": "Bearer " + initialize(home)}
    vault = Vault(home, read_secret(home, "vault.key"))
    procedure = {"nazwa": "Wniosek o wpis w KW", "program": "Portal", "rodzaj": "strona", "adres": site + "/wniosek.html",
                 "kroki": [{"pole": "Numer księgi wieczystej"}, {"pole": "PESEL wnioskodawcy"}, {"pole": "Rodzaj wpisu"},
                           {"pole": "Dalej", "akcja": "kliknij"}, {"pole": "Miejscowość"},
                           {"pole": "Wyślij wniosek", "akcja": "wyslij"}]}
    vault.put(None, 0, "wniosek-o-wpis-w-kw" + SUFFIX, json.dumps(procedure).encode(), case=CASE)
    vault.put(None, 0, "akt.txt", "Nabywca Jan Kowalski, PESEL 44051401359, księga WA1M/00012345/6.".encode(), case="k-1")
    inference = Inference(Policy("eu-central-1", "eu.anthropic.claude-sonnet-4-6"), lambda s: Bedrock(), UsageLedger(home))
    client = TestClient(create_app(home, inference=inference, fill_targets={"strona": lambda: browser}))

    def say(text, **extra):
        return client.post("/v2/chat", headers=admin, json={"text": text, "case": "k-1", **extra}).json()["blocks"]

    assert "Otworzyłem" in say(f"otwórz stronę {site}/wniosek.html")[0]["text"]
    blocks = say("wypełnij wniosek o wpis w KW")
    filled = next(b for b in blocks if b["type"] == "filled")
    assert [(r["field"], r["state"]) for r in filled["report"]] == [
        ("Numer księgi wieczystej", "filled"), ("PESEL wnioskodawcy", "filled"), ("Rodzaj wpisu", "filled"),
        ("Dalej", "clicked"), ("Miejscowość", "filled")]
    assert base64.b64decode(filled["image"])[:3] == b"\xff\xd8\xff" and filled["send"] == "Wyślij wniosek"
    confirm = next(b for b in blocks if b["type"] == "confirm")
    assert browser.where().endswith("/wniosek.html")                      # not sent before approval
    device_code = client.post("/v2/devices/invite", headers=admin, json={"name": "t", "scope": "write"}).json()["code"]
    phone = {"Authorization": "Bearer " + client.post("/v2/devices/redeem", json={"code": device_code}).json()["token"]}
    phone_blocks = client.post("/v2/chat", headers=phone, json={"text": "wypełnij wniosek o wpis w KW", "case": "k-1"}).json()["blocks"]
    assert [b["type"] for b in phone_blocks] == ["text", "fill"] and "panelu stanowiska" in phone_blocks[0]["text"]
    assert "wygasło" in client.post("/v2/chat", headers=phone, json={"confirm": confirm["token"]}).json()["blocks"][0]["text"]
    done = client.post("/v2/chat", headers=admin, json={"confirm": confirm["token"]}).json()["blocks"]
    assert "Wysłałem „Wniosek o wpis w KW”" in done[0]["text"] and done[1]["type"] == "image"
    assert "pesel=44051401359" in browser.where() and "miasto=Warszawa" in browser.where()
    journal = "\n".join(b["text"] for b in say("dziennik") if b["type"] == "text")
    assert "wypełnił formularz" in journal and "wysłał formularz" in journal
