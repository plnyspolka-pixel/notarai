# Integration roadmap (research-only, no automatic release)
## P0 — Completed in this branch
- Preserve Agent Forge source, tests, catalog and academic evidence from PR #34.
- Preserve Web Factory source, tests, CI, demo and MCP from PR #35.
- Provide a unified docs and structured catalog for security, sales and frontier research.
- Add offline, dependency-free experiments for event integrity and randomized uplift, with negative tests.
- Define strict data/scope boundaries and approval gates for NotarAI vs Finance You.

## P1 — Next engineering milestones (NOT yet implemented)
- Real OPA/Cedar and OpenFGA integration in a sandbox with deny-on-outage tests, tenant isolation and expiry checks.
- Signed externally witnessed checkpoints (KMS or isolated signer) and verification of rollback/forks.
- Consent-scoped intake adapter with PII minimization and a synthetic staging dataset; data inventory and DPIA.
- Staging test harness combining Agent Forge execution with Web Factory QA; no automatic writes to production.
- Cross-project CI matrix; coverage thresholds; software composition/dependency/license and SBOM reports.

## P2 — Research program
- By-case paired benchmark with locked holdout for code/web/security tasks.
- Human reviewed design-tokens, content quality and accessibility scorecard.
- Uplift, multi-armed bandit and survival modeling on data approved by legal/privacy.
- Chaos/resilience experiments with adversarial MCP/page payloads and controlled network partitions.
- Formal specification of critical policy and audit invariants (TLA+/Apalache/FRET).
- Cost/quality matrix for GPU and video/voice only after capacity and license validation.

## Hard stop conditions
- Never expose investor projects to outside users via search, model retrieval or public/hidden catalog.
- No customer or notarial documents in development fixtures.
- No auto-push, auto-merge, auto-deploy or automatic spending through an agent.
- Production access, key use, customer communications and legal implications require a separately approved change.