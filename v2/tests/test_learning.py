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


def test_edits_of_a_draft_become_lessons_used_in_the_next_draft(tmp_path):
    learning, home = store(tmp_path)
    proposed = ["Stawający oświadcza, że jest właścicielem lokalu nr 5. Cena wynosi 500 000 zł.",
                "Strony wnoszą o wpis."]
    approved = ["Stawający oświadcza, że jest jedynym właścicielem lokalu nr 5. Cena wynosi 500 000 zł.",
                "Notariusz pouczył strony o treści art. 92 Prawa o notariacie. Strony wnoszą o wpis."]
    learned = learning.from_draft(proposed, approved, ["Jan Kowalski"], kind="umowa sprzedaży")
    texts = [l["text"] for l in learned]
    assert "Zamiast „Stawający oświadcza, że jest właścicielem lokalu nr #.” piszę „Stawający oświadcza, że jest " \
           "jedynym właścicielem lokalu nr #.”." in texts
    assert any(t.startswith("Dodaję zdanie „Notariusz pouczył strony o treści art. ## Prawa") for t in texts)
    assert learning.from_draft(proposed, approved, ["Jan Kowalski"]) == []          # known: stronger, not repeated
    assert learning.guidance("akt") == ""                                           # proposed, not used yet
    for lesson in learned:
        learning.decide(lesson["id"], True)
    assert "jedynym właścicielem" in learning.guidance("akt") and "500" not in learning.guidance("akt")
    assert b"jedynym" not in (home / "vault.sqlite3").read_bytes()                     # encrypted


def test_dictation_corrections_fix_the_next_dictation(tmp_path):
    learning, _ = store(tmp_path)
    learned = learning.from_dictation("spotkanie z panem kowalskim w sprawie notariatu", "spotkanie z panem Kowalskim w sprawie notariatu")
    assert [l["data"] for l in learned] == [{"heard": "kowalskim", "say": "Kowalskim"}]
    assert learning.from_dictation("termin o 10", "termin o 11") == []           # numbers are edits, not mishearing
    assert learning.from_dictation("akt sprzedaży", "akt darowizny") == []        # a different word: an edit
    assert learning.apply_dictation("Dzwonił pan kowalskim.") == "Dzwonił pan kowalskim."      # not confirmed yet
    learning.decide(learned[0]["id"], True)
    assert learning.apply_dictation("Dzwonił pan kowalskim.") == "Dzwonił pan Kowalskim."
    rejected = learning.from_dictation("u notariusza bielaka", "u notariusza Bielaka")[0]
    learning.decide(rejected["id"], False)
    assert learning.apply_dictation("bielaka") == "bielaka" and learning.pending() == []


def test_replies_teach_the_tone_and_only_the_five_latest_stay(tmp_path):
    learning, _ = store(tmp_path)
    for word in ["piątek", "poniedziałek", "wtorek", "środa", "czwartek", "sobota", "jutro"]:
        learning.from_reply(f"Szanowny Panie, dziękujemy za wiadomość. Termin {word} pasuje. Z poważaniem", ["Kowalski"])
    assert len(learning.lessons("odpowiedz")) == 5
    for lesson in learning.pending():
        learning.decide(lesson["id"], True)
    assert "dziękujemy" in learning.guidance("mail")


def test_the_notary_teaches_sees_and_removes_lessons_by_talking(tmp_path):
    home = tmp_path / "home"
    admin = {"Authorization": "Bearer " + initialize(home)}
    client = TestClient(create_app(home))

    def say(text, **extra):
        return client.post("/v2/chat", headers=admin, json={"text": text, **extra}).json()["blocks"]
    assert "Zapamiętałem: akty podpisujemy w gabinecie" in say("zapamiętaj: akty podpisujemy w gabinecie nr 2")[0]["text"]
    assert "zapamiętałem korektę" in say("to było źle: taksa od darowizny w I grupie jest inna")[0]["text"]
    assert client.get("/v2/learning", headers=admin).json() == {"enabled": True, "total": 2, "pending": 0, "counts": {
        "poprawka": 0, "slownik": 0, "odpowiedz": 0, "wiedza": 1, "korekta": 1}}
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
                          json={"heard": "akt u notariusza bielaka", "final": "akt u notariusza Bielaka"}).json()
    assert [l["text"] for l in learned["learned"]] == ["Gdy słyszę „bielaka”, piszę „Bielaka”."]
    ident = learned["learned"][0]["id"]
    assert client.get("/v2/learning", headers=admin).json()["pending"] == 1
    said = client.post("/v2/chat", headers=admin, json={"text": f"potwierdź lekcję {ident}"}).json()["blocks"]
    assert said[0]["text"].startswith("📘 Potwierdzone") and client.get("/v2/learning", headers=admin).json()["pending"] == 0
