"use strict";

const el = id => document.getElementById(id);
const stanowisko = el("stanowisko");
const mikrofon = el("mikrofon");
const kamera = el("kamera");
const podglad = el("podglad");
let strumien = null;
let kontekst = null;
let animacja = 0;
let proba = 0;

function zatrzymaj(komunikat = "Urządzenia są wyłączone.") {
  proba++;
  cancelAnimationFrame(animacja);
  strumien?.getTracks().forEach(tor => tor.stop());
  strumien = null;
  kontekst?.close().catch(() => {});
  kontekst = null;
  podglad.srcObject = null;
  podglad.hidden = true;
  el("poziom").value = 0;
  el("uruchom").disabled = false;
  el("stop").disabled = true;
  el("stan").textContent = komunikat;
}

function uzupelnij(select, urzadzenia, rodzaj, nazwa, aktywny) {
  const lista = urzadzenia.filter(urzadzenie => urzadzenie.kind === rodzaj && urzadzenie.deviceId);
  select.replaceChildren(new Option("Domyślne urządzenie", ""), ...lista.map((urzadzenie, indeks) =>
    new Option(urzadzenie.label || nazwa + " " + (indeks + 1), urzadzenie.deviceId)));
  if (lista.some(urzadzenie => urzadzenie.deviceId === aktywny)) select.value = aktywny;
}

async function uruchom() {
  zatrzymaj("Czekam na dostęp do urządzeń…");
  const numer = proba;
  const gabinet = stanowisko.value === "gabinet";
  const wymagania = select => select.value ? {deviceId: {exact: select.value}} : true;
  el("uruchom").disabled = true;
  el("stop").disabled = false;
  try {
    const nowy = await navigator.mediaDevices.getUserMedia({
      audio: wymagania(mikrofon),
      video: gabinet ? wymagania(kamera) : false,
    });
    if (numer !== proba) {
      nowy.getTracks().forEach(tor => tor.stop());
      return;
    }
    strumien = nowy;
    for (const tor of nowy.getTracks()) {
      tor.addEventListener("ended", () => {
        if (numer === proba) zatrzymaj("Urządzenie zostało odłączone. Podłącz je i ponów test.");
      });
    }
    const urzadzenia = await navigator.mediaDevices.enumerateDevices();
    if (numer !== proba) return;
    uzupelnij(mikrofon, urzadzenia, "audioinput", "Mikrofon", nowy.getAudioTracks()[0]?.getSettings().deviceId);
    uzupelnij(kamera, urzadzenia, "videoinput", "Kamera", nowy.getVideoTracks()[0]?.getSettings().deviceId);
    if (gabinet) {
      podglad.srcObject = new MediaStream(nowy.getVideoTracks());
      podglad.hidden = false;
    }
    kontekst = new AudioContext();
    const analizator = kontekst.createAnalyser();
    kontekst.createMediaStreamSource(nowy).connect(analizator);
    const probki = new Float32Array(analizator.fftSize);
    function mierz() {
      analizator.getFloatTimeDomainData(probki);
      let szczyt = 0;
      for (const probka of probki) szczyt = Math.max(szczyt, Math.abs(probka));
      el("poziom").value = szczyt;
      animacja = requestAnimationFrame(mierz);
    }
    mierz();
    el("stan").textContent = gabinet ? "Test aktywny. Mikrofon i kamera są włączone." : "Test aktywny. Mikrofon jest włączony.";
  } catch {
    if (numer === proba) zatrzymaj("Nie udało się uruchomić testu. Sprawdź podłączenie i uprawnienia przeglądarki.");
  }
}

stanowisko.onchange = () => {
  zatrzymaj();
  el("pole-kamery").hidden = stanowisko.value !== "gabinet";
};
mikrofon.onchange = kamera.onchange = () => zatrzymaj("Wybór zmieniony. Uruchom test ponownie.");
el("uruchom").onclick = uruchom;
el("stop").onclick = () => zatrzymaj();
window.addEventListener("pagehide", () => zatrzymaj());
