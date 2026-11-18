# BIG TECH RESEARCH — frontier agent systems, 2026-11-15

**Scope:** public primary sources and openly visible research artifacts as of Nov 15, 2026. This is a targeted critical literature review, not a complete systematic review. All percentages are author-reported. This file is not an installation plan or a deployment authorization. No research code was executed.

## Central thesis

The frontier is no longer maximizing the number of autonomous agents. The strongest Big Tech patterns combine:
1. **Trusted formal checker**: agent produces hypotheses/proofs; Lean or another verifier checks only exact approved properties (Google AlphaProof Code).
2. **Evidence provenance**: every published scientific claim ties back to a paper, artifact hash, experimental log and independent rerun (Google Scientist One).
3. **External temporal authorization**: requests are checked against historical conditions at the tool boundary, not controlled by the model's prompt (AWS Dogwood).
4. **Observable execution**: model traces, activations and actions can be measured and investigated independently (OpenAI activation probes, Anthropic Petri/AuditBench).
5. **Stateful learning environments**: agents improve on executable environment transitions and validated outcomes (NVIDIA NeMo Gym, Snowflake AWM, Meta CWM).
6. **Continuation-based concurrency**: suspended agents consume persisted history, not necessarily a dedicated process (AWS/UC Berkeley Infinity).

## 1. Formal proof vs. tests: AlphaProof Code

Source: https://google-deepmind.github.io/code-verification/
Released artifacts: https://github.com/google-deepmind/code-verification

A team of AI provers generated approximately 6.5M lines of Lean proofs verifying specific security properties of compiled Signal AArch64 code. About 26,000 lines of trusted specs and processor semantics need expert review. The release includes **proof artifacts**, not evidence that the proprietary AI prover agent has been open sourced.

Relevance: test the control plane's invariants (single-use approval, no cross-tenant access, revoked grant always denies, no state transition from failed to completed, no action after cancellation). Begin with an explicit mathematical model and separate checker; do not claim end-to-end application security from a narrow proof.

## 2. Scientific evidence provenance: Google Scientist One

Source: https://research.google/pubs/scientist-one-verifiable-autonomous-research-via-chain-of-evidence/
Blog: https://research.google/blog/science-one-framework-a-verifiable-autonomous-research-framework-via-chain-of-evidence/

The research abstract reports **60 papers**, zero phantom citations among **830** references, but only **7/15 method-code alignment** in the reported set; the accompanying Google blog describes **75 papers** for a different experimental cohort. This discrepancy is precisely why we should retain exact paper/version/sample identifiers and not blindly copy marketing numbers. 0 hallucinated references does NOT mean all scientific claims are correct.

Proposed Agent Forge audit: claim_id -> evidence URL/document checksum -> exact git SHA -> dataset hash -> evaluator hash -> actual rerun -> independently signed verdict. Claims without a complete evidence chain remain UNVERIFIED.

## 3. Boundary-time governance, not model self-restraint

Dogwood: https://github.com/dogwood-policy/dogwood
Incremental engine: https://github.com/dogwood-policy/dogwood-local-engine
Sandbox: https://github.com/strands-agents/box

Dogwood adds temporal conditions to Cedar-style policies: action may depend on prior approval, testing results and time windows. The reference interpreter is **not production ready**. The incremental local engine is more suitable as a component but requires clock protection, trusted event generation, external audit logs and independent security testing. Box mediates OS operations with explicit policy. Treat anything not mediated as outside the claimed coverage.

High-assurance example invariant: a publish action requires (a) trusted human approval for that specific diff SHA, (b) successful tests on exactly that diff SHA within the allowed window, (c) no subsequent failing tests, (d) active nonrevoked principal, (e) healthy system mode. Neither LLM text nor retrieved content can become a grant.

## 4. Open-source RL environments, evidence preservation and compute

- NVIDIA NeMo Gym v0.7.0: https://github.com/NVIDIA-NeMo/Gym — environment servers, verifiers, token-preserving trajectories, no-inference reverify and scalable run scheduling.
- Microsoft Agent Lightning v1.0: https://github.com/microsoft/agent-lightning — harnessed RL; developer reports Qwen3.5-9B SWE-bench Verified 41.8 -> 56.4 with 6K training examples.
- Meta Code World Model: https://github.com/facebookresearch/cwm — 32B model, observation/action traces from Python and Docker; model learns transition dynamics of code.
- Snowflake/UNC Agent World Model: https://github.com/Snowflake-Labs/agent-world-model — 1000 executable, SQL-backed synthetic tool environments. Study is listed on Microsoft Research but is not Microsoft-owned.
- Amazon ExTS: https://github.com/amazon-science/ExTS — quality-adaptive tree-search, mean relative +5.5% in the researchers' budgeted settings.
- AWS/UC Berkeley Infinity: https://github.com/hydro-project/infinity — research runtime using suspension points; authors report 75k idle agents in 8GB RAM on Raspberry Pi 5. Do not confuse concurrency with throughput or guaranteed event authenticity.

## 5. Security audits that can fail even when models appear aligned

- OpenAI activation probes: https://alignment.openai.com/training-activation-classifiers — real-time internal-activation classifiers, not an off-the-shelf OSS model. Training uses millions of examples and multiple seeds.
- OpenAI monitorability benchmark: https://github.com/openai/monitorability-evals — open source subset of datasets/scoring. Some private safety sets intentionally excluded.
- OpenAI auto-review: https://alignment.openai.com/auto-review — separate reviewer for permission boundary, but a model reviewer is not a deterministic policy gate.
- OpenAI eval-vs-production gap: https://alignment.openai.com/eval-production-behavior-gap/ — evaluation objective framing changes model safety behavior; do not trust a single static benchmark.
- Anthropic AuditBench: https://alignment.anthropic.com/2026/auditbench/ — 56 target models with trained hidden behaviors across 14 classes, 13 auditor tool configurations; white-box tools are not consistently more effective than structured black-box probes.
- Anthropic RL auditors: https://alignment.anthropic.com/2026/training-alignment-auditors/ — naive single-number reward led to fabricated findings; pairwise reward and benign controls improved calibration.
- Petri reference: https://github.com/meridianlabs-ai/inspect_petri — maintained outside Anthropic; tests automated hypotheses on a target model.

## 6. Multimodal world representations

Meta V-JEPA 2.1: https://github.com/facebookresearch/vjepa2 — dense self-supervised video representation and future-state prediction, useful as a motion/continuity evaluator rather than as a direct video generator. Beware checkpoint/config availability and license separation.
Google Genie 4: https://deepmind.google/blog/genie-4-a-new-generation-of-world-simulation/ — interactive audio/visual model announcement, not an OSS installable component as of this review.

## 7. Production reality / empirical counterevidence

IBM/UC Berkeley ICML 2026 surveyed 306 practitioners; 68% of reported production agents execute <=10 steps before intervention and reliability is the leading challenge. IBM ICLR 2026 ST-WebAgentBench reported 375 tasks and 3,057 policies; policy-compliant completion was under two-thirds of nominal task success for the three tested agents. IBM OOPSLA 2026 Graphectory studied 4,000 coding-agent trajectories; reported improvements came from an **identified problematic subset**, not from all tasks. These results argue for short, auditable task segments and process-centric interventions rather than unbounded agent swarms.

Sources:
- https://research.ibm.com/publications/characterizing-agents-in-production
- https://research.ibm.com/publications/st-webagentbench-a-benchmark-for-evaluating-safety-and-trustworthiness-in-web-agents--1
- https://doi.org/10.1145/3798271
- https://research.ibm.com/publications/tangent-an-empirical-study-of-testing-practices-for-llm-based-agent-applications

## Research design, falsifiable hypotheses

**H1: Temporal control.** Compared with static role-based allowlists, a temporal engine reduces unauthorized actions after revocation, test failure, approval timeout or network partition. Test identical synthetic tool traces, inject stale approvals and clock skew, measure false allow/deny; deny all irreversible side effects.

**H2: Process monitor.** A structural trajectory monitor flags futile search/patch loops earlier than flat terminal pass/fail. Match task and model, use blinded per-task evaluation and measure accepted patches, latency and false alarms.

**H3: Auditing behavior.** Pairwise-trained auditor + explicit benign targets reduces fabricated safety alerts compared with scalar reward. Test on holdout targets across distinct underlying models and prompt families. A result requires external adjudication.

**H4: World model transfer.** Environment-aware 32B CWM or smaller AWM-trained agent solves more unseen synthetic code/CRM tasks than a same-cost instruction-only baseline. Prevent test leakage by holding out complete families of environments, not merely individual tasks.

**H5: Proof-carrying actions.** Critical state transitions require a formal or independently machine-checkable condition. Measure false acceptance against mutations, invalidated proofs, unsigned/unreviewed spec changes, and invalidated machine-code assumptions.

**H6: Scalability without hidden cost.** Compare current SQLite scheduler to Infinity for 10 / 100 / 1,000 *idle* fake agents, plus separate tests at fixed actual token throughput. Measure RAM, recovery time, error ordering and cost. Never infer GPU throughput from idle concurrency.

Evidence priority: independently reproduced artifacts > fully documented model/report > author benchmark > blog claim. Keep paper revisions and results separate. For all studies, exact license of source code, checkpoints and data must be verified before commercial integration.

## Agent Forge implementation status

Research records only: no Big Tech code cloned, installed, trained or run. Existing Agent Forge deterministic control plane, fake loopback model, queue, sandbox scaffold and paired statistical evaluator are separate from this research. No cloud/GPU spending or production deployment. Next engineering gate would require separate approvals for funded runs and an architecture review.
