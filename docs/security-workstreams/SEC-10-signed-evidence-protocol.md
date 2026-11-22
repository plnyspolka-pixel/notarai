# SEC-10 — Three-party retention evidence protocol (draft v1)

**Purpose:** enable a separate, independently operated evidence collector, notary/controller and custodian to sign the *same* metadata-only assessment. No signing key, document body, object name, case number or DEK should be placed in GitHub, a user-facing API argument, a log, or a telemetry payload.

This is a **read-only human-review eligibility** protocol. No approval to erase, restore, export or decrypt data is produced by successful verification.

## Wire contract

The verifier in `confidential/signed_retention_evidence.py` accepts:

- Exact UTF-8 bytes of canonical JSON (maximum **8192 bytes**).
- **64-byte raw Ed25519 signature**, once per role: `collector`, `controller`, `custodian`.
- Three distinct **32-byte raw Ed25519 public keys** pinned out of band in a controlled trust configuration, with key identity, owner, rotation and revocation policy.
- `ExpectedScope` independently obtained from the authenticated case and review ledger, not echoed from the sender's JSON.

The JSON structure is a *flat dictionary* with exactly these keys (shown in canonical sorted-key order; actual dates/digests must come from independently verified facts):

```json
{
  "approved_retention_until": "2026-11-21T05:00:00Z",
  "aws_account": "111122223333",
  "backups_verified_expired": true,
  "cloud_audit_retention_exempted_with_legal_basis": true,
  "ddb_pitr_verified_expired": true,
  "inventory_sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
  "legal_hold": "cleared",
  "legal_policy_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "observed_at": "2026-11-22T04:55:00Z",
  "replicas": "none-verified",
  "request_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "s3_all_versions_listed": true,
  "s3_delete_markers_included": true,
  "s3_pagination_complete": true,
  "schema": "notarai.sec10.retention.v1",
  "tenant_id": "pilot01"
}
```

**Important:** The example above uses **synthetic** values and pretty-printed JSON **only for readability**; do not sign or submit the displayed whitespace. The signed payload must be regenerated with:

```python
canonical = json.dumps(
    evidence, sort_keys=True, separators=(",", ":"),
    ensure_ascii=True, allow_nan=False
).encode("utf-8")
```

The message to sign (no hashing step inserted by the application) is:

```python
message = (b"NOTARAI-SEC10-RETENTION-EVIDENCE-V1\x00"
           + role.encode("ascii") + b"\x00" + canonical)
signature = signer_ed25519_private_key.sign(message)
```

Transport may encode the raw signature as base64, but must decode it to **exactly 64 bytes** before verification. Never supply a private signing key to NotarAI application infrastructure. Each signer signs the **identical canonical payload** but with their own role-separated message. A signature for one role is not interchangeable with another.

## Mandatory independent controls BEFORE integration

1. **Key custody:** independent public-key distribution and pinning; prove that all three private signers are separate, rotated and revocable. Operator cannot change the trust set using its own API or deployment rights.
2. **Evidence source:** real inventory collector measures **every S3 version and deletion marker**, backup recovery horizon, replica, PITR window and legal hold; signed *booleans* are claims, not proofs of AWS state.
3. **Legal approval:** controller and legal reviewer approve the actual statutory/contractual retention schedule. A signed `approved_retention_until` does not itself establish its legality.
4. **Request binding:** independently bind `tenant_id`, `aws_account`, `request_sha256`, policy and inventory digests to the review ledger; reject cross-account/cross-tenant substitution.
5. **Freshness and replay:** reject observations older than 24 hours and future observations. Separately enforce a durable, **single-use** request/approval state via an independently controlled atomic ledger; signatures alone do not prevent exact-scope replay.
6. **Immutable evidence retention:** record sanitized hashes, trusted signer identities, timestamps, scoped policy and reviewer decision in a legally approved audit system. Do not store plaintext, credentials, object keys or private signing keys in the evidence ledger.
7. **Review-only release:** successful `assess_signed_retention` returns `ready_for_independent_review` **not** permission to issue `s3:DeleteObjectVersion`, change KMS policies, remove logs, recover records or mark legal destruction complete.

## Verification in isolated CI

```sh
python -m pytest -q test_confidential_signed_retention_evidence.py
```

The test suite generates disposable test-only signing keys and covers role confusion, tampering, wrong tenant/account/request, wrong policy/inventory digest, changed deadline/hold, duplicate JSON keys, noncanonical encodings, stale/future observations and bad trust anchors. **No AWS call, live attestation or destructive operation is performed.**

## AWS deployment boundary

Amazon ECS `CONFIDENTIAL_SANDBOX` requires **ECS Managed Instances**, `awsvpc` and an attestation policy. See:
- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ict-getting-started.html
- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ict-confidential-policy-configuration.html

This signed evidence protocol is separate from hardware attestation for confidential **decryption**, and it must not be represented as equivalent to Nitro attestation, a certified qualified trust service or legal record-erasure attestation.
