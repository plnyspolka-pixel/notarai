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

    def start(self, request: InspectDocx) -> int:
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
    request: InspectDocx
    expires: float


class ConnectSession:
    """Trusted local operator context, with a fixed app grant and one pending approval."""

    def __init__(
        self,
        adapters: Iterable[DocxInspector],
        grants: Mapping[Application, frozenset[str]],
        receipts: LocalReceipts,
    ):
        self._adapters = tuple(adapters)
        self._grants = {app: frozenset(operations) for app, operations in grants.items()}
        self._receipts = receipts
        self._approval: Approval | None = None
        self._lock = Lock()

    def approve(self, request: InspectDocx) -> str:
        if request.operation not in self._grants.get(request.app, ()):
            raise PermissionError("operation denied by local app policy")
        with self._lock:
            token = secrets.token_urlsafe(32)
            self._approval = Approval(token, request, monotonic() + 60)
            return token

    def execute(self, request: InspectDocx, approval_token: str) -> Result:
        with self._lock:
            approval = self._approval
            if (
                approval is None or approval.request != request or monotonic() >= approval.expires
                or not secrets.compare_digest(approval.token.encode(), approval_token.encode())
            ):
                raise PermissionError("approval is invalid or expired")
            self._approval = None

        for adapter in self._adapters:
            if adapter.app != request.app:
                continue
            try:
                if not adapter.supports(request.operation):
                    continue
            except Exception:
                continue

            receipt_id = self._receipts.start(request)
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
