"""Synthetic COSE/X.509 adversarial tests. No live AWS attestation asserted."""
from __future__ import annotations

import copy
import hashlib
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
cbor2 = pytest.importorskip('cbor2', reason='optional Nitro guest-only dependency')
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa, utils
from cryptography.x509.oid import NameOID

from confidential.customer_nitro_attestation import (
    NitroAttestationDenied, _verify_with_pinned_root, verify_aws_nitro_attestation,
)
from confidential.customer_attested_release import (
    challenge_user_data, issue_attested_job_release,
)
from confidential.customer_release import seal_document, ReleaseDenied

NOW = datetime(2026, 11, 22, 12, 0, tzinfo=timezone.utc)
NONCE = b"\xa3" * 32
USER = b"\x7c" * 32
P = {0: b"\x01" * 48, 1: b"\x02" * 48, 2: b"\x03" * 48,
     8: b"\x08" * 48, 17: b"\x11" * 48}
PINS = {8: P[8].hex(), 17: P[17].hex()}


def _cert(subject_key, name, issuer_key, issuer_name, ca):
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, issuer_name)])
    return (x509.CertificateBuilder()
            .subject_name(subject).issuer_name(issuer)
            .public_key(subject_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(NOW - timedelta(days=1))
            .not_valid_after(NOW + timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
            .sign(issuer_key, hashes.SHA384()))


def _fixture():
    root_private = ec.generate_private_key(ec.SECP384R1())
    leaf_private = ec.generate_private_key(ec.SECP384R1())
    root = _cert(root_private, "TEST CA", root_private, "TEST CA", True)
    leaf = _cert(leaf_private, "TEST LEAF", root_private, "TEST CA", False)
    guest = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    pub = guest.public_key().public_bytes(serialization.Encoding.DER,
                                         serialization.PublicFormat.SubjectPublicKeyInfo)
    root_der = root.public_bytes(serialization.Encoding.DER)
    leaf_der = leaf.public_bytes(serialization.Encoding.DER)
    body = dict(module_id="test-enclave", digest="SHA384",
                timestamp=int(NOW.timestamp() * 1000),
                pcrs=P.copy(), certificate=leaf_der, cabundle=[root_der],
                nonce=NONCE, user_data=USER, public_key=pub)
    return root_der, leaf_private, body


def _sign(leaf_private, body, *, protected=None):
    head = cbor2.dumps({1: -35} if protected is None else protected)
    payload = cbor2.dumps(body)
    signed = cbor2.dumps(["Signature1", head, b"", payload])
    der_sig = leaf_private.sign(signed, ec.ECDSA(hashes.SHA384()))
    r, s = utils.decode_dss_signature(der_sig)
    sig = r.to_bytes(48, "big") + s.to_bytes(48, "big")
    return cbor2.dumps(cbor2.CBORTag(18, [head, {}, payload, sig]))


def _verify(document, root, **kwargs):
    return _verify_with_pinned_root(
        document, expected_nonce=NONCE, expected_user_data=USER,
        expected_pcrs=PINS, now=NOW, pinned_root_der=root, **kwargs)


def test_authentic_synthetic_chain_and_rsa_recipient():
    root, signer, body = _fixture()
    receipt = _verify(_sign(signer, body), root)
    assert b"BEGIN PUBLIC KEY" in receipt.public_key_pem
    assert (8, PINS[8]) in receipt.pcrs
    assert receipt.timestamp_ms == int(NOW.timestamp() * 1000)


@pytest.mark.parametrize("change", [
    "nonce", "user_data", "pcr17", "pcr8", "debug", "missing_pcr8",
    "missing_key", "wrong_key_type", "expired", "future", "digest",
    "bad_cert", "missing_chain",
])
def test_modified_or_untrusted_fields_refused(change):
    root, signer, body = _fixture()
    body = copy.deepcopy(body)
    if change == "nonce":
        body["nonce"] = b"wrong nonce"
    elif change == "user_data":
        body["user_data"] = b"wrong context"
    elif change == "pcr17":
        body["pcrs"][17] = b"z" * 48
    elif change == "pcr8":
        body["pcrs"][8] = b"z" * 48
    elif change == "debug":
        for index in (0, 1, 2):
            body["pcrs"][index] = bytes(48)
    elif change == "missing_pcr8":
        del body["pcrs"][8]
    elif change == "missing_key":
        body["public_key"] = None
    elif change == "wrong_key_type":
        k = ec.generate_private_key(ec.SECP256R1())
        body["public_key"] = k.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo)
    elif change == "expired":
        body["timestamp"] -= 600000
    elif change == "future":
        body["timestamp"] += 600000
    elif change == "digest":
        body["digest"] = "SHA256"
    elif change == "bad_cert":
        body["certificate"] = b"invalid cert"
    elif change == "missing_chain":
        body["cabundle"] = []
    with pytest.raises(NitroAttestationDenied):
        _verify(_sign(signer, body), root)


def test_wrong_aws_root_refused_even_when_report_correctly_signed():
    root, signer, body = _fixture()
    with pytest.raises(NitroAttestationDenied):
        verify_aws_nitro_attestation(_sign(signer, body),
            expected_nonce=NONCE, expected_user_data=USER,
            expected_pcrs=PINS, now=NOW)


def test_mutated_signature_and_trailing_cbor_are_refused():
    root, signer, body = _fixture()
    raw = _sign(signer, body)
    mutated = cbor2.loads(raw)
    altered = list(mutated.value)
    altered[-1] = bytes(96)
    with pytest.raises(NitroAttestationDenied):
        _verify(cbor2.dumps(cbor2.CBORTag(18, altered)), root)
    with pytest.raises(NitroAttestationDenied):
        _verify(raw + b"\x00", root)


def test_missing_pinned_pcrs_refused():
    root, signer, body = _fixture()
    raw = _sign(signer, body)
    for pins in ({}, {8: PINS[8]}, {17: PINS[17]},
                 {8: PINS[8], 17: "0" * 96}):
        with pytest.raises(NitroAttestationDenied):
            _verify_with_pinned_root(raw, expected_nonce=NONCE,
                expected_user_data=USER, expected_pcrs=pins,
                now=NOW, pinned_root_der=root)


def test_wrong_algorithm_and_not_a_cose_sign1_refused():
    root, signer, body = _fixture()
    with pytest.raises(NitroAttestationDenied):
        _verify(_sign(signer, body, protected={1: -7}), root)
    with pytest.raises(NitroAttestationDenied):
        _verify(cbor2.dumps({"unsigned": body}), root)


def test_missing_fresh_challenge_refused():
    root, signer, body = _fixture()
    raw = _sign(signer, body)
    for nonce in (b"", b"\x00" * 32):
        with pytest.raises(NitroAttestationDenied):
            _verify_with_pinned_root(raw, expected_nonce=nonce,
                expected_user_data=USER, expected_pcrs=PINS,
                now=NOW, pinned_root_der=root)


def test_user_data_binds_document_and_job():
    owner = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    owner_pub = owner.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo)
    env = seal_document(b"fictional", owner_pub, tenant_id="pilot01",
                        case_id="case01", object_id="object01",
                        document_version="a" * 32)
    a = challenge_user_data(env, job_id="job01", nonce=NONCE)
    assert len(a) == 32
    assert a != challenge_user_data(env, job_id="job02", nonce=NONCE)
    assert a != challenge_user_data(env, job_id="job01", nonce=b"x" * 32)
    modified = dict(env, ciphertext_b64="A" * 48)
    assert a != challenge_user_data(modified, job_id="job01", nonce=NONCE)


def test_attested_adapter_pins_verified_key_and_attestation_context():
    from confidential.customer_nitro_attestation import VerifiedNitroRecipient
    owner = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    guest = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    pem = lambda k: k.private_bytes(serialization.Encoding.PEM,
                                  serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption())
    pub = lambda k: k.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo)
    env = seal_document(b"fictional", pub(owner), tenant_id="pilot01",
                        case_id="case01", object_id="object01",
                        document_version="a" * 32)
    recipient = VerifiedNitroRecipient(pub(guest), "a" * 64,
                                       int(NOW.timestamp() * 1000), tuple())
    # Mock isolates composition only; NEVER implies a hardware pass.
    with patch("confidential.customer_attested_release.verify_aws_nitro_attestation",
               return_value=recipient) as verifier:
        grant, proof = issue_attested_job_release(
            env, pem(owner), b"synthetic", expected_nonce=NONCE,
            expected_pcrs=PINS, job_id="job01", now=NOW)
    assert grant["job_id"] == "job01"
    assert grant["operation"] == "preview-only"
    assert proof == recipient
    assert verifier.call_args.kwargs["expected_user_data"] == (
        challenge_user_data(env, job_id="job01", nonce=NONCE))
    assert verifier.call_args.kwargs["expected_pcrs"] == PINS


def test_attested_adapter_does_not_fallback_to_operator_public_key():
    owner = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    env = seal_document(b"fictional", owner.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo),
        tenant_id="pilot01", case_id="case01", object_id="object01",
        document_version="a" * 32)
    private = owner.private_bytes(serialization.Encoding.PEM,
                                  serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption())
    with pytest.raises(NitroAttestationDenied):
        issue_attested_job_release(env, private, b"operator-forged-attestation",
                                   expected_nonce=NONCE, expected_pcrs=PINS,
                                   job_id="job01", now=NOW)
