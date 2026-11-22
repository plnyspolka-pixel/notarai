"""SEC-07 offline security tests. ALL mock evidence remains non-hardware."""
import copy
import json
import sys
import uuid
from datetime import datetime, timezone, timedelta

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from confidential.nitro_hardware_proof import (
    DENIAL_CASES, SCHEMA, ProofRejected, assemble_audit_payload,
    blocked_result, check_cloudtrail_event, evidence_sha256,
    validate_manifest, canonical_bytes,
)
from confidential.attested_kms import AttestedKMSUnwrapper, AttestationRequired
from confidential.release_approval import public_key_fingerprint
from scripts import run_nitro_attestation_e2e as cli


def fixtures():
    now = datetime.now(timezone.utc).replace(microsecond=0)
    stamp = lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ")
    op = "111122223333"
    cust = "444455556666"
    tenant = "pilot01"
    key = f"arn:aws:kms:eu-central-1:{cust}:key/11111111-2222-3333-4444-555555555555"
    ids = [str(uuid.UUID(int=n + 1)) for n in range(7)]
    manifest = {
        "schema": SCHEMA,
        "region": "eu-central-1", "tenant": tenant,
        "workload_account": op, "custody_account": cust,
        "task_definition_arn": f"arn:aws:ecs:eu-central-1:{op}:task-definition/notarai-confidential-{tenant}:12",
        "task_arn": f"arn:aws:ecs:eu-central-1:{op}:task/notarai-confidential-shared/{'a' * 32}",
        "kms_key_arn": key,
        "image_sha256": "b" * 64, "expected_pcr17": "a" * 96,
        "job_id": "c" * 32,
        "positive_event_id": ids[0],
        "denied_event_ids": dict(zip(DENIAL_CASES, ids[1:])),
        "started_at": stamp(now - timedelta(minutes=5)),
        "ended_at": stamp(now - timedelta(minutes=1)),
    }

    def event(eid, denied=False):
        document = {
            "eventID": eid, "eventSource": "kms.amazonaws.com",
            "eventName": "Decrypt", "awsRegion": "eu-central-1",
            "eventTime": stamp(now - timedelta(minutes=3)),
            "requestParameters": {"keyId": key},
            "responseElements": None,
            "userIdentity": {"accountId": op},
            "sharedEventID": "same-aws-request",
        }
        if denied:
            document["errorCode"] = "AccessDeniedException"
        else:
            document["additionalEventData"] = {"recipient": {
                "attestationDocumentModuleId": "nitro-sandbox-module",
                "attestationDocumentEnclavePCR17": "a" * 96,
            }}
        return document

    events = {ids[0]: event(ids[0])}
    events.update({eid: event(eid, denied=True) for eid in ids[1:]})
    wrong_key_id = manifest["denied_event_ids"]["wrong_key"]
    events[wrong_key_id]["requestParameters"]["keyId"] = (
        f"arn:aws:kms:eu-central-1:{cust}:key/99999999-2222-3333-4444-555555555555"
    )
    custody = event(str(uuid.UUID(int=99)))
    custody["recipientAccountId"] = cust
    task = {
        "taskArn": manifest["task_arn"],
        "taskDefinitionArn": manifest["task_definition_arn"],
        "lastStatus": "STOPPED",
        "trustedExecutionSummary": {
            "isolationMode": "CONFIDENTIAL_SANDBOX",
            "attestationPolicyStatus": "CONFIGURED",
        },
        "containers": [{"name": "confidential-browser", "exitCode": 0}],
    }
    release = {
        "tenant": tenant, "kms_key_arn": key,
        "task_definition_arn": manifest["task_definition_arn"],
        "expected_pcr17": "a" * 96,
        "image_sha256": "b" * 64,
        "independent_release_signature_verified": True,
        "static_configuration_verified": True,
        "key_policy_sha256": "d" * 64,
        "task_definition_sha256": "e" * 64,
        "custody_public_key_sha256": "f" * 64,
    }
    return manifest, events, custody, task, release


def assess(item):
    m, e, c, task, release = item
    return assemble_audit_payload(
        manifest=m, workload_events=e, custody_event=c, task=task,
        release=release, result_marker_exists=True,
    )


def test_all_six_denials_are_recorded_but_offline_is_not_hardware_proof():
    payload = assess(fixtures())
    assert len(payload["denials"]) == 6
    assert all(row["kms_result"] == "DENY"
               for row in payload["denials"].values())
    assert payload["positive"]["kms_result"] == "ALLOW"
    assert len(evidence_sha256(payload)) == 64
    assert "hardware_attestation_verified" not in payload
    assert blocked_result()["hardware_attestation_verified"] is False
    assert blocked_result()["production_enabled"] is False


@pytest.mark.parametrize("case", DENIAL_CASES)
def test_missing_denial_or_successful_attack_fails_closed(case):
    data = list(fixtures())
    m, events = data[:2]
    eid = m["denied_event_ids"][case]
    events[eid].pop("errorCode")
    with pytest.raises(ProofRejected):
        assess(data)
    del events[eid]
    with pytest.raises(ProofRejected):
        assess(data)


@pytest.mark.parametrize("alter", [
    lambda d: d[0].update(region="us-east-1"),
    lambda d: d[0].update(tenant="real-customer"),
    lambda d: d[0].update(custody_account=d[0]["workload_account"]),
    lambda d: d[0].update(image_sha256="a" * 63),
    lambda d: d[0].update(expected_pcr17="0" * 96),
    lambda d: d[0].update(job_id="../test"),
    lambda d: d[0]["denied_event_ids"].pop("wrong_key"),
    lambda d: d[0]["denied_event_ids"].update(
        wrong_key=d[0]["positive_event_id"]),
    lambda d: d[0].update(extra="untrusted"),
])
def test_exact_manifest_scope_and_all_cases_required(alter):
    data = list(fixtures())
    alter(data)
    with pytest.raises(ProofRejected):
        assess(data)


@pytest.mark.parametrize("tamper", [
    lambda d: d[1][d[0]["positive_event_id"]].update(errorCode="AccessDenied"),
    lambda d: d[1][d[0]["positive_event_id"]]["additionalEventData"][
        "recipient"].update(attestationDocumentEnclavePCR17="c" * 96),
    lambda d: d[1][d[0]["positive_event_id"]]["additionalEventData"][
        "recipient"].pop("attestationDocumentModuleId"),
    lambda d: d[1][d[0]["positive_event_id"]].update(
        responseElements={"Plaintext": "FORBIDDEN"}),
    lambda d: d[1][d[0]["positive_event_id"]]["requestParameters"].update(
        keyId="arn:aws:kms:eu-central-1:444455556666:key/unapproved"),
    lambda d: d[1][d[0]["positive_event_id"]].update(eventTime="2020-01-01T00:00:00Z"),
    lambda d: d[1][d[0]["positive_event_id"]]["userIdentity"].update(
        accountId="999988887777"),
    lambda d: d[2].update(sharedEventID="not-the-same"),
    lambda d: d[2].update(recipientAccountId="999988887777"),
    lambda d: d[3]["containers"][0].update(exitCode=1),
    lambda d: d[3]["trustedExecutionSummary"].update(
        isolationMode="ISOLATED_SANDBOX"),
    lambda d: d[3].update(taskDefinitionArn="unapproved-task"),
    lambda d: d[4].update(independent_release_signature_verified=False),
    lambda d: d[4].update(image_sha256="f" * 64),
])
def test_tamper_positive_cloudtrail_custody_task_or_release_denied(tamper):
    data = list(fixtures())
    tamper(data)
    with pytest.raises(ProofRejected):
        assess(data)


def test_plaintext_from_kms_is_denied_before_guest_unwrap():
    class FakeKMS:
        def decrypt(self, **kwargs):
            assert kwargs["Recipient"]["KeyEncryptionAlgorithm"] == "RSAES_OAEP_SHA_256"
            assert kwargs["Recipient"]["AttestationDocument"] == b"fake-nsm"
            return {"Plaintext": b"should-never-be-released"}
    class FakeRecipient:
        def signed_document(self):
            return b"fake-nsm"
        def unwrap_recipient_cms(self, _cms):
            raise AssertionError("must not unwrap")
    key = fixtures()[0]["kms_key_arn"]
    with pytest.raises(AttestationRequired, match="unexpected plaintext"):
        AttestedKMSUnwrapper(FakeKMS(), FakeRecipient(), key).unwrap(
            b"synthetic-ciphertext", key,
        )


def test_auditor_signature_requires_exact_report_and_independent_pin(tmp_path):
    payload = assess(fixtures())
    private_key = ec.generate_private_key(ec.SECP256R1())
    pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    pub_file = tmp_path / "auditor.pub"
    sig_file = tmp_path / "audit.sig"
    pub_file.write_bytes(pem)
    signature = private_key.sign(canonical_bytes(payload), ec.ECDSA(hashes.SHA256()))
    import base64
    sig_file.write_text(base64.b64encode(signature).decode())
    fp = public_key_fingerprint(pem)
    cli._verify_external_signature(payload, str(sig_file), str(pub_file), fp)
    with pytest.raises(ProofRejected):
        cli._verify_external_signature(
            {**payload, "tenant": "pilot02"},
            str(sig_file), str(pub_file), fp,
        )
    with pytest.raises(ProofRejected):
        cli._verify_external_signature(
            payload, str(sig_file), str(pub_file), "0" * 64,
        )


def test_offline_check_does_not_contact_aws(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["run_nitro_attestation_e2e.py", "--check"])
    assert cli.main() == 2
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "BLOCKED"
    assert report["hardware_attestation_verified"] is False
    assert report["production_enabled"] is False


def test_live_mode_fails_closed_without_profiles(monkeypatch, tmp_path, capsys):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(fixtures()[0]))
    monkeypatch.setattr(sys, "argv", [
        "run_nitro_attestation_e2e.py", "--verify-live", "--manifest", str(path),
    ])
    assert cli.main() == 2
    assert json.loads(capsys.readouterr().out)["hardware_attestation_verified"] is False


def test_wrong_key_negative_must_not_use_approved_key():
    data = list(fixtures())
    m, events = data[:2]
    events[m["denied_event_ids"]["wrong_key"]]["requestParameters"]["keyId"] = (
        m["kms_key_arn"]
    )
    with pytest.raises(ProofRejected, match="different custody key"):
        assess(data)


@pytest.mark.parametrize("aws_error", [
    "IncorrectKeyException", "InvalidCiphertextException",
    "AccessDeniedException",
])
def test_realistic_kms_wrong_key_failures_are_accepted_as_denial(aws_error):
    data = list(fixtures())
    manifest, events = data[:2]
    events[manifest["denied_event_ids"]["wrong_key"]]["errorCode"] = aws_error
    assert assess(data)["denials"]["wrong_key"]["kms_result"] == "DENY"


def test_wrong_pcr_invalid_ciphertext_cannot_mask_unexplained_failure():
    data = list(fixtures())
    manifest, events = data[:2]
    events[manifest["denied_event_ids"]["wrong_pcr17"]]["errorCode"] = (
        "InvalidCiphertextException"
    )
    with pytest.raises(ProofRejected):
        assess(data)
