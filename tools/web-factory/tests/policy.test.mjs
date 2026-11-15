import test from 'node:test';
import assert from 'node:assert/strict';
import { allowSubresource, parseAllowlist, readArgs, slug, validateTarget } from '../src/policy.mjs';
import { escapeHtml, evaluateViewport, summarise } from '../src/quality.mjs';

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
