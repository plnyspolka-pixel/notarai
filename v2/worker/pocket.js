"use strict";

const el = id => document.getElementById(id);
const maxBytes = 20 * 1024 * 1024;
let token = "";
let scope = "";
let opened = null;
let originalText = "";

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
  if (response.status === 409) {
    throw new Error("Konflikt wersji. Zachowano edytowany tekst i wybrany plik. Możesz zapisać zmiany jako osobny dokument.");
  }
  if (response.status === 401) {
    throw new Error("Sesja wygasła lub dostęp został cofnięty. Skopiuj niezapisany tekst przed rozłączeniem.");
  }
  if (!response.ok) throw new Error("Nie udało się wykonać operacji (HTTP " + response.status + ").");
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

async function refresh() {
  const items = await call("documents?include_names=true");
  const entries = items.map(item => {
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
}

async function save(name, bytes, current, text) {
  const content_b64 = encode(bytes);
  const result = await call("documents", "POST", {
    id: current?.id ?? null,
    expected_version: current?.version ?? 0,
    name,
    content_b64,
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

el("pair").onclick = run(async () => {
  const code = el("code").value.trim();
  const device = await call("devices/redeem", "POST", { code });
  el("code").value = "";
  token = device.token;
  scope = device.scope;
  el("pairing").hidden = true;
  el("workspace").hidden = false;
  el("write-tools").hidden = scope !== "write";
  status(scope === "write" ? "Połączono z prawem zapisu." : "Połączono w trybie odczytu.");
  await refresh();
});
el("refresh").onclick = run(refresh);
el("logout").onclick = () => {
  if (!mayDiscard()) return;
  token = "";
  scope = "";
  resetEditor();
  el("file").value = "";
  el("docs").replaceChildren();
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
