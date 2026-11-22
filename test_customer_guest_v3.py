"""Nitro guest single-use and local signed policy tests; no AWS calls."""
from __future__ import annotations

import base64
import json
from argparse import Namespace
from unittest.mock import patch

import pytest
pytest.importorskip('cbor2', reason='optional Nitro guest-only dependency')
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa

from confidential.customer_release import (
    ReleaseDenied, issue_job_release, seal_document,
)
from confidential.customer_origin import sign_customer_origin
from confidential.customer_guest_v3 import CustomerGuestSession
from confidential.customer_attested_release import challenge_user_data
from scripts.customer_attested_release import _canonical, _pinned_policy, main

NONCE = b"\xaf" * 32


def pem(private):
    return private.private_bytes(serialization.Encoding.PEM,
                                  serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption())


def pub(private):
    return private.public_key().public_bytes(serialization.Encoding.PEM,
                                            serialization.PublicFormat.SubjectPublicKeyInfo)


@pytest.fixture
def fixture():
    owner = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    notar = ed25519.Ed25519PrivateKey.generate()
    content = b'{"form_id":"local-demo","fields":{"name":"TEST","reference":"SYN-1"}}'
    env = seal_document(content, pub(owner), tenant_id="pilot01",
                        case_id="case01", object_id="object01",
                        document_version="a" * 32)
    receipt, sig = sign_customer_origin(
        env, s3_version="SyntheticVer01", issuer_id="notary01",
        expires_at=2000000000,
        trusted_client_signing_private_pem=pem(notar))
    common = dict(
        expected_tenant="pilot01", expected_case="case01",
        expected_object="object01", expected_job="job01",
        origin_receipt=receipt, origin_signature=sig,
        pinned_notary_signing_public_raw=notar.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw),
        expected_issuer_id="notary01", expected_s3_version="SyntheticVer01",
        now=1900000010,
    )
    return owner, env, common, content


def _run_guest(fixture, *, bad_origin=False):
    owner, env, common, content = fixture
    seen = []
    def fake_nsm(public_key, *, nonce, user_data):
        seen.append((public_key, nonce, user_data))
        return b"synthetic-NOT-AWS-attestation"
    with (patch("confidential.customer_guest_v3.os.path.exists", return_value=True),
          patch("confidential.nsm_recipient._request_attestation",
                side_effect=fake_nsm)):
        guest = CustomerGuestSession()
        report = guest.attest(env, job_id="job01", nonce=NONCE)
        assert report == b"synthetic-NOT-AWS-attestation"
        assert len(seen) == 1
        assert seen[0][1] == NONCE
        assert seen[0][2] == challenge_user_data(env, job_id="job01", nonce=NONCE)
        recipient = serialization.load_der_public_key(seen[0][0])
        recipient_pem = recipient.public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        grant = issue_job_release(env, pem(owner), recipient_pem, job_id="job01",
                                  issued_at=1900000000, expires_at=1900000300)
        if bad_origin:
            common = dict(common, origin_signature=b"invalid")
            with pytest.raises(ReleaseDenied):
                guest.open_preview_once(env, grant, **common)
        else:
            assert guest.open_preview_once(env, grant, **common) == content
        with pytest.raises(ReleaseDenied):
            guest.open_preview_once(env, grant, **common)
        with pytest.raises(ReleaseDenied):
            guest.attest(env, job_id="job01", nonce=NONCE)


def test_nsm_bound_single_use_guest(fixture):
    _run_guest(fixture)


def test_failed_origin_consumes_guest_capability(fixture):
    _run_guest(fixture, bad_origin=True)


def test_no_nsm_guest_refuses_hardwareless(fixture):
    with patch("confidential.customer_guest_v3.os.path.exists", return_value=False):
        with pytest.raises(ReleaseDenied):
            CustomerGuestSession()


def test_challenge_cli_has_no_cloud_calls_or_private_keys(tmp_path, fixture):
    owner, env, _, _ = fixture
    envelope_path = tmp_path / "env.json"
    envelope_path.write_text(json.dumps(env))
    destination = tmp_path / "request.json"
    assert main(["challenge", "--envelope", str(envelope_path),
                 "--job-id", "job01", "--output", str(destination)]) == 0
    payload = json.loads(destination.read_bytes())
    assert payload["schema"] == "notarai.customer-nitro-challenge.v1"
    nonce = base64.b64decode(payload["nonce_b64"])
    assert len(nonce) == 32
    assert base64.b64decode(payload["user_data_b64"]) == challenge_user_data(
        env, job_id="job01", nonce=nonce)
    assert "private" not in destination.read_text()
    assert main(["challenge", "--envelope", str(envelope_path),
                 "--job-id", "job01", "--output", str(destination)]) == 1


def test_pcr_manifest_requires_out_of_band_signature(tmp_path):
    signer = ed25519.Ed25519PrivateKey.generate()
    trusted = tmp_path / "trusted.raw"
    trusted.write_bytes(signer.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw))
    manifest = {
        "schema": "notarai.nitro-pcr-policy.v1", "tenant_id": "pilot01",
        "pcrs": {"8": "8" * 96, "17": "1" * 96},
        "image_digest": "sha256:" + "a" * 64,
        "expires_at": 1900000300,
    }
    source = tmp_path / "manifest.json"
    signature = tmp_path / "manifest.sig"
    source.write_bytes(_canonical(manifest))
    signature.write_bytes(signer.sign(_canonical(manifest)))
    args = Namespace(trusted_policy_public_key=trusted, pcr_manifest=source,
                     pcr_manifest_sig=signature)
    assert _pinned_policy(args, tenant="pilot01", now=1900000000) == {
        8: "8" * 96, 17: "1" * 96}
    source.write_bytes(_canonical(dict(manifest, tenant_id="pilot02")))
    with pytest.raises(ReleaseDenied):
        _pinned_policy(args, tenant="pilot01", now=1900000000)
    source.write_bytes(_canonical(manifest))
    signature.write_bytes(b"0" * 64)
    from cryptography.exceptions import InvalidSignature
    with pytest.raises(InvalidSignature):
        _pinned_policy(args, tenant="pilot01", now=1900000000)
