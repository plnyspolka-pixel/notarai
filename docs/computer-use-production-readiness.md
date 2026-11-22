# NotarAI Virtual Employee — production readiness and verification gates

**Date:** 2026-11-22. **Status:** production-oriented implementation in draft PR #63, **NOT deployed or production-accepted**.
**Primary rule:** NotarAI must work through the least intrusive authorized integration; apps are not special-cased in Python code. There is no claim of universal 100% compatibility without a real application test.

## Completed in source code

- Unified fallback engine `computer_use/fallback_router.py`: API → DOM → Windows UIA → UIA+vision → visual computer use → human. Uncertain writes never retried automatically.
- `computer_use/native_api.py`, `browser.py`, `winapp.py`, `vision.py`: read-only API, browser actions, WinApp CLI, verified visual read/click/type/navigation; all guarded by trusted profile fields.
- EU Bedrock `Converse` vision opt-in; model is constrained to localization and read/verify. Screenshots are not persisted to app logs, but **plaintext is transmitted to an authorized AI provider** when visual mode is enabled. Do not claim zero knowledge, zero operator access or full confidentiality without independent assessment.
- `profiles.py` + `profile_loader.py`, `discovery.py`: signed tenant-app profiles and metadata-only discovery. `workflows.py`: signed bounded 1–12 step plans, no arbitrary scripts and no signing/sending.
- `worker.py` + `session_lock.py`: one known tenant/app per VM and named Windows desktop mutex across processes.
- `jobs.py`, `daemon.py`, `payloads.py`, `runtime.py`: SQS FIFO → DynamoDB conditional claim → encrypted S3 payload → scoped worker execution → status/result. Expired running lease to `needs_reconciliation`, not blind retry.
- Web console `/virtual-employee` and authenticated `/api/virtual-employee/*`: new jobs, status, approval preview of exact values, cancel, stop/start, read result. Approval/worker control only with proper notarial role. API disabled by default until configured.
- IaC `infra/notarai-ve-control-plane.yaml` (shared metadata, settings, encrypted bucket) and `infra/notarai-ve-tenant.yaml` (tenant queue+DLQ, KMS, IAM, VM+SG, no public RDP, IMDSv2, static EU model policy). No resources were created by this PR.
- Focused CI `.github/workflows/computer-use-ci.yml` and regression tests `tests/test_computer_use_*.py` (test assertions alone do not prove an AWS or Windows deployment).

## Strict production gates (all must be true)

### G1 — Code / CI
- [ ] New Computer Use CI completes successfully on the exact merge commit; no pending/queued/failed checks, no temporary workarounds.
- [ ] Windows PowerShell parser and existing SaaS test suite green; Python compileall and frontend JS syntax green.
- [ ] All tests are fully isolated from real notarial records; zero actual customer data in GitHub Actions logs and artifacts.

### G2 — Legal software and Windows environment
- [ ] At least two distinct, legally licensed kancelaria applications tested on actual provisioned Windows VMs (first candidate RejNET Office); confirm Windows version, desktop/VM use rights, office data access, license seat and database compatibility.
- [ ] Windows VM per tenant boots in EU, no public IP/RDP, connects to required private service endpoints.
- [ ] Tenant Windows bot account is separate from notary user, no qualified signature/PIN/2FA tokens stored or automated; stable interactive session lifecycle under RDP disconnect, logoff and VM reboot.

### G3 — Cross-tenant security (must be verified in AWS, not inferred)
- [ ] Tenant A role cannot read/write tenant B DynamoDB PK, S3 prefix, KMS key, queue, settings; verify real **AccessDenied** responses by assuming each role and cross-access attempts.
- [ ] IAM `sts:AssumeRole` from the NotarAI application task only to provisioned per-tenant roles, and only via trusted registry, with a reviewed trust policy.
- [ ] Settings-table stop switch cannot be disabled by VM worker principal.
- [ ] Separate encryption/key rotation, immutable security evidence, no client data in SQS/DDB metadata/CloudWatch; S3 SSE-KMS and private network validated with live negative tests.
- [ ] No exfiltration to unauthorized destinations: VPC endpoint policy, SG, DNS/firewall and Bedrock EU profile proof for actual model requests.

### G4 — Computer Use behavior, live
- [ ] On each real app test: read customer test field, find case, navigate a menu, fill a fictional field without autosave, and verify result by independent UI state.
- [ ] Vision fallback actually invoked when UIA fails; logs contain only status/technical IDs, screenshot stays transient and is processed only under explicit data authorization.
- [ ] Wrong window/process, modal, CAPTCHAs, signing form, low confidence, changed UI version, timeout after input, lost interactive session -> safe refusal/needs_reconciliation with no unintended write.
- [ ] Device click coordinates verified on multi-monitor/DPI configurations. No action on secure logon/UAC desktop.
- [ ] Full 1–12 step signed workflow tested end-to-end; no partial document write is automatically replayed.

### G5 — Reliable operations
- [ ] Control plane provisioner links tenant record `{tenant_id,queue_url,kms_key_id,control_role_arn}` to newly deployed stack outputs; it must never accept these from user or LLM requests.
- [ ] SSM/bootstrap provisions approved Windows software and agent without credentials in repositories, AMIs or scripts; use secret-resolving runtime injection (Secrets Manager / KMS).
- [ ] Durable outbox reconciliation for SQS publish failures, poison-message handling in DLQ, alarms, runbook, explicit operator resolution of stale claims. (Current code detects and refuses stale actions; outbox alarm/reconciler still pending.)
- [ ] User-initiated stop, worker kill switch, staged deployment, rollback and emergency credential revocation tested.
- [ ] Capacity budget and cold-start measured; actual Windows license, CPU, RAM, SQS, S3, Bedrock costs approved.
- [ ] Notarial privacy, contractual processor obligations, security assessment/DPIA as appropriate and access to records reviewed.

### G6 — Product acceptance
- [ ] Notary signs in to **one NotarAI console**, sees only their own worker and tasks, reviews full action input before approving, sees result with no data leakage.
- [ ] Kancelaria user has **zero NotarAI desktop install**; when local-only database prevents cloud VM, onboarding explicitly identifies and configures approved private connectivity/on-prem VM.
- [ ] No public promise "works with every software" or Zero Knowledge until independently evidenced.

## Deployment status matrix

| Component | Source implementation | Real infrastructure | Real end-to-end |
| --- | --- | --- | --- |
| API/DOM/UIA fallback | Yes | No | No |
| Visual model + Windows input | Yes, opt-in | No | No |
| Tenant jobs SQS+DDB+S3 | Yes | No | No |
| IAM/VM isolated per kancelaria | CloudFormation template | No | No |
| Web console/Cognito checks | Committed behind feature flag | Not deployed | No |
| RejNET/Notaris testing | Test plan only | No | No |
| Interactive Windows user session after reboot | Not yet proven | No | No |

**Production gate:** do NOT merge/deploy to customers until every G1–G6 item is evidenced and approved. Before this point, the claim is "code and infrastructure templates ready for controlled integration testing", NOT "production ready".

## Sources and repo links

- PR #63: https://github.com/plnyspolka-pixel/notarai/pull/63
- Microsoft WinApp UI Automation: https://learn.microsoft.com/en-us/windows/apps/dev-tools/winapp-cli/ui-automation
- Windows UI desktop limitations: https://github.com/microsoft/WinAppCli/blob/main/docs/ui-automation.md
- Existing project security conventions: `CLAUDE.md`, `docs/fallback-policy.md`, `docs/computer-use-implementation.md`.
