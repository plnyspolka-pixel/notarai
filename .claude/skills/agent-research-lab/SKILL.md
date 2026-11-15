---
name: agent-research-lab
description: Badanie, porównywanie i bezpieczna ewaluacja eksperymentalnych agentów, narzędzi do RL, danych syntetycznych, generatorów wideo oraz infrastruktury wynajętych GPU. Use when asked to investigate, benchmark or prototype Agent Factory tools.
---

# Agent Research Lab — SOP

Read in order:
1. Repository root CLAUDE.md — nadrzędne polityki i RODO.
2. docs/agent-factory.md and docs/claude-code-handoff-agent-factory.md.
3. docs/agent-factory-research/README.md.
4. docs/agent-factory-research/catalog.json and experiments.md.

For each candidate: verify exact GitHub repo and pinned commit; inspect license of code/models/data; dependency and security review; classify claim (author-claimed vs independently verified); estimate minimal GPU/VRAM/cost; define an offline benchmark with independent success criteria.

Do not run fetched code in host environment. Never install all candidates automatically. Workers must use isolated, no-credentials environments and synthetic data, and must not access production web sessions, client documents or account data.

Never bypass spend caps or geographic constraints to achieve a benchmark. Default budget is zero and external cloud usage requires operator approval. All results need reproducible manifests, seeds, hashes, cost evidence, error cases, and explicit limitations.

Prefer Experiment EXP-01 before EXP-02; do not initiate GPU research when safe CPU baseline has not passed. Finish with a reviewable PR; no auto merge or deployment.
