from dataclasses import dataclass
from sqlite3 import connect
from uuid import uuid4

from pydantic import ValidationError
import pytest

from worker.connect import State
from worker.connect_sdk import (
    Application, ConnectSession, DocxSummary, InspectDocx, LocalReceipts, RevisionTarget,
)

APP = Application(id="org.openxml.wordprocessingml", version="1.2.0")


@dataclass
class Inspector:
    app: Application = APP
    available: bool = True
    correct_target: bool = True
    calls: int = 0

    def supports(self, operation):
        return self.available

    def inspect(self, target):
        self.calls += 1
        if not self.correct_target:
            target = RevisionTarget(document_id=target.document_id, version=target.version + 1)
        return DocxSummary(target=target, body_paragraphs=1, body_tables=0)


@pytest.fixture
def request_v1():
    return InspectDocx(app=APP, target=RevisionTarget(document_id=uuid4(), version=1))


@pytest.mark.parametrize("extra", [{"path": "example.docx"}, {"version": True}, {"version": "1"}])
def test_revision_request_has_strict_scope(request_v1, extra):
    value = request_v1.model_dump()
    value["target"].update(extra)
    with pytest.raises(ValidationError):
        InspectDocx.model_validate(value)


def test_local_grant_and_approval_bind_app_and_revision(tmp_path, request_v1):
    inspector = Inspector()
    receipts = LocalReceipts(tmp_path)
    sdk = ConnectSession([inspector], {APP: frozenset({"inspect_docx"})}, receipts)
    approval = sdk.approve(request_v1)
    later_revision = request_v1.model_copy(
        update={"target": RevisionTarget(document_id=request_v1.target.document_id, version=2)}
    )
    different_app = request_v1.model_copy(
        update={"app": Application(id=APP.id, version="2.0")}
    )
    with pytest.raises(PermissionError):
        sdk.approve(different_app)
    for modified in [later_revision, different_app]:
        with pytest.raises(PermissionError):
            sdk.execute(modified, approval)

    assert sdk.execute(request_v1, approval).state is State.VERIFIED
    with pytest.raises(PermissionError):
        sdk.execute(request_v1, approval)
    assert inspector.calls == 1
    with connect(receipts.path) as db:
        assert db.execute("SELECT application, operation, state FROM receipts").fetchall() == [
            (APP.id, "inspect_docx", "verified")
        ]
    assert str(request_v1.target.document_id).encode() not in receipts.path.read_bytes()


def test_approval_expires(tmp_path, request_v1, monkeypatch):
    monkeypatch.setattr("worker.connect_sdk.monotonic", lambda: 100.0)
    inspector = Inspector()
    sdk = ConnectSession([inspector], {APP: frozenset({"inspect_docx"})}, LocalReceipts(tmp_path))
    approval = sdk.approve(request_v1)
    monkeypatch.setattr("worker.connect_sdk.monotonic", lambda: 160.0)
    with pytest.raises(PermissionError):
        sdk.execute(request_v1, approval)
    assert inspector.calls == 0


def test_bad_postcondition_has_receipt_and_never_falls_through(tmp_path, request_v1):
    unavailable, invalid, fallback = Inspector(available=False), Inspector(correct_target=False), Inspector()
    receipts = LocalReceipts(tmp_path)
    sdk = ConnectSession(
        [unavailable, invalid, fallback], {APP: frozenset({"inspect_docx"})}, receipts
    )
    result = sdk.execute(request_v1, sdk.approve(request_v1))
    assert result.state is State.UNCERTAIN
    assert result.data is None
    assert (unavailable.calls, invalid.calls, fallback.calls) == (0, 1, 0)
    with connect(receipts.path) as db:
        assert db.execute("SELECT state FROM receipts").fetchall() == [("uncertain",)]
