# Benchmark30 — Claude vs rented GPU vs hybrid (immediate trial)

Status: **protocol committed; LLM execution not started**. Do not conflate harness preflight with model-evaluated results.

## Goal
Measure the **total cost in PLN per accepted, independently tested code change**, including retries, GPU rental, Claude tokens/subscription cost allocation, review time and failed attempts. Also report 5-step chain completion, regressions, latency and security policy failures.

## Frozen inputs
- Source branch: `research/coding-agents-100-foundation-20261116` (record resolved commit SHA at start).
- Tasks: `docs/agent-factory-research/benchmark30/tasks.json` — 30 synthetic coding tasks, 6 chains of 5.
- Grading: `docs/agent-factory-research/benchmark30/cases.json` — 61 known test cases, grader controlled outside model workspace.
- Do not copy verifier code or case fixtures into the agent workspace.
- For each arm, use identical task specifications, seed workspaces, time limits, test budget and allowed file changes. Keep steps 1–5 cumulative within each chain. Reset each chain **between** different arms.
- Record model identifier/version, model runtime, GPU make/VRAM, quantization, rental price and region, model-token spend, energy/additional fees where applicable, and results as observed; otherwise `unknown`.

## Arms
A. **Claude-only**: Claude Code writes solution; independently controlled verifier assesses.
B. **GPU-only**: selected locally hosted coding model on an approved rented GPU writes solution; same verifier.
C. **Hybrid**: same GPU model does first implementation; Claude receives only the diff, failures and targeted source evidence, and intervenes on bounded failures; same verifier.

## Immediate cost-free stage — preflight
```bash
python -m tools.agent_factory.benchmark30 validate
python -m tools.agent_factory.benchmark30 plan
python -m pytest -q tests/test_agent_benchmark30.py tests/test_research_foundation.py
```
Capture exit codes and commit SHA. Passing these proves only that test infrastructure works.

## Execution gates
Do **not** call paid GPU or Claude APIs until an operator has approved a spending ceiling and runner/credentials configuration. Never embed secrets in GitHub commits, prompts or logs. All model-written code and verifier execution must use ephemeral isolated nonproduction workers with network egress denied, no production credentials, no user/client data and limited CPU/RAM/time. Do not run `benchmark30_verifier.py` on a trusted host.

Existing repo handoff: `docs/agent-factory-research/CLAUDE_RUN_30_TASKS.md`.

## Result schema per task and arm
```json
{"arm":"A|B|C","task_id":"T01","chain":"catalog","step":1,"base_commit":"SHA","model":"id-and-version","candidate_diff_sha256":"hex","pass_first_attempt":null,"pass_final":null,"cumulative_regressions":null,"wall_time_s":null,"gpu_seconds":null,"gpu_cost_pln":null,"model_cost_pln":null,"review_cost_pln":null,"total_cost_pln":null,"verifier_attestation":"unknown","failure_reason":null}
```
Never substitute 0 for missing cost. Preserve failed cases. Do not let the authoring agent change acceptance criteria.

## Decision rule
First require **no lower security standard** and comparable acceptance/whole-chain reliability. Then compare cost per accepted change and p50/p95 latency. Do not label hybrid cheaper until real paired observations support it. Because 30 tasks contain only 6 correlated multi-step chains, report chain-level outcomes and uncertainty; do not overclaim statistical significance.

## Known blocker
The branch does not yet have a configured Claude Code runner, nor a verified authorized GPU worker. No real A/B/C model tests have been executed by this protocol. A GitHub comment or file push does not start Claude.
