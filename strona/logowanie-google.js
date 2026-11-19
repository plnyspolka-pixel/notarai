/* Podpowiedź logowania kontem Google na notarai.pl (Google One Tap,
 * pasek "Kontynuuj jako...").
 *
 * Ładowana WYŁĄCZNIE po zgodzie odwiedzającego w banerze cookies (ta sama
 * decyzja co analityka: klucz "notarai-zgoda-cookies"), bo skrypt Google
 * kontaktuje przeglądarkę z Google i zapisuje plik cookie g_state.
 *
 * Identyfikator klienta OAuth podaje aplikacja (app.notarai.pl), więc pasek
 * znika sam, gdy logowanie przez Google jest tam wyłączone. Kliknięcie wysyła
 * token formularzem do aplikacji: ona go sprawdza, loguje istniejące konto
 * albo zakłada nowe i otwiera się już zalogowana. Tokenu nie ma w adresie.
 * Nikogo nie logujemy bez kliknięcia.
 */
(function () {
  "use strict";
  var APLIKACJA = "https://app.notarai.pl";
  var ZGODA = "notarai-zgoda-cookies";
  var ruszylo = false;

  function jestZgoda() {
    try { return localStorage.getItem(ZGODA) === "tak"; } catch (e) { return false; }
  }

  function wyslij(odp) {
    if (!odp || !odp.credential) return;
    var f = document.createElement("form");
    f.method = "POST";
    f.action = APLIKACJA + "/api/logowanie/google/powrot";
    f.hidden = true;
    var pole = document.createElement("input");
    pole.type = "hidden";
    pole.name = "credential";
    pole.value = odp.credential;
    f.appendChild(pole);
    document.body.appendChild(f);
    f.submit();
  }

  function start() {
    if (ruszylo || !jestZgoda() || !window.fetch) return;
    ruszylo = true;
    fetch(APLIKACJA + "/api/logowanie/google")
      .then(function (o) { return o.json(); })
      .then(function (info) {
        if (!info || !info.wlaczone || !info.klient) return;
        var s = document.createElement("script");
        s.async = true;
        s.src = "https://accounts.google.com/gsi/client?hl=pl";
        s.onload = function () {
          var g = window.google && window.google.accounts && window.google.accounts.id;
          if (!g) return;
          g.initialize({
            client_id: info.klient,
            callback: wyslij,
            context: "signup",
            auto_select: false,
            cancel_on_tap_outside: false,
            itp_support: true,
            use_fedcm_for_prompt: true
          });
          g.prompt();
        };
        document.head.appendChild(s);
      })
      .catch(function () { /* aplikacja niedostępna albo bloker: po prostu nie ma paska */ });
  }

  function gotowe() {
    start();
    // Zgoda wyrażona dopiero teraz, w banerze: pasek może się pokazać od razu.
    document.addEventListener("click", function (e) {
      if (e.target && e.target.closest && e.target.closest("#zgoda-cookies .zc-tak")) setTimeout(start, 0);
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", gotowe);
  else gotowe();
})();
