/* Sprawdzenie w Krajowym Rejestrze Zadluzonych - zlecenie "krz" z kolejki.

   Odpowiednik krz_portal.przebieg + pomocnik/krz_cdp.py. CO zrobic w portalu
   (zakladki, odstep, wzorce rozpoznawania wyniku) przychodzi ze zleceniem z
   krz_portal.opis_portalu() - tu jest tylko JAK zrobic to w karcie notariusza.
   Dzieki temu po zmianie portalu poprawia sie jeden plik na serwerze.

   Tekst wyniku nie opuszcza przegladarki: rozpoznajemy go tutaj, a do notarai
   wraca status i krotki opis. W dzienniku panelu nie ma numerow PESEL.

   Rozszerzenie nie robi zrzutow ekranu (wymagaloby stalego dostepu do
   wszystkich stron). Wynik "wpis" albo nierozpoznany notariusz sprawdza
   w rejestrze samodzielnie - opis mowi to wprost. */

const NAPIS_FORMULARZA = "Wyszukaj";
const CZEKANIE_NA_WYNIK_S = 15;
const czekajMs = (ms) => new Promise(r => setTimeout(r, ms));

export function maskuj(pesel) {
  const cyfry = String(pesel || "").replace(/\D/g, "");
  return cyfry.length === 11 ? cyfry.slice(0, 4) + "*".repeat(7) : "*".repeat(Math.max(cyfry.length, 1));
}

/* Wzorce z serwera: { zrodlo, flagi }. Bledny opis portalu to blad zlecenia. */
export function wzorce(portal) {
  const z = (portal && portal.wzorce) || {};
  if (!z.brak || !z.wpis || !z.stale || !portal.adres || !portal.zakladki) {
    throw new Error("Zlecenie nie opisuje portalu KRZ. Zaktualizuj notarai.");
  }
  const zbuduj = (w, dodatkowe = "") => new RegExp(w.zrodlo, [...new Set((w.flagi || "") + dodatkowe)].join(""));
  return { brak: zbuduj(z.brak), wpis: zbuduj(z.wpis), stale: zbuduj(z.stale, "g") };
}

/* Heurystyka na tekscie wyniku. Zawsze do potwierdzenia przez czlowieka. */
export function rozpoznaj(tekst, w) {
  const t = String(tekst || "").split(/\s+/).filter(Boolean).join(" ");
  if (w.brak.test(t)) return ["brak_wpisu", "portal: nie znaleziono pozycji"];
  if (w.wpis.test(t.replace(w.stale, " "))) {
    return ["wpis", "portal: znaleziono pozycje - SPRAWDŹ W REJESTRZE"];
  }
  return ["blad", "nie rozpoznano wyniku - sprawdź w rejestrze"];
}

/* Jeden status z dwoch zakladek. Wpis gdziekolwiek przewaza nad brakiem. */
export function zlacz(wyniki) {
  if (wyniki.some(w => w.status === "wpis")) return "wpis";
  if (wyniki.length && wyniki.every(w => w.status === "brak_wpisu")) return "brak_wpisu";
  return "blad";
}

/* Portal KRZ w karcie przegladarki. `strona` to Strona z strona.js. */
export class PortalKRZ {
  constructor(strona, portal, spij = czekajMs) {
    this.strona = strona;
    this.portal = portal;
    this.w = wzorce(portal);
    this.spij = spij;
    this.ramka = null;
  }

  async otworz() {
    this.ramka = null;
    await this.strona.otworz(this.portal.adres);
    await this.spij(2000);                       // portal dociaga interfejs
    await this._klikJesliJest("Akceptuj");       // zgoda na ciasteczka
    await this._klikJesliJest("Wyszukiwanie podmiotów");
    const traf = await this.strona.znajdzTekst(NAPIS_FORMULARZA, 20);
    if (!traf) {
      await this.strona.ramki().catch(() => []);   // odswieza liste obcych ramek
      const obce = (this.strona.obce || []).join(", ");
      throw new Error("Nie znalazłem formularza KRZ na stronie." +
                      (obce ? ` Część strony pochodzi z: ${obce} - zezwól na ten adres.` : ""));
    }
    this.ramka = traf.ramka;
  }

  async _klikJesliJest(fragment) {
    try {
      const traf = await this.strona.znajdzTekst(fragment);
      if (traf) { await this.strona.kliknij(traf); await this.spij(800); }
    } catch { /* tego elementu moze nie byc */ }
  }

  async _elementy() {
    const ramka = (await this.strona.ramki()).find(r => r.ramka === this.ramka);
    return ramka ? ramka.elementy.map(e => ({ ...e, ramka: this.ramka })) : [];
  }

  /* Dokladnie taki napis: "Wyszukaj" zawiera sie w "Wyszukiwanie podmiotow". */
  async _przycisk(nazwa) {
    const szukane = nazwa.trim().toLowerCase();
    return (await this._elementy()).find(e =>
      /^(button|input:submit|input:button)/.test(e.rola) &&
      (e.opis || "").trim().toLowerCase() === szukane) || null;
  }

  async wybierzZakladke(nazwa) {
    const traf = await this.strona.znajdzTekst(nazwa, 5, this.ramka);
    if (!traf) throw new Error(`Nie znalazłem zakładki „${nazwa}” w KRZ.`);
    await this.strona.kliknij(traf);
    await this.spij(800);
  }

  async wpiszIdentyfikator(wartosc) {
    const pole = (await this._elementy()).find(e =>
      /^(input|textarea)/.test(e.rola) && (e.opis || "").toLowerCase().includes("identyfikator"));
    if (!pole) throw new Error("Nie znalazłem pola Identyfikator w formularzu KRZ.");
    await this.strona.wpisz(pole, wartosc);
  }

  async wyszukaj() {
    const przycisk = await this._przycisk("Wyszukaj");
    if (!przycisk) throw new Error("Nie znalazłem przycisku Wyszukaj w formularzu KRZ.");
    await this.strona.kliknij(przycisk);
    // Czekamy na komunikat portalu, a nie na staly czas.
    for (const koniec = Date.now() + CZEKANIE_NA_WYNIK_S * 1000; Date.now() < koniec;) {
      await this.spij(500);
      const tekst = await this.tekstWyniku();
      if (this.w.brak.test(tekst) || this.w.wpis.test(tekst.replace(this.w.stale, " "))) return;
    }
  }

  async wyczysc() {
    const przycisk = await this._przycisk("Wyczyść");
    if (przycisk) { await this.strona.kliknij(przycisk); await this.spij(500); }
  }

  async tekstWyniku() {
    try {
      const ramka = (await this.strona.ramki()).find(r => r.ramka === this.ramka);
      return ramka ? ramka.tekst : "";
    } catch { return ""; }
  }
}

/* Dwa wyszukiwania po PESEL dla jednej osoby. */
export async function sprawdzOsobe(portal, pesel, etykieta, opis, spij = czekajMs) {
  const cyfry = String(pesel || "").replace(/\D/g, "");
  if (cyfry.length !== 11) throw new Error("PESEL musi mieć 11 cyfr");
  const wyniki = [];
  await portal.otworz();
  for (const [klucz, nazwa] of Object.entries(opis.zakladki)) {
    await portal.wybierzZakladke(nazwa);
    await portal.wpiszIdentyfikator(cyfry);
    await portal.wyszukaj();
    const [status, tresc] = rozpoznaj(await portal.tekstWyniku(), portal.w);
    wyniki.push({ zakladka: klucz, status, opis: tresc });
    await portal.wyczysc();
    await spij((opis.odstep_s || 2) * 1000);     // odstep miedzy zapytaniami
  }
  let szczegoly = wyniki.map(w => `${w.zakladka}: ${w.opis}`).join("; ") +
                  " (rozszerzenie przeglądarki, bez zrzutu ekranu)";
  if (etykieta) szczegoly = `${etykieta} - ${szczegoly}`;
  return { status: zlacz(wyniki), szczegoly };
}

/* Cale zlecenie "krz". Blad przy jednej osobie nie przerywa pozostalych. */
export async function wykonajKRZ(zlecenie, strona, opcje = {}) {
  const tresc = zlecenie.tresc || {};
  const osoby = tresc.osoby || [];
  if (!osoby.length) return { sprawdzenia: [], bledy: ["Zlecenie nie wskazuje żadnej osoby."] };
  const spij = opcje.spij || czekajMs;
  const portal = (opcje.portal || ((s, o) => new PortalKRZ(s, o, spij)))(strona, tresc.portal);
  const sprawdzenia = [], bledy = [];
  for (const [i, osoba] of osoby.entries()) {
    const etykieta = osoba.etykieta || "";
    if (opcje.naPostep) opcje.naPostep(i + 1, osoby.length, etykieta);
    try {
      const wynik = await sprawdzOsobe(portal, osoba.pesel, etykieta, tresc.portal, spij);
      sprawdzenia.push({ rejestr: "KRZ", pesel: osoba.pesel, status: wynik.status,
                         szczegoly: wynik.szczegoly, etykieta, zrodlo: tresc.portal.adres });
    } catch (blad) {
      // Komunikaty tego modulu nie niosa numerow; cudzych nie przepisujemy.
      const opis = /KRZ|PESEL musi/.test(String(blad && blad.message)) ? blad.message : "błąd strony";
      bledy.push(`${etykieta || "jedna ze stron"}: nie dokończyłem sprawdzenia (${opis})`);
    }
  }
  return { sprawdzenia, bledy };
}
