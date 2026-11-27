"use strict";
// „Dodaj do sprawy”: telefon udostępnia zdjęcie albo PDF aplikacji NotarAI (Android: Udostępnij).
// Przeglądarka wysyła pliki formularzem na /dodaj-do-sprawy. Zatrzymujemy je TUTAJ, w pamięci tej
// przeglądarki, i przekierowujemy do aplikacji; na serwer trafią dopiero po wybraniu sprawy przez
// zalogowaną osobę. Niczego innego ten service worker nie obsługuje.
const SCHOWEK = "notarai-dodaj-do-sprawy";
const MAKS_PLIKOW = 10;
const MAKS_ROZMIAR = 25 * 1024 * 1024;

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", event => event.waitUntil(self.clients.claim()));

self.addEventListener("fetch", event => {
  const adres = new URL(event.request.url);
  if (event.request.method !== "POST" || adres.origin !== self.location.origin || adres.pathname !== "/dodaj-do-sprawy") return;
  event.respondWith((async () => {
    let wynik = "brak";
    try {
      const dane = await event.request.formData();
      const pliki = dane.getAll("pliki").filter(p => p instanceof File && p.size > 0 && p.size <= MAKS_ROZMIAR).slice(0, MAKS_PLIKOW);
      if (pliki.length) {
        const schowek = await caches.open(SCHOWEK);
        for (const klucz of await schowek.keys()) await schowek.delete(klucz);      // poprzednia, niedokończona paczka
        const teraz = Date.now();
        await Promise.all(pliki.map((plik, numer) => schowek.put(`/_dodaj-do-sprawy/${teraz}-${numer}`, new Response(plik, {
          headers: {
            "Content-Type": plik.type || "application/octet-stream",
            "X-Nazwa": encodeURIComponent(plik.name || `plik-${numer + 1}`),
          },
        }))));
        wynik = "1";
      }
    } catch (_) {
      wynik = "blad";
    }
    return Response.redirect("/?dodaj=" + wynik, 303);
  })());
});
