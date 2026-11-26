const ADRES_PROD = "https://app.notarai.pl";
const ADRES_TESTOWY = "http://127.0.0.1:8000";
const DOZWOLONE_ADRESY = new Set([ADRES_PROD, ADRES_TESTOWY]);
const poprawnyAdres = adres => DOZWOLONE_ADRESY.has(adres);
let laczenie;
const panel = () => chrome.sidePanel?.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
if (typeof browser !== "undefined" && browser.sidebarAction) {
  browser.action.onClicked.addListener(() => browser.sidebarAction.open());
}
async function proba(id) {
  const zapis = await chrome.storage.local.get(["token", "blokadaParowania", "adres"]);
  if (zapis.token) return { stan: "polaczono" };
  if (zapis.blokadaParowania) return { stan: "odlaczono" };
  const adres = zapis.adres || ADRES_PROD;
  if (!poprawnyAdres(adres)) return { stan: "blad" };
  const karty = await chrome.tabs.query({ url: adres + "/*" });
  const karta = karty.find(k => k.id === id) || karty.find(k => k.active) || karty[0];
  if (!karta) return { stan: "logowanie" };
  try {
    await chrome.scripting.executeScript({ target: { tabId: karta.id }, files: ["sesja.js"] });
    const wynik = await chrome.tabs.sendMessage(karta.id, { typ: "notarai-autoryzuj" }, { frameId: 0 });
    if (wynik?.stan !== "polaczono" || typeof wynik.token !== "string" || !wynik.token.startsWith("pom_"))
      return { stan: wynik?.stan || "blad" };
    const teraz = await chrome.storage.local.get(["token", "blokadaParowania"]);
    if (teraz.token || teraz.blokadaParowania) {
      await fetch(adres + "/api/pomocnik/odlacz", { method: "POST", redirect: "error",
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
async function zmianaSesji(msg, id, adresZrodla) {
  if (laczenie) await laczenie.catch(() => {});
  const zapis = await chrome.storage.local.get(["token", "tozsamosc", "adres"]);
  const adres = zapis.adres || ADRES_PROD;
  if (!poprawnyAdres(adres) || adresZrodla !== adres) return { stan: "blad" };
  if (zapis.token && (msg.wylogowano || (zapis.tozsamosc && msg.tozsamosc && zapis.tozsamosc !== msg.tozsamosc))) {
    await chrome.storage.local.set({ token: "", tozsamosc: "", blokadaParowania: true });
    await fetch(adres + "/api/pomocnik/odlacz", { method: "POST", redirect: "error",
      headers: { Authorization: "Bearer " + zapis.token, "Content-Type": "application/json" }, body: "{}" }).catch(() => {});
    return { stan: "odlaczono" };
  }
  return polacz(id);
}
chrome.runtime.onMessage.addListener((msg, sender, odpowiedz) => {
  if (sender.id !== chrome.runtime.id) return;
  const adresZrodla = sender.frameId === 0 && sender.url ? new URL(sender.url).origin : "";
  const zAplikacji = poprawnyAdres(adresZrodla);
  const zPanelu = sender.url?.startsWith(chrome.runtime.getURL("panel.html"));
  if ((msg?.typ === "notarai-sesja" && zAplikacji) || (msg?.typ === "notarai-polacz" && zPanelu)) {
    const zadanie = msg.typ === "notarai-sesja" ? zmianaSesji(msg, sender.tab?.id, adresZrodla) : polacz(sender.tab?.id);
    zadanie.then(odpowiedz, () => odpowiedz({ stan: "blad" }));
    return true;
  }
});
chrome.runtime.onInstalled.addListener(() => { panel(); polacz().catch(() => {}); });
chrome.runtime.onStartup.addListener(() => { panel(); polacz().catch(() => {}); });
panel();
