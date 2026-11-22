"""SEC-11 local signer tests. Ephemeral fake keys only; no AWS/real customer data."""
import json
import os
import stat

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from confidential.signed_evidence import public_fingerprint, verify_bundle
from scripts.custodian_sign_confidential_evidence import sign_from_files
from test_confidential_signed_evidence import NOW, fixture_manifest


def setup_synthetic(tmp_path):
    private = Ed25519PrivateKey.generate()
    key_file = tmp_path / "signer-key.enc.pem"
    key_file.write_bytes(private.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(b"fixture-local-password"),
    ))
    key_file.chmod(0o600)
    manifest_file = tmp_path / "manifest.json"
    manifest = fixture_manifest()
    # Signer accepts honest UNVERIFIED/MOCK records; it must refuse MOCK PASS.
    for record in manifest["checks"].values():
        record["status"] = "UNVERIFIED"
        record["artifact_sha256"] = None
    manifest_file.write_text(json.dumps(manifest), encoding="utf-8")
    return private, key_file, manifest_file, tmp_path / "signed.json"


def sign_local(manifest, key, output, secret=b"fixture-local-password\n"):
    readfd, writefd = os.pipe()
    try:
        os.write(writefd, secret)
        os.close(writefd)
        writefd = -1
        return sign_from_files(
            manifest_path=manifest, key_path=key, output_path=output,
            password_fd=readfd,
        )
    finally:
        os.close(readfd)
        if writefd != -1:
            os.close(writefd)


def test_independent_signer_and_offline_verifier_round_trip(tmp_path):
    private, key_file, manifest_file, output = setup_synthetic(tmp_path)
    pin = sign_local(manifest_file, key_file, output)
    assert output.is_file()
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    pub = private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )
    assert pin == public_fingerprint(pub)
    result = verify_bundle(
        bundle=json.loads(output.read_text()), trusted_public_key_raw=pub,
        pinned_fingerprint=pin, clock=NOW,
    )
    assert result.integrity_status == "PASS"
    assert result.assurance_status == "BLOCKED"
    assert not result.zero_operator_access_proven


def test_private_key_world_readable_is_rejected(tmp_path):
    _, key_file, manifest, output = setup_synthetic(tmp_path)
    key_file.chmod(0o644)
    with pytest.raises(ValueError, match="owner-only"):
        sign_local(manifest, key_file, output)
    assert not output.exists()


def test_overwrite_existing_signature_refused(tmp_path):
    _, key_file, manifest, output = setup_synthetic(tmp_path)
    sign_local(manifest, key_file, output)
    original = output.read_bytes()
    with pytest.raises(FileExistsError):
        sign_local(manifest, key_file, output)
    assert output.read_bytes() == original


def test_wrong_password_refuses_without_output(tmp_path):
    _, key_file, manifest, output = setup_synthetic(tmp_path)
    with pytest.raises(ValueError):
        sign_local(manifest, key_file, output, b"bad-passphrase\n")
    assert not output.exists()


def test_noncanonical_personal_fields_refused_before_signing(tmp_path):
    _, key_file, manifest, output = setup_synthetic(tmp_path)
    payload = json.loads(manifest.read_text())
    payload["person_name"] = "SYNTHETIC_ONLY"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        sign_local(manifest, key_file, output)
    assert not output.exists()


def test_symlink_secret_key_refused(tmp_path):
    _, key_file, manifest, output = setup_synthetic(tmp_path)
    alias = tmp_path / "key-link.pem"
    alias.symlink_to(key_file)
    with pytest.raises(ValueError, match="symlink"):
        sign_local(manifest, alias, output)
    assert not output.exists()


def test_persistent_password_file_descriptor_is_refused(tmp_path):
    _, key_file, manifest, output = setup_synthetic(tmp_path)
    secret_file = tmp_path / "do-not-use-disk-password"
    secret_file.write_bytes(b"fixture-local-password\n")
    descriptor = os.open(secret_file, os.O_RDONLY)
    try:
        with pytest.raises(ValueError, match="transient pipe"):
            sign_from_files(
                manifest_path=manifest, key_path=key_file,
                output_path=output, password_fd=descriptor,
            )
    finally:
        os.close(descriptor)
    assert not output.exists()


def test_signer_refuses_signed_mock_pass_even_with_valid_schema(tmp_path):
    _, key_file, manifest_file, output = setup_synthetic(tmp_path)
    payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    payload["checks"]["kms_attested_decrypt"]["status"] = "PASS"
    payload["checks"]["kms_attested_decrypt"]["artifact_sha256"] = "6" * 64
    manifest_file.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="mock PASS"):
        sign_local(manifest_file, key_file, output)
    assert not output.exists()
