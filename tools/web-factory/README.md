# Web Factory — agent-native frontend laboratory (MVP)

Isolated, **local-first** frontend quality toolchain added to NotarAI as an optional development utility.
It does **not** change application routes, authentication, production build, runtime dependencies, or deployments.
Designed for reuse in Finance You.

## What exists now

- Deterministic screenshots at 4 widths (1440, 834, 390, 320) of one or many same-origin pages (`--paths`).
- Three variants per width: `base` (light, reduced motion), `motion` (light, animations running, page scrolled end to end) and `dark`.
- axe-core checks against WCAG A/AA (2.0, 2.1, 2.2 tags), with the failing selectors in the report.
- JavaScript console/page errors and first-party failed requests.
- Horizontal overflow detection and budgets for CLS, LCP and transferred weight.
- Third-party request gate: any request to a host that was not approved is blocked, listed and fails the run.
- Local API stubs (`--stub-hosts`, `--stub-paths`) so a static build can be audited without touching a live backend.
- Visual comparison of the `base` variant against explicitly approved PNG baselines (pixelmatch).
- JSON + HTML reports, red/green quality gate for CI.
- NotarAI brand tokens (DTCG) and an OSS registry with licence status per library.
- Node built-in unit tests and GitHub Actions checks, including a strict audit of `strona/`.
- MCP v2 server for Claude Code: audit_page, list_oss_components, read_design_tokens.

## Run locally

Requires Node >=20 and a separate running application (NotarAI, Finance You, or a local preview).

    cd tools/web-factory
    npm install
    npx playwright install chromium
    npm test
    npm run audit -- --url=http://127.0.0.1:5173 --name=notarai

Audit the whole public NotarAI site (two terminals):

    npm run serve:strona
    npm run audit:strona

Outputs:
- artifacts/web-factory/notarai/report.json
- artifacts/web-factory/notarai/index.html
- artifacts/web-factory/notarai/images/<page>/<viewport>-<variant>.png

Options:

| Flag | Meaning |
|---|---|
| `--paths=/,/kalkulator/` | extra same-origin pages to audit in the same run (max 40) |
| `--variants=base,motion,dark` | which variants to run; default is all three |
| `--budget-cls=0.1 --budget-lcp=2500 --budget-kb=1500` | budgets; a run over budget fails |
| `--stub-hosts=app.notarai.pl --stub-paths=/api/` | answer these backend calls locally with `{}` |
| `--a11y-exclude=.brand-logo__word` | skip WCAG-exempt content (the logotype) in the accessibility scan |
| `--asset-hosts=fonts.example.org` | allow a third-party asset host; everything else is blocked |
| `--strict` | exit 1 when the gate fails |

LCP is measured on a local server, so it is a floor, not what a visitor on a phone network sees.
Use it to catch regressions, and Lighthouse on a deployed preview for field-like numbers.

Create initial baselines ONLY after human approval:

    npm run audit -- --url=http://127.0.0.1:5173 --name=notarai --write-baseline

The baseline PNGs live under baselines/notarai/<page>/<viewport>.png. Commit reviewed baseline snapshots if you want CI diffs.
Only the `base` variant is compared; `motion` and `dark` screenshots are for review.

**Important:** No approved baseline means the visual regression status is "unbaselined"; it is not treated as evidence of pixel-level similarity.

## Demo (visual concept, never production)

From tools/web-factory:

    python3 -m http.server 5173 --directory demo

Then open http://127.0.0.1:5173 in a browser or run the audit command above.
The fixture is an independent premium UI experiment, not the live NotarAI homepage.

## Claude Code / Codex MCP interface

The MCP server uses the official stable v2 split TypeScript SDK and stdio transport.
Install dependencies (`npm install`) and point your MCP client at the absolute path to `src/mcp.mjs` using Node.
See `mcp.example.json` for a connector configuration example; merge it into your existing MCP config rather than overwriting it.

    npm run mcp

Available read/audit tools:
- `audit_page(url, name?, paths?)` — runs the same locally constrained Playwright audit and returns result paths and metrics.
- `list_oss_components(category?)` — returns a versioned, reviewed candidate registry.
- `read_design_tokens()` — supplies token definitions for agent-generated UI.

There is deliberately no MCP tool to update baselines or deploy code. A human must approve visual baselines.
Remote staging access is opt-in by an operator through `WEB_FACTORY_ALLOW_REMOTE=true` and `WEB_FACTORY_ALLOWED_HOSTS=exact.hostname`.

## Safely audit a staging deployment

Remote targets are **blocked by default**. Explicit opt-in with an exact HTTPS hostname:

    npm run audit -- --url=https://preview.example.org --allow-remote --allow-hosts=preview.example.org --name=staging

External assets are blocked unless listed. For a controlled font CDN, add:

    --asset-hosts=fonts.example.org

Do not use production accounts, notarial documents, personal data, private customer forms, or sensitive investor information in screenshots or test fixtures.

## Architecture

    src/policy.mjs          destination policy, CLI flags, viewport matrix
    src/audit.mjs           Playwright, axe, screenshot, baseline comparison
    src/quality.mjs         quality gate, safe static HTML report
    tests/policy.test.mjs   unit tests for default-deny behavior and scoring
    design-system/         NotarAI brand tokens and OSS registry with licence status

## Security limitations

This is a *development test harness*, not a security boundary for arbitrary untrusted webpages:
- Run it on an isolated dev machine or sandbox. The app itself may execute scripts, navigate or open WebSockets.
- Domain allowlists are explicit, not a substitute for network-level egress controls.
- Reports may contain UI text, URLs, error messages and screenshots; keep artifacts private.
- Remote staging should use synthetic accounts and test data only.
- Browser automation is read/write capable. Do not point at live business workflows.
- No production deployment or automatically applied design changes are performed.

## Definition of done: first iteration

- [x] React/framework-independent visual audit.
- [x] Strict CI quality gate, with no model/API key requirement.
- [x] Unit tests for URL restrictions, scoring and sanitization.
- [x] Machine-readable design tokens and OSS component manifest.
- [x] Connect the real NotarAI public site (`strona/`) to a strict CI audit.
- [ ] Capture approved visual baselines (needs human sign-off).
- [x] Motion, dark-scheme and 320 px runs; overflow, CLS/LCP/weight budgets; third-party request gate.
- [ ] Add screenshot-to-token extraction with a reviewed parser.
- [x] Add an MCP v2 read/audit interface (no deploy/write permissions).
- [ ] Integrate typography and keyboard focus-state checks.
- [ ] Add design proposal evaluation with human approval before merge.

The most important rule: **agent proposes code, deterministic tools check it, humans approve design baselines and production releases.**
