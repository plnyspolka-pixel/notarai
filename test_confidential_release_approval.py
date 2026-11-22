"""Purely synthetic tests: independent P-256 release signatures and replay denial."""
import base64
import copy
from datetime import datetime, timedelta, timezone

import pytest
import yaml
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from confidential.operator_boundary import BoundaryDenied, inspect_operator_boundary
from confidential.release_approval import (
    canonical_bytes, make_release_payload, public_key_fingerprint,
    verify_release,
)
from scripts.custodian_sign_confidential_release import approve
from scripts.verify_confidential_release import check_release
from test_confidential_operator_boundary import fixture
from test_confidential_infra import ROOT, CloudFormationLoader

NOW = datetime(2026, 11, 22, 1, 30, tzinfo=timezone.utc)


def signed_case():
    private = ec.generate_private_key(ec.SECP256R1())
    pub = private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    config = inspect_operator_boundary(**fixture())
    payload = make_release_payload(
        config, clock=NOW, release_id="1" * 32, lifetime_hours=24,
    )
    signature = private.sign(canonical_bytes(payload), ec.ECDSA(hashes.SHA256()))
    return {
        "envelope": {"payload": payload,
                     "signature_b64": base64.b64encode(signature).decode()},
        "config": config,
        "trusted_public_key_pem": pub,
        "pinned_public_key_sha256": public_key_fingerprint(pub),
        "clock": NOW + timedelta(seconds=1),
    }


def test_independent_signature_verifies_but_does_not_claim_hardware():
    output = verify_release(**signed_case())
    assert output["independent_release_signature_verified"] is True
    assert output["static_configuration_verified"] is True
    assert output["hardware_nitro_attestation_verified"] is False
    assert output["zero_operator_access_proven"] is False


@pytest.mark.parametrize("mutate", [
    lambda d: d["envelope"]["payload"].update(image_sha256="f" * 64),
    lambda d: d["envelope"]["payload"].update(expected_pcr17="c" * 96),
    lambda d: d["envelope"]["payload"].update(tenant="pilot02"),
    lambda d: d["envelope"]["payload"].update(kms_key_arn="wrong"),
    lambda d: d["envelope"]["payload"].update(custody_account="987654321098"),
    lambda d: d["envelope"]["payload"].update(task_definition_sha256="0" * 64),
    lambda d: d["envelope"]["payload"].update(issued_at="2026-11-21T00:00:00Z"),
    lambda d: d["envelope"]["payload"].update(expires_at="2027-01-01T00:00:00Z"),
    lambda d: d["envelope"]["payload"].update(release_id="wrong"),
    lambda d: d["envelope"]["payload"].update(extra="operator-backdoor"),
    lambda d: d["envelope"].update(unverified_admin_override=True),
    lambda d: d["envelope"].update(signature_b64="xxx"),
    lambda d: d["config"].update(static_configuration_verified=False),
    lambda d: d["config"].update(key_policy_sha256="9" * 64),
    lambda d: d.update(pinned_public_key_sha256="f" * 64),
    lambda d: d.update(clock=NOW + timedelta(hours=24)),
    lambda d: d.update(clock=NOW - timedelta(seconds=1)),
])
def test_modified_signed_release_and_wrong_trust_root_fail(mutate):
    data = copy.deepcopy(signed_case())
    mutate(data)
    with pytest.raises(BoundaryDenied):
        verify_release(**data)


def test_verifier_does_not_trust_pem_without_out_of_band_pin():
    data = signed_case()
    attacker = ec.generate_private_key(ec.SECP256R1())
    data["trusted_public_key_pem"] = attacker.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    with pytest.raises(BoundaryDenied, match="fingerprint|custodian public"):
        verify_release(**data)


def test_ecdsa_signature_is_not_replayable_for_second_report():
    data = signed_case()
    data["config"] = {**data["config"], "task_definition_arn":
                      data["config"]["task_definition_arn"][:-2] + "13"}
    with pytest.raises(BoundaryDenied):
        verify_release(**data)


def test_expiration_is_short_and_utc():
    config = inspect_operator_boundary(**fixture())
    with pytest.raises(BoundaryDenied):
        make_release_payload(config, clock=NOW, lifetime_hours=100)
    with pytest.raises(BoundaryDenied):
        make_release_payload(config, clock=NOW.replace(tzinfo=None))
    with pytest.raises(BoundaryDenied):
        make_release_payload({**config, "static_configuration_verified": False})
    assert make_release_payload(config, clock=NOW, release_id="2"*32)[
        "expires_at"
    ] == "2026-11-23T01:30:00Z"


def test_signing_command_is_inert_without_explicit_independent_approval():
    assert approve(
        operator_audit_profile="ops", custody_audit_profile="custody-read",
        custody_signer_profile="custody-sign",
        tenant="pilot01", task_definition_arn="test",
        kms_key_arn="test", pcr17="0"*96,
        image_sha256="f"*64,
        signing_key_arn="not-an-arn",
        session_factory=lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("dry-run must never access AWS")
        ),
    )["aws_calls"] == 0
    with pytest.raises(BoundaryDenied):
        approve(
            operator_audit_profile="ops", custody_audit_profile="ops",
            custody_signer_profile="custody-sign",
            tenant="pilot01", task_definition_arn="test",
            kms_key_arn="test", pcr17="0"*96,
            image_sha256="f"*64,
            signing_key_arn="not-an-arn",
        )


def test_release_checker_dry_run_never_accesses_aws():
    data = signed_case()
    result = check_release(
        operator_profile="work", custody_profile="custody",
        tenant="pilot01", task_definition_arn="x", kms_key_arn="x",
        pcr17="a"*96, image_sha256="b"*64,
        receipt=data["envelope"],
        trusted_public_key_pem=data["trusted_public_key_pem"],
        trusted_public_key_sha256=data["pinned_public_key_sha256"],
        session_factory=lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("AWS must not be called")
        ),
    )
    assert result["aws_calls"] == 0


def test_external_signing_key_is_never_a_notarai_iam_or_decrypt_role():
    template = yaml.load(
        (ROOT / "notarai-confidential-custody-signing.yaml").read_text("utf-8"),
        Loader=CloudFormationLoader,
    )
    key = template["Resources"]["CustodianReleaseKey"]
    assert key["Condition"] == "ValidExternalSigner"
    assert "SignerIsCustodyPrincipal" in template["Conditions"]
    assert key["DeletionPolicy"] == "Retain"
    assert key["Properties"]["KeyUsage"] == "SIGN_VERIFY"
    assert key["Properties"]["KeySpec"] == "ECC_NIST_P256"
    statements = key["Properties"]["KeyPolicy"]["Statement"]
    assert len(statements) == 3
    assert statements[1]["Action"] == [
        "kms:Sign", "kms:GetPublicKey", "kms:DescribeKey",
    ]
    assert statements[2]["Action"] == [
        "kms:Verify", "kms:GetPublicKey", "kms:DescribeKey",
    ]
    assert statements[2]["Principal"] == {"AWS": {"Ref": "CustodianAuditRoleArn"}}
    assert "RolesAreSeparate" in template["Conditions"]
    assert "kms:Sign" not in statements[2]["Action"]
    assert "kms:Decrypt" not in str(template)
    assert "kms:CreateGrant" not in str(template)
    assert "notarai-confidential-" not in str(statements[1]["Principal"])
