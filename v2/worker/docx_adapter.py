"""Local read-only structural inspection of one encrypted-vault DOCX revision."""
from importlib.metadata import version
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

from .connect_sdk import Application, DocxSummary, RevisionTarget
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
            operation == "inspect_docx"
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
