import { URL } from 'node:url';

export const VIEWPORTS = Object.freeze({
  desktop: { width: 1440, height: 900 },
  tablet: { width: 834, height: 1112 },
  mobile: { width: 390, height: 844 },
});

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
  for (let index = 0; index < args.length; index++) {
    const item = args[index];
    if (!item.startsWith('--')) throw new Error('Unexpected argument: ' + item);
    const withoutPrefix = item.slice(2);
    const equals = withoutPrefix.indexOf('=');
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
  const allowed = new Set(['url','name','out','baseline','write-baseline','allow-remote','allow-hosts','asset-hosts','visual-threshold','strict']);
  for (const key of Object.keys(result)) if (!allowed.has(key)) throw new Error('Unknown option --' + key);
  if (result['visual-threshold'] !== undefined) {
    const number = Number(result['visual-threshold']);
    if (!Number.isFinite(number) || number < 0 || number > 1) throw new Error('visual-threshold must be between 0 and 1');
  }
  return result;
}
