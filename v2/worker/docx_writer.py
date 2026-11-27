"""Plain reviewed text <-> DOCX. Deterministic, local, no macros or external parts."""
import hashlib
import re
from io import BytesIO

MAX_PARAGRAPHS = 5000
MAX_CHARS = 2_000_000
_FORBIDDEN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
TITLE = "# "


def canonical(paragraphs) -> tuple[str, ...]:
    """Validate and normalise. A line starting with '# ' is a centred heading."""
    if isinstance(paragraphs, str):
        paragraphs = paragraphs.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    result = []
    for line in paragraphs:
        if not isinstance(line, str) or _FORBIDDEN.search(line):
            raise ValueError("unsupported text")
        line = " ".join(line.split())
        if line or (result and result[-1]):   # collapse runs of blank lines
            result.append(line)
    while result and not result[-1]:
        result.pop()
    if not result or len(result) > MAX_PARAGRAPHS or sum(map(len, result)) > MAX_CHARS:
        raise ValueError("text is empty or too long")
    return tuple(result)


def _plain(paragraphs) -> list[str]:
    return [p[len(TITLE):] if p.startswith(TITLE) else p for p in paragraphs if p]


def digest(paragraphs) -> str:
    """Hash of the visible text; the same value is computed again from the stored DOCX."""
    return hashlib.sha256("\n".join(_plain(canonical(paragraphs))).encode()).hexdigest()


def build(paragraphs, template: bytes | None = None) -> bytes:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    paragraphs = canonical(paragraphs)
    document = Document(BytesIO(template)) if template else Document()
    body = document.element.body
    for child in list(body):
        if not child.tag.endswith("}sectPr"):   # keep the template's page setup, headers and styles
            body.remove(child)
    for line in paragraphs:
        if not line:
            continue
        if line.startswith(TITLE):
            paragraph = document.add_paragraph()
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.add_run(line[len(TITLE):]).bold = True
        else:
            document.add_paragraph(line).alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def extract(data: bytes) -> list[str]:
    """Non-empty body paragraphs and table cells, in document order."""
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    from .docx_adapter import OpenXmlDocx

    OpenXmlDocx._check_package(data)
    document = Document(BytesIO(data))
    lines = []

    def walk(container):
        for child in container.iterchildren():
            if child.tag.endswith("}p"):
                text = " ".join(Paragraph(child, document).text.split())
                if text:
                    lines.append(text)
            elif child.tag.endswith("}tbl"):
                for row in Table(child, document).rows:
                    for cell in row.cells:
                        walk(cell._tc)
    walk(document.element.body)
    return lines


def text_digest(data: bytes) -> str:
    return hashlib.sha256("\n".join(extract(data)).encode()).hexdigest()
