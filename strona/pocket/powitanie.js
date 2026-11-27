"use strict";
// Ekran telefonu, który nie jest jeszcze połączony z żadną kancelarią. Dwie drogi:
// 1) konto kancelarii w NotarAI (app.notarai.pl): działa od razu, bez komputera w kancelarii,
// 2) połączenie z komputerem konkretnej kancelarii kodem QR (skaner w samej aplikacji).
(() => {
  const pole = document.getElementById("pairing");
  if (!pole || typeof NotaraiTunnel === "undefined") return;   // const z tunnel.js, nie właściwość window

  const KONTO = "https://app.notarai.pl/";
  const TRYB = "notarai-pocket-tryb";          // "konto": kolejne otwarcia idą prosto do konta kancelarii
  const pamiec = {
    czytaj: () => { try { return localStorage.getItem(TRYB) || ""; } catch (_) { return ""; } },
    zapisz: wartosc => { try { wartosc ? localStorage.setItem(TRYB, wartosc) : localStorage.removeItem(TRYB); } catch (_) { /* tryb prywatny */ } },
  };
  // Skrót „Połącz z komputerem kancelarii” (?wybor=1) zawsze wraca do tego ekranu. Kod QR też:
  // pocket.js zaczyna wtedy parowanie i zostawia pole kodu, więc niżej nic nie przekierowujemy.
  const parametry = new URLSearchParams(window.location.search);
  const chceWyboru = parametry.has("wybor");

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
    karta.append(el("p", "", "Sprawy, dokumenty, kalendarz i asystent Twojej kancelarii. Wybierz, jak chcesz zacząć."));

    karta.append(el("h3", "", "Masz konto kancelarii w NotarAI?"));
    karta.append(el("p", "muted", "Zaloguj się tak jak na komputerze. Działa od razu, także gdy w kancelarii nikogo nie ma."));
    const konto = el("button", "primary big", "Zaloguj się kontem kancelarii");
    konto.onclick = () => {
      pamiec.zapisz("konto");
      window.location.assign(KONTO);
    };
    karta.append(konto);
    const rejestracja = el("p", "muted", "Kancelaria nie ma jeszcze konta? ");
    const zaloz = el("a", "", "Załóż konto");
    zaloz.href = KONTO + "rejestracja";
    rejestracja.append(zaloz, ".");
    karta.append(rejestracja);

    karta.append(el("h3", "powitanie-odstep", "Albo połącz telefon z komputerem kancelarii"));
    karta.append(el("p", "muted", "Dla kancelarii, które trzymają akta na własnym komputerze z programem NotarAI."));
    const kroki = el("ol", "powitanie-kroki");
    kroki.append(
      el("li", "", "Na komputerze kancelarii otwórz program NotarAI i napisz w oknie rozmowy: „dodaj telefon”."),
      el("li", "", "Program wyświetli jednorazowy kod QR tej kancelarii."),
      el("li", "", "Zeskanuj kod tym telefonem. Od tej chwili aplikacja łączy się z kancelarią sama, także poza biurem."));
    karta.append(kroki);

    const komunikat = el("p", "muted");
    komunikat.setAttribute("role", "status");
    if ("BarcodeDetector" in window && navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      const przycisk = el("button", "big", "Zeskanuj kod QR");
      przycisk.onclick = () => skaner(komunikat, przycisk);
      karta.append(przycisk);
    } else {
      komunikat.textContent = "Kod zeskanuj zwykłym aparatem telefonu: otworzy tę aplikację i połączy ją z kancelarią.";
    }
    karta.append(komunikat);

    karta.append(el("h3", "", "Co warto wiedzieć o połączeniu z komputerem"));
    const fakty = el("ul", "powitanie-fakty");
    fakty.append(
      el("li", "", "Telefon łączy się tylko z tą kancelarią, której kod zeskanujesz. Kod działa jeden raz."),
      el("li", "", "Dokumenty zostają na komputerze kancelarii. Połączenie jest szyfrowane od telefonu do tego komputera."),
      el("li", "", "Notariusz może dać telefonowi wgląd w jedną sprawę albo sam odczyt i w każdej chwili go odłączyć poleceniem „cofnij telefon”."),
      el("li", "", "Komputer kancelarii musi być włączony, żeby telefon widział sprawy."));
    karta.append(fakty);

    const pomoc = el("p", "muted", "Pytania? Napisz: ");
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
    if (chceWyboru) pamiec.zapisz("");
    if (pamiec.czytaj() === "konto") {
      // Wybrano konto kancelarii: idziemy prosto do niego, chyba że czeka nowsza paczka aplikacji.
      const nowa = await Promise.race([
        Promise.resolve(window.notaraiNowaPaczka).catch(() => false),
        new Promise(koniec => window.setTimeout(() => koniec(false), 1500)),
      ]);
      if (!nowa) {
        window.location.replace(KONTO);
        return;
      }
    }
    pokaz();
  };
  const obserwator = new MutationObserver(sprawdz);
  obserwator.observe(pole, { childList: true });
  sprawdz();
})();
