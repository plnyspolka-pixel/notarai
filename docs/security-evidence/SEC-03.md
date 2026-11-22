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
| K2 — AAD, replay & provenance | **BLOCKED** | AEAD v2 binds tenant/case/object/logical-version/KMS ARN/public-key pin. The DocumentVersionRegistry durably reserves one S3 VersionId per object ID and allows only one preview admission. Actual S3 VersionId arrives after encryption, so an independent Ed25519 origin receipt signs the exact ciphertext SHA-256 and S3 version, verified in Nitro before KMS. Live S3/Org admin threat model, issuer enrollment and hardware evidence are pending. |
| K3 — creation/wrap/rotation/revocation | **BLOCKED** | Browser creates fresh DEK, RSA-OAEP wraps under pinned custody public key. zk_migration.py now requires recovery.v2 approvals binding exact source SHA-256, S3 VersionId and old KMS pin; signer keys are loaded ONLY from the measured image via recovery_trust.py. The custody nonce ledger verifies external AWS STS account identity. No live key rotation, key-wide KMS DisableKey/revocation, attestation or backup recovery proof yet. |
| K4 — malicious JS/release | **BLOCKED** | Separate no-network HTML encryption client with Ed25519 signed release; synthetic Chromium E2E checks the actual client encrypt/download path. The operator-hosted courier accepts only ciphertext and a separate origin receipt. Production client origin and signing key remain unverified until independently published and pinned outside operator control. |
| K5 — recovery / revoked authority | **BLOCKED** | Two externally pinned Ed25519 signer keys and source SHA-256/S3 version/old key pin are now required. Negative tests reject forged approvers, missing root, wrong tenant, tampered original, source version, replay, forged clock and mismatched custody AWS session. No live secure transfer of custody credentials into attested Nitro, legal succession, tenant-wide KMS revocation, backup or retention evidence. A permanently destroyed KMS key is not recoverable without a separately provisioned recovery path. |
| K6 — operator decrypt denied and Nitro positive | **BLOCKED** | No normal decrypt/recovery/submit web API; synthetic operator KMS Decrypt denial probe available by explicit flag. Nitro worker refuses missing origin trust root and uses attested KMS Recipient. No separate live AWS account test, hardware PCR proof or operator-root/Organizations boundary audit. |

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

## SEC-03 — dodatkowe zabezpieczenia odzyskiwania (testy syntetyczne)

- Podpisy kustosza i powiernika nie mogą być już zweryfikowane kluczami dostarczonymi przez operatora. Moduł confidential/recovery_trust.py odczytuje dwa różne klucze Ed25519 z niezależnie zatwierdzonego obrazu Nitro, związane z tenantem, starym KMS ARN, pinem starego klucza i wygaśnięciem.
- Zgoda recovery.v2 obejmuje oryginalny SHA-256 ciphertextu, S3 VersionId, stary pin KMS, cel migracji i nowy pin. Zmiana choć jednego pola unieważnia podpis.
- Rejestr nonce w osobnym koncie kustosza weryfikuje AWS STS i tworzy klienta DynamoDB z tej samej sesji. Nie jest to jeszcze dowód niezależnej kontroli Organizations ani rozwiązanie bezpiecznego dostarczenia poświadczeń do Nitro.
- confidential/Dockerfile dopuszcza opcjonalny niezależnie sprawdzany SHA-256 obu publicznych trust rootów. Bez nich operacja recovery odmawia działania; zwykłe obrazy CI celowo ich nie zawierają.
- test_confidential_recovery_trust.py oraz test_confidential_zk_client_encryption.py sprawdzają podrobione podpisy dwóch własnych kluczy operatora, brak kluczy kustosza, niezgodny SHA/S3, replay i manipulację zegarem.

**Brak wykonanej revocation:** samo podpisane action=revoke nie wyłącza KMS ani nie usuwa dokumentów. Wyłączenie współdzielonego klucza KMS może uniemożliwić dostęp do wielu dokumentów, więc wymaga osobnej zgody obejmującej cały klucz i polityki retencji. Wymagany niezależny pilotaż AWS nadal BLOCKED.

## Unresolved architectural security boundaries

1. Browser-generated logical version is **not the post-upload S3 VersionId**.
   The application knows the latter only after S3 accepted the request. Existing
   queue ledger pins S3 VersionId, but independent anti-replay authorization must
   be demonstrated in production.
2. Existing v1 documents require a reviewed migration or explicit decommissioning:
   the new guest rejects them. Do not silently make a legacy decrypt fallback.
3. A custodian may unilaterally change KMS policy unless independent governance
   and external evidence of ownership / AWS Organizations separation exist.
4. The main web app still serves code controlled by NotarAI. A separate signed,
   offline client has been prepared, but must be independently hosted and its
   signing public key pinned outside the app origin. Until independently
   distributed, claiming strict Zero Knowledge against a malicious operator
   is false.
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

**SEC-03 implementation update (2026-11-22):** The guest now invokes
`confidential.origin_admission.require_origin_receipt` AFTER validating the
exact ciphertext/VersionId in its DynamoDB ledger and BEFORE calling the Nitro
KMS unwrap path. The receipt is fetched as a separate S3 sidecar object. The
issuer public key is loaded only from `confidential/trusted-origin-root.json`
bundled into the immutable guest image; absent/invalid root, absent receipt,
altered digest, wrong issuer, changed version, duplicate JSON keys and bad
signature **fail closed**, without KMS decrypt. Negative and positive tests
are in `test_confidential_origin_admission.py`.

**Still BLOCKED:** independent issuer identity and signing-key enrollment,
image build containing a custodian-verified origin trust root, independent
image/PCR release approval, real S3/KMS/Nitro positive/denial tests and legal
notary authentication. The origin receipt is not independently verified by
the operator SaaS backend — it accepts opaque signed data and the guest checks
it. No currently approved production release with a custodian root is claimed.

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

## Build implementation since earlier milestone (new critical gate)

- `confidential/origin_admission.py`: independent trust root embedded in the
  measured Nitro image, strict signed receipt parser, origin signature verification
  before DEK unwrap. No runtime env override to change signer.
- `scripts/sign_confidential_origin_receipt.py`: offline Ed25519 signature over
  original client file SHA-256 and immutable S3 VersionId, requiring independent
  key pin; does not call AWS or expose signing keys to NotarAI.
- `scripts/package_confidential_origin_root.py`: prepare release-bundled public
  issuer root with independent SPKI SHA-256 pin check; **not an authorization
  to release an image or change KMS policy**.
- `confidential/Dockerfile`: optional build-time SHA-256 validation of embedded
  origin root; root absent by default -> guest refuses all jobs.
- `confidential/router.py`: preserves exact client ciphertext bytes to S3,
  rejects duplicate JSON fields, publishes digest + VersionId for external
  signing, receives and stores signed origin sidecar immutably, checks sidecar
  presence before consuming a one-use preview authorization.
- `static/confidential-courier.js`: separate ciphertext, signed receipt and
  preview steps; no plaintext path or signing key access.
- `test_confidential_origin_admission.py`: synthetic positive/negative cases
  for authentic and tampered receipts, absent roots, exact S3 binding, trusted
  issuer pin and the **no KMS unwrap before receipt validation** ordering.

Software tests are evidence of software behavior only; root/issuer enrollment,
real Nitro attestation and actual independent custody are unverified.
