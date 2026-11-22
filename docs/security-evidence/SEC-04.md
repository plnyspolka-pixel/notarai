# SEC-04 evidence: NotarAI AI/LLM trust boundary

Date: 2026-11-22 UTC. Scope: PR #69, synthetic-only, eu-central-1.
Owner: NotarAI SEC-04 implementer. State: **INCOMPLETE / DRAFT**.
Current head SHA: see PR #69 (branch advances during implementation).
No AWS deployment, customer data, new IAM permissions or production inference were used.

## Observable changes

- `confidential/ai_boundary.py`: explicit pinned provider/model/region/operation,
  separate external-processing and retention evidence gates, schema-only
  operator output and telemetry. All decisions involving non-attested inference
  have `zk_status=UNVERIFIED`; missing policy denies.
- `bedrock.py`: before any `converse_stream`, confidential runtime
  `NOTARAI_CONFIDENTIAL_REQUIRED=1` denies Bedrock network requests.
  Legacy Bedrock remains a separate, externally processed, **non-ZK** feature.
  Upstream cache error text is no longer logged. Generic validation messages
  replace provider text, and AWS error codes are bounded identifiers.
- `scripts/audit_confidential_ai_routes.py`: full-repository **Python static**
  call-site scan; new AI/HTTP direct usage inside `confidential/` fails CI.
  The scan does not capture JS, native binaries, indirect imports, dynamic
  reflection or actual data retention. It is not a 100%-complete dataflow proof.
- `test_confidential_zk_ai_boundary.py`: offline tests for boundary,
  adversarial changes, injections, no fallback and output/trace minimization.
- `confidential/worker.py`: `validate_worker_marker` enforces an exact
  metadata-only shape before Nitro writes its S3 result marker.
- `dziennik.py` and `app.py`: no raw AWS error messages or request path values
  in unhandled application error logs; route template only.
- `.github/workflows/ci.yml` and `confidential-browser.yml`: checks added.

## Dataflow inventory (verified by code reading, not by traffic capture)

| Route | Code entry and sink | Plaintext exposure | Region / subprocessors | Retention / evidence | Boundary status |
|---|---|---|---|---|---|
| LEGACY-01 | `app.py` -> `bedrock.py` -> AWS `bedrock-runtime` ConverseStream | App process, AWS Bedrock inference; scanned page images, extracted text, draft/QA/form data | `config.REGION`, default `eu-central-1`; AWS and selected model provider | Bedrock prompt `cachePoint` exists; runtime retention and independent subprocessor evidence not in this PR | **ZK UNVERIFIED** |
| LEGACY-02 | `bedrock.py` -> Bedrock prompt caching and numeric token metrics `tokenomia.py` | Model-side cached prompt prefix may contain template, context or case data; app logs numeric usage | Bedrock via default EU profile | Specific cache TTL noted in `docs/cache-promptu.md`; independent deletion/retention audit missing | **BLOCKED** |
| LEGACY-03 | `transkrypcja.py` -> local faster-whisper | Audio plaintext on host CPU and temporary file (unlinked after job) | Local host, download origin of model not independently checked | Temporary file deletion in code; host swap/backup/telemetry evidence missing | **ZK UNVERIFIED** |
| PILOT-01 | `confidential/router.py` -> S3 ciphertext -> `confidential/worker.py` -> Nitro demo form | Decryption only in intended Nitro worker; no inference in current guest | `eu-central-1` pilot AWS KMS / S3 / SQS | Hardware, independent custodian and complete AWS logs require SEC-07/SEC-11 proof | **BLOCKED** |
| EXP-01 | `tools/agent_factory/forge_llm.py` -> loopback Chat Completions | Synthetic integer-only fixtures, not customer docs | Local 127.0.0.1; location of remote GPU behind any tunnel not provable | Local SQLite metrics; test data only | **NOT ZK CLAIMED** |
| EXP-02 | `tools/agent_factory/salad_vllm.py` -> external Salad GPU | Explicitly public repo/synthetic code only; never case data | External provider, outside EU possible | Provider logs/retention not established | **DO NOT SEND CUSTOMER DATA** |
| OCR-01 | `bedrock.py` scanned page/image transcription; `dokumenty.py` local preparation | Original scans in app prior to Bedrock; remote model sees page content | Bedrock EU profile, not attested enclave | Same as LEGACY-01 | **ZK UNVERIFIED** |
| EMB-01 | No production embedding adapter confirmed in inspected files | Unknown until complete runtime inventory | Unknown | Unknown | **BLOCKED** |
| LOG-01 | `app.py`, `bedrock.py`, `pomocnik/klient.py`, `tokenomia.py` logs/metrics | String IDs and some exception paths exist; no blanket no-PII assurance | Application/CloudWatch/etc. need runtime inspection | Log retention/permissions unverified | **BLOCKED** |

This inventory is an audited starting point, NOT proof that every possible
dynamic source/sink has been catalogued. `K1` needs independent review of
JS/browser/UI, SDK wrapping, OCR services, support tools, traces and live
network flows, plus a signed snapshot of the dependency graph. No fabricated
"100% scanned" claim.

## Threat model and controls

**Attacker:** NotarAI web/backend operator, a compromised host, malicious
document/prompt, a changed model or endpoint, bad log config, public API
fallback, and an unapproved processor. Trust roots include independent
custodian, pinned image/release, Nitro hardware attestation and evidence
external to the operator AWS account. These are **not yet proven here**.

- An untrusted web backend cannot be declared Zero Knowledge merely because
  its AWS Bedrock model is in the EU.
- `NOTARAI_CONFIDENTIAL_REQUIRED=1` is a defense-in-depth guard, **not**
  a proof that every confidential request stays inside Nitro. A malicious
  operator may alter the backend, environment or release until independent
  attestation, custody and release verification are enforced.
- A model output is never trusted to choose a URL, tool, signature or submit.
  The operator-result schema only accepts preview metadata. Synthetic canary
  tests cannot establish absence of all PII exfiltration in production.
- No strict ZK hardware-pass can be produced by the policy module or mocks.
  Running an LLM *inside* Nitro with externally attested image/model and
  reproducible I/O policy would require separate SEC-07 validation.

## Acceptance matrix

| Criterion | Status | Evidence / next proof |
|---|---|---|
| K1: 100% AI routes | **BLOCKED** | Python call-site script and initial table; add JS/native/dynamic/network inventory and independent review |
| K2: no unapproved plaintext | **BLOCKED** | `test_k2_*` deny tests and real dispatch guard; missing live flow trace and independent hardware boundary verification |
| K3: six negative attacks | **BLOCKED** | `test_k3_*`, output and telemetry checks added; requires green CI on final SHA and adversarial network evidence |
| K4: two fallback denials | **BLOCKED** | `test_k4_*`; no separate public API fallback in `bedrock.py`; actual live timeout/egress not captured |
| K5: retention and subprocessors | **BLOCKED** | Missing independent processor/retention documentation, CloudWatch trace capture and signed deletion proof |
| K6: strict ZK refusal outside Nitro | **BLOCKED** | `test_k6_*`; true Nitro model-inference evidence not available, SEC-07 required |

Target local command: `python -m pytest -q test_confidential_zk_ai_boundary.py`.
Additional route gate: `python scripts/audit_confidential_ai_routes.py --json`.
**Observed CI for earlier SHA `269be7df372085069f00437139f8b34d23e7af29`:**
- Python + JS tests: `1972 passed, 3 failed, 10 skipped` (three AST-fixture
  strings wrongly escaped; fixed by `b1bfd2bb5ec0bcdece70960e068f30d6727d55c0`).
  Workflow run: https://github.com/plnyspolka-pixel/notarai/actions/runs/44981313392
- Confidential tests: `270 passed, 3 failed`, same fixture error.
  Workflow run: https://github.com/plnyspolka-pixel/notarai/actions/runs/44981313356
- Security workflow for earlier SHA: PASS.
  https://github.com/plnyspolka-pixel/notarai/actions/runs/44981313367

**Current head is newer than these results; its CI is NOT YET VERIFIED.**
There is no independently verified Nitro LLM, custody, retention or subprocessors
proof. Do not infer green CI from old SHA. No local run was performed.

Completion requires K1-K6 all PASS with verifiable evidence, 0 FAIL /
BLOCKED / UNVERIFIED, and green CI for the exact final head SHA. Until then
PR #69 stays **DRAFT** and `zero_knowledge_verified` is **false**.

## Dependencies inspected (2026-11-22)

- #57 `d2129a8a39ad2855aee9d1c1b5f0ba9d70881cdc`, open;
- #60 `44aa2877d31a2023b5732a1b5c1a19f1a7205685`, open;
- #61 `4c68c3a1b9a29f5e94f23429a9b8aa37a9c48d51`, open;
- #62 `d68532df0b77e959d4dbb2724d35e319d418880d`, open;
- #65 `d46e4896fcd0e2cd49295afdc5fd34933db0c68e`, open.
- #69 is based on #65, independently of the concurrent SEC-03 branch #68.

No AUTO submit, signing, filing or portal access was added.


## 2026-11-22 regional routing hardening
- Worker `_config()`, preview enqueue URL and encrypted-envelope KMS key
  validation now require **exactly eu-central-1**, not arbitrary `eu-*`.
- Browser encryption rejects KMS key ARNs from other regions; AUTO policy
  client requires the backend to state AI inference and strict ZK are disabled
  before queueing a synthetic preview. The pilot UI no longer claims real
  AI analysis is active.
- This checks address configuration only. **The geographical location of S3
  bucket storage remains UNVERIFIED** until independently checked via AWS
  bucket-region metadata and infra evidence; do not infer region from a name.


## K1 Python + browser static inventory increment
`scripts/audit_confidential_ai_routes.py` now emits a v2 inventory of both
Python model/network primitives and JavaScript transport primitives, including
dangerous WebSocket/beacon/XHR/remote-fetch/eval classes in
`static/confidential*.js`. CI rejects risky JS transport sites in those
clients. The report exports **only file/line/mechanism**, not code snippets.

**Limitation:** regex scanning is not JS AST, misses indirect/dynamic sinks and
code loaded at runtime; synthetic JS checks and source scanning are NOT 100%
coverage. K1 remains BLOCKED until dynamic runtime network observation and
independent dependency inventory.


## Legacy error-to-client content containment
A real error path in `bedrock.py` previously constructed a
`ValueError` that contained the scanned document filename. The legacy
`bedrock.opis_bledu()` also reflected raw `ValueError` messages into
FastAPI error responses. SEC-04 removes that filename from the
exception and returns only static error categories for `ValueError`
and `Przeciazenie`. Offline tests use fictional document names and
synthetic ID canaries. This mitigates one output/log channel; it does
not prove complete PII-free monitoring or strict ZK.


## Reproducible static evidence artifact (still NOT independent ZK proof)
Both CI workflows now upload their SEC-04 route inventories as short-lived
artifacts (14-day retention): `sec04-ai-routes-ci` and
`sec04-ai-routes-confidential`. Only file paths, numeric lines and mechanism
codes are included, never file contents, document text or model output.
Client AUTO policy negative tests run in the general CI and confidential
Chromium workflow. This closes the previous audit-report loss on runner
shutdown; K1 remains BLOCKED because dynamic dependency and live egress
coverage are not demonstrated.


## S3 exact-region enforcement on the decryption path
The Nitro worker now executes `get_bucket_location` and requires a
positive `LocationConstraint == eu-central-1` result **before queue
consumption, durable job claim and any envelope decryption**. Provider
errors fail closed with a code-only exception. The Nitro IAM role must
have read-only `s3:GetBucketLocation`; missing permission blocks work
instead of silently assuming residency. Offline negative tests cover
`eu-west-1`, `us-east-1`, historical `EU`, absent metadata and errors.

**This is a code-level control, not a live independently attested AWS
check.** The backend's own S3 bucket location and custody evidence remain
unverified until SEC-07/SEC-11 proofs; K2/K6 remain BLOCKED.


## Least-privilege IAM synchronization
`infra/notarai-confidential-task.yaml` now explicitly grants the
worker's task role `s3:GetBucketLocation` **only on its existing
`EncryptedBucketName` bucket ARN**, not `s3:ListAllMyBuckets` and not
a wildcard resource. An offline CloudFormation test checks this grant.
This is an un-deployed template change and does not establish that the
live IAM role already has permission.


## Browser API fail-closed schema hardening
The confidential AUTO browser client now validates exact public-policy,
queue and job-status response keys and types, including `submitted === false`
and `can_submit === false` (not merely `!== true`). It requires the
server's known stage allow/deny lists and disabled AI boundary flags;
unknown response keys carrying simulated document data are rejected.
Each queue/status action reloads the security policy so revoked capabilities
do not rely on a stale in-memory response. Offline Node tests cover
type confusion, additional fields, stage escalation and revocation.
The authenticated backend remains authoritative.


## Direct same-origin fetch policy for confidential client
SEC-04 static audit now denies any fetch target in
`static/confidential*.js` unless the call begins with a literal
`/api/confidential/` path. The AUTO client no longer calls
`fetch(path)` with a dynamically assembled target; it concatenates
validated identifiers onto a static same-origin prefix at the
call site. Negative tests reject variable, external and unrelated-path
destinations. This prevents a class of accidental or malicious dynamic
egress paths, but source-string scanning is not a full JS AST and is
not substitute for CSP/browser network tests or independent egress proof.


## Runtime emergency feature revocation
`confidential.router._scope()` now re-reads the global
`PIECZAPP_CONFIDENTIAL_ENABLED` flag on **every** API request.
Previously `app.py` only checked this flag when mounting the router at
startup, so a runtime flag change alone would not revoke an already
mounted confidential endpoint. An offline API regression test covers
policy, preview queue and status paths under a revoked flag. This
is an application-level kill switch, not tamper-proof authority against
a hostile backend operator or a substitute for independent custody.
