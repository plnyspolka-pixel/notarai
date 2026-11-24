/* Zabezpieczenia silnika: to one, a nie polecenie dla modelu, pilnuja, zeby
   asystent niczego nie wyslal, nie podpisal i nie wpisal hasla. */
import test from "node:test";
import assert from "node:assert/strict";
import { prowadz, WYSYLKA, wolnoWejsc, stanDlaModelu, jestLogowanie } from "../silnik.js";
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

test("strona z polem hasla: nic nie wpisuje, nie pyta modelu i czeka na logowanie", async () => {
  const s = strona([{ rola: "input:password", typ: "password", opis: "PIN" }]);
  let pytano = 0;
  const p = await prowadz("zaloguj", s, async () => { pytano++; return { akcja: "wpisz", nr: 1, tekst: "1234" }; });
  assert.deepEqual(s.dziennik, []);
  assert.equal(pytano, 0);
  assert.equal(p.czeka, "logowanie");
  assert.match(p.pytanie, /Zaloguj się\s+samodzielnie/);
});

test("rozpoznaje logowanie i wygasla sesje, a zwyklej strony nie", () => {
  const stan = (adres, tekst = "", elementy = []) => ({ adres, tekst, elementy });
  assert.equal(jestLogowanie(stan("https://login.gov.pl/login/main")), true);
  assert.equal(jestLogowanie(stan("https://x.pz.gov.pl/dt/login")), true);
  assert.equal(jestLogowanie(stan("https://rejestr.example.gov.pl/logowanie", "Logowanie do systemu")), true);
  assert.equal(jestLogowanie(stan("https://rejestr.example.gov.pl/wniosek", "Twoja sesja wygasła.")), true);
  assert.equal(jestLogowanie(stan("https://rejestr.example.gov.pl/wniosek", "Zostałeś wylogowany")), true);
  assert.equal(jestLogowanie(stan("https://rejestr.example.gov.pl/a", "", [{ typ: "password" }])), true);
  // Odnosnik "Zaloguj" w naglowku publicznej strony to jeszcze nie logowanie.
  assert.equal(jestLogowanie(stan("https://rejestr.example.gov.pl/szukaj", "Zaloguj | Wyszukiwarka")), false);
  // Sciezka /auth bez tresci o logowaniu tez nie.
  assert.equal(jestLogowanie(stan("https://rejestr.example.gov.pl/auth/profil", "Twoje wnioski")), false);
  assert.equal(jestLogowanie(stan("https://nielogin.gov.pl.example.com/", "Formularz")), false);
});

test("przekierowanie do logowania: czeka, a po wznowieniu wraca na ten sam serwis z historia", async () => {
  const s = strona([{ rola: "input:text", typ: "text", opis: "Numer KW" },
                    { rola: "button", typ: "button", opis: "Dalej" }]);
  const widziane = [];
  const model = (odpowiedzi) => async (cel, stan, kroki) => {
    widziane.push({ adres: stan.adres, kroki: kroki.length });
    return odpowiedzi.shift() || { akcja: "koniec" };
  };
  const pierwszy = await prowadz("wypelnij", s, async (cel, stan, kroki) => {
    widziane.push({ adres: stan.adres, kroki: kroki.length });
    s.adres = "https://login.gov.pl/login/main";       // serwis odsyla do logowania
    return { akcja: "wpisz", nr: 1, tekst: "WA1M/1/2" };
  });
  assert.equal(pierwszy.czeka, "logowanie");
  assert.deepEqual(pierwszy.dozwolone, ["rejestr.example.gov.pl"]);
  assert.equal(widziane.length, 1);                     // strony logowania model nie widzial
  assert.equal(pierwszy.kroki.at(-1).akcja, "czekam");

  // Bez logowania "Wznow" nic nie zmienia: dalej czekamy.
  const wciaz = await prowadz("wypelnij", s, model([]),
    { wznow: { kroki: pierwszy.kroki, dozwolone: pierwszy.dozwolone } });
  assert.equal(wciaz.czeka, "logowanie");
  assert.equal(widziane.length, 1);

  // Notariusz zalogowal sie sam i wrocil do formularza.
  s.adres = "https://rejestr.example.gov.pl/formularz";
  const drugi = await prowadz("wypelnij", s,
    model([{ akcja: "kliknij", nr: 2 }, { akcja: "koniec", podsumowanie: "Gotowe." }]),
    { wznow: { kroki: pierwszy.kroki, dozwolone: pierwszy.dozwolone } });
  assert.equal(drugi.czeka, "");
  assert.equal(drugi.podsumowanie, "Gotowe.");
  assert.equal(widziane[1].kroki, pierwszy.kroki.length);  // model dostal historie
  assert.equal(drugi.kroki[0].nr, 1);
  assert.equal(drugi.kroki.at(-1).nr, drugi.kroki.length); // numeracja ciagla
  assert.deepEqual(s.dziennik.at(-1), ["kliknij", "Dalej"]);
});

test("po wznowieniu nie da sie wyjsc na inny serwis niz ten z pierwszego uruchomienia", async () => {
  const s = strona([], "https://inny.example.com/strona");
  const p = await prowadz("x", s, kolejno({ akcja: "czytaj" }),
    { wznow: { kroki: [], dozwolone: ["rejestr.example.gov.pl"] } });
  assert.match(p.pytanie, /Strona przeszła na inny\.example\.com/);
  assert.equal(p.czeka, "");
});

test("przycisk podpisu: oddaje stery i pozwala wznowic po podpisie", async () => {
  const s = strona([{ rola: "button", typ: "button", opis: "Podpisz i wyślij" },
                    { rola: "a", typ: "", opis: "Pobierz dokument" }]);
  const p = await prowadz("zloz", s, kolejno({ akcja: "kliknij", nr: 1 }));
  assert.equal(p.czeka, "czynnosc");
  assert.deepEqual(s.dziennik, []);
  const dalej = await prowadz("zloz", s, kolejno({ akcja: "kliknij", nr: 2 }, { akcja: "koniec" }),
    { wznow: { kroki: p.kroki, dozwolone: p.dozwolone } });
  assert.deepEqual(s.dziennik, [["kliknij", "Pobierz dokument"]]);
  // Po wznowieniu przycisk podpisu jest nadal nie do klikniecia.
  const znow = await prowadz("zloz", s, kolejno({ akcja: "kliknij", nr: 1 }),
    { wznow: { kroki: dalej.kroki, dozwolone: dalej.dozwolone } });
  assert.equal(znow.czeka, "czynnosc");
  assert.equal(s.dziennik.length, 1);
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
