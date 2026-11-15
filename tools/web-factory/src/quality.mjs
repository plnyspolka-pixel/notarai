const NO_BUDGETS = Object.freeze({ cls: Infinity, lcpMs: Infinity, weightKb: Infinity });

export function evaluateViewport(entry, threshold = 0.015, budgets = NO_BUDGETS) {
  const severe = (entry.accessibility || []).filter(item => ['critical', 'serious'].includes(item.impact));
  const runtimeErrors = (entry.consoleErrors || []).length + (entry.pageErrors || []).length;
  const brokenRequests = (entry.failedRequests || []).length;
  const changedPixels = entry.visual?.status === 'compared' ? entry.visual.ratio : null;
  const metrics = entry.metrics || {};
  const overBudget = [];
  if ((metrics.overflowPx || 0) > 0) overBudget.push('horizontal overflow ' + metrics.overflowPx + 'px');
  if ((metrics.cls || 0) > budgets.cls) overBudget.push('CLS ' + metrics.cls + ' > ' + budgets.cls);
  if ((metrics.lcpMs || 0) > budgets.lcpMs) overBudget.push('LCP ' + metrics.lcpMs + 'ms > ' + budgets.lcpMs + 'ms');
  if ((metrics.weightKb || 0) > budgets.weightKb) overBudget.push('weight ' + metrics.weightKb + 'kB > ' + budgets.weightKb + 'kB');
  // A request to a host nobody approved is a privacy defect, not a warning.
  const blocked = (entry.blockedResources || []).length;
  return {
    pass: severe.length === 0 && runtimeErrors === 0 && brokenRequests === 0 && overBudget.length === 0 && blocked === 0 &&
      (changedPixels === null || changedPixels <= threshold),
    severeAccessibility: severe.length,
    runtimeErrors,
    brokenRequests,
    blockedThirdParty: blocked,
    changedPixels,
    overBudget,
    // Only the deterministic variant is ever compared, so only it can be "unbaselined".
    visualUnbaselined: entry.visual?.status === 'no-baseline',
  };
}

// Accepts the v2 shape (pages -> runs) and the v1 shape (viewports) used by older reports.
export function collectRuns(report) {
  if (report.pages) {
    return Object.entries(report.pages).flatMap(([pagePath, page]) =>
      Object.entries(page.runs).map(([key, run]) => ({ pagePath, key, run })));
  }
  return Object.entries(report.viewports || {}).map(([key, run]) => ({ pagePath: '/', key, run }));
}

export function summarise(report, threshold, budgets) {
  const runs = collectRuns(report);
  const checks = runs.map(item => evaluateViewport(item.run, threshold, budgets));
  const sum = pick => checks.reduce((total, check) => total + pick(check), 0);
  return {
    pass: checks.every(check => check.pass),
    pagesChecked: new Set(runs.map(item => item.pagePath)).size,
    viewportsChecked: checks.length,
    severeAccessibility: sum(x => x.severeAccessibility),
    runtimeErrors: sum(x => x.runtimeErrors),
    brokenRequests: sum(x => x.brokenRequests),
    overBudget: sum(x => x.overBudget.length),
    blockedThirdParty: sum(x => x.blockedThirdParty),
    unbaselined: checks.filter(x => x.visualUnbaselined).length,
  };
}

export function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function visualLabel(visual) {
  if (visual?.status === 'compared') return (100 * visual.ratio).toFixed(2) + '% different';
  if (visual?.status === 'not-compared') return 'Not compared (non-deterministic variant)';
  if (visual?.status === 'baseline-written') return 'Baseline written';
  return 'No approved baseline';
}

function renderRun(key, run, threshold, budgets) {
  const check = evaluateViewport(run, threshold, budgets);
  const errors = [...(run.consoleErrors || []), ...(run.pageErrors || []), ...(run.failedRequests || [])];
  const violations = (run.accessibility || []).map(item =>
    item.id + ' (' + item.impact + '): ' + item.nodes + ' nodes' +
    (item.targets?.length ? '\n    ' + item.targets.join('\n    ') : ''));
  const m = run.metrics;
  const metrics = m
    ? 'LCP ' + m.lcpMs + ' ms · CLS ' + m.cls + ' · ' + m.weightKb + ' kB in ' + m.requests + ' requests · overflow ' + m.overflowPx + ' px'
    : 'No metrics collected';
  return '<article><h3>' + escapeHtml(key) + ' — ' + (check.pass ? 'PASS' : 'FAIL') + '</h3>' +
    '<img src="' + escapeHtml(run.screenshot) + '" alt="' + escapeHtml(key) + ' screenshot" loading="lazy">' +
    '<p>Visual: ' + escapeHtml(visualLabel(run.visual)) + '</p>' +
    '<p>Metrics: ' + escapeHtml(metrics) + '</p>' +
    (check.overBudget.length ? '<p>Over budget: ' + escapeHtml(check.overBudget.join('; ')) + '</p>' : '') +
    '<h4>Accessibility</h4><pre>' + escapeHtml(violations.join('\n') || 'No violations') + '</pre>' +
    '<h4>Runtime and network</h4><pre>' + escapeHtml(errors.join('\n') || 'No errors') + '</pre>' +
    '<h4>Blocked third-party requests</h4><pre>' + escapeHtml((run.blockedResources || []).join('\n') || 'None') + '</pre></article>';
}

export function renderHtml(report) {
  const threshold = 0.015;
  const budgets = report.budgets || NO_BUDGETS;
  const byPage = new Map();
  for (const item of collectRuns(report)) {
    if (!byPage.has(item.pagePath)) byPage.set(item.pagePath, []);
    byPage.get(item.pagePath).push(renderRun(item.key, item.run, threshold, budgets));
  }
  const sections = [...byPage.entries()].map(([pagePath, rows]) =>
    '<section><h2>' + escapeHtml(pagePath) + '</h2>' + rows.join('\n') + '</section>').join('\n');
  return [
    '<!doctype html><html lang="en"><meta charset="utf-8">',
    '<meta name="viewport" content="width=device-width,initial-scale=1">',
    '<title>Web Factory report</title>',
    '<style>body{font:15px system-ui;background:#0b1321;color:#e8edf5;max-width:1200px;margin:0 auto;padding:36px}',
    'h1{font-size:30px}h2{margin-top:44px}h3{margin-top:0}article{padding:24px;margin:20px 0;background:#142238;border:1px solid #304564;border-radius:16px}',
    'img{display:block;max-width:100%;max-height:660px;object-fit:contain;background:white;border-radius:8px}',
    'pre{white-space:pre-wrap;overflow-wrap:anywhere;color:#c5d7f0}small{color:#adc2dd}</style>',
    '<main><h1>Web Factory · ' + escapeHtml(report.name) + '</h1>',
    '<p>Result: <strong>' + (report.summary.pass ? 'PASS' : 'FAIL') + '</strong></p>',
    '<pre>' + escapeHtml(JSON.stringify(report.summary)) + '</pre>',
    '<small>Local or explicitly approved test targets only · ' + escapeHtml(report.createdAt) + '</small>',
    sections, '</main></html>',
  ].join('\n');
}
