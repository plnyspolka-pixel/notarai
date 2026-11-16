# Research-backed coding-agent foundation (2026-11-16)

Status: **local tested foundation / research branch candidate**; NOT model integration, not production-ready, not a substitute for sandbox isolation. Parent architecture: `docs/agent-factory.md`, `docs/claude-code-handoff-agent-factory.md`, `CLAUDE.md`.

## What has been implemented

| Component | Code / contract | Research | State |
|---|---|---|---|
| ResearchRegistryIngestor | `load_studies`, `catalog_summary` | 100-paper review | DONE, validates sources and duplicates |
| RepositoryEvidenceIndex baseline | `index_repository` | CodeNib, CodeCompass, RepoNav | DONE deterministic lexical + Python AST/TS symbols; LSP/graph NOT YET |
| ProjectStateLedger baseline | `EvidenceLedger` | MemTrace, StateHarness, REM | DONE SQLite metadata, source file hash, pinned commit; no semantic memory yet |
| PatchIndependentVerifier control plane | `freeze_test_plan`, `gate_patch` | ExecCritic, SWE-Gate, SWE-Review | DONE immutable plan digest and deny checks; trusted execution NOT YET |
| HarnessExperimentController baseline | `evaluate_pairs` | SWE-Skills-Bench, Agentless | DONE paired A/B + bootstrap CI; experimental randomization NOT YET |
| LongHorizonTaskSuite reporting | `evaluate_horizon` | ChainSWE, Multi-step SWE, SlopCodeBench | DONE chain-level measurement; verified replay runner NOT YET |
| AgentPolicyEnforcer | static gate only | Your AI, My Shell, IssueTrojanBench | PARTIAL; no runtime process isolation |
| AgentOpsObservability | structured JSON outputs | SWE-Critix, SWE-Gate | PARTIAL; no live OpenTelemetry integration |

## Commands (no external calls)

From repo root:

```bash
python -m pytest -q tests/test_research_foundation.py
python tools/agent_factory/research_foundation.py catalog docs/agent-factory-research/ai-coding-100-2026.jsonl
python tools/agent_factory/research_foundation.py index . "agent factory benchmark"
python tools/agent_factory/research_foundation.py pairs docs/agent-factory-research/fixtures/sample_ab_results.jsonl
```

Never pass actual client data as tasks, logs, prompts, or benchmark fixtures. `index` is read-only and outputs metadata, not source code. Run in isolated dev environment only. Do not point `index` at a checkout containing client files, credentials or sensitive data. Models and untrusted tests must run in a separate hardened sandbox with network denied by default.

## Workflow / trust boundaries

```
[human synthetic requirement]
       |
[Planner / spec normalization] -- human sign-off required on regulated scopes
       |
[Evidence Index] -- results have source file SHA and pinned commit of caller
       |                                   
[Independent Test Plan] -- freeze digest in control-plane storage
       |
[Coder isolated worktree] -- NEVER receives ability to edit frozen tests/gate
       |
[External container runs frozen tests] -- NOT provided by this module
       |
[Reviewer acceptance + security / contract tests]
       |
[gate_patch] -- fail closed on test, review, integrity, risky file
       |
[human PR approval] -- no auto merge or deployment
       |
[Store metadata-only memory; invalidate on commit and file hash]
       |
[paired/chain evaluation] -- compare actual verified outcomes and costs
```

### Key limitations (must not be erased)

1. The test-plan digest is a **logical** integrity primitive. It MUST be held by a separate control-plane account / DB with permissions denied to the Coder. If attacker can modify both plan and expected digest, the check is worthless.
2. `gate_patch` receives `changed_paths`, `test_results`, `review_criteria` from the caller. **Those are not authenticated**. Trust must come from external CI signed artifact/provenance and an approval service, not model-supplied JSON.
3. `approval=True` is an API argument, NOT identity verification. Claude must replace it with trusted signed human-gate decisions before integration.
4. Current lexical index has no graph correctness or freshness guarantees beyond file hashes. Need cache invalidation, LSP, AST / incremental source checks and file ownership graph.
5. Ledger stores only restrictive metadata labels; tests prove staleness after changing a source file or commit. No external storage and no PII in rows.
6. Bootstrap CIs are descriptive. Do NOT claim a causal effect without randomization, frozen tasks, identical model/context budgets and preregistered metrics. Same task+commit is required for each pair; compare runs with same model version and tool allowances.
7. A result marked "numeric_findings" is not necessarily a performance improvement: numbers can describe dataset size. Every metric needs source passage, evaluation protocol and reproduction before selecting for implementation.
8. There are no model API calls, Docker commands, GPU jobs, browser actions or CI runs executed by this code.

## Implementation targets for Claude Code

**P0: safe protocol integration**
- Check current `tools/agent_factory/forge_core.py`, `forge_scheduler.py`, `forge_sandbox.py` and existing tests. Reuse their event/audit storage; do not create a competing execution engine. Add typed adapter interfaces and exact test fixtures.
- Add `ResearchRunManifest` fields: task_id, repo_id, base_commit, model/version, harness/version, seed, tool policy hash, signed test-plan digest, data classification, cost limit, region, evaluator version, trace_id. Record hashes of artifacts, never raw prompts or confidential snippets.
- Wire the gate to **trusted execution outputs** only. Coder cannot forge test results, change the gate, or self-approve. External process/container isolation is a prior gate; Python flags are not security controls.
- Run entire focused pytest suite; do not change runtime app import paths or production endpoints.

**P1: benchmark reproduction**
- Build 30–50 synthetic or appropriately licensed historical tasks. Freeze base commit SHA, issue/spec, gold behavior, known tests, hidden tests, evaluation image digest. Verify original licensing/data compliance before using tasks.
- Run same tasks through: original single agent (baseline), context localizer, frozen independent test agent, reviewer loop, persistent memory. Start with one module added at a time; register outcome, cost and confidence interval. Include regression and prompt-injection challenge sets.
- Count success **per entire 5–15-step chain** (task sequence), not only per fix. Fail if any previously accepted behavior regresses.

**P2: code intelligence + memory**
- Add AST and language-server symbol/call graph for Python and TypeScript with deterministic fallback. Cache under `repo_id@commit` and invalidate indexes when changed sources/call sites are touched.
- Expand ledger to a provenance graph with evidence version, TTL and verification status; use retrieval only when confidence/need justify its cost, evaluate paired vs memory off. Do not ingest secrets, names, files from real customer cases or arbitrary prompt instructions.

**P3: independent testing and verification**
- Generate requirements/tests in a separate process before patch exposure, freeze their snapshots in control plane, run in container/VM isolated from editor. Use independent repository tests, property tests, negative tests, security scans and mutation or hidden variants. Require review constraints, not only test green.
- Log failure reasons with identifiers, no raw content. Block external network, cloud metadata, credentials and protected branches.

**P4: productionization ONLY AFTER AUTHORIZATION**
- Policy server, external identity-based approvals, audit signatures, task kill switch, quotas, protected CI. Verify EU model residency and lawful processing separately; do not inherit assumptions about Bedrock availability.
- Add dashboard: safe accepted patches/PLN, paired success +/- CI, chain survival, contamination, regression, security, review effort, p95 latency, retrieval cost, stale-memory reject rate and quality drift.

## Research mapping (sources and ways to test)

- ExecCritic, arXiv:2609.09133 — independent test agent, test validation baseline against gold, fail-closed tests.
- SWE-Review, arXiv:2607.06065 — generate/review/revise; reviewer blind to author rationale.
- CodeNib, arXiv:2607.25431 — structural+lexical context, context retirement after reading source, compare against grep baseline.
- MemTrace, arXiv:2610.04838 — provenance, state-anchored memory, stale memory rejection.
- REM, arXiv:2610.27377 — retrieve only on task phase / detected difficulty, evict stale irrelevant detail.
- StateHarness, arXiv:2610.17616 — evolving task state with compact working brief, cross-file impact.
- SWE-Gate, arXiv:2609.04167 — function plus reviewer acceptance constraints.
- Multi-step SWE, arXiv:2611.07166 — dependent changes, 5–15 sequential operations.
- SlopCodeBench, arXiv:2603.24755 — code erosion and verbosity.
- SWE-Skills-Bench, arXiv:2603.15401 — skill utility paired A/B, remove useless skills.
- Your AI, My Shell, arXiv:2509.22040 — malicious issue/repository resource vs command execution.
- SWE-Critix, arXiv:2610.13356 — independent trajectory verification.

Full inventory: `ai-coding-100-2026.jsonl`. Records are source/abstract-level research annotations, not verified local performance.

## Acceptance definition of done

- `python -m pytest -q tests/test_research_foundation.py` all green and no regressions in existing `test_agent_factory.py`, `test_agent_forge.py`, `test_agent_forge_sandbox.py`.
- A/B report from at least 30 real pinned, non-sensitive tasks and >= 3 independent replicates per configuration, with separate hidden verifier.
- One entire 5-step historical sequence passes in a separate isolated worker, and a failure is detected deterministically when an earlier requirement is broken.
- Negative security integration tests (not just mocking) prove inability to access network/cloud/credentials, test snapshots and control-plane approval service.
- User approves any staging or production deployment. No auto merge.
