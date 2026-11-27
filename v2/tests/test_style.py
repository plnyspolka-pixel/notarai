"""Learning the office's way of writing from acts on its computer: what repeats is style, names are not."""
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from worker.api import create_app
from worker.docx_writer import build
from worker.init_vault import initialize
from worker.style import Style, is_act, kind_of, learn, read_text

CLIENTS = [("Jan Kowalski", "44051401359", "WA1M/00012345/6", 450000), ("Anna Nowak", "02070803628", "KR1P/00098765/4", 610000),
           ("Piotr Zieliński", "85010112345", "PO1P/00011111/1", 390000), ("Ewa Lis", "90020212345", "GD1G/00022222/2", 520000)]


def act(client, repertorium):
    name, pesel, kw, price = client
    return [
        f"Repertorium A numer {repertorium}/2025",
        "AKT NOTARIALNY",
        f"Dnia 12 marca 2025 roku przed notariuszem Marią Testową, prowadzącą Kancelarię Notarialną w Warszawie, stawili się: {name}, PESEL {pesel}.",
        "UMOWA SPRZEDAŻY",
        f"§ 1. Stawający oświadcza, że jest właścicielem lokalu, dla którego Sąd Rejonowy prowadzi księgę wieczystą {kw}.",
        f"§ 2. Cena sprzedaży wynosi {price} zł.",
        "§ 3. Strony oświadczają, że cena została zapłacona przed podpisaniem niniejszego aktu.",
        "§ 4. Notariusz pouczył strony o treści art. 91 Prawa o notariacie.",
        "§ 5. Koszty tego aktu ponosi kupujący.",
        "Akt ten został odczytany, przyjęty i podpisany.",
        "Pobrano: taksa notarialna zgodnie z rozporządzeniem.",
    ]


@pytest.fixture
def office_disk(tmp_path):
    disk = tmp_path / "C"
    (disk / "Users" / "notariusz" / "Documents" / "Akty 2025").mkdir(parents=True)
    (disk / "Users" / "notariusz" / "AppData" / "Roaming").mkdir(parents=True)
    (disk / "Archiwum").mkdir()
    folder = disk / "Users" / "notariusz" / "Documents" / "Akty 2025"
    (folder / "sprzedaz-kowalski.docx").write_bytes(build(act(CLIENTS[0], 101)))
    (folder / "sprzedaz-nowak.docx").write_bytes(build(act(CLIENTS[1], 102)))
    (disk / "Archiwum" / "sprzedaz-zielinski.txt").write_text("\n".join(act(CLIENTS[2], 103)), encoding="cp1250")
    content = "".join(f"<text:p>{line}</text:p>" for line in act(CLIENTS[3], 104))
    with zipfile.ZipFile(disk / "Archiwum" / "sprzedaz-lis.odt", "w") as archive:
        archive.writestr("content.xml", f'<office:document-content><office:body><office:text>{content}</office:text></office:body></office:document-content>')
    (folder / "lista zakupów.txt").write_text("mleko, chleb, notariusz?", encoding="utf-8")
    (folder / "~$sprzedaz-kowalski.docx").write_bytes(b"lock")
    # An act in a system folder is not read: the scan skips application data.
    (disk / "Users" / "notariusz" / "AppData" / "Roaming" / "kopia.txt").write_text("\n".join(act(CLIENTS[0], 999)), encoding="utf-8")
    return disk


def test_acts_are_recognised_and_classified(office_disk):
    text = read_text(office_disk / "Archiwum" / "sprzedaz-lis.odt")
    assert "Ewa Lis" in text and is_act(text) and kind_of(text) == "sprzedaż"
    assert not is_act("mleko, chleb, notariusz?")
    assert kind_of("AKT NOTARIALNY. UMOWA DAROWIZNY. Darczyńca daruje") == "darowizna"
    assert kind_of("Pełnomocnictwo. Ustanawiam pełnomocnikiem") == "pełnomocnictwo"
    assert read_text(office_disk / "Archiwum" / "sprzedaz-zielinski.txt").count("Zieliński") == 1   # cp1250 read


def test_what_repeats_is_kept_and_what_names_clients_is_not(office_disk, tmp_path):
    home = tmp_path / "home"
    initialize(home)
    from worker.local_secrets import read_secret
    from worker.vault import Vault

    style = Style(Vault(home, read_secret(home, "vault.key")))
    profile = style.scan([office_disk], "local-admin", seconds=60)
    assert profile["acts"] == {"sprzedaż": 4} and profile["complete"]
    texts = [f["text"] for f in profile["formulas"]["sprzedaż"]]
    assert "§ …. Notariusz pouczył strony o treści art. … Prawa o notariacie." in texts
    assert "Akt ten został odczytany, przyjęty i podpisany." in texts
    assert texts.index("Akt ten został odczytany, przyjęty i podpisany.") > texts.index(
        "§ …. Notariusz pouczył strony o treści art. … Prawa o notariacie.")        # usual order kept
    stored = json.dumps(profile, ensure_ascii=False)
    for name, pesel, kw, _ in CLIENTS:
        assert name.split()[1] not in stored and pesel not in stored and kw not in stored
    # The notary's own opening repeats in every act, so it is the office's formula; clients are not in it.
    assert "Dnia … marca … roku przed notariuszem Marią Testową, prowadzącą Kancelarię Notarialną w Warszawie, stawili się:" in texts
    assert [d["name"] for d in style._vault.summaries()] == ["styl.json"]           # no act was copied
    guidance = style.guidance("przygotuj umowę sprzedaży lokalu")
    assert "STYL KANCELARII" in guidance and "Notariusz pouczył strony" in guidance
    assert style.guidance("przygotuj testament") == ""


def test_learning_needs_more_than_one_act():
    assert learn({"testament": ["Jedno zdanie, które się nie powtarza nigdzie indziej."]}) == {}


def test_the_notary_starts_it_in_the_chat_and_drafts_use_it(office_disk, tmp_path):
    import base64
    import time

    from worker.inference import Inference
    from worker.policy import EU_REGIONS, Policy
    from worker.usage import UsageLedger

    class Bedrock:
        prompts = []

        def get_model_invocation_logging_configuration(self):
            return {}

        def get_inference_profile(self, inferenceProfileIdentifier):
            return {"models": [{"modelArn": f"arn:aws:bedrock:{r}::foundation-model/x"} for r in EU_REGIONS]}

        def converse(self, **kwargs):
            self.prompts.append(kwargs["messages"][0]["content"][-1]["text"])
            return {"output": {"message": {"content": [{"text": "# UMOWA SPRZEDAŻY\nTekst."}]}}, "stopReason": "end_turn",
                    "usage": {"inputTokens": 1, "outputTokens": 1}}

    home = tmp_path / "home"
    admin = {"Authorization": "Bearer " + initialize(home)}
    bedrock = Bedrock()
    inference = Inference(Policy("eu-central-1", "eu.anthropic.claude-sonnet-4-6"), lambda s: bedrock, UsageLedger(home))
    client = TestClient(create_app(home, inference=inference))

    def say(sentence, **extra):
        blocks = client.post("/v2/chat", headers=admin, json={"text": sentence, **extra}).json()["blocks"]
        return blocks, "\n".join(b.get("text", "") for b in blocks)

    assert "Nie znam jeszcze stylu" in say("styl kancelarii")[1]
    assert "Nie ma takiego folderu" in say(f"naucz się stylu z {tmp_path / 'brak'}")[1]
    started = say(f"naucz się stylu z {office_disk}")[1]
    assert "nic nie kopiuję i nic nie wysyłam" in started
    for _ in range(100):
        if "Znam styl kancelarii" in say("stan nauki stylu")[1]:
            break
        time.sleep(0.1)
    blocks, summary = say("styl kancelarii")
    assert "z 4 aktów (sprzedaż: 4)" in summary
    assert "Notariusz pouczył strony" in say("pokaż styl sprzedaż")[1]
    client.post("/v2/documents", headers=admin, json={"name": "notatka.txt", "expected_version": 0, "case": "k",
                                                       "content_b64": base64.b64encode(b"Sprzedaz lokalu.").decode()})
    say("przygotuj umowę sprzedaży lokalu", case="k")
    assert "STYL KANCELARII" in bedrock.prompts[-1] and "Akt ten został odczytany, przyjęty i podpisany." in bedrock.prompts[-1]
