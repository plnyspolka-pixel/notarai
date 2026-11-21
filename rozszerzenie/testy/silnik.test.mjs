/* Zabezpieczenia silnika: to one, a nie polecenie dla modelu, pilnuja, zeby
   asystent niczego nie wyslal, nie podpisal i nie wpisal hasla. */
import test from "node:test";
import assert from "node:assert/strict";
import { prowadz, WYSYLKA, wolnoWejsc, stanDlaModelu } from "../silnik.js";
import { Notarai, BladTokenu, KodNieaktualny, adresPolaczenia } from "../notarai.js";

function strona(elementy, adres = "https://rejestr.example.gov.pl/formularz") {
  const dziennik = [];
  return {
    dziennik, adres,
    async stan() {
      return { adres: this.adres, tekst: "Formularz",
               elementy: elementy.map((e, i) => ({ nr: i + 1, ramka: 0, selektor: "#e" + i, ...e })) };
    },
    async kliknij(el) { dziennik.push(["kliknij", el.opis]); },
    async wpisz(el, tekst) { dziennik.push(["wpisz", el.opis, tekst]); },
    async wybierz(el, tekst) { dziennik.push(["wybierz", el.opis, tekst]); },
    async otworz(adres) { dziennik.push(["otworz", adres]); this.adres = adres; },
  };
}

const kolejno = (...odpowiedzi) => async () => odpowiedzi.shift() || { akcja: "koniec" };

test("wpisuje, klika zwykly przycisk i konczy", async () => {
  const s = strona([{ rola: "input:text", typ: "text", opis: "Numer działki" },
                    { rola: "button:submit", typ: "submit", opis: "Szukaj" }]);
  const p = await prowadz("znajdz dzialke", s, kolejno(
    { akcja: "wpisz", nr: 1, tekst: "123/4" }, { akcja: "kliknij", nr: 2 },
    { akcja: "koniec", podsumowanie: "Znalazłem." }));
  assert.deepEqual(s.dziennik, [["wpisz", "Numer działki", "123/4"], ["kliknij", "Szukaj"]]);
  assert.equal(p.podsumowanie, "Znalazłem.");
  assert.equal(p.pytanie, "");
});

for (const opis of ["Podpisz i wyślij", "Złóż wniosek", "Wyślij", "Zapłać", "Zatwierdź",
                    "Podpisz podpisem kwalifikowanym", "Usuń", "Submit", "Sign document"]) {
  test(`nie klika w „${opis}” i oddaje stery`, async () => {
    const s = strona([{ rola: "button", typ: "button", opis }]);
    const p = await prowadz("zloz wniosek", s, kolejno({ akcja: "kliknij", nr: 1 }));
    assert.deepEqual(s.dziennik, []);
    assert.match(p.pytanie, /Nie kliknę/);
    assert.equal(p.kroki[0].wykonano, false);
  });
}

for (const opis of ["Szukaj", "Dalej", "Rozwiń szczegóły", "Zaloguj", "Sign in", "Pozycja 2"]) {
  test(`„${opis}” to zwykly przycisk`, () => assert.equal(WYSYLKA.test(opis), false));
}

test("nie wpisuje do pola hasla", async () => {
  const s = strona([{ rola: "input:password", typ: "password", opis: "PIN" }]);
  const p = await prowadz("zaloguj", s, kolejno({ akcja: "wpisz", nr: 1, tekst: "1234" }));
  assert.deepEqual(s.dziennik, []);
  assert.match(p.pytanie, /wyłącznie Ty/);
});

test("nie otwiera adresu spoza strony startowej", async () => {
  const s = strona([]);
  const p = await prowadz("x", s, kolejno({ akcja: "otworz", adres: "https://zly.example.com/" }));
  assert.deepEqual(s.dziennik, []);
  assert.match(p.pytanie, /Nie wejdę/);
});

test("otwiera podstrone tego samego serwisu", async () => {
  const s = strona([]);
  await prowadz("x", s, kolejno(
    { akcja: "otworz", adres: "https://rejestr.example.gov.pl/inna" }, { akcja: "koniec" }));
  assert.deepEqual(s.dziennik, [["otworz", "https://rejestr.example.gov.pl/inna"]]);
});

test("zatrzymuje sie, gdy strona sama przeszla do innego serwisu", async () => {
  const s = strona([{ rola: "a", typ: "", opis: "Zaloguj" }]);
  s.kliknij = async () => { s.adres = "https://login.example.org/"; };
  const p = await prowadz("x", s, kolejno({ akcja: "kliknij", nr: 1 }, { akcja: "czytaj" }));
  assert.match(p.pytanie, /login\.example\.org/);
  assert.equal(p.kroki.length, 2);
});

test("nieznany numer elementu i nieznana czynnosc zatrzymuja prace", async () => {
  const s = strona([]);
  assert.match((await prowadz("x", s, kolejno({ akcja: "kliknij", nr: 7 }))).pytanie, /numerze 7/);
  assert.match((await prowadz("x", s, kolejno({ akcja: "skacz" }))).zatrzymano, /Nieznana/);
});

test("limit krokow i przerwanie przez notariusza", async () => {
  const s = strona([]);
  const p = await prowadz("x", s, async () => ({ akcja: "czytaj" }), { maksKrokow: 3 });
  assert.equal(p.kroki.length, 3);
  assert.match(p.zatrzymano, /po 3 krokach/);
  const q = await prowadz("x", s, async () => ({ akcja: "czytaj" }), { przerwij: () => true });
  assert.equal(q.kroki.length, 0);
});

test("model nie dostaje selektorow, a historia - wpisywanych wartosci", async () => {
  const s = strona([{ rola: "input:text", typ: "text", opis: "PESEL" }]);
  const widziane = [];
  await prowadz("x", s, async (cel, stan, kroki) => {
    widziane.push({ stan, kroki });
    return widziane.length === 1 ? { akcja: "wpisz", nr: 1, tekst: "44051401359" } : { akcja: "koniec" };
  });
  assert.deepEqual(Object.keys(widziane[0].stan.elementy[0]), ["nr", "rola", "opis"]);
  assert.equal(JSON.stringify(widziane[1].kroki).includes("44051401359"), false);
  assert.deepEqual(Object.keys(stanDlaModelu(await s.stan())), ["adres", "tekst", "elementy"]);
});

test("wolnoWejsc: poddomeny tak, obce i nie-http nie", () => {
  assert.equal(wolnoWejsc("https://a.gov.pl/x", ["gov.pl"]), true);
  assert.equal(wolnoWejsc("https://zlygov.pl/", ["gov.pl"]), false);
  assert.equal(wolnoWejsc("javascript:alert(1)", ["gov.pl"]), false);
  assert.equal(wolnoWejsc("nie-adres", ["gov.pl"]), false);
});

/* ---------- klient notarai ---------- */

function serwer(odpowiedzi) {
  const zadania = [];
  const pobierz = async (adres, opcje) => {
    zadania.push({ adres, opcje });
    const [kod, tresc] = odpowiedzi.shift();
    return { status: kod, ok: kod >= 200 && kod < 300, json: async () => tresc };
  };
  return { zadania, pobierz };
}

test("token idzie tylko w naglowku, do adresu notarai", async () => {
  const s = serwer([[201, { zlecenie: "z1" }]]);
  const n = new Notarai("https://app.notarai.pl/", "tok", s.pobierz);
  assert.equal(await n.zlecKlikanie("cel", "a.gov.pl"), "z1");
  assert.equal(s.zadania[0].adres, "https://app.notarai.pl/api/pomocnik/klikamy");
  assert.equal(s.zadania[0].opcje.headers.Authorization, "Bearer tok");
  assert.equal(s.zadania[0].adres.includes("tok"), false);
});

test("laczenie: 202 czeka, 200 daje token, 410 to wygasly kod, 401 to odlaczenie", async () => {
  const s = serwer([[202, { stan: "czeka" }], [200, { token: "t" }], [410, {}], [401, {}]]);
  const n = new Notarai("https://app.notarai.pl", "", s.pobierz);
  assert.equal(await n.odbierzToken("ABCD-EFGH", "s"), null);
  assert.equal(await n.odbierzToken("ABCD-EFGH", "s"), "t");
  await assert.rejects(n.odbierzToken("ABCD-EFGH", "s"), KodNieaktualny);
  await assert.rejects(n.odlacz(), BladTokenu);
  assert.equal(adresPolaczenia("https://app.notarai.pl/", "ABCD-EFGH"),
               "https://app.notarai.pl/#polacz=ABCD-EFGH");
});

test("przeciazony model: czeka i pyta jeszcze raz", async () => {
  const s = serwer([[503, { detail: "model zajety" }], [200, { akcja: "czytaj" }]]);
  const n = new Notarai("https://app.notarai.pl", "tok", s.pobierz);
  let czekano = 0;
  const krok = await n.krok("z1", "cel", {}, [], async () => { czekano++; });
  assert.deepEqual(krok, { akcja: "czytaj" });
  assert.equal(czekano, 1);
});
