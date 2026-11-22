# SEC-09 — Tenant isolation: evidence ledger

**As of 2026-11-22. State: IMPLEMENTATION IN PROGRESS / NOT VERIFIED.**
Repository PR: https://github.com/plnyspolka-pixel/notarai/pull/74

## Boundaries and real implementation

- Trusted server-derived tenant identity remains enforced by
  `confidential.router._scope`. Clients cannot select a tenant through
  request body, query or document path.
- New `confidential/tenant_isolation.py` validates immutable per-tenant
  task/execution role ARNs, FIFO queue, job and lease tables, KMS key, S3
  namespace, server-side session identity and common approved image SHA256.
- `confidential.worker._config` now fails before any AWS access if the
  configured tenant and FIFO queue do not match, or if the KMS key is
  outside the pinned EU region. The separate trusted manifest validator
  additionally checks queue account against the ECS workload account;
  the bare guest startup has no independent AWS account assertion yet.
- `infra/notarai-confidential-task.yaml` grants the tenant-scoped
  `s3:GetObjectVersion` required by an actual versioned S3 read in the
  worker, along with existing `s3:GetObject`. It does NOT broaden to
  `arn:aws:s3:::*/*`.
- `confidential/dispatch.py` now refuses to release an ECS dispatch lease based solely on an unrelated STOPPED task: it verifies tenant-cluster ARN, pinned task definition, signed run's `startedBy` token and task ARN before freeing a lease. Synthetic regression in `test_confidential_dispatch.py` covers foreign task injection.
- `test_confidential_cross_tenant_isolation.py` additionally verifies five
  API routes reject an authenticated foreign tenant *before* any AWS call,
  and that query-provided tenant IDs cannot select another job ledger.
- `scripts/verify_confidential_tenant_isolation.py` rejects inactive,
  unpinned or unexpectedly expanded task configurations before IAM simulation.
- Neither plaintext nor document content is placed in the tests, manifest
  or proposed audit evidence. Worker stays `submitted=false`.

## Acceptance criteria (strict interpretation)

| Criterion | Status | Evidence and remaining prerequisite |
|---|---|---|
| K1 Two isolated tenants on same attested cluster/VPC/digest | BLOCKED | Offline manifest pair test exists; deployed roles, sessions, provider, effective policies and VPC not independently verified |
| K2 >=10 real 2-way AccessDenied denials | BLOCKED | Test verifies static IAM scoping; read-only IAM simulation script prepared, but simulator denials do not count as real denial |
| K3 6+ cross-tenant input tampering tests | BLOCKED | Synthetic queue, identity, session, ARN, job, version and body tests added; live authenticated API boundary not probed |
| K4 Two concurrency/confused-deputy cases | BLOCKED | Synthetic duplicate lease and cross-tenant job collisions tested, but no live concurrency yet |
| K5 Two successful tenant-specific preview jobs | BLOCKED | Both synthetic preview flows tested with no-submit marker, but no attested AWS runs |
| K6 Auditable AWS denial evidence and configuration hash | BLOCKED | Read-only verifier produces SHA256 metadata digest, not live denial audit records |

**Verdict: 0/6 LIVE PASS; 6/6 BLOCKED. No verified Zero Knowledge
or Zero Operator Access claim is permitted.**

## Reproducible checks

Offline, no AWS calls:

```bash
python -m pytest -q test_confidential_cross_tenant_isolation.py
python scripts/verify_confidential_tenant_isolation.py
```

Read-only AWS inspection and IAM simulation, **only after separately
approved auditor credentials are available**:

```bash
python scripts/verify_confidential_tenant_isolation.py --check \
  --profile APPROVED_AUDIT_PROFILE --account YOUR_12_DIGIT_ACCOUNT \
  --report /tmp/notarai-sec09-sanitized.json
```

The `--check` command returns a **non-zero exit code (2)** even when
configuration and simulations look good, because they are not evidence
of live runtime denial. It must not be put in an automatically green CI
gate as a substitute for live verification. No AWS mutation is executed
by this checker.

## Separate authorized live test protocol (NOT EXECUTED)

1. Security approver and independent custodian authorize two fresh,
   exclusively synthetic pilot identities in the correct EU account.
   Record approved role ARNs, PCR17, attested image digest and expiry.
2. Independently check shared ECS cluster/capacity provider/VPC/network
   configuration, but distinct tenant session, task/execution roles,
   KMS keys, FIFO queues, S3 object versions, DynamoDB job and lease
   tables and per-tenant prefix policies.
3. Using *actual scoped pilot01 credentials*, attempt forbidden operations
   on pilot02; repeat reverse direction. Count real `AccessDenied`
   for KMS Decrypt with attestation Recipient, S3 GetObjectVersion,
   SQS ReceiveMessage, DynamoDB GetItem and UpdateItem, ECS RunTask and
   iam:PassRole. No real document or customer secret. A local IAM
   simulation is not an accepted denial.
4. Attempt 6+ authenticated API tamper cases: tenant identifier,
   job identifier, query/body, queue URL, task ARN and object VersionId.
   Verify HTTP denial and that no cross-tenant downstream action ran.
5. Run two controlled races: duplicate delivery of one synthetic job
   and collision of job ID across tenants. Verify distinct audit
   identities, conditional leases, no cross-tenant result read and
   no submission.
6. Run one positive fictitious Nitro preview on each tenant and
   verify signed/released digest, KMS recipient attestation and
   `submitted=false` markers.
7. Export **redacted** CloudTrail/IAM/KMS/S3/SQS/ECS log references and
   policy/configuration hashes, review them independently, then mark
   each criterion PASS/FAIL/BLOCKED with date, reviewer and immutable
   evidence URL. Keep production OFF.

Use no actual notarial matter, real customer PII, document plaintext,
DEK, secret, token, screenshots or access keys in any report.

## Conflict / integration note

This branch is based on #65 and changes shared
`confidential/worker.py`, `infra/notarai-confidential-task.yaml`
and `.github/workflows/confidential-browser.yml`. Coordinate
integration with SEC-08 (#73) and SEC-10 (#75), which may also harden
the worker or pipeline. Never silently overwrite their controls.

## Release gate

PR stays OPEN/DRAFT until all K1–K6 have independently verified
`PASS`, 0 critical skipped tests, green CI on the exact PR HEAD SHA,
and signed evidence from the appropriate AWS owner/custodian. Offline
tests do not satisfy any requirement explicitly calling for AWS live
or independent reviewer evidence.

## CI regression investigation (2026-11-22)

The prior PR HEAD `3006fa80` had 3 failing tests: legacy IAM test
expected scalar `s3:GetObject`, two ECS synthetic mock responses used
outdated task ARN shape, and the validator did not yet anchor queue
account to an explicit trusted expected account. Changes after that SHA
fix the test expectation and simulator fixtures, and add the trusted
account check. New API negative tests and hardened audit configuration
checks are also committed. Latest branch CI must be rechecked for
the exact current HEAD SHA; no unverified claim of a green run is made.
