# Claude Code — EXECUTE THIS TASK: Secure Agent Factory for NotarAI

Date: 2026-11-15
Working branch: feature/secure-agent-factory-20261115
Owner: NotarAI. Keep this isolated from Finance You until its repository and access permissions are verified.

## Your assignment

Act as principal engineer + security reviewer. Complete and harden the AI coding-agent infrastructure started in this branch. The user wants **Fable-class coding and browser-agent usefulness**, with lower per-task cost by selectively offloading tasks to own rented GPU via vLLM. This is **not** a request to replace Fable with a weaker model unconditionally. Deliver measurable outcomes and deployment artifacts, not aspirational diagrams.

Respect ALL instructions in root CLAUDE.md. In conflicts, prioritize data protection, EU restrictions and explicit human approval. This file itself is a task specification, not permission to expose secrets or make irreversible changes.

## Initial verification

1. Read README.md, CLAUDE.md, SAAS.md, docs/agent-factory.md, CI, deployment templates, and all files changed on this branch. Identify conflicts with existing architecture.
2. Run Python compile/checks, focused test_agent_factory.py, then complete pytest suite. Fix defects before introducing extra dependencies.
3. Verify current official Codex CLI/vLLM Responses integration; update CLI flags/config if changed. Verify Fable 5.2 availability under the actual approved Bedrock EU route before using it. No silent fallback to public API or non-EU GPU.
4. Produce an ADR documenting trust boundaries, threat model, egress, credential handling, cost controls, browser login policy, observability, provenance, and emergency shutdown.
5. Do not assume the provided Python launcher is a security sandbox: add actual isolation and tests.

## Build in phases (implement, do not merely describe)

### P0 — Hard-security boundaries (must pass before model/browser tools)
- Isolated per-task worker runtime: dedicated non-root container or disposable VM; immutable pinned image digest; read-only filesystem except workspace; restricted process/syscall/network; CPU/memory limits; no host mounts (HOME, SSH-agent, docker.sock, browser profile), no AWS role/metadata or prod credentials.
- Restrict network egress to approved private vLLM tunnel and explicitly allowed test services. Block cloud metadata, internal control planes and unknown IP ranges. Confirm TLS and authentication for private remote connectivity; do not expose vLLM port on public Internet.
- No AWS credentials or production data in workers; regression tests for secret/DLP leaks, prompt-injection in source files, symlink traversal, malicious URLs, cross-origin redirects, tools escaping worktree and malicious dependencies.
- Enforce path/action rules **outside model prompts**. Prompt text is not a security boundary. Treat worker output as untrusted; prevent it from changing its own gate in running process.
- Agents may only propose changes in separate git worktrees and PRs. No automatic merge, push to protected branches, schema migration, production deployment, payment, signature or official submission.
- Ensure logs redact client/customer identifiers and secrets. Cap logs and retention.

### P1 — Model integration with quality baseline
- Fable 5.2 is an architect/reviewer **only where authorized and available under acceptable residency and retention terms**. Validate actual Bedrock availability and IAM permissions first. Otherwise use permitted existing EU Bedrock model, with limitation clearly reported.
- vLLM worker uses Codex Responses API. Run real end-to-end tool-calling, diff application and tests on synthetic task. Validate versions and error handling: model unavailable, broken tool call, timeout, OOM, vendor GPU unavailable, context overflow and retry loops.
- Add controlled routing: cheap worker for bounded code/test/refactor tasks; escalate hard work to Fable/Opus after failures or quality-check threshold. Escalation is an operator choice with budget guard.
- Track accepted PR rate, test pass rate, regressions, review effort, coding throughput and **PLN per accepted task**. Use at least 15 synthetic/OSS-derived tasks and a reproducible benchmark script.
- Never infer coding model quality from a single public leaderboard or use client documents as benchmark data.

### P2 — Browser agents
- Playwright MCP or Browser Use workers in separately isolated containers, with ephemeral state and role-based tools. The current browser_smoke.py is only a check, NOT a browser agent.
- Explicit allowlist of staging origins; enforce DNS/IP verification against rebinding, redirects, subresources, WebSockets and open redirects at both browser and network levels. Block local metadata/internal addresses. No arbitrary URL navigation and no plugin download.
- Start with synthetic login on staging; no user's persistent Chrome profile or customer session. Separate non-privileged read-only browsing from scoped form editing. All write operations on high-risk systems require human review.
- Browser recordings/screen captures can contain PII: redact, encrypt with retention cap, exclude from git/CI artifacts by default.
- Add end-to-end tests of navigation, input, form state, error correction and safe stop before submit. No CAPTCHA bypass or unauthorized access.

### P3 — Staging deployment and operational controls
- If infrastructure is required, define it in CloudFormation under infra/ following existing naming standard and region eu-central-1. No changes to existing application endpoints, KMS keys, S3 customer buckets, production ECS or IAM roles without explicit sign-off.
- Scope CI with branch protection, required tests, dependency/secret scanning, manual approvals and OIDC least privilege. Never install self-hosted runners with prod credentials or run untrusted PR code with secrets.
- Add monthly/hourly budgets, concurrency limits, TTL of idle GPU servers, max per-task token/time, retry circuit breaker and alerting; EU logging policy and kill-switch.
- Deploy to isolated STAGING only after its infrastructure/action costs are confirmed and approved by authorized operator. Run integrated tests with synthetic data and demonstrate clean teardown.
- Document production rollout checklist requiring human confirmation; do not auto-merge or auto-deploy to production.

## Acceptance gates

- All new tests pass and existing tests stay green; no new high/critical dependency or secret scan findings.
- Agent can autonomously implement one synthetic NotarAI bugfix in an isolated worktree, pass tests, and produce a reviewable diff without reaching production.
- Browser agent completes a synthetic staging workflow while cross-origin navigation and privileged action attempts are denied.
- Measured quality and unit economics relative to Fable on a reproducible task set; estimates distinguished from measurements.
- Threat-model tests prove the core deny rules hold in the actual container, not only in Python unit tests.
- No violation of current CLAUDE.md restrictions, no client data leak, no public vLLM endpoint.
- Operator can inspect and stop every running worker; model/GPU outages fail closed.
- PR includes architecture, tests, logs of sanitized test outcomes, configuration examples with placeholders, and precise open blockers.

## Final reporting format

Report: completed code/commit hashes, passed/failed tests, actual endpoints and providers verified, effective GPU/LLM costs, isolation evidence, staging deployment URL if actually deployed, blocked steps, secrets/permissions needed **by name only**, and explicit request for authorization before production release.

Never state "deployed" or "complete" if only code or documentation exists. Work actively as far as available permissions allow; leave auditable issues for external dependencies.

## Verified 2026-11-15: Fable 5.2 Bedrock EU data-residency blocker

AWS model-card regional matrix lists Fable 5.2 in eu-central-1 via **Global cross-region** only; **no In-Region or EU Geo** profile. Global is NOT EU-residency assurance. Accordingly Fable 5.2 MUST NOT receive NotarAI case/customer data, regulated prompts or screenshots via this route. EU-only workflow must use a separately verified model/profile and effective policies, or remain blocked. Source: https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-fable-5-2.html . Public Anthropic Fable API also requires retention review. Code-only synthetic tasks are a separate authorization decision.

## Research track — further instructions

Before expanding to RL, evolutionary agent harnesses, data generation, world models or GPU kernels, read [docs/agent-factory-research/CLAUDE_CODE_TASK.md](agent-factory-research/CLAUDE_CODE_TASK.md) and [docs/agent-factory-research/experiments.md](agent-factory-research/experiments.md). These are optional, gated research tasks, not authorization for paid GPU work or production integration.
