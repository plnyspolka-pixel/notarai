/* Styl i zasady kancelarii (etap 9), raport zgodnosci nad projektem (etap 3)
   i pasek nad zaznaczeniem w projekcie.

   Korzysta z funkcji globalnych index.html: $, api, escape, stan, pokaz, odm.
   Notariusz niczego nie klasyfikuje: pisze zdanie, serwer odpowiada
   "Tak to rozumiem", a zasada trafia do wlasciwej grupy sama. */
(function () {
  "use strict";
  let dane = null;                 // ostatni stan z GET /api/personalizacja
  let czescWidoczna = null;        // filtr sformulowan
  let pokazWszystkie = false;
  let wszystkieSugestie = false;
  let podglad = null;              // interpretacja wpisywanej zasady
  let nadpisania = {};             // poziom / zakres zmienione przez notariusza
  let czekam = null;

  const POLA = {
    OSOBA: "osoba", PESEL: "PESEL", DOWOD: "dowód", DATA: "data", KWOTA: "kwota",
    KWOTA_SLOWNIE: "kwota słownie", MIEJSCE: "miejscowość", ADRES: "adres", KOD_MIEJSCOWOSC: "kod i poczta",
    KW: "nr KW", NR: "numer", POW: "powierzchnia", REP: "repertorium", IMIONA_RODZICOW: "imiona rodziców",
    N: "liczba", EMAIL: "e-mail", TELEFON: "telefon",
  };

  async function json(adres, opcje = {}) {
    const odp = await api(adres, opcje);
    const w = await odp.json();
    if (!odp.ok) throw new Error(w.detail || "Serwer odpowiedział " + odp.status);
    return w;
  }
  const wyslij = (adres, metoda, tresc) => json(adres, {
    method: metoda, headers: {"Content-Type": "application/json"},
    body: tresc === undefined ? undefined : JSON.stringify(tresc),
  });
  const obszar = (k) => (dane?.kategorie?.obszary || {})[k] || {nazwa: "Inne wytyczne", ikona: "•"};
  const bezCudzyslowow = (t) => t.replace(/[„”"“«»]/g, "").replace(/\s+/g, " ").trim();

  /* ---------- wczytanie i liczby ---------- */
  async function rysuj() {
    try {
      dane = await json("/api/personalizacja");
    } catch (e) {
      $("pz-lista").innerHTML = '<span class="stan blad">' + escape(e.message) + "</span>";
      return;
    }
    const l = dane.liczby;
    $("pz-liczby").innerHTML = [
      [l.wlaczonych, odm(l.wlaczonych, "zasada pilnowana", "zasady pilnowane", "zasad pilnowanych")],
      [l.naprawianych, "poprawiam sam, bez Ciebie"],
      [dane.styl.aktow, odm(dane.styl.aktow, "akt w nauce stylu", "akty w nauce stylu", "aktów w nauce stylu")],
    ].map(([n, t]) => `<div class="pz-liczba"><b>${n}</b><span>${escape(t)}</span></div>`).join("");
    const licznik = $("licznik-zasad");
    if (licznik) { licznik.hidden = !dane.sugestie.length; licznik.textContent = dane.sugestie.length || ""; }
    $("pz-tekst").disabled = !dane.moge_zmieniac;
    if (!dane.moge_zmieniac) $("pz-tekst").placeholder = "Zasady zmienia notariusz - właściciel kancelarii. Możesz je przeglądać.";
    rysujPrzyklady(); rysujSugestie(); rysujZasady(); rysujWbudowane(); rysujStyl(); rysujSformulowania();
  }

  function rysujPrzyklady() {
    const k = $("pz-przyklady");
    if (!dane.moge_zmieniac) { k.innerHTML = ""; return; }
    k.innerHTML = "Na przykład: " + dane.przyklady.slice(0, 5).map((p, i) =>
      `<button class="chip" data-i="${i}" type="button">${escape(p)}</button>`).join("");
    k.querySelectorAll("button").forEach(b => b.onclick = () => {
      $("pz-tekst").value = dane.przyklady[+b.dataset.i];
      $("pz-tekst").focus(); interpretujZaChwile(0);
    });
  }

  /* ---------- nowa zasada: podglad "Tak to rozumiem" ---------- */
  function interpretujZaChwile(ms = 350) {
    clearTimeout(czekam);
    const tekst = $("pz-tekst").value.trim();
    $("pz-dodaj").disabled = !tekst;
    if (!tekst) { podglad = null; $("pz-podglad").hidden = true; return; }
    czekam = setTimeout(async () => {
      try {
        const z = await wyslij("/api/personalizacja/zasady/interpretuj", "POST", {tekst});
        if ($("pz-tekst").value.trim() !== tekst) return;
        podglad = z; nadpisania = {};
        rysujPodglad();
      } catch (e) {
        $("pz-podglad").hidden = false;
        $("pz-podglad").innerHTML = '<span class="stan blad">' + escape(e.message) + "</span>";
      }
    }, ms);
  }

  function rysujPodglad() {
    const z = podglad, el = $("pz-podglad");
    const poziom = nadpisania.poziom || z.poziom;
    const rodzaje = dane.kategorie.rodzaje;
    const wybrany = (nadpisania.zakres || z.zakres).rodzaje;
    const opcje = ['<option value="">każdy dokument</option>']
      .concat(wybrany.length > 1 ? [`<option value="__auto" selected>${escape(wybrany.map(r => rodzaje[r]).join(", "))}</option>`] : [])
      .concat(Object.entries(rodzaje).filter(([k]) => k !== "inny").map(([k, n]) =>
        `<option value="${k}"${wybrany.length === 1 && wybrany[0] === k ? " selected" : ""}>${escape(n)}</option>`));
    el.hidden = false;
    el.innerHTML = `<div class="pz-rozumiem">Tak to rozumiem · ${escape(obszar(z.obszar).nazwa)}</div>
      <div class="pz-opis-glowny">${escape(z.opis.split(" · ")[0])}</div>
      <div class="pz-ustawienia">
        <span class="przelacznik" role="radiogroup" aria-label="Siła zasady">
          <input type="radio" name="pz-poziom" id="pz-p-b" value="blokuje"${poziom === "blokuje" ? " checked" : ""}><label for="pz-p-b">Nieprzekraczalna</label>
          <input type="radio" name="pz-poziom" id="pz-p-o" value="ostrzega"${poziom === "ostrzega" ? " checked" : ""}><label for="pz-p-o">Tylko ostrzegaj</label>
        </span>
        <label style="font-size:12.5px;color:var(--tekst2)">Dotyczy: <select id="pz-zakres">${opcje.join("")}</select></label>
        ${z.sprawdzanie === "ai" ? '<span class="pz-znaczek">sprawdza AI</span>' : z.naprawa ? '<span class="pz-znaczek sam">poprawiam sam</span>' : '<span class="pz-znaczek">sprawdzam automatycznie</span>'}
      </div>`;
    el.querySelectorAll('input[name="pz-poziom"]').forEach(r => r.onchange = () => { nadpisania.poziom = r.value; });
    $("pz-zakres").onchange = (e) => {
      const v = e.target.value;
      if (v === "__auto") delete nadpisania.zakres;
      else nadpisania.zakres = {rodzaje: v ? [v] : [], czesci: z.zakres.czesci};
    };
  }

  async function dodajZasade() {
    const tekst = $("pz-tekst").value.trim();
    if (!tekst) return;
    $("pz-dodaj").disabled = true;
    stan($("pz-stan"), "Zapisuję zasadę…", false, true);
    try {
      const w = await wyslij("/api/personalizacja/zasady", "POST", {tekst, ...nadpisania});
      $("pz-tekst").value = ""; podglad = null; $("pz-podglad").hidden = true;
      stan($("pz-stan"), w.juz_byla ? "Taka zasada już jest - nic nie zmieniłem."
        : w.zastapiona ? "Dodane. Zastępuje wcześniejszą: „" + w.zastapiona.tekst + "”."
        : "Dodane. Pilnuję tego od następnego projektu.");
      await rysuj();
      podswietlZasade(w.zasada.id);
    } catch (e) {
      stan($("pz-stan"), e.message, true);
    } finally {
      $("pz-dodaj").disabled = !$("pz-tekst").value.trim();
    }
  }
  function podswietlZasade(id) {
    const el = document.querySelector(`.pz-zasada[data-id="${id}"]`);
    if (!el) return;
    el.scrollIntoView({block: "nearest", behavior: "smooth"});
    el.animate([{boxShadow: "0 0 0 3px var(--akcent)"}, {boxShadow: "0 0 0 0 transparent"}], {duration: 1400});
  }

  /* ---------- sugestie z aktow ---------- */
  function rysujSugestie() {
    const k = $("pz-sugestie");
    if (!dane.sugestie.length) { k.innerHTML = ""; return; }
    const widoczne = wszystkieSugestie ? dane.sugestie : dane.sugestie.slice(0, 3);
    const reszta = dane.sugestie.length - widoczne.length;
    k.innerHTML = `<div class="pz-sugestie"><h3>Zauważyłem w Twoich aktach</h3>${widoczne.map((s, i) => `
      <div class="pz-sugestia"><div><div class="pz-tekst">${escape(s.tekst)}</div><small>${escape(s.uzasadnienie)}</small></div>
      <div class="pz-przyciski">${dane.moge_zmieniac ? `<button data-przyjmij="${i}">Pilnuj tego</button>` : ""}
      <button class="wtorny" data-odrzuc="${i}" title="Nie proponuj tego więcej">Pomiń</button></div></div>`).join("")}
      ${reszta ? `<button class="pz-wiecej" id="pz-wiecej-sugestii">Pokaż jeszcze ${reszta} ${odm(reszta, "podpowiedź", "podpowiedzi", "podpowiedzi")}</button>` : ""}</div>`;
    $("pz-wiecej-sugestii") && ($("pz-wiecej-sugestii").onclick = () => { wszystkieSugestie = true; rysujSugestie(); });
    k.querySelectorAll("[data-przyjmij]").forEach(b => b.onclick = async () => {
      const s = dane.sugestie[+b.dataset.przyjmij];
      b.disabled = true;
      try {
        const w = await wyslij("/api/personalizacja/sugestie/" + encodeURIComponent(s.klucz) + "/przyjmij", "POST");
        await rysuj(); podswietlZasade(w.zasada.id);
      } catch (e) { stan($("pz-stan"), e.message, true); b.disabled = false; }
    });
    k.querySelectorAll("[data-odrzuc]").forEach(b => b.onclick = async () => {
      const s = dane.sugestie[+b.dataset.odrzuc];
      try { await wyslij("/api/personalizacja/sugestie/" + encodeURIComponent(s.klucz) + "/odrzuc", "POST"); await rysuj(); }
      catch (e) { stan($("pz-stan"), e.message, true); }
    });
  }

  /* ---------- lista zasad, pogrupowana po obszarach ---------- */
  function rysujZasady() {
    const k = $("pz-lista");
    if (!dane.zasady.length) {
      k.innerHTML = '<div class="pz-pusto">Nie ma jeszcze zasad kancelarii. Napisz pierwszą powyżej albo wrzuć swoje akty niżej - podpowiem, czego pilnujesz na co dzień.</div>';
      return;
    }
    const grupy = {};
    dane.zasady.forEach(z => (grupy[z.obszar] = grupy[z.obszar] || []).push(z));
    const kolejnosc = Object.keys(dane.kategorie.obszary);
    k.innerHTML = Object.keys(grupy).sort((a, b) => kolejnosc.indexOf(a) - kolejnosc.indexOf(b)).map(o => {
      const ob = obszar(o);
      return `<div class="pz-grupa"><span class="pz-ikona">${escape(ob.ikona)}</span>${escape(ob.nazwa)}</div>` +
        grupy[o].map(z => {
          const [, zakres] = z.opis.split(" · ");
          const znaczki = [
            z.poziom === "blokuje" ? '<span class="pz-znaczek twardy">nieprzekraczalna</span>' : '<span class="pz-znaczek">wskazówka</span>',
            z.sprawdzanie === "ai" ? '<span class="pz-znaczek">sprawdza AI</span>' : z.naprawa ? '<span class="pz-znaczek sam">poprawiam sam</span>' : '<span class="pz-znaczek">sprawdzam automatycznie</span>',
            `<span class="pz-znaczek">${escape(zakres || "")}</span>`,
            z.zrodlo === "z_aktow" ? '<span class="pz-znaczek">z Twoich aktów</span>' : "",
          ].join("");
          return `<div class="pz-zasada${z.wlaczona ? "" : " wyl"}" data-id="${escape(z.id)}">
            <span class="pz-ikona">${escape(ob.ikona)}</span>
            <div class="pz-tresc"><div class="pz-tekst" title="${dane.moge_zmieniac ? "Kliknij, żeby zmienić" : ""}">${escape(z.tekst)}</div>
              <div class="pz-opis">${escape(z.opis.split(" · ")[0])}</div><div class="pz-znaczki">${znaczki}</div></div>
            <div class="pz-akcje">${dane.moge_zmieniac ? `
              <label class="pz-przel" title="${z.wlaczona ? "Wyłącz" : "Włącz"}"><input type="checkbox"${z.wlaczona ? " checked" : ""} aria-label="Zasada włączona"><span></span></label>
              <button class="wtorny" data-usun title="Usuń zasadę" aria-label="Usuń zasadę">×</button>` : ""}</div></div>`;
        }).join("");
    }).join("");
    if (!dane.moge_zmieniac) return;
    k.querySelectorAll(".pz-zasada").forEach(w => {
      const id = w.dataset.id;
      w.querySelector("input[type=checkbox]").onchange = async (e) => {
        try { await wyslij("/api/personalizacja/zasady/" + id, "PUT", {wlaczona: e.target.checked}); await rysuj(); }
        catch (b) { stan($("pz-stan"), b.message, true); }
      };
      w.querySelector("[data-usun]").onclick = async () => {
        const z = dane.zasady.find(x => x.id === id);
        if (!confirm("Usunąć zasadę „" + z.tekst + "”?")) return;
        try { await wyslij("/api/personalizacja/zasady/" + id, "DELETE"); await rysuj(); }
        catch (b) { stan($("pz-stan"), b.message, true); }
      };
      w.querySelector(".pz-tekst").onclick = () => edytuj(w, id);
    });
  }

  function edytuj(wiersz, id) {
    const z = dane.zasady.find(x => x.id === id), tekst = wiersz.querySelector(".pz-tekst");
    if (tekst.querySelector("input")) return;
    tekst.innerHTML = `<input class="pz-edycja" value="${escape(z.tekst)}" maxlength="600" aria-label="Treść zasady">`;
    const pole = tekst.querySelector("input");
    pole.focus(); pole.select();
    const zapisz = async () => {
      const nowy = pole.value.trim();
      if (!nowy || nowy === z.tekst) { rysujZasady(); return; }
      try { await wyslij("/api/personalizacja/zasady/" + id, "PUT", {tekst: nowy}); await rysuj(); podswietlZasade(id); }
      catch (b) { stan($("pz-stan"), b.message, true); rysujZasady(); }
    };
    pole.onkeydown = (e) => { if (e.key === "Enter") zapisz(); if (e.key === "Escape") rysujZasady(); };
    pole.onblur = zapisz;
  }

  function rysujWbudowane() {
    $("pz-wbudowane-tytul").textContent = `Zawsze pilnuję też budowy aktu (${dane.wbudowane.filter(w => w.wlaczona).length} z ${dane.wbudowane.length})`;
    $("pz-wbudowane").innerHTML = dane.wbudowane.map(w => `<div class="pz-wb"><span>${escape(w.opis)}</span>
      ${dane.moge_zmieniac ? `<label class="pz-przel"><input type="checkbox" data-kod="${w.kod}"${w.wlaczona ? " checked" : ""} aria-label="${escape(w.opis)}"><span></span></label>` : ""}</div>`).join("");
    $("pz-wbudowane").querySelectorAll("input").forEach(i => i.onchange = async () => {
      try { await wyslij("/api/personalizacja/wbudowane/" + i.dataset.kod, "PUT", {wlaczona: i.checked}); await rysuj(); }
      catch (b) { stan($("pz-stan"), b.message, true); }
    });
  }

  /* ---------- nauka stylu ---------- */
  function rysujStyl() {
    const s = dane.styl;
    $("pz-nawyki").innerHTML = s.nawyki.map(n =>
      `<span class="pz-nawyk">${escape(n.tekst)}<small>${n.ile}/${n.z}</small></span>`).join("");
    $("pz-akty").innerHTML = s.aktow ? `<div><b>${s.aktow}</b> ${odm(s.aktow, "akt", "akty", "aktów")} · ${s.sformulowan} ${odm(s.sformulowan, "sformułowanie", "sformułowania", "sformułowań")}, w tym ${s.powtarzalnych} powtarzalnych` +
      (s.rodzaje.length ? " · " + s.rodzaje.map(r => escape(r.nazwa) + " (" + r.aktow + ")").join(", ") : "") + "</div>" : "";
    $("pz-zapomnij").hidden = !s.aktow || !dane.moge_zmieniac;
  }

  async function naucz(pliki) {
    if (!pliki.length) return;
    stan($("pz-stan-nauki"), `Czytam ${pliki.length} ${odm(pliki.length, "akt", "akty", "aktów")} i rozbieram na klauzule…`, false, true);
    $("pz-wynik-nauki").innerHTML = "";
    const formularz = new FormData();
    [...pliki].forEach(p => formularz.append("pliki", p));
    try {
      const sugestiePrzed = dane?.sugestie?.length || 0;
      const w = await json("/api/personalizacja/akty", {method: "POST", body: formularz});
      stan($("pz-stan-nauki"), "");
      await rysuj();
      const nowe = dane.sugestie.length - sugestiePrzed;
      $("pz-wynik-nauki").innerHTML = `<div class="pz-wynik">` +
        (w.dodane.length ? `<b>Nauczyłem się z ${w.dodane.length} ${odm(w.dodane.length, "aktu", "aktów", "aktów")}.</b>
          <ul>${w.dodane.map(a => `<li>${escape(a.nazwa || a.etykieta)} - ${escape(a.etykieta.split(" · ")[1] || "")}, ${a.klauzul} ${odm(a.klauzul, "klauzula", "klauzule", "klauzul")}</li>`).join("")}</ul>` : "<b>Niczego nie dodałem.</b>") +
        (w.pominiete.length ? `<div style="margin-top:8px;color:var(--alarm)">Pominięte:</div><ul>${w.pominiete.map(p =>
          `<li>${escape(p.nazwa || "plik " + p.plik)}: ${escape(p.powod)}</li>`).join("")}</ul>` : "") +
        (nowe > 0 ? `<div style="margin-top:8px">Mam ${nowe} ${odm(nowe, "nową podpowiedź", "nowe podpowiedzi", "nowych podpowiedzi")} zasad - zobacz wyżej.</div>` : "") + "</div>";
    } catch (e) {
      stan($("pz-stan-nauki"), e.message, true);
    }
  }

  /* ---------- sformulowania ---------- */
  function szkieletHtml(t) {
    return escape(t).replace(/\{([A-Z_]+)\}/g, (_, p) => `<span class="pz-pole">${escape(POLA[p] || p.toLowerCase())}</span>`);
  }
  function rysujSformulowania() {
    const czesci = dane.styl.czesci;
    $("pz-karta-sformulowan").hidden = !czesci.length;
    if (!czesci.length) return;
    if (!czesci.some(c => c.czesc === czescWidoczna)) czescWidoczna = czesci[0].czesc;
    $("pz-czesci").innerHTML = czesci.map(c => `<button class="chip${c.czesc === czescWidoczna ? " on" : ""}" data-c="${c.czesc}">${escape(c.nazwa.split(" (")[0])} · ${c.sformulowania.length}</button>`).join("");
    $("pz-czesci").querySelectorAll("button").forEach(b => b.onclick = () => { czescWidoczna = b.dataset.c; pokazWszystkie = false; rysujSformulowania(); });
    const lista = czesci.find(c => c.czesc === czescWidoczna).sformulowania;
    const widoczne = pokazWszystkie ? lista : lista.slice(0, 8);
    $("pz-sformulowania").innerHTML = widoczne.map(s => `<div class="pz-sformulowanie${s.przypiete ? " przypiete" : ""}${s.ukryte ? " ukryte" : ""}" data-id="${s.id}">
      <div class="pz-szkielet">${szkieletHtml(s.szkielet)}</div>
      <div class="pz-meta"><span>${s.wlasne ? "dodane przez Ciebie" : `w ${s.wystapien} ${odm(s.wystapien, "akcie", "aktach", "aktach")}`}${s.rodzaje.length ? " · " + escape(s.rodzaje.map(r => dane.kategorie.rodzaje[r] || r).join(", ")) : ""}</span>
      <span><button class="wtorny" data-a="przypiete" title="Wzorcowe - zawsze w pierwszej kolejności">${s.przypiete ? "★ Wzorcowe" : "☆ Ustaw jako wzorcowe"}</button>
      <button class="wtorny" data-a="ukryte">${s.ukryte ? "Przywróć" : "Nie używaj"}</button></span></div></div>`).join("") +
      (lista.length > widoczne.length ? `<button class="pz-wiecej" id="pz-wiecej">Pokaż wszystkie (${lista.length})</button>` : "");
    $("pz-wiecej") && ($("pz-wiecej").onclick = () => { pokazWszystkie = true; rysujSformulowania(); });
    $("pz-sformulowania").querySelectorAll(".pz-sformulowanie").forEach(w => w.querySelectorAll("button").forEach(b => b.onclick = async () => {
      const s = lista.find(x => x.id === w.dataset.id), pole = b.dataset.a;
      try { await wyslij("/api/personalizacja/sformulowania/" + s.id, "PUT", {[pole]: !s[pole]}); await rysuj(); }
      catch (e) { stan($("pz-stan-nauki"), e.message, true); }
    }));
  }

  /* ---------- raport zgodnosci ---------- */
  function raportHtml(r, zLinkiem) {
    if (!r) return null;
    if (r.niesprawdzony) return {klasa: "uwaga", html: `<div class="zg-tytul">⚠ ${escape(r.komunikat)}</div>`};
    const poprawki = (r.poprawki || []).map(p => `<li>${escape(p.opis)}${p.ile > 1 ? " ×" + p.ile : ""}</li>`).join("");
    const lista = (r.naruszenia || []).map(n => `<li><div>${n.poziom === "blokuje" ? "⛔" : "⚠"} ${escape(n.komunikat)}</div>
      <div class="zg-zasada">Zasada: ${escape(n.tekst_zasady)}${n.ai ? " · sprawdziło AI" : ""}</div>
      ${n.fragment ? `<div class="zg-fragment">${escape(n.fragment)}</div>` : ""}</li>`).join("");
    const bezZasad = zLinkiem && r.sprawdzonych <= 5 ? ' <a data-do-zasad>Dodaj zasady kancelarii →</a>' : "";
    const sprawdzil = `sprawdziłem ${r.sprawdzonych} ${odm(r.sprawdzonych, "zasadę", "zasady", "zasad")}`;
    let klasa, tytul;
    if (r.blokujacych) { klasa = "zle"; tytul = `⛔ Projekt narusza ${r.blokujacych} ${odm(r.blokujacych, "nieprzekraczalną zasadę", "nieprzekraczalne zasady", "nieprzekraczalnych zasad")} kancelarii`; }
    else if (r.ostrzezen) { klasa = "uwaga"; tytul = `✓ Zgodny z zasadami nieprzekraczalnymi · ${r.ostrzezen} ${odm(r.ostrzezen, "uwaga", "uwagi", "uwag")}`; }
    else { klasa = "ok"; tytul = "✓ Zgodny z zasadami kancelarii"; }
    const model = r.poprawka_modelu?.przyjeta ? " · część poprawił model" : "";
    return {klasa, html: `<div class="zg-tytul">${tytul}</div><div class="zg-zasada">${sprawdzil}${model}${bezZasad}</div>` +
      (lista ? `<ul>${lista}</ul>` : "") +
      (poprawki ? `<details><summary>Poprawiłem sam przed pokazaniem projektu (${r.poprawki.length})</summary><ul>${poprawki}</ul></details>` : "")};
  }

  function podswietl(el, frazy) {
    const unikalne = [...new Set(frazy.filter(f => f && f.trim().length >= 2))];
    if (!unikalne.length) return;
    const wzor = new RegExp(unikalne.map(f => f.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|"), "g");
    const chodzik = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    const wezly = [];
    while (chodzik.nextNode()) wezly.push(chodzik.currentNode);
    wezly.forEach(w => {
      if (!wzor.test(w.nodeValue)) return;
      wzor.lastIndex = 0;
      const tmp = document.createElement("span");
      tmp.innerHTML = escape(w.nodeValue).replace(new RegExp(unikalne.map(f => escape(f).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|"), "g"),
        m => `<mark class="naruszenie">${m}</mark>`);
      w.replaceWith(...tmp.childNodes);
    });
  }

  window.pokazZgodnosc = function (r) {
    const el = $("zgodnosc3");
    const raport = raportHtml(r, true);
    el.hidden = !raport;
    if (!raport) return;
    el.className = "zgodnosc " + raport.klasa;
    el.innerHTML = raport.html;
    el.querySelector("[data-do-zasad]")?.addEventListener("click", () => pokaz(9));
    podswietl($("projekt"), (r.naruszenia || []).map(n => n.trafienie));
  };

  async function sprawdzTekst() {
    const tekst = $("pz-test").value;
    if (!tekst.trim()) return stan($("pz-stan-test"), "Wklej tekst do sprawdzenia.", true);
    stan($("pz-stan-test"), "Sprawdzam…", false, true);
    try {
      const r = await wyslij("/api/personalizacja/sprawdz", "POST", {tekst});
      stan($("pz-stan-test"), "");
      const raport = raportHtml(r, false);
      $("pz-raport-test").innerHTML = `<div class="zgodnosc ${raport.klasa}" style="margin-top:12px">${raport.html}` +
        (r.poprawiony ? `<div style="margin-top:8px"><button class="wtorny" id="pz-wstaw">Wstaw wersję poprawioną (${r.poprawki.length})</button></div>` : "") +
        (r.do_sprawdzenia_ai ? `<div class="zg-zasada" style="margin-top:6px">${r.do_sprawdzenia_ai} ${odm(r.do_sprawdzenia_ai, "wytyczna opisowa", "wytyczne opisowe", "wytycznych opisowych")} - te sprawdza AI przy sporządzaniu projektu.</div>` : "") + "</div>";
      $("pz-wstaw") && ($("pz-wstaw").onclick = () => { $("pz-test").value = r.poprawiony; sprawdzTekst(); });
    } catch (e) {
      stan($("pz-stan-test"), e.message, true);
    }
  }

  /* ---------- pasek nad zaznaczeniem w projekcie ---------- */
  const pasek = document.createElement("div");
  pasek.className = "pz-zaznaczenie"; pasek.hidden = true;
  pasek.innerHTML = `<button data-z="zakaz" title="Dodaj zasadę: tego sformułowania nie używamy">⛔ Nigdy tak nie pisz</button>
    <button data-z="zamiana" title="Dodaj zasadę: zamieniaj na inne sformułowanie">⇄ Zamieniaj na…</button>
    <button data-z="wzorcowe" title="Zapamiętaj jako wzorcowe sformułowanie kancelarii">★ Zapamiętaj jako wzorcowe</button>`;
  document.body.appendChild(pasek);
  let zaznaczone = "";

  function pokazPasek() {
    const sel = window.getSelection();
    const tekst = sel && !sel.isCollapsed ? bezCudzyslowow(sel.toString()) : "";
    const projekt = $("projekt");
    if (!tekst || !projekt || !projekt.contains(sel.anchorNode) || $("etap3").hidden) { pasek.hidden = true; return; }
    zaznaczone = tekst;
    pasek.querySelector('[data-z="zakaz"]').hidden = tekst.length > 80;
    pasek.querySelector('[data-z="zamiana"]').hidden = tekst.length > 80;
    pasek.querySelector('[data-z="wzorcowe"]').hidden = tekst.length < 20;
    const r = sel.getRangeAt(0).getBoundingClientRect();
    pasek.hidden = false;
    const szer = pasek.offsetWidth;
    pasek.style.left = Math.max(8, Math.min(window.innerWidth - szer - 8, r.left + r.width / 2 - szer / 2)) + "px";
    pasek.style.top = Math.max(8, r.top - pasek.offsetHeight - 8) + "px";
  }
  document.addEventListener("selectionchange", () => { clearTimeout(pasek._t); pasek._t = setTimeout(pokazPasek, 180); });
  window.addEventListener("scroll", () => { pasek.hidden = true; }, true);
  pasek.addEventListener("mousedown", e => e.preventDefault());   // nie gubimy zaznaczenia
  pasek.querySelectorAll("button").forEach(b => b.onclick = async () => {
    const tekst = zaznaczone;
    pasek.hidden = true;
    try {
      if (b.dataset.z === "wzorcowe") {
        await wyslij("/api/personalizacja/sformulowania", "POST", {tekst});
        stan($("stan3"), "Zapamiętane jako wzorcowe sformułowanie kancelarii (bez danych osobowych).");
        return;
      }
      let zdanie = `Nigdy nie używaj „${tekst}”`;
      if (b.dataset.z === "zamiana") {
        const nowe = prompt(`Na co zamieniać „${tekst}”?`);
        if (!nowe || !bezCudzyslowow(nowe)) return;
        zdanie = `Zamiast „${tekst}” pisz „${bezCudzyslowow(nowe)}”`;
      }
      const w = await wyslij("/api/personalizacja/zasady", "POST", {tekst: zdanie});
      stan($("stan3"), (w.juz_byla ? "Ta zasada już jest: " : "Dodana zasada: ") + w.zasada.opis.split(" · ")[0] + ". Obowiązuje od następnego projektu.");
    } catch (e) {
      stan($("stan3"), e.message, true);
    }
  });

  /* ---------- zdarzenia ---------- */
  $("pz-tekst").addEventListener("input", () => interpretujZaChwile());
  $("pz-tekst").addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); dodajZasade(); }
  });
  $("pz-dodaj").onclick = dodajZasade;
  $("pz-pliki").onchange = (e) => { naucz(e.target.files); e.target.value = ""; };
  const strefa = $("pz-strefa");
  strefa.addEventListener("dragover", e => { e.preventDefault(); e.stopPropagation(); strefa.style.borderColor = "var(--akcent)"; });
  strefa.addEventListener("dragleave", () => { strefa.style.borderColor = ""; });
  strefa.addEventListener("drop", e => { e.preventDefault(); e.stopPropagation(); strefa.style.borderColor = ""; naucz(e.dataTransfer.files); });
  $("pz-zapomnij").onclick = async () => {
    if (!confirm("Zapomnieć cały wyuczony styl? Zasady kancelarii zostaną.")) return;
    try { await wyslij("/api/personalizacja/styl", "DELETE"); $("pz-wynik-nauki").innerHTML = ""; await rysuj(); }
    catch (e) { stan($("pz-stan-nauki"), e.message, true); }
  };
  $("pz-sprawdz").onclick = sprawdzTekst;

  window.rysujPersonalizacje = rysuj;
  window.nauczZAktow = naucz;
})();
