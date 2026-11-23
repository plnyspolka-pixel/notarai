/* Panel boczny notarai: pole polecenia obok strony urzedu.

   Notariusz pisze, co ma sie stac na otwartej stronie; panel pyta notarai o
   kolejny krok i wykonuje go w tej karcie. Po kazdym kroku widac, co zrobil
   i po co. Tresci strony ani wpisywanych wartosci nie zapisujemy nigdzie -
   lista krokow zyje tylko w tym panelu. */

import { prowadz, host } from "./silnik.js";
import { Strona } from "./strona.js";
import { wykonajKRZ } from "./krz.js";
import { wykonajFormularz } from "./formularz.js";
import { Notarai, ADRES_DOMYSLNY, BladTokenu, KodNieaktualny, BladPolaczenia,
         adresPolaczenia } from "./notarai.js";

const $ = (id) => document.getElementById(id);
const czekaj = (ms) => new Promise(r => setTimeout(r, ms));

let ustawienia = { adres: ADRES_DOMYSLNY, token: "" };
let karta = null;          // { id, url } - karta, przy ktorej stoi panel
let pracuje = false, przerwij = false, laczenie = 0, kodPolaczenia = "";

/* Tylko do testow: panel otwarty jako zwykla karta dostaje numer karty,
   na ktorej ma pracowac (?karta=12). W panelu bocznym tego parametru nie ma. */
const kartaZTestu = Number(new URLSearchParams(location.search).get("karta")) || 0;

const NAZWY_AKCJI = { kliknij: "Klikam", wpisz: "Wpisuję w", wybierz: "Wybieram w",
                      otworz: "Otwieram", czytaj: "Czytam stronę", pytam: "Pytam",
                      koniec: "Gotowe", krz: "Sprawdzam w KRZ:", pominiete: "Pomijam" };

function nazwaPrzegladarki() {
  return (/Edg\//.test(navigator.userAgent) ? "Edge" : "Chrome") + " - rozszerzenie notarai";
}

function wzorzecZgody(adres) {
  const u = new URL(adres);
  return `${u.protocol}//${u.hostname}/*`;
}

async function zapisz() {
  await chrome.storage.local.set({ adres: ustawienia.adres, token: ustawienia.token });
}

async function odswiezKarte() {
  try {
    const t = kartaZTestu ? await chrome.tabs.get(kartaZTestu)
      : (await chrome.tabs.query({ active: true, currentWindow: true }))[0];
    karta = t ? { id: t.id, url: t.url || "" } : null;
  } catch { karta = null; }
  if (!pracuje) $("host").textContent = (karta && host(karta.url)) || "—";
}

function pokazWidok() {
  const polaczony = !!ustawienia.token;
  $("widok-laczenie").hidden = polaczony;
  $("widok-praca").hidden = !polaczony;
  $("znaczek").textContent = polaczony ? "połączony" : "";
  $("znaczek").classList.toggle("polaczony", polaczony);
  if (!polaczony) polacz(); else pilnujKolejki();
}

/* ---------- laczenie z kancelaria ---------- */

async function polacz() {
  const numer = ++laczenie;                 // nowe laczenie uniewaznia poprzednie
  const notarai = new Notarai(ustawienia.adres);
  let kod = "", sekret = "";
  while (numer === laczenie && !ustawienia.token) {
    try {
      if (!kod) {
        const odp = await notarai.poprosOKod(nazwaPrzegladarki());
        kod = odp.kod; sekret = odp.sekret;
        kodPolaczenia = kod;
        $("kod").textContent = kod;
        $("stan-laczenia").textContent = "Czekam na kliknięcie „Połącz” w notarai…";
      }
      const token = await notarai.odbierzToken(kod, sekret);
      if (token && numer === laczenie) {
        ustawienia.token = token;
        await zapisz();
        pokazWidok();
        return;
      }
      await czekaj(2000);
    } catch (blad) {
      if (blad instanceof KodNieaktualny) { kod = sekret = ""; continue; }
      $("stan-laczenia").textContent = blad.message + " Ponawiam…";
      await czekaj(15000);
    }
  }
}

$("btn-otworz").onclick = () => {
  if (kodPolaczenia) chrome.tabs.create({ url: adresPolaczenia(ustawienia.adres, kodPolaczenia) });
};

$("btn-odlacz").onclick = async () => {
  if (pracuje || !confirm("Odłączyć tę przeglądarkę od kancelarii?")) return;
  try { await new Notarai(ustawienia.adres, ustawienia.token).odlacz(); }
  catch { /* i tak zapominamy token; w notarai mozna odlaczyc recznie */ }
  await odlaczLokalnie();
};

async function odlaczLokalnie() {
  ustawienia.token = "";
  await zapisz();
  pokazWidok();
}

/* ---------- praca na stronie ---------- */

function dopiszKrok(krok) {
  const li = document.createElement("li");
  const co = document.createElement("div");
  co.className = "co";
  co.textContent = `${krok.nr}. ${NAZWY_AKCJI[krok.akcja] || krok.akcja || "Krok"}` +
                   (krok.cel && krok.akcja !== "czytaj" ? ` „${krok.cel}”` : "");
  li.append(co);
  if (krok.mysl) {
    const mysl = document.createElement("div");
    mysl.className = "mysl"; mysl.textContent = krok.mysl;
    li.append(mysl);
  }
  if (krok.uwaga) {
    const nie = document.createElement("div");
    nie.className = "nie"; nie.textContent = krok.uwaga;
    li.append(nie);
  }
  $("kroki").append(li);
  li.scrollIntoView({ block: "nearest" });
}

function pokazWynik(naglowek, tresc, koniec = false) {
  const pole = $("wynik");
  pole.replaceChildren();
  const b = document.createElement("b"); b.textContent = naglowek;
  pole.append(b, document.createTextNode(tresc));
  pole.classList.toggle("koniec", koniec);
  pole.hidden = false;
}

function ustawPrace(trwa) {
  pracuje = trwa;
  $("btn-wykonaj").disabled = trwa;
  $("cel").disabled = trwa;
  $("btn-stop").hidden = !trwa;
}

$("btn-stop").onclick = () => { przerwij = true; $("btn-stop").disabled = true; };

$("formularz").onsubmit = (zdarzenie) => {
  zdarzenie.preventDefault();
  const cel = $("cel").value.trim();
  if (pracuje || !cel) return;
  if (!karta || !/^https?:/.test(karta.url)) {
    pokazWynik("Nie mam strony do pracy.",
               "Otwórz w tej karcie stronę urzędu albo rejestru i spróbuj ponownie.");
    return;
  }
  $("wynik").hidden = true;
  // Prosba o zgode musi isc wprost z klikniecia - dlatego bez await przed nia.
  const cela = { id: karta.id, url: karta.url };
  chrome.permissions.request({ origins: [wzorzecZgody(cela.url)] })
    .then(zgoda => zgoda ? wykonaj(cel, cela)
      : pokazWynik("Bez zgody nie ruszę.", "Asystent pracuje tylko na stronach, na które pozwolisz."))
    .catch(() => pokazWynik("Na tej stronie nie mogę pracować.",
                            "Przeglądarka nie pozwala rozszerzeniom działać pod tym adresem."));
};

async function wykonaj(cel, cela) {
  przerwij = false;
  $("btn-stop").disabled = false;
  $("kroki").replaceChildren();
  $("wynik").hidden = true;
  $("ramki").hidden = true;
  ustawPrace(true);
  $("host").textContent = host(cela.url);

  const notarai = new Notarai(ustawienia.adres, ustawienia.token);
  const strona = new Strona(cela.id);
  let zlecenie = "", przebieg = null;
  try {
    zlecenie = await notarai.zlecKlikanie(cel, host(cela.url));
    przebieg = await prowadz(cel, strona,
      (c, stan, kroki) => notarai.krok(zlecenie, c, stan, kroki),
      { przerwij: () => przerwij, naKrok: dopiszKrok });
  } catch (blad) {
    if (blad instanceof BladTokenu) { ustawPrace(false); await odlaczLokalnie(); return; }
    pokazWynik("Nie udało się.", blad instanceof BladPolaczenia ? blad.message
      : "Coś poszło nie tak po stronie rozszerzenia. Spróbuj ponownie.");
  }

  if (przebieg) {
    let rodzaj = "koniec";
    if (przebieg.pytanie) { rodzaj = "pytanie"; pokazWynik("Teraz Ty.", przebieg.pytanie); }
    else if (przebieg.zatrzymano) {
      rodzaj = przerwij ? "przerwano" : "zatrzymano";
      pokazWynik("Zatrzymałem się.", przebieg.zatrzymano);
    } else pokazWynik("Gotowe.", przebieg.podsumowanie || "Zrobione.", true);
    notarai.koniec(zlecenie, przebieg.kroki.length, rodzaj).catch(() => {});
  } else if (zlecenie) {
    notarai.koniec(zlecenie, 0, "przerwano").catch(() => {});
  }

  if (strona.obce.length) {
    $("ramki-hosty").textContent = strona.obce.join(", ");
    $("ramki").dataset.hosty = JSON.stringify(strona.obce);
    $("ramki").hidden = false;
  }
  ustawPrace(false);
  odswiezKarte();
}

$("btn-ramki").onclick = () => {
  const hosty = JSON.parse($("ramki").dataset.hosty || "[]");
  chrome.permissions.request({ origins: hosty.map(h => `https://${h}/*`) })
    .then(zgoda => { if (zgoda) $("ramki").hidden = true; })
    .catch(() => {});
};

/* ---------- zlecenia z kolejki notarai ----------
   Dopoki panel jest otwarty, pyta notarai o robote zlecona ze sprawy:
   sprawdzenie w KRZ, wypelnienie formularza, polecenie "Klikamy". Zgoda na
   strone musi isc z klikniecia, wiec pierwsze zlecenie dla danego serwisu
   czeka na przycisk; nastepne ruszaja same. */

const PRZERWA_KOLEJKI_MS = 3000;
let kolejka = 0, czekaNaZgode = null;

function wzorceZgody(adres, zRodzenstwem = false) {
  const u = new URL(adres);
  const wzorce = [`${u.protocol}//${u.hostname}/*`];
  const czesci = u.hostname.split(".");
  // Formularz KRZ siedzi w ramce z sasiedniego adresu ministerstwa.
  if (zRodzenstwem && czesci.length >= 4 && /[a-z]/i.test(czesci.at(-1))) wzorce.push(`https://*.${czesci.slice(1).join(".")}/*`);
  return wzorce;
}

function opisZlecenia(z) {
  const tresc = z.tresc || {};
  if (z.rodzaj === "krz") {
    return { tytul: "Sprawdzenie w KRZ", adres: (tresc.portal || {}).adres, rodzenstwo: true,
             opis: `Notarai prosi o sprawdzenie w Krajowym Rejestrze Zadłużonych. Osób: ${(tresc.osoby || []).length}.` };
  }
  if (z.rodzaj === "formularz") {
    return { tytul: "Wypełnienie formularza", adres: tresc.adres,
             opis: "Notarai prosi o wpisanie danych ze sprawy w otwartym formularzu. Niczego nie wyślę." };
  }
  if (z.rodzaj === "klikamy") {
    return { tytul: "Polecenie ze sprawy", adres: karta && /^https?:/.test(karta.url) ? karta.url : "",
             opis: "Notarai prosi o wykonanie polecenia na stronie otwartej w tej karcie." };
  }
  return null;
}

async function pilnujKolejki() {
  const numer = ++kolejka;
  while (numer === kolejka && ustawienia.token) {
    if (!pracuje && !czekaNaZgode) {
      try {
        const lista = await new Notarai(ustawienia.adres, ustawienia.token).zlecenia();
        for (const z of lista) {
          if (numer !== kolejka || czekaNaZgode) break;
          await przyjmij(z);
        }
      } catch (blad) {
        if (blad instanceof BladTokenu) { await odlaczLokalnie(); return; }
        // zerwane lacze to stan przejsciowy - pytamy dalej
      }
    }
    await czekaj(PRZERWA_KOLEJKI_MS);
  }
}

async function przyjmij(z) {
  const notarai = new Notarai(ustawienia.adres, ustawienia.token);
  const opis = opisZlecenia(z);
  if (!opis) {
    await notarai.odeslij(z.id, { bledy: [`Rozszerzenie nie obsługuje zleceń rodzaju „${z.rodzaj}”. Zaktualizuj je.`] });
    return;
  }
  let origins;
  try { origins = wzorceZgody(opis.adres, opis.rodzenstwo); }
  catch {
    await notarai.odeslij(z.id, { bledy: [z.rodzaj === "klikamy"
      ? "W przeglądarce nie ma otwartej strony, na której mam pracować."
      : "Zlecenie nie podaje adresu strony."] });
    return;
  }
  if (await chrome.permissions.contains({ origins })) return wykonajZlecenie(z);
  czekaNaZgode = { z, origins };
  $("zgoda-tytul").textContent = opis.tytul;
  $("zgoda-opis").textContent = `${opis.opis} Strona: ${host(opis.adres)}.`;
  $("zgoda").hidden = false;
}

$("btn-zgoda").onclick = () => {
  if (!czekaNaZgode) return;
  const { z, origins } = czekaNaZgode;
  chrome.permissions.request({ origins }).then(zgoda => {
    if (!zgoda) return;                       // karta zostaje - mozna sprobowac ponownie
    czekaNaZgode = null;
    $("zgoda").hidden = true;
    wykonajZlecenie(z);
  }).catch(() => {});
};

$("btn-odmowa").onclick = async () => {
  if (!czekaNaZgode) return;
  const { z } = czekaNaZgode;
  $("zgoda").hidden = true;
  try {
    await new Notarai(ustawienia.adres, ustawienia.token)
      .odeslij(z.id, { bledy: ["Notariusz nie zezwolił rozszerzeniu na pracę na tej stronie."] });
  } catch { /* zlecenie i tak wygasnie */ }
  czekaNaZgode = null;
};

async function kartaZAdresem(prefiks) {
  if (kartaZTestu) return kartaZTestu;
  const traf = (await chrome.tabs.query({})).find(t => (t.url || "").startsWith(prefiks));
  return traf ? traf.id : null;
}

async function wykonajZlecenie(z) {
  if (pracuje) return;
  const notarai = new Notarai(ustawienia.adres, ustawienia.token);
  const tresc = z.tresc || {};
  $("kroki").replaceChildren();
  $("wynik").hidden = true;
  ustawPrace(true);
  $("btn-stop").hidden = true;                 // zlecen z kolejki nie przerywamy w pol osoby
  let raport;
  try {
    if (z.rodzaj === "krz") {
      const adres = (tresc.portal || {}).adres || "";
      let id = await kartaZAdresem(adres);
      if (id === null) id = (await chrome.tabs.create({ url: adres, active: true })).id;
      const strona = new Strona(id);
      raport = await wykonajKRZ(z, strona, { naPostep: (nr, ile, etykieta) => dopiszKrok(
        { nr, akcja: "krz", cel: etykieta || `osoba ${nr} z ${ile}`, mysl: "Dwa wyszukiwania w KRZ." }) });
      pokazWynik("Sprawdzenie w KRZ zakończone.",
                 `Sprawdzonych osób: ${raport.sprawdzenia.length}, błędów: ${raport.bledy.length}. ` +
                 "Wyniki są w sprawie w notarai.", !raport.bledy.length);
      pokazObceRamki(strona);
    } else if (z.rodzaj === "formularz") {
      const id = await kartaZAdresem(String(tresc.adres || "\u0000"));
      raport = await wykonajFormularz(z, id === null ? null : new Strona(id));
      raport.kroki.forEach((k, i) => dopiszKrok(
        { nr: i + 1, akcja: k.wykonano ? "wpisz" : "pominiete", cel: k.pole, uwaga: k.uwaga }));
      const wpisane = raport.kroki.filter(k => k.wykonano).length;
      pokazWynik(raport.bledy.length ? "Formularz: nie wszystko wpisane." : "Formularz wypełniony.",
                 raport.bledy.length ? raport.bledy.join("; ")
                   : `Wpisanych pól: ${wpisane}. Sprawdź je i wyślij samodzielnie.`, !raport.bledy.length);
    } else {
      const cela = { id: karta.id, url: karta.url };
      const przebieg = await prowadz(tresc.cel || "", new Strona(cela.id),
        (c, stan, kroki) => notarai.krok(z.id, c, stan, kroki), { naKrok: dopiszKrok });
      raport = { bledy: przebieg.zatrzymano ? [przebieg.zatrzymano] : [] };
      if (przebieg.pytanie) pokazWynik("Teraz Ty.", przebieg.pytanie);
      else if (przebieg.zatrzymano) pokazWynik("Zatrzymałem się.", przebieg.zatrzymano);
      else pokazWynik("Gotowe.", przebieg.podsumowanie || "Zrobione.", true);
    }
  } catch (blad) {
    if (blad instanceof BladTokenu) { ustawPrace(false); await odlaczLokalnie(); return; }
    raport = { bledy: ["Rozszerzenie nie dokończyło zlecenia."] };
    pokazWynik("Nie udało się.", blad instanceof BladPolaczenia ? blad.message
      : "Coś poszło nie tak po stronie rozszerzenia.");
  }
  try { await notarai.odeslij(z.id, raport); }
  catch { pokazWynik("Nie odesłałem wyniku.", "Brak połączenia z notarai. Zleć czynność ponownie."); }
  ustawPrace(false);
  odswiezKarte();
}

function pokazObceRamki(strona) {
  if (!strona.obce.length) return;
  $("ramki-hosty").textContent = strona.obce.join(", ");
  $("ramki").dataset.hosty = JSON.stringify(strona.obce);
  $("ramki").hidden = false;
}

/* ---------- start ---------- */

chrome.tabs.onActivated.addListener(odswiezKarte);
chrome.tabs.onUpdated.addListener((id, zmiana) => {
  if (zmiana.url || zmiana.status === "complete") odswiezKarte();
});

(async () => {
  const zapisane = await chrome.storage.local.get(["adres", "token"]);
  ustawienia = { adres: zapisane.adres || ADRES_DOMYSLNY, token: zapisane.token || "" };
  await odswiezKarte();
  pokazWidok();
})();

/* ---------- Ochrona przed phishingiem ----------
   Przelacznik. Dostep (widzenie adresow stron) pytamy DOPIERO przy wlaczeniu -
   instalacja zostaje waska. Wszystko liczy sie lokalnie (bezpieczna_strona.js
   w tle); nic nie wysylamy. */
const OCHRONA_PERM = { permissions: ["webNavigation", "downloads", "notifications"], origins: ["https://*/*"] };

async function odswiezPhishing() {
  const o = await chrome.storage.local.get("ochronaPhishing");
  const on = !!o.ochronaPhishing;
  if ($("chk-phishing")) $("chk-phishing").checked = on;
  if ($("phishing-stan")) $("phishing-stan").textContent = on
    ? "Włączona — ostrzegam na stronach przed podróbkami i ryzykownymi pobraniami."
    : "Wyłączona. Włącz, żeby ostrzegać przed phishingiem (poproszę wtedy o dostęp).";
}

if ($("chk-phishing")) {
  $("chk-phishing").addEventListener("change", async (e) => {
    if (e.target.checked) {
      let ok = false;
      try { ok = await chrome.permissions.request(OCHRONA_PERM); } catch (_) {}
      if (!ok) {
        e.target.checked = false;
        $("phishing-stan").textContent = "Bez dostępu nie mogę ostrzegać. Możesz włączyć ponownie w każdej chwili.";
        return;
      }
      await chrome.storage.local.set({ ochronaPhishing: true });
    } else {
      await chrome.storage.local.set({ ochronaPhishing: false });
      try { await chrome.permissions.remove(OCHRONA_PERM); } catch (_) {}
    }
    odswiezPhishing();
  });
  odswiezPhishing();
}
