"""Versioned, local Connect operations and execution receipts."""
from collections.abc import Iterable, Mapping
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from time import monotonic, time_ns
from typing import Literal, Protocol
from uuid import UUID
import secrets
import sqlite3

from pydantic import BaseModel, ConfigDict, Field

from .connect import Result, State


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Application(Contract):
    id: str = Field(pattern=r"^[a-z0-9]+(?:[.-][a-z0-9]+)+$", max_length=80)
    version: str = Field(pattern=r"^[a-zA-Z0-9.+-]+$", max_length=40)


class RevisionTarget(Contract):
    document_id: UUID
    version: int = Field(ge=1, le=(1 << 63) - 1)


class InspectDocx(Contract):
    schema_version: Literal["v1"] = "v1"
    operation: Literal["inspect_docx"] = "inspect_docx"
    app: Application
    target: RevisionTarget


class DocxSummary(Contract):
    target: RevisionTarget
    body_paragraphs: int = Field(ge=0)
    body_tables: int = Field(ge=0)


class WriteDocx(Contract):
    """Store reviewed text as a DOCX revision. The approval covers these exact fields,
    including the SHA-256 of the text, so what is written is what was approved."""
    schema_version: Literal["v1"] = "v1"
    operation: Literal["write_docx"] = "write_docx"
    app: Application
    name: str = Field(min_length=6, max_length=255, pattern=r"(?i)^[^\\/\x00-\x1f]+\.docx$")
    case: str | None = Field(default=None, min_length=1, max_length=64, pattern=r"^[\w.-]+$")
    base: RevisionTarget | None = None       # None creates a document; otherwise appends after this revision
    template: RevisionTarget | None = None   # office template taken from the vault
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class WrittenRevision(Contract):
    target: RevisionTarget
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


Request = InspectDocx | WriteDocx


class DocxInspector(Protocol):
    app: Application

    def supports(self, operation: str) -> bool: ...

    def inspect(self, target: RevisionTarget) -> DocxSummary: ...


class LocalReceipts:
    def __init__(self, home: Path):
        self.path = home / "connect-receipts.sqlite3"
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS receipts (
                    id INTEGER PRIMARY KEY,
                    application TEXT NOT NULL,
                    app_version TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    started_ns INTEGER NOT NULL,
                    state TEXT NOT NULL
                )
            """)

    def start(self, request: Request) -> int:
        with closing(sqlite3.connect(self.path)) as db, db:
            return db.execute(
                "INSERT INTO receipts VALUES (NULL, ?, ?, ?, ?, ?, 'started')",
                (request.app.id, request.app.version, request.operation, request.schema_version, time_ns()),
            ).lastrowid

    def finish(self, receipt_id: int, state: State) -> None:
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE receipts SET state=? WHERE id=? AND state='started'", (state.value, receipt_id))


@dataclass(frozen=True)
class Approval:
    token: str
    request: Request
    expires: float


class ConnectSession:
    """Trusted local operator context, with fixed app grants and single-use approvals."""

    MAX_PENDING = 32

    def __init__(
        self,
        adapters: Iterable[DocxInspector],
        grants: Mapping[Application, frozenset[str]],
        receipts: LocalReceipts,
    ):
        self._adapters = tuple(adapters)
        self._grants = {app: frozenset(operations) for app, operations in grants.items()}
        self._receipts = receipts
        self._approvals: dict[str, Approval] = {}
        self._lock = Lock()

    def approve(self, request: Request) -> str:
        if request.operation not in self._grants.get(request.app, ()):
            raise PermissionError("operation denied by local app policy")
        with self._lock:
            now = monotonic()
            self._approvals = {t: a for t, a in self._approvals.items() if a.expires > now}
            if len(self._approvals) >= self.MAX_PENDING:
                raise PermissionError("too many pending approvals")
            token = secrets.token_urlsafe(32)
            self._approvals[token] = Approval(token, request, now + 60)
            return token

    def execute(self, request: Request, approval_token: str, payload: tuple[str, ...] | None = None,
                *, actor: str = "local-admin") -> Result:
        with self._lock:
            approval = self._approvals.get(approval_token) if isinstance(approval_token, str) else None
            if approval is None or approval.request != request or monotonic() >= approval.expires:
                raise PermissionError("approval is invalid or expired")
            del self._approvals[approval_token]
        if isinstance(request, WriteDocx):
            from .docx_writer import digest

            if payload is None or digest(payload) != request.content_sha256:
                raise PermissionError("content differs from what was approved")

        for adapter in self._adapters:
            if adapter.app != request.app:
                continue
            try:
                if not adapter.supports(request.operation):
                    continue
            except Exception:
                continue

            receipt_id = self._receipts.start(request)
            if isinstance(request, WriteDocx):
                result = self._write(adapter, request, payload, actor)
            else:
                result = self._inspect(adapter, request)
            try:
                self._receipts.finish(receipt_id, result.state)
            except sqlite3.Error:
                return Result(State.UNCERTAIN, request.app.id)
            return result
        return Result(State.UNAVAILABLE, "none")

    @staticmethod
    def _inspect(adapter: DocxInspector, request: InspectDocx) -> Result:
        try:
            summary = adapter.inspect(request.target)
            if isinstance(summary, DocxSummary) and summary.target == request.target:
                return Result(State.VERIFIED, request.app.id, summary)
        except Exception:
            pass
        return Result(State.UNCERTAIN, request.app.id)

    @staticmethod
    def _write(adapter, request: WriteDocx, payload, actor) -> Result:
        """One attempt. The stored revision is read back and compared before it counts as done."""
        try:
            written = adapter.write(request, payload, actor)
            expected_version = request.base.version + 1 if request.base else 1
            if (
                isinstance(written, WrittenRevision) and written.target.version == expected_version
                and (request.base is None or written.target.document_id == request.base.document_id)
                and adapter.read_back(written.target) == request.content_sha256 == written.content_sha256
            ):
                return Result(State.VERIFIED, request.app.id, written)
        except Exception:
            pass
        return Result(State.UNCERTAIN, request.app.id)
