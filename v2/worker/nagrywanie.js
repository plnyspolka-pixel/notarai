"use strict";

const el = id => document.getElementById(id);
const stan = komunikat => { el("stan").textContent = komunikat; };
const limitFragmentu = 8 * 1024 * 1024;
let sesja = null;

async function api(token, sciezka = "", metoda = "GET", dane) {
  const headers = {Authorization: "Bearer " + token};
  if (dane && !(dane instanceof Blob)) {
    headers["Content-Type"] = "application/json";
    dane = JSON.stringify(dane);
  }
  const odpowiedz = await fetch("/v2/nagrania" + sciezka, {method: metoda, headers, body: dane});
  if (!odpowiedz.ok) throw new Error("Zapis lokalny zwrócił HTTP " + odpowiedz.status + ".");
  return odpowiedz;
}

function mikrofonyDoDolaczenia(urzadzenia, pierwszy) {
  const grupy = new Set([pierwszy.groupId || pierwszy.deviceId]);
  return urzadzenia.filter(urzadzenie => {
    const {kind, deviceId, groupId} = urzadzenie;
    if (kind !== "audioinput" || !deviceId || ["default", "communications", pierwszy.deviceId].includes(deviceId)) return false;
    const grupa = groupId || deviceId;
    if (grupy.has(grupa)) return false;
    grupy.add(grupa);
    return true;
  });
}

function zwolnij(b) {
  clearInterval(b.detektor);
  clearTimeout(b.limitUzbrojenia);
  for (const strumien of b.zrodla) strumien.getTracks().forEach(tor => tor.stop());
  b.audio?.close().catch(() => {});
}

function gotowe(b, komunikat) {
  zwolnij(b);
  if (sesja !== b) return;
  sesja = null;
  el("ustawienia").inert = false;
  el("recznie").disabled = true;
  el("stop").disabled = true;
  stan(komunikat);
}

function zatrzymaj(b) {
  if (sesja !== b || b.konczy) return;
  b.konczy = true;
  if (b.rec?.state === "recording") {
    b.rec.stop();
    zwolnij(b);
    el("recznie").disabled = true;
    el("stop").disabled = true;
    stan("Domykam lokalny zapis…");
  } else {
    gotowe(b, b.blad || "Sesja rozbrojona.");
  }
}

function nagrywaj(b) {
  if (sesja !== b || b.rec || b.konczy) return;
  clearInterval(b.detektor);
  clearTimeout(b.limitUzbrojenia);
  try {
    const formaty = b.wyjscie.getVideoTracks().length
      ? ["video/webm;codecs=vp8,opus", "video/mp4"]
      : ["audio/webm;codecs=opus", "audio/mp4", "audio/ogg;codecs=opus"];
    const mimeType = formaty.find(typ => MediaRecorder.isTypeSupported(typ));
    if (!mimeType) throw new Error("Przeglądarka nie obsługuje wymaganego formatu nagrania.");
    const rec = new MediaRecorder(b.wyjscie, {mimeType, audioBitsPerSecond: 64000, videoBitsPerSecond: 1000000});
    b.rec = rec;
    const sciezka = "/" + b.id;
    let kolejka;
    let numer = 0;
    let zalegle = 0;

    function blad(e) {
      b.blad = e.message + " Identyfikator sesji: " + b.id;
      zatrzymaj(b);
    }

    rec.ondataavailable = ({data}) => {
      if (!data.size || b.blad) return;
      zalegle += data.size;
      for (let od = 0; od < data.size; od += limitFragmentu) {
        const fragment = data.slice(od, od + limitFragmentu);
        const nr = numer++;
        kolejka = kolejka.then(async () => {
          if (b.blad) return;
          await api(b.token, sciezka + "/czesci/" + nr, "PUT", fragment);
        }).catch(blad).finally(() => { zalegle -= fragment.size; });
      }
      if (zalegle > 32 * 1024 * 1024) blad(new Error("Magazyn nie nadąża z zapisem."));
    };
    rec.onerror = () => {
      b.blad = "Rejestrator przerwał zapis. Identyfikator sesji: " + b.id;
      zwolnij(b);
    };
    rec.onstop = async () => {
      try {
        await kolejka;
        if (b.blad) throw new Error(b.blad);
        if (!numer) throw new Error("Nagranie nie zawiera dźwięku ani obrazu.");
        await api(b.token, sciezka + "/koniec", "PUT", {czesci: numer});
        gotowe(b, b.przerwano ? "Źródło odłączone. Zapisano materiał do chwili przerwania." : "Nagranie zapisane lokalnie.");
      } catch (e) {
        gotowe(b, e.message);
      }
    };
    rec.start(2000);
    const format = mimeType.split(";")[0];
    kolejka = api(b.token, sciezka, "PUT", {sprawa: b.sprawa, format}).catch(blad);
    el("recznie").disabled = true;
    stan("Trwa nagrywanie. " + b.zrodlaOpis);
  } catch (e) {
    gotowe(b, "Nie udało się uruchomić rejestratora. " + e.message);
  }
}

async function uzbroj(e) {
  e.preventDefault();
  if (sesja) return;
  const sprawa = el("sprawa").value.trim();
  if (!sprawa) return stan("Podaj sprawę lub opis notatki.");
  const b = {id: crypto.randomUUID(), sprawa, token: el("token").value.trim(), zrodla: []};
  sesja = b;
  el("ustawienia").inert = true;
  el("stop").disabled = false;
  stan("Uruchamiam urządzenia…");
  const gabinet = el("stanowisko").value === "gabinet";
  async function otworz(ustawienia) {
    const strumien = await navigator.mediaDevices.getUserMedia(ustawienia);
    if (sesja !== b) {
      strumien.getTracks().forEach(tor => tor.stop());
      throw new Error("Sesja rozbrojona");
    }
    b.zrodla.push(strumien);
    for (const tor of strumien.getTracks()) tor.addEventListener("ended", () => {
      b.przerwano = true;
      if (!b.rec) b.blad = "Przed zapisem odłączono urządzenie.";
      zatrzymaj(b);
    });
    return strumien;
  }
  try {
    await api(b.token);
    if (sesja !== b) return;
    b.audio = new AudioContext();
    const miks = b.audio.createMediaStreamDestination();
    const analizator = b.audio.createAnalyser();
    analizator.fftSize = 1024;
    const suma = b.audio.createGain();
    suma.connect(miks);
    suma.connect(analizator);
    const pierwszy = await otworz({audio: true, video: false});
    const urzadzenia = await navigator.mediaDevices.enumerateDevices();
    const wejscia = [pierwszy];
    let niedostepne = 0;
    for (const urzadzenie of mikrofonyDoDolaczenia(urzadzenia, pierwszy.getAudioTracks()[0].getSettings())) {
      try {
        wejscia.push(await otworz({audio: {deviceId: {exact: urzadzenie.deviceId}}, video: false}));
      } catch (e) {
        if (sesja !== b) return;
        niedostepne++;
      }
    }
    suma.gain.value = 1 / wejscia.length;
    for (const wejscie of wejscia) b.audio.createMediaStreamSource(wejscie).connect(suma);
    const preferowana = urzadzenia.find(d => d.kind === "videoinput" && /live!?.*cam|creative/i.test(d.label));
    const wideo = gabinet ? await otworz({
      audio: false, video: {...(preferowana ? {deviceId: {ideal: preferowana.deviceId}} : {}),
        width: {ideal: 1280}, height: {ideal: 720}, frameRate: {ideal: 24, max: 30}},
    }) : null;
    b.wyjscie = new MediaStream([...miks.stream.getAudioTracks(), ...(wideo?.getVideoTracks() || [])]);
    await b.audio.resume();
    if (sesja !== b) return;
    el("recznie").disabled = false;
    b.zrodlaOpis = "Aktywne mikrofony: " + wejscia.length + "."
      + (niedostepne ? " Niedostępne wejścia: " + niedostepne + "." : "");
    stan("Sesja uzbrojona. Zapis jeszcze się nie rozpoczął. " + b.zrodlaOpis);
    b.limitUzbrojenia = setTimeout(() => zatrzymaj(b), 5 * 60000);
    if (el("automatyczny").checked) {
      const probki = new Float32Array(analizator.fftSize);
      let kolejne = 0;
      b.detektor = setInterval(() => {
        analizator.getFloatTimeDomainData(probki);
        const energia = probki.reduce((suma, p) => suma + p * p, 0) / probki.length;
        kolejne = energia > 0.0001 ? kolejne + 1 : Math.max(0, kolejne - 1);
        if (kolejne >= 3) nagrywaj(b);
      }, 100);
    }
  } catch (e) {
    if (sesja === b) gotowe(b, "Nie udało się uzbroić sesji. " + e.message);
  }
}

async function lista() {
  const token = el("token").value.trim();
  const rekordy = await (await api(token)).json();
  const elementy = rekordy.map(rekord => {
    const wiersz = document.createElement("li");
    wiersz.textContent = rekord.sprawa + (rekord.gotowe ? " " : " (zapis nieukończony)");
    if (rekord.gotowe) {
      const pobierz = document.createElement("button");
      pobierz.textContent = "Pobierz";
      pobierz.onclick = async () => {
        try {
          const odpowiedz = await api(token, "/" + rekord.id);
          const nazwa = odpowiedz.headers.get("Content-Disposition").split('"')[1];
          const url = URL.createObjectURL(await odpowiedz.blob());
          const link = document.createElement("a");
          link.href = url;
          link.download = nazwa;
          link.click();
          setTimeout(() => URL.revokeObjectURL(url), 60000);
        } catch (e) { stan(e.message); }
      };
      wiersz.append(pobierz);
    }
    return wiersz;
  });
  el("nagrania").replaceChildren(...elementy);
}

el("ustawienia").onsubmit = uzbroj;
el("recznie").onclick = () => { if (sesja) nagrywaj(sesja); };
el("stop").onclick = () => { if (sesja) zatrzymaj(sesja); };
el("lista").onclick = () => lista().catch(e => stan(e.message));
window.addEventListener("beforeunload", e => {
  if (sesja) { e.preventDefault(); e.returnValue = ""; }
});
window.addEventListener("pagehide", () => { if (sesja) zwolnij(sesja); });
