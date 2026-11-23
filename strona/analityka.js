/* Analityka notarai.pl: PostHog (chmura UE, Frankfurt) - nagrania sesji,
 * mapy kliknięć (heatmapy) i statystyki odwiedzin.
 *
 * Ładowana WYŁĄCZNIE po zgodzie odwiedzającego na pliki cookie analityczne
 * (baner poniżej). Bez zgody nic nie trafia do PostHog i nic nie jest
 * zapisywane w przeglądarce poza samą decyzją o zgodzie.
 * Zgodę można zmienić linkiem do "#cookies" (np. w polityce prywatności).
 *
 * Klucz projektu jest publiczny z założenia (widać go w kodzie każdej strony
 * korzystającej z PostHog). Projekt wspólny z financeyou.pl - dane rozróżnia
 * domena ($host).
 */
(function () {
  "use strict";
  var KLUCZ = "phc_ytiYK9zqUQtz7tFij4nY6KJ6QMWMJ2JVp8bZoTEgMwFj";
  var HOST = "https://eu.i.posthog.com";
  var SKRYPT = "https://eu-assets.i.posthog.com/static/array.js";
  var ZGODA = "notarai-zgoda-cookies"; // "tak" | "nie"
  // Strony z danymi spraw i wizyt: heatmapy tak, nagrania sesji nigdy.
  // Skaner bezpieczenstwa: wpisywany e-mail i haslo - nagran sesji nigdy.
  var BEZ_NAGRAN = /^\/(przygotuj-sprawe|wizyta|lead|bezpieczenstwo)(\/|$)/;

  function odczytaj() {
    try { return localStorage.getItem(ZGODA); } catch (e) { return null; }
  }
  function zapisz(v) {
    try { localStorage.setItem(ZGODA, v); } catch (e) { /* tryb prywatny */ }
  }

  var wczytano = false;
  function uruchom() {
    if (wczytano) {
      if (window.posthog && window.posthog.opt_in_capturing) window.posthog.opt_in_capturing();
      return;
    }
    wczytano = true;
    var s = document.createElement("script");
    s.async = true;
    s.crossOrigin = "anonymous";
    s.src = SKRYPT;
    s.onload = function () {
      if (!window.posthog || !window.posthog.init) return;
      window.posthog.init(KLUCZ, {
        api_host: HOST,
        ui_host: "https://eu.posthog.com",
        person_profiles: "identified_only",
        capture_pageview: true,
        capture_pageleave: true,
        enable_heatmaps: true,
        capture_performance: { web_vitals: true },
        // Wszystkie pola formularzy zamaskowane w nagraniach (dane klientów).
        session_recording: { maskAllInputs: true },
        disable_session_recording: BEZ_NAGRAN.test(location.pathname)
      });
    };
    document.head.appendChild(s);
  }

  function wylacz() {
    if (window.posthog && window.posthog.opt_out_capturing) window.posthog.opt_out_capturing();
  }

  function baner() {
    if (document.getElementById("zgoda-cookies")) return;
    var css = document.createElement("style");
    css.textContent =
      "#zgoda-cookies{position:fixed;left:16px;right:16px;bottom:16px;z-index:9999;max-width:560px;margin:0 auto;" +
      "background:#fff;color:#071d49;border:1px solid #d8e5f6;border-radius:14px;padding:18px 20px;" +
      "box-shadow:0 12px 40px rgba(7,29,73,.18);font:15px/1.5 Montserrat,system-ui,sans-serif}" +
      "#zgoda-cookies p{margin:0 0 12px}#zgoda-cookies a{color:inherit}" +
      "#zgoda-cookies .zc-akcje{display:flex;gap:10px;flex-wrap:wrap}" +
      "#zgoda-cookies button{font:inherit;font-weight:600;border-radius:10px;padding:9px 16px;cursor:pointer;border:1px solid #071d49}" +
      "#zgoda-cookies .zc-tak{background:#071d49;color:#fff}#zgoda-cookies .zc-nie{background:#fff;color:#071d49}";
    var el = document.createElement("div");
    el.id = "zgoda-cookies";
    el.setAttribute("role", "dialog");
    el.setAttribute("aria-label", "Zgoda na pliki cookie");
    el.innerHTML =
      "<p>Za Twoją zgodą używamy plików cookie analitycznych (PostHog, serwery w UE), żeby widzieć, " +
      "jak korzystasz ze strony, i ją ulepszać. Wpisywane dane są ukryte. " +
      '<a href="/prywatnosc/">Polityka prywatności</a>.</p>' +
      '<div class="zc-akcje"><button type="button" class="zc-tak">Akceptuję</button>' +
      '<button type="button" class="zc-nie">Tylko niezbędne</button></div>';
    document.head.appendChild(css);
    document.body.appendChild(el);
    el.querySelector(".zc-tak").onclick = function () { zapisz("tak"); el.remove(); uruchom(); };
    el.querySelector(".zc-nie").onclick = function () { zapisz("nie"); el.remove(); wylacz(); };
  }

  function start() {
    var z = odczytaj();
    if (z === "tak") uruchom();
    else if (z !== "nie") baner();
    document.addEventListener("click", function (e) {
      var a = e.target && e.target.closest && e.target.closest('a[href$="#cookies"]');
      if (!a) return;
      e.preventDefault();
      baner();
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
