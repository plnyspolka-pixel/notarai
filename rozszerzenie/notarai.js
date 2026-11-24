/* Rozmowa rozszerzenia z notarai.

   Rozszerzenie laczy sie z kancelaria tak samo jak pomocnik: prosi o kod,
   notariusz klika "Polacz" w zalogowanej notarai, rozszerzenie odbiera wlasny
   token. Token otwiera wylacznie /api/pomocnik/ - spraw kancelarii nim nie
   obejrzysz - i nie wychodzi poza adres notarai.

   Model stoi po stronie serwera (Bedrock, Frankfurt). Przegladarka notariusza
   dostaje gotowa czynnosc do wykonania, a nie klucze do modelu. */

export const ADRES_DOMYSLNY = "https://app.notarai.pl";
export const WERSJA = "0.2";

export class BladPolaczenia extends Error {}
export class BladTokenu extends BladPolaczenia {}
export class KodNieaktualny extends BladPolaczenia {}

export class Notarai {
  constructor(adres = ADRES_DOMYSLNY, token = "", pobierz = (...a) => fetch(...a)) {
    this.adres = adres.replace(/\/+$/, "");
    this.token = token;
    this._pobierz = pobierz;
  }

  async _zadanie(sciezka, dane) {
    const naglowki = { "Content-Type": "application/json" };
    if (this.token) naglowki.Authorization = "Bearer " + this.token;
    let odp;
    try {
      odp = await this._pobierz(this.adres + sciezka, {
        method: dane === undefined ? "GET" : "POST",
        headers: naglowki,
        body: dane === undefined ? undefined : JSON.stringify(dane),
      });
    } catch {
      throw new BladPolaczenia("Nie mogę połączyć się z notarai. Sprawdź internet.");
    }
    if (odp.status === 401) throw new BladTokenu("Ta przeglądarka nie jest już połączona z kancelarią.");
    if (odp.status === 410) throw new KodNieaktualny("Kod połączenia wygasł.");
    let tresc = null;
    try { tresc = await odp.json(); } catch { /* pusta odpowiedz */ }
    if (!odp.ok) {
      const opis = tresc && typeof tresc.detail === "string" ? tresc.detail : "";
      const blad = new BladPolaczenia(opis || `notarai odpowiedziało błędem ${odp.status}.`);
      blad.kod = odp.status;
      throw blad;
    }
    return { kod: odp.status, tresc };
  }

  async poprosOKod(nazwa) {
    return (await this._zadanie("/api/pomocnik/parowanie", { nazwa })).tresc || {};
  }

  /* Token, gdy notariusz potwierdzil. null, dopoki czeka. */
  async odbierzToken(kod, sekret) {
    const odp = await this._zadanie(`/api/pomocnik/parowanie/${encodeURIComponent(kod)}`, { sekret });
    return odp.kod === 200 && odp.tresc ? odp.tresc.token || null : null;
  }

  async odlacz() {
    await this._zadanie("/api/pomocnik/odlacz", {});
  }

  /* Zlecenia z kolejki kancelarii (KRZ, formularze, polecenia ze sprawy).
     Samo pytanie jest dla notarai znakiem, ze jest komu zlecac. */
  async zlecenia() {
    const lista = (await this._zadanie(`/api/pomocnik/zlecenia?wersja=r${WERSJA}`)).tresc;
    return Array.isArray(lista) ? lista : [];
  }

  async odeslij(zlecenie, raport) {
    await this._zadanie(`/api/pomocnik/zlecenia/${zlecenie}/wynik`, raport);
  }

  async wyslijPodglad(zlecenie, kadr) {
    await this._zadanie(`/api/pomocnik/podglad/${encodeURIComponent(zlecenie)}`, kadr);
  }

  async zlecKlikanie(cel, host) {
    return (await this._zadanie("/api/pomocnik/klikamy", { cel, host })).tresc.zlecenie;
  }

  /* Przeciazony model (503) to stan przejsciowy: czekamy i pytamy jeszcze raz. */
  async krok(zlecenie, cel, stan, kroki, czekaj = (ms) => new Promise(r => setTimeout(r, ms))) {
    for (let proba = 0; ; proba++) {
      try {
        return (await this._zadanie(`/api/pomocnik/klikamy/${zlecenie}/krok`,
                                    { cel, stan, kroki })).tresc || {};
      } catch (blad) {
        if (blad.kod !== 503 || proba >= 2) throw blad;
        await czekaj(15000);
      }
    }
  }

  async koniec(zlecenie, krokow, wynik) {
    await this._zadanie(`/api/pomocnik/klikamy/${zlecenie}/koniec`, { krokow, wynik });
  }
}

export function adresPolaczenia(adres, kod) {
  return `${adres.replace(/\/+$/, "")}/#polacz=${kod}`;
}
