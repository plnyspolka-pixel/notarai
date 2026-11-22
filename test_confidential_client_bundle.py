"""Synthetic custodian build; no signing key or real customer data is shipped."""
import base64
import hashlib
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa, ed25519

from confidential.client_release import verify_client_release, UntrustedClientRelease
from scripts.build_custodian_browser_client import build_custodian_client


def test_independent_single_file_signed_client_package(tmp_path):
    root = Path(__file__).resolve().parent
    kms = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    pem = kms.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode("ascii")
    der = kms.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    pin = base64.b64encode(hashlib.sha256(der).digest()).decode("ascii")
    signer = ed25519.Ed25519PrivateKey.generate()
    priv = signer.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    values = dict(
        repository_root=root, output_dir=tmp_path / "custodian-release",
        tenant="pilot01",
        kms_arn="arn:aws:kms:eu-central-1:111122223333:key/fictional",
        kms_public_pem=pem, key_pin=pin, release_id="a"*32,
        expires_at=2000000000, custodian_private_key_pem=priv,
    )
    release = build_custodian_client(**values)
    html = (values["output_dir"] / "client.html").read_bytes()
    manifest = json.loads((values["output_dir"] / "manifest.json").read_bytes())
    signature = base64.b64decode(
        (values["output_dir"] / "manifest.sig").read_bytes().strip()
    )
    public = signer.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    result = verify_client_release(
        javascript=html, manifest=manifest, signature=signature,
        trusted_public_key=public, tenant_id=values["tenant"],
        expected_kms_arn=values["kms_arn"], expected_key_pin=pin,
        now=1900000000,
    )
    assert result == release["artifact_sha256"] == hashlib.sha256(html).hexdigest()
    assert b"connect-src 'none'" in html
    assert b"script-src 'sha256-" in html
    assert b'<script type="module">' in html
    assert b"encryptForConfidentialTask" in html
    assert b"crypto.subtle.encrypt" in html
    assert b"https://" not in html
    assert priv not in html
    for changed in (
        b"tamper" + html, html.replace(b"connect-src 'none'", b"connect-src *"),
    ):
        with pytest.raises(UntrustedClientRelease):
            verify_client_release(
                javascript=changed, manifest=manifest, signature=signature,
                trusted_public_key=public, tenant_id=values["tenant"],
                expected_kms_arn=values["kms_arn"], expected_key_pin=pin,
                now=1900000000,
            )
    # Bundles cannot be overwritten by an operator retry.
    with pytest.raises(FileExistsError):
        build_custodian_client(**values)
    with pytest.raises(ValueError, match="pin mismatch"):
        build_custodian_client(**{**values, "output_dir": tmp_path / "other",
                                  "key_pin": "A" * 43 + "="})
