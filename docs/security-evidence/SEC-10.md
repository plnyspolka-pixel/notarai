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
| stdout/stderr/HTTP server logs | YES if code prints unsanitized data | Could reach operator | Main emits only exception class before secret processing; all guest stdio FDs redirected to /dev/null before KMS unwrap; **not a proof against custom log sinks** | Application |
| CloudWatch, container log driver | YES if enabled elsewhere | Operator may read | Guest task has no LogConfiguration; account-wide audit pending | AWS operator |
| Proxy/DNS/packet captures | YES on decrypted application traffic to external services | High if proxy terminates TLS | Private-egress controls in SEC-08, not independently proven | Network owner |
| External LLM request/output, embeddings, traces | YES if introduced | Provider/operator exposure possible | Current fictional form path does not call LLM; SEC-04 pending | AI provider / controller |
| S3 object current ciphertext and versions | No intended plaintext; ciphertext + identifiers only | Operator may read ciphertext/metadata | Versioning enabled, bucket `Retain`, **NO automatic deletion** | Storage / controller |
| S3 status marker | No, metadata-only | Operator may read job status | No lifecycle policy in current template | Application / storage |
| DynamoDB job ledger and PITR | No intended plaintext; opaque IDs/status and timestamps | Operator may read metadata | PITR enabled; AWS defaults to 35 days when period is omitted, but live configuration MUST be read; table Retain | Storage / controller |
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

### K2b — actual worker state machine with synthetic dependencies

Added `test_confidential_worker_lifecycle_sec10.py` to execute the **real**
`confidential.worker._process_one` function in six scenarios, substituting
only SQS/S3/KMS/DynamoDB clients, the decrypted fictional form and local
browser. It asserts:
- stdout/stderr guard executes **before** decryption;
- no synthetic plaintext/DEK in intercepted stdout/stderr or S3 result body;
- plaintext field dict references are cleared on all post-decrypt paths;
- success writes metadata-only S3 result, then completes the ledger, then
  acknowledges SQS, in precisely that order;
- exception, retry, browser crash, network error and timeout do not persist
  a result or acknowledge SQS, but mark ledger failure; and
- unclaimed jobs are never decrypted.

This tests the actual one-job control flow, not a hardware browser SIGKILL,
provider-level error telemetry, kernel memory cleanup or a genuine Nitro
attestation. Those remain **K6 BLOCKED**.

Command: `python -m pytest -q test_confidential_worker_lifecycle_sec10.py`.

## K3 — storage/runtime controls and verification gaps

Implemented: guest redirects stdout/stderr to /dev/null **before** KMS unwrap (fail-closed if redirect fails). Operational state is stored as metadata in the ledger; this decreases the risk that vendor libraries print decrypted values to operator-visible streams. It does not prevent a compromised guest from opening new exfiltration channels, so independent signed release and network egress controls remain essential.

Implemented: guest startup refuses work if Linux core dumps/ptrace dumpability
cannot be disabled or if `/tmp` is not a mounted `tmpfs`; Chromium profile,
XDG config/cache and `TMPDIR` point to a fresh unique folder in that tmpfs.
Inherited TLS session-key logging (`SSLKEYLOGFILE`), Playwright debug
logging (`PWDEBUG`/`PLAYWRIGHT_DEBUG`) and Chrome file logging
(`CHROME_LOG_FILE`) are disabled or set to `/dev/null` at guest startup.
Browser `HOME`, XDG config/cache/state/data/runtime, `TMPDIR`, `TMP` and
`TEMP` are redirected to the verified, private tmpfs folder during each
browser run. A supplementary regression covers initially closed standard
file descriptors; it is not a guarantee against third-party custom log sinks.

Read-only guest filesystem, no mounted persistent volumes, no container log
driver, no downloads or traces; screenshot/preview data are never persisted
by the fictional guest. No persistence of decrypted PDF or model output is
implemented here.

**Still required**: audit actual deployed ECS task definition and host volumes;
read-only scan of synthetic S3 object version history, backups and snapshots;
confirm crash reporters cannot export to host/operator; validate these settings
after measuring the exact production guest image digest.

### Additional Linux runtime smoke

The separate CI `ephemeral-runtime` job runs the actual kernel guard in a
local read-only, network-disabled, non-root Docker container with a
specifically mounted `/tmp` tmpfs. It also proves that a synthetic stdout
string and stderr are not observable by the CI host after `silence_guest_stdio`.
This is stronger than static CloudFormation inspection but is **NOT an AWS
Nitro attestation**, not an actual browser crash test and not a host-memory
forensic scan. The job must be green for the current HEAD before claiming
the *offline* runtime smoke has passed.

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

## K4a — dry-run retention and legal-hold decision gate

`confidential/retention_gate.py` implements an **offline**, metadata-only
`assess_retention()` guard, with negative tests in
`test_confidential_retention_gate.py`. Its only positive outcome is
`ready_for_independent_review` — **never** `deleted`, `purged`, or
`approved_for_automatic_deletion`. No AWS calls/deletion capability exists
in the module.

A request remains `blocked` if any of the following is unresolved:
- legally approved UTC retention deadline, or active/unknown legal hold;
- complete, non-truncated S3 version inventory including delete markers;
- replica inventory, recovered/reachable backup windows, DDB PITR window;
- approved legal basis for preserving mandatory security/audit logs;
- **independently verified** client/controller and custodian signatures;
- freshness of evidence (24 hours maximum), signed policy/inventory digests.

**Trust boundary:** these booleans/digests are NOT self-authenticating. The
gate only accepts structured facts already verified by an independent source;
future integration must enforce signatures and cannot rely on API request flags.
Even if all checks report true, a reviewer must still collect independent
proof of the actual purge operation and surviving copies. Do not confuse
eligibility to *review* a removal with proof of removal.

Tests: `python -m pytest -q test_confidential_retention_gate.py`.
No true deletion test is possible without a separately authorized process and
verified legal retention schedule.

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

## Read-only audit tool (not yet run in AWS)

`python scripts/verify_confidential_plaintext_lifecycle.py` is dry-run by default,
prints only that AWS calls are disabled. To opt into read-only metadata checks
for `pilot01`/`pilot02`, provide ALL of:
`--check --profile PROFILE --account 12_DIGITS --tenant pilot01
--bucket ntr-cf-pilot01-ACCOUNT-eu-central-1
--queue-url https://sqs.eu-central-1.amazonaws.com/ACCOUNT/notarai-confidential-pilot01.fifo
--task-arn arn:aws:ecs:eu-central-1:ACCOUNT:task-definition/notarai-confidential-pilot01:REVISION`.

The script validates AWS identity and EU region before reading only ECS task
definition, S3 versioning/lifecycle/**full bounded object version counts** for both encrypted payloads and result markers (no object
body/keys output), SQS main and exact synthetic DLQ retention/redrive, DDB
PITR, CloudTrail trail count and CloudWatch **log group retention metadata**
for the synthetic tenant prefix. S3 is additionally checked for actual
`eu-central-1` bucket location, bucket-level replication configuration,
Object Lock configuration and **bounded, complete** version/delete-marker counts across every S3 page for both allowlisted prefixes: `confidential/` and `confidential-results/`. A missing cursor, pagination loop or inventory exceeding 50 pages fails closed.
The script distinguishes `none-reported` from `unverified` permissions,
uses S3 `ExpectedBucketOwner` equal to the verified STS account on **every**
bucket metadata request, and never claims complete S3 deletion based on a
partial page. A missing S3 read permission means `unverified` or an explicit
BLOCKED error, never an inferred clean audit.
It never reads object bodies, queued messages, CloudTrail event bodies,
CloudWatch lines or KMS keys. Output is a sanitized **metadata** report, not
a forensic assertion about memory or plaintext absence. No AWS read has been
performed in this PR from this conversation.

AWS documentation used to scope retention uncertainty:
- DynamoDB PITR default 35 days; configurable 1–35:
  https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Point-in-time-recovery.html
- S3 delete markers do not delete all versions:
  https://docs.aws.amazon.com/AmazonS3/latest/userguide/DeletingObjectVersions.html

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
| K2 six synthetic scenarios | BLOCKED | Engineering / CI | Synthetic tests + read-only auditor committed; must verify current HEAD green CI and limitations |
| K3 no persistent plaintext | BLOCKED | AWS operations | Static controls exist; actual guest/S3/snapshots audit missing |
| K4 legally approved exact retention | BLOCKED | Controller / counsel / AWS | Template periods known; CloudTrail/LLM/PITR and legal approvals missing |
| K5 recovery without operator backdoor | BLOCKED | Independent custodian | Negative static tests added; actual signed recovery/revocation not proven |
| K6 live Nitro evidence | BLOCKED | Independent auditor | Requires approved AWS test; not run here |

**Gate:** draft remains open until K1–K6 are all PASS, current commit CI is
green with zero critical skips, and links to live external evidence exist.
Do not market verified Zero Knowledge / Zero Operator Access.
