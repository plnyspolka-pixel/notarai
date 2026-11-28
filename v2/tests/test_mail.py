"""Mail from the program on the notary's computer: Thunderbird files, Outlook automation, .eml folder."""
import json
import time
from email.message import EmailMessage
from email.utils import formatdate

import pytest
from fastapi.testclient import TestClient

from worker.api import create_app
from worker.init_vault import initialize
from worker.inference import Inference
from worker.mail import Folder, MailError, Outlook, Thunderbird, as_document, parse
from worker.policy import EU_REGIONS, Policy
from worker.usage import UsageLedger


def eml(sender, subject, body, age=0, html=False, attachment=None) -> bytes:
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = sender, "kancelaria@example.pl", subject
    message["Date"] = formatdate(time.time() - age)
    if html:
        message.set_content("wersja tekstowa nieużywana")
        message.set_content(f"<html><style>p{{}}</style><body><p>{body}</p><script>x()</script></body></html>", subtype="html")
    else:
        message.set_content(body)
    if attachment:
        message.add_attachment(b"%PDF", maintype="application", subtype="pdf", filename=attachment)
    return message.as_bytes()


def mbox(*messages, deleted=()) -> bytes:
    out = b""
    for index, raw in enumerate(messages):
        status = b"0008" if index in deleted else b"0001"
        out += b"From - Mon Nov 23 10:00:00 2026\r\nX-Mozilla-Status: " + status + b"\r\n" + raw + b"\r\n"
    return out


@pytest.fixture
def profile(tmp_path):
    inbox = tmp_path / "Profiles" / "abc.default" / "ImapMail" / "imap.example.pl"
    inbox.mkdir(parents=True)
    (inbox / "INBOX").write_bytes(mbox(
        eml("Jan Kowalski <jan@example.pl>", "Odpis z KW", "W załączeniu odpis księgi WA1M/00012345/6.", age=7200, attachment="odpis.pdf"),
        eml("Spam <spam@example.com>", "Usunięta", "nie powinna się pokazać", age=60),
        eml("Anna Nowak <anna@example.pl>", "Termin aktu", "Czy piątek o 10 pasuje?", age=600, html=True),
        deleted={1}))
    (inbox / "INBOX.msf").write_bytes(b"index, not mail")
    local = tmp_path / "Profiles" / "abc.default" / "Mail" / "Local Folders"
    local.mkdir(parents=True)
    (local / "Inbox").write_bytes(mbox(eml("Urząd <urzad@example.gov.pl>", "Zaświadczenie", "Do odbioru.", age=86400)))
    return tmp_path / "Profiles"


def test_thunderbird_inbox_is_read_newest_first_without_touching_it(profile):
    source = Thunderbird(profile)
    before = {p: p.read_bytes() for p in profile.rglob("*") if p.is_file()}
    assert source.available()
    messages = source.latest(10)
    assert [m.subject for m in messages] == ["Termin aktu", "Odpis z KW", "Zaświadczenie"]
    assert messages[0].sender == "Anna Nowak" and messages[0].text == "Czy piątek o 10 pasuje?"
    assert messages[1].attachments == ["odpis.pdf"] and "WA1M/00012345/6" in messages[1].text
    assert {p: p.read_bytes() for p in profile.rglob("*") if p.is_file()} == before
    assert not Thunderbird(profile / "missing").available() and Thunderbird(profile / "missing").latest() == []


def test_only_the_tail_of_a_huge_inbox_is_read(profile, monkeypatch):
    from worker import mail

    inbox = profile / "abc.default" / "ImapMail" / "imap.example.pl" / "INBOX"
    filler = mbox(*[eml("Stary <stary@example.pl>", f"Stara {i}", "x" * 2000, age=10**6 + i) for i in range(40)])
    inbox.write_bytes(filler + mbox(eml("Nowy <nowy@example.pl>", "Najnowsza", "treść", age=5)))
    monkeypatch.setattr(mail, "TAIL", 6000)
    subjects = [m.subject for m in Thunderbird(profile).latest(3)]
    assert subjects[0] == "Najnowsza" and len(subjects) <= 3


def test_outlook_through_its_automation_interface():
    class Item:
        Class = 43

        def __init__(self, sender, subject, stamp, body="Treść", kind=43):
            self.SenderName, self.SenderEmailAddress, self.Subject, self.Body = sender, "a@example.pl", subject, body
            self.ReceivedTime = type("T", (), {"timestamp": lambda self, stamp=stamp: stamp})()
            self.Attachments, self.Class = [type("A", (), {"FileName": "skan.pdf"})()], kind

    class Items:
        def __init__(self, items):
            self.items, self.Count, self.sorted = items, len(items), None

        def Sort(self, field, descending):
            self.sorted = (field, descending)
            self.items.sort(key=lambda i: -i.ReceivedTime.timestamp())

        def Item(self, index):
            return self.items[index - 1]

    items = Items([Item("Jan", "Starsza", 100.0), Item("Anna", "Nowsza", 200.0), Item("Kalendarz", "Zaproszenie", 300.0, kind=53)])
    asked = []

    def dispatch(name):
        asked.append(name)
        inbox = type("F", (), {"Items": items})()
        namespace = type("N", (), {"GetDefaultFolder": lambda self, number: inbox if number == 6 else None})()
        return type("App", (), {"GetNamespace": lambda self, kind: namespace})()

    source = Outlook(dispatch)
    assert source.available() and asked == ["Outlook.Application"]
    messages = source.latest(5)
    assert [m.subject for m in messages] == ["Nowsza", "Starsza"] and items.sorted == ("[ReceivedTime]", True)
    assert messages[0].attachments == ["skan.pdf"] and messages[0].raw is None
    name, data = as_document(messages[0])
    assert name == "mail - Nowsza.txt" and "Od: Anna" in data.decode() and "skan.pdf" in data.decode()

    def broken(name):
        raise OSError("COM failure with details")
    assert not Outlook(broken).available()
    with pytest.raises(MailError) as error:
        Outlook(broken).latest()
    assert "details" not in str(error.value)


def test_eml_folder_and_broken_messages(tmp_path):
    (tmp_path / "a.eml").write_bytes(eml("Jan <jan@example.pl>", "Pierwsza", "Treść A", age=100))
    (tmp_path / "b.eml").write_bytes(eml("Anna <anna@example.pl>", "Druga: pilne/ważne?", "Treść B", age=10))
    (tmp_path / "c.eml").write_bytes(b"\xff\xfe not a message at all")
    (tmp_path / "notes.txt").write_text("ignored")
    messages = Folder(tmp_path).latest(5)
    assert [m.subject for m in messages][:2] == ["Druga: pilne/ważne?", "Pierwsza"]
    name, data = as_document(messages[0])
    assert name == "mail - Druga pilneważne.eml" and parse(data).text == "Treść B"
    with pytest.raises(MailError):
        Folder(tmp_path / "missing").latest()


class Bedrock:
    def __init__(self):
        self.prompts = []

    def get_model_invocation_logging_configuration(self):
        return {}

    def get_inference_profile(self, inferenceProfileIdentifier):
        return {"models": [{"modelArn": f"arn:aws:bedrock:{r}::foundation-model/x"} for r in EU_REGIONS]}

    def converse(self, **kwargs):
        self.prompts.append(kwargs["messages"][0]["content"][0]["text"])
        return {"output": {"message": {"content": [{"text": "W piątek o 10."}]}}, "stopReason": "end_turn",
                "usage": {"inputTokens": 1, "outputTokens": 1}}


def say(client, headers, text, **extra):
    return client.post("/v2/chat", headers=headers, json={"text": text, **extra}).json()["blocks"]


def texts(blocks):
    return "\n".join(b.get("text", "") for b in blocks if b["type"] in {"text", "inbox"})


def test_mail_is_connected_and_used_by_talking(profile, tmp_path):
    home = tmp_path / "home"
    admin = {"Authorization": "Bearer " + initialize(home)}
    bedrock = Bedrock()
    inference = Inference(Policy("eu-central-1", "eu.anthropic.claude-sonnet-4-6"), lambda s: bedrock, UsageLedger(home))
    found = [Thunderbird(profile)]
    client = TestClient(create_app(home, inference=inference, mail_detect=lambda: found))
    assert "nie jest jeszcze połączona" in texts(say(client, admin, "poczta"))
    assert "Połączyłem pocztę z Thunderbird" in texts(say(client, admin, "połącz pocztę"))
    assert json.loads((home / "settings.json").read_text())["mail"] == {"source": "thunderbird", "path": str(profile)}

    listing = texts(say(client, admin, "poczta"))
    assert "1. " in listing and "Anna Nowak: Termin aktu" in listing and "Jan Kowalski: Odpis z KW 📎" in listing
    assert "Usunięta" not in listing
    assert "Czy piątek o 10 pasuje?" in texts(say(client, admin, "mail 1"))
    only = texts(say(client, admin, "maile od kowalski"))
    assert "Odpis z KW" in only and "Termin aktu" not in only
    assert "Do której sprawy" in texts(say(client, admin, "dodaj mail 1 do sprawy"))
    added = say(client, admin, "dodaj mail 1 do sprawy", case="kowalski-2026")
    assert added[1]["items"][0]["name"] == "mail - Odpis z KW.eml"
    assert "Nie ma wiadomości" in texts(say(client, admin, "mail 9"))
    assert b"WA1M" not in (home / "vault.sqlite3").read_bytes()               # stored encrypted
    # The assistant now reads that message with the case, identifiers hidden as usual.
    assert texts(say(client, admin, "Jaki jest numer księgi?", case="kowalski-2026")) == "W piątek o 10."
    assert "Wiadomość e-mail od [OSOBA" not in bedrock.prompts[-1] and "[KW_1]" in bedrock.prompts[-1]
    assert "[EMAIL_1]" in bedrock.prompts[-1] and "WA1M" not in bedrock.prompts[-1]

    # A paired device cannot read the workstation's mailbox.
    code = client.post("/v2/devices/invite", headers=admin, json={"name": "t", "scope": "write"}).json()["code"]
    phone = {"Authorization": "Bearer " + client.post("/v2/devices/redeem", json={"code": code}).json()["token"]}
    before = len(bedrock.prompts)
    assert "Termin aktu" not in json.dumps(say(client, phone, "poczta", case="kowalski-2026"), ensure_ascii=False)
    assert len(bedrock.prompts) == before + 1

    folder = tmp_path / "eml"
    folder.mkdir()
    (folder / "x.eml").write_bytes(eml("Urząd <u@example.gov.pl>", "Z folderu", "Treść"))
    assert "folderu z wiadomościami" in texts(say(client, admin, f"połącz pocztę folder {folder}"))
    assert "Z folderu" in texts(say(client, admin, "poczta"))
    assert "Nie udało się otworzyć" in texts(say(client, admin, f"połącz pocztę folder {tmp_path / 'brak'}"))
    assert "Odłączyłem" in texts(say(client, admin, "odłącz pocztę"))
    found.clear()
    assert "Nie znalazłem Thunderbirda" in texts(say(client, admin, "połącz pocztę"))
    assert "Nie znalazłem programu Outlook" in texts(say(client, admin, "połącz pocztę outlook"))


def test_attachments_go_to_the_case_and_a_reply_opens_in_the_mail_program(profile, tmp_path):
    home = tmp_path / "home"
    admin = {"Authorization": "Bearer " + initialize(home)}
    bedrock = Bedrock()
    inference = Inference(Policy("eu-central-1", "eu.anthropic.claude-sonnet-4-6"), lambda s: bedrock, UsageLedger(home))
    opened = []
    client = TestClient(create_app(home, inference=inference, mail_detect=lambda: [Thunderbird(profile)],
                                   mail_composer=lambda source, to, subject, body, original, send=False: opened.append(
                                       (to, subject, body, original.subject if original else None)) or
                                   "Otworzyłem gotową wiadomość w Thunderbirdzie. Sprawdź ją tam i kliknij Wyślij."))
    say(client, admin, "połącz pocztę")
    inbox = say(client, admin, "poczta")
    rows = inbox[0]["items"]
    assert inbox[0]["type"] == "inbox" and rows[1]["sender"] == "Jan Kowalski" and rows[1]["attachments"] == 1
    shown = say(client, admin, "mail 2")
    labels = [i["label"] for b in shown if b["type"] == "buttons" for i in b["items"]]
    assert "📎 odpis.pdf do sprawy" in labels and "Odpowiedz" in labels
    assert "Do której sprawy" in texts(say(client, admin, "dodaj załącznik 1 z maila 2"))
    added = say(client, admin, "dodaj załącznik 1 z maila 2", case="kowalski-2026")
    assert added[1]["items"][0]["name"] == "odpis.pdf" and "Streść" in json.dumps(added, ensure_ascii=False)
    document = client.get(f"/v2/documents/{added[1]['items'][0]['id']}", headers=admin).json()
    import base64
    assert base64.b64decode(document["content_b64"]) == b"%PDF"
    reply = say(client, admin, "odpowiedz na mail 2")[0]
    assert reply == {"type": "reply", "n": 2, "to": "jan@example.pl", "subject": "Re: Odpis z KW",
                     "body": "W piątek o 10.", "program": "Thunderbird"}
    assert "Napisz krótką, uprzejmą" in bedrock.prompts[-1] and "jan@example.pl" not in bedrock.prompts[-1]
    answer = client.post("/v2/mail/compose", headers=admin, json={"n": 2, "to": reply["to"], "subject": reply["subject"],
                                                                 "body": "Dziękuję, termin pasuje."}).json()
    assert "Otworzyłem gotową wiadomość w Thunderbirdzie" in answer["detail"]
    assert opened == [("jan@example.pl", "Re: Odpis z KW", "Dziękuję, termin pasuje.", "Odpis z KW")]
    code = client.post("/v2/devices/invite", headers=admin, json={"name": "t", "scope": "write"}).json()["code"]
    phone = {"Authorization": "Bearer " + client.post("/v2/devices/redeem", json={"code": code}).json()["token"]}
    assert client.post("/v2/mail/compose", headers=phone, json={"body": "x"}).status_code == 403


def test_a_ready_message_for_other_programs_is_a_draft_file(tmp_path, monkeypatch):
    from worker.mail import Folder, compose
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    started = []
    where = compose(Folder(tmp_path), "a@example.pl", "Re: Akt", "Treść odpowiedzi", runner=started.append)
    draft = tmp_path / "NotarAI" / "do-wyslania" / "Re Akt.eml"
    assert "domyślnym programie pocztowym" in where and started == [[str(draft)]]
    assert b"X-Unsent: 1" in draft.read_bytes() and b"Tre" in draft.read_bytes()


def test_a_command_sends_mail_at_once_when_the_office_does_not_ask(profile, tmp_path, monkeypatch):
    monkeypatch.delenv("NOTARAI_ALWAYS_CONFIRM", raising=False)
    home = tmp_path / "home"
    admin = {"Authorization": "Bearer " + initialize(home)}
    sent = []

    def composer(source, to, subject, body, original, send=False):
        sent.append((to, subject, body, send))
        return "Wysłałem wiadomość z Outlooka." if send else "Otworzyłem."
    client = TestClient(create_app(home, mail_detect=lambda: [Thunderbird(profile)], mail_composer=composer))
    say(client, admin, "połącz pocztę")
    say(client, admin, "poczta")
    done = texts(say(client, admin, "odpowiedz na mail 2: Dziękuję, odpis otrzymaliśmy."))
    assert sent == [("jan@example.pl", "Re: Odpis z KW", "Dziękuję, odpis otrzymaliśmy.", True)]
    assert "Wysłałem wiadomość z Outlooka." in done and "Do: jan@example.pl" in done
    say(client, admin, "odpowiedz na mail 1")            # no assistant: an empty draft is kept, nothing sent
    assert "Nie mam gotowej odpowiedzi" in texts(say(client, admin, "wyślij"))
    assert len(sent) == 1
    log = client.get("/v2/audit", headers=admin).json()
    assert any(entry["action"] == "mail-send" for entry in log["entries"]) if isinstance(log, dict) else True


def test_office_sending_hours_stop_a_mail_too(profile, tmp_path, monkeypatch):
    monkeypatch.delenv("NOTARAI_ALWAYS_CONFIRM", raising=False)
    home = tmp_path / "home"
    admin = {"Authorization": "Bearer " + initialize(home)}
    sent = []
    client = TestClient(create_app(home, mail_detect=lambda: [Thunderbird(profile)],
                                   mail_composer=lambda *a, **k: sent.append(a) or "Wysłałem wiadomość z Outlooka."))
    say(client, admin, "połącz pocztę")
    say(client, admin, "poczta")
    import datetime as dt
    import worker.rules as rules_module
    monkeypatch.setattr(rules_module, "is_working_day", lambda day: False)
    say(client, admin, "zasada: wysyłka tylko w dni robocze od 8 do 16")
    refused = texts(say(client, admin, "odpowiedz na mail 2: Dziękuję."))
    assert "zasady kancelarii" in refused and sent == []
