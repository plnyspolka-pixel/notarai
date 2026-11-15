# Provenance and license handling
Created: 2026-11-15. Sources consolidated from five user discussions and two prior GitHub feature branches. This is curated engineering research, NOT a formal systematic review.

## Attribution levels
- locally_tested: tests actually executed in the environment and with specified commit/versions.
- upstream_software: source identified, not audited or built locally.
- author_reported: result from a paper; not reproduced.
- program_goal: agency/program target, not a completed result.
- verify: candidate requiring primary-source verification.

Every new study should record title, version/date, DOI or durable URL, category, sample size, task specification, model/checkpoint, evaluator hash, run seeds, hardware, region, inference engine, confidence intervals, cost, license and negative limitations.

## Licensing
Do not treat open GitHub access as an OSI license. Code license, model weights, datasets, browser sessions, creative assets and geographic transfer rights must be independently checked at an exact release tag. AGPL/SSPL/BSL/noncommercial/research-only licenses need legal review in a hosted product. Catalog entries use license_review=required until confirmed and approved for the specific use.

## Source pointers
- Agent Forge's verified repo inventory: ../docs/agent-factory-research/catalog.json
- Agent Forge's academic records: ../docs/agent-factory-research/academic-evidence.json
- Web Factory OSS registry: ../tools/web-factory/design-system/oss-registry.json
- Security and sales inventories: ../frontier-lab/catalog/
- Primary official DICE and ARL sources: docs/frontier-research.md

## Claim hygiene
Document **what was implemented** separately from what was researched, intended, or claimed by external authors. Do not cite benchmarks as ours. Never promote synthetic demos to observed revenue, conversion, security or model capability results.