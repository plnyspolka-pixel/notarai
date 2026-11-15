import { URL } from 'node:url';

export const VIEWPORTS = Object.freeze({
  desktop: { width: 1440, height: 900 },
  tablet: { width: 834, height: 1112 },
  mobile: { width: 390, height: 844 },
  small: { width: 320, height: 568 },
});

// Each variant is one browser context per viewport.
// Only "base" is deterministic enough to compare against approved baselines.
export const VARIANTS = Object.freeze({
  base: { colorScheme: 'light', reducedMotion: 'reduce', baseline: true },
  motion: { colorScheme: 'light', reducedMotion: 'no-preference', baseline: false },
  dark: { colorScheme: 'dark', reducedMotion: 'reduce', baseline: false },
});

export const DEFAULT_BUDGETS = Object.freeze({
  cls: 0.1,          // cumulative layout shift, unitless
  lcpMs: 2500,       // largest contentful paint; measured locally, so a floor not a field value
  weightKb: 1500,    // transferred bytes of the page and its subresources
});

export function parseVariants(value) {
  if (value === undefined || value === '') return Object.keys(VARIANTS);
  const names = [...new Set(String(value).split(',').map(x => x.trim()).filter(Boolean))];
  for (const name of names) {
    if (!Object.hasOwn(VARIANTS, name)) throw new Error('Unknown variant: ' + name);
  }
  if (names.length === 0) throw new Error('variants must name at least one of: ' + Object.keys(VARIANTS).join(', '));
  return names;
}

// Extra pages are same-origin paths only, so one approval covers the whole run.
export function parsePaths(value, target) {
  const base = [target.pathname + target.search];
  if (value === undefined || value === '') return base;
  const out = [];
  for (const raw of String(value).split(',').map(x => x.trim()).filter(Boolean)) {
    if (!raw.startsWith('/') || raw.startsWith('//') || raw.includes('\\')) {
      throw new Error('paths must be same-origin absolute paths such as /kalkulator/');
    }
    const resolved = new URL(raw, target.origin);
    if (resolved.origin !== target.origin) throw new Error('paths must stay on the target origin');
    out.push(resolved.pathname + resolved.search);
  }
  if (out.length > 40) throw new Error('At most 40 paths per run');
  return [...new Set(out)];
}

// Backend calls are answered locally with an empty JSON object, so an audit of a static
// build never reaches a live API. Hosts are exact names; paths are same-origin prefixes.
export function parseStubs(args = {}) {
  const hosts = parseAllowlist(args['stub-hosts']);
  const paths = String(args['stub-paths'] || '').split(',').map(x => x.trim()).filter(Boolean);
  for (const item of paths) {
    if (!item.startsWith('/') || item.startsWith('//')) throw new Error('stub-paths must be path prefixes such as /api/');
  }
  return { hosts, paths };
}

export function isStubbed(rawUrl, targetUrl, stubs) {
  let item;
  try {
    item = new URL(rawUrl);
  } catch {
    return false;
  }
  if (!['http:', 'https:'].includes(item.protocol)) return false;
  if (stubs.hosts.includes(normaliseHost(item.hostname))) return true;
  return item.origin === targetUrl.origin && stubs.paths.some(prefix => item.pathname.startsWith(prefix));
}

// Selectors skipped by the accessibility scan. Meant for WCAG-exempt content such as
// the logotype; every use should be justified where the command is written down.
export function parseExcludes(value = '') {
  const list = String(value).split(',').map(x => x.trim()).filter(Boolean);
  for (const item of list) {
    if (item.length > 120 || /[<>{}]/.test(item)) throw new Error('a11y-exclude takes plain CSS selectors');
  }
  if (list.length > 10) throw new Error('At most 10 a11y-exclude selectors');
  return list;
}

export function parseBudgets(args = {}) {
  const read = (key, fallback, max) => {
    if (args[key] === undefined) return fallback;
    const number = Number(args[key]);
    if (!Number.isFinite(number) || number < 0 || number > max) throw new Error(key + ' must be between 0 and ' + max);
    return number;
  };
  return {
    cls: read('budget-cls', DEFAULT_BUDGETS.cls, 10),
    lcpMs: read('budget-lcp', DEFAULT_BUDGETS.lcpMs, 120000),
    weightKb: read('budget-kb', DEFAULT_BUDGETS.weightKb, 1000000),
  };
}

const LOOPBACK_HOSTS = new Set(['localhost', '127.0.0.1', '[::1]']);

export function normaliseHost(host) {
  return String(host || '').trim().toLowerCase().replace(/\.$/, '');
}

export function parseAllowlist(value = '') {
  return [...new Set(String(value).split(',').map(normaliseHost).filter(Boolean))];
}

export function validateTarget(input, options = {}) {
  let parsed;
  try {
    parsed = new URL(input);
  } catch {
    throw new Error('Provide an absolute http(s) URL with --url');
  }
  if (!['http:', 'https:'].includes(parsed.protocol)) {
    throw new Error('Only http and https URLs are allowed');
  }
  if (parsed.username || parsed.password) {
    throw new Error('Credentials in URLs are forbidden');
  }
  const host = normaliseHost(parsed.hostname);
  const isLocal = LOOPBACK_HOSTS.has(host);
  if (!isLocal) {
    const hosts = parseAllowlist(options.allowHosts);
    if (options.allowRemote !== true || !hosts.includes(host)) {
      throw new Error('Remote navigation requires --allow-remote and --allow-hosts=exact.hostname');
    }
    if (parsed.protocol !== 'https:') {
      throw new Error('Remote targets must use HTTPS');
    }
  }
  parsed.hash = '';
  return parsed;
}

export function allowSubresource(rawUrl, targetUrl, externalHosts = '') {
  let item;
  try {
    item = new URL(rawUrl);
  } catch {
    return false;
  }
  if (['data:', 'blob:'].includes(item.protocol)) return true;
  if (!['http:', 'https:'].includes(item.protocol)) return false;
  if (item.origin === targetUrl.origin) return true;
  return item.protocol === 'https:' && parseAllowlist(externalHosts).includes(normaliseHost(item.hostname));
}

export function slug(value) {
  return String(value || 'site')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 64) || 'site';
}

export function readArgs(args) {
  const result = {};
  const allowed = new Set(['url','name','out','baseline','write-baseline','allow-remote','allow-hosts','asset-hosts','visual-threshold','strict','paths','variants','budget-cls','budget-lcp','budget-kb','a11y-exclude','stub-hosts','stub-paths']);
  for (let index = 0; index < args.length; index++) {
    const item = args[index];
    if (!item.startsWith('--')) throw new Error('Unexpected argument: ' + item);
    const withoutPrefix = item.slice(2);
    const equals = withoutPrefix.indexOf('=');
    const option = equals >= 0 ? withoutPrefix.slice(0, equals) : withoutPrefix;
    if (!allowed.has(option)) throw new Error('Unknown option --' + option);
    if (equals >= 0) {
      result[withoutPrefix.slice(0, equals)] = withoutPrefix.slice(equals + 1);
    } else if (['allow-remote', 'write-baseline', 'strict'].includes(withoutPrefix)) {
      result[withoutPrefix] = true;
    } else {
      if (!args[index + 1] || args[index + 1].startsWith('--')) {
        throw new Error('Missing value for --' + withoutPrefix);
      }
      result[withoutPrefix] = args[++index];
    }
  }
  if (!result.url) throw new Error('Missing required --url');
  if (result['visual-threshold'] !== undefined) {
    const number = Number(result['visual-threshold']);
    if (!Number.isFinite(number) || number < 0 || number > 1) throw new Error('visual-threshold must be between 0 and 1');
  }
  return result;
}
