/**
 * Kolory i odstępy aplikacji klienta notarai. Tokeny zgodne z szatą graficzną
 * app.notarai.pl (docs/wyglad-financeyou.md): granat, indygo, błękit, złoto.
 */
export const kolory = {
  granat: "#0d193c",
  granatCiemny: "#050a30",
  indygo: "#1c1cc0",
  blekit: "#2197d3",
  zloto: "#e4c47a",
  tlo: "#f5f7fc",
  powierzchnia: "#ffffff",
  tekst: "#0d193c",
  tekst2: "#5b6680",
  linia: "#dfe4f0",
  linia2: "#c7cfe2",
  sukces: "#1d8a4e",
  sukcesTlo: "#e6f6ec",
  alarm: "#b42318",
  alarmTlo: "#fdecea",
  info: "#eaf4fb",
} as const;

export const odstep = {
  xs: 4,
  s: 8,
  m: 12,
  l: 16,
  xl: 24,
  xxl: 32,
} as const;

export const promien = {
  s: 8,
  m: 12,
  l: 18,
} as const;

export const czcionka = {
  tytul: { fontSize: 24, fontWeight: "700" as const, color: kolory.tekst },
  naglowek: { fontSize: 18, fontWeight: "700" as const, color: kolory.tekst },
  tekst: { fontSize: 16, color: kolory.tekst, lineHeight: 22 },
  pod: { fontSize: 14, color: kolory.tekst2, lineHeight: 20 },
  maly: { fontSize: 12, color: kolory.tekst2 },
};
