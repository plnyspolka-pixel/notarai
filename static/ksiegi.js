/* Ksiegi notarialne (rep. A, P, C, depozyt, dzienniki), wnioski KW i GIIF.
 * Backend: /api/ksiegi-kancelarii, /api/giif. Serwer nadaje numery i pilnuje
 * zasad; tu jest tylko widok i formularze. Dane stron nie trafiaja do konsoli.
 */
(function () {
  "use strict";
  const el = id => document.getElementById(id);
  const esc = t => String(t ?? "").replace(/[&<>"']/g, z => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[z]));
  const zl = t => (t ? Number(t).toLocaleString("pl-PL", {minimumFractionDigits: 2}) + " zł" : "");
  let definicje = null, ksiega = "repertorium_a", lista = [];

  async function json(adres, opcje) {
    const odp = await api(adres, opcje);
    const dane = await odp.json().catch(() => ({}));
    if (!odp.ok) throw new Error(typeof dane.detail === "string" ? dane.detail : "Błąd " + odp.status);
    return dane;
  }
  const post = (adres, dane) => json(adres, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(dane)});
  const komunikat = (tekst, blad) => stan(el("stan8"), tekst, blad);

  /* ---------- ksiegi ---------- */
  window.rysujKsiegi = async function () {
    if (!el("ks-rok").value) el("ks-rok").value = new Date().getFullYear();
    el("ks-rok").onchange = rysujListe;
    try { definicje = definicje || await json("/api/ksiegi-kancelarii"); }
    catch (e) { return komunikat(e.message, true); }
    el("ks-zakladki").innerHTML = Object.entries(definicje.ksiegi).map(([k, d]) =>
      `<button class="chip${k === ksiega ? " on" : ""}" data-k="${k}">${esc(d.nazwa)}</button>`).join("");
    el("ks-zakladki").querySelectorAll("button").forEach(b => b.onclick = () => { ksiega = b.dataset.k; window.rysujKsiegi(); });
    el("ks-opis").textContent = definicje.ksiegi[ksiega].opis;
    el("ks-wniosek").hidden = true;
    rysujFormularz();
    await rysujListe();
  };

  async function rysujListe() {
    const d = definicje.ksiegi[ksiega];
    const rok = d.roczna ? "?rok=" + encodeURIComponent(el("ks-rok").value) : "";
    try { lista = await json(`/api/ksiegi-kancelarii/${ksiega}${rok}`); }
    catch (e) { return komunikat(e.message, true); }
    komunikat(lista.length ? "" : "Brak wpisów.");
    const kolumny = Object.entries(d.rubryki).slice(0, 6);
    el("ks-lista").innerHTML = `<div style="overflow-x:auto"><table class="ks-tab"><thead><tr><th>Nr</th>${
      kolumny.map(([, n]) => `<th>${esc(n)}</th>`).join("")}<th></th></tr></thead><tbody>${
      lista.map(w => `<tr><td><b>${esc(w.oznaczenie)}</b>${w.korekty.length ? `<br><small title="Poprawki">✎ ${w.korekty.length}</small>` : ""}</td>${
        kolumny.map(([p]) => `<td>${esc(Array.isArray(w[p]) ? w[p].map(x => x.nazwa || x).join("; ") : (/^(wartosc|wynagr|vat|oplata|podatek|kwota)/.test(p) ? zl(w[p]) : w[p]))}</td>`).join("")
      }<td>${akcje(w)}</td></tr>`).join("")}</tbody></table></div>`;
    el("ks-lista").querySelectorAll("[data-a]").forEach(b => b.onclick = () => akcja(b.dataset.a, b.dataset.id));
  }

  function akcje(w) {
    const b = (a, t) => `<button class="wtorny maly-p" data-a="${a}" data-id="${w.id}">${t}</button>`;
    let wynik = b("popraw", "Popraw") + b("uwaga", "Uwaga");
    if (ksiega === "repertorium_a") {
      wynik += b("kw", "Wniosek KW" + (w.wnioski_kw?.length ? ` (${w.wnioski_kw.length})` : "")) + b("giif", "GIIF");
    }
    return wynik;
  }

  function rysujFormularz() {
    const d = definicje.ksiegi[ksiega];
    if (d.numer_z_systemu) {
      el("ks-nowy").innerHTML = `<h2>Nowy wpis</h2><p class="pod">Wpisy w repertorium C powstają same, gdy w repertorium A oznaczysz wniosek KW jako złożony i podasz numer REP.C nadany przez system.</p>`;
      return;
    }
    el("ks-nowy").innerHTML = `<h2>Nowy wpis: ${esc(d.nazwa)}</h2>${Object.entries(d.rubryki).map(([p, n]) =>
      `<label class="pole">${esc(n)}${d.wymagane.includes(p) ? " *" : ""}<input type="text" data-p="${p}" ${p.startsWith("data") ? 'placeholder="RRRR-MM-DD"' : ""}${p === "strony" ? ' placeholder="Imię Nazwisko; Imię Nazwisko"' : ""}></label>`).join("")
      }<button id="ks-dodaj">Wpisz do księgi</button>`;
    el("ks-dodaj").onclick = async () => {
      const dane = {};
      el("ks-nowy").querySelectorAll("[data-p]").forEach(i => { if (i.value.trim()) dane[i.dataset.p] = i.value.trim(); });
      try { const w = await post(`/api/ksiegi-kancelarii/${ksiega}`, dane); komunikat("Wpisano " + w.oznaczenie); rysujFormularz(); await rysujListe(); }
      catch (e) { komunikat(e.message, true); }
    };
  }

  async function akcja(rodzaj, id) {
    const w = lista.find(x => x.id === id);
    try {
      if (rodzaj === "popraw") {
        const pole = prompt("Którą rubrykę poprawić? " + Object.keys(definicje.ksiegi[ksiega].rubryki).join(", "));
        if (!pole) return;
        const wartosc = prompt("Nowa treść rubryki", w[pole] ?? ""); if (wartosc === null) return;
        const powod = prompt("Powód poprawki (zostaje w historii)"); if (!powod) return;
        await post(`/api/ksiegi-kancelarii/${ksiega}/${id}/poprawka`, {zmiany: {[pole]: wartosc}, powod});
      } else if (rodzaj === "uwaga") {
        const tresc = prompt("Uwaga (np. wydano wypis — komu, kiedy)"); if (!tresc) return;
        await post(`/api/ksiegi-kancelarii/${ksiega}/${id}/uwagi`, {tresc});
      } else if (rodzaj === "kw") {
        return rysujWnioski(w);
      } else if (rodzaj === "giif") {
        const kurs = prompt("Średni kurs EUR z tabeli A NBP z dnia czynności (pusty = bez sprawdzania progu)", "");
        const z = await post("/api/giif", {rep_a_id: id, kurs_eur: kurs || ""});
        return komunikat(`Utworzono szkic zgłoszenia (termin ${z.termin || "—"}). Otwórz „Zgłoszenia GIIF”.`);
      }
      await rysujListe();
    } catch (e) { komunikat(e.message, true); }
  }

  /* ---------- wnioski KW ---------- */
  function rysujWnioski(w) {
    const k = el("ks-wniosek"); k.hidden = false;
    const zad = definicje.wniosek_kw.zadania;
    const strony = (w.strony || []).map(s => s.nazwa);
    k.innerHTML = `<h2>Wnioski KW do ${esc(w.oznaczenie)}</h2>
      ${(w.wnioski_kw || []).map(wn => `<div class="pole"><b>${esc(wn.numer_kw || "nowa księga")}</b> — ${esc(wn.status)}${wn.numer_rep_c ? " · " + esc(wn.numer_rep_c) : ""} · opłata ${zl(wn.oplata.razem)}
        ${wn.braki.length ? `<br><span class="stan blad">Braki: ${esc(wn.braki.join("; "))}</span>` : ""}
        <br><button class="wtorny" data-pakiet="${wn.id}">Pakiet do portalu</button>
        ${wn.status === "przygotowany" ? `<button class="wtorny" data-zloz="${wn.id}">Złożony — wpisz REP.C</button>` : `<button class="wtorny" data-status="${wn.id}">Zmień stan</button>`}</div>`).join("")}
      <h2>Nowy wniosek</h2>
      <label class="pole">Numer KW<input type="text" id="kw-numer" placeholder="WA4M/00160286/2"></label>
      <label class="pole">Sąd i wydział KW<input type="text" id="kw-sad"></label>
      <label class="pole">Notariusz<input type="text" id="kw-notariusz"></label>
      <label class="pole">Siedziba kancelarii<input type="text" id="kw-siedziba"></label>
      <label class="pole">Na rzecz (nabywca / wierzyciel)<select id="kw-na-rzecz">${strony.map(s => `<option>${esc(s)}</option>`).join("")}</select></label>
      <label class="pole">Imiona rodziców nabywcy<input type="text" id="kw-rodzice"></label>
      <div class="pole">${Object.entries(zad).map(([kl, z]) => `<label style="display:block"><input type="checkbox" value="${kl}" class="kw-zad"> ${esc(z.opis)}</label>`).join("")}</div>
      <label class="pole">Suma hipoteki (gdy wpis hipoteki)<input type="text" id="kw-suma"></label>
      <button id="kw-zapisz">Przygotuj wniosek</button><div id="kw-pakiet"></div>`;
    el("kw-zapisz").onclick = async () => {
      const naRzecz = el("kw-na-rzecz").value;
      const uczestnicy = (w.strony || []).map(s => ({nazwa: s.nazwa, pesel: s.pesel || "",
        rola: s.nazwa === naRzecz ? "nabywca" : "uczestnik",
        imiona_rodzicow: s.nazwa === naRzecz ? el("kw-rodzice").value : ""}));
      const zadania = [...k.querySelectorAll(".kw-zad:checked")].map(c => ({rodzaj: c.value, na_rzecz: [naRzecz], suma: el("kw-suma").value}));
      try {
        const rep = await post(`/api/ksiegi-kancelarii/repertorium_a/${w.id}/wnioski-kw`, {
          numer_kw: el("kw-numer").value, sad: el("kw-sad").value, uczestnicy, zadania,
          akt: {notariusz: el("kw-notariusz").value, siedziba: el("kw-siedziba").value}});
        rysujWnioski(rep); await rysujListe();
      } catch (e) { komunikat(e.message, true); }
    };
    k.querySelectorAll("[data-pakiet]").forEach(b => b.onclick = async () => {
      try {
        const p = await json(`/api/ksiegi-kancelarii/repertorium_a/${w.id}/wnioski-kw/${b.dataset.pakiet}/pakiet`);
        el("kw-pakiet").innerHTML = `<h2>Do portalu MS${p.gotowy ? "" : " — uzupełnij braki"}</h2>` + p.kroki.map(kr =>
          `<div class="pole"><b>${esc(kr.krok)}</b>${Object.entries(kr.pola).map(([n, v]) =>
            `<div>${esc(n)}: <code>${esc(v)}</code> <button class="wtorny maly-p" data-kopiuj="${esc(v)}">Kopiuj</button></div>`).join("")}</div>`).join("");
        el("kw-pakiet").querySelectorAll("[data-kopiuj]").forEach(c => c.onclick = () => navigator.clipboard?.writeText(c.dataset.kopiuj));
      } catch (e) { komunikat(e.message, true); }
    });
    const zmien = async (idw, dane) => {
      try { const rep = await post(`/api/ksiegi-kancelarii/repertorium_a/${w.id}/wnioski-kw/${idw}/status`, dane); rysujWnioski(rep); await rysujListe(); }
      catch (e) { komunikat(e.message, true); }
    };
    k.querySelectorAll("[data-zloz]").forEach(b => b.onclick = () => {
      const numer = prompt("Numer REP.C nadany przez system (np. REP.C/NOTA/1234/26)"); if (!numer) return;
      const data = prompt("Data złożenia (RRRR-MM-DD)", new Date().toISOString().slice(0, 10)); if (!data) return;
      zmien(b.dataset.zloz, {status: "zlozony", numer_rep_c: numer, data_zlozenia: data});
    });
    k.querySelectorAll("[data-status]").forEach(b => b.onclick = () => {
      const status = prompt("Nowy stan: " + definicje.statusy_wniosku_kw.slice(2).join(", ")); if (!status) return;
      const sygnatura = prompt("Numer w dzienniku KW (sygnatura sądu), jeśli znany", "") || "";
      zmien(b.dataset.status, {status, sygnatura_dz_kw: sygnatura,
        data_wpisu: status === "wpis_dokonany" ? new Date().toISOString().slice(0, 10) : ""});
    });
    k.scrollIntoView({behavior: "smooth"});
  }

  /* ---------- GIIF ---------- */
  const NAZWY_STATUSOW = {szkic: "szkic", do_podpisu: "do podpisu w SI*GIIF", wyslane: "wysłane", upo: "UPO odebrane"};
  window.rysujGiif = async function () {
    let dane;
    try { dane = await json("/api/giif"); } catch (e) { return stan(el("stan9"), e.message, true); }
    const zalegle = new Set(dane.zalegle.map(z => z.id));
    el("licznik-giif").hidden = !zalegle.size; el("licznik-giif").textContent = zalegle.size || "";
    stan(el("stan9"), dane.zgloszenia.length ? "" : "Brak zgłoszeń. Utwórz je z wpisu w repertorium A (przycisk GIIF).");
    el("giif-lista").innerHTML = dane.zgloszenia.map(z => `<div class="pole"${zalegle.has(z.id) ? ' style="border-left:3px solid var(--alarm);padding-left:8px"' : ""}>
      <b>${esc(z.rep_a)}</b> — ${esc(dane.definicje.rodzaje[z.rodzaj].nazwa)} · ${esc(NAZWY_STATUSOW[z.status])}
      ${z.termin ? ` · termin ${esc(z.termin)}` : ""}${z.rownowartosc_eur ? ` · ${esc(z.rownowartosc_eur)} EUR` : ""}
      ${z.braki.length ? `<br><span class="stan blad">Braki: ${esc(z.braki.join("; "))}</span>` : ""}
      ${z.identyfikator_si_giif ? `<br>SI*GIIF: ${esc(z.identyfikator_si_giif)} (${esc(z.data_wysylki)})${z.po_terminie ? " — po terminie" : ""}` : ""}
      <br>${z.status === "szkic" ? `<button class="wtorny" data-g="edytuj" data-id="${z.id}">Uzupełnij</button><button class="wtorny" data-g="zatwierdz" data-id="${z.id}">Zatwierdź</button>` : ""}
      ${z.status === "do_podpisu" ? `<button class="wtorny" data-g="wyslane" data-id="${z.id}">Wysłane w SI*GIIF</button>` : ""}
      ${z.status === "wyslane" ? `<label class="wtorny">UPO <input type="file" data-upo="${z.id}" hidden></label>` : ""}</div>`).join("");
    el("giif-lista").querySelectorAll("[data-g]").forEach(b => b.onclick = () => akcjaGiif(b.dataset.g, dane.zgloszenia.find(z => z.id === b.dataset.id), dane.definicje));
    el("giif-lista").querySelectorAll("[data-upo]").forEach(i => i.onchange = async () => {
      const f = new FormData(); f.append("plik", i.files[0]);
      try { await json(`/api/giif/${i.dataset.upo}/upo`, {method: "POST", body: f}); window.rysujGiif(); }
      catch (e) { stan(el("stan9"), e.message, true); }
    });
  };

  async function akcjaGiif(rodzaj, z, def) {
    try {
      if (rodzaj === "zatwierdz") await post(`/api/giif/${z.id}/zatwierdz`, {});
      if (rodzaj === "wyslane") {
        const numer = prompt("Identyfikator przesyłki z SI*GIIF"); if (!numer) return;
        const data = prompt("Data wysyłki (RRRR-MM-DD)", new Date().toISOString().slice(0, 10)); if (!data) return;
        await post(`/api/giif/${z.id}/wysylka`, {identyfikator_si_giif: numer, data_wysylki: data});
      }
      if (rodzaj === "edytuj") return edytujGiif(z, def);
      el("giif-edycja").hidden = true;
      window.rysujGiif();
    } catch (e) { stan(el("stan9"), e.message, true); }
  }

  function edytujGiif(z, def) {
    const k = el("giif-edycja"); k.hidden = false;
    const n = z.nieruchomosc || {};
    const poleStrony = (s, i, p, opis) => `<label class="pole">${esc(opis)}<input type="text" data-s="${i}" data-p="${p}" value="${esc(s[p])}"></label>`;
    k.innerHTML = `<h2>${esc(z.rep_a)} — uzupełnij</h2>
      <label class="pole">Przedmiot transakcji<input type="text" id="g-przedmiot" value="${esc(z.przedmiot)}"></label>
      <label class="pole">Wartość<input type="text" id="g-kwota" value="${esc(z.kwota)}"></label>
      <label class="pole">Kurs EUR (tabela A NBP)<input type="text" id="g-kurs" value="${esc(z.kurs_eur)}"></label>
      <label class="pole"><input type="checkbox" id="g-nier" ${z.nieruchomosc ? "checked" : ""}> Przedmiotem jest nieruchomość</label>
      ${def.pola_nieruchomosci.map(p => `<label class="pole">Nieruchomość: ${esc(p.replace(/_/g, " "))}<input type="text" data-n="${p}" value="${esc(n[p])}"></label>`).join("")}
      ${z.strony.map((s, i) => `<h2>${esc(s.nazwa)}</h2>` + poleStrony(s, i, "pesel", "PESEL") + poleStrony(s, i, "dokument", "Dokument tożsamości (gdy brak PESEL)")
        + poleStrony(s, i, "panstwo_dokumentu", "Państwo wydania dokumentu") + poleStrony(s, i, "adres", "Adres") + poleStrony(s, i, "udzial", "Udział")).join("")}
      <button id="g-zapisz">Zapisz</button>`;
    el("g-zapisz").onclick = async () => {
      const strony = z.strony.map(s => ({...s}));
      k.querySelectorAll("[data-s]").forEach(i => { strony[+i.dataset.s][i.dataset.p] = i.value; });
      const nier = {}; k.querySelectorAll("[data-n]").forEach(i => { nier[i.dataset.n] = i.value; });
      try {
        await post(`/api/giif/${z.id}`, {przedmiot: el("g-przedmiot").value, kwota: el("g-kwota").value,
          kurs_eur: el("g-kurs").value, strony, nieruchomosc: el("g-nier").checked ? nier : null});
        k.hidden = true; window.rysujGiif();
      } catch (e) { stan(el("stan9"), e.message, true); }
    };
    k.scrollIntoView({behavior: "smooth"});
  }
})();
