/* NotarAI — odsluch projektu przez Amazon Polly. Zero trwalego zapisu audio. */
(function () {
  "use strict";
  const projekt = document.getElementById("projekt");
  const przycisk = document.getElementById("polly-start");
  const pauza = document.getElementById("polly-pauza");
  const stop = document.getElementById("polly-stop");
  const glos = document.getElementById("polly-glos");
  const stan = document.getElementById("polly-stan");
  if (!projekt || !przycisk || !pauza || !stop || !glos || !stan) return;

  const LIMIT = 2100; // ponizej serwerowego limitu i limitu Polly
  let segmenty = [], indeks = 0, odtwarzacz = null, url = null, kontroler = null;
  let aktywny = false, zatrzymany = false, generacja = 0;

  function komunikat(tresc, blad) {
    stan.textContent = tresc;
    stan.style.color = blad ? "var(--alarm)" : "";
  }
  function przyciski() {
    przycisk.disabled = aktywny;
    pauza.disabled = !aktywny;
    stop.disabled = !aktywny;
    pauza.textContent = zatrzymany ? "Wznów" : "Pauza";
    glos.disabled = aktywny;
  }
  function zwolnijAudio() {
    if (odtwarzacz) {
      odtwarzacz.onended = null;
      odtwarzacz.onerror = null;
      odtwarzacz.pause();
      odtwarzacz.removeAttribute("src");
      odtwarzacz.load();
      odtwarzacz = null;
    }
    if (url) { URL.revokeObjectURL(url); url = null; }
  }
  function zatrzymaj(tekst) {
    generacja++;
    if (kontroler) { kontroler.abort(); kontroler = null; }
    zwolnijAudio();
    aktywny = false;
    zatrzymany = false;
    segmenty = [];
    indeks = 0;
    przyciski();
    komunikat(tekst || "");
  }
  function podziel(tekst) {
    const wynik = [];
    let aktualny = "";
    const wyrazy = tekst.trim().match(/\S+\s*/gu) || [];
    for (const wyraz of wyrazy) {
      if (aktualny.length + wyraz.length > LIMIT && aktualny) {
        wynik.push(aktualny.trim());
        aktualny = "";
      }
      if (wyraz.length > LIMIT) {
        let reszta = wyraz;
        while (reszta.length > LIMIT) {
          wynik.push(reszta.slice(0, LIMIT));
          reszta = reszta.slice(LIMIT);
        }
        aktualny = reszta;
      } else {
        aktualny += wyraz;
      }
    }
    if (aktualny.trim()) wynik.push(aktualny.trim());
    return wynik;
  }
  function tekstDoCzytania() {
    // Zaznaczenie musi lezec W CALOSCI wewnatrz wyswietlonego projektu.
    const zaznaczenie = window.getSelection();
    if (zaznaczenie && !zaznaczenie.isCollapsed &&
        projekt.contains(zaznaczenie.anchorNode) &&
        projekt.contains(zaznaczenie.focusNode)) {
      return zaznaczenie.toString().trim();
    }
    return (projekt.innerText || projekt.textContent || "").trim();
  }
  async function odtworzKolejny() {
    if (!aktywny || zatrzymany) return;
    if (indeks >= segmenty.length) {
      zatrzymaj("Odsłuch zakończony. To nie jest formalne odczytanie aktu.");
      return;
    }
    const wersja = generacja;
    kontroler = new AbortController();
    komunikat("Przygotowuję fragment " + (indeks + 1) + " z " + segmenty.length + "…");
    try {
      const wybrane = glos.value.split(":");
      const odp = await api("/api/polly/synteza", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({tekst: segmenty[indeks], glos: wybrane[0], silnik: wybrane[1]}),
        signal: kontroler.signal
      });
      if (!odp.ok) {
        const dane = await odp.json().catch(() => ({}));
        throw new Error(typeof dane.detail === "string" ? dane.detail : "Błąd serwera (" + odp.status + ")");
      }
      const blob = await odp.blob();
      if (wersja !== generacja) return;
      url = URL.createObjectURL(blob);
      odtwarzacz = new Audio(url);
      odtwarzacz.onended = () => {
        zwolnijAudio();
        indeks++;
        void odtworzKolejny();
      };
      odtwarzacz.onerror = () => zatrzymaj("Nie udało się odtworzyć pliku MP3.");
      kontroler = null;
      komunikat("Odtwarzam fragment " + (indeks + 1) + " z " + segmenty.length + ".");
      if (!zatrzymany) await odtwarzacz.play();
    } catch (blad) {
      if (wersja !== generacja || blad.name === "AbortError") return;
      zatrzymaj("Odsłuch przerwany: " + blad.message);
      stan.style.color = "var(--alarm)";
    }
  }

  przycisk.addEventListener("click", () => {
    const tekst = tekstDoCzytania();
    if (!tekst) { komunikat("Najpierw wygeneruj projekt dokumentu.", true); return; }
    zatrzymaj();
    segmenty = podziel(tekst);
    aktywny = true;
    przyciski();
    if (tekst.includes("<<BRAK") || tekst.includes("<<WYBOR")) {
      komunikat("Uwaga: projekt zawiera nierozstrzygnięte znaczniki.");
    }
    void odtworzKolejny();
  });
  pauza.addEventListener("click", () => {
    if (!aktywny) return;
    zatrzymany = !zatrzymany;
    if (zatrzymany) {
      if (odtwarzacz) odtwarzacz.pause();
      komunikat("Pauza odczytu.");
    } else if (odtwarzacz) {
      odtwarzacz.play().catch(() => zatrzymaj("Odtwarzanie wymaga interakcji z przyciskiem."));
      komunikat("Wznowiono odczyt.");
    } else if (!kontroler) {
      // Trwajace zadanie HTTP samo uruchomi odtwarzanie po powrocie.
      // Nie wysylamy drugiego, rownoleglego zadania Polly.
      void odtworzKolejny();
    }
    przyciski();
  });
  stop.addEventListener("click", () => zatrzymaj("Odczyt zatrzymany."));
  // Zmiana projektu w trakcie sesji nie moze pozostawic starego glosu.
  new MutationObserver(() => { if (aktywny) zatrzymaj("Projekt zmieniono — odsłuch został zatrzymany."); })
    .observe(projekt, {subtree: true, childList: true, characterData: true});
  window.addEventListener("pagehide", () => zatrzymaj());
  przyciski();
})();
