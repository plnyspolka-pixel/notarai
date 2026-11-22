"""Offline triage of EU DSS SimpleReport XML; NEVER a signature validator.

Input must be a report produced by a separately authenticated/controlled DSS
service, bound to the relevant signed document by the calling application.
An XML report can be forged. This code checks its shape and consistency only.
No outside network, no certificate trust or QES legal assessment.

Reference: esig/dss, SimpleReport.xsd, and European Commission DSS documentation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import re
import xml.etree.ElementTree as ET

NAMESPACE = "http://dss.esig.europa.eu/validation/simple-report"
Q = "{" + NAMESPACE + "}"
MAX_REPORT_BYTES = 2 * 1024 * 1024
MAX_ELEMENTS = 10000
MAX_DEPTH = 40
MAX_SIGNERS = 128
INDICATIONS = frozenset({"TOTAL_PASSED", "TOTAL_FAILED", "INDETERMINATE"})
QUALIFICATIONS = frozenset({
    "QESig", "QESeal", "Unknown-QC-QSCD", "AdESig-QC", "AdESeal-QC",
    "Unknown-QC", "AdESig", "AdESeal", "Unknown", "Indeterminate QESig",
    "Indeterminate QESeal", "Indeterminate Unknown-QC-QSCD",
    "Indeterminate AdESig-QC", "Indeterminate AdESeal-QC",
    "Indeterminate Unknown-QC", "Indeterminate AdESig",
    "Indeterminate AdESeal", "Indeterminate Unknown",
    "Not AdES but QC with QSCD", "Not AdES but QC", "Not AdES", "N/A",
})
SCOPE_TYPES = frozenset({"FULL", "PARTIAL", "DIGEST", "ARCHIVED", "COUNTER_SIGNATURE", "ATTESTATION_SIGNATURE", "KEY_BINDING_SIGNATURE", "SIGNATURE"})
HASH_RE = re.compile(r"[a-f0-9]{64}\Z")


class InvalidReport(ValueError):
    """Malformed, inconsistent or oversized XML; no content echoed to caller."""


@dataclass(frozen=True)
class SignatureSummary:
    opaque_id: str
    indication: str
    qualification: str
    scope: str
    is_countersignature: bool
    qes_candidate: bool


@dataclass(frozen=True)
class ReportSummary:
    report_sha256: str
    document_sha256: str
    validation_time: str | None
    declared_signatures: int
    declared_valid_signatures: int
    signatures: tuple[SignatureSummary, ...]
    status: str
    manual_review_required: bool = True
    qualified_signature_confirmed: bool = False
    production_approved: bool = False
    disclaimer: str = (
        "XML consistency check only. Does not verify signatures, trust lists, "
        "qualified status, report authenticity or legal effects."
    )

    def to_dict(self) -> dict:
        data = asdict(self)
        data["signatures"] = [asdict(x) for x in self.signatures]
        return data


def _single(parent: ET.Element, name: str, required: bool = False) -> ET.Element | None:
    matches = parent.findall(Q + name)
    if len(matches) > 1 or (required and not matches):
        raise InvalidReport("missing or duplicate report field")
    return matches[0] if matches else None


def _text(parent: ET.Element, name: str, required: bool = False) -> str | None:
    node = _single(parent, name, required)
    if node is None:
        return None
    value = (node.text or "").strip()
    if required and not value:
        raise InvalidReport("empty mandatory report field")
    return value or None


def _number(parent: ET.Element, name: str) -> int:
    raw = _text(parent, name, True)
    if raw is None or not re.fullmatch(r"\d{1,5}", raw):
        raise InvalidReport("invalid signature count")
    result = int(raw)
    if result > MAX_SIGNERS:
        raise InvalidReport("too many signatures")
    return result


def _datetime(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        # DSS specifies xs:dateTime; timezone, if present, must be valid.
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError) as exc:
        raise InvalidReport("invalid validation timestamp") from exc
    if parsed.year < 2000:
        raise InvalidReport("invalid validation timestamp")
    return value


def _check_xml_shape(root: ET.Element) -> None:
    if root.tag != Q + "SimpleReport":
        raise InvalidReport("not a DSS SimpleReport")
    stack = [(root, 0)]
    count = 0
    while stack:
        node, depth = stack.pop()
        count += 1
        if count > MAX_ELEMENTS or depth > MAX_DEPTH:
            raise InvalidReport("XML complexity limit exceeded")
        if not isinstance(node.tag, str) or not node.tag.startswith(Q):
            raise InvalidReport("unexpected XML namespace")
        stack.extend((child, depth + 1) for child in node)


def evaluate_report(xml: bytes, signed_document_sha256: str) -> ReportSummary:
    """Validate report structure and triage findings, not signature authenticity.

    Never use this result to assert legal validity or authorize execution.
    The caller MUST authenticate the DSS source and independently bind the
    report to the supplied SHA256 of the signed document.
    """
    if not isinstance(xml, bytes) or len(xml) > MAX_REPORT_BYTES or not xml.strip():
        raise InvalidReport("XML input missing or oversized")
    if not isinstance(signed_document_sha256, str) or not HASH_RE.fullmatch(signed_document_sha256):
        raise InvalidReport("invalid document SHA256")
    if re.search(rb"<!\s*(?:DOCTYPE|ENTITY)\b", xml, flags=re.IGNORECASE):
        raise InvalidReport("DTD and entities forbidden")
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise InvalidReport("malformed XML") from exc
    _check_xml_shape(root)
    _single(root, "ValidationPolicy", required=True)
    declared = _number(root, "SignaturesCount")
    valid_declared = _number(root, "ValidSignaturesCount")
    if declared == 0 or valid_declared > declared:
        raise InvalidReport("invalid signature counts")
    sig_nodes = root.findall(Q + "Signature")
    if len(sig_nodes) != declared:
        raise InvalidReport("signature count does not match elements")
    ids: set[str] = set()
    signed_summaries: list[SignatureSummary] = []
    passed = 0
    for sig in sig_nodes:
        ident = sig.get("Id")
        if not ident or len(ident) > 512 or ident in ids:
            raise InvalidReport("missing or duplicate signature ID")
        ids.add(ident)
        if not sig.get("SignatureFormat"):
            raise InvalidReport("signature format missing")
        indication = _text(sig, "Indication", True)
        if indication not in INDICATIONS:
            raise InvalidReport("unknown indication")
        if indication == "TOTAL_PASSED":
            passed += 1
        level = _text(sig, "SignatureLevel") or "N/A"
        if level not in QUALIFICATIONS:
            raise InvalidReport("unknown signature qualification")
        scopes = sig.findall(Q + "SignatureScope")
        scope_names = {s.get("scope", "") for s in scopes}
        if not scope_names:
            scope = "UNSPECIFIED"
        elif any(s not in SCOPE_TYPES for s in scope_names):
            raise InvalidReport("unknown signature scope")
        elif scope_names == {"FULL"}:
            scope = "FULL"
        else:
            scope = "MIXED_OR_NOT_FULL"
        countersig_raw = sig.get("CounterSignature", "false")
        if countersig_raw not in {"true", "false", "1", "0"}:
            raise InvalidReport("invalid counter-signature attribute")
        countersig = countersig_raw in {"true", "1"}
        signed_summaries.append(SignatureSummary(
            opaque_id=sha256(ident.encode("utf-8")).hexdigest()[:16],
            indication=indication,
            qualification=level,
            scope=scope,
            is_countersignature=countersig,
            qes_candidate=(level == "QESig" and indication == "TOTAL_PASSED"),
        ))
    if passed != valid_declared:
        raise InvalidReport("valid signature count disagrees with indications")
    if any(s.indication == "TOTAL_FAILED" for s in signed_summaries):
        status = "REPORTED_FAILURE"
    elif any(s.indication == "INDETERMINATE" for s in signed_summaries):
        status = "REPORTED_INDETERMINATE"
    elif any(s.scope != "FULL" or s.is_countersignature for s in signed_summaries):
        status = "REVIEW_SCOPE_REQUIRED"
    else:
        status = "REPORTED_PASSED_REVIEW_REQUIRED"
    return ReportSummary(
        report_sha256=sha256(xml).hexdigest(),
        document_sha256=signed_document_sha256,
        validation_time=_datetime(root.get("ValidationTime")),
        declared_signatures=declared,
        declared_valid_signatures=valid_declared,
        signatures=tuple(signed_summaries),
        status=status,
    )


def sha256_regular_file(path: Path, max_bytes: int = 100 * 1024 * 1024) -> str:
    """Hash the input signed file without logging its name or contents."""
    if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes:
        raise InvalidReport("invalid signed file")
    h = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()
