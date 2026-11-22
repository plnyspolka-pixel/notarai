"""Offline tests for the conservative official ELI format and quote gates."""

import json
from io import BytesIO
from hashlib import sha256

import pytest

from tools.eli_source.eli_gate import (
    EliAct, EliSourceError, decide_source, fetch_official_metadata,
    get_source_decision, fetch_document, OfficialDocument, MAX_METADATA_BYTES,
    MAX_HTML_BYTES, MAX_PDF_BYTES,
)
from tools.eli_source.quote_gate import match_literal_quote


def metadata(publisher="DU", year=2026, pos=1243, html=False, pdf=True):
    return {
        "ELI": f"{publisher}/{year}/{pos}", "publisher": publisher,
        "year": year, "pos": pos, "textHTML": html, "textPDF": pdf,
        "title": "Fikcyjny akt na potrzeby testu",
        "status": "obowiązujący",
    }


class FakeResponse:
    def __init__(self, content: bytes, url: str, mime: str):
        self.buffer = BytesIO(content)
        self.url = url
        self.headers = {"Content-Type": mime}

    def geturl(self):
        return self.url

    def read(self, n):
        return self.buffer.read(n)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def fake_open(content: bytes, mime: str, redirect: str | None = None):
    def open_request(request, timeout):
        assert timeout == 8
        return FakeResponse(content, redirect or request.full_url, mime)
    return open_request


def synthetic_official_html():
    return (b'<html><head><title>Not legal text</title></head><body>'
            b'<p>Na podstawie art. 19 ust. 1 ustawy</p>'
            b'<p>o prawie celnym zarzadza sie, co nastepuje.</p>'
            b'<script>Never cite scripts</script></body></html>')


def test_official_reference_and_canonical_parsing():
    act = EliAct.parse("DU/2026/1243")
    assert act == EliAct("DU", 2026, 1243)
    assert act.base == "https://api.sejm.gov.pl/eli/acts/DU/2026/1243"
    assert EliAct.parse("MP/2020/1") == EliAct("MP", 2020, 1)


@pytest.mark.parametrize("ident", ["DU/2026/../1", "DU/2026/0", "DU/2026/01",
                                 "https://example.com", "ZZ/2026/1", "DU/2101/1",
                                 "DU/2026/1?x=1", None, "DU/2026/1#x"])
def test_bad_identifiers_rejected(ident):
    with pytest.raises(EliSourceError):
        EliAct.parse(ident)


@pytest.mark.parametrize("p,y,n", [("XX", 2026, 1), ("DU", 1800, 1),
                                  ("DU", 2026, -2), ("DU", True, 1),
                                  ("DU", 2026, True)])
def test_invalid_field_values(p, y, n):
    with pytest.raises(EliSourceError):
        EliAct(p, y, n)


def test_pdf_only_requires_external_extraction_and_never_approves_citation():
    result = decide_source(EliAct("DU", 2026, 1243), metadata())
    assert result.status == "PDF_EXTRACTION_REQUIRED"
    assert result.official_text_url is None
    assert result.official_pdf_url.endswith("/DU/2026/1243/text.pdf")
    assert result.citation_verified is False
    assert result.as_dict()["legal_validity_on_selected_date_verified"] is False


def test_html_declared_but_citation_unverified():
    result = decide_source(EliAct("DU", 2020, 1), metadata(year=2020, pos=1, html=True))
    assert result.status == "HTML_AVAILABLE"
    assert result.official_text_url.endswith("/DU/2020/1/text.html")
    assert result.citation_verified is False


def test_no_formats_returns_unavailable():
    result = decide_source(EliAct("MP", 2025, 1), metadata("MP", 2025, 1, False, False))
    assert result.status == "UNAVAILABLE" and result.official_pdf_url is None


@pytest.mark.parametrize("field,value", [
    ("ELI", "DU/2026/99"), ("publisher", "MP"), ("pos", 123),
    ("year", 2020), ("textHTML", "false"), ("textPDF", None),
    ("year", True), ("pos", False),
])
def test_mismatch_and_malformed_flags_fail_closed(field, value):
    item = metadata()
    item[field] = value
    with pytest.raises(EliSourceError):
        decide_source(EliAct("DU", 2026, 1243), item)


def test_official_metadata_endpoint_and_size_and_header():
    act = EliAct.parse("DU/2026/1243")
    raw = json.dumps(metadata()).encode()
    def opener(request, timeout):
        assert request.full_url == act.base
        assert request.headers["Accept"] == "application/json"
        return FakeResponse(raw, act.base, "application/json; charset=UTF-8")
    assert fetch_official_metadata(act, opener)["textHTML"] is False
    assert get_source_decision(act, opener).status == "PDF_EXTRACTION_REQUIRED"


def test_metadata_cannot_be_redirected():
    op = fake_open(json.dumps(metadata()).encode(), "application/json",
                   redirect="https://fake.invalid/eli/acts/DU/2026/1243")
    with pytest.raises(EliSourceError):
        fetch_official_metadata(EliAct("DU", 2026, 1243), op)


def test_metadata_to_another_page_on_same_host_cannot_be_redirected():
    op = fake_open(json.dumps(metadata()).encode(), "application/json",
                   redirect="https://api.sejm.gov.pl/eli/acts/DU/2026/1244")
    with pytest.raises(EliSourceError):
        fetch_official_metadata(EliAct("DU", 2026, 1243), op)


def test_bad_mime_rejected():
    op = fake_open(json.dumps(metadata()).encode(), "text/html")
    with pytest.raises(EliSourceError):
        fetch_official_metadata(EliAct("DU", 2026, 1243), op)


def test_metadata_size_bound():
    op = fake_open(b"x" * (MAX_METADATA_BYTES + 1), "application/json")
    with pytest.raises(EliSourceError):
        fetch_official_metadata(EliAct("DU", 2026, 1243), op)


def test_json_error_does_not_echo_fetched_content():
    with pytest.raises(EliSourceError) as exc:
        fetch_official_metadata(EliAct("DU", 2026, 1243), fake_open(b"SECRET123", "application/json"))
    assert "SECRET123" not in str(exc.value)


def test_document_format_undeclared_blocks_network():
    act = EliAct.parse("DU/2026/1243")
    decision = decide_source(act, metadata())
    def should_not_call(*args, **kwargs):
        raise AssertionError("unexpected external request")
    with pytest.raises(EliSourceError):
        fetch_document(act, decision, "html", should_not_call)


def test_fetch_official_pdf_receipt_without_extracting_text():
    act = EliAct.parse("DU/2026/1243")
    decision = decide_source(act, metadata())
    sample = b"%PDF-1.7\n1 0 obj\n<</Type/Catalog>>\nendobj\n%%EOF"
    document = fetch_document(act, decision, "pdf", fake_open(sample, "application/pdf"))
    assert document.format == "pdf" and document.data == sample
    assert document.receipt()["sha256"] == sha256(sample).hexdigest()
    assert document.receipt()["legal_validity_on_selected_date_verified"] is False
    assert "data" not in document.receipt()


def test_pdf_wrong_magic_or_oversize_rejected():
    act = EliAct.parse("DU/2026/1243")
    decision = decide_source(act, metadata())
    with pytest.raises(EliSourceError):
        fetch_document(act, decision, "pdf", fake_open(b"<html>not PDF</html>", "application/pdf"))
    with pytest.raises(EliSourceError):
        fetch_document(act, decision, "pdf", fake_open(b"%PDF-" + b"x" * MAX_PDF_BYTES, "application/pdf"))


def test_declared_html_fetch_with_exact_source_url():
    act = EliAct.parse("DU/2020/1")
    decision = decide_source(act, metadata(year=2020, pos=1, html=True, pdf=True))
    sample = synthetic_official_html()
    document = fetch_document(act, decision, "html", fake_open(sample, "text/html"))
    assert document.source_url.endswith("/DU/2020/1/text.html")
    assert document.sha256_digest == sha256(sample).hexdigest()
    assert document.receipt()["format"] == "html"


def test_html_content_size_and_type_rejected():
    act = EliAct.parse("DU/2020/1")
    d = decide_source(act, metadata(year=2020, pos=1, html=True, pdf=True))
    with pytest.raises(EliSourceError):
        fetch_document(act, d, "html", fake_open(b"x" * (MAX_HTML_BYTES + 1), "text/html"))
    with pytest.raises(EliSourceError):
        fetch_document(act, d, "html", fake_open(b"%PDF-1.7", "text/html"))


def test_no_cross_act_decision_confusion():
    act1 = EliAct.parse("DU/2020/1")
    act2 = EliAct.parse("DU/2020/2")
    d = decide_source(act1, metadata(year=2020, pos=1, html=True))
    with pytest.raises(EliSourceError):
        fetch_document(act2, d, "html", fake_open(synthetic_official_html(), "text/html"))


def test_matching_literal_html_quote_but_not_applicability():
    act = EliAct.parse("DU/2020/1")
    d = decide_source(act, metadata(year=2020, pos=1, html=True))
    doc = fetch_document(act, d, "html", fake_open(synthetic_official_html(), "text/html"))
    evidence = match_literal_quote(doc, "Na podstawie art. 19 ust. 1 ustawy")
    assert evidence.matched_literal_in_published_document is True
    assert evidence.status == "FOUND_IN_OFFICIAL_HTML"
    assert evidence.as_dict()["legal_validity_on_selected_date_verified"] is False
    assert evidence.as_dict()["requires_legal_review"] is True
    assert evidence.as_dict().get("quote") is None


def test_not_found_quote_does_not_claim_verification():
    act = EliAct.parse("DU/2020/1")
    d = decide_source(act, metadata(year=2020, pos=1, html=True))
    doc = fetch_document(act, d, "html", fake_open(synthetic_official_html(), "text/html"))
    evidence = match_literal_quote(doc, "Przepis wymaga złożenia przed notariuszem")
    assert evidence.status == "NOT_FOUND_IN_OFFICIAL_HTML"
    assert evidence.matched_literal_in_published_document is False


def test_script_and_head_are_not_legal_citations():
    act = EliAct.parse("DU/2020/1")
    d = decide_source(act, metadata(year=2020, pos=1, html=True))
    doc = fetch_document(act, d, "html", fake_open(synthetic_official_html(), "text/html"))
    assert not match_literal_quote(doc, "Never cite scripts please").matched_literal_in_published_document
    assert not match_literal_quote(doc, "Not legal text here").matched_literal_in_published_document


def test_pdf_cannot_be_fed_as_html_for_quote_validation():
    data = b"%PDF-1.4\n%%EOF"
    doc = OfficialDocument("https://api.sejm.gov.pl/eli/acts/DU/2026/1243/text.pdf",
                           "pdf", data, sha256(data).hexdigest())
    with pytest.raises(EliSourceError):
        match_literal_quote(doc, "fikcyjny przepis z pliku PDF")


def test_empty_or_oversize_quote_rejected():
    sample = synthetic_official_html()
    doc = OfficialDocument("https://api.sejm.gov.pl/eli/acts/DU/2020/1/text.html",
                           "html", sample, sha256(sample).hexdigest())
    for text in ("", "  ", "a" * 1501, "abc\x00" + "some long text"):
        with pytest.raises(EliSourceError):
            match_literal_quote(doc, text)


def test_metadata_checksum_is_deterministic():
    act = EliAct.parse("DU/2026/1243")
    obj = metadata()
    d1 = decide_source(act, obj)
    d2 = decide_source(act, dict(reversed(list(obj.items()))))
    assert len(d1.metadata_sha256) == 64
    assert d1.metadata_sha256 == d2.metadata_sha256


def test_cli_metadata_only_and_fail_closed_on_pdf_only_quote(tmp_path, capsys):
    from tools.eli_source.__main__ import main
    raw = json.dumps(metadata()).encode()
    assert main(["DU/2026/1243"], opener=fake_open(raw, "application/json")) == 0
    out = capsys.readouterr().out
    assert '"status": "PDF_EXTRACTION_REQUIRED"' in out
    assert '"citation_verified": false' in out
    quote_path = tmp_path / "quote.txt"
    quote_path.write_text("Przepis nie został sprawdzony", encoding="utf-8")
    assert main(["DU/2026/1243", "--quote-file", str(quote_path)],
                opener=fake_open(raw, "application/json")) == 2
    assert "requires --fetch-format html" in capsys.readouterr().err


def test_cli_html_quote_match_and_no_quote_echo(tmp_path, capsys):
    from tools.eli_source.__main__ import main
    raw = json.dumps(metadata(year=2020, pos=1, html=True)).encode()
    html = synthetic_official_html()
    def opener(request, timeout):
        if request.full_url.endswith("text.html"):
            return FakeResponse(html, request.full_url, "text/html")
        return FakeResponse(raw, request.full_url, "application/json")
    q = tmp_path / "quote.txt"
    q.write_text("Na podstawie art. 19 ust. 1 ustawy", encoding="utf-8")
    assert main(["DU/2020/1", "--fetch-format", "html", "--quote-file", str(q)], opener=opener) == 0
    out = capsys.readouterr().out
    assert '"matched_literal_in_published_document": true' in out
    assert "Na podstawie art. 19 ust." not in out
    assert '"legal_validity_on_selected_date_verified": false' in out


def test_cli_quote_not_found_returns_nonzero(tmp_path, capsys):
    from tools.eli_source.__main__ import main
    raw = json.dumps(metadata(year=2020, pos=1, html=True)).encode()
    def opener(request, timeout):
        if request.full_url.endswith("text.html"):
            return FakeResponse(synthetic_official_html(), request.full_url, "text/html")
        return FakeResponse(raw, request.full_url, "application/json")
    q = tmp_path / "quote.txt"
    q.write_text("Nie ma takiego zdania w tym akcie.", encoding="utf-8")
    assert main(["DU/2020/1", "--fetch-format", "html", "--quote-file", str(q)], opener=opener) == 2
    out = capsys.readouterr().out
    assert '"matched_literal_in_published_document": false' in out