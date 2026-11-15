# Web Factory — premium frontend R&D
The exact implementation copied from the existing Web Factory feature branch is under ../tools/web-factory/. It includes Playwright, axe-core, pixelmatch, DTCG design tokens, preview and read/audit MCP interface. No production routes/auth flows are changed.

## Research hypotheses
W-01 Persistent style contract: enforce design tokens, typography scales and component semantics throughout an agent's multi-file edits. Compare visual/a11y regression against unconstrained code generation.
W-02 Shared visual state: agents reference consistent page snapshots, DOM state, annotation and component provenance instead of re-describing a screenshot each step.
W-03 Executable flow contracts: express user journeys and invariants as deterministic browser tests, not prose-only prompts.
W-04 Component selection: evaluate OSS candidates such as Puck, OpenPencil, Theatre.js, gpu-curtains, BrowserGym and Argos for concrete performance/accessibility/licensing before importing.
W-05 Visual quality: combine screenshot/pixel differences with layout, semantic DOM, interaction tests, Core Web Vitals and blind human design review. Pixel similarity alone is not premium UX.

## Literature/artifact leads
WebGen-V Bench; WebGen-Agent; WebGrader; Design2Code; WebWeaver; Project State Graph; Apple SQUIRE; Weblica. These were discussed in the underlying research; exact paper versions, publication and licensing must be validated before citing quantitative improvements or importing model artifacts.

## MVP evaluation protocol
3 fixed viewports, identical seed/tasks, no client data, bounded time, held-out pages and a blind UI review. Primary outcomes: tests passed, accessibility violations, layout stability, successful flows, reviewer-rated UI quality and human rework time. Report confidence, costs, and failures, not a single marketing score. Human review authorizes baseline snapshots.

## Limitation
Rendered demo and local smoke tests are available; no tested production deployment, live office data integration or visual performance superiority is claimed.