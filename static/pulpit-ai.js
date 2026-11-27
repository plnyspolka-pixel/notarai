/* Główny czat. Nigdy nie wykonujemy skutków zewnętrznych z odpowiedzi modelu
 * bez osobnego kliknięcia i okna zgody. Polecenia API wyłącznie ze stałej listy. */
(function(){
  "use strict";
  const $ai = id => document.getElementById(id);
  const panel = $ai("pulpit-ai");
  if (!panel) return;
  const rozmowa = $ai("pai-rozmowa");
  const pole = $ai("pai-polecenie");
  const status = $ai("pai-status");
  const btnWyslij = $ai("pai-wyslij");
  const mikrofon = $ai("pai-mikrofon");
  const historia = []; // bez localStorage: dane kancelarii nie zostają w urządzeniu
  const NAWIGACJA = Object.freeze({
    panel: () => pokaz(0),
    nowa_sprawa: () => $ai("btn-nowa")?.click(),
    odczyt: () => pokaz(2),
    projekt: () => pokaz(3),
    rejestry: () => pokaz(4),
    klikamy: () => pokaz(5),
    kalendarz: () => pokaz(6),
    osoby: () => pokaz(7),
    przesylki: () => pokaz(8),
    poczta: () => pokaz(12),
    styl: () => pokaz(9),
    ksiegi: () => pokaz(10),
    giif: () => pokaz(11),
    poswiadczenia: () => location.assign("/poswiadczenia"),
    stenogramy: () => location.assign("/stenogramy"),
    ustawienia: () => $ai("btn-asystent")?.click(),
    pomocnik: () => $ai("btn-pomocnik")?.click(),
    taksa: () => window.open("/kalkulator", "_blank", "noopener"),
  });
  let zajety = false, recorder = null, strumien = null, kawalki = [], nagrywa = false;
  let doZatwierdzenia = null;
  let doNaprawienia = null;
  let stopTimer = null;
  let pokolenieCzatu = 0;

  function powiadom(tekst, blad=false) {
    status.textContent = tekst || "";
    status.style.color = blad ? "#b52e40" : "";
  }
  function dodajWiadomosc(rola, tekst) {
    const el = document.createElement("div");
    el.className = "pai-wiadomosc " + (rola === "uzytkownik" ? "pai-uzytkownik" : "pai-asystent");
    el.textContent = tekst;
    rozmowa.append(el);
    rozmowa.scrollTop = rozmowa.scrollHeight;
  }
  function dodajAkcje(akcje) {
    for (const a of (akcje || []).slice(0, 5)) {
      if (a.typ === "otworz" && Object.prototype.hasOwnProperty.call(NAWIGACJA, a.ekran)) {
        // Nawigacja jest bezpieczna - nie zapisuje ani nie wysyła danych.
        NAWIGACJA[a.ekran]();
      } else if (a.typ === "przygotuj_rejestr" && ["uldk","krs","vat"].includes(a.usluga) && typeof a.identyfikator === "string" && a.identyfikator.length <= 64) {
        const karta = document.createElement("div");
        karta.className = "pai-akcja";
        const opis = document.createElement("p");
        opis.textContent = "Zapytanie do " + a.usluga.toUpperCase() + ": " + a.identyfikator;
        const przycisk = document.createElement("button");
        przycisk.type = "button";
        przycisk.textContent = "Sprawdź formularz";
        przycisk.onclick = () => {
          const usluga = $ai("rp-usluga"), identyfikator = $ai("rp-id");
          if (!usluga || !identyfikator) return;
          NAWIGACJA.rejestry();
          usluga.value = a.usluga;
          usluga.dispatchEvent(new Event("change"));
          identyfikator.value = a.identyfikator;
          identyfikator.focus();
        };
        karta.append(opis,przycisk);
        rozmowa.append(karta);
      } else if (a.typ === "potwierdz_windows" && a.komputer && a.cel) {
        const karta = document.createElement("div");
        karta.className = "pai-akcja";
        const naglowek = document.createElement("b");
        naglowek.textContent = "Polecenie dla " + (a.nazwa || "komputera");
        const opis = document.createElement("p");
        opis.textContent = a.cel;
        const przycisk = document.createElement("button");
        przycisk.type = "button";
        przycisk.textContent = "Sprawdź i zatwierdź";
        przycisk.onclick = () => pokazZgode(a);
        karta.append(naglowek, opis, przycisk);
        rozmowa.append(karta);
      } else if (a.typ === "potwierdz_naprawe" && a.opis) {
        const karta = document.createElement("div");
        karta.className = "pai-akcja";
        const naglowek = document.createElement("b");
        naglowek.textContent = "Samonaprawa · zgłoszenie do zatwierdzenia";
        const opis = document.createElement("p");
        opis.textContent = a.opis;
        const przycisk = document.createElement("button");
        przycisk.type = "button";
        przycisk.textContent = "Sprawdź i zgłoś usterkę";
        przycisk.onclick = () => pokazZgodeNaprawy(a.opis);
        karta.append(naglowek, opis, przycisk);
        rozmowa.append(karta);
      } else if (a.typ === "postep_napraw" && Array.isArray(a.naprawy)) {
        const karta = document.createElement("div");
        karta.className = "pai-akcja";
        const naglowek = document.createElement("b");
        naglowek.textContent = "Postęp samonaprawy";
        karta.append(naglowek);
        if (!a.naprawy.length) {
          const brak = document.createElement("p");
          brak.textContent = "Brak zgłoszeń samonaprawy w tej kancelarii.";
          karta.append(brak);
        }
        for (const n of a.naprawy.slice(0, 5)) {
          const p = document.createElement("p");
          const procent = Number.isFinite(n.procent) ? " · " + n.procent + "%" : "";
          p.textContent = (n.numer || "Zgłoszenie") + " · " +
            (n.etykieta || n.etap || "Nieznany status") + procent;
          karta.append(p);
        }
        rozmowa.append(karta);
      }
    }
    rozmowa.scrollTop = rozmowa.scrollHeight;
  }
  async function wyslij() {
    if (zajety || nagrywa) return;
    const tresc = pole.value.trim();
    if (!tresc) return;
    // A direct KW request opens the existing form; retrieval still requires consent.
    const kw = tresc.match(/\b[A-Z0-9]{4}\s*\/\s*\d{8}\s*\/\s*\d\b/i);
    if (kw && /^(?:proszę\s+)?(?:pobierz|sprawdź|otwórz|ściągnij)\s+(?:(?:aktualną\s+)?(?:kw|księgę(?:\s+wieczystą)?)\s*)?[: ]*[A-Z0-9]{4}\s*\/\s*\d{8}\s*\/\s*\d\s*[.!]?$/i.test(tresc)) {
      if (window.otworzKsiegeWieczysta?.(kw[0].toUpperCase().replace(/\s+/g, ""))) {
        pole.value = "";
        dodajWiadomosc("uzytkownik", tresc);
        dodajWiadomosc("asystent", "Otworzyłem formularz EKW. Wybierz sprawę, jeśli nie jest otwarta, i potwierdź pobranie.");
      } else {
        powiadom("Pobieranie EKW nie jest dostępne w tym trybie lub na tym koncie.", true);
      }
      return;
    }
    const poprzednia = historia.slice(-12);
    const sesja = pokolenieCzatu;
    pole.value = "";
    dodajWiadomosc("uzytkownik", tresc);
    zajety = true; btnWyslij.disabled = true; mikrofon.disabled = true;
    powiadom("Analizuję polecenie…");
    try {
      const odp = await api("/api/pulpit-ai/rozmowa", {
        method: "POST", headers: {"Content-Type":"application/json"},
        body: JSON.stringify({wiadomosc: tresc, historia: poprzednia})
      });
      const dane = await odp.json().catch(() => ({}));
      if (sesja !== pokolenieCzatu) return;
      if (!odp.ok) throw new Error(dane.detail || "Nie udało się wykonać polecenia.");
      const tekst = dane.odpowiedz || "Wybierz dalszą czynność.";
      dodajWiadomosc("asystent", tekst);
      historia.push({rola:"uzytkownik",tresc}, {rola:"asystent",tresc:tekst});
      if (historia.length > 16) historia.splice(0, historia.length - 16);
      dodajAkcje(dane.akcje);
      powiadom("");
    } catch (e) {
      if (sesja !== pokolenieCzatu) return;
      // Bez przechowywania poufnej treści poza sesją.
      dodajWiadomosc("asystent", "Nie udało się odpowiedzieć. Polecenie nie zostało wykonane.");
      pole.value = tresc;
      powiadom(e.message || "Błąd połączenia", true);
    } finally {
      zajety = false; btnWyslij.disabled = false; mikrofon.disabled = false;
    }
  }
  function pokazZgode(akcja) {
    doZatwierdzenia = akcja;
    $ai("pai-zgoda-komputer").textContent = akcja.nazwa || "Komputer";
    $ai("pai-zgoda-cel").textContent = akcja.cel;
    $ai("pai-zgoda-stan").textContent = "";
    $ai("pai-zgoda-wykonaj").disabled = false;
    $ai("pai-zgoda").showModal();
  }
  $ai("pai-zgoda-anuluj").onclick = () => {
    doZatwierdzenia = null; $ai("pai-zgoda").close();
  };
  $ai("pai-zgoda-wykonaj").onclick = async () => {
    const a = doZatwierdzenia;
    if (!a) return;
    const btn = $ai("pai-zgoda-wykonaj");
    btn.disabled = true;
    $ai("pai-zgoda-stan").textContent = "Przekazuję do wskazanego komputera…";
    try {
      // Endpoint dodany przez PR #124. Do czasu jego scalenia: czytelny błąd,
      // żadnych alternatywnych kanałów wykonywania polecenia.
      const odp = await api("/api/urzadzenia/polecenia", {
        method: "POST", headers: {"Content-Type":"application/json"},
        body: JSON.stringify({komputer:a.komputer, cel:a.cel, dozwolone_hosty:[]})
      });
      const wynik = await odp.json().catch(() => ({}));
      if (!odp.ok) throw new Error(odp.status === 404
        ? "Mobilne polecenia Windows będą dostępne po wdrożeniu modułu pomocnika."
        : (wynik.detail || "Komputer odmówił przyjęcia zadania."));
      $ai("pai-zgoda").close();
      dodajWiadomosc("asystent", "Polecenie przyjęte do kolejki komputera. "
        + "Nie oznacza to jeszcze wykonania ani wysyłki.");
      doZatwierdzenia = null;
      powiadom("Komputer przyjął polecenie. Wynik sprawdź w panelu Pomocnik.");
    } catch (e) {
      $ai("pai-zgoda-stan").textContent = e.message;
      btn.disabled = false;
    }
  };

  function pokazZgodeNaprawy(opis) {
    doNaprawienia = opis;
    $ai("pai-naprawa-opis").value = opis;
    $ai("pai-naprawa-stan").textContent = "";
    $ai("pai-naprawa-zglos").disabled = false;
    $ai("pai-naprawa-zgoda").showModal();
  }
  $ai("pai-naprawa-anuluj").onclick = () => {
    doNaprawienia = null;
    $ai("pai-naprawa-zgoda").close();
  };
  $ai("pai-naprawa-zglos").onclick = async () => {
    if (!doNaprawienia) return;
    const opis = $ai("pai-naprawa-opis").value.trim();
    if (opis.length < 12 || opis.length > 2000) {
      $ai("pai-naprawa-stan").textContent = "Opis musi mieć od 12 do 2000 znaków.";
      return;
    }
    const sesja = pokolenieCzatu;
    const btn = $ai("pai-naprawa-zglos");
    btn.disabled = true;
    $ai("pai-naprawa-stan").textContent = "Przekazuję do istniejącego modułu samonaprawy…";
    try {
      const odp = await api("/api/pulpit-ai/samonaprawa/zglos", {
        method: "POST", headers: {"Content-Type":"application/json"},
        body: JSON.stringify({opis})
      });
      const wynik = await odp.json().catch(() => ({}));
      if (sesja !== pokolenieCzatu) return;
      if (!odp.ok || wynik.przyjeto !== true) throw new Error(
        wynik.detail || wynik.uwaga || "Zgłoszenie nie zostało przyjęte.");
      doNaprawienia = null;
      $ai("pai-naprawa-zgoda").close();
      dodajWiadomosc("asystent", "Samonaprawa przyjęła zgłoszenie nr " +
        (wynik.numer || "bez numeru") + ". " +
        (wynik.duplikat ? "To już zgłoszona usterka. " : "") +
        "Napisz «sprawdź postęp samonaprawy», żeby poznać aktualny stan.");
      powiadom("Zgłoszenie przekazane.");
    } catch (e) {
      if (sesja !== pokolenieCzatu) return;
      $ai("pai-naprawa-stan").textContent = e.message || "Nie udało się zgłosić usterki.";
      btn.disabled = false;
    }
  };

  async function nagrywaj() {
    if (zajety) return;
    if (nagrywa) {
      clearTimeout(stopTimer);
      nagrywa = false;
      mikrofon.dataset.nagrywa = "0";
      mikrofon.textContent = "🎙 Nagraj";
      recorder?.stop(); // onstop zajmuje się transkrypcją i zamknięciem strumienia
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      powiadom("Ta przeglądarka nie obsługuje nagrywania dźwięku.", true);
      return;
    }
    try {
      strumien = await navigator.mediaDevices.getUserMedia({audio:true});
      const typy = ["audio/webm;codecs=opus","audio/mp4","audio/webm"];
      const typ = typy.find(x => MediaRecorder.isTypeSupported(x));
      recorder = typ ? new MediaRecorder(strumien, {mimeType:typ}) : new MediaRecorder(strumien);
      kawalki = [];
      recorder.ondataavailable = e => { if (e.data?.size) kawalki.push(e.data); };
      recorder.onerror = () => {
        powiadom("Nie udało się nagrać wiadomości.", true);
        strumien?.getTracks().forEach(t => t.stop());
        nagrywa = false;
      };
      const sesjaNagrania = pokolenieCzatu;
      recorder.onstop = async () => {
        if (sesjaNagrania !== pokolenieCzatu) return;
        strumien?.getTracks().forEach(t => t.stop());
        strumien = null;
        const blob = new Blob(kawalki, {type:recorder.mimeType || "audio/webm"});
        if (!blob.size || blob.size > 15 * 1024 * 1024) {
          powiadom("Nagranie jest puste lub zbyt duże (maks. 15 MB).", true);
          return;
        }
        zajety = true; btnWyslij.disabled = true; mikrofon.disabled = true;
        powiadom("Zamieniam głos na tekst…");
        try {
          const format = blob.type.includes("mp4") ? "mp4" : "webm";
          const fd = new FormData();
          fd.append("audio", blob, "polecenie." + format);
          const odp = await api("/api/pulpit-ai/glos", {method:"POST",body:fd});
          let wynik = await odp.json().catch(() => ({}));
          if (!odp.ok) throw new Error(wynik.detail || "Transkrypcja nie jest teraz dostępna.");
          if (wynik.stan === "przetwarzanie" && wynik.zadanie) {
            let gotowe = false;
            for (let proba = 0; proba < 35; proba++) {
              await new Promise(resolve => setTimeout(resolve, 2200));
              const odczyt = await api("/api/pulpit-ai/glos/" + encodeURIComponent(wynik.zadanie));
              wynik = await odczyt.json().catch(() => ({}));
              if (!odczyt.ok) throw new Error(wynik.detail || "Nie udało się odczytać głosówki.");
              if (wynik.stan === "gotowe") { gotowe = true; break; }
            }
            if (!gotowe) throw new Error("Rozpoznawanie głosu nadal trwa. Spróbuj ponownie za chwilę.");
          }
          if (sesjaNagrania !== pokolenieCzatu) return;
          if (!wynik.tekst?.trim()) throw new Error("Nie rozpoznano słów w nagraniu.");
          pole.value = [pole.value.trim(), wynik.tekst.trim()].filter(Boolean).join(" ");
          pole.focus();
          powiadom("Sprawdź tekst i naciśnij „Wyślij”. Nic nie wysyłamy automatycznie.");
        } catch (e) {
          if (sesjaNagrania === pokolenieCzatu) powiadom(e.message, true);
        } finally {
          zajety = false; btnWyslij.disabled = false; mikrofon.disabled = false;
        }
      };
      recorder.start();
      nagrywa = true;
      mikrofon.dataset.nagrywa = "1";
      mikrofon.textContent = "■ Zakończ";
      powiadom("Nagrywanie trwa. Dotknij „Zakończ” (maksymalnie 60 sekund).");
      stopTimer = setTimeout(() => { if (nagrywa) nagrywaj(); }, 60000);
    } catch {
      strumien?.getTracks().forEach(t => t.stop());
      powiadom("Nie przyznano dostępu do mikrofonu.", true);
    }
  }
  $ai("pai-form").addEventListener("submit", ev => { ev.preventDefault(); wyslij(); });
  pole.addEventListener("keydown", ev => {
    if (ev.key === "Enter" && !ev.shiftKey && !ev.isComposing) {
      ev.preventDefault(); wyslij();
    }
  });
  mikrofon.onclick = nagrywaj;
  $ai("btn-pulpit-ai").onclick = () => pokaz(13);
  $ai("pai-pokaz-panel").onclick = () => pokaz(0);
  document.querySelectorAll("[data-pai-prompt]").forEach(btn => {
    btn.addEventListener("click", () => { pole.value = btn.dataset.paiPrompt; pole.focus(); });
  });
  // Reset historii po wylogowaniu - ponowne użycie tej samej przeglądarki
  // nie może wyświetlić odpowiedzi z wcześniejszej sesji.
  window.wyczyscPulpitAI = () => {
    pokolenieCzatu++;
    historia.length = 0;
    rozmowa.replaceChildren();
    dodajWiadomosc("asystent", "W czym pomóc kancelarii?");
    pole.value = "";
    if (nagrywa) {
      clearTimeout(stopTimer);
      nagrywa = false;
      if (recorder) { recorder.onstop = null; recorder.ondataavailable = null; recorder.stop(); }
      strumien?.getTracks().forEach(t => t.stop());
      strumien = null; kawalki = [];
      mikrofon.dataset.nagrywa = "0";
      mikrofon.textContent = "🎙 Nagraj";
    }
    doZatwierdzenia = null;
    doNaprawienia = null;
    if ($ai("pai-zgoda").open) $ai("pai-zgoda").close();
    if ($ai("pai-naprawa-zgoda").open) $ai("pai-naprawa-zgoda").close();
  };
  window.wyczyscPulpitAI();
  // Serwer sprawdza dostępność rozpoznawania mowy w tym wariancie instalacji.
  api("/api/pulpit-ai/narzedzia").then(async odp => {
    if (!odp.ok) return;
    const wynik = await odp.json();
    if (!wynik.glos) {
      mikrofon.disabled = true;
      mikrofon.title = "Rozpoznawanie mowy nie jest dostępne w tej instalacji.";
    }
  }).catch(() => {});
})();
