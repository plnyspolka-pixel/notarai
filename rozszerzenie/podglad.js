/* Zaszyfrowany podglad aktywnej karty tylko podczas zadania z telefonu.

ECDH P-256 + AES-GCM w WebCrypto. Serwer NotarAI dostaje wylacznie ciphertext,
publiczny klucz rozszerzenia i nonce. Prywatny klucz nigdy nie opuszcza
rozszerzenia; prywatny klucz telefonu nigdy nie opuszcza telefonu.
Bez nagrywania, bez mikrofonu, bez przechowywania screenshotow lokalnie.
*/
const czekaj = ms => new Promise(r => setTimeout(r, ms));

function base64(bytes) {
  let s = "";
  for (let i = 0; i < bytes.length; i += 8192) {
    s += String.fromCharCode(...bytes.slice(i, i + 8192));
  }
  return btoa(s);
}

async function zmniejsz(dataUrl) {
  const blob = await (await fetch(dataUrl)).blob();
  const obraz = await createImageBitmap(blob);
  const szer = Math.min(960, obraz.width);
  const wys = Math.round(obraz.height * szer / obraz.width);
  const plotno = document.createElement("canvas");
  plotno.width = szer;
  plotno.height = wys;
  plotno.getContext("2d").drawImage(obraz, 0, 0, szer, wys);
  obraz.close();
  const jpg = await new Promise(resolve => plotno.toBlob(resolve, "image/jpeg", 0.52));
  return new Uint8Array(await jpg.arrayBuffer());
}

export async function uruchomPodglad(zlecenie, kartaId, notarai, chromeApi = chrome) {
  const publicznyTelefonu = (zlecenie.tresc || {}).podglad_pubkey;
  if (!publicznyTelefonu) return { zatrzymaj: async () => {}, raz: async () => {} };

  const odbiorca = await crypto.subtle.importKey(
    "jwk", publicznyTelefonu, { name: "ECDH", namedCurve: "P-256" }, false, []);
  const klucze = await crypto.subtle.generateKey(
    { name: "ECDH", namedCurve: "P-256" }, true, ["deriveKey"]);
  const aes = await crypto.subtle.deriveKey(
    { name: "ECDH", public: odbiorca }, klucze.privateKey,
    { name: "AES-GCM", length: 256 }, false, ["encrypt"]);
  const klucz = await crypto.subtle.exportKey("jwk", klucze.publicKey);
  let wlaczony = true, numer = 0, blokada = false;

  async function raz() {
    if (!wlaczony || blokada) return;
    blokada = true;
    try {
      const tab = await chromeApi.tabs.get(kartaId);
      const aktywna = (await chromeApi.tabs.query({ active: true, windowId: tab.windowId }))[0];
      // Nie robimy kadrow innych kart, stron systemowych, przegladarek prywatnych
      // ani kart, ktore nie sa wlasnie prowadzone przez to zlecenie.
      if (!tab.active || !aktywna || aktywna.id !== kartaId ||
          !/^https:\/\//.test(tab.url || "")) return;
      const dataUrl = await chromeApi.tabs.captureVisibleTab(
        tab.windowId, { format: "jpeg", quality: 50 });
      const pixels = await zmniejsz(dataUrl);
      const seq = ++numer;
      const iv = crypto.getRandomValues(new Uint8Array(12));
      const aad = new TextEncoder().encode(zlecenie.id + "|" + seq);
      const zaszyfrowane = await crypto.subtle.encrypt(
        { name: "AES-GCM", iv, additionalData: aad }, aes, pixels);
      await notarai.wyslijPodglad(zlecenie.id, {
        numer: seq, klucz: { kty: klucz.kty, crv: klucz.crv, x: klucz.x, y: klucz.y },
        iv: base64(iv), dane: base64(new Uint8Array(zaszyfrowane)),
      });
    } finally {
      blokada = false;
    }
  }

  const petla = (async () => {
    while (wlaczony) {
      try { await raz(); }
      catch { /* Brak activeTab albo utrata lacza: zadanie wykonuje sie dalej. */ }
      if (wlaczony) await czekaj(1300);
    }
  })();
  return {
    raz,
    zatrzymaj: async () => { wlaczony = false; await Promise.race([petla, czekaj(1700)]); },
  };
}
