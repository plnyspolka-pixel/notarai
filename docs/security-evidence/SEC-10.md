# SEC-10 — plaintext lifecycle / evidence ledger

Date: 2026-11-22. Branch: `plan/confidential-sec-10-zk-data-lifecycle-20261122`.
Scope: **fictional** `pilot01`/`pilot02`, offline only, no submission/signature.
Owner of this implementation: NotarAI engineering. Approval owner: independent custody/security reviewer.

## Claim boundary
This is **NOT** proof of Zero Knowledge or Zero Operator Access. Static controls and
synthetic tests cannot prove AWS hardware isolation, deletion of all memory copies,
operator blindness in every AWS account, absence of provider retention or safety
of recovery processes. One-shot Nitro task destruction is the primary RAM lifetime
boundary; `del`, `dict.clear()`, temp-file cleanup and `RLIMIT_CORE` are defense
in depth, not guaranteed memory erasure.

## K1 — explicit plaintext and metadata inventory

"Operator access" is a design expectation, NOT independently verified access
evidence. All rows require tenant-specific AWS inspection before being signed off.

| Location | Plaintext potentially present? | Operator access / risk | Current retention / handling | Owner |
|---|---|---|---|---|
| Guest process RAM / Python bytes | YES | Intended Nitro isolation; hardware unverified | One job, task shutdown; no RAM-zero guarantee | Nitro runtime / custody |
| DEK and AWS KMS recipient memory | YES | Intended guest-only; actual attestation unverified | One key unwrap per job; Python copies may linger | Nitro runtime / independent KMS custodian |
| Chromium renderer RAM / model context | YES in renderer; no model invoked in current local demo | Guest only if isolation works; future LLM risk | Browser closes, task terminates; not cryptographic wipe | Browser / model provider |
| `/tmp` including `HOME`, XDG and Playwright | YES transiently | Guest only if tmpfs and readonly are enforced | Must be explicit tmpfs; unique directory removed on exit | Guest |
| Chromium profile/cache/downloads | YES possible | Guest only under verified tmpfs; downloads disallowed | Session-only, no persistent user-data-dir | Guest |
| Crash dump / trace / core / minidump | YES possible if misconfigured | Potentially high if forwarded to operator | RLIMIT_CORE=0, dumpable=0, breakpad disabled; verify live | Guest / host |
| Screenshot, video, HAR, Playwright trace | YES if enabled in future | High if exported | Not generated in preview; no recording configured | Application |
| stdout/stderr/HTTP server logs | YES if code prints unsanitized data | Could reach operator | Main emits only exception class; HTTP handler suppresses request logs; **not a proof for all libraries** | Application |
| CloudWatch, container log driver | YES if enabled elsewhere | Operator may read | Guest task has no LogConfiguration; account-wide audit pending | AWS operator |
| Proxy/DNS/packet captures | YES on decrypted application traffic to external services | High if proxy terminates TLS | Private-egress controls in SEC-08, not independently proven | Network owner |
| External LLM request/output, embeddings, traces | YES if introduced | Provider/operator exposure possible | Current fictional form path does not call LLM; SEC-04 pending | AI provider / controller |
| S3 object current ciphertext and versions | No intended plaintext; ciphertext + identifiers only | Operator may read ciphertext/metadata | Versioning enabled, bucket `Retain`, **NO automatic deletion** | Storage / controller |
| S3 status marker | No, metadata-only | Operator may read job status | No lifecycle policy in current template | Application / storage |
| DynamoDB job ledger and PITR | No intended plaintext; opaque IDs/status and timestamps | Operator may read metadata | PITR enabled; actual configured recovery period must be read from AWS; table Retain | Storage / controller |
| SQS and DLQ | No intended plaintext; opaque job references | Operator may read metadata | Main queue 86,400 s (1 d); DLQ 1,209,600 s (14 d) | Queue owner |
| CloudTrail management/data event history | No intended plaintext, but potentially identifying resource/role IDs | Operator/auditor according to AWS policy | Unknown until live trail/bucket/log-group inventory | AWS security |
| Volumes, snapshots, backups, cross-region replicas | YES if bad guest mount/log/backup policy | Potentially high | No shared volume in task template; AWS snapshots/backups not audited | AWS operator / custodian |
| Support tickets / exports / browser HTTP responses | YES if operator or user copies content | High | Outside guest technical guarantees; contractual and product control pending | Support / controller |

**Important:** source ZIP artifact bucket in `notarai-confidential-artifacts.yaml` is
versioned with `DeletionPolicy: Retain`. It is for synthetic Lambda **source**
only, but still must be checked for accidental data inclusion.

## K2 — synthetic marker protocol (not hardware evidence)

`python -m pytest -q test_confidential_plaintext_lifecycle.py`

- Six explicitly named test paths: success, exception, retry, simulated browser
  crash, simulated network error, simulated timeout.
- Never use personal information, actual KEKs/DEKs or live documents in CI.
- Synthetic marker and fake-key marker are placed only in a temporary browser
  directory; after normal exception exits the path must be removed.
- Operator-visible **synthetic** log directory is scanned for both markers
  with zero allowed occurrences; a deliberate injected leak must cause FAIL.
- Worker exceptional logging test asserts no attacker-controlled exception
  message is echoed to stdout/stderr.
- A simulated exception is **not** evidence of a true SIGKILL/guest
  crash: those require independent live artifact capture under K6.

## K3 — storage/runtime controls and verification gaps

Implemented: guest startup refuses work if Linux core dumps/ptrace dumpability
cannot be disabled or if `/tmp` is not a mounted `tmpfs`; Chromium profile,
XDG config/cache and `TMPDIR` point to a fresh unique folder in that tmpfs.
Read-only guest filesystem, no mounted persistent volumes, no container log
driver, no downloads or traces; screenshot/preview data are never persisted
by the fictional guest. No persistence of decrypted PDF or model output is
implemented here.

**Still required**: audit actual deployed ECS task definition and host volumes;
read-only scan of synthetic S3 object version history, backups and snapshots;
confirm crash reporters cannot export to host/operator; validate these settings
after measuring the exact production guest image digest.

## K4 — retention and deletion: verified template values vs policy decisions

| Store | Template-declared period | Deletion approach and dependency |
|---|---|---|
| SQS main | 1 day | Queue expiry; verify actual attributes and redrive behavior |
| SQS DLQ | 14 days | Expiry; verify attributes and whether independent queues duplicate messages |
| S3 ciphertext/versions | **Indefinite in template** (versioning, Retain, no lifecycle) | Need document-specific lawful schedule, explicit delete of **all** versions/delete markers, retention/lock checks, and backup purge confirmation |
| S3 code artifacts | **Indefinite in template** (Retain) | Separate source-artifact release schedule; never assume stack deletion erases objects |
| DynamoDB job/dispatch ledgers | No TTL; `Retain` on job ledger; PITR enabled | Set approved TTL only if lawful; review PITR configured period and recovery windows; deleting item is not immediate purge from PITR |
| CloudTrail/S3 access data-event logs | **UNVERIFIED** | Read-only account inspection + legal schedule and separately controlled audit retention |
| CloudWatch / app/API logs | Guest log driver not set; other groups **UNVERIFIED** | Enumerate groups and retentionInDays; redact IDs; preserve necessary security audit history |
| LLM/provider traces/caches | No external LLM call in current preview; future **UNVERIFIED** | Require provider contract/retention terms and independent technical evidence per SEC-04 |
| KMS recovery/DEK material | No server-side DEK escrow in this scope; key status **UNVERIFIED** | Controlled custody revocation/rotation, explicitly test recoverability |
| EC2/EBS/container backups | **UNVERIFIED** | Inspect actual managed-instance snapshot policy, guest disk mounts and lifecycle |

Legal retention of notarial records, data controller obligations under GDPR,
legal hold and litigation preservation must be approved separately; **no fixed
legal retention deadline is inferred from technical SQS expiry**. Deletion
request must create an auditable *pending* record until all versions,
PITR windows, replicas and legal holds are resolved. A legal hold may prohibit
deletion; it must never silently add an operator escrow/backdoor.

## K5 — recovery and emergency handling

Allowed only after **authenticated, independently cryptographically verified**
customer/notary authorization AND independent custodian approval through
SEC-03/SEC-06. The application role must never possess a fallback decrypt
principal, AWS key-policy mutation permission, recovery master secret, or
unrestricted operator escrow. Existing guest role permits only
recipient-attested `kms:Decrypt` pinned to PCRs; no `PutKeyPolicy`,
`CreateGrant`, `RestoreObject` or `DeleteObject` grants. This test is
necessary but not sufficient: AWS administrators, independent account policy
and live key revocation must be checked externally.

Decision matrix:
- **Operator-only request:** DENY, even during incident or legal hold.
- **Lost plaintext DEK with no separately approved recovery material:** DATA
  UNRECOVERABLE; do **not** invent an emergency universal key.
- **KMS key revoked/unavailable:** DENY key release until authorized recovery
  or new lawful workflow; may remain permanently unrecoverable.
- **Notary + custodian both approve a specific recovery:** still requires a
  valid independently verified signed release, authorized key access and fresh
  attestation; no bypass through admin/API flags.
- **Legal hold:** retain ciphertext/records according to legal obligation,
  but does not grant anyone plaintext access by itself.

Recovery end-to-end remains **BLOCKED** until independent signed proofs and
live negative tests are integrated. This branch intentionally adds no recovery
endpoint or privileged decrypt fallback.

## K6 — required external live evidence, NOT done

Evidence bundle after authorized isolated AWS test, with sanitized identifiers:

1. Approved immutable image digest, task definition ARN, PCR17, recipient NSM
   attestation, KMS request identity and independent custody receipt.
2. Successful fictional marker test and six error paths including actual
   browser process kill and task restart with exact timestamps.
3. Read-only inspection: guest task logs, CloudTrail/KMS, S3 current/versions,
   SQS/DLQ, DDB PITR, EBS snapshots, configured CloudWatch groups, browser
   cache, proxy and model/provider telemetry.
4. Signed independent auditor conclusion: exact SHA, scope, exceptions and
   pass/fail evidence, **without** real data, DEKs, or plaintext marker values
   in GitHub logs. Report only counts and hashes of evidence packages.
5. Explicit inability to prove physical RAM wiping or full provider deletion
   must be reported as a limitation, not a PASS.

## Acceptance ledger

| Criterion | Status | Owner | Evidence/next required |
|---|---|---|---|
| K1 map of >=10 locations | BLOCKED | Security reviewer | Map above exists; operational AWS inventory and approval missing |
| K2 six synthetic scenarios | BLOCKED | Engineering / CI | Test file committed; must verify current HEAD green CI and limitations |
| K3 no persistent plaintext | BLOCKED | AWS operations | Static controls exist; actual guest/S3/snapshots audit missing |
| K4 legally approved exact retention | BLOCKED | Controller / counsel / AWS | Template periods known; CloudTrail/LLM/PITR and legal approvals missing |
| K5 recovery without operator backdoor | BLOCKED | Independent custodian | Negative static tests added; actual signed recovery/revocation not proven |
| K6 live Nitro evidence | BLOCKED | Independent auditor | Requires approved AWS test; not run here |

**Gate:** draft remains open until K1–K6 are all PASS, current commit CI is
green with zero critical skips, and links to live external evidence exist.
Do not market verified Zero Knowledge / Zero Operator Access.
