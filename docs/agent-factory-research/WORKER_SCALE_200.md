# Worker Army: large-sample orchestration research

Status (2026-11-16): **200 synthetic parameterized contracts, 1600 oracle cases, 10 algorithm families** generated and validated; initial **40-contract / 80-real-model-call** paired CPU pilot started on GitHub Actions. Not a trained model, not a Claude/Codex-led run, not rented GPU access.

## Why this is a meaningfully larger sample

Instead of reusing the old 30 public tasks, we add ten families:
numeric reduction, text normalization, record deduplication, authorization, scheduling, dependency graphs, event replay, redaction, slugs and interval merging.

Each family has 20 distinct public instruction/configuration contracts and eight deterministic independent oracle cases for each. The model never sees the grader cases. Hence **200 distinct parameterized contracts** and **1600 checks**; NOT 200 independent algorithm types. Effective algorithm-family diversity is ten, and reporting must cluster uncertainty at family level.

## Two controlled orchestration arms

- **Plain:** senior gives a request and a simple entrypoint.
- **Structured:** same model, same request, same graders and same budget, plus an explicit interface/checklist/preservation contract.

Assignment order alternates between contracts to reduce model warm-up and order effects. Independent Python execution is permitted only in an opt-in Docker verifier on disposable CI VMs, never on the trusted lead host.

## Separation of development from evaluation

- Contracts 0–9 of each family: 100 **development** contracts for trying work-packet strategies.
- Contracts 10–19 of each family: 100 **heldout** contracts, unused while strategies are tuned.
- A *different task ID* still does **not** mean independent distribution shift: the same ten algorithm families and parameter combinators generated both halves.
- Never train model weights using these tasks, their tests, generated answers or observed evaluation outcomes.
- Future genuine training examples must come from *new* synthetic tasks with independent verification, human review and independent signed approval, via the already implemented LoRA evidence gates.

## Execution stages

1. Offline validation: 200 task specs, 1600 expected outputs, independent grader sandbox policy and result-grid tests.
2. CPU pilot: 40 development contracts across 10 families × two ways of delegating = **80 real Qwen7B calls**, split into five independent shards for manageable runtime.
3. Only when step 2 yields complete, credible artifacts: scale to **100 development contracts × two arms = 200 model calls**. Do not inflate pass rates by silently discarding failures.
4. Lock the most promising delegation policy and run **100 never-used heldout contracts × two arms = 200 calls**. These results inform whether the method generalizes even across new parameter settings.
5. Add genuinely new family types and multi-file integration tasks, role-based reviewer/test-writer/triage tasks and real anonymized nonproduction engineering work. The latter requires risk/legal approval before passing any source to worker models.
6. **Eventually** use an authenticated Claude Opus / Codex lead runner and measure the number of successfully integrated, verified PRs, total premium-model tokens, human time, GPU/CPU cost and escaped regressions. The present research does not establish those numbers.

## Data integrity and telemetry

- `tools/agent_factory/worker_scale_corpus.py`: deterministic task and oracle generator.
- `worker_scale_runner.py`: paired actual model calls, source-hash/case counts/usage/timing.
- `worker_scale_sandbox.py` and `worker_scale_grader.py`: restricted grading inside ephemeral Docker.
- `worker_scale_analysis.py`: strict five-shard assembly, paired per-contract win/loss, and family-cluster bootstrap rather than treating 1600 correlated checks as independent trials.
- Artifacts show unknown prices as unknown; model rental cost is NOT measured in this CPU run.
- Generated results and failures are **diagnostics**, not authenticated evidence suitable for automatically promoting weights or merging production code.

## Limits and next learning question

We optimize **the method of controlling cheaper workers**, not replacing Opus. The new corpus still tests isolated small Python implementations, so by itself it cannot show the success of an Opus-led multi-agent software factory. After scaling this baseline, add safe parallel worker dispatch, bounded correction, graded handoff, and selective Opus escalation to the *same* new heldout tasks, one experimental change at a time.

PR: [Agent Factory Worker Army #45](https://github.com/plnyspolka-pixel/notarai/pull/45).
