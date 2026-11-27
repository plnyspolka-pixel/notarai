"""Editing a vault document in a desktop editor: check-out, check-in, conflicts, cleanup."""
import os
import shutil
import subprocess
from io import BytesIO

import pytest
from docx import Document
from fastapi.testclient import TestClient

from worker.api import create_app
from worker.docx_writer import build, extract
from worker.init_vault import initialize
from worker.local_secrets import read_secret
from worker.vault import Vault
from worker.workcopy import WorkCopies, WorkCopyError, _safe_name


@pytest.fixture
def desk(tmp_path):
    home = tmp_path / "home"
    initialize(home)
    vault = Vault(home, read_secret(home, "vault.key"))
    opened = []
    return home, vault, WorkCopies(home, vault, opener=opened.append), opened


def edit(path, text):
    document = Document(path)
    document.add_paragraph(text)
    document.save(path)


def test_edit_cycle_creates_the_next_revision_and_removes_plaintext(desk):
    home, vault, copies, opened = desk
    doc, _ = vault.put(None, 0, "Akt: sprzedaż?.docx", build(["Pierwotna treść."]), case="sprawa-1")
    info = copies.checkout(doc)
    path = opened[0]
    assert str(path) == info["path"] and path.name == "Akt_ sprzedaż_.docx" and not info["changed"]
    assert oct(path.stat().st_mode & 0o777) == "0o600" or os.name == "nt"
    with pytest.raises(WorkCopyError):
        copies.checkout(doc)
    edit(path, "Dopisany paragraf.")
    assert copies.list()[0]["changed"]
    (path.parent / ("~$" + path.name)).write_bytes(b"lock")          # Word still has it open
    with pytest.raises(WorkCopyError):
        copies.checkin(doc)
    (path.parent / ("~$" + path.name)).unlink()
    assert copies.checkin(doc) == {"id": doc, "version": 2, "saved": True}
    assert extract(vault.get(doc)[2]) == ["Pierwotna treść.", "Dopisany paragraf."]
    assert vault.get(doc)[1] == "Akt: sprzedaż?.docx" and vault.case_of(doc) == "sprawa-1"
    assert not (home / "workcopies" / doc).exists() and copies.list() == []
    actions = [e["action"] for e in vault.audit()]
    assert actions.index("write") < actions.index("checkout")      # newest first: checkout, then the new revision


def test_unchanged_and_discarded_copies_leave_no_revision(desk):
    home, vault, copies, opened = desk
    doc, _ = vault.put(None, 0, "akt.docx", build(["Treść."]))
    copies.checkout(doc)
    assert copies.checkin(doc) == {"id": doc, "version": 1, "saved": False}
    copies.checkout(doc)
    edit(opened[-1], "Niechciana zmiana.")
    copies.discard(doc)
    assert vault.versions(doc) == [1] and not any((home / "workcopies").iterdir())
    with pytest.raises(WorkCopyError):
        copies.checkin(doc)


def test_newer_revision_in_the_vault_keeps_the_working_copy(desk):
    _, vault, copies, opened = desk
    doc, _ = vault.put(None, 0, "akt.docx", build(["Treść."]))
    copies.checkout(doc)
    edit(opened[0], "Moja zmiana.")
    vault.put(doc, 1, "akt.docx", build(["Zmiana z telefonu."]))
    with pytest.raises(WorkCopyError) as error:
        copies.checkin(doc)
    assert "nowsza wersja" in str(error.value)
    assert "Moja zmiana." in extract(opened[0].read_bytes())      # nothing was lost
    assert vault.versions(doc) == [2, 1]


def test_refusals(desk):
    _, vault, copies, opened = desk
    program, _ = vault.put(None, 0, "skrypt.exe", b"MZ")
    with pytest.raises(WorkCopyError):
        copies.checkout(program)
    with pytest.raises(WorkCopyError):
        copies.checkout("11111111-1111-4111-8111-111111111111")
    doc, _ = vault.put(None, 0, "akt.docx", build(["Treść."]))
    copies.checkout(doc)
    opened[-1].unlink()
    with pytest.raises(WorkCopyError):
        copies.checkin(doc)
    copies.discard(doc)
    assert _safe_name("CON.docx") == "_CON.docx" and _safe_name("../../x.docx") == ".._.._x.docx".strip(" .")
    assert "/" not in _safe_name("a/b\\c.docx") and _safe_name("   ") == "dokument"


def test_only_the_workstation_panel_can_open_documents(tmp_path):
    home = tmp_path / "home"
    admin = {"Authorization": "Bearer " + initialize(home)}
    opened = []
    client = TestClient(create_app(home, opener=opened.append))
    doc = client.post("/v2/documents", headers=admin, json={
        "name": "akt.txt", "expected_version": 0, "content_b64": "YQ=="}).json()["id"]
    code = client.post("/v2/devices/invite", headers=admin, json={"name": "telefon", "scope": "write"}).json()["code"]
    phone = {"Authorization": "Bearer " + client.post("/v2/devices/redeem", json={"code": code}).json()["token"]}
    assert client.post(f"/v2/documents/{doc}/checkout", headers=phone).status_code == 403
    assert client.get("/v2/workcopies", headers=phone).status_code == 403
    assert opened == []
    assert client.post(f"/v2/documents/{doc}/checkout", headers=admin).status_code == 200
    opened[0].write_text("zmienione w edytorze")
    assert client.get("/v2/workcopies", headers=admin).json()[0]["changed"] is True
    assert client.post(f"/v2/workcopies/{doc}/checkin", headers=admin).json()["version"] == 2
    assert client.post(f"/v2/workcopies/{doc}/checkin", headers=admin).status_code == 409


@pytest.mark.skipif(not (os.environ.get("NOTARAI_V2_TEST_SOFFICE") or shutil.which("soffice")),
                    reason="LibreOffice is not installed")
def test_real_libreoffice_edit_is_checked_in(desk, tmp_path):
    """A real editor rewrites the file (ODT -> DOCX round trip); the result is stored and readable."""
    _, vault, copies, opened = desk
    soffice = os.environ.get("NOTARAI_V2_TEST_SOFFICE") or shutil.which("soffice")
    doc, _ = vault.put(None, 0, "akt.docx", build(["# UMOWA", "Treść zapisana przez NotarAI."]))
    copies.checkout(doc)
    path = opened[0]
    profile = (tmp_path / "profile").as_uri()
    out = tmp_path / "out"
    for target, source in (("odt", path), ("docx", out / "akt.odt")):
        subprocess.run([soffice, f"-env:UserInstallation={profile}", "--headless", "--convert-to", target,
                        "--outdir", str(out), str(source)], check=True, timeout=120, capture_output=True)
    shutil.copyfile(out / "akt.docx", path)
    result = copies.checkin(doc)
    assert result["saved"] and result["version"] == 2
    assert extract(vault.get(doc)[2]) == ["UMOWA", "Treść zapisana przez NotarAI."]
