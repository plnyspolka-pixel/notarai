# Qwen 14B versus 32B — GPU experiment

**Current state:** Real GPU benchmark client, 2×2 model/method comparison, GitHub Actions preflight and manual paid-run workflow have been committed. **No SaladCloud GPU has been provisioned, and no real 14B/32B inference has been run yet.** The user's SaladCloud account and inference endpoints are not connected to these tools.

## Why and how

Compare the SAME public synthetic tasks against **Qwen2.5-Coder-14B-Instruct** and **Qwen2.5-Coder-32B-Instruct**. Each receives two task-handoff styles: basic and structured. Verify every returned solution using independently calculated test vectors inside network-disabled disposable Docker on GitHub Actions. This compares delegation and model capacity without giving the worker hidden tests or production files.

Suggested quantization: Q4_K_M for both; 14B weights ~8.99 GB, 32B weights ~19.9 GB. Practical class choices: RTX 3090 24 GB for 14B and RTX 5090 32 GB for 32B, allowing VRAM for runtime and context. For a **pure model-size quality comparison**, serve both sequentially on the SAME RTX 5090, then run 14B on RTX 3090 separately to compare actual cost per accepted change. Different GPUs confound inference latency, not correctness if both are served with same precision and context.

## GPU hosting details

SaladCloud Container Engine can run GPU-backed container groups and expose a TLS-protected Container Gateway endpoint. This repository deliberately does not start or stop billable SaladCloud resources; the operator must create them and disable them after a trial. Use a tested llama.cpp CUDA inference server or other OpenAI-compatible service exposing /v1/chat/completions. On a 5090 verify CUDA 12.8+ support and use an appropriately built image.

Never expose the raw model server unauthenticated. Protect the gateway and confirm the exact authentication header expected by the deployment. **Salad-Api-Key for the management API is not automatically an inference bearer token.** Do not put either credential in a commit or in a ChatGPT message.

## Github Actions setup

Under NotarAI Settings > Secrets and variables > Actions configure:

Secrets:
- AGENT_GPU_14B_ENDPOINT: approved HTTPS inference gateway URL ending /v1
- AGENT_GPU_14B_TOKEN: credential for this inference gateway (not Salad account control API)
- AGENT_GPU_32B_ENDPOINT
- AGENT_GPU_32B_TOKEN

Variables:
- AGENT_GPU_ALLOWED_HOSTS: exact two DNS hostnames, separated with comma (without https:// or path)
- AGENT_GPU_14B_MODEL: model alias exposed by the 14B server
- AGENT_GPU_32B_MODEL: model alias exposed by the 32B server
- AGENT_GPU_14B_AUTH_HEADER: Authorization or Salad-Api-Key
- AGENT_GPU_32B_AUTH_HEADER: Authorization or Salad-Api-Key

CI: .github/workflows/worker-gpu-pair-preflight.yml runs offline on source changes, with **zero GPU use**. Manual real experiment: .github/workflows/worker-gpu-pair-real.yml. Trigger workflow_dispatch with confirm exactly I_APPROVE_TWO_SYNTHETIC_GPU_MODEL_TRIALS and per_family=1 to limit the first trial to 10 distinct tasks × two models × two prompt methods = **40 real model calls** and **320 verifier cases**, across ten algorithm families. The same workflow may scale to per_family=4 (160 calls).

**Billing caution:** The workflow does not buy/provision, pause, or terminate SaladCloud container groups. The GitHub timeout is not a spending limit. You pay Salad for *running instance seconds*, including idle model server time, not merely individual inference requests. Stop/scale to zero on the provider immediately after the experiment. Without the endpoints and explicit confirmation, paid testing is blocked.

Published prices on November 16, 2026 for Lowest tier: RTX 3090 $0.090 per running GPU-hour; RTX 5090 $0.250 per running GPU-hour. Live availability, interruptions, taxes, fees and actual billed uptime may vary. Source: https://salad.com/pricing/

## Evidence and limitations

Outputs: acceptance by eight independent synthetic oracle cases per work packet, request latency, completion and prompt tokens, failure categories, model aliases, source digests, and explicitly unknown actual provider billing. Require at least a few dozen tasks before any recommendation. These are TEN correlated algorithm families, not 200 unrelated problems. Keep heldout contracts untested until development strategy is frozen.

**No Claude Opus invocation**, no QLoRA training, no private source code, no claim of savings. The subsequent experiment will route failed cheap workers selectively to Opus and measure completed, independently accepted PRs, premium tokens, worker compute, and human review time.

Resources: tools/agent_factory/gpu_pair_benchmark.py, tests/test_gpu_pair_benchmark.py, and the two GitHub workflows. PR #45 remains draft.
