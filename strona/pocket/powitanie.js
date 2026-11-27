"use strict";
// Ekran telefonu, który nie jest jeszcze połączony z żadną kancelarią: co to za aplikacja,
// jak ją sparować z komputerem konkretnej kancelarii i skaner kodu QR w samej aplikacji.
(() => {
  const pole = document.getElementById("pairing");
  if (!pole || typeof NotaraiTunnel === "undefined") return;   // const z tunnel.js, nie właściwość window

  const el = (tag, klasa, tekst) => {
    const wezel = document.createElement(tag);
    if (klasa) wezel.className = klasa;
    if (tekst) wezel.textContent = tekst;
    return wezel;
  };

  // Przyjmujemy wyłącznie kod parowania NotarAI prowadzący na tę stronę; wszystko inne odrzucamy.
  function fragmentParowania(tresc) {
    let adres;
    try {
      adres = new URL(String(tresc).trim());
    } catch (_) {
      return "";
    }
    if (adres.origin !== window.location.origin || adres.pathname !== window.location.pathname) return "";
    return NotaraiTunnel.parseLink(adres.hash) ? adres.hash : "";
  }

  function skaner(komunikat, przycisk) {
    const ramka = el("div", "powitanie-skaner");
    const obraz = el("video");
    obraz.setAttribute("playsinline", "");
    obraz.muted = true;
    const zamknij = el("button", "quiet", "Anuluj");
    ramka.append(obraz, zamknij);
    let strumien = null;
    let trwa = true;
    const koniec = () => {
      trwa = false;
      if (strumien) strumien.getTracks().forEach(sciezka => sciezka.stop());
      ramka.remove();
      przycisk.hidden = false;
    };
    zamknij.onclick = koniec;
    przycisk.hidden = true;
    przycisk.after(ramka);
    komunikat.textContent = "Skieruj aparat na kod QR na ekranie komputera kancelarii.";
    navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false }).then(async zrodlo => {
      strumien = zrodlo;
      if (!trwa) return koniec();
      obraz.srcObject = zrodlo;
      await obraz.play();
      const czytnik = new window.BarcodeDetector({ formats: ["qr_code"] });
      const szukaj = async () => {
        if (!trwa) return;
        let kody = [];
        try {
          kody = await czytnik.detect(obraz);
        } catch (_) { /* klatka jeszcze niegotowa */ }
        for (const kod of kody) {
          const fragment = fragmentParowania(kod.rawValue);
          if (fragment) {
            koniec();
            komunikat.textContent = "Kod odczytany. Łączę z kancelarią…";
            window.location.hash = fragment;
            window.location.reload();
            return;
          }
          komunikat.textContent = "To nie jest kod parowania NotarAI. Kod wyświetla program NotarAI na komputerze kancelarii po wpisaniu „dodaj telefon”.";
        }
        window.setTimeout(szukaj, 250);
      };
      szukaj();
    }).catch(() => {
      koniec();
      komunikat.textContent = "Nie mam dostępu do aparatu. Zezwól na aparat dla tej strony albo zeskanuj kod zwykłym aparatem telefonu.";
    });
  }

  function pokaz() {
    const karta = el("div", "powitanie");
    karta.append(el("h2", "", "Kancelaria w telefonie"));
    karta.append(el("p", "", "NotarAI Pocket pokazuje sprawy, dokumenty i rozmowę z asystentem Twojej kancelarii. "
      + "Ten telefon nie jest jeszcze połączony z żadną kancelarią."));
    karta.append(el("h3", "", "Jak połączyć telefon z kancelarią"));
    const kroki = el("ol", "powitanie-kroki");
    kroki.append(
      el("li", "", "Na komputerze kancelarii otwórz program NotarAI i napisz w oknie rozmowy: „dodaj telefon”."),
      el("li", "", "Program wyświetli jednorazowy kod QR tej kancelarii."),
      el("li", "", "Zeskanuj kod tym telefonem. Od tej chwili aplikacja łączy się z kancelarią sama, także poza biurem."));
    karta.append(kroki);

    const komunikat = el("p", "muted");
    komunikat.setAttribute("role", "status");
    if ("BarcodeDetector" in window && navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      const przycisk = el("button", "primary big", "Zeskanuj kod QR");
      przycisk.onclick = () => skaner(komunikat, przycisk);
      karta.append(przycisk);
    } else {
      komunikat.textContent = "Kod zeskanuj zwykłym aparatem telefonu: otworzy tę aplikację i połączy ją z kancelarią.";
    }
    karta.append(komunikat);

    karta.append(el("h3", "", "Co warto wiedzieć"));
    const fakty = el("ul", "powitanie-fakty");
    fakty.append(
      el("li", "", "Telefon łączy się tylko z tą kancelarią, której kod zeskanujesz. Kod działa jeden raz."),
      el("li", "", "Dokumenty zostają na komputerze kancelarii. Połączenie jest szyfrowane od telefonu do tego komputera."),
      el("li", "", "Notariusz może dać telefonowi wgląd w jedną sprawę albo sam odczyt i w każdej chwili go odłączyć poleceniem „cofnij telefon”."),
      el("li", "", "Komputer kancelarii musi być włączony, żeby telefon widział sprawy."));
    karta.append(fakty);

    const pomoc = el("p", "muted", "Kancelaria nie ma jeszcze programu NotarAI na komputer? Napisz: ");
    const poczta = el("a", "", "kontakt@notarai.pl");
    poczta.href = "mailto:kontakt@notarai.pl";
    pomoc.append(poczta, ".");
    karta.append(pomoc);
    pole.replaceChildren(karta);
    const tryb = document.getElementById("mode");
    if (tryb) tryb.hidden = true;
  }

  // pocket.js usuwa pole kodu, gdy strona jest otwarta pod publicznym adresem bez sparowania.
  let gotowe = false;
  const sprawdz = async () => {
    if (gotowe || pole.hidden || pole.querySelector("#code")) return;
    if (await NotaraiTunnel.hasIdentity().catch(() => true)) return;
    if (gotowe) return;
    gotowe = true;
    obserwator.disconnect();
    pokaz();
  };
  const obserwator = new MutationObserver(sprawdz);
  obserwator.observe(pole, { childList: true });
  sprawdz();
})();
