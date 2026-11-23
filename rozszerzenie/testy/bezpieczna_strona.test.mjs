/* Lokalna ochrona przed phishingiem i zlosliwym pobraniem. Czysta logika,
   liczona na urzadzeniu - nic nie wychodzi. */
import test from "node:test";
import assert from "node:assert/strict";
import { ocenStrone, czyPodrobka, czyPunycode, ryzykoPobrania, odleglosc }
  from "../bezpieczna_strona.js";

const kody = (os) => os.map(o => o.kod);

test("prawdziwe domeny nie sa oznaczane jako podrobki", () => {
  assert.equal(czyPodrobka("mbank.pl"), null);
  assert.equal(czyPodrobka("www.mbank.pl"), null);
  assert.equal(czyPodrobka("online.mbank.pl"), null);
  assert.equal(czyPodrobka("ekw.ms.gov.pl"), null);
  assert.equal(czyPodrobka("podatki.gov.pl"), null);
});

test("literowka w domenie banku = podrobka", () => {
  assert.equal(czyPodrobka("mbonk.pl"), "mbank.pl");
  assert.equal(czyPodrobka("santnder.pl"), "santander.pl");
});

test("prawdziwa domena jako segment podstawiony (mbank.pl.evil.com)", () => {
  assert.equal(czyPodrobka("mbank.pl.evil.com"), "mbank.pl");
  assert.equal(czyPodrobka("login.ipko.pl.konto-weryfikacja.ru"), "ipko.pl");
});

test("zwykla, niepodobna domena nie jest oznaczana", () => {
  assert.equal(czyPodrobka("przyklad-kancelaria.pl"), null);
  assert.equal(czyPodrobka("thegov.pl"), null);   // zawiera 'gov.pl', ale nie jako segment
});

test("punycode wykrywane", () => {
  assert.equal(czyPunycode("xn--80ak6aa92e.com"), true);
  assert.equal(czyPunycode("mbank.pl"), false);
});

test("ocenStrone: alarm przy podrobce", () => {
  const os = ocenStrone("https://mbonk.pl/logowanie");
  assert.ok(kody(os).includes("podrobka"));
  assert.equal(os.find(o => o.kod === "podrobka").podobnaDo, "mbank.pl");
});

test("ocenStrone: http = ostrzezenie, https na prawdziwej domenie = czysto", () => {
  assert.deepEqual(kody(ocenStrone("http://mbank.pl/")), ["http"]);
  assert.deepEqual(kody(ocenStrone("https://www.mbank.pl/")), []);
});

test("ryzyko pobrania: pliki wykonywalne vs dokumenty", () => {
  assert.ok(ryzykoPobrania("aktualizacja.exe"));
  assert.ok(ryzykoPobrania("faktura.js"));
  assert.equal(ryzykoPobrania("wniosek.pdf"), null);
  assert.equal(ryzykoPobrania("akt-notarialny.docx"), null);
});

test("odleglosc Levenshteina", () => {
  assert.equal(odleglosc("mbank", "mbonk"), 1);
  assert.equal(odleglosc("kot", "kot"), 0);
});
