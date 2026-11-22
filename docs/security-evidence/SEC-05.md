# SEC-05 / PR #70 — evidence register (synthetic only)

Updated: 2026-11-22. Implementer: ChatGPT via connected GitHub repository.
PR: https://github.com/plnyspolka-pixel/notarai/pull/70
Branch: `plan/confidential-sec-05-release-enforcement-20261122`

## Scope and guardrails

**Status: IN PROGRESS — NOT ACCEPTED / NOT DEPLOYED.**
All tests in this PR are fictional `pilot01`/`pilot02` in `eu-central-1`.
No AWS deployment, customer documents, plaintext, signatures of forms or
commercial Zero Knowledge/Zero Operator Access claims are authorized.
An offline KMS mock is **never** evidence of actual DEK denial.

## Paths mapped (K1)

| Entry point | Gate | Present verification |
|---|---|---|
| `confidential/dispatch_lambda.py:handler` (EventBridge) | mandatory `LiveReleaseGate` | S3 receipt from custody-owned bucket/version, KMS Verify, ECS/KMS read-only live snapshot, external account and signer fingerprint |
| `confidential/dispatch.py:dispatch_once` (AWS ECS SDK RunTask) | required `release_gate` callable | pre-lease plus second pre-RunTask check, strict task/network/role pinning |
| `scripts/confidential_pilot_run.py:run_pilot` | external-custody mode calls independent `check_release` | source already present before SEC-05; legacy same-account key remains explicitly **synthetic pilot only**, never commercial |
| Direct AWS ECS RunTask by IAM principal | **not controlled by Python gate** | exact task-definition IAM on scheduler; actual KMS PCR/key policy negative test with independent auditor still required |
| Other API, CLI, service accounts, administrator overrides | **not exhaustively audited** | must inventory IAM principals, CloudTrail and production deployment account before K1 PASS |

The operator can change workload IAM/Lambda code. A release signature alone does
not make direct ECS RunTask or a modified operator account cryptographically
impossible; independent KMS enforcement, separate administration and live proof
remain necessary.

## Offline code changes

- `confidential/release_enforcement.py`: validates strict canonical release v1
  payload, time, identity, exact ECS task definition and PCR17, signing key metadata,
  SHA-256 SPKI fingerprint, RSA KMS policy hash, and ECDSA signature via AWS KMS
  `Verify`. It fetches a version-pinned receipt with `ExpectedBucketOwner`
  from a separate custody account. No KMS `Decrypt` or `Sign` calls.
- `confidential/dispatch.py`: no unsigned scheduler launch; checks twice and
  fails closed on drift; no ECS Exec, overrides, log drivers or sidecars.
- `confidential/dispatch_lambda.py`: refuses non-shared/demo scheduler
  configurations. No request flag for bypass or downgrade.
- `infra/notarai-confidential-dispatch.yaml`: scheduler role can assume only
  an exact custody read-only role; no direct signing/decryption policy.
- `infra/notarai-confidential-custody-signing.yaml`: separate signer and
  read-only auditor, no auditor `kms:Sign`.
- `infra/notarai-confidential-external-custody-kms.yaml`: read-only
  `ListGrants` is allowed in independently administered custody account.
- `scripts/package_confidential_dispatch.py`: bundles release enforcement
  and boundary checker into server ZIP.
- `test_confidential_release_gate.py`: seven mandatory deny cases, two
  successful signed checks, policy drift between checks, missing gate,
  invalid trust pin, same-account fallback and task isolation.
- `.github/workflows/confidential-browser.yml`: targeted offline test included.

## Acceptance matrix

These are **overall** SEC-05 statuses; offline partial success alone cannot
satisfy hardware-dependent `DONE`.

| Criterion | Overall | Evidence / remaining independent evidence |
|---|---|---|
| K1: 100% start paths | BLOCKED | Scheduler path covered in code + unit tests, but IAM/API/admin path inventory and live admission control unfinished |
| K2: seven denials | BLOCKED | `test_seven_denials_never_reach_run_task_or_lease` (synthetic); still need actual KMS deny, no DEK, ECS/CloudTrail evidence |
| K3: no downgrade | BLOCKED | Lambda refuses demo/same-account external path; no live commercial workload permission review |
| K4: direct RunTask | BLOCKED | Cannot verify cross-account KMS denial from mock; test from operator privileges against actual approved/unapproved image required |
| K5: supply chain | BLOCKED | `@sha256` enforced in scheduler; authenticated source SHA, independent provenance/SBOM and custodian signoff on exact task revision not yet established |
| K6: hardware/live AWS | BLOCKED | No independent custody credentials, Nitro live attestation, two-account CloudTrail deny/allow records in this session |

No criterion can be reported `PASS` for production until the relevant evidence
link and independent reviewer exist. CI must pass for the current head SHA.

## Reproducible offline validation

```sh
python -m pytest -q test_confidential_release_gate.py
python -m pytest -q test_confidential_dispatch.py test_confidential_operator_boundary.py test_confidential_release_approval.py test_confidential_custody_launch.py
python scripts/package_confidential_dispatch.py --output /tmp/notarai-confidential-dispatch.zip
```

CI history: https://github.com/plnyspolka-pixel/notarai/actions
The test result and current-head green status are **UNVERIFIED** pending CI
completion; do not cite a queued run as a pass.

## External live evidence required (do not run without authorization)

1. Independent custody administrator reviews effective AWS Organizations/SSO,
   exact KMS policy/grants, IAM trust boundaries and owns both signing and
   decryption KMS keys in a *separate* account.
2. Build and independently review signed OCI digest, exact ECS task revision,
   provenance/source SHA and SBOM; pin these to the custodian's signed release.
3. Auditor obtains signer public-key SHA256 through a channel outside operator
   infrastructure, validates S3 owner, immutable VersionId, and custody role.
4. Run actual AWS Nitro test with synthetic ciphertext: approved digest/PCR17
   must succeed *only* under authorized attested recipient; wrong PCR, unsigned
   task revision, direct RunTask, policy drift, wrong tenant and expired release
   must not expose DEK. Capture sanitised CloudTrail from *both* accounts.
5. Collect AWS execution IDs, current SHA, IAM policy simulator and independent
   auditor signoff, with no PII/plaintext/keys in artifacts.

**Release decision:** keep PR #70 DRAFT and commercial launch DISABLED.
