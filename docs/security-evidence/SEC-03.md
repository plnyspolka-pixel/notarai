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
| K2 — AAD, replay & provenance | **BLOCKED** | `confidential/envelope.py` / `static/confidential-crypto.js` v2 bind tenant+case+object+128-bit random logical version+key ARN+public-key SHA-256. Negative tests cover tenant/object/case/version/pin/ARN/tag, duplicate S3 object writes. **Actual AWS S3 VersionId is only assigned after upload and cannot be included in pre-upload AEAD AAD**. It is pinned separately in the existing S3->DynamoDB job ledger; replay across distinct permitted jobs is not globally prevented. Add durable cryptographic-version mapping and one-time-use policy if the threat model requires strict anti-replay. |
| K3 — creation/wrap/rotation/revocation | **BLOCKED** | Browser creates fresh DEK and RSA-OAEP wraps with pinned public key. `confidential/zk_migration.py` now implements Nitro-only synthetic decrypt/re-encrypt to a fresh key + NEW object ID, requiring two externally signed authorizations, target tenant, target key fingerprint, and custody `claim_once`. `confidential/custody_nonce.py` and `infra/notarai-confidential-custody-recovery.yaml` implement a separate immutable approval nonce ledger. **No live KMS key migration, verified custody account, actual revoke, external signature issuance, or backup-key recovery proof yet.** |
| K4 — malicious JS/release | **BLOCKED** | `scripts/build_custodian_browser_client.py` creates a network-disabled, offline encrypting `client.html` and Ed25519-signed release manifest; `confidential/client_release.py` verifies artifact hash, tenant, KMS ARN, pin, expiration and signature. `scripts/verify_custodian_client_browser.py` performs synthetic Chromium download/AEAD smoke. `static/confidential-courier.html/.js` is a ciphertext-only same-origin importer. **No independently hosted/signed custodian release, verified signer custody or full onboarding yet; operator-hosted JS is never an independent trust root.** | `confidential/client_release.py` verifies Ed25519 signed tenant-specific releases, file SHA-256, key pin and expiration. Negative tests reject modified JS, signature and trust key. **Verifier plus trusted signing public key must be independently delivered and user-verifiable**. The operator-hosted website, its CSP/SRI, and self-hosted verifier are not an independent trust anchor. No independent distribution exists yet. |
| K5 — recovery / revoked authority | **BLOCKED** | `confidential/zk_recovery.py` requires distinct custodian + trustee Ed25519 signatures and binds tenant, source/target object, original logical version, old and new KMS keys and replacement public key pin. `confidential/zk_migration.py` performs pure software migration logic guarded by Nitro and a custodian-controlled one-time ledger. **No production custodian process, no verified identity/succession, no KMS disable/delete rights enforcement, no confirmed backup/retention policy. A permanently lost KMS private key remains unrecoverable without a separately provisioned recovery path.** | Two independent Ed25519 approvals required by `confidential/zk_recovery.py`; tests cover missing signer, wrong tenant, wrong key and expired authorization. This does NOT decrypt, rewrap or revoke KMS. Need tested policy with external custodian and recovery trustee, single-use request IDs, tenant identity/legal succession, Nitro-only recovery/re-encryption, backups/retention; no administrator override. |
| K6 — operator decrypt denied and Nitro positive | **BLOCKED** | No normal decrypt/recovery/sign/submit web API. `scripts/verify_sec03_operator_denial.py` performs explicit-flag synthetic RSA-OAEP KMS Decrypt denial probe for the nominated operator principal, with real AWS identities and independently pinned public key. **Not run with live profiles; hardware Nitro + PCR evidence requires SEC-07. Denial of one IAM principal cannot prove operator/root/Organizations separation.** | No decrypt/recovery/sign/submit route exposed in confidential web API; new Nitro worker denies version-1 ciphertext. No real hardware KMS Recipient / PCR tests (SEC-07), independent operator denial or Organizations control audit. |

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


## Additional finding: independently authenticated document origin

**Do not conflate AEAD integrity with document provenance.** Anyone with the
custodian's PUBLIC RSA key can generate a different valid DEK + ciphertext
envelope without learning the original plaintext. Consequently, a malicious
operator controlling the web backend and same-account DynamoDB can substitute
an entirely new ciphertext envelope unless the guest checks independently
trusted document *origin* approval.

`confidential/document_authenticity.py` now contains an Ed25519 verifier for a
receipt binding tenant, case, object, logical version, exact S3 VersionId,
ciphertext SHA-256, KMS ARN, public key pin, issuer and expiry. Negative tests
reject changed digest, S3 version, tenant, expired signature and wrong signer.

**IMPORTANT: the receipt verifier is not yet wired into Nitro admission.**
Independent issuer enrollment, notary authentication, receipt generation after
S3 VersionId is known, fixed public key pin in attested release, and receipt
fetch from independently controlled custody storage remain integration
dependencies. It would be dishonest to mark malicious-operator document
provenance PASS until that integration and live tests exist. This is not a
shipped forgery defense.

## Offline software changes since the initial report

- `confidential/document_registry.py`: DDB reservation before S3, conditional
  finalize, one-use preview claim, and exact digest / S3 version checks in
  guest and download. S3 `IfNoneMatch=*` alone permits a new write after
  a current delete marker; the registry prevents accidental re-use without
  claims of immunity to a malicious AWS account administrator.
- `confidential/router.py`: dedicated opaque v2 upload, committed version
  validation on download, one-use queue admission.
- `confidential/worker.py`: strict v2 + registry verification before unwrap.
- `scripts/confidential_pilot_fixture.py`: synthetic fixture now reserves,
  uploads and admits the same immutable document version.
- `scripts/build_custodian_browser_client.py` +
  `scripts/verify_custodian_client_browser.py`: independently signable
  single-file offline HTML encryption + browser E2E (not deployed).
- `static/confidential-courier.html` and `static/confidential-courier.js`:
  operator-hosted ciphertext import only; external plaintext is never
  handed to this page. Import triggers preview only when explicitly requested.
- `confidential/zk_migration.py`, `confidential/zk_recovery.py`,
  `confidential/custody_nonce.py`: nonce and signed-recovery prerequisites
  for a new immutable document, without a support/admin decrypt API.
- `infra/notarai-confidential-custody-recovery.yaml`: separate DDB table in
  *custodian account*, no grants for NotarAI operator.
- `scripts/verify_sec03_operator_denial.py`: opt-in synthetic live probe;
  dry-run must never talk to AWS.
- `test_confidential_courier_js.js`, `test_confidential_client_bundle.py`,
  `test_confidential_zk_client_encryption.py`: negative checks and mocks.

### Exact non-AWS commands

```sh
python -m pytest -q test_confidential_zk_client_encryption.py test_confidential_client_bundle.py test_confidential_worker.py test_confidential_auto.py test_confidential_interop.py
node --check static/confidential-courier.js
node test_confidential_courier_js.js
python -m scripts.build_custodian_browser_client --help
python -m scripts.verify_sec03_operator_denial --help
```

**Gate still unresolved:** latest HEAD SHA CI conclusion, real two-account
AWS KMS and attested Nitro, trusted client publication and independently
signed origin receipt, verified recovery/custody operations. Synthetic tests
are not a substitute for external evidence. Never release to notarial client
production or market unqualified Zero Knowledge based on this report.
