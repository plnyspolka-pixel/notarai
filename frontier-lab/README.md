# FRONTIER ENGINEERING LAB — unified five-track workspace

**Purpose.** A single, reproducible foundation combining the five research threads from 15 Nov 2026. This is an integration branch in the existing NotarAI repository, not a new stand-alone GitHub repository. The production application and its permissions are unchanged.

## What is actually included
| Track | Functional source | Research |
|---|---|---|
| Agent Forge / LLM agents | ../tools/agent_factory/ (model adapter, scheduler, worktrees, isolated test utilities) | ../docs/agent-factory-research/ (55 candidate OSS repos, academic evidence, experiments) |
| Web Factory | ../tools/web-factory/ (Playwright audit, axe, design tokens, MCP read/audit interface, tests, CI) | docs/web-factory-research.md |
| Security / crypto / blockchain | tools/hashchain.py (synthetic, non-signed proof of integrity only) | catalog/security.json, docs/security-architecture.md |
| Sales Intelligence / customer analytics | tools/uplift_demo.py (reproducible synthetic experiment) | catalog/sales.json, docs/sales-intelligence.md |
| Frontier Research / defense / big tech | tools/catalog.py (validated offline searchable index of resources) | catalog/research.json, docs/frontier-research.md |

## Quick start (Python 3.11+; no external packages)
    python3 frontier-lab/tools/catalog.py check
    python3 frontier-lab/tools/catalog.py list --track security
    python3 frontier-lab/tools/uplift_demo.py
    python3 frontier-lab/tools/hashchain.py demo
    python3 -m unittest discover -s frontier-lab/tests -v

Web Factory has separate Node >=20 dependencies. From repository root:
    cd tools/web-factory
    npm install
    npm test

Agent Forge tests are at root; refer to docs/agent-factory-research/README.md for prerequisites.

## Design principles
1. Evidence tags separate a **proposed research goal** from author-reported results, vendor claims and locally tested functionality.
2. No data from clients, notarial matters, investors, identifiers, documents or production environments in experiments.
3. No cross-tenant data access. NotarAI, Finance You and Fundacja stay logically and operationally isolated.
4. Policy enforcement is outside the LLM: short-lived least-privilege credentials, deny-by-default network egress, approvals for sensitive actions.
5. Only reviewed changes can reach staging; production writes, deployments, billing and real fund transfers are outside this lab.
6. The GitHub links are references to third-party projects. Licenses of code, weights, datasets, fonts and assets must be checked independently.

## Practical usage
- Discover candidates: catalog.py list --track sales / security / research.
- Pick a hypothesis and register a deterministic experiment with fixed evaluation and budget.
- Evaluate with synthetic/approved staging inputs, keep artifacts private and collect CI evidence.
- Apply changes separately in NotarAI or Finance You only after licensing, threat modeling, privacy assessment, review and approval.

## Source of consolidation
- Agent research branch: feature/secure-agent-factory-20261115 (PR #34).
- Web research branch: feature/web-factory-premium-20261115 (PR #35).
- Three additional areas sourced from the user's Nov 15 security, sales and big-tech/defense research discussions.
- Existing code from both branches was copied without rewriting their implementations.
- No claim that every third-party repository has been locally built or independently reproduced.

## Maps
- docs/architecture.md — boundaries/interfaces
- docs/security-architecture.md — trust, attestation, signing, GDPR
- docs/sales-intelligence.md — event schema, causal experiments, exposure minimization
- docs/frontier-research.md — research atlas, evidence level
- docs/web-factory-research.md — design experiments and evaluation
- docs/roadmap.md — prioritized P0/P1/P2 tasks
- docs/provenance.md — evidence, licenses, reproducibility

## Preserved source material and usable research artifacts
- Original long-form documents and machine-readable military/Big Tech atlases (57 + 39 records) are under research-archives/. These preserve research context that a short synthesis cannot.
- The user's original security starter has been imported as security-lab/ including OpenFGA model, OPA gateway policies, SHA-384 log with Ed25519 checkpoints, tests and a separate CI workflow. This is an educational prototype, not a fully hardened append-only service.
- Ten topic-specific Claude skills from the original agent-factory skills bundle have been integrated at repository root .claude/skills/. They cover code, browser, security, agents, GPU, video, voice, fine-tuning, evaluation and skill ingestion.
- A video job JSON Schema and synthetic storyboard fixture live under contracts/ and examples/. Nothing in the fixture licenses a real voice or footage.

To validate signed audit demo (Python 3.11+, cryptography 46.0.4):
    cd frontier-lab/security-lab
    python3 -m pip install -r requirements.txt
    python3 -m unittest discover -s tests -v

**Evidence count caution:** 55 Agent Forge catalog entries, 90 new cross-domain candidates, 57 military JSONL records and 39 Big Tech JSONL records are separately inventoried and may overlap. Do not sum these into a count of unique validated tools.
