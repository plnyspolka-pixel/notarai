"""Evidence-gated security claims for synthetic NotarAI Confidential workloads.

This module does not query AWS, attest Nitro hardware, or certify a product.
A PASS means only that the provided signed evidence receipts satisfy the
configured structural rules and independently supplied trust-root fingerprints.
The evidence's *substantive truth* needs independent testing and SEC-13 review.
No marketing claim may be inferred directly from this module.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

CLAIMS = frozenset({
    "zero_trust", "zero_operator_access", "confidential_computing",
    "scoped_zero_knowledge",
})
OWNERS = frozenset({"independent_custodian", "independent_auditor"})
SOURCES = frozenset({"live_aws", "independent_audit"})
_ALLOWED_STATUS = frozenset({"UNVERIFIED", "BLOCKED", "FAIL", "PASS"})
# A source-controlled policy must never downgrade the mandatory security
# evidence types/owners. Review of policy changes is NOT a replacement for
# independent approval of the deployed code hash (SEC-05).
_MANDATORY_EVIDENCE = {
    "zero_trust": {
        "authenticated_tenant_scope": ("independent_auditor", "independent_audit"),
        "live_iam_deny": ("independent_auditor", "independent_audit"),
        "cross_tenant_live_deny": ("independent_auditor", "independent_audit"),
    },
    "zero_operator_access": {
        "independent_custody": ("independent_custodian", "live_aws"),
        "nitro_kms_allow_deny": ("independent_auditor", "independent_audit"),
        "approved_release_enforced": ("independent_custodian", "live_aws"),
        "plaintext_exfil_deny": ("independent_auditor", "independent_audit"),
        "independent_penetration_audit": ("independent_auditor", "independent_audit"),
    },
    "confidential_computing": {
        "hardware_nsmlive": ("independent_auditor", "independent_audit"),
        "pcr17_image_binding": ("independent_custodian", "live_aws"),
        "kms_recipient_ciphertext_only": ("independent_auditor", "independent_audit"),
    },
    "scoped_zero_knowledge": {
        "client_encryption_audit": ("independent_auditor", "independent_audit"),
        "frontend_supply_chain_independence": ("independent_auditor", "independent_audit"),
        "no_unattested_ai_plaintext": ("independent_auditor", "independent_audit"),
        "plaintext_lifecycle_audit": ("independent_auditor", "independent_audit"),
        "independent_penetration_audit": ("independent_auditor", "independent_audit"),
    },
}
_MANDATORY_THREATS = frozenset("TH-%02d" % i for i in range(1, 13))

_HEX64 = re.compile(r"^[a-f0-9]{64}$")
_HEX32 = re.compile(r"^[a-f0-9]{32}$")
_TENANT = re.compile(r"^pilot0[12]$")
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_EVIDENCE_DOMAIN = b"NotarAI:independent-security-evidence:v1\x00"
_REQUIRED_CLAIM_KEYS = frozenset({
    "id", "scope", "trust_boundary", "required_evidence", "evidence_owner",
    "negative_test", "expires_at", "status",
})
_REQUIRED_THREAT_KEYS = frozenset({
    "id", "attack", "trust_boundary", "control", "negative_test",
    "owner", "claim_ids",
})
_REQUIRED_EVIDENCE_KEYS = frozenset({"id", "owner", "source"})
_REQUIRED_PAYLOAD_KEYS = frozenset({
    "schema", "evidence_id", "claim_id", "evidence_type", "evidence_owner",
    "source", "tenant", "region", "image_sha256", "issued_at", "expires_at",
    "negative_tests_passed", "report_id", "report_sha256",
})


class ClaimsRejected(ValueError):
    """Fail closed. Never include source documents in the exception text."""


def _require(ok: bool, reason: str) -> None:
    if not ok:
        raise ClaimsRejected(reason)


def _utc(value: Any) -> datetime:
    _require(isinstance(value, str) and bool(_UTC.fullmatch(value)),
             "invalid UTC timestamp")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc,
        )
    except ValueError:
        raise ClaimsRejected("invalid UTC timestamp") from None


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and 0 < len(value) <= 300 and bool(value.strip())


def validate_policy(policy: Mapping) -> None:
    """Validate the source-controlled matrix; it cannot self-promote to PASS."""
    _require(isinstance(policy, Mapping) and set(policy) == {
        "schema", "region", "environment", "allowed_tenants",
        "auto_actions", "claims", "threats",
    }, "security policy schema invalid")
    _require(policy["schema"] == "notarai.security-claims.v1" and
             policy["region"] == "eu-central-1" and
             policy["environment"] == "synthetic_only" and
             policy["allowed_tenants"] == ["pilot01", "pilot02"],
             "security scope unsupported")
    _require(policy["auto_actions"] == {
        "submit": False, "sign": False, "register": False, "file": False,
    }, "AUTO legal submission/signing is prohibited")
    claims = policy["claims"]
    threats = policy["threats"]
    _require(isinstance(claims, list) and len(claims) == 4 and
             isinstance(threats, list) and len(threats) >= 10,
             "threat/claim coverage incomplete")
    ids: set[str] = set()
    for claim in claims:
        _require(isinstance(claim, dict) and set(claim) == _REQUIRED_CLAIM_KEYS,
                 "claim fields invalid")
        cid = claim["id"]
        _require(isinstance(cid, str) and cid in CLAIMS and cid not in ids,
                 "invalid or duplicate security claim")
        ids.add(cid)
        _require(_nonempty(claim["scope"]) and
                 _nonempty(claim["trust_boundary"]) and
                 _nonempty(claim["evidence_owner"]) and
                 _nonempty(claim["negative_test"]) and
                 claim["expires_at"] is None and
                 claim["status"] == "UNVERIFIED",
                 "source matrix must remain unverified without evidence")
        required = claim["required_evidence"]
        _require(isinstance(required, list) and len(required) >= 3,
                 "claim requires at least 3 independently checked proofs")
        seen = set()
        for item in required:
            _require(isinstance(item, dict) and
                     set(item) == _REQUIRED_EVIDENCE_KEYS and
                     _nonempty(item["id"]) and item["id"] not in seen and
                     isinstance(item["owner"], str) and item["owner"] in OWNERS and
                     isinstance(item["source"], str) and item["source"] in SOURCES,
                     "required evidence not independently specified")
            seen.add(item["id"])
        found = {item["id"]: (item["owner"], item["source"])
                 for item in required}
        _require(all(found.get(k) == v
                     for k, v in _MANDATORY_EVIDENCE[cid].items()),
                 "mandatory evidence or independent owner removed")
    _require(ids == CLAIMS, "security claims missing")
    seen_threats: set[str] = set()
    for threat in threats:
        _require(isinstance(threat, dict) and set(threat) == _REQUIRED_THREAT_KEYS,
                 "threat record incomplete")
        tid = threat["id"]
        _require(isinstance(tid, str) and
                 re.fullmatch(r"TH-[0-9]{2}", tid) is not None and
                 tid not in seen_threats, "duplicate or invalid threat")
        seen_threats.add(tid)
        _require(all(_nonempty(threat[k]) for k in (
            "attack", "trust_boundary", "control", "negative_test",
            "owner",
        )) and threat["owner"] in OWNERS and
                 isinstance(threat["claim_ids"], list) and
                 bool(threat["claim_ids"]) and
                 set(threat["claim_ids"]) <= CLAIMS,
                 "attack scenario lacks negative test or accountable owner")
    _require(all(c["negative_test"] in seen_threats for c in claims),
             "claim does not reference existing attack test")
    _require(_MANDATORY_THREATS <= seen_threats,
             "mandatory adversarial security scenarios removed")


def canonical_evidence_bytes(payload: Mapping) -> bytes:
    """Canonical ECDSA message with protocol domain separation."""
    _require(isinstance(payload, dict) and
             set(payload) == _REQUIRED_PAYLOAD_KEYS and
             payload.get("schema") == "notarai.security-evidence.v1",
             "signed evidence fields invalid")
    try:
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True,
                             separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError):
        raise ClaimsRejected("signed evidence not serializable") from None
    return _EVIDENCE_DOMAIN + encoded


def public_key_fingerprint(public_pem: bytes) -> str:
    """SHA256 fingerprint of P-256 SubjectPublicKeyInfo DER, not PEM text."""
    try:
        key = serialization.load_pem_public_key(public_pem)
    except (TypeError, ValueError):
        raise ClaimsRejected("independent public key unreadable") from None
    _require(isinstance(key, ec.EllipticCurvePublicKey) and
             isinstance(key.curve, ec.SECP256R1),
             "independent key is not ECDSA P-256")
    der = key.public_bytes(serialization.Encoding.DER,
                           serialization.PublicFormat.SubjectPublicKeyInfo)
    return hashlib.sha256(der).hexdigest()


def _verify_receipt(receipt: Mapping, expected: Mapping, *, claim_id: str,
                    tenant: str, digest: str, roots: Mapping, now: datetime) -> None:
    _require(isinstance(receipt, Mapping) and
             set(receipt) == {"payload", "signature_b64"},
             "unsigned or malformed security evidence")
    payload = receipt["payload"]
    signed = canonical_evidence_bytes(payload)
    _require(payload["claim_id"] == claim_id and
             payload["evidence_type"] == expected["id"] and
             payload["evidence_owner"] == expected["owner"] and
             payload["source"] == expected["source"],
             "security evidence belongs to another claim or witness")
    _require(payload["tenant"] == tenant and
             payload["region"] == "eu-central-1" and
             payload["image_sha256"] == digest and
             isinstance(payload["evidence_id"], str) and
             _HEX32.fullmatch(payload["evidence_id"]) is not None and
             isinstance(payload["report_sha256"], str) and
             _HEX64.fullmatch(payload["report_sha256"]) is not None and
             _nonempty(payload["report_id"]) and
             len(payload["report_id"]) <= 64 and
             re.fullmatch(r"[A-Za-z0-9_-]+", payload["report_id"]) is not None,
             "evidence not bound to approved tenant/image/report")
    _require(payload["negative_tests_passed"] is True,
             "negative scenario failed or not demonstrated")
    issued = _utc(payload["issued_at"])
    expires = _utc(payload["expires_at"])
    _require(issued <= now < expires and
             expires - issued <= timedelta(days=7) and
             expires > issued, "evidence missing, future-dated or expired")
    root = roots.get(expected["owner"])
    _require(isinstance(root, Mapping) and
             set(root) == {"public_key_pem", "fingerprint_sha256"},
             "independent trust root unavailable")
    pem, pin = root["public_key_pem"], root["fingerprint_sha256"]
    _require(isinstance(pem, bytes) and isinstance(pin, str) and
             _HEX64.fullmatch(pin) is not None and
             public_key_fingerprint(pem) == pin,
             "trusted public key fingerprint mismatch")
    signature = receipt["signature_b64"]
    _require(isinstance(signature, str), "independent evidence signature missing")
    try:
        decoded = base64.b64decode(signature, validate=True)
    except (binascii.Error, ValueError):
        raise ClaimsRejected("independent evidence signature encoding invalid") from None
    _require(bool(decoded), "independent evidence signature missing")
    try:
        key = serialization.load_pem_public_key(pem)
        key.verify(decoded, signed, ec.ECDSA(hashes.SHA256()))
    except (InvalidSignature, ValueError, TypeError):
        raise ClaimsRejected("independent signature verification failed") from None


def evaluate_claims(policy: Mapping, evidence: list | None = None, *,
                    trust_roots: Mapping | None = None, tenant: str = "pilot01",
                    image_sha256: str = "0" * 64,
                    now: datetime | None = None) -> dict:
    """Report evidence status, with commercial clearance ALWAYS false.

    PASS refers only to signatures and schema, not external provenance truth.
    Never use this output alone to enable a marketing label or decrypt.
    """
    validate_policy(policy)
    _require(isinstance(tenant, str) and _TENANT.fullmatch(tenant) is not None and
             isinstance(image_sha256, str) and
             _HEX64.fullmatch(image_sha256) is not None,
             "tenant or image binding invalid")
    moment = now if now is not None else datetime.now(timezone.utc)
    _require(isinstance(moment, datetime) and moment.tzinfo is not None,
             "timezone-aware validation clock required")
    moment = moment.astimezone(timezone.utc)
    receipts = [] if evidence is None else evidence
    _require(isinstance(receipts, list) and
             len(receipts) <= 256, "evidence batch invalid")
    roots = {} if trust_roots is None else trust_roots
    _require(isinstance(roots, Mapping), "independent roots invalid")
    result: dict[str, dict] = {}
    seen_receipts: set[str] = set()
    for claim in policy["claims"]:
        cid = claim["id"]
        matches = []
        wrong = 0
        for receipt in receipts:
            if not isinstance(receipt, Mapping) or not isinstance(
                receipt.get("payload"), Mapping
            ):
                wrong += 1
                continue
            if receipt["payload"].get("claim_id") == cid:
                matches.append(receipt)
            elif not isinstance(receipt["payload"].get("claim_id"), str) or receipt["payload"].get("claim_id") not in CLAIMS:
                wrong += 1
        required = {item["id"]: item for item in claim["required_evidence"]}
        missing = sorted(set(required))
        issues = []
        for item in matches:
            payload = item["payload"]
            kind = payload.get("evidence_type")
            rid = payload.get("evidence_id")
            if not isinstance(kind, str) or kind not in required or not isinstance(rid, str) or rid in seen_receipts:
                issues.append("unexpected or replayed evidence")
                continue
            seen_receipts.add(rid)
            try:
                _verify_receipt(item, required[kind], claim_id=cid, tenant=tenant,
                                digest=image_sha256, roots=roots, now=moment)
            except ClaimsRejected:
                issues.append("invalid, unsigned, expired or untrusted proof")
            else:
                if kind in missing:
                    missing.remove(kind)
                else:
                    issues.append("duplicate evidence kind")
        if issues or wrong:
            status = "FAIL"
        elif not matches:
            status = "UNVERIFIED" if not receipts else "BLOCKED"
        elif missing:
            status = "BLOCKED"
        else:
            status = "PASS"
        _require(status in _ALLOWED_STATUS, "unknown internal claim status")
        result[cid] = {
            "status": status,
            "missing_evidence": missing,
            "rejected_evidence": len(issues) + wrong,
            "required_evidence_count": len(required),
            "accepted_evidence_count": len(required) - len(missing),
        }
    return {
        "schema": "notarai.security-claims-report.v1",
        "region": "eu-central-1",
        "tenant": tenant,
        "image_sha256": image_sha256,
        "claims": result,
        "security_claims_commercially_verified": False,
        "limitations": [
            "Signed assertions are not hardware attestation; independent live checks remain necessary",
            "Public-key fingerprints must be delivered out of band by external owners",
            "Zero Knowledge does not mean Nitro never processes plaintext",
            "No autonomous legal submission, signature or registration",
            "Commercial GO/NO-GO requires separate independent SEC-13 audit",
        ],
    }
