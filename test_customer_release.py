"""Offline-only cryptographic regression. No AWS, Nitro or customer data."""
import copy

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from confidential.customer_release import (
    ReleaseDenied, seal_document, envelope_sha256, issue_job_release,
    open_preview_in_guest, parse_envelope, parse_grant,
)


def pem_pair():
    priv = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    return (
        priv.private_bytes(serialization.Encoding.PEM,
                           serialization.PrivateFormat.PKCS8,
                           serialization.NoEncryption()),
        priv.public_key().public_bytes(serialization.Encoding.PEM,
                                       serialization.PublicFormat.SubjectPublicKeyInfo),
    )


@pytest.fixture(scope="module")
def f():
    owner_priv, owner_pub = pem_pair()
    guest_priv, guest_pub = pem_pair()
    second_priv, second_pub = pem_pair()
    content = b'{"form_id":"local-demo","fields":{"name":"FICTIONAL","reference":"SYN-0001"}}'
    env = seal_document(content, owner_pub, tenant_id="pilot01", case_id="case01",
                        object_id="scan01", document_version="a" * 32)
    release = issue_job_release(env, owner_priv, guest_pub, job_id="job01",
                                issued_at=1900000000, expires_at=1900000300)
    expected = dict(expected_tenant="pilot01", expected_case="case01",
                    expected_object="scan01", expected_job="job01", now=1900000010)
    return locals()


def open_valid(f, **kwargs):
    return open_preview_in_guest(f["env"], f["release"], f["guest_priv"],
                                 **(f["expected"] | kwargs))


def test_round_trip_customer_owned_no_kms(f):
    assert open_valid(f) == f["content"]
    assert "kms_key_arn" not in f["env"]
    assert "private" not in str(f["env"])
    assert "private" not in str(f["release"])
    assert f["content"] not in str(f["env"]).encode()


def test_released_dek_cannot_be_read_with_other_guest_key(f):
    with pytest.raises(ReleaseDenied):
        open_preview_in_guest(f["env"], f["release"], f["second_priv"], **f["expected"])


@pytest.mark.parametrize("field,value", [
    ("expected_tenant", "pilot02"), ("expected_case", "case02"),
    ("expected_object", "scan02"), ("expected_job", "job02"),
    ("now", 1900000300), ("now", 1899999999),
])
def test_wrong_scope_or_time_rejected(f, field, value):
    with pytest.raises(ReleaseDenied):
        open_valid(f, **{field: value})


@pytest.mark.parametrize("field,value", [
    ("tenant_id", "pilot02"), ("document_version", "b" * 32),
    ("envelope_sha256", "0" * 64), ("operation", "submit"),
    ("recipient_spki_sha256", "A" * 43 + "="),
    ("expires_at", 1900001000), ("release_nonce_b64", "A" * 32),
])
def test_grant_tampering_rejected(f, field, value):
    grant = dict(f["release"], **{field: value})
    with pytest.raises(ReleaseDenied):
        open_preview_in_guest(f["env"], grant, f["guest_priv"], **f["expected"])


def test_ciphertext_tampering_rejected(f):
    env = dict(f["env"])
    env["ciphertext_b64"] = "A" * 48
    with pytest.raises(ReleaseDenied):
        open_preview_in_guest(env, f["release"], f["guest_priv"], **f["expected"])


def test_owner_private_key_is_required_to_issue_release(f):
    with pytest.raises(ReleaseDenied):
        issue_job_release(f["env"], f["second_priv"], f["guest_pub"],
                          job_id="job01", issued_at=1900000000, expires_at=1900000300)


def test_ttl_limited_to_fifteen_minutes(f):
    with pytest.raises(ReleaseDenied):
        issue_job_release(f["env"], f["owner_priv"], f["guest_pub"],
                          job_id="job01", issued_at=1900000000, expires_at=1900000901)


def test_extra_field_legacy_or_changed_schema_fail_closed(f):
    with pytest.raises(ReleaseDenied):
        parse_grant(dict(f["release"], admin_override=True))
    with pytest.raises(ReleaseDenied):
        parse_envelope(dict(f["env"], kms_key_arn="operator-kms"))
    with pytest.raises(ReleaseDenied):
        parse_grant(dict(f["release"], schema="notarai.customer-release.v0"))


def test_wrong_owner_public_cannot_change_existing_envelope(f):
    altered = dict(f["env"])
    altered["owner_spki_sha256"] = "A" * 43 + "="
    assert envelope_sha256(altered) != envelope_sha256(f["env"])
    with pytest.raises(ReleaseDenied):
        issue_job_release(altered, f["owner_priv"], f["guest_pub"],
                          job_id="job01", issued_at=1900000000, expires_at=1900000300)


def test_release_replay_cannot_open_after_guest_key_rotates(f):
    with pytest.raises(ReleaseDenied):
        open_preview_in_guest(f["env"], f["release"], f["second_priv"], **f["expected"])


def test_explicit_job_binding_different_new_release(f):
    fresh = issue_job_release(f["env"], f["owner_priv"], f["guest_pub"],
                              job_id="job02", issued_at=1900000000,
                              expires_at=1900000300)
    assert fresh["recipient_wrapped_dek_b64"] != f["release"]["recipient_wrapped_dek_b64"]
    with pytest.raises(ReleaseDenied):
        open_preview_in_guest(f["env"], fresh, f["guest_priv"], **f["expected"])