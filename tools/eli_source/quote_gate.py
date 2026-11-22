"""Literal quote matching against a fetched official HTML representation.

Matching a passage in *one published document* is NOT verifying that its
wording was applicable on a chosen date. No legal status or effective date is
inferred from metadata or from an excerpt.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from html.parser import HTMLParser
import re
import unicodedata

from .eli_gate import EliSourceError, OfficialDocument

_BLOCKS = frozenset({"p", "div", "h1", "h2", "h3", "h4", "h5", "li", "tr", "td", "th", "br", "section", "article"})
_SKIP = frozenset({"head", "script", "style", "template", "noscript", "svg"})


class _VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tokens: list[str] = []
        self.skip_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.skip_stack:
            if tag in _SKIP:
                self.skip_stack.append(tag)
            return
        if tag in _SKIP:
            self.skip_stack.append(tag)
        elif tag in _BLOCKS:
            self.tokens.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if self.skip_stack:
            if tag == self.skip_stack[-1]:
                self.skip_stack.pop()
            return
        if tag in _BLOCKS:
            self.tokens.append(" ")

    def handle_data(self, data: str) -> None:
        if not self.skip_stack:
            self.tokens.append(data)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _BLOCKS and not self.skip_stack:
            self.tokens.append(" ")


def _normalized(value: str) -> str:
    # Normalize only formatting: case, non-breaking spaces, Unicode compatibility.
    # Do not remove punctuation or infer substantive equivalence.
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip().casefold()


@dataclass(frozen=True)
class QuoteReceipt:
    source_url: str
    source_sha256: str
    quote_sha256: str
    status: str
    matched_literal_in_published_document: bool
    legal_validity_on_selected_date_verified: bool = False

    def as_dict(self) -> dict[str, str | bool]:
        return {
            "source_url": self.source_url,
            "source_sha256": self.source_sha256,
            "quote_sha256": self.quote_sha256,
            "status": self.status,
            "matched_literal_in_published_document": self.matched_literal_in_published_document,
            "legal_validity_on_selected_date_verified": False,
            "requires_legal_review": True,
        }


def match_literal_quote(document: OfficialDocument, quote: str) -> QuoteReceipt:
    if document.format != "html" or not document.source_url.endswith("/text.html"):
        raise EliSourceError("literal match requires an official HTML document")
    if not isinstance(quote, str) or not 16 <= len(quote) <= 1500 or "\x00" in quote:
        raise EliSourceError("quote must be nonempty, bounded text")
    try:
        html_text = document.data.decode("utf-8-sig")
    except UnicodeError as exc:
        raise EliSourceError("official HTML text cannot be decoded") from exc
    text_parser = _VisibleText()
    try:
        text_parser.feed(html_text)
        text_parser.close()
    except (AssertionError, ValueError) as exc:
        raise EliSourceError("official HTML parser failed") from exc
    normalized_source = _normalized("".join(text_parser.tokens))
    normalized_quote = _normalized(quote)
    # Do not treat a whitespace-only quote or an empty HTML as verified.
    matched = bool(normalized_quote and normalized_quote in normalized_source)
    return QuoteReceipt(
        source_url=document.source_url,
        source_sha256=document.sha256_digest,
        quote_sha256=sha256(normalized_quote.encode("utf-8")).hexdigest(),
        status="FOUND_IN_OFFICIAL_HTML" if matched else "NOT_FOUND_IN_OFFICIAL_HTML",
        matched_literal_in_published_document=matched,
    )