# NotarAI 2.0 — Codex implementation handoff

## Mandate
Develop on a branch based on notarai-2.0, not master. Keep V1 and production deployments untouched. Preserve chat-first UX. No cloud storage of documents, CRM, prompts, conversation history, embeddings, audit or backups. AWS Bedrock is the only inference provider; real data blocked until EU routing, retention, logging, contracts and privacy gates are verified. No required additional hardware. Endpoints may hold explicitly authorized encrypted replicas. No secrets or real client records in this public repository.

## Read first
- v2/README.md
- v2/CONNECT.md
- v2/POCKET.md
- v2/worker/connect.py and winapp_adapter.py
- v2/worker/api.py, devices.py, vault.py, sync.py, bedrock.py
- v2/tests and .github/workflows/notarai-v2-tests.yml

## Build sequence (small reviewable PRs)
1. Baseline: run existing tests on Windows/Linux; pin dependencies; document actual output and failures. Verify current WinApp CLI syntax against installed version and upstream docs.
2. Desktop worker: separate Windows service from interactive user agent; authenticated local IPC, least privilege, explicit session ownership, OS-backed secrets (DPAPI/TPM), signed installer and updates. Never expose the development API directly.
3. Connect SDK: versioned typed operation schemas, app identification, capability probes, per-app policy, approval bound to exact arguments/target, postconditions and local receipts. No arbitrary shell or model-supplied executable paths. No fallback after uncertain mutation.
4. Adapter factory: discover authorized installed apps; prefer official API/MCP/CLI/import-export, then Playwright, WinApp CLI/FlaUI UIA3/FlaUI-MCP, finally scoped visual automation. Use CLI-Anything to generate candidate harnesses where appropriate; inspect, pin, test and sign before activation. Never run generated code automatically.
5. Demonstration: investigate Microsoft Record-and-Run for recording semantic UI actions, parameterization and replay; remove/disable non-Bedrock inference and cloud persistence. Store procedures locally. Investigate Stemma for DOCX tracked changes, not procedure recording.
6. First integrations: Word/Open XML, Excel, LibreOffice, RejNET Office (authorized sandbox and vendor-supported interface first); browser extension via authenticated native messaging. Record actual compatibility, version and licensing. Test only synthetic cases.
7. Mesh/Pocket: private WireGuard-compatible transport, device-bound keys, explicit pairing and revocation, encrypted offline native mobile cache, conflict-aware sync and verified failover. No public ports, no central document store. Wake-on-LAN optional, with honest availability limits.
8. Bedrock: centrally defined local policy with approved EU model IDs and verified retention settings; no invocation content logs or cloud state. Local context selection, pseudonymization and tool-call policy enforcement. Synthetic end-to-end tests before real data.
9. Security and recovery: per-case permissions, encrypted backup and restore, stolen device, crash and network failure drills, independent review; opt-in V1 migration only.

## Definition of done
Actual runnable code, reproducible tests and recorded results; no claim of real integration from mock tests. Each PR includes risks, rollback, compatibility evidence and remaining blockers. All irreversible/external actions (sending, signing, filing, deleting) require explicit authorization and independently verified result. No production deployment without separate approval.

## Initial Codex task
Start with steps 1–3, then implement the first safe Word/LibreOffice adapter. Open draft PRs targeting notarai-2.0. Do not merge to master.
