# NotarAI 2.0 — local-first / Bedrock-only

Development track separate from V1. No production deployment or migration.
Run only with synthetic data until security review, AWS policy validation and Windows/mobile integration tests are complete.

## Non-negotiable constraints
- Documents, CRM, indexes, conversation history, audit and keys remain on authorized endpoints.
- AWS Bedrock is the only AI inference provider. Transient inference is not the same as local-only processing. EU-only approved model IDs, retention and invocation logging must be verified before real data can be sent.
- No S3, cloud document persistence, hosted conversation state or cloud fallback.
- Existing V1 and its production configuration remain unchanged. No implicit import.
- Mobile: private authenticated transport, optional encrypted offline replicas, explicit per-device access; reject stale versions, never silently overwrite.
- Offline AI is not available. If all authorized replicas are offline, uncached files are unavailable.
- No extra hardware required. Wake-on-LAN is best-effort.

## Phase 1 (prototype)
Python worker, authenticated loopback API, encrypted SQLite document revisions and explicit compare-and-set versioning. Bedrock integration disabled by default; only synthetic test data permitted until release gates pass.
The existing V1 uses Python, so the prototype reuses that runtime instead of introducing .NET immediately.

## Next phases
1. Windows service + interactive session agent, DPAPI/TPM key storage, signed installer and update channels.
2. Mesh VPN with authenticated device pairing and revocation; no public worker endpoints; per-device identities, TLS and permissions.
3. Pocket mobile native client with hardware-backed keys, selective offline sync, conflict resolution and biometric unlock.
4. DOCX/PDF editing and voice commands with preview and approval; RejNET/Word session agent.
5. Bedrock EU account policy enforcement, privacy review, real end-to-end synthetic-data tests.
6. Backup/restore, independent audit, device theft and failure drills; explicit migration wizard.

## Prototype usage
From v2: create a Python 3.11+ virtual environment, install requirements, set NOTARAI_V2_HOME to a local non-synced directory, run python -m worker.init_vault, then python -m worker.api. The initializer prints a bearer token once. Do not store it in a shared or synced directory. The key is currently file-based for development only, not production-grade. Run pytest -q for tests.

Do not expose the development API to the LAN or internet. No production credentials or data in this public repository.
