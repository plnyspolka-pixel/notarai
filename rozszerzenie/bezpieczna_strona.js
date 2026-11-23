/* Lokalna ocena bezpieczenstwa odwiedzanej strony i pobieranego pliku.
   Wszystko liczone NA URZADZENIU - nic nie wychodzi, historia przegladania
   nigdzie nie jest wysylana. To maksimum ochrony przed phishingiem i zlosliwym
   pobraniem, jakie lekkie narzedzie (rozszerzenie) moze dac bez uprawnien
   systemowych.

   Plik czysty (bez chrome.* i DOM) - testowalny w samym Node. */

/* Domeny czesto podrabiane: urzedy, poczta, banki. Lista rozszerzalna -
   notariusz moze dodac wlasne wazne domeny w ustawieniach rozszerzenia. */
export const WAZNE_DOMENY = [
  "gov.pl", "podatki.gov.pl", "epuap.gov.pl", "mojepanstwo.pl",
  "ekw.ms.gov.pl", "prs.ms.gov.pl", "krs-online.com.pl",
  "login.microsoftonline.com", "office.com", "accounts.google.com",
  "ing.pl", "mbank.pl", "santander.pl", "pkobp.pl", "ipko.pl", "pekao.com.pl",
  "millenet.pl", "aliorbank.pl",
];

/* Pliki, ktore moga uruchomic kod - glowna droga ransomware przez pobranie. */
export const ROZSZERZENIA_RYZYKOWNE = [
  "exe", "scr", "msi", "bat", "cmd", "com", "js", "jse", "vbs", "vbe",
  "ps1", "jar", "hta", "lnk", "reg", "msc", "pif", "apk",
];

export function czyPunycode(host) {
  return /(^|\.)xn--/i.test(host || "");
}

/* Odleglosc edycyjna Levenshteina - do wykrycia literowek w domenie. */
export function odleglosc(a, b) {
  a = a || ""; b = b || "";
  const m = a.length, n = b.length;
  if (!m) return n; if (!n) return m;
  let poprz = Array.from({ length: n + 1 }, (_, i) => i);
  for (let i = 1; i <= m; i++) {
    const biez = [i];
    for (let j = 1; j <= n; j++) {
      const koszt = a[i - 1] === b[j - 1] ? 0 : 1;
      biez[j] = Math.min(biez[j - 1] + 1, poprz[j] + 1, poprz[j - 1] + koszt);
    }
    poprz = biez;
  }
  return poprz[n];
}

function bezWww(host) {
  return (host || "").toLowerCase().replace(/^www\./, "");
}

/* Zwraca nazwe prawdziwej domeny, pod ktora host sie podszywa, albo null. */
export function czyPodrobka(host, wazne = WAZNE_DOMENY) {
  const h = bezWww(host);
  if (!h) return null;
  for (const w of wazne) {
    if (h === w || h.endsWith("." + w)) return null;  // to prawdziwa domena
  }
  // Prawdziwa domena jako segment, ale nie jako koncowka (np. mbank.pl.evil.com).
  for (const w of wazne) {
    if (h.startsWith(w + ".") || h.includes("." + w + ".")) return w;
  }
  // Literowka/podmiana 1-2 znakow przy zblizonej dlugosci = prawdopodobna podróbka.
  for (const w of wazne) {
    const d = odleglosc(h, w);
    if (d > 0 && d <= 2 && Math.abs(h.length - w.length) <= 2) return w;
  }
  return null;
}

/* Ocena odwiedzanej strony: lista ostrzezen (moze byc pusta). */
export function ocenStrone(adres, wazne = WAZNE_DOMENY) {
  let url;
  try { url = new URL(adres); } catch { return []; }
  const host = url.hostname;
  const ostrz = [];
  if (czyPunycode(host)) {
    ostrz.push({ poziom: "alarm", kod: "punycode",
      tekst: "Adres zawiera zakodowane znaki (punycode) — częsta sztuczka podróbek udających znaną stronę. Sprawdź dokładnie, zanim cokolwiek wpiszesz." });
  }
  const podr = czyPodrobka(host, wazne);
  if (podr) {
    ostrz.push({ poziom: "alarm", kod: "podrobka", podobnaDo: podr,
      tekst: 'Adres łudząco podobny do „' + podr + '". To może być strona podszywająca się — nie wpisuj tu haseł ani danych.' });
  }
  if (url.protocol === "http:") {
    ostrz.push({ poziom: "uwaga", kod: "http",
      tekst: "Połączenie nieszyfrowane (http). Nie podawaj tu haseł ani danych osobowych." });
  }
  return ostrz;
}

/* Ocena pobieranego pliku. */
export function ryzykoPobrania(nazwa) {
  const m = /\.([a-z0-9]+)$/i.exec(nazwa || "");
  const ext = m ? m[1].toLowerCase() : "";
  if (ROZSZERZENIA_RYZYKOWNE.includes(ext)) {
    return { poziom: "alarm", ext,
      tekst: "Pobierasz plik, który może uruchomić program (." + ext + "). Jeśli nie wiesz dokładnie, co to i od kogo — nie uruchamiaj. Tak najczęściej wchodzi ransomware." };
  }
  return null;
}
