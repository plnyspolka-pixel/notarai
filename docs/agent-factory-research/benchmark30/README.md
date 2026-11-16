# Benchmark30 · 6 × 5 sequential synthetic coding tasks

**Status: executable *preparation and deterministic validation*, not a completed Claude/LLM evaluation.**

The suite contains 30 task cards and 61 test cases distributed among six independent synthetic projects: `catalog`, `permissions`, `slots`, `deps`, `ledger`, and `scrub`. Each project evolves over five sequential requirements. Every subsequent edit must preserve earlier tests. We deliberately separate **specification** from **verification**: do not give the agent `/grader/cases.json` as a working file.

## Offline commands (no model calls)

```bash
python -m tools.agent_factory.benchmark30 validate
python -m tools.agent_factory.benchmark30 plan
python -m tools.agent_factory.benchmark30 spec T01
python -m pytest -q tests/test_agent_benchmark30.py
python -m tools.agent_factory.benchmark30 prepare --output /tmp/notarai-benchmark30-$(date +%s)
```

`prepare` creates six *new*, synthetic workspaces containing only starter `solution.py` and README files; it never overwrites existing content. This command deliberately does not execute untrusted code or contact Claude.

## Real agent run (needs a separate authorized isolated worker)

Perform **30 steps in order** T01..T30, keeping each chain workspace intact for its five stages. Ask the coding agent to edit only `<chain>/solution.py`. Use one model and identical budgets for a first baseline. Keep verifier fixtures and approval controls outside the writable worktree; do not mount the main NotarAI repo, host HOME, credentials, cloud IAM roles, browser profiles or Docker socket into the agent.

An optional `benchmark30_docker.py` wrapper provides single-stage verification on an **already trusted disposable VM only**. To invoke it, an operator must independently audit the VM, pre-pull an immutable image with a verified digest, and set `AGENT_BENCH30_ISOLATED_VM_APPROVED=SYNTHETIC_DISPOSABLE_VM_ONLY` in the VM. The agent itself must not receive Docker access. The wrapper uses `--network none`, no privileges, read-only mounts, CPU/memory/pid limits, a non-root user and a hard timeout. A Docker daemon on the host is not a security boundary. It emits local outcomes, **not authenticated signed CI attestations**.

Example, **illustrative only** (requires the real audited image digest and an authorized disposable VM):

```bash
python -m tools.agent_factory.benchmark30_docker \
  --workspace /tmp/isolated-bench30 --chain catalog --upto 1 \
  --image 'python:3.12-slim@sha256:<VERIFIED_SHA256>'
```

## Evidence, interpretation and study provenance

- `tasks.json`: human-readable task prompts, target module and acceptance criteria.
- `cases.json`: 61 publicly reproducible test vectors. This is **not** an unseen/hidden production benchmark, and 61 tests do not make 30 independent scientific samples.
- `test_agent_benchmark30.py`: validates fixture structure, security/negative paths and reporting. All green means **test harness configured correctly**, not 30 tasks completed by an AI.
- `benchmark30_verifier.py`: imports candidate code; never run on a normal workstation or CI host. Only in the disposable isolated worker invoked via `benchmark30_docker.py`.
- `benchmark30.py report`: refuses to claim verification from ordinary JSON and marks even fake-signed records *UNVERIFIED*. The later CI trust plane must verify signatures and GitHub Actions OIDC provenance.

**Proposed A/B experiments:** baseline-terminal vs code navigation, independent tests, state-aware memory and review. Maintain same model, commit, retry/time budget and executor. Record pass@1, whole-chain success, regressions and accepted change per PLN. When comparing a sequential chain, do not reset the same chain between stages. Execute all prior stage test vectors after each change.

Research anchors: CodeNib (arXiv:2607.25431), SWE-Gate (2609.04167), ExecCritic (2609.09133), StateHarness (2610.17616), Multi-step SWE (2611.07166), MemTrace (2610.04838), Your AI My Shell (2509.22040).

## Limitations

- No real Claude Code execution or measured model cost is provided by this suite alone.
- This is not a statistical replication of the cited studies. The cases are intentionally small and synthetic.
- Static test cases are located in Git; do not claim they are secret to models with full repo access.
- No independent attestation, external authenticated grading service, or production authorization exists yet.
