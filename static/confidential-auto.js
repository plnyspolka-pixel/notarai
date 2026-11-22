/* NotarAI Confidential Browser: opt-in AUTO preview client.
 * Does not submit or sign anything. It is visible only when the authenticated
 * backend explicitly exposes the confidential pilot for this tenant.
 */
(function () {
  'use strict';
  const ID = /^[A-Za-z0-9_-]{1,80}$/;
  const POLICY_KEYS = [
    'version', 'mode', 'thinking_enabled', 'can_submit', 'can_sign',
    'external_writes_enabled', 'requires_human_for_external_effect',
    'automatic_stages', 'blocked_stages', 'ai_inference'
  ];
  const AI_KEYS = [
    'confidential_llm_enabled', 'external_bedrock_allowed',
    'zk_status', 'strict_zero_knowledge_verified'
  ];
  const QUEUE_KEYS = [
    'queued', 'job_id', 'mode', 'operation', 'thinking_enabled', 'can_submit'
  ];
  const STATUS_KEYS = [
    'job_id', 'status', 'attempts', 'submitted', 'mode', 'can_submit'
  ];
  const AUTO_STAGES = [
    'read_encrypted_input_in_nitro', 'validate_document', 'prepare_form',
    'fill_form', 'preview_result'
  ];
  const BLOCKED_STAGES = [
    'submit_form', 'sign_document', 'send_application',
    'make_binding_declaration'
  ];
  let verifiedPolicy = null;

  function exactKeys(value, keys) {
    return value !== null && typeof value === 'object' &&
      !Array.isArray(value) &&
      Object.keys(value).length === keys.length &&
      keys.every((key) => Object.prototype.hasOwnProperty.call(value, key));
  }

  function exactStages(value, stages) {
    return Array.isArray(value) && value.length === stages.length &&
      stages.every((name, index) => value[index] === name);
  }

  async function loadPolicy() {
    const response = await fetch('/api/confidential/policy', {
      credentials: 'same-origin', cache: 'no-store',
      headers: {Accept: 'application/json'}
    });
    if (!response.ok) throw new Error('Confidential AUTO unavailable');
    const value = await response.json();
    if (!exactKeys(value, POLICY_KEYS) ||
        value.version !== 1 || value.mode !== 'auto' ||
        value.can_submit !== false || value.can_sign !== false ||
        value.external_writes_enabled !== false ||
        value.thinking_enabled !== false ||
        value.requires_human_for_external_effect !== true ||
        !exactStages(value.automatic_stages, AUTO_STAGES) ||
        !exactStages(value.blocked_stages, BLOCKED_STAGES) ||
        !exactKeys(value.ai_inference, AI_KEYS) ||
        value.ai_inference.confidential_llm_enabled !== false ||
        value.ai_inference.external_bedrock_allowed !== false ||
        value.ai_inference.zk_status !== 'BLOCKED' ||
        value.ai_inference.strict_zero_knowledge_verified !== false) {
      verifiedPolicy = null;
      throw new Error('Unsafe confidential policy');
    }
    Object.freeze(value.ai_inference);
    Object.freeze(value.automatic_stages);
    Object.freeze(value.blocked_stages);
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
    await loadPolicy(); // re-check policy before every action; never trust stale state
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
    if (!exactKeys(result, QUEUE_KEYS) ||
        result.queued !== true || result.mode !== 'auto' ||
        result.operation !== 'preview-only' ||
        result.thinking_enabled !== false || result.can_submit !== false ||
        typeof result.job_id !== 'string' || !ID.test(result.job_id)) {
      throw new Error('Invalid preview response');
    }
    return result;
  }

  async function jobStatus(jobId) {
    await loadPolicy(); // also fail closed if access was revoked since enqueue
    const response = await fetch(
      '/api/confidential/jobs/' + encodeURIComponent(validId(jobId)), {
        credentials: 'same-origin', cache: 'no-store',
        headers: {Accept: 'application/json'}
      }
    );
    if (!response.ok) throw new Error('Cannot read AUTO preview status');
    const result = await response.json();
    if (!exactKeys(result, STATUS_KEYS) || result.job_id !== jobId ||
        !['queued', 'queue_uncertain', 'running', 'retryable',
          'preview_completed', 'needs_review'].includes(result.status) ||
        result.submitted !== false || result.can_submit !== false ||
        result.mode !== 'auto' ||
        !Number.isInteger(result.attempts) ||
        result.attempts < 0 || result.attempts > 3) {
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
    info.textContent = 'Pilot: syntetyczny podgląd formularza. AI, podpis i wysyłanie wyłączone.';
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
