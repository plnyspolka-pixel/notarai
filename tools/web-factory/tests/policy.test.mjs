import test from 'node:test';
import assert from 'node:assert/strict';
import { allowSubresource, isStubbed, parseStubs, parseAllowlist, parseBudgets, parseExcludes, parsePaths, parseVariants, readArgs, slug, validateTarget, VIEWPORTS } from '../src/policy.mjs';
import { collectRuns, failureLines, escapeHtml, evaluateViewport, renderHtml, summarise } from '../src/quality.mjs';

test('local http target is permitted', () => {
  assert.equal(validateTarget('http://127.0.0.1:5173/demo').pathname, '/demo');
});

test('remote targets are denied without explicit exact host approval', () => {
  assert.throws(() => validateTarget('https://example.com'), /Remote navigation/);
  assert.throws(() => validateTarget('https://example.com', {allowRemote:true,allowHosts:'sub.example.com'}), /Remote navigation/);
  assert.equal(validateTarget('https://example.com', {allowRemote:true,allowHosts:'example.com'}).hostname, 'example.com');
});

test('HTTP remote targets and URL credentials are denied', () => {
  assert.throws(() => validateTarget('http://example.com', {allowRemote:true,allowHosts:'example.com'}), /HTTPS/);
  assert.throws(() => validateTarget('https://alice:secret@example.com', {allowRemote:true,allowHosts:'example.com'}), /Credentials/);
  assert.throws(() => validateTarget('file:///etc/passwd'), /Only http/);
});

test('external subresources are denied unless host is approved', () => {
  const target = new URL('http://localhost:5173/');
  assert.equal(allowSubresource('http://localhost:5173/style.css', target), true);
  assert.equal(allowSubresource('https://tracker.example/collect', target), false);
  assert.equal(allowSubresource('https://fonts.example/font.woff2', target, 'fonts.example'), true);
  assert.equal(allowSubresource('http://fonts.example/font.woff2', target, 'fonts.example'), false);
  assert.equal(allowSubresource('data:image/png;base64,aGVsbG8=', target), true);
});

test('slug strips path characters and unsafe names', () => {
  assert.equal(slug('../../Świetny Panel!'), 'swietny-panel');
  assert.equal(slug('---'), 'site');
  assert.deepEqual(parseAllowlist('Example.COM,example.com, fonts.example'), ['example.com','fonts.example']);
});

test('CLI rejects unknown switches and malformed thresholds', () => {
  assert.throws(() => readArgs(['--url','http://localhost:5173','--mystery']), /Unknown option/);
  assert.throws(() => readArgs(['--url','http://localhost:5173','--visual-threshold','2']), /between/);
  assert.equal(readArgs(['--url=http://localhost:5173','--write-baseline'])['write-baseline'], true);
});

test('critical accessibility, JS exceptions and visual regression fail a viewport', () => {
  const base = {accessibility:[],consoleErrors:[],pageErrors:[],failedRequests:[],visual:{status:'compared',ratio:0.005}};
  assert.equal(evaluateViewport(base, 0.015).pass, true);
  assert.equal(evaluateViewport({...base,accessibility:[{impact:'critical'}]}, 0.015).pass, false);
  assert.equal(evaluateViewport({...base,pageErrors:['boom']}, 0.015).pass, false);
  assert.equal(evaluateViewport({...base,visual:{status:'compared',ratio:0.05}}, 0.015).pass, false);
  assert.equal(summarise({viewports:{desktop:base,mobile:base}},0.015).viewportsChecked,2);
});

test('HTML report escapes dynamic content', () => {
  assert.equal(escapeHtml('<script>"x"</script>'), '&lt;script&gt;&quot;x&quot;&lt;/script&gt;');
});

test('extra paths must stay on the target origin', () => {
  const target = new URL('http://localhost:5173/');
  assert.deepEqual(parsePaths(undefined, target), ['/']);
  assert.deepEqual(parsePaths('/, /kalkulator/,/', target), ['/', '/kalkulator/']);
  assert.throws(() => parsePaths('//evil.example/x', target), /same-origin/);
  assert.throws(() => parsePaths('https://evil.example/x', target), /same-origin/);
  assert.throws(() => parsePaths('kalkulator', target), /same-origin/);
});

test('variants and budgets are validated', () => {
  assert.deepEqual(parseVariants(), ['base', 'motion', 'dark']);
  assert.deepEqual(parseVariants('base,motion'), ['base', 'motion']);
  assert.throws(() => parseVariants('base,sparkle'), /Unknown variant/);
  assert.equal(parseBudgets({}).cls, 0.1);
  assert.equal(parseBudgets({ 'budget-kb': '800' }).weightKb, 800);
  assert.throws(() => parseBudgets({ 'budget-cls': '-1' }), /between/);
  assert.equal(VIEWPORTS.small.width, 320);
});

test('overflow and budget overruns fail a run; non-compared variants are not unbaselined', () => {
  const budgets = { cls: 0.1, lcpMs: 2500, weightKb: 1500 };
  const ok = { accessibility: [], consoleErrors: [], pageErrors: [], failedRequests: [],
    visual: { status: 'not-compared' }, metrics: { lcpMs: 400, cls: 0.02, weightKb: 300, overflowPx: 0 } };
  assert.equal(evaluateViewport(ok, 0.015, budgets).pass, true);
  assert.equal(evaluateViewport(ok, 0.015, budgets).visualUnbaselined, false);
  assert.equal(evaluateViewport({ ...ok, metrics: { ...ok.metrics, overflowPx: 12 } }, 0.015, budgets).pass, false);
  assert.equal(evaluateViewport({ ...ok, metrics: { ...ok.metrics, cls: 0.4 } }, 0.015, budgets).pass, false);
  assert.equal(evaluateViewport({ ...ok, metrics: { ...ok.metrics, weightKb: 4000 } }, 0.015, budgets).pass, false);
  assert.equal(evaluateViewport({ ...ok, visual: { status: 'no-baseline' } }, 0.015, budgets).visualUnbaselined, true);
});

test('v2 reports are summarised per page and rendered with escaping', () => {
  const run = { screenshot: 'images/home/desktop-base.png', accessibility: [], consoleErrors: ['<b>x</b>'],
    pageErrors: [], failedRequests: [], blockedResources: ['https://cdn.example/a.js'], visual: { status: 'no-baseline' } };
  const report = { name: 'demo', createdAt: 'now', pages: { '/': { runs: { 'desktop-base': run } }, '/a/': { runs: { 'desktop-base': { ...run, consoleErrors: [] } } } } };
  assert.equal(collectRuns(report).length, 2);
  report.summary = summarise(report, 0.015);
  assert.equal(report.summary.pagesChecked, 2);
  assert.equal(report.summary.pass, false);
  assert.equal(report.summary.blockedThirdParty, 2);
  const html = renderHtml(report);
  assert.ok(html.includes('&lt;b&gt;x&lt;/b&gt;'));
  assert.ok(!html.includes('<b>x</b>'));
});

test('accessibility exclusions accept only plain selectors', () => {
  assert.deepEqual(parseExcludes('.brand-logo__word, #x'), ['.brand-logo__word', '#x']);
  assert.deepEqual(parseExcludes(), []);
  assert.throws(() => parseExcludes('<script>'), /plain CSS/);
});

test('stubbed backends are answered locally and third-party requests fail the gate', () => {
  const target = new URL('http://localhost:5173/');
  const stubs = parseStubs({ 'stub-hosts': 'app.example.org', 'stub-paths': '/api/' });
  assert.equal(isStubbed('https://app.example.org/api/x', target, stubs), true);
  assert.equal(isStubbed('http://localhost:5173/api/taksa?x=1', target, stubs), true);
  assert.equal(isStubbed('http://localhost:5173/style.css', target, stubs), false);
  assert.equal(isStubbed('https://other.example/api/', target, stubs), false);
  assert.throws(() => parseStubs({ 'stub-paths': 'api' }), /path prefixes/);
  const run = { accessibility: [], consoleErrors: [], pageErrors: [], failedRequests: [], blockedResources: ['https://cdn.example/x.js'] };
  assert.equal(evaluateViewport(run).pass, false);
  assert.equal(evaluateViewport({ ...run, blockedResources: [] }).pass, true);
});

test('failing runs are explained in one line each', () => {
  const run = { accessibility: [{ id: 'label', impact: 'critical' }], consoleErrors: [], pageErrors: [], failedRequests: [],
    blockedResources: [], metrics: { lcpMs: 3000, cls: 0, weightKb: 10, overflowPx: 0 } };
  const lines = failureLines({ pages: { '/x/': { runs: { 'mobile-base': run } } } }, 0.015, { cls: 0.1, lcpMs: 2500, weightKb: 1500 });
  assert.equal(lines.length, 1);
  assert.match(lines[0], /^\/x\/ \[mobile-base\] LCP 3000ms > 2500ms; a11y: label$/);
});
