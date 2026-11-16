/* Rece rozszerzenia na stronie: odczyt i czynnosci przez chrome.scripting.

   Pracujemy w prawdziwej karcie notariusza - z jego sesja, certyfikatem i
   wtyczka podpisu. Nie uzywamy chrome.debugger (zolty pasek "debugowanie"
   i pelna wladza nad przegladarka), tylko skryptu wstrzykiwanego do strony,
   na ktora notariusz dal zgode.

   Kod wstrzykiwany dziala we wszystkich ramkach strony, do ktorych mamy
   zgode - formularze urzedowe lubia siedziec w iframe (KRZ tak ma). */

import { WYSYLKA_ZRODLO } from "./silnik.js";

const LIMIT_ELEMENTOW = 120;
const LIMIT_TEKSTU = 4000;

/* Ta funkcja jest przenoszona do strony jako tekst, wiec musi byc
   samowystarczalna: zadnych odwolan do zmiennych spoza niej. */
export function naStronie(polecenie) {
  const sciezka = (el) => {
    if (el.id) return "#" + CSS.escape(el.id);
    const kroki = [];
    let w = el;
    while (w && w.nodeType === 1 && w !== document.body) {
      const rodzic = w.parentNode;
      if (!rodzic || !rodzic.children) break;
      const rodzenstwo = [...rodzic.children].filter(e => e.tagName === w.tagName);
      kroki.unshift(w.tagName.toLowerCase() + ":nth-of-type(" + (rodzenstwo.indexOf(w) + 1) + ")");
      w = rodzic;
    }
    return "body > " + kroki.join(" > ");
  };
  const widoczny = (el) => {
    const p = el.getBoundingClientRect();
    return p.width > 0 && p.height > 0 && getComputedStyle(el).visibility !== "hidden";
  };
  const opis = (el) => (
    el.getAttribute("aria-label") || el.placeholder || el.title ||
    (el.labels && el.labels[0] ? el.labels[0].textContent : "") ||
    (el.value && (el.type === "submit" || el.type === "button") ? el.value : "") ||
    el.textContent || "").replace(/\s+/g, " ").trim().slice(0, 100);

  if (polecenie.co === "stan") {
    const wybor = "a[href], button, input, select, textarea, [role=button], [onclick], [contenteditable]";
    const tu = location.hostname;
    const obce = [...document.querySelectorAll("iframe[src]")].map(r => {
      try { return new URL(r.src, location.href).hostname; } catch { return ""; }
    }).filter(h => h && h !== tu);
    return {
      adres: location.href,
      glowna: window === window.top,
      tekst: (document.body ? document.body.innerText : "").replace(/\s+\n/g, "\n")
        .slice(0, polecenie.limitTekstu),
      obce: [...new Set(obce)],
      elementy: [...document.querySelectorAll(wybor)]
        .filter(el => el.type !== "hidden" && widoczny(el))
        .slice(0, polecenie.limitElementow)
        .map(el => ({
          rola: el.tagName.toLowerCase() + (el.type ? ":" + el.type : ""),
          typ: String(el.type || "").toLowerCase(),
          opis: opis(el),
          selektor: sciezka(el),
        })),
    };
  }

  if (polecenie.co === "szukaj") {
    // Najglebszy widoczny element z takim napisem. Portale urzedowe nie
    // gwarantuja nazw klas, ale gwarantuja napisy - te widzi czlowiek.
    const szukane = polecenie.fragment.toLowerCase();
    const pasuje = [...document.querySelectorAll("body *")].filter(e =>
      widoczny(e) && (e.textContent || "").toLowerCase().includes(szukane));
    if (!pasuje.length) return { selektor: null };
    pasuje.sort((a, b) => (a.textContent || "").length - (b.textContent || "").length);
    return { selektor: sciezka(pasuje[0]) };
  }

  let el = null;
  try { el = document.querySelector(polecenie.selektor); } catch { /* zly selektor = brak */ }
  if (polecenie.co === "jest") return { jest: !!el };
  if (!el) return { blad: "Nie znalazłem tego elementu na stronie - strona się zmieniła." };

  if (polecenie.co === "zaznacz") {
    if (!!el.checked !== !!polecenie.tak) el.click();
    return { ok: true };
  }

  if (polecenie.co === "kliknij") {
    // Drugi straznik: strona mogla sie zmienic miedzy odczytem a kliknieciem.
    if (new RegExp(polecenie.wysylka, "i").test(opis(el))) return { odmowa: "wysylka" };
    el.scrollIntoView({ block: "center" });
    el.click();
    return { ok: true };
  }

  if (polecenie.co === "wpisz") {
    if (String(el.type || "").toLowerCase() === "password") return { odmowa: "haslo" };
    el.scrollIntoView({ block: "center" });
    el.focus();
    if ("value" in el) {
      // Ustawienie przez pierwotny setter: React i Angular widza wtedy zmiane.
      const wzor = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype
        : el instanceof HTMLSelectElement ? HTMLSelectElement.prototype
        : HTMLInputElement.prototype;
      const ustaw = Object.getOwnPropertyDescriptor(wzor, "value");
      if (ustaw && ustaw.set) ustaw.set.call(el, polecenie.tekst); else el.value = polecenie.tekst;
    } else {
      el.textContent = polecenie.tekst;
    }
    for (const nazwa of ["input", "change"]) {
      el.dispatchEvent(new Event(nazwa, { bubbles: true }));
    }
    const jest = ("value" in el ? el.value : el.textContent) || "";
    if (polecenie.tekst && !jest) {
      return { blad: "Pole nie przyjęło wartości. Może być zablokowane albo wymagać wcześniejszego wyboru." };
    }
    return { ok: true };
  }

  if (polecenie.co === "wybierz") {
    if (!el.options) return { blad: "To nie jest lista wyboru." };
    const szukane = polecenie.tekst.trim().toLowerCase();
    const opcja = [...el.options].find(o =>
      (o.label || "").trim().toLowerCase() === szukane ||
      (o.text || "").trim().toLowerCase() === szukane ||
      (o.value || "").trim().toLowerCase() === szukane);
    if (!opcja) return { blad: "Na liście nie ma takiej pozycji." };
    el.value = opcja.value;
    for (const nazwa of ["input", "change"]) {
      el.dispatchEvent(new Event(nazwa, { bubbles: true }));
    }
    return { ok: true };
  }
  return { blad: "Nieznane polecenie." };
}

const czekaj = (ms) => new Promise(r => setTimeout(r, ms));

/* Jedna karta przegladarki widziana oczami silnika. */
export class Strona {
  constructor(karta, api = chrome) {
    this.karta = karta;
    this.api = api;
    this.obce = [];   // hosty ramek, do ktorych nie mamy zgody
  }

  async _wstrzyknij(cel, polecenie) {
    try {
      return await this.api.scripting.executeScript({ target: cel, func: naStronie, args: [polecenie] });
    } catch (blad) {
      throw new Error("Nie mam dostępu do tej strony. Otwórz stronę urzędu albo rejestru " +
                      "i uruchom mnie ponownie.");
    }
  }

  async _ustabilizuj() {
    await czekaj(700);
    for (let i = 0; i < 40; i++) {
      const karta = await this.api.tabs.get(this.karta);
      if (karta.status === "complete") return;
      await czekaj(250);
    }
  }

  async stan() {
    const wyniki = await this._wstrzyknij(
      { tabId: this.karta, allFrames: true },
      { co: "stan", limitElementow: LIMIT_ELEMENTOW, limitTekstu: LIMIT_TEKSTU });
    const ramki = wyniki.filter(w => w && w.result);
    const glowna = ramki.find(w => w.result.glowna) || ramki[0];
    if (!glowna) throw new Error("Strona nie odpowiada. Odśwież ją i spróbuj ponownie.");

    const elementy = [];
    let tekst = glowna.result.tekst;
    const widziane = new Set(ramki.map(w => {
      try { return new URL(w.result.adres).hostname; } catch { return ""; }
    }));
    const obce = new Set();
    for (const ramka of [glowna, ...ramki.filter(w => w !== glowna)]) {
      if (ramka !== glowna && ramka.result.tekst) {
        tekst = (tekst + "\n" + ramka.result.tekst).slice(0, LIMIT_TEKSTU);
      }
      for (const h of ramka.result.obce) if (!widziane.has(h)) obce.add(h);
      for (const e of ramka.result.elementy) {
        if (elementy.length >= LIMIT_ELEMENTOW) break;
        elementy.push({ ...e, nr: elementy.length + 1, ramka: ramka.frameId });
      }
    }
    this.obce = [...obce];
    return { adres: glowna.result.adres, tekst, elementy };
  }

  /* --- dla zlecen z kolejki (KRZ, formularze): praca po ramkach i selektorach --- */

  /* Kazda ramka strony osobno: { ramka, adres, tekst, elementy }. */
  async ramki(limitElementow = 300) {
    const wyniki = await this._wstrzyknij(
      { tabId: this.karta, allFrames: true },
      { co: "stan", limitElementow, limitTekstu: 20000 });
    const ramki = wyniki.filter(w => w && w.result).map(w => ({ ramka: w.frameId, ...w.result }));
    const widziane = new Set(ramki.map(r => {
      try { return new URL(r.adres).hostname; } catch { return ""; }
    }));
    this.obce = [...new Set(ramki.flatMap(r => r.obce))].filter(h => !widziane.has(h));
    return ramki;
  }

  async adres() {
    return (await this.api.tabs.get(this.karta)).url || "";
  }

  async _wRamkach(polecenie) {
    const wyniki = await this._wstrzyknij({ tabId: this.karta, allFrames: true }, polecenie);
    return wyniki.filter(w => w && w.result).map(w => ({ ramka: w.frameId, ...w.result }));
  }

  /* Numer ramki, w ktorej jest element o tym selektorze; null po uplywie czasu. */
  async ramkaZSelektorem(selektor, sekundy = 15) {
    for (const koniec = Date.now() + sekundy * 1000; ;) {
      // Strona w trakcie przeladowania chwilowo nie przyjmuje skryptu - ponawiamy.
      const traf = (await this._wRamkach({ co: "jest", selektor }).catch(() => [])).find(w => w.jest);
      if (traf) return traf.ramka;
      if (Date.now() >= koniec) return null;
      await czekaj(400);
    }
  }

  /* { ramka, selektor } elementu z takim napisem; null po uplywie czasu. */
  async znajdzTekst(fragment, sekundy = 0, ramka = null) {
    for (const koniec = Date.now() + sekundy * 1000; ;) {
      const traf = (await this._wRamkach({ co: "szukaj", fragment }).catch(() => []))
        .find(w => w.selektor && (ramka === null || w.ramka === ramka));
      if (traf) return { ramka: traf.ramka, selektor: traf.selektor };
      if (Date.now() >= koniec) return null;
      await czekaj(400);
    }
  }

  async zaznacz(el, tak) {
    await this._czynnosc(el, { co: "zaznacz", tak });
  }

  async _czynnosc(el, polecenie) {
    const wyniki = await this._wstrzyknij(
      { tabId: this.karta, frameIds: [el.ramka] },
      { ...polecenie, selektor: el.selektor });
    const wynik = (wyniki[0] && wyniki[0].result) || { blad: "Strona nie odpowiedziała." };
    if (wynik.odmowa === "wysylka") {
      throw new Error("Ten element zmienił się w przycisk wysyłki albo podpisu. Zatrzymuję się.");
    }
    if (wynik.odmowa === "haslo") throw new Error("To pole hasła. Hasło i PIN wpisujesz wyłącznie Ty.");
    if (wynik.blad) throw new Error(wynik.blad);
  }

  async kliknij(el) {
    await this._czynnosc(el, { co: "kliknij", wysylka: WYSYLKA_ZRODLO });
    await this._ustabilizuj();
  }

  async wpisz(el, tekst) {
    await this._czynnosc(el, { co: "wpisz", tekst });
  }

  async wybierz(el, tekst) {
    await this._czynnosc(el, { co: "wybierz", tekst });
    await czekaj(300);
  }

  async otworz(adres) {
    await this.api.tabs.update(this.karta, { url: adres });
    await this._ustabilizuj();
  }
}
