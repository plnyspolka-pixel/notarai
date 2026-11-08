/* Customer workflow shortcuts in the authenticated notary dashboard.
 * The existing backend remains authoritative. No customer records are cached.
 */
(function () {
  "use strict";
  const el = id => document.getElementById(id);
  const leads = el("kokpit-open-leads");
  const calendar = el("kokpit-open-calendar");
  const counter = el("kokpit-lead-count");
  const inbox = el("btn-zapytania");

  if (!leads || !calendar || !counter || !inbox) return;

  function setCount(text) { counter.textContent = text; }

  async function refresh() {
    if (inbox.hidden || document.getElementById("brama")?.hidden === false) {
      setCount("Zaloguj się i zaakceptuj dokumenty, aby zobaczyć zapytania.");
      return;
    }
    try {
      // api() already attaches the correct JWT and enforces the current tenant.
      const response = await api("/api/zapytania");
      if (!response.ok) {
        setCount("Zapytania są niedostępne. Sprawdź uprawnienia.");
        return;
      }
      const items = await response.json();
      if (!Array.isArray(items)) {
        setCount("Nie udało się pobrać liczby zapytań.");
        return;
      }
      const n = items.filter(item => item.status === "nowa").length;
      const ending = n === 1 ? "nowe zapytanie" :
        (n % 10 >= 2 && n % 10 <= 4 && !(n % 100 >= 12 && n % 100 <= 14)
          ? "nowe zapytania" : "nowych zapytań");
      setCount(n ? n + " " + ending + " do obsłużenia" : "Brak nowych zapytań");
    } catch {
      setCount("Nie udało się pobrać zapytań — spróbuj ponownie.");
    }
  }

  leads.addEventListener("click", () => {
    if (inbox.hidden) {
      setCount("Brak dostępu do zapytań na tym koncie.");
      return;
    }
    inbox.click(); // Original dialog, status updates and calendar scheduling.
    refresh();
  });
  calendar.addEventListener("click", () => {
    const step = document.querySelector('.krok[data-etap="6"]');
    if (!step || step.hidden) {
      setCount("Kalendarz jest niedostępny w trybie plików na komputerze.");
      return;
    }
    pokaz(6);
  });
  // Re-fetch only when the user actually sees the dashboard or closes the inbox.
  el("btn-kokpit")?.addEventListener("click", () => { void refresh(); });
  el("btn-zamknij-zapytania")?.addEventListener("click", () => { void refresh(); });
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && el("kokpit")?.hidden === false) void refresh();
  });
  // Dashboard is shown during the original application's async initialization.
  // A short interval only watches DOM state; no polling of client records.
  const observer = new MutationObserver(() => {
    if (el("kokpit")?.hidden === false && inbox.hidden === false) {
      void refresh();
      observer.disconnect();
    }
  });
  observer.observe(inbox, {attributes:true,attributeFilter:["hidden"]});
  if (inbox.hidden === false) void refresh();
})();
