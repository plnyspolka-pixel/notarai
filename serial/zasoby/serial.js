/* Pomiar serialu na notarai.pl. Zdarzenia trafiają do PostHog WYŁĄCZNIE
 * wtedy, gdy analityka.js wczytała PostHog, czyli po zgodzie na cookie
 * analityczne. Bez zgody ten skrypt niczego nie wysyła i niczego nie zapisuje.
 * Opis zdarzeń: docs/serial-pomiar.md */
(function () {
  "use strict";
  function wyslij(nazwa, cechy) {
    var ph = window.posthog;
    if (!ph || typeof ph.capture !== "function") return;
    if (typeof ph.has_opted_out_capturing === "function" && ph.has_opted_out_capturing()) return;
    ph.capture(nazwa, cechy || {});
  }
  var wideo = document.getElementById("wideo");
  var odcinek = wideo ? wideo.getAttribute("data-odcinek") : null;
  var parametry = new URLSearchParams(location.search);
  var baza = { odcinek: odcinek, zrodlo: parametry.get("utm_source") || null };

  // Otwarcie strony odcinka; powrót na kolejny odcinek liczy się z sekwencji tych zdarzeń.
  window.addEventListener("load", function () {
    setTimeout(function () { if (odcinek) wyslij("serial_odcinek_otwarty", baza); }, 1500);
  });

  if (wideo) {
    var progi = [3, 10];
    var procenty = [25, 50, 75, 100];
    var wyslane = {};
    function raz(klucz, nazwa, cechy) {
      if (wyslane[klucz]) return;
      wyslane[klucz] = true;
      wyslij(nazwa, Object.assign({}, baza, cechy || {}));
    }
    wideo.addEventListener("play", function () { raz("play", "serial_odtworzenie"); });
    wideo.addEventListener("timeupdate", function () {
      var t = wideo.currentTime;
      var d = wideo.duration;
      progi.forEach(function (s) { if (t >= s) raz("s" + s, "serial_obejrzane_" + s + "s"); });
      if (d && isFinite(d)) {
        procenty.forEach(function (p) {
          if (t / d >= (p === 100 ? 0.98 : p / 100)) raz("p" + p, "serial_obejrzane_procent", { procent: p });
        });
      }
    });
    wideo.addEventListener("ended", function () { raz("p100", "serial_obejrzane_procent", { procent: 100 }); });
  }

  document.addEventListener("click", function (e) {
    var a = e.target.closest ? e.target.closest("[data-zdarzenie]") : null;
    if (!a) return;
    wyslij(a.getAttribute("data-zdarzenie"), Object.assign({}, baza, { do_odcinka: a.getAttribute("data-odcinek") }));
  });
})();
