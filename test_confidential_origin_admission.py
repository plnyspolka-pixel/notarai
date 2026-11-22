"""SEC-03: signed document origin must pass before any synthetic Nitro DEK unwrap.

No AWS access, live notary files, installed signing keys, or actual Nitro.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding, ed25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

import confidential.origin_admission as origin
from confidential.envelope import Envelope
from confidential.worker import _load_decrypted_form
from scripts.sign_confidential_origin_receipt import sign_origin_receipt

TENANT = "pilot01"
CASE = "case01"
OBJECT = "scan01"
ARN = "arn:aws:kms:eu-central-1:111122223333:key/fictional"
VERSION = "s3SyntheticVersion01"
ISSUER = "notary_fixture_01"
TEXT = b'{"form_id":"local-demo","fields":{"name":"FICTIONAL","reference":"SYN-0001"}}'


@pytest.fixture
def synthetic(tmp_path, monkeypatch):
    kms = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    pub_der = kms.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    pin = base64.b64encode(hashlib.sha256(pub_der).digest()).decode("ascii")
    dek = bytes(range(32))
    nonce = bytes(range(12))
    logical = "a" * 32
    aad = f"notarai-v2|{TENANT}|{CASE}|{OBJECT}|{logical}|{ARN}|{pin}".encode("ascii")
    wrapped = kms.public_key().encrypt(
        dek, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),
                          algorithm=hashes.SHA256(), label=None),
    )
    envelope = {
        "version": 2, "algorithm": "AES-256-GCM+RSA-OAEP-SHA256",
        "tenant_id": TENANT, "case_id": CASE, "object_id": OBJECT,
        "document_version": logical,
        "kms_key_arn": ARN, "public_key_sha256": pin,
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "wrapped_dek": base64.b64encode(wrapped).decode("ascii"),
        "ciphertext": base64.b64encode(AESGCM(dek).encrypt(nonce, TEXT, aad)).decode("ascii"),
    }
    wire = json.dumps(envelope, separators=(",", ":")).encode("ascii")
    wirepath = tmp_path / "synthetic.encrypted.json"
    wirepath.write_bytes(wire)
    sha = hashlib.sha256(wire).hexdigest()

    signer = ed25519.Ed25519PrivateKey.generate()
    signing_key_pem = signer.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    receiptpath = tmp_path / "synthetic.origin.json"
    sign_origin_receipt(
        ciphertext_file=wirepath, output_file=receiptpath,
        expected_sha256=sha, verified_s3_version=VERSION,
        issuer_id=ISSUER, expires_at=2000000000,
        issuer_private_key_pem=signing_key_pem,
        approved_tenant=TENANT, approved_kms_key_arn=ARN, approved_key_pin=pin,
    )
    root = {
        "schema": "notarai.origin-root.v1", "tenant_id": TENANT,
        "issuer_id": ISSUER,
        "issuer_public_key_b64": base64.b64encode(
            signer.public_key().public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw
            )
        ).decode("ascii"),
        "kms_key_arn": ARN, "public_key_sha256": pin,
        "expires_at": 2000000000,
    }
    rootpath = tmp_path / "signed-release-embedded-origin-root.json"
    rootpath.write_text(json.dumps(root), encoding="ascii")
    monkeypatch.setattr(origin, "_ROOT_PATH", rootpath)
    return {
        "kms": kms, "envelope": envelope, "wire": wire, "sha": sha,
        "pin": pin, "receipt": receiptpath.read_bytes(),
        "receiptpath": receiptpath, "wirepath": wirepath, "root": root,
        "rootpath": rootpath, "signing_key": signing_key_pem,
    }


class FakeS3:
    def __init__(self, wire, receipt):
        self.wire = wire
        self.receipt = receipt
        self.reads = []
    def get_object(self, **kwargs):
        self.reads.append(kwargs)
        if kwargs["Key"].endswith(".origin.json"):
            return {"Body": io.BytesIO(self.receipt)}
        assert kwargs["VersionId"] == VERSION
        return {"Body": io.BytesIO(self.wire)}


def verify(sample, *, now=1900000000, s3=None):
    s3 = s3 or FakeS3(sample["wire"], sample["receipt"])
    origin.require_origin_receipt(
        s3, bucket="fixture-bucket", tenant=TENANT, case_id=CASE,
        object_id=OBJECT, s3_version=VERSION,
        ciphertext_sha256=sample["sha"], document_version="a" * 32,
        key_arn=ARN, public_key_sha256=sample["pin"], now=now,
    )
    return s3


def test_correct_signed_receipt_and_exact_object_version(synthetic):
    s3 = verify(synthetic)
    assert len(s3.reads) == 1
    assert s3.reads[0]["Key"] == (
        f"kancelarie/{TENANT}/confidential/{CASE}/{OBJECT}.origin.json"
    )
    assert s3.reads[0]["Bucket"] == "fixture-bucket"


@pytest.mark.parametrize("field, wrong", [
    ("tenant", "pilot02"), ("case", "other_case"),
    ("object", "other_object"), ("s3_version", "stale_version"),
    ("digest", "f" * 64), ("key", "arn:aws:kms:eu-central-1:111122223333:key/changed"),
    ("pin", "A" * 43 + "="), ("logical", "b" * 32),
])
def test_signed_receipt_does_not_authorize_different_context(synthetic, field, wrong):
    kw = dict(s3=FakeS3(synthetic["wire"], synthetic["receipt"]),
              bucket="fixture-bucket", tenant=TENANT, case_id=CASE,
              object_id=OBJECT, s3_version=VERSION,
              ciphertext_sha256=synthetic["sha"], document_version="a" * 32,
              key_arn=ARN, public_key_sha256=synthetic["pin"],
              now=1900000000)
    name = dict(tenant="tenant", case="case_id", object="object_id",
                s3_version="s3_version", digest="ciphertext_sha256",
                key="key_arn", pin="public_key_sha256", logical="document_version")
    kw[name[field]] = wrong
    with pytest.raises((origin.OriginAdmissionDenied, ValueError)):
        origin.require_origin_receipt(**kw)


def test_invalid_receipts_and_missing_trust_root_fail_closed(synthetic, monkeypatch, tmp_path):
    valid = json.loads(synthetic["receipt"])
    for invalid in (
        b'{"unexpected":"fields"}',
        b"{" + synthetic["receipt"] + b"}",
        json.dumps({**valid, "signature_b64": "A" * 88}).encode(),
        json.dumps({**valid, "receipt": {
            **valid["receipt"], "ciphertext_sha256": "0" * 64,
        }}).encode(),
        synthetic["receipt"] + b" " * 9000,
        b'{"schema":"x","schema":"x"}',
    ):
        with pytest.raises(origin.OriginAdmissionDenied):
            verify(synthetic, s3=FakeS3(synthetic["wire"], invalid))
    monkeypatch.setattr(origin, "_ROOT_PATH", tmp_path / "nonexistent")
    with pytest.raises(origin.OriginAdmissionDenied, match="not provisioned"):
        verify(synthetic)
    monkeypatch.setattr(origin, "_ROOT_PATH", synthetic["rootpath"])
    with pytest.raises(origin.OriginAdmissionDenied):
        verify(synthetic, now=2000000000)


def test_offline_signer_refuses_wrong_ciphertext_pin_and_signature_reuse(synthetic, tmp_path):
    base = dict(
        ciphertext_file=synthetic["wirepath"],
        output_file=tmp_path / "new.origin.json",
        expected_sha256=synthetic["sha"], verified_s3_version=VERSION,
        issuer_id=ISSUER, expires_at=2000000000,
        issuer_private_key_pem=synthetic["signing_key"],
        approved_tenant=TENANT, approved_kms_key_arn=ARN,
        approved_key_pin=synthetic["pin"],
    )
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        sign_origin_receipt(**{**base, "expected_sha256": "0" * 64})
    with pytest.raises(ValueError, match="approved key"):
        sign_origin_receipt(**{**base, "approved_tenant": "pilot02"})
    with pytest.raises(FileExistsError):
        sign_origin_receipt(**{**base, "output_file": synthetic["receiptpath"]})


def test_guest_enforces_receipt_before_any_key_unwrap(synthetic, monkeypatch):
    import confidential.worker as worker
    import confidential.nitro_unwrapper as nitro
    from confidential.origin_admission import OriginAdmissionDenied
    calls = []
    class TestUnwrapper:
        def __init__(self, kms, arn):
            calls.append("construct_unwrapper")
        def unwrap(self, wrapped, key_arn):
            calls.append("unwrap")
            return synthetic["kms"].decrypt(wrapped, padding.OAEP(
                mgf=padding.MGF1(hashes.SHA256()),
                algorithm=hashes.SHA256(), label=None,
            ))
    monkeypatch.setattr(nitro, "NitroKMSUnwrapper", TestUnwrapper)
    class Registry:
        def require_guest(self, **kwargs):
            calls.append("ledger")
            assert kwargs["ciphertext_sha256"] == synthetic["sha"]

    good = FakeS3(synthetic["wire"], synthetic["receipt"])
    output = _load_decrypted_form(
        good, object(), "fixture-bucket", TENANT, CASE, OBJECT,
        ARN, VERSION, Registry()
    )
    assert output == {"name": "FICTIONAL", "reference": "SYN-0001"}
    assert calls == ["ledger", "construct_unwrapper", "unwrap"]
    calls.clear()
    forged = json.loads(synthetic["receipt"])
    forged["signature_b64"] = base64.b64encode(b"x" * 64).decode("ascii")
    bad = FakeS3(synthetic["wire"], json.dumps(forged).encode())
    with pytest.raises(OriginAdmissionDenied):
        _load_decrypted_form(
            bad, object(), "fixture-bucket", TENANT, CASE, OBJECT,
            ARN, VERSION, Registry(),
        )
    assert calls == ["ledger"], "Nitro unwrapped a DEK before verifying origin"
    calls.clear()
    missing = FakeS3(synthetic["wire"], b"")
    with pytest.raises(OriginAdmissionDenied):
        _load_decrypted_form(
            missing, object(), "fixture-bucket", TENANT, CASE, OBJECT,
            ARN, VERSION, Registry(),
        )
    assert calls == ["ledger"]


def test_package_custodian_issuer_root_requires_out_of_band_spki_pin(synthetic, tmp_path, monkeypatch):
    from scripts.package_confidential_origin_root import package_origin_root
    issuer = serialization.load_pem_private_key(synthetic["signing_key"], password=None)
    spki = issuer.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    pem = issuer.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    args = dict(
        destination=tmp_path / "trusted-origin-root.json",
        tenant_id=TENANT, issuer_id=ISSUER,
        issuer_public_key_pem=pem,
        independently_pinned_issuer_spki_sha256=hashlib.sha256(spki).hexdigest(),
        kms_key_arn=ARN, kms_public_key_sha256=synthetic["pin"],
        expires_at=2000000000,
    )
    result = package_origin_root(**args)
    assert len(result["root_sha256"]) == 64
    monkeypatch.setattr(origin, "_ROOT_PATH", args["destination"])
    assert origin.load_trusted_origin_root(
        tenant=TENANT, key_arn=ARN, now=1900000000,
    )["issuer_id"] == ISSUER
    with pytest.raises(FileExistsError):
        package_origin_root(**args)
    with pytest.raises(ValueError, match="pin mismatch"):
        package_origin_root(**{**args,
            "destination": tmp_path / "wrong.json",
            "independently_pinned_issuer_spki_sha256": "f" * 64,
        })
