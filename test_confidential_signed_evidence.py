"""SEC-11 offline synthetic tests. No AWS, customer data or stored private keys."""
import copy
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from confidential.signed_evidence import (
    REQUIRED_CHECKS, SCHEMA, InvalidEvidence, canonical_manifest,
    manifest_sha256, public_fingerprint, sign_manifest,
    verify_bundle, verify_chain,
)

NOW = datetime(2026, 11, 22, 4, 0, tzinfo=timezone.utc)
HASH = "a" * 64


def at(instant):
    return instant.strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture
def identities():
    key = Ed25519PrivateKey.generate()
    pub = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return key, pub, public_fingerprint(pub)


def fixture_manifest():
    return {
        "schema": SCHEMA,
        "tenant": "pilot01",
        "region": "eu-central-1",
        "operator_account": "111122223333",
        "custody_account": "444455556666",
        "observed_at": at(NOW - timedelta(minutes=1)),
        "expires_at": at(NOW + timedelta(hours=1)),
        "source_sha256": "1" * 64,
        "image_sha256": "2" * 64,
        "task_arn": "arn:aws:ecs:eu-central-1:111122223333:task/pilot/abcd0123",
        "pcr17": "3" * 96,
        "kms_policy_sha256": "4" * 64,
        "release_id": "release01",
        "evidence_owner": "independent_auditor",
        "sequence": 1,
        "previous_sha256": None,
        "checks": {
            control: {
                "status": "PASS",
                "provenance": "MOCK",
                "artifact_sha256": "5" * 64,
                "owner": "synthetic_fixture",
            }
            for control in REQUIRED_CHECKS
        },
    }


def verify(bundle, identities, **kwargs):
    _, pub, pin = identities
    return verify_bundle(
        bundle=bundle, trusted_public_key_raw=pub,
        pinned_fingerprint=pin, clock=NOW, **kwargs,
    )


def test_signed_manifest_has_valid_integrity_but_never_proves_live_security(identities):
    key, _, _ = identities
    manifest = fixture_manifest()
    bundle = sign_manifest(manifest, key)
    result = verify(bundle, identities)
    assert result.integrity_status == "PASS"
    assert result.assurance_status == "BLOCKED"
    assert result.zero_operator_access_proven is False
    assert result.manifest_sha256 == manifest_sha256(manifest)
    assert set(result.check_status) == REQUIRED_CHECKS
    assert all(status == "BLOCKED" for status in result.check_status.values())
    assert all(status == "PASS" for status in result.asserted_check_status.values())
    assert all(src == "MOCK" for src in result.check_provenance.values())
    assert result.as_dict()["zero_operator_access_proven"] is False


@pytest.mark.parametrize("field,change", [
    ("tenant", "pilot02"),
    ("image_sha256", "f" * 64),
    ("pcr17", "a" * 96),
    ("kms_policy_sha256", "e" * 64),
    ("observed_at", at(NOW - timedelta(minutes=2))),
])
def test_five_tampered_signed_fields_fail(field, change, identities):
    key, _, _ = identities
    bundle = sign_manifest(fixture_manifest(), key)
    poisoned = copy.deepcopy(bundle)
    poisoned["manifest"][field] = change
    assert verify(poisoned, identities).integrity_status == "FAIL"


def test_removed_operator_deny_test_fails(identities):
    key, _, _ = identities
    poisoned = copy.deepcopy(sign_manifest(fixture_manifest(), key))
    del poisoned["manifest"]["checks"]["kms_operator_deny"]
    assert verify(poisoned, identities).integrity_status == "FAIL"


def test_expired_manifest_is_expired_not_pass(identities):
    key, _, _ = identities
    manifest = fixture_manifest()
    manifest["observed_at"] = at(NOW - timedelta(days=2))
    manifest["expires_at"] = at(NOW - timedelta(seconds=1))
    assert verify(sign_manifest(manifest, key), identities).integrity_status == "EXPIRED"


def test_changed_signature_and_wrong_fingerprint_fail(identities):
    key, pub, pin = identities
    bundle = sign_manifest(fixture_manifest(), key)
    altered = copy.deepcopy(bundle)
    altered["signature_b64"] = "A" * 88
    assert verify(altered, identities).integrity_status == "FAIL"
    assert verify_bundle(bundle=bundle, trusted_public_key_raw=pub,
                         pinned_fingerprint="f" * 64, clock=NOW).integrity_status == "FAIL"
    other = Ed25519PrivateKey.generate().public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    assert verify_bundle(bundle=bundle, trusted_public_key_raw=other,
                         pinned_fingerprint=public_fingerprint(other),
                         clock=NOW).integrity_status == "FAIL"


def test_unknown_fields_prevent_pii_and_free_text_sinks():
    manifest = fixture_manifest()
    manifest["customer_personal_id"] = "synthetic-only"
    with pytest.raises(InvalidEvidence):
        canonical_manifest(manifest)
    del manifest["customer_personal_id"]
    manifest["checks"]["cloudtrail_kms"]["request_payload"] = "synthetic-only"
    with pytest.raises(InvalidEvidence):
        canonical_manifest(manifest)


@pytest.mark.parametrize("malformation", [
    lambda m: m.update({"custody_account": m["operator_account"]}),
    lambda m: m.update({"sequence": 2}),
    lambda m: m.update({"previous_sha256": HASH}),
    lambda m: m.update({"expires_at": at(NOW + timedelta(days=8))}),
    lambda m: m["checks"]["nitro_hardware"].update({"artifact_sha256": None}),
    lambda m: m["checks"]["nitro_hardware"].update({"status": "UNKNOWN"}),
])
def test_reject_nonverifiable_manifest(malformation):
    m = fixture_manifest()
    malformation(m)
    with pytest.raises(InvalidEvidence):
        canonical_manifest(m)


def test_unsigned_missing_hardware_or_mock_only_cannot_enable_zoa(identities):
    key, _, _ = identities
    m = fixture_manifest()
    m["checks"]["nitro_hardware"]["status"] = "BLOCKED"
    m["checks"]["nitro_hardware"]["artifact_sha256"] = None
    b = sign_manifest(m, key)
    result = verify(b, identities)
    assert result.integrity_status == "PASS"
    assert result.check_status["nitro_hardware"] == "BLOCKED"
    assert result.assurance_status == "BLOCKED"
    assert not result.zero_operator_access_proven
    del b["manifest"]["checks"]["nitro_hardware"]
    assert verify(b, identities).integrity_status == "FAIL"


def test_chain_valid_only_with_externally_pinned_head(identities):
    key, pub, pin = identities
    one = fixture_manifest()
    two = fixture_manifest()
    two["sequence"] = 2
    two["previous_sha256"] = manifest_sha256(one)
    two["release_id"] = "release02"
    bundles = [sign_manifest(one, key), sign_manifest(two, key)]
    head = manifest_sha256(two)
    assert verify_chain(bundles=bundles, trusted_public_key_raw=pub,
                        pinned_fingerprint=pin, trusted_head_sha256=head,
                        clock=NOW).integrity_status == "PASS"
    assert verify_chain(bundles=bundles[:-1], trusted_public_key_raw=pub,
                        pinned_fingerprint=pin, trusted_head_sha256=head,
                        clock=NOW).integrity_status == "FAIL"
    assert verify_chain(bundles=bundles[::-1], trusted_public_key_raw=pub,
                        pinned_fingerprint=pin, trusted_head_sha256=head,
                        clock=NOW).integrity_status == "FAIL"
    assert verify_chain(bundles=bundles, trusted_public_key_raw=pub,
                        pinned_fingerprint=pin, trusted_head_sha256="b" * 64,
                        clock=NOW).integrity_status == "FAIL"


def test_chain_middle_link_replay_detected_even_if_resigned(identities):
    key, pub, pin = identities
    one = fixture_manifest()
    two = fixture_manifest()
    two.update(sequence=2, previous_sha256="a" * 64, release_id="release02")
    b = [sign_manifest(one, key), sign_manifest(two, key)]
    assert verify_chain(bundles=b, trusted_public_key_raw=pub, pinned_fingerprint=pin,
                        trusted_head_sha256=manifest_sha256(two),
                        clock=NOW).integrity_status == "FAIL"


def test_future_dated_and_missing_trust_root_deny(identities):
    key, pub, pin = identities
    m = fixture_manifest()
    m["observed_at"] = at(NOW + timedelta(minutes=1))
    m["expires_at"] = at(NOW + timedelta(hours=2))
    assert verify(sign_manifest(m, key), identities).integrity_status == "FAIL"
    assert verify_bundle(bundle=sign_manifest(fixture_manifest(), key),
                         trusted_public_key_raw=pub, pinned_fingerprint="",
                         clock=NOW).integrity_status == "FAIL"


def test_valid_non_mock_assertions_still_need_independent_live_proof(identities):
    key, _, _ = identities
    m = fixture_manifest()
    for control in m["checks"].values():
        control["provenance"] = "AWS_LIVE"
    v = verify(sign_manifest(m, key), identities)
    assert v.integrity_status == "PASS"
    assert v.assurance_status == "BLOCKED"
    assert v.zero_operator_access_proven is False
