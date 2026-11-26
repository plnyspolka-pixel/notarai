import json
import os
import subprocess
import sys
from io import BytesIO
from uuid import UUID
from zipfile import ZipFile

from docx import Document
import pytest

from worker.connect import State
from worker.connect_sdk import ConnectSession, InspectDocx, LocalReceipts, RevisionTarget
from worker.docx_adapter import DOCX_APP, OpenXmlDocx
from worker.local_secrets import write_new_secret
from worker.vault import Vault


def docx_with_paragraphs(*paragraphs, table=False):
    document = Document()
    for text in paragraphs:
        document.add_paragraph(text)
    if table:
        document.add_table(rows=1, cols=1).cell(0, 0).text = "synthetic cell"
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def inspect(vault, home, document_id, version):
    request = InspectDocx(
        app=DOCX_APP, target=RevisionTarget(document_id=UUID(document_id), version=version)
    )
    session = ConnectSession(
        [OpenXmlDocx(vault)], {DOCX_APP: frozenset({"inspect_docx"})}, LocalReceipts(home)
    )
    return session.execute(request, session.approve(request))


def test_cli_reads_exact_encrypted_revision(tmp_path):
    key = os.urandom(32)
    write_new_secret(tmp_path, "vault.key", key)
    vault = Vault(tmp_path, key)
    first = docx_with_paragraphs("synthetic first", "synthetic second", table=True)
    document_id, _ = vault.put(None, 0, "synthetic.DOCX", first)
    second = docx_with_paragraphs("synthetic revision two")
    vault.put(document_id, 1, "synthetic.docx", second)
    completed = subprocess.run(
        [sys.executable, "-m", "worker.inspect_docx", document_id, "1", "--approve", "--synthetic-only"],
        env={**os.environ, "NOTARAI_V2_HOME": str(tmp_path)},
        capture_output=True, check=True, timeout=20,
    )
    assert json.loads(completed.stdout) == {
        "state": "verified",
        "backend": DOCX_APP.id,
        "data": {
            "target": {"document_id": document_id, "version": 1},
            "body_paragraphs": 2,
            "body_tables": 1,
        },
    }
    assert vault.versions(document_id) == [2, 1]
    assert vault.get(document_id, 1)[2] == first
    assert vault.get(document_id, 2)[2] == second


def test_invalid_packages_and_missing_revision_fail_closed(tmp_path, monkeypatch):
    vault = Vault(tmp_path, os.urandom(32))
    valid_id, _ = vault.put(None, 0, "test.docx", docx_with_paragraphs("a"))
    assert inspect(vault, tmp_path, valid_id, 2).state is State.UNCERTAIN
    invalid_id, _ = vault.put(None, 0, "test.docx", b"synthetic invalid DOCX")
    assert inspect(vault, tmp_path, invalid_id, 1).state is State.UNCERTAIN

    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("data", b"two bytes and more")
    oversized_id, _ = vault.put(None, 0, "test.docx", output.getvalue())
    monkeypatch.setattr("worker.docx_adapter.MAX_UNCOMPRESSED_BYTES", 2)
    assert inspect(vault, tmp_path, oversized_id, 1).state is State.UNCERTAIN


@pytest.mark.skipif(
    not os.environ.get("NOTARAI_V2_TEST_SOFFICE"), reason="requires a trusted LibreOffice Writer executable"
)
def test_libreoffice_writer_generated_docx(tmp_path):
    source = tmp_path / "synthetic.txt"
    source.write_text("Synthetic paragraph one\nSynthetic paragraph two", encoding="utf-8")
    subprocess.run(
        [
            os.environ["NOTARAI_V2_TEST_SOFFICE"],
            f"-env:UserInstallation={(tmp_path / 'office-profile').as_uri()}",
            "--headless", "--convert-to", "docx:Office Open XML Text",
            "--outdir", str(tmp_path), str(source),
        ],
        capture_output=True, check=True, timeout=45,
    )
    package = (tmp_path / "synthetic.docx").read_bytes()
    vault = Vault(tmp_path, os.urandom(32))
    document_id, _ = vault.put(None, 0, "synthetic.docx", package)
    result = inspect(vault, tmp_path, document_id, 1)
    assert result.state is State.VERIFIED
    assert result.data.body_paragraphs == 2
    assert result.data.body_tables == 0
