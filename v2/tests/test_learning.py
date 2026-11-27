"""Learning mode: lessons from the notary's own corrections, visible, removable, without personal data."""
from fastapi.testclient import TestClient

from worker.api import create_app
from worker.init_vault import initialize
from worker.learning import Learning, anonymize
from worker.local_secrets import read_secret
from worker.vault import Vault


def store(tmp_path):
    home = tmp_path / "home"
    initialize(home)
    return Learning(Vault(home, read_secret(home, "vault.key"))), home


def test_names_numbers_and_addresses_are_cut_out():
    text = "Jan Kowalski, PESEL 44051401359, jan@example.pl, kupuje lokal nr 5 od Anny Nowak."
    assert anonymize(text, ["Jan Kowalski", "Anna Nowak"]) == \
        "[osoba], PESEL ###########, [email], kupuje lokal nr # od [osoba]."
    assert anonymize("Przekazano Nowakowi i nowa umowa", ["Anna Nowak"]) == "Przekazano [osoba] i nowa umowa"


class Assistant:
    """Stands in for the EU model: says which general rules the edits show."""
    enabled = True

    def __init__(self, reply):
        self.reply, self.asked = reply, []

    def ask(self, **kwargs):
        self.asked.append(kwargs)
        from types import SimpleNamespace
        return SimpleNamespace(text=self.reply)


PROPOSED = ["Stawający oświadcza, że jest właścicielem lokalu nr 5. Cena wynosi 500 000 zł.", "Strony wnoszą o wpis."]
APPROVED = ["Stawający oświadcza, że jest jedynym właścicielem lokalu nr 5. Cena wynosi 500 000 zł.",
            "Notariusz pouczył strony o treści art. 92 Prawa o notariacie. Strony wnoszą o wpis."]


def test_edits_of_a_draft_teach_general_rules_not_trivia(tmp_path):
    learning, home = store(tmp_path)
    assistant = Assistant("- W umowach sprzedaży stawający oświadcza, że jest jedynym właścicielem.\n"
                          "- Kancelaria zawsze dopisuje pouczenie z art. 92 Prawa o notariacie.\n- [OSOBA_1] x")
    learning._inference = lambda: assistant
    learned = learning.from_draft(PROPOSED, APPROVED, ["Jan Kowalski"], kind="umowa sprzedaży")
    assert [l["kind"] for l in learned] == ["zasada", "zasada"]
    assert learned[1]["text"] == "Kancelaria zawsze dopisuje pouczenie z art. 92 Prawa o notariacie. (umowa sprzedaży)"
    sent = assistant.asked[0]
    assert sent["purpose"] == "insight" and "BYŁO:" in sent["text"] and "500" not in sent["text"]
    assert learning.guidance("akt") == ""                                          # nothing used before a yes
    learning.decide(learned[1]["id"], True)
    guidance = learning.guidance("akt")
    assert "pouczenie z art. 92" in guidance and "jedynym właścicielem lokalu nr #" in guidance   # rule + its material
    assert b"pouczenie" not in (home / "vault.sqlite3").read_bytes()               # encrypted


def test_capital_letters_and_typos_are_not_lessons(tmp_path):
    learning, _ = store(tmp_path)
    assert learning.from_draft(["Strony wnosza o wpis do ksiegi."], ["Strony wnoszą o wpis do księgi."]) == []
    assert learning.from_draft(["umowa sprzedaży lokalu."], ["Umowa sprzedaży lokalu."]) == []


def test_without_an_assistant_the_exact_edits_are_proposed(tmp_path):
    learning, _ = store(tmp_path)
    learned = learning.from_draft(PROPOSED, APPROVED, ["Jan Kowalski"], kind="umowa sprzedaży")
    assert any(l["text"].startswith("Dodaję zdanie „Notariusz pouczył strony") for l in learned)


def test_dictation_fixes_capitals_quietly_and_asks_about_misheard_words(tmp_path):
    learning, _ = store(tmp_path)
    assert learning.from_dictation("spotkanie z panem kowalskim", "spotkanie z panem Kowalskim") == []
    assert learning.apply_dictation("Dzwonił pan kowalskim.") == "Dzwonił pan Kowalskim."        # done, no question
    misheard = learning.from_dictation("wizyta u notariatu w piątek", "wizyta u notariusza w piątek")
    assert [l["data"] for l in misheard] == [{"heard": "notariatu", "say": "notariusza"}]
    assert learning.apply_dictation("u notariatu") == "u notariatu"                              # until confirmed
    learning.decide(misheard[0]["id"], True)
    assert learning.apply_dictation("u notariatu") == "u notariusza"
    assert learning.from_dictation("termin o 10", "termin o 11") == []
    assert learning.from_dictation("akt sprzedaży", "akt darowizny") == []


def test_replies_teach_the_office_tone_every_few_replies(tmp_path):
    learning, _ = store(tmp_path)
    assistant = Assistant("- Odpowiedzi zaczynają się od „Szanowni Państwo” i podają termin z dniem tygodnia.")
    learning._inference = lambda: assistant
    told = []
    for word in ["piątek", "poniedziałek", "wtorek"]:
        told += learning.from_reply(f"Szanowni Państwo, dziękujemy za wiadomość. Termin {word} pasuje. Z poważaniem", ["Kowalski"])
    assert [l["kind"] for l in told] == ["zasada"] and "Szanowni Państwo" in told[0]["text"]
    assert "dziękujemy" in learning.guidance("mail")                     # her own replies serve as examples at once


def test_the_notary_teaches_sees_and_removes_lessons_by_talking(tmp_path):
    home = tmp_path / "home"
    admin = {"Authorization": "Bearer " + initialize(home)}
    client = TestClient(create_app(home))

    def say(text, **extra):
        return client.post("/v2/chat", headers=admin, json={"text": text, **extra}).json()["blocks"]
    assert "Zapamiętałem: akty podpisujemy w gabinecie" in say("zapamiętaj: akty podpisujemy w gabinecie nr 2")[0]["text"]
    assert "zapamiętałem korektę" in say("to było źle: taksa od darowizny w I grupie jest inna")[0]["text"]
    assert client.get("/v2/learning", headers=admin).json() == {"enabled": True, "total": 2, "pending": 0, "counts": {
        "zasada": 0, "poprawka": 0, "slownik": 0, "odpowiedz": 0, "wiedza": 1, "korekta": 1}}
    listing = say("czego się nauczyłeś")[0]["text"]
    assert "Wiedza kancelarii:\n1. akty podpisujemy w gabinecie nr 2" in listing and "Korekty odpowiedzi:\n2." in listing
    asked = say("zapomnij lekcję 1")
    assert asked[0]["type"] == "confirm"
    client.post("/v2/chat", headers=admin, json={"confirm": asked[0]["token"]})
    assert client.get("/v2/learning", headers=admin).json()["total"] == 1
    assert "wyłączony" in say("wyłącz tryb uczenia")[0]["text"]
    assert client.get("/v2/learning", headers=admin).json()["enabled"] is False
    assert "Tryb uczenia: wyłączony" in say("tryb uczenia")[0]["text"]


def test_dictation_learning_is_reachable_from_the_window(tmp_path):
    home = tmp_path / "home"
    admin = {"Authorization": "Bearer " + initialize(home)}
    client = TestClient(create_app(home))
    learned = client.post("/v2/learning/dictation", headers=admin,
                          json={"heard": "wizyta u notariatu", "final": "wizyta u notariusza"}).json()
    assert [l["text"] for l in learned["learned"]] == ["Gdy słyszę „notariatu”, piszę „notariusza”."]
    ident = learned["learned"][0]["id"]
    assert client.get("/v2/learning", headers=admin).json()["pending"] == 1
    said = client.post("/v2/chat", headers=admin, json={"text": f"potwierdź lekcję {ident}"}).json()["blocks"]
    assert said[0]["text"].startswith("📘 Potwierdzone") and client.get("/v2/learning", headers=admin).json()["pending"] == 0
