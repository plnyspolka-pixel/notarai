"""SEC-07 negative trial taxonomy, using only fake metadata (never hardware PASS)."""
import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from confidential.nitro_denial_matrix import (
    CASES, EARLY_CASES, KMS_CASES, SCHEMA, DenialEvidenceRejected,
    incomplete_audit_result, inspect_early_denial_receipt,
    inspect_kms_denial, kms_receipt_sha256, validate_matrix,
)


def sample():
    now = datetime.now(timezone.utc).replace(microsecond=0)
    fmt = lambda v: v.strftime("%Y-%m-%dT%H:%M:%SZ")
    op, custody, tenant = "111122223333", "444455556666", "pilot01"
    key = (
        f"arn:aws:kms:eu-central-1:{custody}:key/"
        "11111111-2222-3333-4444-555555555555"
    )
    trials = {}
    for n, case in enumerate(CASES, start=1):
        trials[case] = {
            "boundary": "kms" if case in KMS_CASES else EARLY_CASES[case],
            "event_id": str(UUID(int=n)) if case in KMS_CASES else None,
            "receipt_sha256": "a" * 64,
            "observed_at": fmt(now - timedelta(seconds=30)),
        }
    matrix = {
        "schema": SCHEMA, "region": "eu-central-1",
        "tenant": tenant, "workload_account": op,
        "custody_account": custody, "approved_kms_key_arn": key,
        "expected_pcr17": "b" * 96, "image_sha256": "c" * 64,
        "job_id": "d" * 32,
        "started_at": fmt(now - timedelta(minutes=2)),
        "ended_at": fmt(now), "trials": trials,
    }
    role = f"arn:aws:iam::{op}:role/notarai-confidential-{tenant}"
    other = f"arn:aws:iam::{op}:role/notarai-confidential-pilot02"
    events = {}
    for case in KMS_CASES:
        event = {
            "eventID": trials[case]["event_id"],
            "requestID": str(UUID(int=100 + list(CASES).index(case))),
            "eventName": "Decrypt", "eventSource": "kms.amazonaws.com",
            "awsRegion": "eu-central-1", "responseElements": None,
            "eventTime": trials[case]["observed_at"],
            "requestParameters": {"keyId": key},
            "userIdentity": {"accountId": op, "sessionContext": {
                "sessionIssuer": {"arn": other if case == "cross_tenant_or_role" else role},
            }},
            "errorCode": "AccessDeniedException",
        }
        if case == "wrong_pcr17":
            event["additionalEventData"] = {"recipient": {
                "attestationDocumentModuleId": "nitro-fixture-only",
                "attestationDocumentEnclavePCR17": "e" * 96,
            }}
        if case == "wrong_key":
            event["requestParameters"]["keyId"] = (
                f"arn:aws:kms:eu-central-1:{custody}:key/"
                "99999999-2222-3333-4444-555555555555"
            )
            event["errorCode"] = "IncorrectKeyException"
        events[case] = event
        trials[case]["receipt_sha256"] = kms_receipt_sha256(case, event)
    receipts = {}
    for case in EARLY_CASES:
        receipt = {
            "schema": "notarai.confidential.nitro-denial-receipt.v1",
            "case": case, "tenant": tenant, "job_id": "d" * 32,
            "observed_at": trials[case]["observed_at"],
            "boundary": trials[case]["boundary"], "result": "DENIED",
            "image_sha256": "f" * 64 if case == "altered_image" else "c" * 64,
            "run_task_count": 1 if case == "altered_image" else 0,
            "kms_decrypt_count": 0,
            "observation_sha256": "1" * 64,
        }
        trials[case]["receipt_sha256"] = hashlib.sha256(
            json.dumps(receipt, sort_keys=True, ensure_ascii=True,
                       separators=(",", ":")).encode()
        ).hexdigest()
        receipts[case] = receipt
    return matrix, events, receipts


def test_canonical_six_case_boundary_mapping():
    matrix, events, receipts = sample()
    assert len(validate_matrix(matrix)["trials"]) == 6
    assert set(events) == KMS_CASES
    for case, event in events.items():
        assert inspect_kms_denial(case, event, matrix)["precondition_observed"] is True
    for case, receipt in receipts.items():
        assert inspect_early_denial_receipt(
            case, receipt, matrix,
        )["evidence_status"] == "STRUCTURALLY_VALID_ONLY"
    assert incomplete_audit_result()["hardware_attestation_verified"] is False
    assert incomplete_audit_result()["negative_cases_independently_verified"] is False


@pytest.mark.parametrize("case", CASES)
def test_no_missing_six_cases(case):
    matrix, _, _ = sample()
    matrix["trials"].pop(case)
    with pytest.raises(DenialEvidenceRejected):
        validate_matrix(matrix)


@pytest.mark.parametrize("case", tuple(KMS_CASES))
def test_wrong_boundary_cannot_be_called_kms(case):
    matrix, _, _ = sample()
    matrix["trials"][case]["boundary"] = "prelaunch"
    with pytest.raises(DenialEvidenceRejected):
        validate_matrix(matrix)


@pytest.mark.parametrize("case", tuple(EARLY_CASES))
def test_no_fabricated_kms_events_for_early_rejection(case):
    matrix, _, _ = sample()
    matrix["trials"][case]["event_id"] = str(UUID(int=99))
    with pytest.raises(DenialEvidenceRejected):
        validate_matrix(matrix)


@pytest.mark.parametrize("case,modify", [
    ("ordinary_host", lambda e: e.update(additionalEventData={"recipient": {
        "attestationDocumentModuleId": "unapproved-nsm",
    }})),
    ("ordinary_host", lambda e: e["userIdentity"]["sessionContext"][
        "sessionIssuer"].update(arn="arn:aws:iam::111122223333:role/admin")),
    ("wrong_pcr17", lambda e: e["additionalEventData"]["recipient"].update(
        attestationDocumentEnclavePCR17="b" * 96)),
    ("wrong_pcr17", lambda e: e.pop("additionalEventData")),
    ("cross_tenant_or_role", lambda e: e["userIdentity"]["sessionContext"][
        "sessionIssuer"].update(
            arn="arn:aws:iam::111122223333:role/notarai-confidential-pilot01")),
    ("wrong_key", lambda e: e["requestParameters"].update(
        keyId="arn:aws:kms:eu-central-1:444455556666:key/"
              "11111111-2222-3333-4444-555555555555")),
    ("wrong_key", lambda e: e["requestParameters"].update(
        keyId="arn:aws:kms:eu-central-1:999988887777:key/wrong")),
])
def test_denial_must_match_actual_precondition(case, modify):
    matrix, events, _ = sample()
    modify(events[case])
    with pytest.raises(DenialEvidenceRejected):
        inspect_kms_denial(case, events[case], matrix)


@pytest.mark.parametrize("mutation", [
    lambda r: r.update(kms_decrypt_count=1),
    lambda r: r.update(run_task_count=1),
    lambda r: r.update(image_sha256="f" * 64),
    lambda r: r.update(result="ALLOW"),
    lambda r: r.update(extra="forged"),
])
def test_unsigned_release_receipt_must_prove_early_stop(mutation):
    matrix, _, receipts = sample()
    mutation(receipts["unsigned_release"])
    with pytest.raises(DenialEvidenceRejected):
        inspect_early_denial_receipt("unsigned_release", receipts["unsigned_release"],
                                     matrix)


@pytest.mark.parametrize("mutation", [
    lambda r: r.update(image_sha256="c" * 64),
    lambda r: r.update(kms_decrypt_count=2),
    lambda r: r.update(run_task_count=2),
    lambda r: r.update(observation_sha256="9" * 64),
])
def test_altered_image_requires_distinct_digest_and_matching_receipt(mutation):
    matrix, _, receipts = sample()
    mutation(receipts["altered_image"])
    with pytest.raises(DenialEvidenceRejected):
        inspect_early_denial_receipt("altered_image", receipts["altered_image"],
                                     matrix)


def test_duplicate_cloudtrail_id_is_rejected():
    matrix, _, _ = sample()
    matrix["trials"]["wrong_key"]["event_id"] = (
        matrix["trials"]["wrong_pcr17"]["event_id"]
    )
    with pytest.raises(DenialEvidenceRejected):
        validate_matrix(matrix)


@pytest.mark.parametrize("tamper", [
    lambda m: m.update(region="us-east-1"),
    lambda m: m.update(tenant="actual-client"),
    lambda m: m.update(workload_account=m["custody_account"]),
    lambda m: m.update(expected_pcr17="0" * 96),
    lambda m: m.update(image_sha256="f" * 63),
    lambda m: m.update(extra="raw_aws_credentials"),
])
def test_manifest_fail_closed_on_bad_region_identity_measurements(tamper):
    matrix, _, _ = sample()
    tamper(matrix)
    with pytest.raises(DenialEvidenceRejected):
        validate_matrix(matrix)


def test_binary_readonly_results_cannot_be_mistaken_for_hardware_pass():
    matrix, events, receipts = sample()
    assert validate_matrix(matrix)
    assert all(inspect_kms_denial(case, event, matrix)
               for case, event in events.items())
    assert all(inspect_early_denial_receipt(case, receipt, matrix)
               for case, receipt in receipts.items())
    assert incomplete_audit_result()["status"] == "BLOCKED"



def test_cli_offline_never_invokes_aws(monkeypatch, capsys):
    import sys
    from scripts import audit_nitro_denials as audit
    monkeypatch.setattr(sys, "argv", ["audit_nitro_denials.py", "--check"])
    assert audit.main() == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "BLOCKED"
    assert result["hardware_attestation_verified"] is False


def test_live_readonly_four_kms_trials_and_two_receipts_still_blocked():
    from scripts import audit_nitro_denials as audit
    matrix, events, receipts = sample()
    event_lookup = {
        matrix["trials"][case]["event_id"]: event
        for case, event in events.items()
    }
    calls = []

    class Sts:
        def __init__(self, account):
            self.account = account

        def get_caller_identity(self):
            calls.append("sts:get_caller_identity")
            return {"Account": self.account}

    class Trail:
        def lookup_events(self, **kwargs):
            calls.append("cloudtrail:lookup_events")
            key = kwargs["LookupAttributes"][0]["AttributeValue"]
            return {"Events": [{
                "CloudTrailEvent": json.dumps(event_lookup[key]),
            }]}

    class Session:
        def __init__(self, profile_name, region_name):
            assert region_name == "eu-central-1"
            self.custody = profile_name == "custody"

        def client(self, name):
            if name == "sts":
                return Sts(
                    matrix["custody_account"] if self.custody else
                    matrix["workload_account"]
                )
            if name == "cloudtrail" and not self.custody:
                return Trail()
            raise AssertionError("non-readonly or unexpected AWS client")

    result = audit.audit_live(
        matrix=matrix, operator_profile="operator",
        custody_profile="custody", receipts=receipts,
        session_factory=Session,
    )
    assert result["kms_cases_live_observed"] == 4
    assert result["early_case_metadata_validated"] == 2
    assert result["hardware_attestation_verified"] is False
    assert result["status"] == "BLOCKED"
    assert calls.count("cloudtrail:lookup_events") == 4
    assert set(calls) == {"sts:get_caller_identity", "cloudtrail:lookup_events"}



def test_identical_denial_code_but_different_aws_request_is_not_same_trial():
    matrix, events, _ = sample()
    events["ordinary_host"]["requestID"] = str(UUID(int=999))
    with pytest.raises(DenialEvidenceRejected, match="independently pinned receipt"):
        inspect_kms_denial("ordinary_host", events["ordinary_host"], matrix)


def test_recipient_tampering_changes_signed_receipt_even_if_case_is_valid():
    matrix, events, _ = sample()
    events["wrong_pcr17"]["additionalEventData"]["recipient"][
        "attestationDocumentEnclavePCR17"
    ] = "a" * 96
    with pytest.raises(DenialEvidenceRejected, match="independently pinned receipt"):
        inspect_kms_denial("wrong_pcr17", events["wrong_pcr17"], matrix)
