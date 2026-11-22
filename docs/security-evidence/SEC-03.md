# SEC-03 — Evidence ledger (2026-11-22)

**PR:** https://github.com/plnyspolka-pixel/notarai/pull/68
**Executor:** ChatGPT, code changes on dedicated SEC-03 branch.
**Overall:** **BLOCKED / DRAFT. Not verified Zero Knowledge, Zero Operator Access or Zero Trust.**
**No real-client records, live KMS calls, Nitro launch or production deployment were used.**

The offline unit and integration tests constitute only reproducible *software*
evidence. Their success cannot prove behavior of an AWS operator, real KMS
custody, client distribution or enclave hardware.

## Per-criterion evidence

| Criterion | Current result | Code/test and missing proof |
| --- | --- | --- |
| K1 — zero plaintext reaching backend | **BLOCKED** | `confidential/router.py` rejects new v1 uploads, validates v2 pinned key and writes ciphertext conditionally to versioned S3. Two synthetic uploads inspected by `test_two_synthetic_uploads_never_store_plaintext_or_dek`. Needs real endpoint capture + logging/telemetry and all alternative upload paths audited before PASS. |
| K2 — AAD & five negative controls | **BLOCKED** | `confidential/envelope.py` / `static/confidential-crypto.js` v2 bind tenant+case+object+128-bit random logical version+key ARN+public-key SHA-256. Negative tests cover tenant/object/case/version/pin/ARN/tag, duplicate S3 object writes. **Actual AWS S3 VersionId is only assigned after upload and cannot be included in pre-upload AEAD AAD**. It is pinned separately in the existing S3->DynamoDB job ledger; replay across distinct permitted jobs is not globally prevented. Add durable cryptographic-version mapping and one-time-use policy if the threat model requires strict anti-replay. |
| K3 — creation/wrap/rotation/revocation | **BLOCKED** | Browser creates random DEK and RSA-OAEP wraps using pinned custodian public key, decryption only through existing attested unwrap API. `confidential/zk_recovery.py` provides signed **authorization only**, not actual rotate/revoke or KMS custody implementation. Live custodian key and lifecycle proofs pending. |
| K4 — malicious JS/release | **BLOCKED** | `confidential/client_release.py` verifies Ed25519 signed tenant-specific releases, file SHA-256, key pin and expiration. Negative tests reject modified JS, signature and trust key. **Verifier plus trusted signing public key must be independently delivered and user-verifiable**. The operator-hosted website, its CSP/SRI, and self-hosted verifier are not an independent trust anchor. No independent distribution exists yet. |
| K5 — recovery / revoked authority | **BLOCKED** | Two independent Ed25519 approvals required by `confidential/zk_recovery.py`; tests cover missing signer, wrong tenant, wrong key and expired authorization. This does NOT decrypt, rewrap or revoke KMS. Need tested policy with external custodian and recovery trustee, single-use request IDs, tenant identity/legal succession, Nitro-only recovery/re-encryption, backups/retention; no administrator override. |
| K6 — operator decrypt denied and Nitro positive | **BLOCKED** | No decrypt/recovery/sign/submit route exposed in confidential web API; new Nitro worker denies version-1 ciphertext. No real hardware KMS Recipient / PCR tests (SEC-07), independent operator denial or Organizations control audit. |

## Files implemented

- `static/confidential-crypto.js`: v2 browser AES-256-GCM + RSA-OAEP envelope and fresh logical version.
- `confidential/envelope.py`: strict v2 parser and authenticated context, with legacy v1 parse retained solely for prior offline compatibility; live worker requires v2.
- `confidential/router.py`: authenticated scoped ciphertext-only ingest; strict v2 and public-key pin; S3 `IfNoneMatch=*`, requires actual S3 VersionId.
- `confidential/worker.py`: fail closed on legacy ciphertext; no submit.
- `scripts/confidential_pilot_fixture.py`: synthetic v2 fixture.
- `confidential/client_release.py`: independent release signature/hash verifier (not independently distributed).
- `confidential/zk_recovery.py`: signed dual-approval recovery/rotation/revocation *admission only*.
- `test_confidential_zk_client_encryption.py`: unit + backend stub + tamper/replay + release/recovery tests.
- `.github/workflows/confidential-browser.yml`: executes mandatory new test suite.

## Reproducible test commands

```sh
python -m pytest -q test_confidential_zk_client_encryption.py
python -m pytest -q test_confidential.py test_confidential_worker.py test_confidential_interop.py
```

**CI run:** see the current HEAD of PR #68 and the matching
`NotarAI Confidential Browser - chromium smoke` check; do not reuse green
checks from previous SHAs. No claim of PASS before CI finishes on latest HEAD.

## Unresolved architectural security boundaries

1. Browser-generated logical version is **not the post-upload S3 VersionId**.
   The application knows the latter only after S3 accepted the request. Existing
   queue ledger pins S3 VersionId, but independent anti-replay authorization must
   be demonstrated in production.
2. Existing v1 documents require a reviewed migration or explicit decommissioning:
   the new guest rejects them. Do not silently make a legacy decrypt fallback.
3. A custodian may unilaterally change KMS policy unless independent governance
   and external evidence of ownership / AWS Organizations separation exist.
4. The browser executes code delivered by NotarAI. Until a separate signed,
   pinned client is distributed and verified outside the web origin, claiming
   strict Zero Knowledge against a malicious operator is false.
5. Allowed confidential inference or browser automation inevitably has transient
   plaintext inside the explicitly trusted Nitro guest. If any plaintext leaves
   Nitro for Bedrock or a website, unqualified Zero Knowledge is false.
6. Browser encryption is a separate opt-in confidential pathway. Other NotarAI
   document upload routes are not made ciphertext-only by this PR.

**Release gate:** K1–K6 must all independently become PASS, no skipped critical
scenarios, fresh green CI and external evidence before review-ready or marketing.
