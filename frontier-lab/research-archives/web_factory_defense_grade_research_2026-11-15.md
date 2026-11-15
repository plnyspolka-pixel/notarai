# WEB FACTORY — Defense-Grade Research / Public Open Source

**Research date:** 2026-11-15. **Scope:** agentic engineering of web interfaces and business web applications; publicly accessible research from DARPA, NATO, DoD, NASA, NIST, MITRE, academic labs, and commercial OSS communities. **Not a military certification** and not a claim that a web application is equivalent to avionics or command-and-control software.

## Executive synthesis

The useful transfer from military and aerospace engineering to a website-building agent is **assurance**, not visual militarization: (1) mission-scoped requirements; (2) explicit non-negotiable invariants; (3) model-checking at critical boundaries; (4) risk-tiered human authorization; (5) deterministic tool mediation and sandboxing; (6) continuous evidence generation; (7) resilience under degraded conditions; (8) cognitive ergonomics and calibrated trust. A model-generated test result is not independently sufficient evidence of safety.

### Five substantive discoveries

1. **DARPA AI Forge (June 2026):** explicitly identifies secure sandboxing for agentic AI, risk-tiered verification, intervention at runtime, and traceable agent behavior as high-priority research challenges. Public report: https://www.darpa.mil/sites/default/files/attachment/2026-06/ai-forge-report.pdf ; program: https://www.darpa.mil/research/programs/ai-forge . The report is a research roadmap, not a completed technology.
2. **DARPA LUCID:** translating formally proven software properties into comprehensible operator experiences; unusually relevant to both human–agent supervision and UI explanations. https://www.darpa.mil/research/programs/lucid . Research program, not a drop-in library.
3. **DARPA DICE:** decentralized, coordinated agent teams with constraints and resilience to failing/compromised members. https://www.darpa.mil/research/programs/decentralized-artificial-intelligence-through-controlled-emergence . Program intent, not verified implementation.
4. **Cedar for Agents (Apache-2.0):** actual source for deriving Cedar authorization schemas from MCP tool definitions, with JS/WASM/Python bindings and analysis MCP server. https://github.com/cedar-policy/cedar-for-agents . Directly actionable.
5. **NASA FRET (Apache-2.0):** restricted natural language -> formal requirements, consistency checks, export, traceability, and requirements-derived tests. https://github.com/NASA-SW-VnV/fret . Directly testable with a small sample of web-business workflows.

## A. Public military / high-assurance research programs

| Program | What it establishes or investigates | Operational transfer to Web Factory | Evidence |
|---|---|---|---|
| DARPA HACMS | Formal specifications, code generation, machine-checkable proofs, attack-resilient system components | Safety and access invariants ahead of code generation; evidence on each merge | https://www.darpa.mil/research/programs/high-assurance-cyber-military-systems ; https://www.darpa.mil/news/resources/case-studies/hacms |
| DARPA PROVERS | Proof engineering and maintenance integrated into a development pipeline | Change-aware proof/test maintenance | https://www.darpa.mil/research/programs/pipelined-reasoning-of-verifiers-enabling-robust-systems |
| DARPA CLARA | Integrating machine learning with compositional symbolic reasoning | LLM proposes; independent logical checker validates | https://www.darpa.mil/research/programs/clara |
| DARPA LUCID | Human-interpretable views derived from formal proof evidence | Explain actual access/approval conditions to operators, not plausible narratives | https://www.darpa.mil/research/programs/lucid |
| DARPA Assured Autonomy | Safety assurance maintained at design and operation time | Continuous checking of agent actions and policy before tool execution | https://www.darpa.mil/research/programs/assured-autonomy |
| DARPA AI Forge | AI interpretation, control, adversarial robustness; sandboxing and runtime intervention | Policy gate, risk-tiered approvals, incident trace; network isolation | https://www.darpa.mil/research/programs/ai-forge |
| DARPA DICE | Cooperative decentralized agents resilient to single-agent failure or compromise | Split independent frontend agent / critic / policy enforcer; graceful failover | https://www.darpa.mil/research/programs/decentralized-artificial-intelligence-through-controlled-emergence |
| NIST SP 800-160 vol. 2 rev. 1 | Anticipate, withstand, recover, adapt; cyber-resilience engineering | Defining safe degraded modes, recovery and rehearsal scenarios | https://csrc.nist.gov/pubs/sp/800/160/v2/r1/final |
| DoD DSOP | Secure software factory; hardening, DevSecOps, portable infrastructure | Attested builds and repeatable evidence gates; not merely GitHub CI success | https://software.af.mil/dsop/ |
| NATO 2024 revised AI strategy | Testing, evaluation, verification, validation, responsible use | Independent test plans and human accountability | https://www.nato.int/en/about-us/official-texts-and-resources/official-texts/2024/07/10/summary-of-natos-revised-artificial-intelligence-ai-strategy |

**Research maturity warning:** HACMS has documented technology demonstrations; newer programs CLARA, LUCID and DICE mostly specify research objectives. Do not equate program goals with production-ready open-source implementations.

## B. Actual open-source engineering tools

### B1. Formal requirements, model checking, access controls

| Repo | Role | Known license / caveat | Integration priority |
|---|---|---|---|
| https://github.com/cedar-policy/cedar | Server-side policy engine for RBAC/ABAC; deny overrides allow | Apache-2.0 | P0 |
| https://github.com/cedar-policy/cedar-spec | Lean formalization and randomized differential testing against Rust implementation | Apache-2.0 | P0 research |
| https://github.com/cedar-policy/cedar-for-agents | MCP tool authorization: schema generation, agent-oriented bindings, analysis server | Apache-2.0 | P0 |
| https://github.com/cedar-policy/cedar-examples | Concrete integration samples | Apache-2.0 | P0 |
| https://github.com/NASA-SW-VnV/fret | Specification, formalization and analysis of requirements | Apache-2.0 | P1 |
| https://github.com/tlaplus/tlaplus | Temporal logic model checking with TLC | MIT | P1 |
| https://github.com/apalache-mc/apalache | Symbolic model-checking for TLA+/Quint | Apache-2.0 | P1 |
| https://github.com/quint-co/quint | State-machine/specification authoring and execution | Confirm current release/license before incorporation | P1 |
| https://github.com/informalsystems/modelator | Model-derived implementation tests | Verify maintenance and license | P2 |
| https://github.com/galoisinc/saw-script | Software Analysis Workbench for C/Java/Rust/Cryptol | Strong specialist tool, not for everyday TS React code | P3 research |
| https://github.com/seL4/seL4 | Formally verified microkernel (for specific configurations) | GPLv2 kernel; **not a browser/frontend dependency** | Study only |

**Cedar caution:** formal verification of Cedar semantics does **not** prove that an application wired the engine into every route, file upload and websocket. Enforcement must be at the backend boundary, not merely hiding a button in the UI. A missing `authorize` invocation is still a security defect.

### B2. Attested software delivery

- https://github.com/sigstore/cosign — signing and verification for OCI artifacts (Apache-2.0).
- https://github.com/in-toto/in-toto — signed supply-chain step attestations; protect integrity of source-to-binary lifecycle.
- https://github.com/ossf/scorecard — OSS dependency security heuristics (Apache-2.0).
- https://github.com/argoproj/argo-rollouts — canary / blue-green, metric-based analysis and rollback (Apache-2.0).
- https://github.com/open-telemetry/opentelemetry-js — metrics and traces (Apache-2.0).
- https://github.com/chaos-mesh/chaos-mesh — fault/chaos experiments under Kubernetes (Apache-2.0).
- https://github.com/temporalio/temporal — durable workflows, compensation and retries (MIT).

**Practicality:** do not install Kubernetes, service mesh and a complex signing service on day one if the target is a small web preview. Establish signed builds, trace IDs and safe rollback first, then scale infrastructure only where justified.

### B3. Agent red-team and sandbox validation

- https://github.com/ethz-spylab/agentdojo — MIT, academic benchmark of prompt injection attacks and defenses against agents; suitable for testing webpage-sourced untrusted instructions.
- https://github.com/microsoft/pyrit — public toolkit for LLM security and safety evaluations, including adaptive multi-turn tests. Validate current licenses and target configuration.
- https://github.com/OWASP/AISVS — emerging application-security verification guidance for AI systems; confirm draft/status before using as compliance claim.
- https://github.com/cedar-policy/cedar-for-agents — explicit authorization for model-mediated tool use.

**Security boundary:** tool-calling permissions, filesystem rights, network egress, vault access, data visibility, and deployment privileges must be controlled externally to the LLM, regardless of how persuasive or malicious a prompt is.

### B4. Public-sector interface engineering and human factors

- https://github.com/uswds/uswds — U.S. Web Design System, public-domain / open-source accessibility patterns, federal design guidance; reuse accessibility methodology, not generic aesthetics.
- MIL-STD-1472 Human Engineering standard metadata: https://quicksearch.dla.mil/qaDocDetails.aspx?ident_number=36903 (active as of 2026-11-13; scope goes beyond web apps).
- DoD Human Systems Integration Guidebook: https://www.cto.mil/wp-content/uploads/2024/07/HSI-Guidebook-C1-2024.pdf .
- MITRE Human-Machine Teaming Systems Engineering Guide: https://www.mitre.org/news-insights/publication/human-machine-teaming-systems-engineering-guide . Covers observability, predictability, directing attention, directability, calibrated trust, common ground, adaptive automation.
- US Army Research Laboratory 2026 Soldier–AI Integration metrics: https://arl.devcom.army.mil/arlreport/arl-tr-10403/ . Documents research on measuring trust, workload and teamwork; does not prove any specific UI technique is superior.

## C. Architecture: Web Factory Assurance Layer

```text
Design request / acceptance criteria
                |
                v
       Style & Interaction Contracts
                |
         AI proposes UI/code  <----->  Visual State / Screenshot Validator
                |
                v
       Threat & Risk Classification
                |
                v
  Formal policy engine (Cedar + default deny)
                |
   +------------+-------------+
   |            |             |
 Low risk     Medium risk   High risk
 (read-only)  (staging)     (prod, data, auth)
   |            |             |
 Allow        Audit+tests   Manual approval + enforce via identity & infrastructure
   +------------+-------------+
                |
   Playwright / Axe / Property-based tests
                |
          Signed evidence bundle
                |
          Preview / PR only
                |
     Explicit release authorization
                |
       Canary / rollback / tracing
```

Never rely on a model's stated permission, auto-generated test result, or screenshot for high-risk actions. A signed attestation verifies provenance, **not** correctness of the claim inside the artifact.

## D. Initial hard invariants to formalize

These are **proposed application properties**, not statements about current deployments:

1. A UI may not reveal information unless the backend has independently authorized access to that exact object and operation.
2. Every resource query or file download must be re-evaluated server-side for tenant, role, identity and explicit disclosure state.
3. A privileged action requiring human approval cannot be performed using an agent's own self-issued approval.
4. An agent with only preview permission cannot invoke production deployment, access signing keys, or send private data to uncontrolled domains.
5. A failed identity check cannot reach a state of `APPROVED`, even through out-of-order events or retries.
6. Workflows that retry must not accidentally execute irreversible side effects twice; idempotency is checked at the server.
7. A temporary network outage must never cause an offline client to silently mark an uncommitted high-risk action as confirmed.
8. Human operators can inspect the last verified step, active permission scope, data sources and pending approvals; they can stop a running agent.

Model-check policy transitions (Quint/TLA+/Apalache) and enforce policy decisions in Cedar on production API boundaries. Use Playwright to test the concrete application against model traces; each layer validates a different assumption.

## E. Human-machine operator UX, grounded in HSI research

A high-assurance operator panel should provide:

- **Observed state**: last confirmed server state; data freshness and confidence when available.
- **Intent and plan**: what the agent intends to do, with explicit visible scope.
- **Boundary and authority**: what the agent *may* and *may not* do; provenance of approval.
- **Decision rationale**: verifiable rule decisions and input sources, not simply a generated explanation.
- **Degraded-mode indication**: explicit offline/partial-connectivity status and what remains possible.
- **Intervention**: stop execution, revoke tools, safely resume, escalate.
- **Post-action trace**: exact action/parameters/result and correlation IDs; redact secrets and sensitive content.

MITRE specifically recommends **calibrated** trust rather than making a system seem more trustworthy through aesthetic cues or high-confidence prose. Source: https://www.mitre.org/news-insights/publication/human-machine-teaming-systems-engineering-guide .

## F. Suggested experimental program

**Test environment:** isolated demo fixtures and fake client data. Never red-team or chaos-test active customer workflows.

### E1 — Authorization invariants

- Build a tiny Cedar schema for two tenants and a limited number of actions.
- Generate allowed and disallowed cases, including object swaps, role escalation and out-of-order state transitions.
- Measure unauthorized actions reaching the backend as the primary safety metric (acceptance target: zero in specified test suite; this is NOT proof of zero real-world vulnerabilities).

### E2 — Model checking of one real workflow

- Model states and transitions in Quint or TLA+.
- Specify invariants and fairness/liveness rules, e.g. no transition from `REJECTED` to `COMPLETED` without re-authorization.
- Produce counterexample traces and convert them to integration test scenarios.

### E3 — Agent red team

- Use AgentDojo or adapted equivalent with hostile text in website elements, repo README files, issue comments or tool descriptions.
- Quantify attack success, legitimate task completion and false positive blocks.
- Compare prompt-based defense to infrastructure mediation (Cedar + sandbox + egress deny).

### E4 — Fault injection

- At staging level, inject 500 errors, timeouts, stale cache, lost network, partial API responses and abandoned user sessions.
- Verify read-only degraded mode, idempotency, recovery and unambiguous user messaging.
- Start with browser/request stubs; add Chaos Mesh only if Kubernetes environment justifies it.

### E5 — Human factors

- Two variants: conventional agent panel vs evidence-first assurance panel.
- Measure unsafe approvals, time to identify a false agent claim, task completion rate, error recovery, workload (e.g., a validated workload instrument if available), and operator calibration.
- Avoid claiming evidence-first necessarily improves outcomes before conducting the experiment.

### E6 — Supply chain attestation

- Record source commit, toolchain, build digest, selected test outputs and reviewer approval in evidence bundle.
- Sign build artifacts with Cosign, attach in-toto provenance, verify prior to staged deployment.
- Conduct rollback drill and test whether a tampered or unsigned artifact is refused.

## G. Risk-prioritized integration roadmap

| Stage | Deliverable | Acceptance criteria |
|---|---|---|
| P0 | Separate risk classes and capabilities for MCP tools | No tool invocation without explicit authorization decision; baseline deny; staging sandbox |
| P0 | Application invariants and fixtures | Documented principal/action/resource/context matrix, test cases for unauthorized flows |
| P1 | Cedar integrated at actual server boundaries | Cross-tenant and role escalation tests fail closed; audit trace records policy outcomes |
| P1 | Model-check one critical workflow | Counterexample tests and mapping to integration tests |
| P1 | Incident- & fault-oriented browser QA | Stable synthetic fixtures, timeout/disconnect/retry tests, no false success indications |
| P2 | Attested build and human-controlled deploy | Valid signature / provenance verification, revert available, no auto-promotion for high-risk routes |
| P2 | Human factors evidence interface | Controlled usability study with measured operator performance |
| P3 | Multi-agent independent assurance | Agent proposal, verifier, policy enforcer separated by actual permissions and trust boundaries |

## H. Exclusions / cautions

- An avionics/military standard cannot be used to **certify** a general website by association.
- seL4's formally verified kernel properties apply to specific supported configurations; they do not prove a Node or browser app is secure.
- AI Forge/DICE/LUCID are research directions; production-readiness must not be invented.
- Military HCI evidence can motivate experiments but not replace studies with a legal/financial/notarial user population.
- Avoid automatic security tool installation from unreviewed repos and dependency drift; pin versions and audit licenses.
- When using source code and models, distinguish an openly accessible repository from approved commercial usage rights for datasets, weights and checkpoints.

## I. Sources (primary or official project documentation)

1. DARPA AI Forge, 2026: https://www.darpa.mil/news/2026/ai-forge-accelerating-ai-breakthroughs-national-security ; report: https://www.darpa.mil/sites/default/files/attachment/2026-06/ai-forge-report.pdf
2. DARPA HACMS: https://www.darpa.mil/research/programs/high-assurance-cyber-military-systems
3. DARPA HACMS case study: https://www.darpa.mil/news/resources/case-studies/hacms
4. DARPA CLARA: https://www.darpa.mil/research/programs/clara
5. DARPA LUCID: https://www.darpa.mil/research/programs/lucid
6. DARPA PROVERS: https://www.darpa.mil/research/programs/pipelined-reasoning-of-verifiers-enabling-robust-systems
7. DARPA Assured Autonomy: https://www.darpa.mil/research/programs/assured-autonomy
8. DARPA DICE: https://www.darpa.mil/research/programs/decentralized-artificial-intelligence-through-controlled-emergence
9. NIST SP 800-160 v2r1: https://csrc.nist.gov/pubs/sp/800/160/v2/r1/final
10. DoD DSOP: https://software.af.mil/dsop/
11. NATO AI Strategy 2024: https://www.nato.int/en/about-us/official-texts-and-resources/official-texts/2024/07/10/summary-of-natos-revised-artificial-intelligence-ai-strategy
12. US Army AI teaming metrics 2026: https://arl.devcom.army.mil/arlreport/arl-tr-10403/
13. MITRE HMT guide: https://www.mitre.org/news-insights/publication/human-machine-teaming-systems-engineering-guide
14. NASA FRET: https://github.com/NASA-SW-VnV/fret
15. NASA FRET publications: https://github.com/NASA-SW-VnV/fret/blob/master/PUBLICATIONS.md
16. Cedar: https://github.com/cedar-policy/cedar
17. Cedar formal spec and proofs: https://github.com/cedar-policy/cedar-spec
18. Cedar for Agents: https://github.com/cedar-policy/cedar-for-agents
19. TLA+: https://github.com/tlaplus/tlaplus
20. Apalache: https://github.com/apalache-mc/apalache
21. AgentDojo: https://github.com/ethz-spylab/agentdojo
22. PyRIT: https://github.com/microsoft/pyrit
23. USWDS: https://github.com/uswds/uswds
24. OpenSSF Scorecard: https://github.com/ossf/scorecard
25. Cosign: https://github.com/sigstore/cosign
26. in-toto: https://github.com/in-toto/in-toto
27. Chaos Mesh: https://github.com/chaos-mesh/chaos-mesh
28. Argo Rollouts: https://github.com/argoproj/argo-rollouts
29. OpenTelemetry JS: https://github.com/open-telemetry/opentelemetry-js
30. Temporal: https://github.com/temporalio/temporal
31. seL4: https://github.com/seL4/seL4
32. ARL HMT & calibration research: https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2021.652776/full
