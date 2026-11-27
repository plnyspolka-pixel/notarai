"""Local read-only structural inspection of one encrypted-vault DOCX revision."""
from importlib.metadata import version
from io import BytesIO
from uuid import UUID
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

from .connect_sdk import Application, DocxSummary, RevisionTarget, WriteDocx, WrittenRevision
from .vault import MAX_BYTES, Vault

DOCX_APP = Application(id="org.openxml.wordprocessingml", version="1.2.0")
MAX_PARTS = 512
MAX_UNCOMPRESSED_BYTES = 64 * 1024 * 1024


class OpenXmlDocx:
    app = DOCX_APP

    def __init__(self, vault: Vault):
        self._vault = vault

    def supports(self, operation: str) -> bool:
        return (
            operation in {"inspect_docx", "write_docx"}
            and version("python-docx") == self.app.version
            and version("lxml") == "6.1.3"
        )

    def inspect(self, target: RevisionTarget) -> DocxSummary:
        from docx import Document

        revision, name, data = self._vault.get(str(target.document_id), target.version)
        if revision != target.version or not name.lower().endswith(".docx") or len(data) > MAX_BYTES:
            raise ValueError("expected the selected DOCX revision")
        self._check_package(data)
        document = Document(BytesIO(data))
        return DocxSummary(
            target=target,
            body_paragraphs=len(document.paragraphs),
            body_tables=len(document.tables),
        )

    def write(self, request: WriteDocx, paragraphs, actor: str) -> WrittenRevision:
        from .docx_writer import build, digest

        template = None
        if request.template is not None:
            revision, name, template = self._vault.get(
                str(request.template.document_id), request.template.version, actor=actor)
            if not name.lower().endswith(".docx"):
                raise ValueError("template must be a DOCX revision")
            self._check_package(template)
        data = build(paragraphs, template)
        if request.base is None:
            document_id, version = self._vault.put(None, 0, request.name, data, actor=actor, case=request.case)
        else:
            if self._vault.case_of(str(request.base.document_id)) != request.case:
                raise ValueError("base revision belongs to another case")
            document_id, version = self._vault.put(
                str(request.base.document_id), request.base.version, request.name, data, actor=actor)
        return WrittenRevision(
            target=RevisionTarget(document_id=UUID(document_id), version=version),
            content_sha256=digest(paragraphs))

    def read_back(self, target: RevisionTarget) -> str:
        from .docx_writer import text_digest

        _, _, data = self._vault.get(str(target.document_id), target.version, actor="connect-verify")
        return text_digest(data)

    @staticmethod
    def _check_package(data: bytes) -> None:
        with ZipFile(BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_PARTS or sum(entry.file_size for entry in entries) > MAX_UNCOMPRESSED_BYTES:
                raise ValueError("DOCX exceeds archive limits")
            names = set()
            for entry in entries:
                name = entry.filename.casefold()
                parts = name.rstrip("/").split("/")
                if (
                    name in names or any(part in {"", ".", ".."} for part in parts)
                    or "\\" in name or "\x00" in entry.orig_filename
                    or entry.flag_bits & 1 or entry.compress_type not in {ZIP_STORED, ZIP_DEFLATED}
                ):
                    raise ValueError("unsupported DOCX entry")
                names.add(name)
