const ADRES = "https://app.notarai.pl";
let laczenie;
const panel = () => chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
async function proba(id) {
  const zapis = await chrome.storage.local.get(["token", "blokadaParowania", "adres"]);
  if (zapis.token) return { stan: "polaczono" };
  if (zapis.blokadaParowania) return { stan: "odlaczono" };
  if (zapis.adres && zapis.adres !== ADRES) return { stan: "blad" };
  const karty = await chrome.tabs.query({ url: ADRES + "/*" });
  const karta = karty.find(k => k.id === id) || karty.find(k => k.active) || karty[0];
  if (!karta) return { stan: "logowanie" };
  try {
    await chrome.scripting.executeScript({ target: { tabId: karta.id }, files: ["sesja.js"] });
    const wynik = await chrome.tabs.sendMessage(karta.id, { typ: "notarai-autoryzuj" }, { frameId: 0 });
    if (wynik?.stan !== "polaczono" || typeof wynik.token !== "string" || !wynik.token.startsWith("pom_"))
      return { stan: wynik?.stan || "blad" };
    const teraz = await chrome.storage.local.get(["token", "blokadaParowania"]);
    if (teraz.token || teraz.blokadaParowania) {
      await fetch(ADRES + "/api/pomocnik/odlacz", { method: "POST", redirect: "error",
        headers: { Authorization: "Bearer " + wynik.token, "Content-Type": "application/json" }, body: "{}" }).catch(() => {});
      return { stan: teraz.token ? "polaczono" : "odlaczono" };
    }
    await chrome.storage.local.set({ token: wynik.token, adres: ADRES, tozsamosc: wynik.tozsamosc });
    return { stan: "polaczono" };
  } catch { return { stan: "blad" }; }
}
function polacz(id) {
  if (!laczenie) laczenie = proba(id).finally(() => { laczenie = undefined; });
  return laczenie;
}
async function zmianaSesji(msg, id) {
  if (laczenie) await laczenie.catch(() => {});
  const zapis = await chrome.storage.local.get(["token", "tozsamosc"]);
  if (zapis.token && (msg.wylogowano || (zapis.tozsamosc && msg.tozsamosc && zapis.tozsamosc !== msg.tozsamosc))) {
    await chrome.storage.local.set({ token: "", tozsamosc: "", blokadaParowania: true });
    await fetch(ADRES + "/api/pomocnik/odlacz", { method: "POST", redirect: "error",
      headers: { Authorization: "Bearer " + zapis.token, "Content-Type": "application/json" }, body: "{}" }).catch(() => {});
    return { stan: "odlaczono" };
  }
  return polacz(id);
}
chrome.runtime.onMessage.addListener((msg, sender, odpowiedz) => {
  if (sender.id !== chrome.runtime.id) return;
  const zAplikacji = sender.frameId === 0 && sender.url?.startsWith(ADRES + "/");
  const zPanelu = sender.url?.startsWith(chrome.runtime.getURL("panel.html"));
  if ((msg?.typ === "notarai-sesja" && zAplikacji) || (msg?.typ === "notarai-polacz" && zPanelu)) {
    const zadanie = msg.typ === "notarai-sesja" ? zmianaSesji(msg, sender.tab?.id) : polacz(sender.tab?.id);
    zadanie.then(odpowiedz, () => odpowiedz({ stan: "blad" }));
    return true;
  }
});
chrome.runtime.onInstalled.addListener(() => { panel(); polacz().catch(() => {}); });
chrome.runtime.onStartup.addListener(() => { panel(); polacz().catch(() => {}); });
panel();
