/* NotarAI Confidential Browser: opt-in AUTO preview client.
 * Does not submit or sign anything. It is visible only when the authenticated
 * backend explicitly exposes the confidential pilot for this tenant.
 */
(function () {
  'use strict';
  const ID = /^[A-Za-z0-9_-]{1,80}$/;
  let verifiedPolicy = null;

  async function loadPolicy() {
    const response = await fetch('/api/confidential/policy', {
      credentials: 'same-origin', cache: 'no-store',
      headers: {Accept: 'application/json'}
    });
    if (!response.ok) throw new Error('Confidential AUTO unavailable');
    const value = await response.json();
    if (!value || value.version !== 1 || value.mode !== 'auto' ||
        value.can_submit !== false || value.can_sign !== false ||
        value.external_writes_enabled !== false ||
        value.thinking_enabled !== false) {
      throw new Error('Unsafe confidential policy');
    }
    verifiedPolicy = Object.freeze(value);
    return verifiedPolicy;
  }

  async function policy() {
    return verifiedPolicy || loadPolicy();
  }

  function validId(value) {
    if (typeof value !== 'string' || !ID.test(value)) {
      throw new TypeError('Invalid preview identifier');
    }
    return value;
  }

  async function queuePreview(caseId, objectId) {
    await policy(); // require live backend security policy first
    const path = '/api/confidential/preview/' +
      encodeURIComponent(validId(caseId)) + '/' +
      encodeURIComponent(validId(objectId)) + '?mode=auto';
    const response = await fetch(path, {
      method: 'POST', credentials: 'same-origin', cache: 'no-store',
      headers: {Accept: 'application/json'}
      // No body. No submit, sign, or approval parameters.
    });
    if (!response.ok) throw new Error('AUTO preview was not queued');
    const result = await response.json();
    if (!result || result.queued !== true || result.mode !== 'auto' ||
        result.can_submit !== false || !ID.test(result.job_id || '')) {
      throw new Error('Invalid preview response');
    }
    return result;
  }

  async function jobStatus(jobId) {
    await policy();
    const response = await fetch(
      '/api/confidential/jobs/' + encodeURIComponent(validId(jobId)), {
        credentials: 'same-origin', cache: 'no-store',
        headers: {Accept: 'application/json'}
      }
    );
    if (!response.ok) throw new Error('Cannot read AUTO preview status');
    const result = await response.json();
    if (!result || result.job_id !== jobId ||
        !['queued', 'queue_uncertain', 'running', 'retryable',
          'preview_completed', 'needs_review'].includes(result.status) ||
        result.submitted === true || result.can_submit === true) {
      throw new Error('Unsafe AUTO preview status');
    }
    return result;
  }

  function showPolicy() {
    const parent = document.querySelector('aside');
    if (!parent || document.getElementById('notarai-confidential-auto')) return;
    const section = document.createElement('section');
    section.id = 'notarai-confidential-auto';
    section.setAttribute('aria-label', 'Tryb automatyczny NotarAI');
    const heading = document.createElement('strong');
    heading.textContent = 'AUTO · przygotowanie';
    const info = document.createElement('small');
    info.textContent = 'Analiza i podgląd automatycznie. Podpis i wysłanie zablokowane.';
    section.append(heading, info);
    const logo = parent.querySelector('.logo');
    if (logo) logo.after(section); else parent.prepend(section);
  }

  async function refreshPolicy() {
    try {
      await loadPolicy();
      showPolicy();
    } catch (_) {
      // Normal for production and for users without access to pilot.
      // Never display a false 'AUTO enabled' indicator.
      verifiedPolicy = null;
      const old = document.getElementById('notarai-confidential-auto');
      if (old) old.remove();
    }
  }

  window.NotarAIConfidentialAuto = Object.freeze({
    policy, queuePreview, jobStatus, refreshPolicy
  });
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', refreshPolicy, {once: true});
  } else {
    refreshPolicy();
  }
})();
