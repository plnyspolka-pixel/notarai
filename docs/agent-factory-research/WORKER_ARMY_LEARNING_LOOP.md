# Low-cost worker army for Claude Opus / Codex — implementation

**Status:** Working MCP stdio tool bridge, bounded parallel dispatch and an evidence-gated training-data pipeline. **No rented GPU or paid Claude session started by these files.** Initial tasks limited to synthetic or pre-approved public code, no private customer/client documents.

## How the architecture works

A premium lead (Claude Code Opus or Codex) uses MCP tools exposed by `.mcp.json`:

- `worker_pool_status`: confirms whether a local CPU/GPU coding endpoint is configured.
- `validate_worker_batch`: checks up to six independent scoped tasks without a model call.
- `delegate_workers`: sends six limited packets, at most four simultaneously, to an operator-run vLLM / llama.cpp OpenAI-compatible **loopback** endpoint and returns **unverified** proposals.

Supported role specialization: implementer, test-designer, reviewer, bug-triage, documentation, research-assistant. A role is a bounded prompt profile, **not a separate autonomous process** and not automatically a separate fine-tuned model. The premium lead can create further batches based on earlier results; there are no production write operations or execution tools for workers.

**Resource model:** multiple model *requests* can share a single GPU-backed inference server; this is not six GPU instances. Scaling GPU replicas is a later, metered infrastructure decision.

## Connect to Claude Code

The project contains the MCP server declaration. Check that the workspace launch recognizes `agent-forge-workers` and approves the project configuration in the Claude Code UI. The host running this MCP process must be able to access an authorized local model server on loopback.

Example, on a **disposable developer or test host** after independently provisioning `vLLM` or `llama.cpp`:

```bash
export AGENT_FORGE_WORKER_ENDPOINT=http://127.0.0.1:8000/v1
export AGENT_FORGE_WORKER_MODEL=Qwen2.5-Coder-7B-Instruct
export AGENT_FORGE_ALLOW_LOCAL_WORKERS=I_APPROVE_SYNTHETIC_LOOPBACK_WORKERS
python -m tools.agent_factory.worker_mcp
```

The program uses JSON-RPC stdio. Invoke its exposed tools through Claude Code, not by typing unstructured commands into stdin. **Without the explicit opt-in it reports disabled and refuses delegations.** It does not provision remote GPUs. To connect a remote GPU, create a separately authenticated and audited local tunnel. Never put a provider token or private model endpoint URL inside Git.

Use only synthetic or explicitly reviewed public snippets in work packets. Never pass full source trees, credentials, hidden tests or customer data. High-risk path names are automatically blocked. Model output is **untrusted** and cannot authorize CI merging or deployments.

## Continuous improvement / training loop

1. Claude creates verifiable work packets and delegates low-risk work.
2. An independently managed verifier tests generated code on a disposable isolated worker. Claude then reviews any proposed change.
3. Only after independent verification AND human approval, a trusted evidence signer creates an HMAC-signed record with the exact accepted-code SHA-256, base commit and task family.
4. `python -m tools.agent_factory.learning_loop signed-evidence.jsonl /tmp/new-version` verifies every record and makes **train** and **holdout** splits grouped by task family.
5. The accepted export can be used to train LoRA/QLoRA adapters on an approved GPU. The dataset build itself **never** downloads or trains a model.
6. Any fine-tuned adapter must outperform a pinned baseline on a never-trained holdout set plus independent coding tasks before promotion.
7. The lead can then route suitable worker roles to the winning adapter; high-risk work stays with Claude/Codex.

The independent signing key is supplied only to a trusted grading process using `AGENT_FORGE_INDEPENDENT_EVIDENCE_KEY` and NEVER to the inference worker or any prompt. Evidence filenames, raw prompts and solutions are not logged by the MCP server.

A dataset export requires at least 20 independently accepted examples from at least five distinct task families, explicit reviewer approval and a valid signature on every sample. The current 30 synthetic tasks do **not** automatically become legitimate training records. No claim of learning improvement can be made before a real, unseen evaluation.

## Deployment boundary and next technical steps

- Extend work packets to include **diffs in isolated worktrees**, not merely text proposals, while retaining strict scope and independent tests.
- Implement reliable retries, cancellation, queueing and leased workers with cost telemetry; reuse existing `forge_scheduler.py` primitives where possible.
- Run a vLLM worker gateway on the chosen GPU, accessible only via local authenticated tunnel to Claude Code MCP.
- Add a tested LoRA training command after a sufficiently large, independently verified corpus exists.
- Compare premium-only vs naive delegation vs orchestrated army on the same realistic nonproduction tasks, measuring premium tokens, accepted changes, regressions and total cost.

**No auto-merges, no hidden-test disclosure, no automatic fine-tuning on model self-reports, no production secrets, no direct customer data sent to workers.**


## QLoRA training only after evidence review

On a separately approved ephemeral CUDA GPU (not on CI), install compatible `torch`, `transformers`, `peft`, `bitsandbytes`, and `accelerate`. The operator then sets `AGENT_FORGE_TRAINING_APPROVED=I_APPROVE_SYNTHETIC_LORA_GPU` and runs:

```bash
python -m tools.agent_factory.train_qlora \
  --dataset /mnt/verified-synthetic-export \
  --output /mnt/new-unreleased-adapter \
  --revision MODEL_IMMUTABLE_40_HEX_COMMIT \
  --max-steps 120
```

This is a **training command available for later authorized use**, not evidence that fine-tuning has already been performed. It verifies checksums, split separation and approval before importing GPU libraries and downloading weights. Assistant-only loss concentrates learning on accepted worker answers. No trained adapter is automatically promoted or deployed.


## Experiment-driven lessons: CPU first

The source for diagnosing missing skills is `tools/agent_factory/worker_learning_lab.py`. A GitHub Actions workflow runs the SAME Qwen2.5-Coder 7B model on six disjoint synthetic coding families under two distinct instruction styles:

1. `plain_delegation`: job description and function stub only.
2. `contract_scaffold`: identical task, plus explicit public input/output contract and instruction constraints; hidden grading cases are NEVER included.

Both use `benchmark30_docker.grade` in a no-network isolated container. The output artifact contains `learning-report.json` with paired acceptance and per-family diagnoses and `NEXT_LESSONS.md` with suggested exercises. Only synthetic code that passes the independent local grader is written to `pending_review/`, with an index explicitly flagging **not human approved, not independently signed, not training eligible**. All failures remain in the diagnostic report.

This establishes a **repeatable method for learning how to delegate** and automatically constructing a future **human-reviewed** LoRA candidate queue. It is not self-modifying model weights, a Claude Opus run, or an end-to-end coding agent benchmark.

For a role-specific specialization, first gather adequately diverse independent examples of that role, review for correctness and safety, sign through the separate grading/review authority, export with `learning_loop.py`, and only then consider GPU QLoRA. Do not use the fixed benchmark's evaluation cases as training labels or claim progress based on a single six-task study.

Research priority: improve orchestration and feedback before expanding model sizes; new lessons should be supported by paired independently graded evidence, not merely by increasing model output length.
