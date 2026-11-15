# Unified engineering architecture (2026-11-15)

## Control plane
Operator -> proposal queue -> OPA/Cedar policy gateway -> scoped agent identity -> sandbox job -> independent evaluator -> human approval -> *separate* project PR. Deny-by-default; promotion never depends solely on the agent's own self-assessment.

Use Agent Forge as the basic **execution substrate**:
- Scheduler with retries, pause/resume, leases and state.
- Model adapter (OpenAI-compatible/vLLM); record model, region, engine, cost and seed.
- Worktree-per-task and container sandbox with explicit resource limits.
- Evaluation from immutable inputs; agent lacks write access to evaluator and holdout.
- Browser tools restricted to local/staging fixtures; no customer login.

Web Factory provides **visual QA substrate**:
- Screenshot matrix, accessibility errors and visual diffs.
- DTCG design tokens and reviewed OSS registry.
- Read/audit MCP tools, no automatic baseline writing or deployment.
- Agents propose pages; deterministic checks and human review decide acceptance.

Security is a **cross-cutting system**, not a prompt:
- Identity plane: human/service/agent identities, purpose, bounded delegation, revocation.
- Authorization plane: OpenFGA for object relations; OPA/Cedar for contextual actions; deny on unavailable policy services.
- Execution plane: network isolation, time/memory/GPU ceilings; isolated credentials; no untrusted task can call secret services.
- Provenance plane: signatures over artifacts and reviewed events, external witness/WORM/independent checkpoint verification. Prototype hashchain is not a replacement.
- Recovery plane: credential rotation, disaster recovery, backup immutability, replay, chaos tests and incident handling.

Sales Intelligence is an **isolated experimental analytics plane**:
- Consent-scoped event producer -> schema validation/minimization -> event queue -> ClickHouse/PostgreSQL sandbox -> controlled feature builder -> experiment registry -> offline policy evaluation.
- Separate causal question: observation is not causality. Use randomized outreach assignments or carefully qualified quasi-experimental techniques.
- No unrestricted session replay or undisclosed cross-site tracking; retention, lawful basis, opt-out and access controls are prerequisites.
- No investor project listings or automated investment matchmaking exposed by this lab.

Frontier Research is the **evidence/evaluation plane**:
- Curated refs with status: official program goal / peer-reviewed finding / preprint / software artifact / vendor description.
- Benchmark cards require dataset/license, hardware, release, task definition, baselines, uncertainty, evaluator integrity.
- DICE-style coordination and distributed resilience are inspiration for simulation; no unverified claims of military-grade certification.
- Export research as proposed experiments, not production feature flags.

## Interface contract (not yet deployed)
Event envelope schema: contracts/event.schema.json. Producing services must validate server-side and attach a purpose + source classification; PII is not allowed in the research bus. Project-specific adapters (future) must publish pseudonymous only when consent and DPIA support that purpose.

## Project separation
**NotarAI:** strict tenant isolation, professional secrecy, notarial documents never enter research. User-visible approvals and non-repudiation need qualified legal/technical review.

**Finance You:** never let the research/index plane expose investor projects. Finance You remains the only party with access to its own restricted project data; an experimental recommendation model cannot bypass authorization or legal compliance.

## Definition of done for new module
Structured inputs; deterministic fixtures; tests with bad/missing inputs; network/secret-denial tests; reviewable observability; measured baseline; licensing review; rollback; distinct staging deployment approval; security and privacy sign-off.