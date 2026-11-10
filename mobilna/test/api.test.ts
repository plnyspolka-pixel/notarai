/**
 * Testy jednostkowe src/api.ts: daty, linki, mapowanie błędów i ponawianie.
 * Bez zależności: wbudowany `node --test`, Node sam usuwa typy z plików .ts
 * (npm test). Sieć jest podstawiona (globalThis.fetch), nic nie wychodzi.
 */
import assert from "node:assert/strict";
import { afterEach, describe, it } from "node:test";
import {
  api,
  BladApi,
  brakPolaczenia,
  czyMiniona,
  dataDlugo,
  dataKrotko,
  dataZIso,
  doPonowienia,
  isoZDaty,
  linkEmail,
  linkKalendarza,
  linkMapy,
  linkTelefonu,
  POLITYKA_PRYWATNOSCI,
  type Rezerwacja,
} from "../src/api.ts";

const prawdziwyFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = prawdziwyFetch;
});

/** Kolejne odpowiedzi podstawionego fetch: Error = brak sieci, liczba = status z JSON. */
function siec(...odpowiedzi: Array<Error | [number, unknown]>) {
  const wywolania: Array<{ url: string; init?: RequestInit }> = [];
  globalThis.fetch = (async (url: string, init?: RequestInit) => {
    wywolania.push({ url: String(url), init });
    const o = odpowiedzi[Math.min(wywolania.length - 1, odpowiedzi.length - 1)];
    if (o instanceof Error) throw o;
    const [status, cialo] = o;
    return new Response(JSON.stringify(cialo), { status, headers: { "Content-Type": "application/json" } });
  }) as typeof fetch;
  return wywolania;
}

const REZERWACJA: Rezerwacja = {
  id: "abc123",
  status: "potwierdzona",
  data: "2026-11-12",
  godzina: "10:00",
  koniec: "11:00",
  rodzaj: "sprzedaż",
  rodzaj_inny: "",
  utworzono: "2026-11-10T12:00:00",
  kancelaria: { id: "demo-lublin", nazwa: "Kancelaria Notarialna Demo", adres: "ul. Próbna 1, Lublin", miasto: "Lublin", lat: 51.25, lon: 22.57, telefony: [] },
};

describe("daty", () => {
  it("ISO <-> Date bez przesunięć strefy", () => {
    const d = dataZIso("2026-03-29");          // dzień zmiany czasu na letni
    assert.equal(d.getFullYear(), 2026);
    assert.equal(d.getMonth(), 2);
    assert.equal(d.getDate(), 29);
    assert.equal(isoZDaty(d), "2026-03-29");
    assert.equal(isoZDaty(new Date(2026, 0, 5)), "2026-01-05");
  });

  it("opisy po polsku", () => {
    assert.deepEqual(dataKrotko("2026-11-12"), { dzien: "czw.", numer: "12", miesiac: "lis" });
    assert.equal(dataDlugo("2026-11-12"), "czwartek, 12 listopada 2026");
    assert.equal(dataDlugo("2027-01-01"), "piątek, 1 stycznia 2027");
  });

  it("czy wizyta minęła", () => {
    assert.equal(czyMiniona("2000-01-01", "10:00"), true);
    assert.equal(czyMiniona("2999-01-01", "10:00"), false);
  });
});

describe("linki", () => {
  it("Google Calendar z datą, strefą i adresem", () => {
    const u = new URL(linkKalendarza(REZERWACJA));
    assert.equal(u.hostname, "calendar.google.com");
    assert.equal(u.searchParams.get("dates"), "20261112T100000/20261112T110000");
    assert.equal(u.searchParams.get("ctz"), "Europe/Warsaw");
    assert.equal(u.searchParams.get("location"), "ul. Próbna 1, Lublin");
    assert.match(u.searchParams.get("text") ?? "", /Kancelaria Notarialna Demo/);
    assert.match(u.searchParams.get("details") ?? "", /sprzedaż/);
  });

  it("wizyta bez godziny końca nie psuje linku", () => {
    const u = new URL(linkKalendarza({ ...REZERWACJA, koniec: "" }));
    assert.equal(u.searchParams.get("dates"), "20261112T100000/20261112T100000");
  });

  it("mapa: współrzędne albo adres", () => {
    assert.match(linkMapy(REZERWACJA.kancelaria), /query=51\.25%2C22\.57$/);
    const bezWspolrzednych = linkMapy({ lat: null, lon: null, nazwa: "Kancelaria X", adres: "Rynek 1" });
    assert.equal(new URL(bezWspolrzednych).searchParams.get("query"), "Kancelaria X, Rynek 1");
  });

  it("telefon, e-mail, polityka", () => {
    assert.equal(linkTelefonu("+48 81 000-00-00"), "tel:+48810000000");
    assert.equal(linkEmail("kontakt@notarai.pl"), "mailto:kontakt@notarai.pl");
    assert.equal(linkEmail("kontakt@notarai.pl", "Aplikacja notarai"), "mailto:kontakt@notarai.pl?subject=Aplikacja%20notarai");
    assert.equal(POLITYKA_PRYWATNOSCI, "https://notarai.pl/prywatnosc/");
  });
});

describe("błędy i ponawianie", () => {
  it("które statusy ponawiamy", () => {
    assert.deepEqual([0, 502, 503, 504].map(doPonowienia), [true, true, true, true]);
    assert.deepEqual([400, 404, 409, 429, 500].map(doPonowienia), [false, false, false, false, false]);
    assert.equal(brakPolaczenia(new BladApi(0, "x")), true);
    assert.equal(brakPolaczenia(new Error("x")), false);
  });

  it("odczyt terminów ponawiany po zerwanym połączeniu", async () => {
    const wywolania = siec(new TypeError("Failed to fetch"), [200, { dni: [] }]);
    const wynik = await api.terminy("demo-lublin", "2026-11-12", 7);
    assert.deepEqual(wynik, { dni: [] });
    assert.equal(wywolania.length, 2);
    assert.match(wywolania[1].url, /\/api\/klient\/kancelarie\/demo-lublin\/terminy\?od=2026-11-12&dni=7$/);
  });

  it("kodu SMS nie wysyłamy drugi raz sami - błąd sieci od razu do użytkownika", async () => {
    const wywolania = siec(new TypeError("Failed to fetch"), [201, { id: "w1" }]);
    await assert.rejects(api.weryfikacja("600700800"), (e: unknown) => e instanceof BladApi && e.status === 0 && /internet/i.test(e.message));
    assert.equal(wywolania.length, 1);
  });

  it("token rezerwacji tylko w ciele żądania, nie w adresie", async () => {
    const wywolania = siec([200, REZERWACJA]);
    await api.rezerwacja("abc123", "demo-lublin", "tajny-token");
    assert.ok(!wywolania[0].url.includes("tajny-token"));
    assert.deepEqual(JSON.parse(String(wywolania[0].init?.body)), { kancelaria: "demo-lublin", token: "tajny-token" });
  });

  it("komunikaty serwera dla klienta", async () => {
    siec([409, { detail: "Ten termin został właśnie zajęty. Wybierz inną godzinę." }]);
    await assert.rejects(api.anuluj("a", "b", "c"), (e: unknown) => e instanceof BladApi && e.status === 409 && /zajęty/.test(e.message));
    siec([422, { detail: [{ loc: ["body", "telefon"], msg: "field required" }] }]);
    await assert.rejects(api.weryfikacja(""), /Sprawdź wpisane dane/);
    siec([429, {}]);
    await assert.rejects(api.weryfikacja("600700800"), /Za dużo prób/);
  });
});
