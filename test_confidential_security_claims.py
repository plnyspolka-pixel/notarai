"""SEC-01: synthetic security-claims proof gating and adversarial test matrix.

All private signing keys below are transient test-only keys. Test PASS means
the evaluator behaves correctly, NEVER that AWS Nitro/ZOA/ZK is certified.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from confidential.security_claims import (
    ClaimsRejected, canonical_evidence_bytes, evaluate_claims,
    public_key_fingerprint, validate_policy,
)

ROOT = Path(__file__).parent
POLICY_PATH = ROOT / "docs/security-claims/policy.json"
NOW = datetime(2026, 11, 22, 12, 0, 0, tzinfo=timezone.utc)
DIGEST = "b" * 64
AUDITOR = "independent_auditor"
CUSTODIAN = "independent_custodian"


def policy():
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def _time(instant):
    return instant.strftime("%Y-%m-%dT%H:%M:%SZ")


def _sign(payload, key):
    return base64.b64encode(
        key.sign(canonical_evidence_bytes(payload), ec.ECDSA(hashes.SHA256()))
    ).decode("ascii")


def fixtures():
    keys = {k: ec.generate_private_key(ec.SECP256R1()) for k in (
        AUDITOR, CUSTODIAN,
    )}
    roots = {}
    for role, key in keys.items():
        pem = key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        roots[role] = {
            "public_key_pem": pem,
            "fingerprint_sha256": public_key_fingerprint(pem),
        }
    receipts = []
    for ci, claim in enumerate(policy()["claims"]):
        for ei, required in enumerate(claim["required_evidence"]):
            payload = {
                "schema": "notarai.security-evidence.v1",
                "evidence_id": hashlib.sha256(
                    (claim["id"] + required["id"]).encode()
                ).hexdigest()[:32],  # synthetic unique ID; not a signature
                "claim_id": claim["id"],
                "evidence_type": required["id"],
                "evidence_owner": required["owner"],
                "source": required["source"],
                "tenant": "pilot01",
                "region": "eu-central-1",
                "image_sha256": DIGEST,
                "issued_at": _time(NOW - timedelta(hours=1)),
                "expires_at": _time(NOW + timedelta(hours=12)),
                "negative_tests_passed": True,
                "report_id": "synthetic_case_" + str(ci) + "_" + str(ei),
                "report_sha256": hashlib.sha256(
                    (str(ci) + ":" + str(ei)).encode()
                ).hexdigest(),
            }
            receipts.append({
                "payload": payload,
                "signature_b64": _sign(payload, keys[required["owner"]]),
            })
    return keys, roots, receipts


def evaluate(receipts=None, roots=None, *, policy_override=None, digest=DIGEST,
             tenant="pilot01", now=NOW):
    return evaluate_claims(
        policy_override if policy_override is not None else policy(),
        receipts, trust_roots=roots, tenant=tenant, image_sha256=digest,
        now=now,
    )


def test_k1_four_complete_claims_and_non_optional_fields():
    data = policy()
    validate_policy(data)
    assert set(x["id"] for x in data["claims"]) == {
        "zero_trust", "zero_operator_access", "confidential_computing",
        "scoped_zero_knowledge",
    }
    assert all(set(x) == {
        "id", "scope", "trust_boundary", "required_evidence",
        "evidence_owner", "negative_test", "expires_at", "status",
    } for x in data["claims"])
    assert all(x["status"] == "UNVERIFIED" for x in data["claims"])


@pytest.mark.parametrize("field", [
    "scope", "trust_boundary", "required_evidence", "evidence_owner",
    "negative_test", "expires_at", "status",
])
def test_k1_missing_claim_fields_rejected(field):
    data = policy()
    data["claims"][0].pop(field)
    with pytest.raises(ClaimsRejected):
        validate_policy(data)


def test_k2_every_claim_unverified_by_default():
    result = evaluate()
    assert set(result["claims"]) == {
        "zero_trust", "zero_operator_access", "confidential_computing",
        "scoped_zero_knowledge",
    }
    assert [x["status"] for x in result["claims"].values()] == (
        ["UNVERIFIED"] * 4
    )
    assert result["security_claims_commercially_verified"] is False


def test_k2_ci_or_static_report_cannot_make_any_claim_pass():
    keys, roots, receipts = fixtures()
    for item in receipts:
        item["payload"]["source"] = "ci"
        item["signature_b64"] = _sign(
            item["payload"], keys[item["payload"]["evidence_owner"]]
        )
    report = evaluate(receipts, roots)
    assert all(x["status"] != "PASS" for x in report["claims"].values())
    assert report["security_claims_commercially_verified"] is False


def test_k3_12_attack_paths_accountable_and_negative_testable():
    data = policy()
    assert len(data["threats"]) >= 10
    text = json.dumps(data["threats"]).lower()
    for token in (
        "passrole", "github", "kms:putkeypolicy", "organizations",
        "pcr17", "cross", "dns", "proxy", "logging", "llm", "js",
        "submit",
    ):
        assert token in text
    assert all(t["negative_test"] and t["owner"] in (
        AUDITOR, CUSTODIAN,
    ) for t in data["threats"])


def test_valid_signed_evidence_only_admits_structural_pass_not_marketing():
    _, roots, receipts = fixtures()
    report = evaluate(receipts, roots)
    assert all(item["status"] == "PASS" for item in report["claims"].values())
    assert all(not item["missing_evidence"] for item in report["claims"].values())
    assert report["security_claims_commercially_verified"] is False


@pytest.mark.parametrize("tamper", [
    lambda r: r[0]["payload"].update(tenant="pilot02"),
    lambda r: r[0]["payload"].update(image_sha256="a" * 64),
    lambda r: r[0]["payload"].update(expires_at="2026-11-21T00:00:00Z"),
    lambda r: r[0]["payload"].update(source="synthetic"),
    lambda r: r[0]["payload"].update(negative_tests_passed=False),
    lambda r: r[0]["payload"].update(region="us-east-1"),
    lambda r: r[0]["payload"].update(report_sha256="not-a-hash"),
    lambda r: r[0]["payload"].update(evidence_owner="notarai_operator"),
    lambda r: r[0]["payload"].update(evidence_type="unapproved_type"),
    lambda r: r[0]["payload"].update(claim_id="operator_controls_claim"),
    lambda r: r[0].update(signature_b64="tampered"),
    lambda r: r[0].pop("signature_b64"),
    lambda r: r[0]["payload"].update(schema="notarai.security-evidence.v99"),
    lambda r: r[0]["payload"].update(operator_override=True),
])
def test_k4_signed_receipt_tampering_fails_closed(tamper):
    _, roots, receipts = fixtures()
    tamper(receipts)
    report = evaluate(receipts, roots)
    assert report["claims"]["zero_trust"]["status"] == "FAIL"
    assert report["security_claims_commercially_verified"] is False


def test_k4_validly_signed_but_wrong_tenant_digest_expiry_and_failed_tests():
    keys, roots, receipts = fixtures()
    for field, value in [
        ("tenant", "pilot02"), ("image_sha256", "c" * 64),
        ("expires_at", "2026-11-22T11:59:59Z"),
        ("issued_at", "2026-11-22T12:01:00Z"),
        ("negative_tests_passed", False),
    ]:
        changed = copy.deepcopy(receipts)
        changed[0]["payload"][field] = value
        changed[0]["signature_b64"] = _sign(
            changed[0]["payload"], keys[changed[0]["payload"]["evidence_owner"]]
        )
        assert evaluate(changed, roots)["claims"]["zero_trust"]["status"] == "FAIL"


def test_k4_missing_or_incomplete_evidence_does_not_pass():
    _, roots, receipts = fixtures()
    assert evaluate(receipts[:1], roots)["claims"]["zero_trust"]["status"] == "BLOCKED"
    assert all(x["status"] == "UNVERIFIED"
               for x in evaluate()["claims"].values())
    del receipts[1]
    assert evaluate(receipts, roots)["claims"]["zero_trust"]["status"] == "BLOCKED"


def test_k4_untrusted_root_missing_or_replaced_is_rejected():
    _, roots, receipts = fixtures()
    assert evaluate(receipts, {})["claims"]["zero_trust"]["status"] == "FAIL"
    changed = copy.deepcopy(roots)
    changed[AUDITOR]["fingerprint_sha256"] = "0" * 64
    assert evaluate(receipts, changed)["claims"]["zero_trust"]["status"] == "FAIL"
    extra = ec.generate_private_key(ec.SECP256R1()).public_key()
    changed = copy.deepcopy(roots)
    changed[AUDITOR]["public_key_pem"] = extra.public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    assert evaluate(receipts, changed)["claims"]["zero_trust"]["status"] == "FAIL"


def test_k4_replay_duplicate_and_wrong_owner_fail():
    keys, roots, receipts = fixtures()
    dupe = copy.deepcopy(receipts)
    dupe.append(copy.deepcopy(dupe[0]))
    assert evaluate(dupe, roots)["claims"]["zero_trust"]["status"] == "FAIL"
    forged = copy.deepcopy(receipts)
    forged[0]["signature_b64"] = _sign(forged[0]["payload"], keys[CUSTODIAN])
    assert evaluate(forged, roots)["claims"]["zero_trust"]["status"] == "FAIL"


def test_k4_clock_must_be_explicitly_timezone_aware():
    with pytest.raises(ClaimsRejected):
        evaluate(now=datetime(2026, 11, 22, 12, 0))
    with pytest.raises(ClaimsRejected):
        evaluate(digest="not-hex")


def test_k5_scoped_zero_knowledge_never_means_no_guest_plaintext():
    data = policy()
    claim = next(c for c in data["claims"] if c["id"] == "scoped_zero_knowledge")
    assert "NOT strict" in claim["scope"]
    assert "Nitro in-memory plaintext" in claim["trust_boundary"]
    assert "no_unattested_ai_plaintext" in {
        e["id"] for e in claim["required_evidence"]
    }
    _, roots, receipts = fixtures()
    report = evaluate(receipts, roots)
    assert report["security_claims_commercially_verified"] is False
    assert any("Nitro" in item for item in report["limitations"])


@pytest.mark.parametrize("action", ["submit", "sign", "register", "file"])
def test_k6_legal_actions_remain_deny_only(action):
    data = policy()
    assert data["auto_actions"][action] is False
    data["auto_actions"][action] = True
    with pytest.raises(ClaimsRejected, match="AUTO"):
        validate_policy(data)


def test_source_matrix_must_not_be_manually_marked_pass():
    data = policy()
    data["claims"][0]["status"] = "PASS"
    with pytest.raises(ClaimsRejected):
        validate_policy(data)


def test_source_matrix_rejects_missing_attack_scenarios():
    data = policy()
    data["threats"] = data["threats"][:5]
    with pytest.raises(ClaimsRejected):
        validate_policy(data)


@pytest.mark.parametrize("alter", [
    lambda p: p["claims"][1]["required_evidence"].pop(0),
    lambda p: p["claims"][1]["required_evidence"][0].update(
        owner="independent_auditor"
    ),
    lambda p: p["claims"][3]["required_evidence"][-2].update(
        id="fake_operator_signed_review"
    ),
    lambda p: p["claims"][0]["required_evidence"][0].update(
        source="live_aws"
    ),
    lambda p: p["threats"].pop(5),  # 11 threats, but a mandatory one is missing
])
def test_operator_cannot_downgrade_mandatory_claims_or_attacks(alter):
    data = policy()
    alter(data)
    with pytest.raises(ClaimsRejected):
        validate_policy(data)


@pytest.mark.parametrize("wrong", [
    ["invalid", "kind"], {}, None, 0, False,
])
def test_unhashable_or_wrong_type_evidence_returns_fail_not_exception(wrong):
    _, roots, receipts = fixtures()
    receipts[0]["payload"]["evidence_type"] = wrong
    report = evaluate(receipts, roots)
    assert report["claims"]["zero_trust"]["status"] == "FAIL"


def test_malformed_receipt_claim_id_returns_fail_not_exception():
    _, roots, receipts = fixtures()
    receipts[0]["payload"]["claim_id"] = ["not", "hashable"]
    report = evaluate(receipts, roots)
    assert report["claims"]["zero_trust"]["status"] == "FAIL"


def test_malformed_evidence_policy_cannot_hijack_verifier():
    data = policy()
    data["claims"][0]["required_evidence"][0]["owner"] = ["not", "hashable"]
    with pytest.raises(ClaimsRejected):
        validate_policy(data)


def test_independent_witnesses_cannot_share_same_signing_key():
    _, roots, receipts = fixtures()
    roots["independent_custodian"] = copy.deepcopy(roots["independent_auditor"])
    with pytest.raises(ClaimsRejected, match="share a signing key"):
        evaluate(receipts, roots)
