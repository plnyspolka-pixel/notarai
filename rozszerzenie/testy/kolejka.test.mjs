/* Zlecenia z kolejki notarai wykonywane w rozszerzeniu: KRZ i formularze. */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { maskuj, wzorce, rozpoznaj, zlacz, wykonajKRZ, PortalKRZ } from "../krz.js";
import { wykonajFormularz, plan } from "../formularz.js";

// Opis portalu dokladnie taki, jaki wysyla serwer (krz_portal.opis_portalu()).
// Zgodnosc pliku z serwerem pilnuje test_rozszerzenie.py.
const PORTAL = JSON.parse(readFileSync(new URL("./portal-krz.json", import.meta.url), "utf8"));

/* ---------- KRZ ---------- */

test("wzorce z serwera dzialaja w JavaScripcie tak jak w Pythonie", () => {
  const w = wzorce(PORTAL);
  assert.equal(rozpoznaj("Nie zostały znalezione żadne pozycje dla podanych kryteriów wyszukiwania.", w)[0], "brak_wpisu");
  assert.equal(rozpoznaj("Sygnatura\nPostępowanie upadłościowe, numer sprawy WA1M/GUp/1/2026", w)[0], "wpis");
  // Stale napisy strony (zakladki, "Sygnatura") same nie sa wpisem.
  assert.equal(rozpoznaj("Osoba fizyczna nieprowadząca działalności gospodarczej Sygnatura zakładka 1 z 3", w)[0], "blad");
  assert.equal(rozpoznaj("", w)[0], "blad");
  assert.throws(() => wzorce({}), /Zaktualizuj/);
});

test("maskuj i zlacz jak w krz_portal", () => {
  assert.equal(maskuj("44051401359"), "4405*******");
  assert.equal(maskuj("123"), "***");
  assert.equal(zlacz([{ status: "brak_wpisu" }, { status: "wpis" }]), "wpis");
  assert.equal(zlacz([{ status: "brak_wpisu" }, { status: "brak_wpisu" }]), "brak_wpisu");
  assert.equal(zlacz([{ status: "brak_wpisu" }, { status: "blad" }]), "blad");
  assert.equal(zlacz([]), "blad");
});

function atrapaPortalu(teksty, psujDla = []) {
  let i = 0;
  const wpisane = [];
  return {
    wpisane, w: wzorce(PORTAL),
    async otworz() {}, async wybierzZakladke() {}, async wyszukaj() {}, async wyczysc() {},
    async wpiszIdentyfikator(v) {
      if (psujDla.includes(v)) throw new Error("portal odmówił dla " + v);
      wpisane.push(v);
    },
    async tekstWyniku() { return teksty[i++ % teksty.length]; },
  };
}

test("KRZ: kazda osoba, dwie zakladki, blad jednej nie przerywa reszty", async () => {
  const portal = atrapaPortalu(["Nie znaleziono"], ["85031512331"]);
  const zlecenie = { id: "z1", rodzaj: "krz", tresc: { portal: PORTAL, osoby: [
    { pesel: "44051401359", etykieta: "zbywca" }, { pesel: "85031512331", etykieta: "nabywca" },
    { pesel: "123", etykieta: "świadek" }] } };
  const raport = await wykonajKRZ(zlecenie, {}, { portal: () => portal, spij: async () => {} });
  assert.equal(raport.sprawdzenia.length, 1);
  assert.equal(raport.sprawdzenia[0].status, "brak_wpisu");
  assert.equal(raport.sprawdzenia[0].zrodlo, PORTAL.adres);
  assert.match(raport.sprawdzenia[0].szczegoly, /^zbywca - prowadzaca: .*bez zrzutu/);
  assert.deepEqual(portal.wpisane, ["44051401359", "44051401359"]);
  assert.equal(raport.bledy.length, 2);
  // Komunikat bledu nie przepisuje cudzej tresci - a wiec i numeru.
  assert.equal(JSON.stringify(raport.bledy).includes("85031512331"), false);
  assert.match(raport.bledy[1], /PESEL musi/);
});

test("KRZ: zlecenie bez osob", async () => {
  const raport = await wykonajKRZ({ tresc: { portal: PORTAL, osoby: [] } }, {});
  assert.deepEqual(raport.sprawdzenia, []);
  assert.equal(raport.bledy.length, 1);
});

test("KRZ: przycisk musi miec dokladnie taki napis", async () => {
  const strona = { ramki: async () => [{ ramka: 3, tekst: "", elementy: [
    { rola: "a", opis: "Wyszukiwanie podmiotów", selektor: "#a" },
    { rola: "button:submit", opis: "Wyszukaj", selektor: "#b" }] }] };
  const portal = new PortalKRZ(strona, PORTAL, async () => {});
  portal.ramka = 3;
  assert.deepEqual(await portal._przycisk("Wyszukaj"),
                   { rola: "button:submit", opis: "Wyszukaj", selektor: "#b", ramka: 3 });
});

/* ---------- formularz ---------- */

function atrapaStrony(adres, opcje = {}) {
  const dziennik = [];
  return {
    dziennik,
    async adres() { return adres; },
    async ramkaZSelektorem(s) { return (opcje.brak || []).includes(s) ? null : 0; },
    async wpisz(el, v) {
      if (el.selektor === "#pin") throw new Error("To pole hasła. Hasło i PIN wpisujesz wyłącznie Ty.");
      dziennik.push(["wpisz", el.selektor, v]);
    },
    async wybierz(el, v) { dziennik.push(["wybierz", el.selektor, v]); },
    async zaznacz(el, tak) { dziennik.push(["zaznacz", el.selektor, tak]); },
  };
}

const ADRES = "https://rejestr.example.gov.pl/formularz";
const formularz = (zmiany = {}) => ({ id: "f1", rodzaj: "formularz", tresc: {
  system: "probny", adres: ADRES, gotowosc: "#pesel",
  przycisk_wysylki: "#wyslij", status_mapowania: "gotowe", tryb: "faktyczny",
  kroki: [{ pole: "PESEL", selektor: "#pesel", typ: "tekst", wartosc: "44051401359" },
          { pole: "Rodzaj", selektor: "#rodzaj", typ: "lista", wartosc: "Sprzedaż" },
          { pole: "Zgoda", selektor: "#zgoda", typ: "pole_wyboru", wartosc: "tak" },
          { pole: "Uwagi", selektor: "#uwagi", typ: "tekst", wartosc: null }], ...zmiany } });

test("formularz: wpisuje pola i nie zwraca wartosci w raporcie", async () => {
  const s = atrapaStrony(ADRES + "?krok=1");
  const raport = await wykonajFormularz(formularz(), s);
  assert.deepEqual(s.dziennik, [["wpisz", "#pesel", "44051401359"],
                                ["wybierz", "#rodzaj", "Sprzedaż"], ["zaznacz", "#zgoda", true]]);
  assert.deepEqual(raport.kroki.map(k => k.wykonano), [true, true, true, false]);
  assert.equal(raport.kroki[3].uwaga, "brak wartości");
  assert.deepEqual(raport.bledy, []);
  assert.equal(JSON.stringify(raport).includes("44051401359"), false);
});

test("formularz: pole celujace w przycisk wysylki odrzuca cale zlecenie", async () => {
  const s = atrapaStrony(ADRES);
  const z = formularz();
  z.tresc.kroki.push({ pole: "Wyślij", selektor: " #wyslij ", typ: "pole_wyboru", wartosc: "tak" });
  const raport = await wykonajFormularz(z, s);
  assert.deepEqual(s.dziennik, []);
  assert.match(raport.bledy[0], /przycisku wysyłki/);
});

test("formularz: szkic, zla strona, niepelny adres, niegotowy, pusty - nic nie wpisane", async () => {
  for (const [zmiany, adres, wzorzec] of [
    [{ status_mapowania: "szkic" }, ADRES, /szkic/],
    [{}, "https://inny.example.com/formularz", /nie jest formularzem/],
    [{ adres: "https://" }, "https://cokolwiek.example.com/", /pełnego adresu/],
    [{ gotowosc: "#nie-ma" }, ADRES, /nie jest gotowy/],
    [{ kroki: [] }, ADRES, /niekompletne/],
  ]) {
    const s = atrapaStrony(adres, { brak: ["#nie-ma"] });
    const raport = await wykonajFormularz(formularz(zmiany), s);
    assert.deepEqual(s.dziennik, []);
    assert.match(raport.bledy[0], wzorzec);
  }
  assert.match((await wykonajFormularz(formularz(), null)).bledy[0], /nie jest formularzem/);
});

test("formularz: tryb podgladu niczego nie dotyka", async () => {
  const s = atrapaStrony(ADRES);
  const podglad = await wykonajFormularz(formularz({ tryb: "podglad" }), s);
  assert.deepEqual([s.dziennik, podglad.bledy], [[], []]);
  assert.equal(plan(formularz().tresc).length, 4);
});

test("formularz: pole hasla i brakujace pole to blad kroku, reszta idzie dalej", async () => {
  const s = atrapaStrony(ADRES, { brak: ["#rodzaj"] });
  const z = formularz();
  z.tresc.kroki[0] = { pole: "PIN", selektor: "#pin", typ: "tekst", wartosc: "1234" };
  const raport = await wykonajFormularz(z, s);
  assert.deepEqual(s.dziennik, [["zaznacz", "#zgoda", true]]);
  assert.match(raport.bledy[0], /^PIN: To pole hasła/);
  assert.match(raport.bledy[1], /^Rodzaj: Nie znalazłem pola/);
  assert.equal(JSON.stringify(raport).includes("1234"), false);
});
