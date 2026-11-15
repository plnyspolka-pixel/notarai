#!/usr/bin/env node
import fs from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { chromium } from 'playwright';
import axe from 'axe-core';
import pixelmatch from 'pixelmatch';
import pngjs from 'pngjs';
import { allowSubresource, readArgs, slug, validateTarget, VIEWPORTS } from './policy.mjs';
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

async function main() {
  const args = readArgs(process.argv.slice(2));
  const target = validateTarget(args.url, {
    allowRemote: Boolean(args['allow-remote']),
    allowHosts: args['allow-hosts'],
  });
  const name = slug(args.name || target.hostname);
  const outputDir = path.resolve(args.out || 'artifacts/web-factory', name);
  const baselineDir = path.resolve(args.baseline || 'baselines', name);
  const threshold = Number(args['visual-threshold'] ?? 0.015);
  await fs.mkdir(path.join(outputDir, 'images'), { recursive: true });
  if (args['write-baseline']) await fs.mkdir(baselineDir, { recursive: true });

  const report = {
    schemaVersion: 1,
    name,
    target: target.origin + target.pathname,
    createdAt: new Date().toISOString(),
    safety: {
      remoteTargetApproved: Boolean(args['allow-remote']),
      externalAssetHosts: args['asset-hosts'] || '',
      note: 'No authenticated production data or real customer documents should be used.',
    },
    viewports: {},
  };

  const browser = await chromium.launch({
    headless: true,
    args: ['--disable-dev-shm-usage'],
  });
  try {
    for (const [viewportName, viewport] of Object.entries(VIEWPORTS)) {
      const context = await browser.newContext({
        viewport,
        deviceScaleFactor: 1,
        reducedMotion: 'reduce',
        colorScheme: 'light',
        serviceWorkers: 'block',
        ignoreHTTPSErrors: false,
      });
      const page = await context.newPage();
      const viewportReport = {
        screenshot: 'images/' + viewportName + '.png',
        accessibility: [],
        consoleErrors: [],
        pageErrors: [],
        failedRequests: [],
        blockedResources: [],
      };
      report.viewports[viewportName] = viewportReport;

      await context.route('**/*', async route => {
        const requested = route.request().url();
        if (allowSubresource(requested, target, args['asset-hosts'])) {
          await route.continue();
        } else {
          if (viewportReport.blockedResources.length < 50) {
            viewportReport.blockedResources.push(requested.split('?')[0]);
          }
          await route.abort('blockedbyclient');
        }
      });
      page.on('console', message => {
        if (message.type() === 'error' && viewportReport.consoleErrors.length < 30) {
          viewportReport.consoleErrors.push(message.text().slice(0, 300));
        }
      });
      page.on('pageerror', error => {
        if (viewportReport.pageErrors.length < 30) {
          viewportReport.pageErrors.push(String(error.message).slice(0, 300));
        }
      });
      page.on('requestfailed', request => {
        if (request.url().startsWith(target.origin) && viewportReport.failedRequests.length < 30) {
          viewportReport.failedRequests.push(request.url().split('?')[0] + ': ' +
            (request.failure()?.errorText || 'failed'));
        }
      });

      try {
        const response = await page.goto(target.href, {
          waitUntil: 'domcontentloaded',
          timeout: 25000,
        });
        if (response?.status() >= 400) {
          viewportReport.pageErrors.push('Navigation returned HTTP ' + response.status());
        }
        await page.waitForLoadState('networkidle', { timeout: 7000 }).catch(() => {});
        await page.waitForTimeout(350);
        await page.addScriptTag({ content: axe.source });
        const violations = await page.evaluate(async () => {
          const outcome = await window.axe.run(document, {
            runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa'] },
          });
          return outcome.violations.map(item => ({
            id: item.id,
            impact: item.impact,
            description: item.help,
            nodes: item.nodes.length,
          }));
        });
        viewportReport.accessibility = violations;
      } catch (error) {
        viewportReport.pageErrors.push('Audit or navigation failed: ' + String(error.message).slice(0, 300));
      }

      const file = path.join(outputDir, viewportReport.screenshot);
      try {
        await page.screenshot({ path: file, fullPage: true, animations: 'disabled', timeout: 15000 });
        const referencePath = path.join(baselineDir, viewportName + '.png');
        if (args['write-baseline']) {
          await fs.copyFile(file, referencePath);
          viewportReport.visual = { status: 'baseline-written' };
        } else {
          viewportReport.visual = await visualDiff(
            file,
            referencePath,
            path.join(outputDir, 'images', viewportName + '-diff.png'),
          );
        }
      } catch (error) {
        viewportReport.pageErrors.push('Screenshot failure: ' + String(error.message).slice(0, 300));
        viewportReport.visual = { status: 'screenshot-error' };
      }
      await context.close();
    }
  } finally {
    await browser.close();
  }
  report.summary = summarise(report, threshold);
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
