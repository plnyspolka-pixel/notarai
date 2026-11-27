"use strict";
/* „Dodaj do sprawy”: pliki udostępnione aplikacji NotarAI z telefonu (galeria, poczta, komunikator)
   czekają w pamięci tej przeglądarki (dodaj-do-sprawy-sw.js). Tu notariusz wybiera sprawę i dopiero
   wtedy pliki idą na serwer zwykłą ścieżką załączników. Korzysta z api() i $ z index.html. */
(() => {
  const SCHOWEK = "notarai-dodaj-do-sprawy";
  if (!("serviceWorker" in navigator) || !("caches" in window)) return;
  navigator.serviceWorker.register("/dodaj-do-sprawy-sw.js", {scope: "/"}).catch(() => { /* bez tej funkcji */ });

  const okno = $("okno-dodaj-do-sprawy");
  const lista = $("dds-pliki"), wybor = $("dds-sprawa"), stanDds = $("dds-stan");
  const dodaj = $("dds-dodaj"), odrzuc = $("dds-odrzuc");
  const komunikat = (tekst, blad) => { stanDds.textContent = tekst; stanDds.classList.toggle("blad", !!blad); };

  async function czekajace() {
    const schowek = await caches.open(SCHOWEK);
    const pliki = [];
    for (const klucz of await schowek.keys()) {
      const odp = await schowek.match(klucz);
      if (!odp) continue;
      let nazwa = "plik";
      try { nazwa = decodeURIComponent(odp.headers.get("X-Nazwa") || "plik"); } catch (_) { /* zostaje "plik" */ }
      pliki.push(new File([await odp.blob()], nazwa, {type: odp.headers.get("Content-Type") || "application/octet-stream"}));
    }
    return pliki;
  }
  const wyczysc = () => caches.delete(SCHOWEK);
  const sprzataj = () => {
    const adres = new URL(location.href);
    if (adres.searchParams.has("dodaj")) { adres.searchParams.delete("dodaj"); history.replaceState(null, "", adres); }
  };

  async function pokaz() {
    const wynik = new URLSearchParams(location.search).get("dodaj");
    const pliki = await czekajace().catch(() => []);
    if (!pliki.length) {
      if (wynik === "brak" || wynik === "blad") {
        sprzataj();
        alert(wynik === "brak"
          ? "NotarAI nie odebrał plików. Otwórz aplikację, a potem udostępnij pliki jeszcze raz."
          : "Nie udało się odebrać plików. Udostępnij je jeszcze raz (do 10 plików, każdy do 25 MB).");
      }
      return;
    }
    lista.replaceChildren(...pliki.map(plik => {
      const wiersz = document.createElement("li");
      wiersz.textContent = `${plik.name} (${Math.max(1, Math.round(plik.size / 1024))} KB)`;
      return wiersz;
    }));
    komunikat("Wczytuję sprawy…");
    dodaj.disabled = true;
    if (!okno.open) okno.showModal();
    let sprawy = [];
    try {
      const odp = await api("/api/sprawy");
      if (!odp.ok) throw new Error();
      sprawy = await odp.json();
    } catch (_) {
      // Niezalogowany: api() otworzyło okno logowania; pliki czekają i wrócą po zalogowaniu.
      okno.close();
      return;
    }
    wybor.replaceChildren(...sprawy.map(sprawa => {
      const opcja = document.createElement("option");
      opcja.value = sprawa.id;
      opcja.textContent = sprawa.sygnatura ? `${sprawa.nazwa} (${sprawa.sygnatura})` : sprawa.nazwa;
      return opcja;
    }));
    if (!sprawy.length) {
      komunikat("Nie ma jeszcze żadnej sprawy. Załóż sprawę, a potem udostępnij pliki ponownie.", true);
      return;
    }
    komunikat("");
    dodaj.disabled = false;

    dodaj.onclick = async () => {
      dodaj.disabled = true;
      komunikat("Dodaję do sprawy…");
      const dane = new FormData();
      pliki.forEach(plik => dane.append("pliki", plik, plik.name));
      try {
        const odp = await api(`/api/sprawy/${encodeURIComponent(wybor.value)}/pliki`, {method: "POST", body: dane});
        if (!odp.ok) {
          const tresc = await odp.json().catch(() => ({}));
          throw new Error(tresc.detail || "Nie udało się dodać plików.");
        }
        await wyczysc();
        sprzataj();
        const nazwa = wybor.selectedOptions[0] ? wybor.selectedOptions[0].textContent : "sprawy";
        komunikat(`Dodano ${pliki.length === 1 ? "plik" : "pliki (" + pliki.length + ")"} do sprawy: ${nazwa}.`);
        dodaj.hidden = true;
        odrzuc.textContent = "Zamknij";
      } catch (blad) {
        komunikat(String(blad.message || "Nie udało się dodać plików."), true);
        dodaj.disabled = false;
      }
    };
  }
  odrzuc.onclick = async () => {
    await wyczysc();
    sprzataj();
    okno.close();
  };
  okno.addEventListener("cancel", event => event.preventDefault());   // Esc nie gubi plików: decyzja przyciskiem

  pokaz();
  // Po zalogowaniu strona nie zawsze się przeładowuje: sprawdzamy ponownie, gdy karta wraca na wierzch.
  document.addEventListener("visibilitychange", () => { if (!document.hidden && !okno.open) pokaz(); });
})();
