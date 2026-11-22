"""All inputs are synthetic and no external validation service is contacted."""

from pathlib import Path
import json
import pytest

from tools.signature_policy.report_gate import (
    InvalidReport, evaluate_report, sha256_regular_file,
)
from tools.signature_policy.__main__ import main

HASH = "0" * 64
NAMESPACE = "http://dss.esig.europa.eu/validation/simple-report"


def xml_report(*, outcomes=("TOTAL_PASSED",), levels=None, scopes=None, valid=None, count=None,
               time="2026-11-22T10:00:00Z", include_policy=True, duplicate_id=False):
    levels = levels if levels is not None else ["QESig"] * len(outcomes)
    scopes = scopes if scopes is not None else ["FULL"] * len(outcomes)
    n = count if count is not None else len(outcomes)
    passed = valid if valid is not None else outcomes.count("TOTAL_PASSED")
    policy = "<ValidationPolicy><PolicyName>synthetic</PolicyName></ValidationPolicy>" if include_policy else ""
    sigs = ""
    for i, (outcome, level, scope) in enumerate(zip(outcomes, levels, scopes)):
        ident = "sig1" if duplicate_id else f"sig{i}"
        qual = f"<SignatureLevel>{level}</SignatureLevel>" if level is not None else ""
        scp = f'<SignatureScope Id="a{i}" scope="{scope}">synthetic</SignatureScope>' if scope is not None else ""
        sigs += (f'<Signature Id="{ident}" SignatureFormat="PAdES-BASELINE-B">'
                 f'<Indication>{outcome}</Indication>'
                 f'<BestSignatureTime>2026-11-22T10:00:00Z</BestSignatureTime>{qual}{scp}</Signature>')
    t = f' ValidationTime="{time}"' if time is not None else ""
    return (f'<SimpleReport xmlns="{NAMESPACE}"{t}>{policy}'
            f'<ValidSignaturesCount>{passed}</ValidSignaturesCount><SignaturesCount>{n}</SignaturesCount>'
            f'{sigs}</SimpleReport>').encode()


def test_passed_qes_candidate_is_not_legal_conclusion():
    result = evaluate_report(xml_report(), HASH)
    assert result.status == "REPORTED_PASSED_REVIEW_REQUIRED"
    assert result.declared_valid_signatures == 1
    assert result.signatures[0].qes_candidate
    assert result.signatures[0].scope == "FULL"
    assert result.qualified_signature_confirmed is False
    assert result.production_approved is False
    assert result.manual_review_required is True


def test_failed_signature_always_blocked():
    result = evaluate_report(xml_report(outcomes=("TOTAL_FAILED",), levels=["QESig"]), HASH)
    assert result.status == "REPORTED_FAILURE"
    assert not result.signatures[0].qes_candidate


def test_indeterminate_signature_not_accepted():
    result = evaluate_report(xml_report(outcomes=("INDETERMINATE",)), HASH)
    assert result.status == "REPORTED_INDETERMINATE"


def test_two_signatures_if_one_fails_then_failed():
    result = evaluate_report(xml_report(outcomes=("TOTAL_PASSED", "TOTAL_FAILED")), HASH)
    assert result.status == "REPORTED_FAILURE"
    assert len(result.signatures) == 2


def test_two_signatures_if_one_unknown_then_indeterminate():
    result = evaluate_report(xml_report(outcomes=("TOTAL_PASSED", "INDETERMINATE")), HASH)
    assert result.status == "REPORTED_INDETERMINATE"


def test_qualified_seal_not_qualified_signature():
    result = evaluate_report(xml_report(levels=["QESeal"]), HASH)
    assert result.signatures[0].qualification == "QESeal"
    assert result.signatures[0].qes_candidate is False


def test_nonqualified_advanced_signature_not_qes():
    result = evaluate_report(xml_report(levels=["AdESig"]), HASH)
    assert not result.signatures[0].qes_candidate


def test_indeterminate_qesig_level_not_qes():
    result = evaluate_report(xml_report(levels=["Indeterminate QESig"]), HASH)
    assert not result.signatures[0].qes_candidate


def test_missing_level_does_not_forge_qualification():
    result = evaluate_report(xml_report(levels=[None]), HASH)
    assert result.signatures[0].qualification == "N/A"
    assert not result.signatures[0].qes_candidate


def test_partial_scope_forces_review():
    result = evaluate_report(xml_report(scopes=["PARTIAL"]), HASH)
    assert result.status == "REVIEW_SCOPE_REQUIRED"


def test_missing_scope_forces_review():
    result = evaluate_report(xml_report(scopes=[None]), HASH)
    assert result.status == "REVIEW_SCOPE_REQUIRED"
    assert result.signatures[0].scope == "UNSPECIFIED"


def test_countersignature_forces_review():
    xml = xml_report().replace(b'SignatureFormat="PAdES-BASELINE-B"', b'SignatureFormat="PAdES-BASELINE-B" CounterSignature="true"')
    assert evaluate_report(xml, HASH).status == "REVIEW_SCOPE_REQUIRED"


def test_reject_entity_and_dtd():
    xml = xml_report()
    with pytest.raises(InvalidReport):
        evaluate_report(b'<!DOCTYPE foo [<!ENTITY x SYSTEM "file:///etc/passwd">]>' + xml, HASH)


def test_reject_wrong_namespace():
    with pytest.raises(InvalidReport):
        evaluate_report(xml_report().replace(NAMESPACE.encode(), b"https://example.invalid/fake"), HASH)


def test_reject_wrong_root():
    with pytest.raises(InvalidReport):
        evaluate_report(xml_report().replace(b"SimpleReport", b"UntrustedReport"), HASH)


def test_reject_missing_policy():
    with pytest.raises(InvalidReport):
        evaluate_report(xml_report(include_policy=False), HASH)


def test_reject_declared_count_mismatch():
    with pytest.raises(InvalidReport):
        evaluate_report(xml_report(count=2), HASH)


def test_reject_declared_valid_count_mismatch():
    with pytest.raises(InvalidReport):
        evaluate_report(xml_report(valid=0), HASH)


def test_reject_invalid_counts():
    with pytest.raises(InvalidReport):
        evaluate_report(xml_report(valid=2), HASH)


def test_reject_duplicate_ids():
    with pytest.raises(InvalidReport):
        evaluate_report(xml_report(outcomes=("TOTAL_PASSED", "TOTAL_PASSED"), duplicate_id=True), HASH)


def test_reject_unknown_indication():
    with pytest.raises(InvalidReport):
        evaluate_report(xml_report(outcomes=("PASSED",), valid=0), HASH)


def test_reject_unknown_qualification():
    with pytest.raises(InvalidReport):
        evaluate_report(xml_report(levels=["NOT_AN_ACTUAL_QES"]), HASH)


def test_reject_unknown_scope():
    with pytest.raises(InvalidReport):
        evaluate_report(xml_report(scopes=["UNKNOWN"]), HASH)


def test_reject_invalid_document_hash():
    with pytest.raises(InvalidReport):
        evaluate_report(xml_report(), "some_bad_hash")


def test_reject_oversized_xml():
    with pytest.raises(InvalidReport):
        evaluate_report(b"a" * (2 * 1024 * 1024 + 1), HASH)


def test_reject_wrong_validation_timestamp():
    with pytest.raises(InvalidReport):
        evaluate_report(xml_report(time="not-a-date"), HASH)


def test_reject_zero_signatures():
    with pytest.raises(InvalidReport):
        evaluate_report(xml_report(outcomes=()), HASH)


def test_never_log_signer_identity():
    xml = xml_report().replace(b'<SignatureLevel>', b'<SignedBy>Test Person</SignedBy><SignatureLevel>')
    obj = evaluate_report(xml, HASH).to_dict()
    assert "Test Person" not in json.dumps(obj)
    assert "sig0" not in json.dumps(obj)
    assert obj["report_sha256"]


def test_cli_is_offline_and_reads_files(tmp_path, capsys):
    path_xml = tmp_path / "report.xml"
    path_doc = tmp_path / "signed.pdf"
    path_xml.write_bytes(xml_report())
    path_doc.write_bytes(b"%PDF-1.7\nfictional bytes\n%%EOF")
    assert main(["--report", str(path_xml), "--document", str(path_doc)]) == 0
    captured = capsys.readouterr().out
    obj = json.loads(captured)
    assert obj["document_sha256"] == sha256_regular_file(path_doc)
    assert obj["qualified_signature_confirmed"] is False
    assert obj["production_approved"] is False


def test_reject_output_overwrite(tmp_path):
    path_xml = tmp_path / "report.xml"
    path_doc = tmp_path / "signed.pdf"
    path_out = tmp_path / "out.json"
    path_xml.write_bytes(xml_report())
    path_doc.write_bytes(b"fictional")
    path_out.write_text("do not overwrite")
    assert main(["--report", str(path_xml), "--document", str(path_doc), "--output", str(path_out)]) == 2
    assert path_out.read_text() == "do not overwrite"


def test_reject_symlink_report(tmp_path):
    path_xml = tmp_path / "report.xml"
    path_doc = tmp_path / "signed.pdf"
    path_link = tmp_path / "link.xml"
    path_xml.write_bytes(xml_report())
    path_doc.write_bytes(b"fictional")
    path_link.symlink_to(path_xml)
    assert main(["--report", str(path_link), "--document", str(path_doc)]) == 2


def test_reject_symlink_signed_file(tmp_path):
    path_doc = tmp_path / "signed.pdf"
    path_doc.write_bytes(b"fictional")
    path_link = tmp_path / "link.pdf"
    path_link.symlink_to(path_doc)
    with pytest.raises(InvalidReport):
        sha256_regular_file(path_link)
