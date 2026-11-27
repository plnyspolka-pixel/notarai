"use strict";

const el = id => document.getElementById(id);
const maxBytes = 20 * 1024 * 1024;
const ALL = "\u0000all";
const NONE = "\u0000none";
let token = "";
let scope = "";
let allowedCases = null;
let opened = null;
let originalText = "";
let proposal = null;
let listed = [];

function status(message) {
  el("status").textContent = message;
}

async function call(path, method = "GET", data) {
  const headers = {};
  if (data !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = "Bearer " + token;
  const response = await fetch("/v2/" + path, {
    method, headers, cache: "no-store", credentials: "omit",
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  if (response.status === 401) {
    throw new Error("Sesja wygasła lub dostęp został cofnięty. Skopiuj niezapisany tekst przed rozłączeniem.");
  }
  if (!response.ok) {
    let detail = "";
    try { detail = (await response.json()).detail || ""; } catch { /* no body */ }
    if (response.status === 409 && detail === "revision conflict") {
      throw new Error("Konflikt wersji. Zachowano edytowany tekst i wybrany plik. Możesz zapisać zmiany jako osobny dokument.");
    }
    // Messages written for the notary are Polish sentences; protocol errors stay generic.
    if (/[ąćęłńóśźż .]/i.test(detail) && detail.length > 20) throw new Error(detail);
    throw new Error("Nie udało się wykonać operacji (HTTP " + response.status + ").");
  }
  return response.json();
}

function run(action) {
  return async () => {
    const controls = [...document.querySelectorAll("button, input, select, textarea")];
    const previous = controls.map(control => control.disabled);
    controls.forEach(control => { control.disabled = true; });
    try {
      await action();
    } catch (error) {
      status(error.message);
    } finally {
      controls.forEach((control, i) => { control.disabled = previous[i]; });
    }
  };
}

function mayDiscard() {
  const dirty = !el("text-editor").hidden && scope === "write" &&
    (el("name").value !== (opened?.name ?? "") || el("body").value !== originalText);
  return !dirty || window.confirm("Porzucić niezapisane zmiany?");
}

function currentCase() {
  const value = el("case").value;
  return value === ALL || value === NONE || value === "" ? null : value;
}

function resetEditor() {
  opened = null;
  originalText = "";
  el("name").value = "";
  el("body").value = "";
  el("replacement").value = "";
  el("versions").replaceChildren();
  el("editor").hidden = true;
}

function decode(content) {
  return Uint8Array.from(atob(content), character => character.charCodeAt(0));
}

function encode(bytes) {
  if (bytes.length > maxBytes) throw new Error("Limit rozmiaru pliku to 20 MiB.");
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += 8192) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 8192));
  }
  return btoa(binary);
}

function showEditor(document, versions, localText) {
  opened = document;
  let text = localText;
  if (document && text === undefined && /\.txt$/i.test(document.name)) {
    try {
      text = new TextDecoder("utf-8", { fatal: true }).decode(decode(document.content_b64));
    } catch {
      // Non-UTF-8 files are available for download with their original bytes.
    }
  }
  originalText = text ?? "";
  el("name").value = document?.name ?? "";
  el("body").value = originalText;
  el("name").readOnly = scope !== "write";
  el("body").readOnly = scope !== "write";
  el("text-editor").hidden = text === undefined;
  const writable = scope === "write" && (!document || document.version === versions[0]);
  el("save").hidden = !writable;
  el("replace-tools").hidden = !writable || !document;
  el("replacement").value = "";
  el("copy").hidden = scope !== "write" || !document;
  el("selected").textContent = document ? document.name + " · wersja " + document.version : "Nowy dokument";
  el("versions").replaceChildren(...versions.map(version =>
    new Option("Wersja " + version, version, false, version === document?.version)
  ));
  el("history").hidden = !document;
  el("editor").hidden = false;
}

async function openDocument(id, version) {
  const [document, versions] = await Promise.all([
    call("documents/" + id + (version ? "?version=" + version : "")),
    call("documents/" + id + "/versions"),
  ]);
  showEditor(document, versions);
  status("Otwarto wersję " + document.version + ".");
}

function notice(text) {
  const box = document.createElement("p");
  box.className = "notice";
  box.textContent = text;
  return box;
}

async function refreshStatus() {
  const state = await call("status");
  allowedCases = state.cases;
  el("mode").textContent = state.mode === "synthetic-only"
    ? "Tryb próbny. Używaj wyłącznie fikcyjnych dokumentów."
    : "Dokumenty są przechowywane na komputerze kancelarii.";
  const notes = [];
  if (!state.recovery.enrolled) {
    notes.push(notice("Sejf nie ma kodu odzyskiwania. Po awarii komputera dokumentów nie da się odtworzyć. Utwórz kod w panelu stanowiska na komputerze kancelarii."));
  } else if (state.recovery.backup_overdue) {
    notes.push(notice("Dawno nie było kopii zapasowej. Zrób ją w panelu stanowiska na komputerze kancelarii."));
  }
  if (!state.ai.enabled) notes.push(notice("Asystent AI jest wyłączony na tym stanowisku."));
  else if (!state.ai.signed_in) notes.push(notice("Asystent AI wymaga zalogowania w panelu stanowiska."));
  el("notices").replaceChildren(...notes);
  el("draft").hidden = scope !== "write";
  el("new-case-tools").hidden = scope !== "write" || allowedCases !== null;
}

async function refreshCases(keep) {
  const cases = await call("cases");
  const selected = keep ?? el("case").value;
  const options = [];
  if (allowedCases === null) {
    options.push(new Option("Wszystkie dokumenty", ALL));
  }
  cases.forEach(name => options.push(new Option(name, name)));
  if (!options.length) options.push(new Option("Brak spraw", NONE));
  el("case").replaceChildren(...options);
  if ([...el("case").options].some(option => option.value === selected)) el("case").value = selected;
}

async function refresh() {
  const selected = currentCase();
  listed = await call("documents?include_names=true" + (selected ? "&case=" + encodeURIComponent(selected) : ""));
  const entries = listed.map(item => {
    const entry = document.createElement("li");
    const button = document.createElement("button");
    button.textContent = item.name + " · wersja " + item.version;
    button.onclick = run(async () => {
      if (mayDiscard()) await openDocument(item.id);
    });
    entry.append(button);
    return entry;
  });
  if (!entries.length) {
    const empty = document.createElement("li");
    empty.textContent = "Brak dokumentów.";
    entries.push(empty);
  }
  el("docs").replaceChildren(...entries);
  el("assistant").hidden = !selected;
  if (!selected) hideProposal();
}

async function save(name, bytes, current, text) {
  const content_b64 = encode(bytes);
  const result = await call("documents", "POST", {
    id: current?.id ?? null,
    expected_version: current?.version ?? 0,
    name,
    content_b64,
    case: current ? null : currentCase(),
  });
  const versions = Array.from({ length: result.version }, (_, index) => result.version - index);
  showEditor({ ...result, name, content_b64 }, versions, text);
  el("file").value = "";
  status("Zapisano wersję " + result.version + ".");
  try {
    await refresh();
  } catch {
    status("Zapisano wersję " + result.version + ". Lista dokumentów wymaga odświeżenia.");
  }
}

async function saveText(current) {
  const name = el("name").value.trim();
  if (!/\.txt$/i.test(name)) throw new Error("Podaj nazwę pliku z rozszerzeniem .txt.");
  const text = el("body").value;
  await save(name, new TextEncoder().encode(text), current, text);
}

// ---------------------------------------------------------------- assistant
function names() {
  return el("names").value.split("\n").map(line => line.trim()).filter(Boolean).slice(0, 50);
}

function question() {
  const text = el("prompt").value.trim();
  if (!text) throw new Error("Wpisz pytanie albo polecenie.");
  if (!currentCase()) throw new Error("Wybierz sprawę.");
  return { text, names: names() };
}

function hideProposal() {
  proposal = null;
  el("proposal").hidden = true;
  el("proposal-text").value = "";
}

function showProposal(result) {
  proposal = result;
  const notes = [];
  notes.push(notice("To propozycja modelu. Przeczytaj całość przed zapisem; odpowiadasz za treść dokumentu."));
  if (result.gaps) notes.push(notice("Miejsca do uzupełnienia: " + result.gaps + ". Szukaj w tekście „[DO UZUPEŁNIENIA”."));
  if (result.unknown_placeholders.length) {
    notes.push(notice("Model użył znaczników, których nie było w dokumentach: " + result.unknown_placeholders.join(", ") + ". Popraw te miejsca."));
  }
  if (result.skipped.length) {
    notes.push(notice("Nie odczytano (tylko TXT i DOCX): " + result.skipped.join(", ") + "."));
  }
  const sources = document.createElement("p");
  sources.className = "muted";
  sources.textContent = "Na podstawie: " + result.sources.map(source => source.name + " (wersja " + source.version + ")").join(", ") + ".";
  notes.push(sources);
  el("proposal-notes").replaceChildren(...notes);
  el("proposal-text").value = result.paragraphs.join("\n");
  const documents = listed.filter(item => /\.docx$/i.test(item.name));
  el("proposal-base").replaceChildren(
    new Option("Nowy dokument", ""),
    ...documents.map(item => new Option("Kolejna wersja: " + item.name, item.id + ":" + item.version)),
  );
  el("proposal-template").replaceChildren(
    new Option("Bez wzoru", ""),
    ...documents.map(item => new Option(item.name, item.id + ":" + item.version)),
  );
  el("proposal").hidden = false;
  el("answer").hidden = true;
}

function target(value) {
  if (!value) return null;
  const [id, version] = value.split(":");
  return { id, version: Number(version) };
}

el("ask").onclick = run(async () => {
  const result = await call("cases/" + encodeURIComponent(currentCase()) + "/ask", "POST", question());
  el("answer").textContent = result.answer;
  el("answer").hidden = false;
  status("Odpowiedź na podstawie " + result.sources.length + " dokumentów sprawy.");
});
el("draft").onclick = run(async () => {
  status("Przygotowuję projekt. To może potrwać do kilku minut.");
  showProposal(await call("cases/" + encodeURIComponent(currentCase()) + "/draft", "POST", question()));
  status("Projekt gotowy do sprawdzenia. Nic nie zostało jeszcze zapisane.");
});
el("approve").onclick = run(async () => {
  const name = el("proposal-name").value.trim();
  if (!/\.docx$/i.test(name)) throw new Error("Podaj nazwę pliku z rozszerzeniem .docx.");
  const base = target(el("proposal-base").value);
  const result = await call("drafts/" + proposal.id + "/approve", "POST", {
    name, paragraphs: el("proposal-text").value.split("\n"),
    base, template: target(el("proposal-template").value),
  });
  hideProposal();
  status("Zapisano " + result.name + " jako wersję " + result.version + " i potwierdzono odczytem kontrolnym.");
  await refresh();
});
el("discard").onclick = run(async () => {
  if (!window.confirm("Odrzucić projekt? Nie da się go przywrócić.")) return;
  await call("drafts/" + proposal.id, "DELETE");
  hideProposal();
  status("Projekt odrzucony. Nic nie zapisano.");
});

// ---------------------------------------------------------------- fees
async function loadFees() {
  const catalog = await call("taksa/katalog");
  el("fee-kind").replaceChildren(...catalog.map(kind => new Option(kind.nazwa, kind.id)));
}

el("fee").onclick = run(async () => {
  const value = Number(el("fee-value").value.replace(/\s/g, "").replace(",", "."));
  if (!(value > 0)) throw new Error("Podaj wartość większą od zera.");
  const result = await call("taksa", "POST", { parameters: { czynnosci: [{ rodzaj: el("fee-kind").value, wartosc: value }] } });
  el("fee-result").textContent = result.tekst || (result.uwagi || []).join("\n");
  el("fee-result").hidden = false;
  status("Taksę policzył program według stawek maksymalnych, nie model.");
});

// ---------------------------------------------------------------- session
async function enter(device) {
  token = device.token;
  scope = device.scope;
  el("pairing").hidden = true;
  el("workspace").hidden = false;
  el("write-tools").hidden = scope !== "write";
  status(scope === "write" ? "Połączono z prawem zapisu." : "Połączono w trybie odczytu.");
  await refreshStatus();
  await refreshCases();
  await refresh();
  await loadFees();
}

el("pair").onclick = run(async () => {
  const code = el("code").value.trim();
  const device = await call("devices/redeem", "POST", { code });
  el("code").value = "";
  await enter(device);
});
el("refresh").onclick = run(async () => {
  await refreshStatus();
  await refreshCases();
  await refresh();
});
el("case").onchange = run(async () => {
  if (!mayDiscard()) return;
  resetEditor();
  hideProposal();
  el("answer").hidden = true;
  await refresh();
});
el("add-case").onclick = run(async () => {
  const name = el("new-case").value.trim();
  if (!/^[\p{L}\p{N}_.-]{1,64}$/u.test(name)) throw new Error("Nazwa sprawy: litery, cyfry, myślnik, kropka; bez spacji.");
  if (![...el("case").options].some(option => option.value === name)) el("case").add(new Option(name, name));
  el("case").value = name;
  el("new-case").value = "";
  await refresh();
  status("Sprawa „" + name + "” pojawi się na stałe po zapisaniu pierwszego dokumentu.");
});
el("logout").onclick = () => {
  if (!mayDiscard()) return;
  token = "";
  scope = "";
  resetEditor();
  hideProposal();
  el("file").value = "";
  el("docs").replaceChildren();
  el("answer").hidden = true;
  el("workspace").hidden = true;
  el("pairing").hidden = false;
  status("Rozłączono.");
};
el("new").onclick = () => {
  if (mayDiscard()) showEditor(null, [], "");
};
el("open-version").onclick = run(async () => {
  if (mayDiscard()) await openDocument(opened.id, el("versions").value);
});
el("download").onclick = () => {
  const url = URL.createObjectURL(new Blob([decode(opened.content_b64)]));
  const link = document.createElement("a");
  link.href = url;
  link.download = opened.name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
el("save").onclick = run(() => saveText(opened));
el("copy").onclick = run(() => saveText(null));
async function saveFile(input, current) {
  const file = el(input).files[0];
  if (!file) throw new Error("Wybierz plik.");
  if (file.size > maxBytes) throw new Error("Limit rozmiaru pliku to 20 MiB.");
  if (mayDiscard()) await save(file.name, new Uint8Array(await file.arrayBuffer()), current);
}

el("import").onclick = run(() => saveFile("file", null));
el("replace").onclick = run(() => saveFile("replacement", opened));

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/v2/pocket-sw.js", { scope: "/v2/" }).catch(() => { /* optional */ });
}
