(async () => {
  const rules = {
    chrome: /^https:\/\/chromewebstore\.google\.com\/detail\/(?:[a-z0-9-]+\/)?[a-p]{32}\/?$/,
    edge: /^https:\/\/microsoftedge\.microsoft\.com\/addons\/detail\/(?:[a-z0-9-]+\/)?[a-p]{32}\/?$/
  };
  try {
    const response = await fetch("stores.json", {cache:"no-cache", credentials:"same-origin"});
    if (!response.ok) return;
    const config = await response.json();
    for (const [browser, rule] of Object.entries(rules)) {
      const url = config[browser];
      if (typeof url !== "string" || !rule.test(url)) continue;
      const link = document.getElementById(browser + "-install");
      link.href = url;
      link.hidden = false;
      document.getElementById(browser + "-status").textContent = "Dostępne — instalacja z oficjalnego sklepu";
    }
  } catch { /* keep unavailable state */ }
})();
