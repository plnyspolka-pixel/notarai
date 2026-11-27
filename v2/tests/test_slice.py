"""The vertical slice: case documents -> draft -> approval -> verified DOCX revision.

The model is a fake Bedrock client; everything else is the real worker.
"""
import base64
import json
import sqlite3
from io import BytesIO

import pytest
from docx import Document
from fastapi.testclient import TestClient

from worker import recovery
from worker.api import create_app
from worker.connect import State
from worker.connect_sdk import ConnectSession, LocalReceipts, RevisionTarget, WriteDocx, WrittenRevision
from worker.docx_adapter import DOCX_APP, OpenXmlDocx
from worker.docx_writer import build, canonical, digest, extract, text_digest
from worker.inference import Inference
from worker.init_vault import initialize
from worker.local_secrets import read_secret
from worker.policy import EU_REGIONS, Policy
from worker.usage import UsageLedger
from worker.vault import Vault

MODEL = "eu.anthropic.claude-sonnet-4-6"
DRAFT = ("# UMOWA SPRZEDAŻY\n\n[OSOBA_1], PESEL [PESEL_1], sprzedaje lokal.\n"
         "Cena: [DO UZUPEŁNIENIA: cena].\n[OSOBA_7] nie istnieje.")


class Bedrock:
    """Stands in for both the control plane and the runtime."""
    def __init__(self, reply=DRAFT, stop="end_turn"):
        self.reply, self.stop, self.prompts = reply, stop, []

    def get_model_invocation_logging_configuration(self):
        return {}

    def get_inference_profile(self, inferenceProfileIdentifier):
        return {"models": [{"modelArn": f"arn:aws:bedrock:{r}::foundation-model/x"} for r in EU_REGIONS]}

    def converse(self, **kwargs):
        self.prompts.append(kwargs)
        return {"output": {"message": {"content": [{"text": self.reply}]}}, "stopReason": self.stop,
                "usage": {"inputTokens": 100, "outputTokens": 50}}


@pytest.fixture
def office(tmp_path):
    home = tmp_path / "home"
    token = initialize(home)
    bedrock = Bedrock()
    inference = Inference(Policy("eu-central-1", MODEL), lambda service: bedrock, UsageLedger(home))
    client = TestClient(create_app(home, inference=inference))
    return client, {"Authorization": "Bearer " + token}, home, bedrock


def upload(client, headers, name, data, case="sprawa-1", **extra):
    body = {"name": name, "expected_version": 0, "case": case,
            "content_b64": base64.b64encode(data).decode(), **extra}
    return client.post("/v2/documents", headers=headers, json=body)


def pair(client, admin, scope, cases=None):
    code = client.post("/v2/devices/invite", headers=admin,
                       json={"name": "telefon", "scope": scope, "cases": cases}).json()["code"]
    return {"Authorization": "Bearer " + client.post("/v2/devices/redeem", json={"code": code}).json()["token"]}


SOURCE = "Sprzedający Jan Kowalski, PESEL 44051401359, zbywa lokal nr 5. Kowalskiego reprezentuje pełnomocnik."


def test_draft_is_reviewed_approved_and_verified(office):
    client, admin, home, bedrock = office
    assert upload(client, admin, "notatka.txt", SOURCE.encode()).status_code == 200
    assert upload(client, admin, "skan.pdf", b"%PDF").status_code == 200
    assert upload(client, admin, "obca.txt", b"TAJEMNICA INNEJ SPRAWY", case="sprawa-2").status_code == 200

    response = client.post("/v2/cases/sprawa-1/draft", headers=admin,
                           json={"text": "Przygotuj umowę sprzedaży.", "names": ["Jan Kowalski"]})
    assert response.status_code == 200, response.text
    proposal = response.json()
    sent = bedrock.prompts[0]["messages"][0]["content"][0]["text"]
    assert "44051401359" not in sent and "Kowalski" not in sent and "TAJEMNICA" not in sent
    assert "[OSOBA_1]" in sent and "Przygotuj umowę sprzedaży." in sent
    assert proposal["paragraphs"][0] == "# UMOWA SPRZEDAŻY"
    assert proposal["paragraphs"][2] == "Jan Kowalski, PESEL 44051401359, sprzedaje lokal."
    assert proposal["gaps"] == 1 and proposal["unknown_placeholders"] == ["[OSOBA_7]"]
    assert [s["name"] for s in proposal["sources"]] == ["notatka.txt"] and proposal["skipped"] == ["skan.pdf"]
    # Nothing is stored before approval.
    assert len(client.get("/v2/documents?case=sprawa-1", headers=admin).json()) == 2

    edited = proposal["paragraphs"][:3] + ["Cena: 500 000 zł."]
    approved = client.post(f"/v2/drafts/{proposal['id']}/approve", headers=admin,
                           json={"name": "umowa.docx", "paragraphs": edited})
    assert approved.status_code == 200, approved.text
    result = approved.json()
    assert result["state"] == "verified" and result["version"] == 1
    stored = client.get("/v2/documents/" + result["id"], headers=admin).json()
    assert extract(base64.b64decode(stored["content_b64"])) == [
        "UMOWA SPRZEDAŻY", "Jan Kowalski, PESEL 44051401359, sprzedaje lokal.", "Cena: 500 000 zł."]
    # Single use: the proposal is gone.
    assert client.post(f"/v2/drafts/{proposal['id']}/approve", headers=admin,
                       json={"name": "umowa.docx"}).status_code == 409
    with sqlite3.connect(home / "connect-receipts.sqlite3") as db:
        assert db.execute("SELECT operation, state FROM receipts").fetchall() == [("write_docx", "verified")]
    assert client.get("/v2/usage", headers=admin).json() == [
        {"model": MODEL, "purpose": "draft", "calls": 1, "input_tokens": 100, "output_tokens": 50}]
    actions = [(e["actor"], e["action"]) for e in client.get("/v2/audit", headers=admin).json()]
    assert ("connect-verify", "read") in actions and ("local-admin", "write") in actions

    # A second draft becomes the next revision of the same document.
    second = client.post("/v2/cases/sprawa-1/draft", headers=admin, json={"text": "Popraw."})
    assert second.status_code == 200, second.text
    second = second.json()
    again = client.post(f"/v2/drafts/{second['id']}/approve", headers=admin,
                        json={"name": "umowa.docx", "base": {"id": result["id"], "version": 1}})
    assert again.json()["version"] == 2 and again.json()["id"] == result["id"]
    stale = client.post("/v2/cases/sprawa-1/draft", headers=admin, json={"text": "Jeszcze raz."}).json()
    conflict = client.post(f"/v2/drafts/{stale['id']}/approve", headers=admin,
                           json={"name": "umowa.docx", "base": {"id": result["id"], "version": 1}})
    assert conflict.status_code == 409 and "ponownie" in conflict.json()["detail"]
    assert client.get(f"/v2/documents/{result['id']}/versions", headers=admin).json() == [2, 1]


def test_ask_answers_from_case_documents_only(office):
    client, admin, _, bedrock = office
    bedrock.reply = "Sprzedającym jest [OSOBA_1]."
    upload(client, admin, "notatka.txt", SOURCE.encode())
    answer = client.post("/v2/cases/sprawa-1/ask", headers=admin,
                         json={"text": "Kto sprzedaje?", "names": ["Jan Kowalski"]})
    assert answer.json()["answer"] == "Sprzedającym jest Jan Kowalski."
    assert client.post("/v2/cases/pusta/ask", headers=admin, json={"text": "?"}).status_code == 409


def test_draft_limits(office):
    client, admin, _, bedrock = office
    upload(client, admin, "notatka.txt", SOURCE.encode())
    bedrock.stop = "max_tokens"
    assert client.post("/v2/cases/sprawa-1/draft", headers=admin, json={"text": "x"}).status_code == 409
    bedrock.stop, bedrock.reply = "end_turn", "   "
    assert client.post("/v2/cases/sprawa-1/draft", headers=admin, json={"text": "x"}).status_code == 409
    bedrock.reply = DRAFT
    proposal = client.post("/v2/cases/sprawa-1/draft", headers=admin, json={"text": "x"}).json()
    for bad in ({"name": "umowa.txt"}, {"name": "../umowa.docx"}, {"name": "umowa.docx", "paragraphs": ["\x00"]}):
        assert client.post(f"/v2/drafts/{proposal['id']}/approve", headers=admin, json=bad).status_code == 409
    other = upload(client, admin, "obca.docx", build(["x"]), case="sprawa-2").json()
    assert client.post(f"/v2/drafts/{proposal['id']}/approve", headers=admin,
                       json={"name": "umowa.docx", "template": {"id": other["id"], "version": 1}}).status_code == 409
    assert client.delete(f"/v2/drafts/{proposal['id']}", headers=admin).status_code == 200
    assert client.get(f"/v2/drafts/{proposal['id']}", headers=admin).status_code == 409


def test_ai_off_by_default(tmp_path):
    home = tmp_path / "home"
    admin = {"Authorization": "Bearer " + initialize(home)}
    client = TestClient(create_app(home))
    upload(client, admin, "notatka.txt", b"x")
    response = client.post("/v2/cases/sprawa-1/draft", headers=admin, json={"text": "x"})
    assert response.status_code == 403 and "wyłączone" in response.json()["detail"]
    status = client.get("/v2/status", headers=admin).json()
    assert status["ai"] == {"enabled": False, "signed_in": False, "account_configured": False, "pseudonymize": True}
    assert status["mode"] == "synthetic-only"


def test_device_limited_to_a_case_sees_nothing_else(office):
    client, admin, _, _ = office
    mine = upload(client, admin, "moja.txt", b"a", case="sprawa-1").json()["id"]
    other = upload(client, admin, "obca.txt", b"b", case="sprawa-2").json()["id"]
    loose = upload(client, admin, "luzna.txt", b"c", case=None).json()["id"]
    phone = pair(client, admin, "write", cases=["sprawa-1"])
    assert client.get("/v2/cases", headers=phone).json() == ["sprawa-1"]
    assert [d["id"] for d in client.get("/v2/documents?include_names=true", headers=phone).json()] == [mine]
    assert client.get("/v2/documents", headers=phone).json() == [{"id": mine, "version": 1}]
    assert client.post("/v2/sync/plan", headers=phone, json={"items": []}).json()["download"] == [
        {"id": mine, "version": 1}]
    for hidden in (other, loose):
        assert client.get("/v2/documents/" + hidden, headers=phone).status_code == 404
        assert client.get(f"/v2/documents/{hidden}/versions", headers=phone).status_code == 404
        assert client.post("/v2/documents", headers=phone, json={
            "id": hidden, "expected_version": 1, "name": "x.txt", "content_b64": "eA=="}).status_code == 404
    assert client.get("/v2/documents?case=sprawa-2", headers=phone).status_code == 404
    assert upload(client, phone, "nowa.txt", b"d", case="sprawa-2").status_code == 404
    assert upload(client, phone, "nowa.txt", b"d", case=None).status_code == 404
    assert upload(client, phone, "nowa.txt", b"d", case="sprawa-1").status_code == 200
    assert client.post("/v2/cases/sprawa-2/ask", headers=phone, json={"text": "?"}).status_code == 404
    assert client.get("/v2/status", headers=phone).json()["cases"] == ["sprawa-1"]
    assert client.post("/v2/devices/invite", headers=admin,
                       json={"name": "x", "cases": ["../zle"]}).status_code == 400
    # Another device cannot approve or read someone else's proposal.
    upload(client, admin, "notatka.txt", SOURCE.encode())
    proposal = client.post("/v2/cases/sprawa-1/draft", headers=admin, json={"text": "x"}).json()
    assert client.get(f"/v2/drafts/{proposal['id']}", headers=phone).status_code == 409
    reader = pair(client, admin, "read")
    assert client.post("/v2/cases/sprawa-1/draft", headers=reader, json={"text": "x"}).status_code == 403


def test_status_recovery_backup_and_fee(office, tmp_path):
    client, admin, home, _ = office
    status = client.get("/v2/status", headers=admin).json()
    assert status["recovery"] == {"enrolled": False, "last_backup": None, "backup_overdue": True,
                                  "backup_dir_configured": False, "offsite_enabled": False, "last_offsite": None}
    assert client.post("/v2/backup", headers=admin).status_code == 409
    code = client.post("/v2/recovery/enroll", headers=admin).json()["code"]
    assert client.post("/v2/recovery/enroll", headers=admin).status_code == 409
    backups = tmp_path / "usb"
    backups.mkdir()
    (home / "settings.json").write_text(json.dumps({"backup_dir": str(backups)}))
    client = TestClient(create_app(home))
    upload(client, admin, "akt.txt", b"tresc")
    made = client.post("/v2/backup", headers=admin).json()
    assert made["documents"] == 1
    status = client.get("/v2/status", headers=admin).json()["recovery"]
    assert status["enrolled"] and not status["backup_overdue"] and status["last_backup"]
    assert recovery.restore(backups / made["file"], tmp_path / "nowy", code)["documents"] == 1

    fee = client.post("/v2/taksa", headers=admin, json={"parameters": {
        "data": "2026-11-27", "czynnosci": [{"rodzaj": "sprzedaz", "wartosc": 500000}]}})
    assert fee.status_code == 200 and fee.json()["tabela"]["id"] == "2026"
    phone = pair(client, admin, "read")
    for path in ("/v2/audit", "/v2/usage"):
        assert client.get(path, headers=phone).status_code == 403
    assert client.post("/v2/backup", headers=phone).status_code == 403
    assert client.post("/v2/account/login", headers=admin,
                       json={"email": "a@b.pl", "password": "x"}).status_code == 409


def test_invalid_settings_stop_the_worker(tmp_path):
    home = tmp_path / "home"
    initialize(home)
    for bad in ('{"ai": {"region": "us-east-1"}}', '{"ai": {"model": "global.anthropic.x"}}',
                '{"unknown": 1}', "not json",
                '{"account": {"region": "eu-central-1", "user_pool_id": "us-east-1_x", "client_id": "c", "identity_pool_id": "eu-central-1:x"}}'):
        (home / "settings.json").write_text(bad)
        with pytest.raises(ValueError):
            create_app(home)


def test_pairing_guesses_are_throttled(office):
    client, _, _, _ = office
    codes = [client.post("/v2/devices/redeem", json={"code": "x" * 30}).status_code for _ in range(12)]
    assert codes[:10] == [403] * 10 and codes[10:] == [429, 429]


# ---------------------------------------------------------------- Connect write contract
def session(tmp_path, adapter_class=OpenXmlDocx):
    vault = Vault(tmp_path, b"K" * 32)
    receipts = LocalReceipts(tmp_path)
    return vault, ConnectSession([adapter_class(vault)], {DOCX_APP: frozenset({"write_docx"})}, receipts), receipts


def test_text_roundtrip_and_template(tmp_path):
    text = canonical("# Tytuł\r\n\r\n\r\nPierwszy  akapit.\t\nDrugi.\n\n")
    assert text == ("# Tytuł", "", "Pierwszy akapit.", "Drugi.")
    template = Document()
    template.add_paragraph("STARA TREŚĆ WZORU")
    template.sections[0].header.paragraphs[0].text = "Kancelaria Notarialna"
    raw = BytesIO()
    template.save(raw)
    data = build(text, raw.getvalue())
    assert extract(data) == ["Tytuł", "Pierwszy akapit.", "Drugi."]
    assert Document(BytesIO(data)).sections[0].header.paragraphs[0].text == "Kancelaria Notarialna"
    assert text_digest(data) == digest(text)
    for bad in ([], [""], ["\x07"], [1]):
        with pytest.raises(ValueError):
            canonical(bad)


def test_approved_hash_must_match_written_content(tmp_path):
    vault, sdk, receipts = session(tmp_path)
    request = WriteDocx(app=DOCX_APP, name="akt.docx", content_sha256=digest(["zatwierdzone"]))
    token = sdk.approve(request)
    with pytest.raises(PermissionError):
        sdk.execute(request, token, ("podmienione",))
    assert vault.list() == []
    with pytest.raises(PermissionError):
        sdk.execute(request, token, ("zatwierdzone",))   # the approval was consumed
    assert sdk.execute(request, sdk.approve(request), ("zatwierdzone",)).state is State.VERIFIED


def test_unverifiable_write_is_uncertain_and_not_retried(tmp_path):
    class Lying(OpenXmlDocx):
        calls = 0

        def write(self, request, paragraphs, actor):
            type(self).calls += 1
            written = super().write(request, ("coś innego",), actor)
            return WrittenRevision(target=written.target, content_sha256=request.content_sha256)

    vault, sdk, receipts = session(tmp_path, Lying)
    request = WriteDocx(app=DOCX_APP, name="akt.docx", content_sha256=digest(["tekst"]))
    result = sdk.execute(request, sdk.approve(request), ("tekst",))
    assert result.state is State.UNCERTAIN and result.data is None and Lying.calls == 1
    with sqlite3.connect(receipts.path) as db:
        assert db.execute("SELECT state FROM receipts").fetchall() == [("uncertain",)]


def test_write_request_is_strict():
    for bad in ({"name": "a.exe"}, {"name": "a/b.docx"}, {"case": "../x"}, {"content_sha256": "zz"}, {"path": "C:/x"}):
        with pytest.raises(ValueError):
            WriteDocx.model_validate({"app": DOCX_APP.model_dump(), "name": "akt.docx",
                                      "content_sha256": "0" * 64, **bad})
    with pytest.raises(ValueError):
        RevisionTarget(document_id="not-a-uuid", version=1)


# ---------------------------------------------------------------- workstation panel
def test_panel_session_is_local_only_single_use_and_expires(office):
    from worker.devices import DeviceRegistry

    client, admin, home, _ = office
    assert client.post("/v2/devices/invite", headers=admin, json={"name": "x", "scope": "admin"}).status_code == 400
    registry = DeviceRegistry(home)
    with pytest.raises(ValueError):
        registry.invite("panel", "admin")
    with pytest.raises(ValueError):
        registry.invite("panel", "admin", allow_admin=True, cases=["sprawa-1"])
    code = registry.invite("panel", "admin", allow_admin=True)["code"]
    session = client.post("/v2/devices/redeem", json={"code": code}).json()
    assert session["scope"] == "admin"
    panel = {"Authorization": "Bearer " + session["token"]}
    assert client.get("/v2/devices", headers=panel).json() == []      # panel sessions are not listed as devices
    assert client.get("/v2/audit", headers=panel).status_code == 200
    assert client.post("/v2/devices/redeem", json={"code": code}).status_code == 403
    with sqlite3.connect(home / "devices.sqlite3") as db:
        db.execute("UPDATE devices SET expires = 1")
    assert client.get("/v2/audit", headers=panel).status_code == 401
    assert client.get("/v2/admin").status_code == 200 and client.get("/v2/qrcode.js").status_code == 200


def test_settings_are_validated_and_release_gate_is_not_a_setting(office, tmp_path):
    client, admin, home, _ = office
    current = client.get("/v2/settings", headers=admin).json()
    assert current["ai"]["enabled"] is False and current["ai"]["real_data_approved"] is False
    assert client.put("/v2/settings", headers=admin,
                      json={**current, "ai": {**current["ai"], "real_data_approved": True}}).status_code == 403
    assert client.put("/v2/settings", headers=admin,
                      json={**current, "ai": {**current["ai"], "region": "us-east-1"}}).status_code == 400
    assert client.put("/v2/settings", headers=admin,
                      json={**current, "backup_dir": str(tmp_path / "missing")}).status_code == 409
    assert not (home / "settings.json").exists()
    saved = client.put("/v2/settings", headers=admin, json={**current, "backup_dir": str(tmp_path)})
    assert saved.status_code == 200 and json.loads((home / "settings.json").read_text())["backup_dir"] == str(tmp_path)
    assert client.get("/v2/status", headers=admin).json()["recovery"]["backup_dir_configured"] is True
    assert client.get("/v2/settings", headers=pair(client, admin, "write")).status_code == 403


def test_ui_assets_obey_the_content_security_policy(office):
    client, _, _, _ = office
    for page in ("/v2/pocket", "/v2/admin"):
        html = client.get(page).text
        assert "<style" not in html and " style=" not in html and "onclick=" not in html
    for asset in ("pocket.css", "pocket.js", "pocket-sw.js", "pocket.webmanifest", "pocket-icon.svg"):
        assert client.get("/v2/" + asset).status_code == 200
    assert client.get("/v2/vault.sqlite3").status_code == 404


def test_settings_reject_urls_that_could_escape(office):
    client, admin, _, _ = office
    current = client.get("/v2/settings", headers=admin).json()
    for relay in ("ws://127.0.0.1:1@evil.example/x", "ws://127.0.0.1:1 ; frame-ancestors *",
                  "wss://ok.example/\r\nX: y", "ws://relay.example", "http://relay.example"):
        body = {**current, "tunnel": {"enabled": True, "relay_url": relay, "pocket_url": "https://notarai.pl/pocket"}}
        assert client.put("/v2/settings", headers=admin, json=body).status_code == 400, relay
    assert "evil" not in client.get("/v2/pocket").headers["content-security-policy"]


def test_foreign_document_id_gives_no_existence_hint(office):
    client, admin, _, _ = office
    other = upload(client, admin, "obca.txt", b"b", case="sprawa-2").json()["id"]
    phone = pair(client, admin, "write", cases=["sprawa-1"])
    body = {"id": other, "expected_version": 0, "name": "x.txt", "case": "sprawa-1", "content_b64": "eA=="}
    unknown = {**body, "id": "11111111-1111-4111-8111-111111111111", "case": "sprawa-2"}
    assert client.post("/v2/documents", headers=phone, json=body).status_code == 404
    assert client.post("/v2/documents", headers=phone, json=unknown).status_code == 404


def test_pocket_exports_as_a_static_site_and_preset_is_valid(tmp_path):
    import sys
    from pathlib import Path

    from worker.settings import validate

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "tools"))
    from export_pocket import export

    names = export(tmp_path / "pocket")
    html = (tmp_path / "pocket" / "index.html").read_text(encoding="utf-8")
    assert "index.html" in names and 'src="pocket.js"' in html and "/v2/" not in html
    assert '"./"' in (tmp_path / "pocket" / "pocket-sw.js").read_text(encoding="utf-8")
    preset = validate(json.loads((root / "installer" / "preset.json").read_text(encoding="utf-8")))
    assert not preset.ai.enabled and not preset.tunnel.enabled and not preset.replica.enabled
    assert not preset.ai.real_data_approved and preset.account.region == "eu-central-1"
