"use strict";

(() => {
  const panel = el("panel-kalendarza");
  const lista = el("wpisy-kalendarza");
  const komunikat = el("stan-kalendarza");
  const odtwarzacz = el("zrodlo-ustalenia");
  let url = null;
  let odtwarzanie = 0;

  function wyczyscOdtwarzacz() {
    odtwarzanie++;
    odtwarzacz.pause();
    odtwarzacz.removeAttribute("src");
    odtwarzacz.load();
    odtwarzacz.hidden = true;
    if (url) URL.revokeObjectURL(url);
    url = null;
  }

  async function odtworz(wpis) {
    wyczyscOdtwarzacz();
    const proba = odtwarzanie;
    try {
      const odpowiedz = await fetch("/v2/nagrania/" + wpis.id, {
        headers: {Authorization: "Bearer " + token}, cache: "no-store",
      });
      if (!odpowiedz.ok) throw new Error("Nagranie nie jest dostępne na tym stanowisku.");
      const plik = await odpowiedz.blob();
      if (proba !== odtwarzanie) return;
      url = URL.createObjectURL(plik);
      odtwarzacz.onloadedmetadata = () => {
        odtwarzacz.currentTime = wpis.sekunda;
        odtwarzacz.play().catch(() => {});
      };
      odtwarzacz.src = url;
      odtwarzacz.hidden = false;
    } catch (error) {
      komunikat.textContent = error.message;
    }
  }

  async function odswiez() {
    panel.hidden = false;
    try {
      const wpisy = await call("nagrania/kalendarz/wpisy");
      const sprawa = currentCase();
      const widoczne = sprawa ? wpisy.filter(wpis => wpis.sprawa === sprawa) : wpisy;
      komunikat.textContent = widoczne.length ? "" : "Brak ustaleń do pokazania.";
      lista.replaceChildren(...widoczne.map(wpis => {
        const pozycja = document.createElement("li");
        const naglowek = document.createElement("strong");
        const etykieta = wpis.termin
          ? (wpis.zatwierdzony ? "Zatwierdzony termin " : "Proponowany termin ") + wpis.termin.replace("T", " ")
          : wpis.rodzaj === "dokument" ? "Dokument do sprawdzenia" : "Ustalenie";
        naglowek.textContent = wpis.sprawa + " · " + etykieta;
        const cytat = document.createElement("p");
        cytat.textContent = wpis.tekst;
        pozycja.append(naglowek, cytat);
        if (token) {
          const zrodlo = document.createElement("button");
          const data = wpis.start
            ? new Date(Date.parse(wpis.start) + wpis.sekunda * 1000).toLocaleString("pl-PL", {timeZone: "Europe/Warsaw"})
            : "";
          zrodlo.textContent = "Nagranie " + (data || "+" + wpis.sekunda + " s");
          zrodlo.onclick = () => odtworz(wpis);
          pozycja.append(zrodlo);
        }
        if (wpis.termin && !wpis.zatwierdzony && scope !== "read") {
          const zatwierdz = document.createElement("button");
          zatwierdz.textContent = "Zatwierdź termin (60 min)";
          zatwierdz.onclick = async () => {
            zatwierdz.disabled = true;
            try {
              await call("nagrania/" + wpis.id + "/ustalenia/" + wpis.nr + "/zatwierdz", "POST");
              await odswiez();
            } catch (error) {
              komunikat.textContent = error.message;
              zatwierdz.disabled = false;
            }
          };
          pozycja.append(zatwierdz);
        }
        return pozycja;
      }));
    } catch (error) {
      lista.replaceChildren();
      komunikat.textContent = error.message;
    }
  }

  el("otworz-kalendarz").onclick = odswiez;
  el("case").addEventListener("change", () => {
    if (!panel.hidden) {
      wyczyscOdtwarzacz();
      odswiez();
    }
  });
  window.addEventListener("notarai-rozlacz", () => {
    wyczyscOdtwarzacz();
    lista.replaceChildren();
    panel.hidden = true;
  });
})();
