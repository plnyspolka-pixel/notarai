# Defense labs, big-tech and academic research atlas

Research labels: **program_goal** (a target), **author_reported** (reported result, not reproduced), **software** (source code exists), **review_required** (link/license/status still to confirm). No military/government qualification is implied.

## Military / government-facing studies
**DARPA DICE — Decentralized Artificial Intelligence through Controlled Emergence**. Official program: https://www.darpa.mil/research/programs/decentralized-artificial-intelligence-through-controlled-emergence. Goals include decentralized peer coordination, long-horizon operation, predictable emergent behavior, local inference control and resilience to compromised members. The DARPA page specifies simulation rather than real-world deployment. Do not claim target scale as measured performance.

**DEVCOM Army Research Laboratory A2I2**. ARL-TR-10274 (published 2026-01-20), https://arl.devcom.army.mil/arlreport/arl-tr-10274/. Survey of foundational AI, autonomy, adversarial robustness, multimodal perception, decision support and LLM planning over 2018–2025. Reported research output is not a certification of any SaaS component.

**DARPA AMCOM-DI, CyPhER Forge, NATO CyCon studies** were raised in the prior research conversations. Preserve as discovery candidates; exact program references and quantitative claims require independent retrieval/verification before being treated as sourced facts.

## Big-tech transfer candidates
- Microsoft Research: DoWhy/EconML causal models, policy/verification experiments, AI agent evaluation; see https://www.microsoft.com/en-us/research/group/causal-inference/tools/
- Google: Meridian causal media modeling, TLA+-style specification, Trillian transparency, RecSim NG simulation, privacy/secure aggregation.
- Meta: GeoLift, ReAgent, research on privacy-preserving processing and evaluation.
- Amazon/AWS: Nitro Enclaves attestation and KMS separation; check the published proof assumptions versus your threat model.
- IBM: signed audit, delegated agent scopes, Crypto Bill of Materials (CBOM), crypto agility as research topics; exact repo/claim must be verified.
- Apple: Private Cloud Compute and UI-agent research are reference architectures. Licenses for research-only artifacts and models may forbid commercial reuse.
- NVIDIA: confidential compute, measured GPU workloads and realistic price/performance evaluation.
- DARPA/NASA: formal reasoning, safety specifications, fault injection and auditable autonomy rather than product branding.

## Translating research into testable products
R-01: distributed agents under partial outage, lost network, byzantine/malicious worker. Report accepted-task success, number of policy violations, recovery time and message overhead. Test only in synthetic simulations.
R-02: ability of a local verifier to reject forbidden output despite apparently good task completion; use separate immutable evaluators.
R-03: serve exactly same tasks across inference engines with recorded precision/KV cache, concurrency, GPU, region and pricing. Compare accepted tasks per real billed GPU-hour.
R-04: adaptive policy from causal evidence under real randomized data *only after* legal review; compare against locked random baseline.
R-05: confidentiality stress tests on multi-agent browser execution: tainted source text must never become executable authority.

## Boundaries
Specific quantitative results from model or vendor papers are hypotheses until their evaluation conditions are carried into a test card. Defense programs have objectives that can remain unmet. Use publicly available research for safe software architecture and resilience testing only. This workspace contains no operational weapons design, targeting, tactical automation or deployment instructions.