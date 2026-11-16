# Hybrid Coding Factory — benchmark of orchestration, not isolated models

**Decision (2026-11-16):** The research target is **augmentation of a premium lead programmer (Claude Code or Codex) with cheap CPU/GPU coding workers**, not raw coding accuracy of any single open model.

## Research question

Can a lead programmer reliably deliver more accepted, maintainable features per unit of premium-model time and total cost, by delegating scoped implementation/debugging/research to cheaper models?

**Keep the previously measured Qwen-7B 2/30 as a diagnostic**, not as a go/no-go verdict on the hybrid architecture. A standalone model in a one-turn task is not a delegated software engineering workflow.

## Intended operating loop

1. **Human requirement** -> premium lead creates a design, decomposes into atomic verifiable tickets, checks cross-module dependencies and legal/security constraints.
2. **Dispatch/risk assessment** -> route research, test drafting, narrow implementation, refactors and routine diagnosis to cheap workers. Reserve architectural trade-offs, privileged actions, security-critical business rules and complex integration for the premium lead.
3. **Isolated execution** -> local CPU/GPU model receives a bounded work package, an explicit interface contract, versioned dependencies and ONLY an approved, synthetic worktree. No deployment credentials, private customer data, GitHub write token, or unreviewed shell access.
4. **Independent grading** -> unit tests, integration tests, static checks, visual tests where appropriate. Grader data is held outside the worker's editable workspace.
5. **Bounded repair** -> return actionable, sanitized failure categories and reproduction evidence; max two worker retries; preserve last known passing baseline. Count tokens and wall time for all attempts.
6. **Escalation** -> premium lead receives terse, evidence-backed context when the worker repeatedly fails, changes too much, crosses a risky boundary, or causes regressions. Premium lead can re-specify, take over coding, or reject.
7. **Final integration** -> premium lead reviews architecture and PR diff; mandatory CI and human confirmation for sensitive actions. No automatic production deployment.
8. **Knowledge update** -> only independently verified decisions/test outcomes become memory, bound to repository SHA and source hash. Discard stale memory on changes.

**Critical principle:** Claude/Codex is the *manager of goals, interfaces, integration and exceptions*, not an expensive reviewer of every trivial line. The independent test runner does bulk verification.

## Experiments using the same tasks and base commits

| Arm | Lead programmer | Low-cost worker | Verification / retries |
| --- | --- | --- | --- |
| A — premium baseline | Premium model codes all tasks | none | fixed CI acceptance |
| B — naive delegation | Premium designs and reviews | CPU/GPU model writes first diff | fixed CI; premium fixes remaining defects |
| C — structured factory | Premium designs, routes, integrates and handles escalations | same CPU/GPU model | explicit contracts, incremental tests, two cheap repair attempts, selective premium takeover |
| D — memory/context | same lead and model as C | same worker | same C, with commit-bound memory and smart retrieval |

Compare **A vs B** to measure benefit from delegation; **B vs C** to measure *the orchestration method*; **C vs D** to measure memory/context benefits. The cheap model must be held constant within paired comparisons. Match runtime budgets, task ordering and grading inputs.

Our current 30 synthetic coding tasks are a **cheap smoke and development suite**, not a substitute for real feature tickets. Add a separate acceptance suite of multi-file, long-horizon, realistic non-production work before claiming enterprise engineering improvement.

## Signals to record

- Task acceptance in independently controlled tests; end-to-end sequence completion; regressions after integration.
- Premium lead tokens and minutes **per accepted change**, number of escalations / premium takeovers.
- Cheap worker CPU/GPU seconds, rental or allocated CI cost, retries, test calls.
- Wall-clock turnaround, complexity and risk category; defects found in later revisions.
- A/B differences with confidence intervals and full failures. Not all thirty checkpoints are statistically independent.

Total cost = premium-model cost (or defensible subscription allocation) + worker compute + runner/test costs + human-review time. Unknown inputs remain **unknown**, not 0. Never claim cost reduction based only on cheaper tokens or a synthetic 2/30 result.

## What is already working, and what is not

**Working:** 30 synthetic task cards, independently specified grader fixtures, restricted Docker verifier, offline tests, actual CPU-based coding inference and recorded trial artifacts.

**Missing:** authenticated premium Claude Code/Codex executor; approval-scoped delegation bridge; validated cost accounting; authenticated independent verifier attestations; realistic multi-file task suite; funded and authenticated GPU backend. No claim that a real A/B/C hybrid lead-programmer experiment has run yet.

## Immediate implementation order

- **P0:** create machine-readable hand-off contracts, routing and escalation policy. Unit-test risk boundaries.
- **P0:** log exact worker input hashes, source diffs, verifier outputs, retries and escalation decisions.
- **P1:** add a constrained Claude Code/Codex connector so the lead can submit/receive work packets without granting workers broad repository/production access.
- **P1:** test A/B/C on the thirty-task diagnostic suite, then repeat on realistic NotarAI/Finance You feature tickets with synthetic data.
- **P2:** move workers from CPU to approved EU or globally appropriate GPU providers; use compute cost and latency measurements to select the appropriate backend.

**No automatic merge, no production access, no credential copying to workers.**
