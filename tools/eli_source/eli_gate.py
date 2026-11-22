"""Conservative read-only source gate for official Sejm ELI documents.

This gate decides which official representation is available and can download
its bytes with strict size and origin limits. It neither reconstructs the law
on a given date nor certifies an act's applicability or a legal citation.

No documents, credentials or client inputs are sent to third-party services.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any, Callable
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

OFFICIAL_HOST = "api.sejm.gov.pl"
MAX_METADATA_BYTES = 256 * 1024
MAX_HTML_BYTES = 8 * 1024 * 1024
MAX_PDF_BYTES = 24 * 1024 * 1024
TIMEOUT_SECONDS = 8.0


class _NoRedirects(HTTPRedirectHandler):
    """Never contact a redirected endpoint, even before validating final URL."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _open_no_redirect(request: Request, timeout: float):
    return build_opener(_NoRedirects()).open(request, timeout=timeout)


class EliSourceError(ValueError):
    """A source cannot safely be used; messages contain no fetched content."""


@dataclass(frozen=True)
class EliAct:
    publisher: str
    year: int
    position: int

    def __post_init__(self) -> None:
        if self.publisher not in ("DU", "MP"):
            raise EliSourceError("unsupported journal")
        if type(self.year) is not int or not 1918 <= self.year <= 2100:
            raise EliSourceError("invalid journal year")
        if type(self.position) is not int or not 1 <= self.position <= 100000:
            raise EliSourceError("invalid journal position")

    @classmethod
    def parse(cls, identifier: str) -> "EliAct":
        if not isinstance(identifier, str):
            raise EliSourceError("ELI identifier must be a string")
        match = re.fullmatch(r"(DU|MP)/(19\d\d|20\d\d|2100)/([1-9]\d{0,5})", identifier)
        if match is None:
            raise EliSourceError("invalid canonical ELI identifier")
        return cls(match[1], int(match[2]), int(match[3]))

    @property
    def eli(self) -> str:
        return f"{self.publisher}/{self.year}/{self.position}"

    @property
    def base(self) -> str:
        return f"https://{OFFICIAL_HOST}/eli/acts/{self.eli}"


@dataclass(frozen=True)
class EliSourceDecision:
    eli: str
    status: str
    official_metadata_url: str
    official_text_url: str | None
    official_pdf_url: str | None
    metadata_sha256: str
    citation_verified: bool = False

    def __post_init__(self) -> None:
        if self.citation_verified:
            raise EliSourceError("metadata cannot verify a citation")

    def as_dict(self) -> dict[str, str | bool | None]:
        return {
            "eli": self.eli,
            "status": self.status,
            "official_metadata_url": self.official_metadata_url,
            "official_text_url": self.official_text_url,
            "official_pdf_url": self.official_pdf_url,
            "metadata_sha256": self.metadata_sha256,
            "citation_verified": False,
            "legal_validity_on_selected_date_verified": False,
        }


@dataclass(frozen=True)
class OfficialDocument:
    source_url: str
    format: str
    data: bytes
    sha256_digest: str

    @property
    def size(self) -> int:
        return len(self.data)

    def receipt(self) -> dict[str, str | int | bool]:
        """No document bytes or legal excerpts are emitted to logs."""
        return {
            "source_url": self.source_url,
            "format": self.format,
            "sha256": self.sha256_digest,
            "bytes": self.size,
            "legal_validity_on_selected_date_verified": False,
        }


def decide_source(act: EliAct, metadata: dict[str, Any]) -> EliSourceDecision:
    """Fail closed on missing/inconsistent metadata; never invent legal text."""
    if not isinstance(metadata, dict):
        raise EliSourceError("metadata is not an object")
    if metadata.get("ELI") != act.eli:
        raise EliSourceError("ELI identifier mismatch")
    if metadata.get("publisher") != act.publisher:
        raise EliSourceError("publisher mismatch")
    if type(metadata.get("year")) is not int or metadata["year"] != act.year:
        raise EliSourceError("year mismatch")
    if type(metadata.get("pos")) is not int or metadata["pos"] != act.position:
        raise EliSourceError("position mismatch")
    html, pdf = metadata.get("textHTML"), metadata.get("textPDF")
    if type(html) is not bool or type(pdf) is not bool:
        raise EliSourceError("source-format flags are missing or invalid")
    fingerprint = sha256(json.dumps(metadata, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()
    if html:
        return EliSourceDecision(
            eli=act.eli, status="HTML_AVAILABLE", official_metadata_url=act.base,
            official_text_url=act.base + "/text.html",
            official_pdf_url=act.base + "/text.pdf" if pdf else None,
            metadata_sha256=fingerprint,
        )
    if pdf:
        return EliSourceDecision(
            eli=act.eli, status="PDF_EXTRACTION_REQUIRED", official_metadata_url=act.base,
            official_text_url=None, official_pdf_url=act.base + "/text.pdf",
            metadata_sha256=fingerprint,
        )
    return EliSourceDecision(
        eli=act.eli, status="UNAVAILABLE", official_metadata_url=act.base,
        official_text_url=None, official_pdf_url=None, metadata_sha256=fingerprint,
    )


def _fetch_official(url: str, max_bytes: int, allowed_mime: tuple[str, ...],
                    opener: Callable[..., Any] = _open_no_redirect,
                    timeout: float = TIMEOUT_SECONDS) -> bytes:
    """Bounded, official-host-only transport; injectable for network-free tests."""
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.hostname != OFFICIAL_HOST or
            parsed.port not in (None, 443) or parsed.username or parsed.password or
            parsed.query or parsed.fragment or not parsed.path.startswith("/eli/acts/")):
        raise EliSourceError("source URL is not an official ELI endpoint")
    if not (0 < timeout <= 15):
        raise EliSourceError("invalid timeout")
    req = Request(url, headers={"Accept": ", ".join(allowed_mime),
                                "Accept-Encoding": "identity",
                                "User-Agent": "NotarAI-ELI-Research/1.0"})
    try:
        with opener(req, timeout=timeout) as response:
            # Even same-host redirects are disallowed: receipts must identify
            # the exact source read, not a redirected or substituted resource.
            if response.geturl() != url:
                raise EliSourceError("official source redirected")
            mime = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if mime not in allowed_mime:
                raise EliSourceError("unexpected source content type")
            body = response.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise EliSourceError("official source exceeds size limit")
        if not body:
            raise EliSourceError("official source returned empty body")
        return body
    except EliSourceError:
        raise
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise EliSourceError("official ELI source fetch failed") from exc


def fetch_official_metadata(act: EliAct, opener: Callable[..., Any] = _open_no_redirect,
                            timeout: float = TIMEOUT_SECONDS) -> dict[str, Any]:
    body = _fetch_official(act.base, MAX_METADATA_BYTES, ("application/json",), opener, timeout)
    try:
        result = json.loads(body.decode("utf-8-sig"))
    except (UnicodeError, ValueError) as exc:
        raise EliSourceError("official metadata is not valid JSON") from exc
    if not isinstance(result, dict):
        raise EliSourceError("official metadata is not an object")
    # Validate the identity before returning metadata to any caller.
    decide_source(act, result)
    return result


def get_source_decision(act: EliAct, opener: Callable[..., Any] = _open_no_redirect) -> EliSourceDecision:
    return decide_source(act, fetch_official_metadata(act, opener=opener))


def fetch_document(act: EliAct, decision: EliSourceDecision, fmt: str,
                   opener: Callable[..., Any] = _open_no_redirect) -> OfficialDocument:
    """Download an available representation. Does NOT parse or validate law."""
    if decision.eli != act.eli or decision.official_metadata_url != act.base:
        raise EliSourceError("decision does not match requested act")
    if fmt == "html":
        url, size, mimes = decision.official_text_url, MAX_HTML_BYTES, ("text/html", "application/xhtml+xml")
    elif fmt == "pdf":
        url, size, mimes = decision.official_pdf_url, MAX_PDF_BYTES, ("application/pdf", "application/octet-stream")
    else:
        raise EliSourceError("unsupported document format")
    if not url or url != act.base + ("/text.html" if fmt == "html" else "/text.pdf"):
        raise EliSourceError("requested format not declared by official metadata")
    content = _fetch_official(url, size, mimes, opener)
    if fmt == "pdf" and b"%PDF-" not in content[:1024]:
        raise EliSourceError("official PDF signature missing")
    if fmt == "html":
        try:
            sample = content[:1024].decode("utf-8-sig")
        except UnicodeError as exc:
            raise EliSourceError("official HTML encoding invalid") from exc
        if not sample.strip() or sample.lstrip().startswith("%PDF-"):
            raise EliSourceError("official HTML is not HTML text")
    return OfficialDocument(source_url=url, format=fmt, data=content,
                            sha256_digest=sha256(content).hexdigest())