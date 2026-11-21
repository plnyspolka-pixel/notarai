/* Read-only AUTO Control Room for authenticated notaries and office owners.
 * Displays synthetic pilot job metadata only, never a document or action.
 * No submit/retry/approve endpoint, no localStorage, no background polling.
 */
(function () {
  'use strict';
  const ALLOWED = Object.freeze([
    'queued', 'running', 'retryable',
    'preview_completed', 'needs_review', 'queue_uncertain'
  ]);
  const NAMES = Object.freeze({
    queued: 'W kolejce',
    running: 'Przygotowywanie',
    retryable: 'Ponowienie podglądu',
    preview_completed: 'Podgląd gotowy',
    needs_review: 'Wymaga sprawdzenia',
    queue_uncertain: 'Niepotwierdzona kolejka'
  });
  const REASONS = Object.freeze({
    needs_review: 'Wymaga interwencji',
    queue_uncertain: 'Niepewny stan kolejki',
    expired_lease: 'Upłynął czas zadania',
    long_wait: 'Długi czas oczekiwania'
  });
  const ID = /^[A-Za-z0-9_-]{1,80}$/;
  const blockId = 'notarai-confidential-ops';
  let pending = false;

  async function fetchJobs() {
    const response = await fetch('/api/confidential/control/jobs?limit=10', {
      method: 'GET', credentials: 'same-origin', cache: 'no-store',
      headers: {Accept: 'application/json'}
    });
    if (!response.ok) {
      const error = new Error('AUTO control room unavailable');
      error.status = response.status;
      throw error;
    }
    const result = await response.json();
    if (!result || result.version !== 1 || result.mode !== 'auto' ||
        result.can_submit !== false || result.thinking_enabled !== false ||
        result.read_only !== true || !Array.isArray(result.jobs) ||
        result.jobs.length > 10 || !Number.isSafeInteger(result.attention_on_page) ||
        result.attention_on_page < 0 || result.attention_on_page > result.jobs.length ||
        typeof result.more_available !== 'boolean') {
      throw new Error('Unsafe AUTO control room response');
    }
    for (const job of result.jobs) {
      if (!job || !ID.test(job.job_id || '') || !ALLOWED.includes(job.status) ||
          job.submitted !== false || typeof job.attention_required !== 'boolean' ||
          !Number.isInteger(job.attempts) || job.attempts < 0 ||
          job.attempts > 3 || !Number.isSafeInteger(job.created_at) ||
          ![null, 'needs_review', 'queue_uncertain', 'expired_lease', 'long_wait']
            .includes(job.attention_reason)) {
        throw new Error('Untrusted control room job');
      }
    }
    return result;
  }

  function line(parent, text, className) {
    const element = document.createElement('span');
    if (className) element.className = className;
    element.textContent = text;
    parent.appendChild(element);
    return element;
  }

  function render(data) {
    const parent = document.querySelector('aside');
    if (!parent) return;
    let section = document.getElementById(blockId);
    if (!section) {
      section = document.createElement('section');
      section.id = blockId;
      section.setAttribute('aria-label', 'Zadania AUTO — tylko odczyt');
      const autoBadge = document.getElementById('notarai-confidential-auto');
      if (autoBadge) autoBadge.after(section); else parent.prepend(section);
    }
    // Trusted static DOM, no innerHTML or API data in attributes.
    section.replaceChildren();
    const head = document.createElement('div');
    head.className = 'ntr-ops-head';
    line(head, 'Praca AUTO', 'ntr-ops-heading');
    const refresh = document.createElement('button');
    refresh.type = 'button';
    refresh.textContent = 'Odśwież';
    refresh.setAttribute('aria-label', 'Odśwież stan zadań AUTO');
    refresh.addEventListener('click', () => { void refreshPanel(); });
    head.appendChild(refresh);
    section.appendChild(head);

    const count = data.attention_on_page;
    line(
      section,
      count
        ? String(count) + ' zadań do sprawdzenia (ostatnia strona)'
        : 'Brak zadań wymagających uwagi na tej stronie',
      'ntr-ops-summary'
    );
    const items = document.createElement('ul');
    items.className = 'ntr-ops-list';
    data.jobs.forEach(job => {
      const item = document.createElement('li');
      item.className = job.attention_required ? 'ntr-ops-attention' : '';
      const suffix = job.job_id.slice(-8);
      line(item, 'Zadanie …' + suffix, 'ntr-ops-id');
      line(item, NAMES[job.status], 'ntr-ops-state');
      if (job.attention_required) {
        line(item, REASONS[job.attention_reason] || 'Sprawdź stan zadania',
          'ntr-ops-warning');
      }
      items.appendChild(item);
    });
    section.appendChild(items);
    if (data.more_available) {
      line(section, 'Pokazano tylko najnowsze 10 zadań', 'ntr-ops-footnote');
    }
    line(section, 'AUTO nigdy nie podpisuje ani nie wysyła wniosków.',
      'ntr-ops-footnote');
  }

  async function refreshPanel() {
    if (pending) return;
    pending = true;
    try {
      const data = await fetchJobs();
      render(data);
    } catch (error) {
      // 403 means employee has no authority to inspect notarial workload;
      // 404/503 may mean the pilot is OFF or absent.
      const visible = document.getElementById(blockId);
      if (visible) visible.remove();
    } finally {
      pending = false;
    }
  }

  window.NotarAIConfidentialControlRoom = Object.freeze({
    fetchJobs, refresh: refreshPanel
  });
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', refreshPanel, {once: true});
  } else {
    void refreshPanel();
  }
})();
