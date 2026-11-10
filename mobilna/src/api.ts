/**
 * Klient API notarai (app.notarai.pl, moduł rezerwacje_klienta.py i wizyty.py).
 *
 * Adres serwera: EXPO_PUBLIC_API_URL (plik .env obok package.json), domyślnie
 * produkcja. Emulator Androida widzi komputer pod 10.0.2.2, przeglądarka pod
 * 127.0.0.1 - patrz README.md.
 */
export const API_URL = (process.env.EXPO_PUBLIC_API_URL ?? "https://app.notarai.pl").replace(/\/+$/, "");

export class BladApi extends Error {
  status: number;
  constructor(status: number, wiadomosc: string) {
    super(wiadomosc);
    this.status = status;
  }
}

export type Kancelaria = {
  id: string;
  online: boolean;
  baza_id?: number;
  nazwa: string;
  notariusze: string;
  adres: string;
  miasto: string;
  lat: number | null;
  lon: number | null;
  telefony: string[];
  www?: string;
  czas_minut?: number;
  max_dni?: number;
  odleglosc_km?: number;
};

export type Miejscowosc = { slug: string; nazwa: string; liczba: number };

export type Termin = { godzina: string; koniec: string };
export type DzienTerminow = { data: string; nieczynne: boolean; terminy: Termin[] };
export type Terminy = {
  kancelaria: Kancelaria;
  czas_minut: number;
  od: string;
  max_dni: number;
  dni: DzienTerminow[];
};

export type Konfiguracja = {
  rezerwacje_online: boolean;
  rodzaje: string[];
  waznosc_kodu_s: number;
  strona: string;
};

export type Weryfikacja = { id: string; wygasa_s: number; koncowka: string; kod_testowy?: string };

export type KancelariaRezerwacji = Pick<Kancelaria, "id" | "nazwa" | "adres" | "miasto" | "lat" | "lon" | "telefony">;

export type Rezerwacja = {
  id: string;
  status: "potwierdzona" | "anulowana";
  data: string;
  godzina: string;
  koniec: string;
  rodzaj: string;
  rodzaj_inny: string;
  utworzono: string;
  kancelaria: KancelariaRezerwacji;
  token?: string;
  komunikat?: string;
};

export type DaneRezerwacji = {
  kancelaria: string;
  data: string;
  godzina: string;
  rodzaj: string;
  rodzaj_inny?: string;
  imie: string;
  telefon: string;
  email?: string;
  uwagi?: string;
  zgoda: boolean;
  weryfikacja: string;
  kod: string;
};

export type Zgloszenie = {
  imie: string;
  telefon: string;
  email?: string;
  czynnosc: string;
  termin?: string;
  wiadomosc?: string;
  zgoda: boolean;
  kancelaria?: number | null;
  miejscowosc?: string;
};

async function zapytanie<T>(sciezka: string, init?: RequestInit): Promise<T> {
  let odp: Response;
  try {
    odp = await fetch(API_URL + sciezka, {
      ...init,
      headers: { Accept: "application/json", ...(init?.body ? { "Content-Type": "application/json" } : {}), ...init?.headers },
    });
  } catch {
    throw new BladApi(0, "Brak połączenia z serwerem. Sprawdź internet i spróbuj ponownie.");
  }
  let dane: unknown = null;
  const tekst = await odp.text();
  if (tekst) {
    try {
      dane = JSON.parse(tekst);
    } catch {
      dane = null;
    }
  }
  if (!odp.ok) {
    const szczegol = (dane as { detail?: unknown } | null)?.detail;
    const wiadomosc =
      typeof szczegol === "string"
        ? szczegol
        : Array.isArray(szczegol)
          ? "Sprawdź wpisane dane."
          : odp.status === 429
            ? "Za dużo prób. Spróbuj za chwilę."
            : "Serwer nie przyjął żądania. Spróbuj ponownie.";
    throw new BladApi(odp.status, wiadomosc);
  }
  return dane as T;
}

const q = (parametry: Record<string, string | number | undefined>) => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(parametry)) if (v !== undefined && v !== "") p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : "";
};

export const api = {
  konfiguracja: () => zapytanie<Konfiguracja>("/api/klient/konfiguracja"),
  miejscowosci: (szukane: string) =>
    zapytanie<{ miejscowosci: Miejscowosc[] }>(`/api/klient/miejscowosci${q({ q: szukane })}`),
  kancelarie: (parametry: { miasto?: string; lat?: number; lon?: number }) =>
    zapytanie<{ kancelarie: Kancelaria[]; miejscowosc: { slug: string; nazwa: string } | null }>(
      `/api/klient/kancelarie${q(parametry)}`,
    ),
  terminy: (id: string, od?: string, dni = 14) =>
    zapytanie<Terminy>(`/api/klient/kancelarie/${encodeURIComponent(id)}/terminy${q({ od, dni })}`),
  weryfikacja: (telefon: string) =>
    zapytanie<Weryfikacja>("/api/klient/weryfikacja", { method: "POST", body: JSON.stringify({ telefon }) }),
  rezerwuj: (dane: DaneRezerwacji) =>
    zapytanie<Rezerwacja>("/api/klient/rezerwacje", { method: "POST", body: JSON.stringify(dane) }),
  rezerwacja: (id: string, kancelaria: string, token: string) =>
    zapytanie<Rezerwacja>(`/api/klient/rezerwacje/${encodeURIComponent(id)}/podglad`, {
      method: "POST",
      body: JSON.stringify({ kancelaria, token }),
    }),
  anuluj: (id: string, kancelaria: string, token: string) =>
    zapytanie<Rezerwacja>(`/api/klient/rezerwacje/${encodeURIComponent(id)}/anuluj`, {
      method: "POST",
      body: JSON.stringify({ kancelaria, token }),
    }),
  przeloz: (id: string, kancelaria: string, token: string, data: string, godzina: string) =>
    zapytanie<Rezerwacja>(`/api/klient/rezerwacje/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: JSON.stringify({ kancelaria, token, data, godzina }),
    }),
  zgloszenie: (dane: Zgloszenie) =>
    zapytanie<{ id: string; notarai: boolean; komunikat: string }>("/api/wizyty/zgloszenie", {
      method: "POST",
      body: JSON.stringify({ ...dane, zrodlo: "aplikacja" }),
    }),
};

// --- daty ---------------------------------------------------------------------

const DNI = ["niedz.", "pon.", "wt.", "śr.", "czw.", "pt.", "sob."];
const DNI_PELNE = ["niedziela", "poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota"];
const MIESIACE = ["sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"];
const MIESIACE_DOPELNIACZ = [
  "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
  "lipca", "sierpnia", "września", "października", "listopada", "grudnia",
];

export function dataZIso(iso: string): Date {
  const [r, m, d] = iso.split("-").map(Number);
  return new Date(r, m - 1, d);
}

export function isoZDaty(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** "wt., 11 lis" - na pasku dni. */
export function dataKrotko(iso: string): { dzien: string; numer: string; miesiac: string } {
  const d = dataZIso(iso);
  return { dzien: DNI[d.getDay()], numer: String(d.getDate()), miesiac: MIESIACE[d.getMonth()] };
}

/** "wtorek, 11 listopada 2026" - w podsumowaniu. */
export function dataDlugo(iso: string): string {
  const d = dataZIso(iso);
  return `${DNI_PELNE[d.getDay()]}, ${d.getDate()} ${MIESIACE_DOPELNIACZ[d.getMonth()]} ${d.getFullYear()}`;
}

export function czyMiniona(data: string, godzina: string): boolean {
  const d = dataZIso(data);
  const [g, m] = godzina.split(":").map(Number);
  d.setHours(g, m, 0, 0);
  return d.getTime() < Date.now();
}

/** Link "Dodaj do kalendarza" (Google Calendar), działa na każdym telefonie i w przeglądarce. */
export function linkKalendarza(r: Rezerwacja): string {
  const znacznik = (iso: string, godzina: string) => iso.replace(/-/g, "") + "T" + godzina.replace(":", "") + "00";
  const p = new URLSearchParams({
    action: "TEMPLATE",
    text: `Notariusz: ${r.kancelaria.nazwa}`,
    dates: `${znacznik(r.data, r.godzina)}/${znacznik(r.data, r.koniec || r.godzina)}`,
    details: `Wizyta umówiona przez aplikację notarai. Czynność: ${r.rodzaj_inny || r.rodzaj}. Weź dowód osobisty.`,
    location: r.kancelaria.adres,
    ctz: "Europe/Warsaw",
  });
  return `https://calendar.google.com/calendar/render?${p.toString()}`;
}

export function linkMapy(k: { lat: number | null; lon: number | null; adres: string; nazwa: string }): string {
  const cel = k.lat != null && k.lon != null ? `${k.lat},${k.lon}` : `${k.nazwa}, ${k.adres}`;
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(cel)}`;
}

export function linkTelefonu(numer: string): string {
  return `tel:${numer.replace(/[^\d+]/g, "")}`;
}
