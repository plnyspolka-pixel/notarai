/* Maskowanie danych wrazliwych przed wyslaniem do modelu. To mechanizm, nie
   obietnica: tekst strony i opisy elementow wychodza z PESEL-ami, dowodami,
   numerami aktow i kont zamienionymi na etykiety. */
import test from "node:test";
import assert from "node:assert/strict";
import { maskujDane, stanDlaModelu } from "../silnik.js";

test("PESEL jest maskowany", () => {
  assert.equal(maskujDane("PESEL 44051401359 klienta"), "PESEL [PESEL] klienta");
});

test("NIP maskowany - ciagiem i z mysnikami", () => {
  assert.equal(maskujDane("NIP 1234563218"), "NIP [NIP]");
  assert.equal(maskujDane("NIP 123-456-32-18"), "NIP [NIP]");
});

test("numer rachunku (NRB, 26 cyfr) -> [NR KONTA], nie [PESEL]", () => {
  assert.equal(maskujDane("konto 61109010140000071219812874"), "konto [NR KONTA]");
  assert.equal(maskujDane("PL61109010140000071219812874"), "[NR KONTA]");
});

test("dowod osobisty", () => {
  assert.equal(maskujDane("dowod ABC123456"), "dowod [DOWÓD]");
  assert.equal(maskujDane("dowod ABC 123456"), "dowod [DOWÓD]");
});

test("numer aktu (repertorium A)", () => {
  assert.equal(maskujDane("Rep. A nr 1234/2026"), "[NR AKTU]");
});

test("telefon +48", () => {
  assert.equal(maskujDane("tel. +48 600 700 800"), "tel. [TEL]");
});

test("zwykly tekst (nazwiska, adresy) nie jest ruszany", () => {
  const t = "Jan Kowalski, ul. Testowa 5, Lublin";
  assert.equal(maskujDane(t), t);
});

test("stanDlaModelu maskuje tekst, opis i adres, zostawia nr i role", () => {
  const stan = {
    adres: "https://portal.gov.pl/sprawa?pesel=44051401359",
    tekst: "Klient 44051401359, akt Rep. A nr 7/2026",
    elementy: [{ nr: 1, rola: "input", opis: "PESEL 44051401359", selektor: "#p" }],
  };
  const out = stanDlaModelu(stan);
  assert.ok(!out.tekst.includes("44051401359"));
  assert.ok(out.tekst.includes("[PESEL]") && out.tekst.includes("[NR AKTU]"));
  assert.ok(!out.adres.includes("44051401359"));
  assert.equal(out.elementy[0].opis, "PESEL [PESEL]");
  assert.equal(out.elementy[0].nr, 1);
  assert.equal(out.elementy[0].rola, "input");
  assert.equal(out.elementy[0].selektor, undefined); // selektory dalej zostaja w przegladarce
});
