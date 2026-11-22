"""Offline regression tests for image-pinned independent recovery signers.

No cloud accounts, notary data, KMS calls or private keys in artifact outputs.
"""
import base64
import hashlib
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

import confidential.recovery_trust as trust
from confidential.zk_recovery import (
    RecoveryDenied, authorize_recovery, canonical_recovery_request,
)
from scripts.package_confidential_recovery_root import package_recovery_root

ARN = "arn:aws:kms:eu-central-1:111122223333:key/fictional"
PIN = "A" * 43 + "="


@pytest.fixture
def root_fixture(tmp_path, monkeypatch):
    first, second = ed25519.Ed25519PrivateKey.generate(), ed25519.Ed25519PrivateKey.generate()
    def public(signer):
        key = signer.public_key()
        return (
            key.public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
            ),
            key.public_bytes(
                serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
            ),
            key.public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw
            ),
        )
    c, t = public(first), public(second)
    args = {
        "output_file": tmp_path / "trusted-recovery-root.json",
        "tenant": "pilot01", "old_key_arn": ARN, "old_key_pin": PIN,
        "custodian_public_key_pem": c[0],
        "trustee_public_key_pem": t[0],
        "custodian_spki_sha256": hashlib.sha256(c[1]).hexdigest(),
        "trustee_spki_sha256": hashlib.sha256(t[1]).hexdigest(),
        "expires_at": 2000000000,
    }
    result = package_recovery_root(**args)
    monkeypatch.setattr(trust, "_ROOT_PATH", args["output_file"])
    return args, result, (first, second), (c[2], t[2])


def test_two_distinct_externally_pinned_signers_load(root_fixture):
    args, result, _, keys = root_fixture
    assert result["root_sha256"] == hashlib.sha256(args["output_file"].read_bytes()).hexdigest()
    assert trust.load_recovery_trust_root(
        tenant="pilot01", old_key_arn=ARN, old_key_pin=PIN, now=1900000000
    ) == keys
    assert b"PRIVATE KEY" not in args["output_file"].read_bytes()
    with pytest.raises(FileExistsError):
        package_recovery_root(**args)
    with pytest.raises(ValueError, match="pin mismatch"):
        package_recovery_root(**{**args,
            "output_file": args["output_file"].parent / "mismatch.json",
            "trustee_spki_sha256": "f" * 64,
        })
    with pytest.raises(ValueError, match="different"):
        package_recovery_root(**{**args,
            "output_file": args["output_file"].parent / "same.json",
            "trustee_public_key_pem": args["custodian_public_key_pem"],
            "trustee_spki_sha256": args["custodian_spki_sha256"],
        })


@pytest.mark.parametrize("change", [
    {"tenant": "pilot02"},
    {"old_key_pin": "B" * 43 + "="},
    {"old_key_arn": "arn:aws:kms:eu-central-1:111122223333:key/alternate"},
    {"now": 2000000000},
])
def test_cross_tenant_key_drift_and_expired_root_are_denied(root_fixture, change):
    opts = dict(tenant="pilot01", old_key_arn=ARN, old_key_pin=PIN, now=1900000000)
    with pytest.raises(RecoveryDenied):
        trust.load_recovery_trust_root(**{**opts, **change})


def test_missing_altered_and_duplicate_key_roots_fail_closed(root_fixture, monkeypatch, tmp_path):
    args, _, _, _ = root_fixture
    root = json.loads(args["output_file"].read_text())
    for bad in (
        b"",
        b"{" + args["output_file"].read_bytes() + b"}",
        b'{"schema":"notarai.recovery-root.v1","schema":"notarai.recovery-root.v1"}',
        json.dumps({**root, "custodian_public_key_b64": "not base64"}).encode(),
        json.dumps({**root, "trustee_public_key_b64": root["custodian_public_key_b64"]}).encode(),
        json.dumps({**root, "tenant_id": "pilot02"}).encode(),
        b" " * 2200,
    ):
        changed = tmp_path / "altered.json"
        changed.write_bytes(bad)
        monkeypatch.setattr(trust, "_ROOT_PATH", changed)
        with pytest.raises(RecoveryDenied):
            trust.load_recovery_trust_root(
                tenant="pilot01", old_key_arn=ARN, old_key_pin=PIN,
                now=1900000000,
            )
    monkeypatch.setattr(trust, "_ROOT_PATH", tmp_path / "missing")
    with pytest.raises(RecoveryDenied, match="not provisioned"):
        trust.load_recovery_trust_root(
            tenant="pilot01", old_key_arn=ARN, old_key_pin=PIN, now=1900000000
        )


def test_source_ciphertext_digest_version_and_pin_signed_by_both(root_fixture):
    _, _, signers, keys = root_fixture
    request = {
        "schema": "notarai.recovery.v2", "action": "rotate",
        "tenant_id": "pilot01", "case_id": "case01",
        "object_id": "scan01", "target_tenant_id": "pilot02",
        "target_object_id": "scan02",
        "document_version": "a" * 32,
        "old_key_arn": ARN,
        "source_s3_version": "originalS3version01",
        "source_ciphertext_sha256": "a" * 64,
        "source_key_pin": PIN,
        "new_key_arn": ARN.replace("fictional", "replacement"),
        "new_key_sha256": "B" * 43 + "=",
        "request_id": "b" * 32, "expires_at": 2000000000,
    }
    canonical = canonical_recovery_request(request)
    args = dict(
        request=request, custodian_signature=signers[0].sign(canonical),
        trustee_signature=signers[1].sign(canonical),
        custodian_public_key=keys[0], trustee_public_key=keys[1],
        expected_tenant="pilot01", expected_old_key=ARN, now=1900000000,
    )
    assert authorize_recovery(**args) == "rotate"
    for bad in (
        {"source_s3_version": "anotherVersion"},
        {"source_ciphertext_sha256": "b" * 64},
        {"source_key_pin": "B" * 43 + "="},
        {"tenant_id": "pilot02"},
        {"target_object_id": "scan03"},
        {"new_key_sha256": "C" * 43 + "="},
        {"request_id": "c" * 32},
    ):
        with pytest.raises(RecoveryDenied):
            authorize_recovery(**{**args, "request": {**request, **bad}})
    with pytest.raises(RecoveryDenied):
        canonical_recovery_request({**request, "schema": "notarai.recovery.v1"})
