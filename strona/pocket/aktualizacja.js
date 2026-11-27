"use strict";
// Aktualizacje NotarAI Pocket na Androidzie.
// Nowe funkcje trafiają do wszystkich same, bo aplikacja wyświetla tę stronę. Osobnej wymiany wymaga
// tylko sama powłoka (ikona, nazwa, ustawienia systemowe). Powłoka podaje swój numer w adresie
// startowym (?apk=N); gdy na stronie leży nowsza paczka, pokazujemy jeden wiersz z przyciskiem.
window.notaraiNowaPaczka = (() => {
  const KLUCZ = "notarai-pocket-apk";
  let zainstalowana = 0;
  try {
    const podana = new URLSearchParams(window.location.search).get("apk");
    if (podana && /^\d{1,9}$/.test(podana)) localStorage.setItem(KLUCZ, podana);
    zainstalowana = Number(localStorage.getItem(KLUCZ) || 0);
  } catch (_) {
    return Promise.resolve(false);
  }
  // W zwykłej przeglądarce nie ma czego wymieniać.
  if (!zainstalowana || !window.matchMedia("(display-mode: standalone)").matches) return Promise.resolve(false);
  return fetch("wersja.json", { cache: "no-store" })
    .then(odpowiedz => (odpowiedz.ok ? odpowiedz.json() : null))
    .then(wersja => {
      if (!wersja || !(Number(wersja.versionCode) > zainstalowana)) return false;
      const wiersz = document.createElement("p");
      wiersz.className = "card";
      wiersz.setAttribute("role", "status");
      wiersz.append("Jest nowa wersja aplikacji NotarAI. ");
      const link = document.createElement("a");
      link.href = "NotarAI-Pocket.apk";
      link.download = "NotarAI-Pocket.apk";
      link.textContent = "Pobierz i zainstaluj";
      wiersz.append(link, ". Sparowanie telefonu zostaje.");
      document.querySelector("header").after(wiersz);
      return true;
    })
    .catch(() => false);   // brak sieci: sprawdzimy przy następnym otwarciu
})();
