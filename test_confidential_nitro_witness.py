"""SEC-07 witness dual-signature regression tests (entirely synthetic)."""
import base64
import copy
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from confidential.nitro_denial_matrix import (
    CASES, KMS_CASES, DenialEvidenceRejected,
)
from confidential.nitro_witness import (
    _matrix_hash, canonical_witness, validate_witness_payload,
    verify_independent_witnesses,
)
from confidential.release_approval import public_key_fingerprint
from test_confidential_nitro_denial_matrix import sample


def signed_fixture():
    matrix, _, _ = sample()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "schema": "notarai.confidential.nitro-denial-witness.v1",
        "tenant": matrix["tenant"], "job_id": matrix["job_id"],
        "matrix_sha256": _matrix_hash(matrix),
        "observed_at": matrix["ended_at"],
        "expires_at": fmt(now + timedelta(hours=1)),
        "denied_event_ids": {
            name: matrix["trials"][name]["event_id"] for name in KMS_CASES
        },
        "trial_receipt_sha256": {
            name: matrix["trials"][name]["receipt_sha256"] for name in CASES
        },
        "result": "SIX_DENIALS_WITNESSED",
        "submitted": False,
        "signed": False,
    }
    keys = [ec.generate_private_key(ec.SECP256R1()) for _ in range(2)]
    pem = [key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ) for key in keys]
    sig = [base64.b64encode(
        key.sign(canonical_witness(payload), ec.ECDSA(hashes.SHA256()))
    ).decode() for key in keys]
    args = {
        "payload": payload, "matrix": matrix,
        "custodian_signature_b64": sig[0],
        "custodian_public_key_pem": pem[0],
        "custodian_public_key_sha256": public_key_fingerprint(pem[0]),
        "auditor_signature_b64": sig[1],
        "auditor_public_key_pem": pem[1],
        "auditor_public_key_sha256": public_key_fingerprint(pem[1]),
    }
    return args


def test_two_valid_distinct_signatures_still_cannot_prove_hardware():
    result = verify_independent_witnesses(**signed_fixture())
    assert result["witness_signatures_verified"] is True
    assert result["hardware_attestation_verified"] is False
    assert result["status"] == "BLOCKED"
    assert result["production_enabled"] is False


@pytest.mark.parametrize("alter", [
    lambda data: data["payload"].update(tenant="pilot02"),
    lambda data: data["payload"].update(job_id="e" * 32),
    lambda data: data["payload"].update(submitted=True),
    lambda data: data["payload"].update(signed=True),
    lambda data: data["payload"].update(result="PASS"),
    lambda data: data["payload"].update(matrix_sha256="f" * 64),
    lambda data: data["payload"]["trial_receipt_sha256"].update(
        wrong_pcr17="f" * 64),
    lambda data: data["payload"]["denied_event_ids"].pop("wrong_key"),
    lambda data: data["payload"].update(extra="admin_override"),
])
def test_witness_payload_tampering_is_denied(alter):
    data = signed_fixture()
    alter(data)
    with pytest.raises(DenialEvidenceRejected):
        verify_independent_witnesses(**data)


def test_invalid_auditor_signature_denied():
    data = signed_fixture()
    data["auditor_signature_b64"] = base64.b64encode(b"forged").decode()
    with pytest.raises(DenialEvidenceRejected):
        verify_independent_witnesses(**data)


def test_same_pinned_identity_cannot_sign_as_both_witnesses():
    data = signed_fixture()
    data["auditor_signature_b64"] = data["custodian_signature_b64"]
    data["auditor_public_key_pem"] = data["custodian_public_key_pem"]
    data["auditor_public_key_sha256"] = data["custodian_public_key_sha256"]
    with pytest.raises(DenialEvidenceRejected):
        verify_independent_witnesses(**data)


def test_untrusted_auditor_pin_denied_even_with_valid_signature():
    data = signed_fixture()
    data["auditor_public_key_sha256"] = "0" * 64
    with pytest.raises(DenialEvidenceRejected):
        verify_independent_witnesses(**data)


def test_expired_signature_denied():
    data = signed_fixture()
    now = datetime.now(timezone.utc) + timedelta(hours=25)
    with pytest.raises(DenialEvidenceRejected):
        verify_independent_witnesses(**data, now=now)


def test_signature_is_bound_to_the_exact_six_cases():
    data = signed_fixture()
    data["matrix"]["trials"]["wrong_pcr17"]["receipt_sha256"] = "9" * 64
    with pytest.raises(DenialEvidenceRejected):
        verify_independent_witnesses(**data)



def test_audit_command_checks_two_signatures_and_never_enables_hardware(
    tmp_path, monkeypatch, capsys,
):
    import json
    import sys
    from scripts import audit_nitro_denials as audit

    fixture = signed_fixture()
    files = {
        "matrix": json.dumps(fixture["matrix"]),
        "witness": json.dumps(fixture["payload"]),
        "altered": "{}",
        "unsigned": "{}",
        "custody-sig": fixture["custodian_signature_b64"],
        "custody-pub": fixture["custodian_public_key_pem"],
        "auditor-sig": fixture["auditor_signature_b64"],
        "auditor-pub": fixture["auditor_public_key_pem"],
    }
    for name, data in files.items():
        path = tmp_path / name
        if isinstance(data, bytes):
            path.write_bytes(data)
        else:
            path.write_text(data, encoding="utf-8")
    monkeypatch.setattr(audit, "audit_live", lambda **kwargs: {
        "status": "BLOCKED",
        "hardware_attestation_verified": False,
        "production_enabled": False,
        "kms_cases_live_observed": 4,
        "early_case_metadata_validated": 2,
    })
    argv = [
        "audit_nitro_denials.py", "--verify-live",
        "--matrix", str(tmp_path / "matrix"),
        "--operator-profile", "workload-ro",
        "--custody-profile", "custody-ro",
        "--altered-image-receipt", str(tmp_path / "altered"),
        "--unsigned-release-receipt", str(tmp_path / "unsigned"),
        "--witness-payload", str(tmp_path / "witness"),
        "--custodian-witness-signature", str(tmp_path / "custody-sig"),
        "--custodian-witness-public-key", str(tmp_path / "custody-pub"),
        "--custodian-witness-public-key-sha256",
        fixture["custodian_public_key_sha256"],
        "--auditor-witness-signature", str(tmp_path / "auditor-sig"),
        "--auditor-witness-public-key", str(tmp_path / "auditor-pub"),
        "--auditor-witness-public-key-sha256",
        fixture["auditor_public_key_sha256"],
    ]
    monkeypatch.setattr(sys, "argv", argv)
    assert audit.main() == 2
    output = json.loads(capsys.readouterr().out)
    assert output["witness_signatures_verified"] is True
    assert output["status"] == "BLOCKED"
    assert output["hardware_attestation_verified"] is False
    assert output["production_enabled"] is False
    # A malicious or modified signature must not produce a signed audit.
    (tmp_path / "auditor-sig").write_text("invalid-sig")
    assert audit.main() == 2
    output = json.loads(capsys.readouterr().out)
    assert output["hardware_attestation_verified"] is False
    assert output.get("witness_signatures_verified") is not True
