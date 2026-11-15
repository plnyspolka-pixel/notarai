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

## Preserved original user research files
Directory: frontier-lab/research-archives/. Seven long-form Markdown research files and two JSONL atlases (57 military/government records, 39 Big Tech AI records) were copied from previous research Library files. The two JSONL exports were parsed successfully during import. No new peer review, replication or automatic license clearance is implied.

## Preserved original engineering starter files
The security-lab files were ported from high_assurance_security_starter.zip after inspecting its contents. The original ZIP's 2 Python unit tests passed in this session; the branch's Signed Audit Research Lab CI also passed. The older 10 Claude skills were adapted from Claude_Agent_Factory_skills_2026-11-15.zip and placed in .claude/skills/. The demonstration video schema/fixture was reconstructed from the same archive. No deployment or production customer data is involved.
