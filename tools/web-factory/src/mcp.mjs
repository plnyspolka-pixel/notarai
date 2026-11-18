#!/usr/bin/env node
import process from 'node:process';
import path from 'node:path';
import fs from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { McpServer } from '@modelcontextprotocol/server';
import { StdioServerTransport } from '@modelcontextprotocol/server/stdio';
import * as z from 'zod/v4';
import { parsePaths, slug, validateTarget } from './policy.mjs';
import { collectRuns } from './quality.mjs';

const run = promisify(execFile);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const server = new McpServer({ name: 'web-factory', version: '0.1.0' });

// Deliberately NO tool for writing baselines, committing code, or deploying.
server.registerTool('audit_page', {
  title: 'Audit a local or operator-approved staging page',
  description: 'Audit one or more same-origin pages at four viewport widths, with reduced motion, full motion and dark scheme: accessibility, runtime errors, horizontal overflow, CLS/LCP/weight budgets, blocked third-party requests and approved visual baselines. Returns a concise JSON summary. No production data.',
  inputSchema: z.object({
    url: z.string().url().max(2048),
    name: z.string().regex(/^[a-zA-Z0-9_-]{1,64}$/).optional(),
    paths: z.array(z.string().max(512)).max(40).optional(),
  }),
}, async ({ url, name, paths }) => {
  try {
    const remote = process.env.WEB_FACTORY_ALLOW_REMOTE === 'true';
    const allowHosts = process.env.WEB_FACTORY_ALLOWED_HOSTS || '';
    const target = validateTarget(url, { allowRemote: remote, allowHosts });
    const site = slug(name || target.hostname);
    const args = [
      path.join(root, 'src', 'audit.mjs'),
      '--url', target.href,
      '--name', site,
      '--out', path.join(root, 'artifacts', 'mcp'),
    ];
    if (paths?.length) {
      parsePaths(paths.join(','), target);
      args.push('--paths', paths.join(','));
    }
    if (remote && allowHosts) args.push('--allow-remote', '--allow-hosts', allowHosts);
    const assetHosts = process.env.WEB_FACTORY_ASSET_HOSTS || '';
    if (assetHosts) args.push('--asset-hosts', assetHosts);
    // No shell, no inherited browser cookies, no user-supplied filesystem paths.
    const { stdout } = await run(process.execPath, args, {
      cwd: root,
      timeout: 900000,
      maxBuffer: 1024 * 1024,
    });
    const reportPath = path.join(root, 'artifacts', 'mcp', site, 'report.json');
    const data = JSON.parse(await fs.readFile(reportPath, 'utf8'));
    const structured = {
      status: data.summary.pass ? 'pass' : 'fail',
      summary: data.summary,
      runs: collectRuns(data).map(({ pagePath, key, run }) => ({
        page: pagePath,
        run: key,
        accessibility: run.accessibility,
        metrics: run.metrics,
        visual: run.visual,
        consoleErrorCount: run.consoleErrors.length,
        pageErrorCount: run.pageErrors.length,
        failedRequestCount: run.failedRequests.length,
        blockedThirdParty: run.blockedResources,
      })),
      reportPath,
      htmlPath: path.join(root, 'artifacts', 'mcp', site, 'index.html'),
      commandSummary: stdout.trim().slice(0, 500),
    };
    return {
      content: [{ type: 'text', text: JSON.stringify(structured, null, 2) }],
      structuredContent: structured,
    };
  } catch (error) {
    return {
      isError: true,
      content: [{ type: 'text', text: 'Audit denied or failed: ' + String(error.message).slice(0, 500) }],
    };
  }
});

server.registerTool('list_oss_components', {
  title: 'List reviewed open-source frontend candidates',
  description: 'Read local versioned OSS registry. Library inclusion is not permission to skip license review.',
  inputSchema: z.object({ category: z.string().max(80).optional() }),
}, async ({ category }) => {
  const registry = JSON.parse(await fs.readFile(path.join(root, 'design-system', 'oss-registry.json'), 'utf8'));
  const entries = registry.approvedForEvaluation.filter(x => !category || x.category === category);
  const result = { entries, legalReview: registry.requiresSeparateLegalReview };
  return {
    content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
    structuredContent: result,
  };
});

server.registerTool('read_design_tokens', {
  title: 'Read versioned design tokens',
  description: 'Read the NotarAI brand tokens (colour, type, radius, spacing, motion) for reproducible UI generation.',
  inputSchema: z.object({}),
}, async () => {
  const tokens = JSON.parse(await fs.readFile(path.join(root, 'design-system', 'tokens.json'), 'utf8'));
  return {
    content: [{ type: 'text', text: JSON.stringify(tokens, null, 2) }],
    structuredContent: tokens,
  };
});

// Stdio MCP: stdout must contain protocol messages only.
const transport = new StdioServerTransport();
await server.connect(transport);
