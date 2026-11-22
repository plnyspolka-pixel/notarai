# SEC-07 — NotarAI PR #72: hardware Nitro/KMS

**Status at 2026-11-22: PARTIAL IMPLEMENTATION; LIVE HARDWARE EVIDENCE BLOCKED.**
This document is the evidence register, not proof that hardware tests ran.
PR: https://github.com/plnyspolka-pixel/notarai/pull/72
Dependencies: SEC-05 / PR #70, SEC-06 / PR #71 and custody sign-off / PR #65.
Pending external access is already registered in docs/czeka-na-dostep.md as NA-15.

**Constraints:** only synthetic pilot01/pilot02, eu-central-1, zero customer PII or document content, production disabled, preview-only, no form submission/signature. Do not start chargeable AWS resources from this PR.

## Status of measurable requirements

| Criterion | Status | Actual proof required | Code/available evidence |
| --- | --- | --- | --- |
| K1: Positive real NSM/KMS decrypt | BLOCKED | ECS confidential task exited 0, exact task revision and image digest, PCR17, KMS recipient and guest unwrap | Offline validation of ECS / CloudTrail metadata only |
| K2: Six live denials | BLOCKED | Separately witnessed ordinary host, wrong PCR17, altered image, cross-tenant/role, unsigned release and wrong key; each attempt denied | Six synthetic negative-test categories, no executed AWS attacks |
| K3: No plaintext DEK outside guest | BLOCKED | Live KMS response uses only CiphertextForRecipient, guest unwrap and operator-side log/data leak check | Mock Plaintext rejection test only |
| K4: Two independent AWS accounts | BLOCKED | Read-only snapshots of identity/Organizations/root/SSO, KMS policy, grants, ECS task and CloudTrail from both accounts | Dual-account readonly audit implementation, not executed |
| K5: Reproducible cryptographic report | BLOCKED | Timestamped job, exact image/PCR17/key policy/task hashes, 1+6 trial links, canonical SHA256 and custodian/auditor signature | Canonicalization and ECDSA signature verification implementation |
| K6: Hardware proof gate | BLOCKED | Real K1-K5, independently verified trials with two identities; mock/CI can never set verified=true | Offline dry-run returns BLOCKED, hardware=false |

**No row has live evidence or an independent auditor signature.** Hardware and commercial zero-operator-access or zero-knowledge claims remain unverified. Do not mark PR DONE, merge, or enable production until all K1-K6 PASS with 0 failed, 0 blocked, 0 unverified, non-skipped critical tests and green CI on current HEAD.

## Implemented code and reproducibility

- confidential/nitro_hardware_proof.py: strict evidence schema, exact region/tenant/account/image/PCR/job binding; KMS CloudTrail checks, cross-account positive sharedEventID, ECS confidential task exit code, SHA256 of canonical synthetic-only report.
- scripts/run_nitro_attestation_e2e.py: --check is offline, returns BLOCKED and exit 2 without any AWS call; --verify-live runs read-only dual-account AWS queries, signed-release verification, ECS and CloudTrail lookup. It never deploys, calls KMS Decrypt, changes KMS policy, runs ECS tasks or creates a signature.
- test_confidential_nitro_hardware_plan.py: synthetic positive and denial fixtures, six missing/successful-denial regressions, tamper failures, KMS Plaintext guard, auditor ECDSA signature integrity and offline fail-closed checks.

Target command: python -m pytest -q test_confidential_nitro_hardware_plan.py
Offline safety check: python scripts/run_nitro_attestation_e2e.py --check
The safety check must exit with code 2; this is expected, not a security-test failure.

CI evidence for current HEAD: NOT YET VERIFIED. Never cite an earlier green run as proof for the final HEAD.

## Independent AWS hardware test runbook — NOT EXECUTED

1. Independently controlled custodian account and a separate workload account are required. Auditor independently verifies IAM/Organizations/root/SSO control, not just different account numbers. Custodian chooses release key and holds its signing key outside NotarAI control.
2. Resolve SEC-05 and SEC-06 admission and custody blockers. Obtain exact approved OCI image@sha256, ECS task definition ARN and revision, role, KMS RSA key ARN and current KMS policy/grants hash. Generate PCR17 with official AWS ecs-nitro-sandbox-genpolicy --check and --output pcrs; do not invent it.
3. Independently authorize one synthetic task for pilot01 in eu-central-1. Use existing guarded runner only with a fresh, independently signed release and approved private-network controls. Run Nitro NSM /dev/nsm => KMS Recipient => CiphertextForRecipient => guest unwrap, then verify fictional preview result with submitted=false and ECS exitCode=0.
4. With an independent witness and safe isolated synthetic jobs, conduct all six negative cases separately:
   a. ordinary_host: no NSM Recipient; no plaintext release;
   b. wrong_pcr17: NSM task measured with different PCR17; KMS deny;
   c. altered_image: different OCI digest and policy; reject by release gate/KMS, record exact digest/PCR binding;
   d. cross_tenant_or_role: pilot02 or unauthorized task role against pilot01 key; deny;
   e. unsigned_release: missing independently signed release must stop all allowed launch paths; verify direct RunTask cannot result in authorized DEK, beyond app-layer check;
   f. wrong_key: use a truly different custodian KMS key ARN and record denial.
5. Download CloudTrail observations read-only from *both* AWS accounts using independent audit identities. For successful cross-account calls, correlate by sharedEventID; cross-account AccessDenied is logged only on caller side. Preserve original raw events outside NotarAI-controlled repository, and import only sanitized event IDs and SHA digests.
6. Auditor crosschecks the conditions of each trial, snapshots of grants/policy/role/task, guest logs and leaked-plaintext checks. The manifest includes schema, region, tenant, workload_account, custody_account, task_definition_arn, task_arn, kms_key_arn, image_sha256, expected_pcr17, job_id, positive_event_id, denied_event_ids, started_at, ended_at. UTC only.
7. Read-only CLI command after these trials:
   python scripts/run_nitro_attestation_e2e.py --verify-live --manifest manifest.json --operator-profile AUDITOR_WORKLOAD_RO --custody-profile AUDITOR_CUSTODY_RO --release-file release.json --custodian-public-key-file external-release.pub --custodian-public-key-sha256 PIN_HEX
   Audit payload SHA is computed using domain-separated canonical JSON; an independent auditor signs exactly the resulting payload with ECDSA P-256. The pinned public key arrives out of band, never from NotarAI.
8. Attach the independent signed evidence and links per K1-K6 to this register; audit and review false positives, retention, tamper, rollback and grant revocation. Production and marketing remain OFF until separately authorized.

**Important evidentiary limitation:** six operator-labeled AccessDenied event IDs do not by themselves prove the six attack preconditions. Hardware verification MUST remain BLOCKED until the independent reviewer verifies the actual inputs and release, not just the names of tests in a JSON document.

Reference AWS docs:
https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ict-confidential-policy-configuration.html
https://docs.aws.amazon.com/kms/latest/APIReference/API_Decrypt.html
https://docs.aws.amazon.com/kms/latest/developerguide/logging-using-cloudtrail.html

## Correction: six denials occur at three different security boundaries (v2)

The first verifier, `confidential/nitro_hardware_proof.py`, deliberately remains fail-closed, but its original assumption that **all six refusals must produce a KMS Decrypt AccessDenied event is not a correct full E2E acceptance criterion**. An altered OCI image can be denied by ECS sandbox admission before KMS, and an unsigned custodian release must stop before ECS RunTask. The v1 report is **not eligible** to close K2 or K6.

New, independently testable topology:

| Case | Enforcement boundary | Evidence required |
|---|---|---|
| ordinary_host | KMS | Decrypt deny, no recipient NSM, pinned task role/key |
| wrong_pcr17 | KMS | Decrypt deny, recipient attestation PCR17 != approved PCR17 |
| altered_image | ECS confidential sandbox admission | Different immutable image digest; ECS admission failure; no unauthorized DEK; independently witnessed synthetic trial |
| cross_tenant_or_role | KMS | Decrypt deny to other synthetic tenant's IAM task role |
| unsigned_release | Independent custody release gate | Reject before ECS RunTask; no KMS decrypt; independently witnessed record and control-plane trace |
| wrong_key | KMS | Different custodian key ARN, failed Decrypt |

The code for this second evidence channel is `confidential/nitro_denial_matrix.py`, `scripts/audit_nitro_denials.py`, and `test_confidential_nitro_denial_matrix.py`.

Use `python -m pytest -q test_confidential_nitro_denial_matrix.py` to check metadata parsing. The offline command `python scripts/audit_nitro_denials.py --check` returns `BLOCKED` and exit status 2. Read-only AWS verification (only when the independent sessions and signed witness records exist):

```bash
python scripts/audit_nitro_denials.py --verify-live \
  --matrix negative-matrix.json \
  --operator-profile AUDITOR_WORKLOAD_RO \
  --custody-profile AUDITOR_CUSTODY_RO \
  --altered-image-receipt altered-image.json \
  --unsigned-release-receipt unsigned-release.json
```

This sub-audit only establishes that four KMS preconditions are reflected in live caller-account CloudTrail and that two early-denial receipts are **structurally** consistent; it **always returns BLOCKED**. It cannot prove the absence of RunTask/KMS calls from an operator-authored receipt alone. A separately retained independently signed record, ECS snapshots, official policy-generator measurements, KMS policy/grant snapshots, and authenticated primary AWS trails are still necessary. Do not label a synthetic mock as live.

## Independent dual-witness provenance (implementation, no AWS run)

The six-case matrix may now be bound to **two distinct ECDSA P-256 public keys**, independently pinned outside the operator's control. The module `confidential/nitro_witness.py` validates the domain-separated canonical witness payload and its two signatures; `test_confidential_nitro_witness.py` covers replacement, replay/expiry, same-identity signer, wrong pin and modified event/receipt hashes. Exactly six trial receipt hashes and four KMS event IDs are part of the signed scope. No private signing key is persisted or read by the application.

The witness verifier intentionally returns `hardware_attestation_verified=false` even if both signatures are valid. A signature can authenticate that someone approved metadata, but cannot on its own prove that Nitro hardware executed or that a purportedly independent signer is actually independent of the NotarAI operator. A later review must independently validate real AWS evidence and witness employment/administration separation before updating K1–K6.

Targeted offline CI: `.github/workflows/confidential-sec07.yml`, which installs only `pytest` and `cryptography`, runs the three SEC-07 test modules without AWS credentials, asserts both dry-run commands return `BLOCKED` (exit 2), and performs Python syntax checks. This check can satisfy offline implementation regression only, **not** hardware acceptance.

## Stricter v2 proof binding (new code; not run against real AWS)

- For the four KMS-negative cases, `kms_receipt_sha256()` hashes a **whitelisted CloudTrail projection**: eventID, requestID, UTC, request key ARN SHA256, role/account, error and relevant NSM PCR17. The operator cannot substitute another AccessDenied request after the independent witness signed its receipt digest. The audit fetches the AWS original by EventId from the workload account and re-derives the receipt hash.
- For `altered_image`, the witness receipt must contain a specific **one-time** ECS task ARN and a different candidate image digest. The read-only auditor now calls ECS DescribeTasks and DescribeTaskDefinition, checks stopped confidential isolation, image pinned to the different digest, matching tenant role, failed container and a policy/authorization-related stop reason. Arbitrary crashed container is not counted as an admission rejection.
- AWS documents that `DescribeTasks` only guarantees stopped-task visibility for **at least one hour**. Capture task evidence as soon as the negative trial completes, and independently retain the raw AWS evidence outside the NotarAI account; stale queries without ECS task cannot pass K2. Source: https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_DescribeTasks.html.
- For `unsigned_release`, require `RunTask=0` in an independently witnessed and signed control-plane trace; no fabricated KMS negative event. This remains BLOCKED without independent evidence of the blocked launch path, and cannot be inferred merely from a JSON count.

These changes strengthen verifiability, but **all K1–K6 remain BLOCKED** until an authorized independent real AWS pilot exists and every negative scenario is witnessed.

## Dual-witness audit CLI (read-only, prepared; LIVE still BLOCKED)

When the independent custodian and auditor have already **each signed the exact same SEC-07 denial witness payload** using separately held P-256 keys, include the following arguments in the read-only v2 audit command:

```bash
  --witness-payload witness.json \
  --custodian-witness-signature custody-signature.b64 \
  --custodian-witness-public-key custody-public.pem \
  --custodian-witness-public-key-sha256 EXTERNALLY_PINNED_CUSTODY_KEY_SHA256 \
  --auditor-witness-signature auditor-signature.b64 \
  --auditor-witness-public-key auditor-public.pem \
  --auditor-witness-public-key-sha256 EXTERNALLY_PINNED_AUDITOR_KEY_SHA256
```

No private keys, temporary AWS credentials or raw CloudTrail events belong in GitHub. The CLI tests certificate/key mismatch, stale signature, cross-tenant binding and tampered receipt hashes. If signatures validate, it can report `witness_signatures_verified=true`, while **still returning `status=BLOCKED`, `hardware_attestation_verified=false` and exit status 2** until all independent AWS evidence and witness independence controls are satisfied. Do not misinterpret these two signatures as an external hardware attestation certificate.

## Odtwarzalny pakiet podpisów dwóch niezależnych świadków (offline)

Dodano `scripts/prepare_nitro_witness.py` oraz `test_confidential_nitro_prepare_witness.py`. Niezależny świadek używa **wcześniej zweryfikowanego** `negative-matrix.json`, pełnych identyfikatorów CloudTrail i własnoręcznie zweryfikowanych skrótów recepitów. Skrypt zapisuje pliki 0600 poza repozytorium: czytelny JSON i **kanoniczne bajty z prefiksem dziedzinowym**, które trzeba podpisać. Istniejące pliki nie są nadpisywane.

```bash
python scripts/prepare_nitro_witness.py \
  --matrix /secure/negative-matrix.json \
  --observed-at 2026-11-22T09:00:00Z \
  --expires-at 2026-11-22T10:00:00Z \
  --payload-out /secure/witness.json \
  --signing-bytes-out /secure/witness.signing.bin
```

Każda niezależna strona **najpierw** weryfikuje obserwacje AWS poza kontrolą operatora i potwierdza niezależność administracyjną obydwu kont AWS. Sam skrypt **nie tworzy kluczy prywatnych, nie atestuje sprzętu, nie pobiera danych AWS i niczego nie podpisuje**.

Dwóch świadków, na dwóch osobno zarządzanych stacjach roboczych, podpisuje te same bajty, każdy **innym posiadanym już prywatnym kluczem ECDSA P-256**:

```bash
# Wykonuje kustosz, z kluczem zabezpieczonym poza systemem NotarAI:
openssl dgst -sha256 -sign /private/custodian-p256.pem \
  -out /secure/custodian.der /secure/witness.signing.bin
openssl base64 -A -in /secure/custodian.der -out /secure/custodian.b64

# Audytor powtarza z INNYM kluczem prywatnym:
openssl dgst -sha256 -sign /private/auditor-p256.pem \
  -out /secure/auditor.der /secure/witness.signing.bin
openssl base64 -A -in /secure/auditor.der -out /secure/auditor.b64
```

Pliki `.b64` z podpisami oraz niezależnie zweryfikowane klucze publiczne PEM przekazuje się do `scripts/audit_nitro_denials.py --verify-live`. Nie wolno przechowywać kluczy prywatnych, poświadczeń ani pełnych logów CloudTrail w repozytorium. Dowód ma ważność maksymalnie 24 h i zawiera skróty **wszystkich sześciu** prób. Zweryfikowanie obu podpisów nadal daje `BLOCKED`, nie certyfikat bezpieczeństwa sprzętowego.

**Pozostałe dowody sprzętowe:** rzeczywiste uruchomienie zaufanego ECS Managed Instances `CONFIDENTIAL_SANDBOX`; polityka wygenerowana i zweryfikowana `ecs-nitro-sandbox-genpolicy --check`; przypięty digest obrazu, PCR17 i klucz KMS z `PCR8:ServiceName=ecs.amazonaws.com`; rzeczywisty wynik no-submit; CloudTrail z obu kont; niezależnie zatwierdzony release; administracyjny brak kontroli NotarAI nad kontem kustosza.

Dokumentacja AWS: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ict-confidential-policy-configuration.html i https://docs.aws.amazon.com/kms/latest/developerguide/ct-nitro-enclave.html.
