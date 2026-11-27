"use strict";

const el = id => document.getElementById(id);
let token = "";
let settings = null;
let deviceNames = {};
let tunnelState = { enabled: false };

const ACTIONS = {
  read: "odczyt", write: "zapis", backup: "kopia zapasowa", restore: "odtworzenie z kopii",
  migrate: "migracja sejfu", "rotate-key": "wymiana klucza", "enroll-recovery": "utworzenie kodu odzyskiwania",
  "revoke-device": "cofnięcie urządzenia", settings: "zmiana ustawień",
};

function status(message) { el("status").textContent = message; }

async function call(path, method = "GET", data) {
  const headers = { Authorization: "Bearer " + token };
  if (data !== undefined) headers["Content-Type"] = "application/json";
  const response = await fetch("/v2/" + path, {
    method, headers, cache: "no-store", credentials: "omit",
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  let body = null;
  try { body = await response.json(); } catch { /* no body */ }
  if (!response.ok) {
    const error = new Error(response.status === 401 && !body?.challenge && !/[ąćęłńóśźż]/i.test(body?.detail || "")
      ? "Sesja panelu wygasła. Otwórz panel ponownie z menu Start."
      : (/[ąćęłńóśźż .]/i.test(body?.detail || "") && body.detail.length > 20
        ? body.detail : "Nie udało się wykonać operacji (HTTP " + response.status + ")."));
    error.challenge = body?.challenge;
    throw error;
  }
  return body;
}

function run(action) {
  return async () => {
    const controls = [...document.querySelectorAll("button")];
    controls.forEach(control => { control.disabled = true; });
    try { await action(); } catch (error) { status(error.message); }
    finally { controls.forEach(control => { control.disabled = false; }); }
  };
}

function cells(values) {
  const row = document.createElement("tr");
  values.forEach(value => {
    const cell = document.createElement("td");
    if (value instanceof Node) cell.append(value); else cell.textContent = value;
    row.append(cell);
  });
  return row;
}

function when(seconds) {
  return new Date(seconds * 1000).toLocaleString("pl-PL");
}

function notice(text) {
  const box = document.createElement("p");
  box.className = "notice";
  box.textContent = text;
  return box;
}

async function loadStatus() {
  const state = await call("status");
  settings = await call("settings");
  el("mode").textContent = state.mode === "synthetic-only"
    ? "Tryb próbny: wyłącznie fikcyjne dokumenty." : "Dokumenty kancelarii są przechowywane na tym komputerze.";
  const notes = [];
  if (!state.recovery.enrolled) notes.push(notice("Najpierw utwórz kod odzyskiwania. Bez niego awaria komputera oznacza utratę dokumentów."));
  else if (state.recovery.backup_overdue) notes.push(notice("Zrób kopię zapasową: ostatnia jest starsza niż " + settings.backup_reminder_days + " dni albo nie ma żadnej."));
  el("notices").replaceChildren(...notes);
  el("recovery-state").textContent = state.recovery.enrolled ? "Kod odzyskiwania jest utworzony." : "Brak kodu odzyskiwania.";
  el("enroll").hidden = state.recovery.enrolled;
  el("backup").disabled = !state.recovery.enrolled;
  el("backup-dir").value = settings.backup_dir || "";
  el("backup-state").textContent = state.recovery.last_backup
    ? "Ostatnia kopia: " + when(state.recovery.last_backup) + "." : "Nie zrobiono jeszcze żadnej kopii.";
  el("ai-enabled").checked = settings.ai.enabled;
  el("ai-enabled").disabled = !state.ai.account_configured;
  el("ai-state").textContent = !state.ai.account_configured
    ? "To stanowisko nie ma jeszcze danych konta NotarAI. Otrzymasz je przy wdrożeniu."
    : (state.ai.signed_in ? "Zalogowano do AI." : "Nie zalogowano do AI.");
  el("login-form").hidden = !state.ai.account_configured || state.ai.signed_in;
  el("logout-ai").hidden = !state.ai.signed_in;
}

async function loadTunnel() {
  tunnelState = await call("tunnel");
  el("tunnel-enabled").checked = settings.tunnel.enabled;
  el("relay-url").value = settings.tunnel.relay_url;
  el("pocket-url").value = settings.tunnel.pocket_url;
  el("tunnel-state").textContent = !tunnelState.enabled ? "Dostęp spoza kancelarii jest wyłączony."
    : (tunnelState.connected ? "Połączono z przekaźnikiem." : "Brak połączenia z przekaźnikiem (ponawiam).");
}

function drawQr(text) {
  const code = qrcode(0, "M");
  code.addData(text);
  code.make();
  const count = code.getModuleCount(), scale = 5, margin = 4;
  const canvas = el("pair-qr");
  canvas.width = canvas.height = (count + 2 * margin) * scale;
  const context = canvas.getContext("2d");
  context.fillStyle = "#fff";
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.fillStyle = "#000";
  for (let row = 0; row < count; row++) {
    for (let column = 0; column < count; column++) {
      if (code.isDark(row, column)) context.fillRect((column + margin) * scale, (row + margin) * scale, scale, scale);
    }
  }
}

async function loadDevices() {
  const devices = await call("devices");
  deviceNames = Object.fromEntries(devices.map(device => [device.id, device.name]));
  const rows = devices.map(device => {
    const revoke = document.createElement("button");
    revoke.className = "danger";
    revoke.textContent = device.revoked ? "Cofnięto" : "Cofnij dostęp";
    revoke.disabled = device.revoked;
    revoke.onclick = run(async () => {
      if (!window.confirm("Cofnąć dostęp urządzenia „" + device.name + "”?")) return;
      await call("devices/" + device.id, "DELETE");
      status("Dostęp cofnięty. Kopii pobranych wcześniej na to urządzenie nie da się usunąć zdalnie.");
      await loadDevices();
    });
    return cells([device.name, device.scope === "write" ? "odczyt i zapis" : "odczyt",
      device.cases ? device.cases.join(", ") : "wszystkie", revoke]);
  });
  el("devices").replaceChildren(...(rows.length ? rows : [cells(["Brak sparowanych urządzeń.", "", "", ""])]));
}

async function loadUsage() {
  const usage = await call("usage");
  el("usage").replaceChildren(...usage.map(row =>
    cells([row.model, row.purpose, row.calls, row.input_tokens, row.output_tokens])));
}

async function loadAudit() {
  await loadDevices();    // names of devices paired since the panel was opened
  const entries = await call("audit?limit=100");
  el("audit").replaceChildren(...entries.map(entry => cells([
    when(Math.floor(entry.ts / 1e9)),
    deviceNames[entry.actor] || ({ "local-admin": "ten komputer", "connect-verify": "kontrola po zapisie", migration: "migracja" })[entry.actor] || "panel stanowiska",
    ACTIONS[entry.action] || entry.action,
    entry.doc_id ? entry.doc_id.slice(0, 8) + (entry.version ? " · wersja " + entry.version : "") : "",
  ])));
}

async function loadAll() {
  await loadStatus();
  await loadTunnel();
  await loadDevices();
  await loadUsage();
  await loadAudit();
}

async function unlock(code) {
  const response = await fetch("/v2/devices/redeem", {
    method: "POST", headers: { "Content-Type": "application/json" }, cache: "no-store",
    credentials: "omit", body: JSON.stringify({ code }),
  });
  const session = response.ok ? await response.json() : null;
  if (!session || session.scope !== "admin") throw new Error("Kod panelu jest nieważny. Otwórz panel ponownie z menu Start.");
  token = session.token;
  el("locked").hidden = true;
  el("panel").hidden = false;
  await loadAll();
  status("Panel otwarty.");
}

el("unlock").onclick = run(() => unlock(el("code").value.trim()));

el("enroll").onclick = run(async () => {
  const result = await call("recovery/enroll", "POST");
  el("recovery-code").textContent = result.code;
  el("recovery-date").textContent = "Utworzono: " + new Date().toLocaleString("pl-PL");
  el("print-area").hidden = false;
  el("code-actions").hidden = false;
  await loadStatus();
  status("Kod utworzony. Wydrukuj go teraz: nie pokażemy go ponownie.");
});
el("print").onclick = () => window.print();
el("code-saved").onclick = () => {
  if (!window.confirm("Czy kod jest wydrukowany albo przepisany? Po ukryciu nie da się go wyświetlić.")) return;
  el("recovery-code").textContent = "";
  el("print-area").hidden = true;
  el("code-actions").hidden = true;
};
el("save-backup-dir").onclick = run(async () => {
  settings = await call("settings", "PUT", { ...settings, backup_dir: el("backup-dir").value.trim() || null });
  status("Katalog kopii zapisany.");
  await loadStatus();
});
el("backup").onclick = run(async () => {
  const result = await call("backup", "POST");
  status("Kopia zapisana: " + result.file + " (dokumentów: " + result.documents + ", wersji: " + result.revisions + ").");
  await loadStatus();
  await loadAudit();
});
el("invite").onclick = run(async () => {
  const name = el("device-name").value.trim();
  if (!name) throw new Error("Podaj nazwę urządzenia.");
  const cases = el("device-cases").value.split("\n").map(line => line.trim()).filter(Boolean);
  const result = await call("devices/invite", "POST", {
    name, scope: el("device-scope").value, cases: cases.length ? cases : null,
  });
  el("pair-code").textContent = result.code;
  el("pair-code").hidden = false;
  el("remote-pair").hidden = !tunnelState.enabled;
  if (tunnelState.enabled) {
    const link = tunnelState.pocket + "#" + new URLSearchParams({
      r: tunnelState.relay, o: tunnelState.office, k: tunnelState.key, c: result.code }).toString();
    drawQr(link);
    el("pair-qr").dataset.link = link;
  }
  el("device-name").value = "";
  status("Kod parowania jest ważny 5 minut i działa jeden raz.");
});
el("save-ai").onclick = run(async () => {
  settings = await call("settings", "PUT", { ...settings, ai: { ...settings.ai, enabled: el("ai-enabled").checked } });
  status(settings.ai.enabled ? "Asystent włączony." : "Asystent wyłączony.");
  await loadStatus();
});
el("save-tunnel").onclick = run(async () => {
  settings = await call("settings", "PUT", { ...settings, tunnel: {
    enabled: el("tunnel-enabled").checked, relay_url: el("relay-url").value.trim(), pocket_url: el("pocket-url").value.trim() } });
  await new Promise(resolve => setTimeout(resolve, 1200));
  await loadTunnel();
  status(settings.tunnel.enabled ? "Dostęp spoza kancelarii włączony." : "Dostęp spoza kancelarii wyłączony.");
});
el("login").onclick = run(async () => {
  try {
    await call("account/login", "POST", {
      email: el("email").value.trim(), password: el("password").value,
      mfa_code: el("mfa").value.trim() || null, new_password: el("new-password").value || null,
    });
  } catch (error) {
    if (error.challenge === "mfa") el("mfa-row").hidden = false;
    if (error.challenge === "new_password") el("new-password-row").hidden = false;
    throw error;
  }
  ["password", "mfa", "new-password"].forEach(id => { el(id).value = ""; });
  status("Zalogowano do AI.");
  await loadStatus();
});
el("logout-ai").onclick = run(async () => {
  await call("account/logout", "POST");
  status("Wylogowano z AI.");
  await loadStatus();
});
el("reload-audit").onclick = run(loadAudit);

// The launcher opens this page with a one-time code in the fragment, which never reaches a server log.
const fragment = window.location.hash.slice(1);
if (fragment) {
  history.replaceState(null, "", window.location.pathname);
  run(() => unlock(fragment))();
}
