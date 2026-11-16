# Claude Code: execute Benchmark30 after checkout of PR #44

**Mandate:** start with the 30-task synthetic suite now, but only in a properly isolated non-production environment. The owner authorizes this coding/research task; this is not permission to use production secrets, sensitive case data, paid GPU beyond an approved budget, public non-EU model routes, or privileged browser actions.

## Repo target

- `plnyspolka-pixel/notarai`
- PR #44, branch `research/coding-agents-100-foundation-20261116`
- Target base `feature/secure-agent-factory-20261115`
- Read `CLAUDE.md`, `docs/agent-factory.md`, `docs/claude-code-handoff-agent-factory.md`, `docs/agent-factory-research/CLAUDE_CODE_HANDOFF_100_PAPERS.md`, and `benchmark30/README.md`.

## Do now (safe offline preflight)

```bash
python -m tools.agent_factory.benchmark30 validate
python -m tools.agent_factory.benchmark30 plan
python -m pytest -q tests/test_agent_benchmark30.py tests/test_research_foundation.py
python -m tools.agent_factory.forge_benchmark --prefix b30-preflight
```

Record exact commits, command exit codes, number of cases, and GitHub CI job URLs. Avoid importing benchmark verifier on the host with candidate code.

## Run 30 tasks when trusted execution is available

1. Confirm dedicated ephemeral VM/worker isolation, hard egress deny, synthetic-only inputs, isolated Git worktree, disabled production/cloud credentials, fixed budgets and manual stop ability. If any fail, **stop and report BLOCKED**.
2. Create six synthetic workspaces using `benchmark30 prepare --output <NEW_TEMP_DIR>` (no forced overwrite). Agent sees the applicable `solution.py` plus only current task specification and relevant previous specs, **not grader fixtures**.
3. For each T01..T30 call `benchmark30 spec TXX`, ask Claude Code for an implementation, and require a bounded diff in that chain's `solution.py`. Keep the same workspace from steps 1 to 5 for each chain.
4. At each step, execute the current and **every prior** stage test with an independently controlled verifier in a disposable VM (`benchmark30_docker.py` only after independent environment attestation). Agent cannot alter tests, expected results, runner code or output labels. A failing step must be recorded, not silently retried indefinitely. Stop per-task upon budget/timeout exhaustion.
5. Run a *single* controlled 30-task baseline first. Do not launch a 5-variant 150-run test matrix without agreed cost limits, repeatable settings and an additional approval.
6. Once baseline is reproducible, run paired A/B with fixed model/version, task set, base hash and cost budget: context-index, independent-test, memory and reviewer. No invented timings or savings.
7. Export machine-readable outcomes containing task id, chain, step, model, harness revision, base/diff hashes, tests executed, pass/fail, latency, token usage, exact cost currency and FX assumptions, verifier provenance. Mark missing fields `unknown`, never zero.
8. Present failed task causes, behavioral logs without PII, regressions, chain completion and PR with independent reviewer. **No auto-merge, no production deployment.**

## Minimal acceptance criteria

- Exactly 30 task cards (6 chains × 5) and 61 reproducible cases validated.
- At least one baseline result from an actual authorized LLM in isolated worktree, clearly distinguished from offline test preflight.
- Each incremental stage graded cumulatively.
- No secret, model-key or customer data in fixtures, prompts, CI logs or workspaces.
- Verifier not controlled by coding agent; any missing audit proof is a failure of the acceptance gate.
- For possible human handoff, report the exact command needed and why automatic Claude execution is unavailable.

This is **not** an instruction to start Claude Code through GitHub Actions with a copied production secret. No `@claude` automation is configured in the inspected workflows. Provision and approve a constrained Claude runner separately; do not assume a comment will summon Claude.
