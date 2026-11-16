/* Klikniecie ikony notarai otwiera panel boczny obok biezacej strony.
   Cala praca dzieje sie w panelu (panel.js) - tu nie ma nic wiecej. */
chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
});
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
