/* notarai.pl/bezpieczenstwo - skaner bezpieczenstwa kancelarii.
 * Strona stoi na notarai.pl (hosting statyczny) i wola API na app.notarai.pl.
 * Wszystkie teksty z odpowiedzi trafiaja na strone przez textContent. */
(function () {
  "use strict";
  var API = ["notarai.pl", "www.notarai.pl"].indexOf(location.hostname) >= 0 ? "https://app.notarai.pl" : "";
  var KROK_MS = 1400;
  var POZIOMY = { krytyczne: "Krytyczne", uwaga: "Do poprawy", info: "Warto wiedzieć", ok: "W porządku" };

  function $(id) { return document.getElementById(id); }
  function el(tag, klasa, tekst) {
    var e = document.createElement(tag);
    if (klasa) e.className = klasa;
    if (tekst != null) e.textContent = tekst;
    return e;
  }
  function poziomOceny(wynik) { return wynik >= 75 ? "dobry" : wynik >= 50 ? "sredni" : "zly"; }

  // --- konsola krokow ------------------------------------------------------
  var zegar = null;
  function krokiStart() {
    var kroki = document.querySelectorAll("#skan-kroki li");
    var i = 0;
    kroki.forEach(function (k) { k.className = ""; });
    function nastepny() {
      if (i > 0) kroki[i - 1].className = "zrobione";
      if (i < kroki.length) { kroki[i].className = "trwa"; i++; zegar = setTimeout(nastepny, KROK_MS); }
    }
    nastepny();
  }
  function krokiStop(sukces) {
    clearTimeout(zegar);
    document.querySelectorAll("#skan-kroki li").forEach(function (k) { k.className = sukces ? "zrobione" : ""; });
  }

  // --- raport --------------------------------------------------------------
  function ustalenieEl(u) {
    var li = el("li", "ustalenie");
    li.dataset.poziom = u.poziom;
    var h = el("h4");
    var etykieta = el("span", "etykieta-poziom", POZIOMY[u.poziom] || u.poziom);
    etykieta.dataset.poziom = u.poziom;
    h.appendChild(etykieta);
    h.appendChild(el("span", null, u.tytul));
    li.appendChild(h);
    if (u.opis) li.appendChild(el("p", null, u.opis));
    if (u.naprawa) {
      var d = el("details");
      d.appendChild(el("summary", null, "Jak naprawić"));
      d.appendChild(el("p", null, u.naprawa));
      if (u.poziom === "krytyczne") d.open = true;
      li.appendChild(d);
    }
    return li;
  }

  function fakt(dl, nazwa, wartosc) {
    if (wartosc == null || wartosc === "" || (Array.isArray(wartosc) && !wartosc.length)) return;
    dl.appendChild(el("dt", null, nazwa));
    var dd = el("dd");
    if (Array.isArray(wartosc)) {
      var ul = el("ul");
      wartosc.forEach(function (w) { ul.appendChild(el("li", null, w)); });
      dd.appendChild(ul);
    } else dd.textContent = wartosc;
    dl.appendChild(dd);
  }

  function pokazWycieki(w, email) {
    var box = $("wycieki");
    box.textContent = "";
    if (!email) return;
    box.className = "wycieki";
    box.appendChild(el("h4", null, "Wycieki adresu e-mail"));
    if (!w || !w.dostepne) {
      box.appendChild(el("p", null, "Automatyczne sprawdzenie jest chwilowo niedostępne. Sprawdź adres samodzielnie:"));
      var a = el("a", null, "haveibeenpwned.com");
      a.href = "https://haveibeenpwned.com/"; a.rel = "noopener"; a.target = "_blank";
      var p = el("p"); p.appendChild(a); box.appendChild(p);
      return;
    }
    if (w.blad) { box.appendChild(el("p", null, "Nie udało się sprawdzić adresu. Spróbuj później.")); return; }
    if (!w.liczba) { box.appendChild(el("p", null, "Adresu nie ma w znanych wyciekach. Włącz powiadomienia na haveibeenpwned.com.")); return; }
    box.appendChild(el("p", null, "Adres pojawił się w " + w.liczba + " wyciekach. Zmień hasła w tych serwisach i włącz logowanie dwuskładnikowe."));
    var ul = el("ul");
    w.wycieki.forEach(function (x) {
      ul.appendChild(el("li", null, x.nazwa + (x.data ? " (" + x.data.slice(0, 4) + ")" : "") +
        (x.dane && x.dane.length ? ": " + x.dane.join(", ") : "")));
    });
    box.appendChild(ul);
  }

  function pokazRaport(r, email) {
    var poziom = poziomOceny(r.wynik);
    $("raport-domena").textContent = r.domena;
    var ocena = $("raport-ocena");
    ocena.textContent = r.ocena; ocena.dataset.poziom = poziom;
    $("raport-werdykt").textContent = r.werdykt;
    var liczby = [];
    if (r.krytyczne) liczby.push(r.krytyczne + " krytyczne");
    if (r.do_poprawy) liczby.push(r.do_poprawy + " do poprawy");
    $("raport-liczby").textContent = liczby.length ? "Problemy: " + liczby.join(", ") + "." : "Nie znaleźliśmy problemów krytycznych.";

    var alarm = $("raport-alarm");
    alarm.textContent = "";
    var pierwszy = (r.ustalenia || []).filter(function (u) { return u.poziom === "krytyczne"; })[0];
    alarm.hidden = !pierwszy;
    if (pierwszy) {
      alarm.appendChild(el("strong", null, pierwszy.tytul));
      alarm.appendChild(document.createTextNode(pierwszy.opis || ""));
    }

    var wsk = $("wskaznik");
    wsk.dataset.poziom = poziom;
    wsk.setAttribute("aria-label", "Wynik " + r.wynik + " na 100, ocena " + r.ocena);
    var liczba = $("wynik-liczba");
    var cel = r.wynik, ruch = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    wsk.style.setProperty("--wynik", 0);
    requestAnimationFrame(function () { requestAnimationFrame(function () { wsk.style.setProperty("--wynik", cel); }); });
    if (ruch) {
      var t0 = performance.now();
      (function licz(t) {
        var p = Math.min(1, (t - t0) / 700);
        liczba.textContent = Math.round(cel * (1 - Math.pow(1 - p, 3)));
        if (p < 1) requestAnimationFrame(licz);
      })(t0);
    } else liczba.textContent = cel;

    var kat = $("raport-kategorie");
    kat.textContent = "";
    (r.kategorie || []).forEach(function (k) {
      if (k.procent == null) return;
      var d = el("div", "kategoria");
      d.dataset.poziom = poziomOceny(k.procent);
      d.appendChild(el("p", null, k.nazwa));
      var pasek = el("div", "pasek"); var i = el("i"); i.style.setProperty("--p", k.procent + "%");
      pasek.appendChild(i); d.appendChild(pasek);
      d.appendChild(el("strong", null, k.procent + "%"));
      kat.appendChild(d);
    });

    var lista = $("ustalenia");
    lista.textContent = "";
    var dobre = [];
    (r.ustalenia || []).forEach(function (u) {
      if (u.poziom === "ok") dobre.push(u); else lista.appendChild(ustalenieEl(u));
    });
    var stare = document.querySelector(".ustalenia-wiecej");
    if (stare) stare.remove();
    if (dobre.length) {
      var wiecej = el("details", "ustalenia-wiecej");
      wiecej.appendChild(el("summary", null, "W porządku (" + dobre.length + ")"));
      var ol = el("ol", "ustalenia");
      dobre.forEach(function (u) { ol.appendChild(ustalenieEl(u)); });
      wiecej.appendChild(ol);
      lista.after(wiecej);
    }

    var f = r.fakty || {};
    var dl = $("fakty");
    dl.textContent = "";
    fakt(dl, "Adres IP serwera", (f.ip || []).join(", "));
    fakt(dl, "Serwer", f.serwer);
    fakt(dl, "System strony", f.cms);
    if (f.certyfikat) fakt(dl, "Certyfikat", (f.certyfikat.wystawca || "") +
      (f.certyfikat.wazny_do ? ", ważny do " + f.certyfikat.wazny_do : "") +
      (f.certyfikat.wersja ? ", " + f.certyfikat.wersja.replace("v", " ") : ""));
    fakt(dl, "Serwery poczty", f.poczta);
    fakt(dl, "Usługi zewnętrzne na stronie", (f.zewnetrzne || []).map(function (z) { return z.nazwa; }));
    pokazWycieki(r.wycieki, email);

    var sekcja = $("raport");
    sekcja.hidden = false;
    sekcja.scrollIntoView({ behavior: ruch ? "smooth" : "auto", block: "start" });
    sekcja.focus({ preventScroll: true });
  }

  // --- formularz -----------------------------------------------------------
  function start() {
    var form = $("skaner");
    if (!form) return;
    var pole = $("adres"), przycisk = $("skan-przycisk"), status = $("skan-status");
    pole.addEventListener("input", function () {
      $("konsola-domena").textContent = pole.value.trim() || "kancelaria-kowalski.pl";
    });
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var adres = pole.value.trim();
      var email = $("email").value.trim();
      var zgoda = $("zgoda").checked;
      status.textContent = ""; status.classList.remove("blad");
      if (!adres) { status.classList.add("blad"); status.textContent = "Wpisz adres strony kancelarii."; pole.focus(); return; }
      if (email && !zgoda) { status.classList.add("blad"); status.textContent = "Zaznacz zgodę na sprawdzenie adresu e-mail albo usuń adres."; $("zgoda").focus(); return; }
      przycisk.disabled = true;
      przycisk.textContent = "Sprawdzam…";
      status.textContent = "Trwa sprawdzanie, to potrwa do 30 sekund.";
      document.querySelector(".skan-konsola").classList.add("aktywna");
      krokiStart();
      fetch(API + "/api/skan", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ adres: adres, email: email, zgoda_wycieki: zgoda })
      }).then(function (odp) {
        return odp.json().catch(function () { return {}; }).then(function (dane) {
          if (!odp.ok) throw new Error(typeof dane.detail === "string" ? dane.detail : "Nie udało się sprawdzić strony. Spróbuj ponownie.");
          return dane;
        });
      }).then(function (r) {
        krokiStop(true);
        status.textContent = "Gotowe: ocena " + r.ocena + ".";
        pokazRaport(r, email);
      }).catch(function (err) {
        krokiStop(false);
        status.classList.add("blad");
        status.textContent = err && err.message && err.message !== "Failed to fetch" ? err.message :
          "Brak połączenia ze skanerem. Spróbuj ponownie za chwilę.";
      }).then(function () {
        przycisk.disabled = false;
        przycisk.textContent = "Sprawdź";
      });
    });
    $("drukuj").addEventListener("click", function () { window.print(); });
    window.addEventListener("beforeprint", function () {
      document.querySelectorAll("#raport details").forEach(function (d) { d.open = true; });
    });
    $("jeszcze-raz").addEventListener("click", function (e) {
      e.preventDefault(); pole.focus(); pole.select();
      form.scrollIntoView({ block: "center" });
    });
  }

  // --- checklista (zaznaczenia tylko w tej przegladarce) --------------------
  function checklista() {
    var KLUCZ = "notarai-checklista-bezpieczenstwa";
    var pola = document.querySelectorAll("#checklista-lista input[type=checkbox]");
    var licznik = $("checklista-licznik");
    var stan = {};
    try { stan = JSON.parse(localStorage.getItem(KLUCZ) || "{}") || {}; } catch (e) { stan = {}; }
    function odswiez() {
      var n = 0;
      pola.forEach(function (p) { if (p.checked) n++; });
      licznik.textContent = n + " z " + pola.length;
    }
    pola.forEach(function (p) {
      p.checked = !!stan[p.dataset.id];
      p.addEventListener("change", function () {
        stan[p.dataset.id] = p.checked;
        try { localStorage.setItem(KLUCZ, JSON.stringify(stan)); } catch (e) { /* tryb prywatny */ }
        odswiez();
      });
    });
    odswiez();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function () { start(); checklista(); });
  else { start(); checklista(); }
})();
