/* Tylko zaufana domena aplikacji; token logowania nigdy nie opuszcza tej karty. */
(() => {
  if (window.top !== window || location.origin !== "https://app.notarai.pl" || globalThis.__notaraiSesja) return;
  globalThis.__notaraiSesja = true;
  const token = () => { try { return localStorage.getItem("notarai_token") || ""; } catch { return ""; } };
  let poprzedni;
  function sygnal() {
    const t = token();
    if (t === poprzedni) return;
    poprzedni = t;
    if (t) chrome.runtime.sendMessage({ typ: "notarai-sesja" }).catch(() => {});
  }
  chrome.runtime.onMessage.addListener((msg, sender, odpowiedz) => {
    if (sender.id !== chrome.runtime.id || msg?.typ !== "notarai-autoryzuj") return;
    const t = token();
    if (!t) { odpowiedz({ stan: "logowanie" }); return; }
    (async () => {
      try {
        const r = await fetch("/api/urzadzenia/rozszerzenie", {
          method: "POST", credentials: "omit", redirect: "error", cache: "no-store",
          headers: { "Authorization": "Bearer " + t, "Content-Type": "application/json" },
          body: JSON.stringify({ nazwa: /Edg\\//.test(navigator.userAgent) ? "Edge - NotarAI" : "Chrome - NotarAI" })
        });
        if (r.status === 401) return { stan: "logowanie" };
        if (r.status === 403 || r.status === 428) return { stan: "brak-uprawnien" };
        if (!r.ok) return { stan: "blad" };
        const d = await r.json();
        if (typeof d.token !== "string" || !d.token.startsWith("pom_")) return { stan: "blad" };
        return { stan: "polaczono", token: d.token };
      } catch { return { stan: "blad" }; }
    })().then(odpowiedz);
    return true;
  });
  sygnal();
  window.addEventListener("storage", sygnal);
  setInterval(sygnal, 2000);
})();
