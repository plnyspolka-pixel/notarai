export function evaluateViewport(entry, threshold = 0.015) {
  const severe = (entry.accessibility || []).filter(item => ['critical', 'serious'].includes(item.impact));
  const runtimeErrors = (entry.consoleErrors || []).length + (entry.pageErrors || []).length;
  const brokenRequests = (entry.failedRequests || []).length;
  const changedPixels = entry.visual?.status === 'compared' ? entry.visual.ratio : null;
  return {
    pass: severe.length === 0 && runtimeErrors === 0 && brokenRequests === 0 &&
      (changedPixels === null || changedPixels <= threshold),
    severeAccessibility: severe.length,
    runtimeErrors,
    brokenRequests,
    changedPixels,
    visualUnbaselined: changedPixels === null,
  };
}

export function summarise(report, threshold) {
  const checks = Object.values(report.viewports).map(v => evaluateViewport(v, threshold));
  return {
    pass: checks.every(check => check.pass),
    viewportsChecked: checks.length,
    severeAccessibility: checks.reduce((sum, x) => sum + x.severeAccessibility, 0),
    runtimeErrors: checks.reduce((sum, x) => sum + x.runtimeErrors, 0),
    brokenRequests: checks.reduce((sum, x) => sum + x.brokenRequests, 0),
    unbaselined: checks.filter(x => x.visualUnbaselined).length,
  };
}

export function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function renderHtml(report) {
  const rows = Object.entries(report.viewports).map(([name, v]) => {
    const errors = [...v.consoleErrors, ...v.pageErrors, ...v.failedRequests];
    const violations = v.accessibility.map(item => item.id + ' (' + item.impact + '): ' + item.nodes + ' nodes');
    const visual = v.visual?.status === 'compared' ? (100 * v.visual.ratio).toFixed(2) + '% different' : 'No approved baseline';
    return '<article><h2>' + escapeHtml(name) + '</h2><img src="' + escapeHtml(v.screenshot) +
      '" alt="' + escapeHtml(name) + ' screenshot" loading="lazy"><p>Visual: ' + escapeHtml(visual) +
      '</p><h3>Accessibility</h3><pre>' + escapeHtml(violations.join('\n') || 'No serious violations') +
      '</pre><h3>Runtime and network</h3><pre>' + escapeHtml(errors.join('\n') || 'No errors') + '</pre></article>';
  }).join('\n');
  return [
    '<!doctype html><html lang="en"><meta charset="utf-8">',
    '<meta name="viewport" content="width=device-width,initial-scale=1">',
    '<title>Web Factory report</title>',
    '<style>body{font:15px system-ui;background:#0b1321;color:#e8edf5;max-width:1200px;margin:0 auto;padding:36px}',
    'h1{font-size:30px}h2{margin-top:0}article{padding:24px;margin:20px 0;background:#142238;border:1px solid #304564;border-radius:16px}',
    'img{display:block;max-width:100%;max-height:660px;object-fit:contain;background:white;border-radius:8px}',
    'pre{white-space:pre-wrap;overflow-wrap:anywhere;color:#c5d7f0}small{color:#adc2dd}</style>',
    '<main><h1>Web Factory · ' + escapeHtml(report.name) + '</h1>',
    '<p>Result: <strong>' + (report.summary.pass ? 'PASS' : 'FAIL') + '</strong></p>',
    '<small>Local or explicitly approved test targets only · ' + escapeHtml(report.createdAt) + '</small>',
    rows, '</main></html>'
  ].join('\n');
}
