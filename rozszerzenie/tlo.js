/* Klikniecie ikony notarai otwiera panel boczny obok biezacej strony.

   Dodatkowo: gdy notariusz WLACZY "Ochrone przed phishingiem" w panelu (i
   zgodzi sie wtedy na dostep), tlo sprawdza LOKALNIE adres odwiedzanej strony
   i pobierane pliki, i ostrzega przed podrobkami. Nic nie wysylamy - cala
   ocena liczy sie na urzadzeniu (bezpieczna_strona.js). Funkcja jest wylaczona,
   dopoki notariusz jej sam nie wlaczy; instalacja zostaje waska. */
import { ocenStrone, ryzykoPobrania } from "./bezpieczna_strona.js";

const KLUCZ = "ochronaPhishing";

chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
  zastosujStan();
});
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});

async function wlaczona() {
  try { const o = await chrome.storage.local.get(KLUCZ); return !!o[KLUCZ]; } catch (_) { return false; }
}

/* Wstrzykiwane do kontekstu strony: czerwony baner na gorze. */
function banerOstrzezenia(teksty) {
  const stary = document.getElementById("notarai-ostrzezenie");
  if (stary) stary.remove();
  const el = document.createElement("div");
  el.id = "notarai-ostrzezenie";
  el.setAttribute("role", "alert");
  el.style.cssText = "position:fixed;inset:0 0 auto 0;z-index:2147483647;background:#b52e44;color:#fff;" +
    "font:600 14px/1.45 system-ui,'Segoe UI',Arial,sans-serif;padding:12px 16px;" +
    "box-shadow:0 2px 14px rgba(0,0,0,.35);display:flex;gap:12px;align-items:flex-start;";
  const t = document.createElement("div"); t.style.flex = "1";
  const b = document.createElement("b"); b.textContent = "notarai — uwaga: ";
  t.append(b, document.createTextNode(teksty.join("  ")));
  const x = document.createElement("button"); x.textContent = "Zamknij";
  x.style.cssText = "background:#fff;color:#b52e44;border:0;border-radius:6px;padding:6px 12px;font-weight:700;cursor:pointer;flex:0 0 auto;";
  x.addEventListener("click", () => el.remove());
  el.append(t, x);
  (document.body || document.documentElement).appendChild(el);
}

function powiadom(tytul, tresc) {
  try { if (chrome.notifications) chrome.notifications.create({ type: "basic", iconUrl: "ikony/128.png", title: tytul, message: tresc }); } catch (_) {}
}

async function sprawdzStrone(tabId, url) {
  if (!url || !/^https?:/i.test(url)) return;
  const ostrz = ocenStrone(url);
  try {
    await chrome.action.setBadgeBackgroundColor({ color: "#b52e44" });
    await chrome.action.setBadgeText({ tabId, text: ostrz.length ? "!" : "" });
  } catch (_) {}
  if (!ostrz.length) return;
  try {
    await chrome.scripting.executeScript({ target: { tabId }, func: banerOstrzezenia, args: [ostrz.map(o => o.tekst)] });
  } catch (_) {
    powiadom("notarai — uwaga", ostrz[0].tekst);  // brak dostepu do tej strony
  }
}

function naNawigacji(d) { if (d && d.frameId === 0) sprawdzStrone(d.tabId, d.url); }
function naPobraniu(item) {
  const r = ryzykoPobrania((item && (item.filename || item.url)) || "");
  if (r) powiadom("notarai — ryzykowne pobranie", r.tekst);
}

async function zastosujStan() {
  const on = await wlaczona();
  try { if (chrome.webNavigation) chrome.webNavigation.onCommitted.removeListener(naNawigacji); } catch (_) {}
  try { if (chrome.downloads) chrome.downloads.onCreated.removeListener(naPobraniu); } catch (_) {}
  if (!on) return;
  try { if (chrome.webNavigation) chrome.webNavigation.onCommitted.addListener(naNawigacji); } catch (_) {}
  try { if (chrome.downloads) chrome.downloads.onCreated.addListener(naPobraniu); } catch (_) {}
}

if (chrome.runtime.onStartup) chrome.runtime.onStartup.addListener(zastosujStan);
chrome.storage.onChanged.addListener((zm, obszar) => { if (obszar === "local" && KLUCZ in zm) zastosujStan(); });
zastosujStan();
