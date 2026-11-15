# Web Factory — agent-native frontend laboratory (MVP)

Isolated, **local-first** frontend quality toolchain added to NotarAI as an optional development utility.
It does **not** change application routes, authentication, production build, runtime dependencies, or deployments.
Designed for reuse in Finance You.

## What exists now

- 3 deterministic viewport screenshots (1440x900, 834x1112, 390x844).
- axe-core checks against WCAG A/AA (2.0/2.1 tags).
- JavaScript console/page errors and first-party failed requests.
- Visual comparison against explicitly approved PNG baselines (pixelmatch).
- JSON + HTML reports, red/green quality gate for CI.
- Local-only navigation by default; remote hosts and third-party assets require exact explicit allowlists.
- Sample DTCG-style token file and OSS component evaluation registry.
- Node built-in unit tests and standalone GitHub Actions check.

## Run locally

Requires Node >=20 and a separate running application (NotarAI, Finance You, or a local preview).

    cd tools/web-factory
    npm install
    npx playwright install chromium
    npm test
    npm run audit -- --url=http://127.0.0.1:5173 --name=notarai

Outputs:
- artifacts/web-factory/notarai/report.json
- artifacts/web-factory/notarai/index.html
- artifacts/web-factory/notarai/images/{desktop,tablet,mobile}.png

Create initial baselines ONLY after human approval:

    npm run audit -- --url=http://127.0.0.1:5173 --name=notarai --write-baseline

The baseline PNGs live under baselines/notarai/. Commit reviewed baseline snapshots if you want CI diffs.

To fail the command on serious accessibility/runtime/network errors or visual diffs above the threshold:

    npm run audit -- --url=http://127.0.0.1:5173 --name=notarai --strict --visual-threshold=0.015

**Important:** No approved baseline means the visual regression status is "unbaselined"; it is not treated as evidence of pixel-level similarity.

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
    design-system/         initial design-token skeleton and OSS candidates

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
- [ ] Connect real NotarAI staging/local URL and capture approved baselines.
- [ ] Add screenshot-to-token extraction with a reviewed parser.
- [ ] Build an agent tool interface on top of audit reports.
- [ ] Integrate typography and focus-state checks.
- [ ] Add design proposal evaluation with human approval before merge.

The most important rule: **agent proposes code, deterministic tools check it, humans approve design baselines and production releases.**
