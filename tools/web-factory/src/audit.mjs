#!/usr/bin/env node
import fs from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { chromium } from 'playwright';
import axe from 'axe-core';
import pixelmatch from 'pixelmatch';
import pngjs from 'pngjs';
import {
  allowSubresource, isStubbed, parseBudgets, parseExcludes, parsePaths, parseStubs, parseVariants, readArgs, slug,
  validateTarget, VARIANTS, VIEWPORTS,
} from './policy.mjs';
import { renderHtml, summarise } from './quality.mjs';

const { PNG } = pngjs;

async function visualDiff(actualPath, referencePath, diffPath) {
  try {
    await fs.access(referencePath);
  } catch {
    return { status: 'no-baseline' };
  }
  const actual = PNG.sync.read(await fs.readFile(actualPath));
  const baseline = PNG.sync.read(await fs.readFile(referencePath));
  if (actual.width !== baseline.width || actual.height !== baseline.height) {
    return {
      status: 'compared',
      ratio: 1,
      note: 'Image dimensions differ: ' + actual.width + 'x' + actual.height +
        ' vs ' + baseline.width + 'x' + baseline.height,
    };
  }
  const diff = new PNG({ width: actual.width, height: actual.height });
  const count = pixelmatch(actual.data, baseline.data, diff.data, actual.width, actual.height, {
    threshold: 0.12,
    includeAA: false,
  });
  await fs.writeFile(diffPath, PNG.sync.write(diff));
  return {
    status: 'compared',
    ratio: count / (actual.width * actual.height),
    differentPixels: count,
    totalPixels: actual.width * actual.height,
    diff: path.basename(diffPath),
  };
}

// Runs in the page before any site script: records paint and layout-shift entries.
function installProbe() {
  const state = { lcp: 0, cls: 0 };
  Object.defineProperty(window, '__webFactory', { value: state });
  try {
    new PerformanceObserver(list => {
      for (const entry of list.getEntries()) state.lcp = Math.max(state.lcp, entry.startTime);
    }).observe({ type: 'largest-contentful-paint', buffered: true });
    new PerformanceObserver(list => {
      for (const entry of list.getEntries()) if (!entry.hadRecentInput) state.cls += entry.value;
    }).observe({ type: 'layout-shift', buffered: true });
  } catch { /* metrics stay at zero where the browser lacks the entry types */ }
}

function readMetrics() {
  const entries = [
    ...performance.getEntriesByType('navigation'),
    ...performance.getEntriesByType('resource'),
  ];
  const bytes = entries.reduce((sum, e) => sum + (e.transferSize || e.encodedBodySize || 0), 0);
  const root = document.documentElement;
  return {
    lcpMs: Math.round(window.__webFactory?.lcp || 0),
    cls: Number((window.__webFactory?.cls || 0).toFixed(4)),
    weightKb: Math.round(bytes / 1024),
    requests: entries.length,
    overflowPx: Math.max(0, root.scrollWidth - root.clientWidth),
  };
}

// Walks the page so scroll-linked and in-view animations actually run.
async function scrollThrough(page) {
  await page.evaluate(async () => {
    const step = Math.max(200, Math.floor(window.innerHeight * 0.8));
    const limit = Math.min(document.documentElement.scrollHeight, 40000);
    for (let y = 0; y < limit; y += step) {
      window.scrollTo(0, y);
      await new Promise(resolve => setTimeout(resolve, 120));
    }
    window.scrollTo(0, 0);
    await new Promise(resolve => setTimeout(resolve, 250));
  });
}

async function auditRun({ browser, target, pagePath, viewportName, variantName, args, stubs, outputDir, baselineDir, pageSlug }) {
  const variant = VARIANTS[variantName];
  const context = await browser.newContext({
    viewport: VIEWPORTS[viewportName],
    deviceScaleFactor: 1,
    reducedMotion: variant.reducedMotion,
    colorScheme: variant.colorScheme,
    serviceWorkers: 'block',
    ignoreHTTPSErrors: false,
  });
  const run = {
    viewport: viewportName,
    variant: variantName,
    screenshot: path.posix.join('images', pageSlug, viewportName + '-' + variantName + '.png'),
    accessibility: [],
    consoleErrors: [],
    pageErrors: [],
    failedRequests: [],
    blockedResources: [],
    stubbedRequests: [],
    metrics: null,
  };
  try {
    await context.addInitScript(installProbe);
    const page = await context.newPage();
    await context.route('**/*', async route => {
      const requested = route.request().url();
      if (isStubbed(requested, target, stubs)) {
        if (run.stubbedRequests.length < 50) run.stubbedRequests.push(requested.split('?')[0]);
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          headers: { 'access-control-allow-origin': '*', 'access-control-allow-headers': '*' },
          body: '{}',
        });
      } else if (allowSubresource(requested, target, args['asset-hosts'])) {
        await route.continue();
      } else {
        if (run.blockedResources.length < 50) run.blockedResources.push(requested.split('?')[0]);
        await route.abort('blockedbyclient');
      }
    });
    page.on('console', message => {
      // A request this tool blocked is already listed under blockedResources.
      if (message.text().includes('ERR_BLOCKED_BY_CLIENT')) return;
      if (message.type() === 'error' && run.consoleErrors.length < 30) {
        run.consoleErrors.push(message.text().slice(0, 300));
      }
    });
    page.on('pageerror', error => {
      if (run.pageErrors.length < 30) run.pageErrors.push(String(error.message).slice(0, 300));
    });
    page.on('requestfailed', request => {
      if (request.url().startsWith(target.origin) && run.failedRequests.length < 30) {
        run.failedRequests.push(request.url().split('?')[0] + ': ' + (request.failure()?.errorText || 'failed'));
      }
    });

    try {
      const response = await page.goto(new URL(pagePath, target.origin).href, {
        waitUntil: 'domcontentloaded',
        timeout: 25000,
      });
      if (response?.status() >= 400) run.pageErrors.push('Navigation returned HTTP ' + response.status());
      await page.waitForLoadState('networkidle', { timeout: 7000 }).catch(() => {});
      await page.waitForTimeout(350);
      if (!variant.baseline) await scrollThrough(page);
      run.metrics = await page.evaluate(readMetrics);
      await page.addScriptTag({ content: axe.source });
      run.accessibility = await page.evaluate(async ({ excluded, midAnimation }) => {
        const scope = excluded.length ? { exclude: excluded.map(selector => [selector]) } : document;
        const outcome = await window.axe.run(scope, {
          runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'] },
          // Off-screen elements sit at the first frame of their scroll animation, so their
          // contrast is meaningless here; the base and dark variants measure it at rest.
          rules: midAnimation ? { 'color-contrast': { enabled: false } } : {},
        });
        return outcome.violations.map(item => ({
          id: item.id,
          impact: item.impact,
          description: item.help,
          nodes: item.nodes.length,
          targets: item.nodes.slice(0, 8).map(node => String(node.target?.[0] ?? '').slice(0, 120)),
        }));
      }, { excluded: parseExcludes(args['a11y-exclude']), midAnimation: variant.reducedMotion !== 'reduce' });
    } catch (error) {
      run.pageErrors.push('Audit or navigation failed: ' + String(error.message).slice(0, 300));
    }

    const file = path.join(outputDir, run.screenshot);
    try {
      await fs.mkdir(path.dirname(file), { recursive: true });
      await page.screenshot({
        path: file,
        fullPage: true,
        animations: variant.baseline ? 'disabled' : 'allow',
        timeout: 15000,
      });
      if (!variant.baseline) {
        run.visual = { status: 'not-compared' };
      } else {
        const referencePath = path.join(baselineDir, pageSlug, viewportName + '.png');
        if (args['write-baseline']) {
          await fs.mkdir(path.dirname(referencePath), { recursive: true });
          await fs.copyFile(file, referencePath);
          run.visual = { status: 'baseline-written' };
        } else {
          run.visual = await visualDiff(
            file,
            referencePath,
            path.join(outputDir, 'images', pageSlug, viewportName + '-diff.png'),
          );
        }
      }
    } catch (error) {
      run.pageErrors.push('Screenshot failure: ' + String(error.message).slice(0, 300));
      run.visual = { status: 'screenshot-error' };
    }
  } finally {
    await context.close();
  }
  return run;
}

async function main() {
  const args = readArgs(process.argv.slice(2));
  const target = validateTarget(args.url, {
    allowRemote: Boolean(args['allow-remote']),
    allowHosts: args['allow-hosts'],
  });
  const pagePaths = parsePaths(args.paths, target);
  const variants = parseVariants(args.variants);
  const budgets = parseBudgets(args);
  const stubs = parseStubs(args);
  const name = slug(args.name || target.hostname);
  const outputDir = path.resolve(args.out || 'artifacts/web-factory', name);
  const baselineDir = path.resolve(args.baseline || 'baselines', name);
  const threshold = Number(args['visual-threshold'] ?? 0.015);
  await fs.mkdir(path.join(outputDir, 'images'), { recursive: true });

  const report = {
    schemaVersion: 2,
    name,
    target: target.origin,
    createdAt: new Date().toISOString(),
    variants,
    budgets,
    a11yExcluded: parseExcludes(args['a11y-exclude']),
    stubs,
    safety: {
      remoteTargetApproved: Boolean(args['allow-remote']),
      externalAssetHosts: args['asset-hosts'] || '',
      note: 'No authenticated production data or real customer documents should be used.',
    },
    pages: {},
  };

  const browser = await chromium.launch({ headless: true, args: ['--disable-dev-shm-usage'] });
  try {
    for (const pagePath of pagePaths) {
      const pageSlug = pagePath === '/' ? 'home' : slug(pagePath);
      const runs = {};
      for (const viewportName of Object.keys(VIEWPORTS)) {
        for (const variantName of variants) {
          runs[viewportName + '-' + variantName] = await auditRun({
            browser, target, pagePath, viewportName, variantName, args, stubs, outputDir, baselineDir, pageSlug,
          });
        }
      }
      report.pages[pagePath] = { slug: pageSlug, runs };
    }
  } finally {
    await browser.close();
  }
  report.summary = summarise(report, threshold, budgets);
  await fs.writeFile(path.join(outputDir, 'report.json'), JSON.stringify(report, null, 2) + '\n');
  await fs.writeFile(path.join(outputDir, 'index.html'), renderHtml(report));
  console.log('Web Factory report: ' + path.join(outputDir, 'index.html'));
  console.log(JSON.stringify(report.summary));
  if (args.strict && !report.summary.pass) process.exitCode = 1;
}

main().catch(error => {
  console.error('Web Factory error:', error.message);
  process.exitCode = 1;
});
