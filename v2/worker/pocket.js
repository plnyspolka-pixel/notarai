"use strict";
// One chat window for Pocket (a paired device) and for the workstation panel (data-mode="admin").
// The page sends sentences to /v2/chat and renders the blocks it gets back.

const el = id => document.getElementById(id);
const admin = document.body.dataset.mode === "admin";
// Closing the station's window stops any work the agent is doing on the computer (owner's decision 27.11.2026).
if (admin) {
  addEventListener("pagehide", () => {
    try {
      if (typeof token === "string" && token) {
        fetch("/v2/agent/stop", { method: "POST", keepalive: true, headers: { Authorization: "Bearer " + token } });
      }
    } catch { /* the server also notices that nobody asks for the job any more */ }
  });
}
const maxBytes = 20 * 1024 * 1024;
const ALL = "\u0000all";
let token = "";
let scope = "";
let tunnel = null;           // set when this device reaches the office through the relay
let opened = null;
let originalText = "";
let names = [];
let busy = false;

function status(message) {
  el("status").textContent = message;
}

async function call(path, method = "GET", data) {
  let code, body = null;
  if (tunnel) {
    try {
      ({ status: code, body } = await tunnel.request(method, "/v2/" + path, data));
    } catch (error) {
      // The office restarted or renewed its relay connection: sign in again with the device key, once.
      if (!error.bye) throw error;
      const resumed = await NotaraiTunnel.resume();
      if (!resumed) throw error;
      const onclose = tunnel.onclose;
      tunnel.onclose = () => {};
      tunnel.close();
      tunnel = resumed.tunnel;
      tunnel.onclose = onclose;
      ({ status: code, body } = await tunnel.request(method, "/v2/" + path, data));
    }
  } else {
    const headers = {};
    if (data !== undefined) headers["Content-Type"] = "application/json";
    if (token) headers.Authorization = "Bearer " + token;
    const response = await fetch("/v2/" + path, {
      method, headers, cache: "no-store", credentials: "omit",
      body: data === undefined ? undefined : JSON.stringify(data),
    });
    code = response.status;
    try { body = await response.json(); } catch { /* no body */ }
  }
  if (code < 200 || code >= 300) {
    const detail = (body && body.detail) || "";
    const error = new Error(
      code === 401 && !(body && body.challenge) && !/[ąćęłńóśźż]/i.test(detail)
        ? (admin ? "Sesja wygasła. Otwórz NotarAI ponownie ikoną na pulpicie albo z menu Start."
                 : "Sesja wygasła lub dostęp został cofnięty. Skopiuj niezapisany tekst przed rozłączeniem.")
        : code === 409 && detail === "revision conflict"
          ? "Konflikt wersji. Zachowano edytowany tekst i wybrany plik. Możesz zapisać zmiany jako osobny dokument."
          // Messages written for the notary are Polish sentences; protocol errors stay generic.
          : (/[ąćęłńóśźż .]/i.test(detail) && detail.length > 20 ? detail : "Nie udało się wykonać operacji (HTTP " + code + ")."));
    error.challenge = body && body.challenge;
    error.code = code;
    throw error;
  }
  return body;
}

function run(action) {
  return async (...args) => {
    if (busy) return;
    busy = true;
    const controls = [...document.querySelectorAll("button, input, select, textarea")];
    const previous = controls.map(control => control.disabled);
    controls.forEach(control => { control.disabled = true; });
    try {
      await action(...args);
    } catch (error) {
      status(error.message);
    } finally {
      // New controls created meanwhile start enabled; old ones return to what they were.
      controls.forEach((control, i) => { control.disabled = previous[i]; });
      busy = false;
    }
  };
}

function currentCase() {
  const value = el("case").value;
  return value === ALL || value === "" ? null : value;
}

// ---------------------------------------------------------------- conversation
function node(tag, className, textContent) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (textContent !== undefined) element.textContent = textContent;
  return element;
}

function show(element) {
  el("messages").append(element);
  element.scrollIntoView({ block: "end" });
  return element;
}

function bubble(text, who) {
  return show(node("div", "bubble " + who, text));
}

function sayButton(label, sentence) {
  const button = node("button", "", label);
  button.onclick = run(() => send(sentence, label));
  return button;
}

function field(labelText, input) {
  const label = node("label", "", labelText);
  label.append(input);
  return label;
}

function target(value) {
  if (!value) return null;
  const [id, version] = value.split(":");
  return { id, version: Number(version) };
}

// ---------------------------------------------------------------- tiles
let layout = { show: false, tiles: [] };
let arranging = false;

async function storeLayout() {
  layout = await call("layout", "POST", layout);
  drawTiles();
}

function moveTile(from, to) {
  if (to < 0 || to >= layout.tiles.length || from === to) return;
  layout.tiles.splice(to, 0, layout.tiles.splice(from, 1)[0]);
}

function drawTiles() {
  el("desk").hidden = !layout.show || !layout.tiles.length;
  el("tiles").classList.toggle("arranging", arranging);
  el("arrange").textContent = arranging ? "Gotowe" : "Ustaw";
  el("tiles").replaceChildren(...layout.tiles.map((tile, index) => {
    const box = node("div", "tile");
    const go = node("button", "go", tile.label);
    go.onclick = run(async () => { if (!arranging) await send(tile.say, tile.label); });
    box.append(go);
    // Arranging: drag with a mouse, or use the arrows (touch screens, keyboards).
    box.draggable = arranging;
    box.ondragstart = event => { event.dataTransfer.setData("text/plain", String(index)); box.classList.add("dragging"); };
    box.ondragend = () => box.classList.remove("dragging");
    box.ondragover = event => { if (arranging) event.preventDefault(); };
    box.ondrop = run(async event => {
      event.preventDefault();
      moveTile(Number(event.dataTransfer.getData("text/plain")), index);
      await storeLayout();
    });
    const edit = node("div", "edit");
    const step = (label, title, action) => {
      const button = node("button", "", label);
      button.title = title;
      button.setAttribute("aria-label", title + ": " + tile.label);
      button.onclick = run(async () => { action(); await storeLayout(); });
      return button;
    };
    edit.append(
      step("←", "Przesuń wcześniej", () => moveTile(index, index - 1)),
      step("→", "Przesuń dalej", () => moveTile(index, index + 1)),
      step("✕", "Usuń kafelek", () => { layout.tiles.splice(index, 1); }),
    );
    box.append(edit);
    return box;
  }));
}

// ---------------------------------------------------------------- the office's hard rules
async function refreshRules() {
  const known = await call("rules");
  el("rules-toggle").textContent = "Zasady kancelarii · " + (known.length || "brak");
  el("rules-list").replaceChildren(...known.map(rule => {
    const item = node("li", "", rule.text);
    if (admin) {
      const remove = node("button", "quiet", "✕");
      remove.setAttribute("aria-label", "Usuń zasadę " + rule.number);
      remove.onclick = run(() => send("usuń zasadę " + rule.number));
      item.append(" ", remove);
    }
    return item;
  }));
  el("rules-hint").textContent = admin
    ? "Nową zasadę dodasz zdaniem, np. „zasada: każdy akt musi zawierać „Notariusz pouczył strony…””."
    : (known.length ? "" : "Kancelaria nie ma jeszcze zasad. Ustawia się je w panelu stanowiska.");
}

el("rules-toggle").onclick = () => {
  const open = el("rules-box").hidden;
  el("rules-box").hidden = !open;
  el("rules-toggle").setAttribute("aria-expanded", String(open));
};

const render = {
  rules: () => refreshRules(),

  layout: block => { layout = block.layout; arranging = false; drawTiles(); },


  text: block => bubble(block.text, "them"),

  buttons: block => {
    const group = node("div", "group");
    block.items.forEach(item => group.append(sayButton(item.label, item.say)));
    show(group);
  },

  documents: block => {
    const group = node("div", "group docs");
    block.items.forEach(item => {
      const button = node("button", "", item.name + " · wersja " + item.version);
      button.onclick = run(() => openDocument(item.id));
      group.append(button);
    });
    show(group);
  },

  case: block => {
    if (![...el("case").options].some(option => option.value === block.case)) el("case").add(new Option(block.case, block.case));
    el("case").value = block.case;
  },

  names: block => { names = block.names; },

  open: block => openDocument(block.id),

  confirm: block => {
    const card = node("div", "card them");
    card.append(node("p", "", block.text));
    const yes = node("button", "danger", block.label);
    const no = node("button", "", "Nie");
    yes.onclick = run(async () => {
      card.remove();
      bubble(block.label, "me");
      await exchange({ confirm: block.token });
    });
    no.onclick = () => { card.remove(); bubble("Nie", "me"); bubble("Dobrze, nic nie zmieniam.", "them"); };
    const row = node("div", "row");
    row.append(yes, no);
    card.append(row);
    show(card);
  },

  secret: block => {
    const card = node("div", "card them");
    card.append(node("p", "", block.title), node("p", "code", block.text), node("p", "muted", block.hint || ""));
    const row = node("div", "row");
    if (block.print) {
      const print = node("button", "", "Drukuj");
      // A sheet of its own straight under <body>: printing never depends on the window's layout.
      print.onclick = () => {
        const sheet = node("section", "");
        sheet.id = "print-sheet";
        sheet.append(node("h1", "", "NotarAI – " + block.title), node("p", "print-code", block.text),
          node("p", "", block.hint || ""),
          node("p", "", "Wydrukowano: " + new Date().toLocaleString("pl-PL") + ". Przechowuj w sejfie kancelarii."));
        document.body.append(sheet);
        document.body.classList.add("print-sheet");
        const done = () => { sheet.remove(); document.body.classList.remove("print-sheet"); };
        window.addEventListener("afterprint", done, { once: true });
        window.print();
        setTimeout(() => { if (sheet.isConnected && !matchMedia("print").matches) done(); }, 60000);
      };
      row.append(print);
    }
    const hide = node("button", "", block.print ? "Kod jest bezpiecznie zapisany – ukryj" : "Ukryj kod");
    hide.onclick = () => {
      if (block.print && !window.confirm("Czy kod jest wydrukowany albo przepisany? Po ukryciu nie da się go wyświetlić.")) return;
      card.remove();
      bubble("Kod ukryty.", "them");
    };
    row.append(hide);
    card.append(row);
    show(card);
  },

  qr: block => {
    const card = node("div", "card them");
    const canvas = node("canvas");
    canvas.setAttribute("aria-label", "Kod QR do sparowania telefonu");
    canvas.dataset.link = block.link;
    const code = qrcode(0, "M");
    code.addData(block.link);
    code.make();
    const count = code.getModuleCount(), scale = 5, margin = 4;
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
    card.append(canvas);
    show(card);
  },

  login: () => {
    const card = node("div", "card them");
    const input = (type, autocomplete) => {
      const element = node("input");
      element.type = type;
      element.autocomplete = autocomplete;
      return element;
    };
    const email = input("email", "username"), password = input("password", "current-password");
    const mfa = input("text", "one-time-code"), fresh = input("password", "new-password");
    const mfaRow = field("Kod z aplikacji uwierzytelniającej", mfa);
    const freshRow = field("Nowe hasło (pierwsze logowanie)", fresh);
    mfaRow.hidden = freshRow.hidden = true;
    const submit = node("button", "primary", "Zaloguj");
    submit.onclick = run(async () => {
      try {
        await call("account/login", "POST", {
          email: email.value.trim(), password: password.value,
          mfa_code: mfa.value.trim() || null, new_password: fresh.value || null,
        });
      } catch (error) {
        if (error.challenge === "mfa") mfaRow.hidden = false;
        if (error.challenge === "new_password") freshRow.hidden = false;
        throw error;
      }
      card.remove();
      bubble("Zalogowano do AI.", "them");
    });
    card.append(field("Adres e-mail konta NotarAI", email), field("Hasło", password), mfaRow, freshRow, submit);
    show(card);
  },

  proposal: block => {
    const card = node("div", "card them");
    card.append(node("p", "notice", "To propozycja modelu. Przeczytaj całość przed zapisem; odpowiadasz za treść dokumentu."));
    if (block.gaps) card.append(node("p", "notice", "Miejsca do uzupełnienia: " + block.gaps + ". Szukaj w tekście „[DO UZUPEŁNIENIA”."));
    if (block.unknown_placeholders.length) {
      card.append(node("p", "notice", "Model użył znaczników, których nie było w dokumentach: " + block.unknown_placeholders.join(", ") + ". Popraw te miejsca."));
    }
    if (block.skipped.length) card.append(node("p", "notice", "Nie odczytano (tylko TXT i DOCX): " + block.skipped.join(", ") + "."));
    card.append(node("p", "muted", "Na podstawie: " + block.sources.map(source => source.name + " (wersja " + source.version + ")").join(", ") + "."));
    const body = node("textarea", "tall");
    body.value = block.paragraphs.join("\n");
    const name = node("input");
    name.maxLength = 255;
    name.value = "projekt.docx";
    const base = node("select"), template = node("select");
    base.append(new Option("Nowy dokument", ""), ...block.docx.map(item => new Option("Kolejna wersja: " + item.name, item.id + ":" + item.version)));
    template.append(new Option("Bez wzoru", ""), ...block.docx.map(item => new Option(item.name, item.id + ":" + item.version)));
    card.append(field("Treść projektu (możesz poprawić przed zapisem)", body), field("Nazwa pliku", name));
    if (block.docx.length) card.append(field("Zapisz jako", base), field("Wzór kancelarii (układ strony i nagłówek)", template));
    const approve = node("button", "primary", "Zatwierdzam i zapisuję");
    const discard = node("button", "danger", "Odrzuć projekt");
    approve.onclick = run(async () => {
      const file = name.value.trim();
      if (!/\.docx$/i.test(file)) throw new Error("Podaj nazwę pliku z rozszerzeniem .docx.");
      const result = await call("drafts/" + block.id + "/approve", "POST", {
        name: file, paragraphs: body.value.split("\n"), base: target(base.value), template: target(template.value),
      });
      card.remove();
      bubble("Zatwierdzam i zapisuję", "me");
      bubble("Zapisałem " + result.name + " jako wersję " + result.version + " i potwierdziłem odczytem kontrolnym.", "them");
      render.documents({ items: [{ id: result.id, name: result.name, version: result.version }] });
      showLearned(result.learned);
      status("Zapisano " + result.name + " jako wersję " + result.version + " i potwierdzono odczytem kontrolnym.");
    });
    discard.onclick = run(async () => {
      if (!window.confirm("Odrzucić projekt? Nie da się go przywrócić.")) return;
      await call("drafts/" + block.id, "DELETE");
      card.remove();
      bubble("Odrzuć projekt", "me");
      bubble("Projekt odrzucony. Nic nie zapisałem.", "them");
    });
    const row = node("div", "row");
    row.append(approve, discard);
    card.append(row);
    show(card);
  },
};

// ---------------------------------------------------------------- teaching by showing
const FRAME_EVERY_MS = 2000, MAX_FRAMES = 12, MAX_RECORDING_MS = 5 * 60 * 1000;

function signature(context, width, height) {
  // A tiny grey thumbnail: enough to tell whether the screen changed since the last kept frame.
  const small = document.createElement("canvas");
  small.width = 32; small.height = 18;
  const pen = small.getContext("2d");
  pen.drawImage(context.canvas, 0, 0, width, height, 0, 0, 32, 18);
  const pixels = pen.getImageData(0, 0, 32, 18).data;
  const grey = new Uint8Array(32 * 18);
  for (let i = 0; i < grey.length; i++) grey[i] = (pixels[4 * i] + pixels[4 * i + 1] + pixels[4 * i + 2]) / 3;
  return grey;
}

function changed(a, b) {
  if (!a) return true;
  let total = 0;
  for (let i = 0; i < a.length; i++) total += Math.abs(a[i] - b[i]);
  return total / a.length > 2;
}

// The month on the left: days with appointments marked; a click shows that day underneath.
const MONTHS = ["styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec", "lipiec", "sierpień", "wrzesień",
                "październik", "listopad", "grudzień"];
const cal = { month: null, day: null };

function isoDay(date) {
  return date.getFullYear() + "-" + String(date.getMonth() + 1).padStart(2, "0") + "-" + String(date.getDate()).padStart(2, "0");
}

function agendaItem(entry, withDay) {
  const item = node("li", entry.source === "rozmowa" ? "check" : "");
  const hour = entry.all_day ? "cały dzień" : entry.start.slice(11, 16).replace(/^0/, "");
  const when = withDay ? entry.label : hour;
  item.append(node("span", "when", when), node("span", "what", entry.title + (entry.case ? " · " + entry.case : "")));
  item.title = entry.source === "rozmowa" ? "Termin z rozmowy: sprawdź go" : "";
  return item;
}

async function refreshAgenda() {
  if (!cal.month) { const now = new Date(); cal.month = new Date(now.getFullYear(), now.getMonth(), 1); }
  const first = cal.month;
  const gridStart = new Date(first);
  gridStart.setDate(1 - ((first.getDay() + 6) % 7));            // weeks start on Monday
  let month = [], soon = [];
  try {
    [month, soon] = await Promise.all([
      call("calendar?days=42&start=" + isoDay(gridStart)).then(r => r.items),
      call("calendar?days=14").then(r => r.items),
    ]);
  } catch { return; }
  const byDay = {};
  for (const entry of month) (byDay[entry.start.slice(0, 10)] ||= []).push(entry);
  el("month-title").textContent = MONTHS[first.getMonth()] + " " + first.getFullYear();
  const today = isoDay(new Date());
  const cells = ["pn", "wt", "śr", "cz", "pt", "so", "nd"].map(name => node("span", "dow", name));
  for (let i = 0; i < 42; i++) {
    const date = new Date(gridStart);
    date.setDate(gridStart.getDate() + i);
    const key = isoDay(date);
    const cell = node("button", "day", String(date.getDate()));
    if (date.getMonth() !== first.getMonth()) cell.classList.add("other");
    if (key === today) cell.classList.add("today");
    if (key === cal.day) cell.classList.add("chosen");
    if (byDay[key]) {
      cell.classList.add("busy");
      cell.setAttribute("aria-label", date.getDate() + " " + MONTHS[date.getMonth()] + ": terminów " + byDay[key].length);
    }
    cell.onclick = () => { cal.day = cal.day === key ? null : key; refreshAgenda(); };
    cells.push(cell);
  }
  el("month").replaceChildren(...cells);
  const list = el("agenda");
  if (cal.day) {
    const [y, m, d] = cal.day.split("-").map(Number);
    el("agenda-title").textContent = d + " " + ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca",
      "sierpnia", "września", "października", "listopada", "grudnia"][m - 1] + (y !== new Date().getFullYear() ? " " + y : "");
    const items = byDay[cal.day] || [];
    list.replaceChildren(...(items.length ? items.map(e => agendaItem(e, false)) : [node("li", "muted", "Brak terminów tego dnia.")]));
  } else {
    el("agenda-title").textContent = "Dziś i najbliższe";
    list.replaceChildren(...(soon.length ? soon.slice(0, 12).map(e => agendaItem(e, true))
      : [node("li", "muted", "Brak terminów w najbliższych dwóch tygodniach.")]));
  }
}
el("month-prev").onclick = () => { cal.month = new Date(cal.month.getFullYear(), cal.month.getMonth() - 1, 1); refreshAgenda(); };
el("month-next").onclick = () => { cal.month = new Date(cal.month.getFullYear(), cal.month.getMonth() + 1, 1); refreshAgenda(); };
render.calendar = () => refreshAgenda();

// What to do now, worked out from what the program sees; refreshed after every exchange.
async function refreshAhead() {
  let items = [];
  try {
    const query = currentCase() ? "?case=" + encodeURIComponent(currentCase()) : "";
    items = (await call("suggestions" + query)).items;
  } catch { return; }
  el("ahead-box").hidden = !items.length;
  el("ahead").replaceChildren(...items.map(item => {
    const row = node("li");
    const go = sayButton(item.label, item.say);
    go.title = item.why;
    row.append(go, node("span", "muted why", item.why));
    return row;
  }));
}
setInterval(() => { if (scope && scope !== "listen" && !document.hidden) refreshAgenda(); }, 5 * 60 * 1000);

render["pick-folder"] = block => {
  // The Windows "choose a folder" dialog opens on the office computer; the path then goes back as a sentence.
  const button = node("button", "primary", block.label || "Wybierz folder…");
  button.onclick = run(async () => {
    status("Wybierz folder w oknie Windows…");
    const chosen = await call("pick-folder", "POST", {});
    if (!chosen.path) { status("Nie wybrano folderu."); return; }
    await send((block.purpose === "kopie" ? "katalog kopii " : "folder aktów ") + chosen.path);
  });
  show(node("div", "group")).append(button);
};

// ---------------------------------------------------------------- first run on a phone or tablet
let installPrompt = null;
window.addEventListener("beforeinstallprompt", event => { event.preventDefault(); installPrompt = event; });

function installedAsApp() {
  return window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
}

function welcome() {
  let seen = false;
  try { seen = localStorage.getItem("notarai-welcome") === "1"; } catch { /* storage blocked */ }
  if (seen || admin || scope === "listen") return;
  const card = node("div", "card them welcome");
  const ios = /iPhone|iPad|iPod/.test(navigator.userAgent);
  const steps = [
    ["Na ekran główny", installedAsApp() ? "Pocket jest już zainstalowany jako aplikacja." : ios
      ? "W Safari stuknij „Udostępnij” (kwadrat ze strzałką), potem „Do ekranu początkowego”. Pocket otworzy się jak aplikacja, bez paska adresu."
      : "Dodaj Pocket do ekranu głównego: przycisk poniżej albo menu przeglądarki → „Zainstaluj aplikację”. Otworzy się jak aplikacja."],
    ["Połączenie zostaje", "Ten telefon jest już sparowany z kancelarią. Nie musisz nic wpisywać ponownie, także po wyłączeniu."],
    ["Mów zamiast pisać", "🎤 nagrywa notatkę głosową: tekst trafia do wybranej sprawy razem z nagraniem."],
    ["Zdjęcia i pliki", "📎 dodaje zdjęcia dokumentów i pliki do sprawy; możesz od razu poprosić o streszczenie."],
    ["Kalendarz", "Napisz „co mam jutro” albo „termin w piątek 10:00 akt Kowalski”."],
  ];
  card.append(node("h2", "", "Witaj w NotarAI Pocket"));
  const list = node("ol", "welcome-steps");
  for (const [title, body] of steps) {
    const item = node("li");
    item.append(node("strong", "", title), node("p", "", body));
    list.append(item);
  }
  card.append(list);
  const row = node("div", "row");
  if (!installedAsApp() && !ios) {
    const install = node("button", "", "Dodaj do ekranu głównego");
    install.onclick = async () => {
      if (installPrompt) {
        installPrompt.prompt();
        await installPrompt.userChoice.catch(() => null);
        installPrompt = null;
      } else {
        status("Otwórz menu przeglądarki (⋮) i wybierz „Zainstaluj aplikację” albo „Dodaj do ekranu głównego”.");
      }
    };
    row.append(install);
  }
  const tour = node("button", "", "Co potrafi NotarAI");
  tour.onclick = run(async () => {
    try { localStorage.setItem("notarai-welcome", "1"); } catch { /* storage blocked */ }
    card.remove();
    await send("pokaż możliwości");
  });
  row.append(tour);
  const done = node("button", "primary", "Zaczynam");
  done.onclick = () => {
    try { localStorage.setItem("notarai-welcome", "1"); } catch { /* storage blocked */ }
    card.remove();
  };
  row.append(done);
  card.append(row);
  el("messages").prepend(card);
}

// ---------------------------------------------------------------- the tour of abilities
const ICONS = {
  calendar: '<rect x="10" y="14" width="44" height="40" rx="6"/><path d="M10 26h44M22 8v12M42 8v12"/><circle cx="24" cy="38" r="3"/><circle cx="40" cy="38" r="3"/>',
  mic: '<rect x="24" y="8" width="16" height="30" rx="8"/><path d="M16 30a16 16 0 0 0 32 0M32 46v10M24 56h16"/>',
  deed: '<path d="M16 8h24l10 10v38H16z"/><path d="M40 8v10h10M22 28h22M22 36h22M22 44h14"/><path d="M38 50l4 4 8-10"/>',
  files: '<path d="M12 18h18l4 6h18v28H12z"/><path d="M22 36h20M32 26v20"/>',
  book: '<path d="M12 12h18a4 4 0 0 1 4 4v38a4 4 0 0 0-4-4H12zM52 12H34v42a4 4 0 0 1 4-4h14z"/><path d="M18 22h10M18 30h10M40 22h8"/>',
  scale: '<path d="M32 10v44M18 54h28M14 18h36"/><path d="M14 18l-8 16a8 8 0 0 0 16 0zM50 18l-8 16a8 8 0 0 0 16 0z"/>',
  form: '<rect x="12" y="8" width="40" height="48" rx="4"/><path d="M20 20h24M20 30h24M20 40h12"/><path d="M38 44l4 4 8-10"/>',
  plug: '<path d="M24 8v14M40 8v14M18 22h28v8a14 14 0 0 1-28 0zM32 44v12"/>',
  mail: '<rect x="8" y="14" width="48" height="36" rx="5"/><path d="M8 18l24 18 24-18"/>',
  coins: '<ellipse cx="26" cy="20" rx="14" ry="6"/><path d="M12 20v10c0 3 6 6 14 6s14-3 14-6V20"/><path d="M24 40v6c0 3 6 6 14 6s14-3 14-6V34c0-3-6-6-14-6"/>',
  phone: '<rect x="20" y="6" width="24" height="52" rx="5"/><path d="M28 50h8"/>',
  ear: '<path d="M22 26a12 12 0 1 1 24 0c0 8-8 10-8 18a8 8 0 0 1-14 4"/><path d="M28 26a6 6 0 0 1 12 0"/>',
  rules: '<path d="M14 10h36v44H14z"/><path d="M22 22h4M30 22h12M22 32h4M30 32h12M22 42h4M30 42h12"/>',
  learn: '<path d="M8 20l24-10 24 10-24 10z"/><path d="M18 25v12c0 4 6 8 14 8s14-4 14-8V25M56 20v14"/>',
  shield: '<path d="M32 6l22 8v16c0 14-10 24-22 28C20 54 10 44 10 30V14z"/><path d="M22 32l7 7 13-14"/>',
};

render.tour = block => {
  const card = node("div", "card them tour");
  card.setAttribute("aria-roledescription", "pokaz");
  let at = 0;
  const art = node("div", "tour-art");
  const body = node("div", "tour-body");
  const count = node("span", "muted tour-count");
  const prev = node("button", "quiet", "‹ Wstecz");
  const next = node("button", "primary", "Dalej ›");
  const dots = node("div", "tour-dots");
  const draw = () => {
    const slide = block.slides[at];
    art.innerHTML = '<svg viewBox="0 0 64 64" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="3" ' +
      'stroke-linecap="round" stroke-linejoin="round">' + (ICONS[slide.icon] || "") + "</svg>";
    const sample = node("div", "tour-sample");
    sample.append(node("div", "bubble me", slide.you), node("div", "bubble them", slide.notarai));
    const parts = [node("h2", "", slide.title), node("p", "", slide.text), sample];
    if (slide.try) {
      const tryIt = node("button", "", "Spróbuj: „" + slide.try + "”");
      tryIt.onclick = run(() => send(slide.try));
      parts.push(tryIt);
    } else if (slide.icon === "mic") {
      const tryIt = node("button", "", "Spróbuj: dotknij 🎤 obok pola wiadomości");
      tryIt.onclick = () => el("voice").focus();
      parts.push(tryIt);
    }
    body.replaceChildren(...parts);
    count.textContent = (at + 1) + " / " + block.slides.length;
    prev.disabled = at === 0;
    next.textContent = at === block.slides.length - 1 ? "Gotowe" : "Dalej ›";
    dots.replaceChildren(...block.slides.map((_, i) => {
      const dot = node("button", i === at ? "dot on" : "dot");
      dot.setAttribute("aria-label", "Pokaz, krok " + (i + 1));
      dot.onclick = () => { at = i; draw(); };
      return dot;
    }));
  };
  prev.onclick = () => { if (at > 0) { at--; draw(); } };
  next.onclick = run(async () => {
    if (at < block.slides.length - 1) { at++; draw(); return; }
    card.classList.add("finished");
    await send(block.done, "Obejrzałem pokaz");
  });
  card.addEventListener("keydown", event => {
    if (event.key === "ArrowRight") next.click();
    if (event.key === "ArrowLeft") prev.click();
  });
  const nav = node("div", "row tour-nav");
  nav.append(prev, count, next);
  const main = node("div", "tour-main");
  main.append(art, body);
  card.append(main, dots, nav);
  show(card);
  draw();
};

// ---------------------------------------------------------------- mail in the window
render.inbox = block => {
  const card = node("div", "card them inbox");
  card.append(node("h2", "", "Poczta"));
  const list = node("ul", "inbox-list");
  for (const item of block.items) {
    const row = node("li");
    const open = node("button", "mail-row");
    open.append(node("span", "mail-from", item.sender), node("span", "mail-when", item.when),
                node("span", "mail-subject", item.subject + (item.attachments ? "  📎 " + item.attachments : "")));
    open.onclick = run(() => send("mail " + item.n, "Wiadomość " + item.n));
    row.append(open);
    list.append(row);
  }
  card.append(list);
  show(card);
};

render.reply = block => {
  const card = node("div", "card them reply");
  card.append(node("h2", "", "Odpowiedź"));
  const to = node("input");
  to.value = block.to;
  const subject = node("input");
  subject.value = block.subject;
  const body = node("textarea", "tall");
  body.value = block.body;
  body.placeholder = "Napisz albo podyktuj treść odpowiedzi…";
  const dictate = node("button", "", "🎤 Dyktuj treść");
  dictate.onclick = run(() => startDictation(body));
  const open = node("button", "primary", "Otwórz w " + (block.program === "Outlook" ? "Outlooku" : block.program === "Thunderbird" ? "Thunderbirdzie" : "programie pocztowym"));
  open.onclick = run(async () => {
    if (!body.value.trim()) throw new Error("Odpowiedź jest pusta.");
    const answer = await call("mail/compose", "POST", { n: block.n, to: to.value, subject: subject.value, body: body.value,
                                                       draft: block.body });
    bubble(answer.detail, "them");
    showLearned(answer.learned);
    status(answer.detail);
  });
  const sendNow = node("button", "primary", block.program === "Outlook" ? "Wyślij" : "Otwórz do wysłania");
  sendNow.onclick = run(async () => {
    if (!body.value.trim()) throw new Error("Odpowiedź jest pusta.");
    const answer = await call("mail/compose", "POST", { n: block.n, to: to.value, subject: subject.value, body: body.value,
                                                       draft: block.body, send: true });
    bubble(answer.detail, "them");
    if (answer.sent) card.remove();
    showLearned(answer.learned);
  });
  open.className = "";
  const row = node("div", "row");
  row.append(dictate, open, sendNow);
  card.append(field("Do", to), field("Temat", subject), field("Treść (" + (block.body ? "projekt przygotował asystent, popraw go" : "pusta") + ")", body), row,
              node("p", "muted", "„Wyślij” wysyła od razu z Twojego programu pocztowego; możesz też napisać albo powiedzieć „wyślij”."));
  show(card);
  if (!admin) { open.disabled = sendNow.disabled = true; open.title = sendNow.title = "Pocztę obsługuje komputer kancelarii."; }
};

render.job = block => {
  // A longer task on the office computer (a land register, a KRZ search): its result arrives here by itself.
  // While it runs, every step the program takes is listed here as it happens (the same lines as /activity).
  const waiting = node("div", "bubble them wait working");
  const head = node("div", "", "Pracuję nad tym…");
  const log = node("ol", "steps live");
  waiting.append(head, log);
  show(waiting);
  const said = [];
  const drain = async () => {
    try {
      const { lines } = await call("activity?after=" + activitySeen);
      for (const line of lines) {
        activitySeen = Math.max(activitySeen, line.n);
        said.push(line.text);
        log.append(node("li", "", line.text));
        head.textContent = "Pracuję. Dziennik czynności na żywo (wpisy: " + said.length + "):";
        log.scrollTop = log.scrollHeight;
        waiting.scrollIntoView({ block: "end" });
      }
    } catch { /* the result matters more than the commentary */ }
  };
  (async () => {
    for (let attempt = 0; attempt < 4500; attempt++) {           // about an hour of work
      await new Promise(resolve => setTimeout(resolve, 800));
      await drain();
      if (attempt % 3 !== 2) continue;                           // the result is asked for less often than the log
      try {
        const answer = await call("jobs/" + block.id);
        if (!answer.done) continue;
        await drain();
        waiting.remove();
        if (said.length) {
          const how = node("details", "how");
          how.append(node("summary", "", "Dziennik czynności (" + said.length + ")"));
          const list = node("ol", "steps");
          for (const line of said) list.append(node("li", "", line));
          how.append(list);
          show(how);
        }
        for (const part of answer.blocks) await (render[part.type] || render.text)(part);
        return;
      } catch { head.textContent = "Nie mogę sprawdzić wyniku. Spróbuję jeszcze raz."; }
    }
    head.textContent = "To trwa wyjątkowo długo. Wynik znajdziesz w dokumentach sprawy, gdy będzie gotowy.";
  })();
};

// ---------------------------------------------------------------- learning mode: always visible
function showLearned(lessons) {
  // „Nauczyłem się tego, potwierdzasz?” - lessons learned by watching are used only after a yes.
  if (!lessons || !lessons.length) return;
  const card = node("div", "card them learned-now");
  card.append(node("strong", "", "Tryb uczenia: nauczyłem się tego, potwierdzasz?"));
  const list = node("ul", "lesson-list");
  for (const lesson of lessons) {
    const item = node("li");
    const words = node("span", "", typeof lesson === "string" ? lesson : lesson.text);
    item.append(words);
    if (lesson.id) {
      const yes = node("button", "chip", "Tak");
      const no = node("button", "chip quiet", "Nie");
      const decide = accept => run(async () => {
        await call("learning/" + lesson.id, "POST", { accept });
        item.replaceChildren(node("span", "muted", (accept ? "✓ Zapamiętane: " : "✗ Odrzucone: ") + words.textContent));
        refreshLearning();
      });
      yes.onclick = decide(true);
      no.onclick = decide(false);
      item.append(yes, no);
    }
    list.append(item);
  }
  card.append(list, node("p", "muted", "Dopóki nie potwierdzisz, nie korzystam z tej lekcji. Wszystkie: „czego się nauczyłeś”."));
  show(card);
  refreshLearning();
}

async function refreshLearning() {
  let state;
  try { state = await call("learning"); } catch { return; }
  const badge = el("learning");
  badge.hidden = false;
  badge.textContent = (state.enabled ? "Tryb uczenia · " + state.total + (state.pending ? " · " + state.pending + " do potwierdzenia" : "")
                                     : "Tryb uczenia wyłączony");
  badge.classList.toggle("off", !state.enabled);
  badge.title = state.enabled ? "Uczę się z Twoich poprawek. Kliknij, żeby zobaczyć lekcje." : "Kliknij, żeby zobaczyć tryb uczenia.";
}
render.learning = () => refreshLearning();
render.lessons = block => showLearned(block.items);

render.progress = block => {
  // A long job on the office computer (e.g. downloading the speech model): a bar that fills by itself.
  const card = node("div", "card them progress");
  const bar = node("progress");
  bar.max = 100;
  const line = node("p", "muted", "Sprawdzam…");
  card.append(line, bar);
  el("messages").append(card);
  card.scrollIntoView({ block: "end" });
  (async () => {
    for (let attempt = 0; attempt < 2400 && card.isConnected; attempt++) {
      try {
        const now = await call(block.source);
        line.textContent = now.text;
        bar.value = now.percent;
        bar.hidden = now.state === "brak" || now.state === "blad";
        if (["gotowy", "blad", "brak"].includes(now.state)) return;
      } catch { line.textContent = "Nie mogę sprawdzić postępu. Spróbuję za chwilę."; }
      await new Promise(resolve => setTimeout(resolve, 1500));
    }
  })();
};

render.record = block => {
  const card = node("div", "card them");
  const name = node("input");
  name.maxLength = 80;
  name.value = block.name || "";
  name.placeholder = "np. Wniosek o wpis w KW";
  const start = node("button", "primary", "Zacznij nagrywać");
  const stop = node("button", "danger", "Zakończ nagranie");
  const state = node("p", "muted", "Nagranie obejmie ekran, który wskażesz, i mikrofon. Najwyżej 5 minut.");
  const narration = node("textarea");
  const narrationRow = field("Co mówiłeś (popraw, jeśli trzeba; możesz też dopisać ręcznie)", narration);
  const teach = node("button", "primary", "Naucz się z nagrania");
  stop.hidden = narrationRow.hidden = teach.hidden = true;
  let recorder = null, streams = [], frames = [], chunks = [], timer = null, limit = null, recording = null;

  const finish = () => {
    clearInterval(timer);
    clearTimeout(limit);
    streams.forEach(stream => stream.getTracks().forEach(track => track.stop()));
    if (recorder && recorder.state !== "inactive") recorder.stop();
  };

  start.onclick = run(async () => {
    if (!name.value.trim()) throw new Error("Najpierw nazwij procedurę.");
    let screen;
    try {
      screen = await navigator.mediaDevices.getDisplayMedia({ video: { frameRate: 5 }, audio: false });
    } catch {
      throw new Error("Nie wybrano ekranu do nagrania.");
    }
    let voice = null;
    try {
      voice = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      state.textContent = "Mikrofon niedostępny: nagrywam sam ekran, komentarz wpiszesz po nagraniu.";
    }
    streams = [screen, ...(voice ? [voice] : [])];
    const video = document.createElement("video");
    video.muted = true;
    video.srcObject = screen;
    await video.play();
    const canvas = document.createElement("canvas");
    const context = canvas.getContext("2d");
    let last = null;
    frames = []; chunks = [];
    const grab = () => {
      if (!video.videoWidth) return;
      const scale = Math.min(1, 1280 / video.videoWidth);
      canvas.width = Math.round(video.videoWidth * scale);
      canvas.height = Math.round(video.videoHeight * scale);
      context.drawImage(video, 0, 0, canvas.width, canvas.height);
      const now = signature(context, canvas.width, canvas.height);
      if (!changed(last, now)) return;
      last = now;
      frames.push(canvas.toDataURL("image/jpeg", 0.6).split(",")[1]);
      if (frames.length > MAX_FRAMES) frames = frames.filter((_, index) => index % 2 === 0 || index === frames.length - 1);
    };
    recorder = new MediaRecorder(new MediaStream([...screen.getVideoTracks(), ...(voice ? voice.getAudioTracks() : [])]),
      { videoBitsPerSecond: 350000, audioBitsPerSecond: 32000 });
    recorder.ondataavailable = event => { if (event.data.size) chunks.push(event.data); };
    recorder.onstop = run(async () => {
      grab();
      recording = new Blob(chunks, { type: "video/webm" });
      stop.hidden = true;
      narrationRow.hidden = teach.hidden = false;
      state.textContent = "Nagranie gotowe (" + frames.length + " ujęć ekranu).";
      if (block.transcribes && voice && recording.size <= maxBytes) {
        state.textContent += " Rozpoznaję mowę na tym komputerze…";
        try {
          const heard = await call("procedures/transcribe", "POST", { recording_b64: encode(new Uint8Array(await recording.arrayBuffer())) });
          narration.value = heard.text;
          state.textContent = "Nagranie gotowe. Sprawdź, czy dobrze zrozumiałem, co mówiłeś.";
        } catch (error) {
          state.textContent = error.message;
        }
      } else if (!block.transcribes) {
        state.textContent += " Na tym komputerze nie ma rozpoznawania mowy: wpisz, co wypełniałeś i dlaczego.";
      }
    });
    screen.getVideoTracks()[0].onended = finish;        // the browser's own "stop sharing" button
    recorder.start(1000);
    grab();
    timer = setInterval(grab, FRAME_EVERY_MS);
    limit = setTimeout(finish, MAX_RECORDING_MS);
    start.hidden = true;
    stop.hidden = false;
    name.readOnly = true;
    state.textContent = "Nagrywam. Mów na głos, co wpisujesz w każde pole i dlaczego.";
  });
  stop.onclick = finish;
  teach.onclick = run(async () => {
    if (narration.value.trim().length < 20) throw new Error("Opisz, co wypełniasz i dlaczego: bez tego nie nauczę się procedury.");
    status("Uczę się z nagrania. To może potrwać minutę.");
    const lesson = { name: name.value.trim(), narration: narration.value, frames };
    if (recording && recording.size <= maxBytes) lesson.recording_b64 = encode(new Uint8Array(await recording.arrayBuffer()));
    const proposal = await call("procedures/learn", "POST", lesson);
    card.remove();
    bubble("Naucz się z nagrania: " + lesson.name, "me");
    render.learned(proposal);
    status("Procedura do sprawdzenia. Nic nie zostało jeszcze zapisane.");
  });
  card.append(field("Nazwa procedury", name), state, start, stop, narrationRow, teach);
  show(card);
};

render.learned = proposal => {
  const procedure = proposal.procedure;
  const card = node("div", "card them");
  card.append(node("p", "notice", "Tak zrozumiałem tę procedurę. Popraw, co trzeba: każdy wiersz to „pole | skąd wartość | dlaczego”."));
  card.append(node("p", "muted", (procedure.program || "Program") + (procedure.cel ? ": " + procedure.cel : "")));
  const steps = node("textarea", "tall");
  const sourceOf = step => step.akcja === "wyslij" ? "wyślij" : step.akcja === "kliknij" ? "kliknij" : step.zrodlo;
  steps.value = procedure.kroki.map(step => [step.pole, sourceOf(step), step.dlaczego].join(" | ")).join("\n");
  const kind = node("select");
  kind.append(new Option("Strona internetowa", "strona"), new Option("Program na tym komputerze", "program"));
  kind.value = procedure.rodzaj || "strona";
  const address = node("input");
  address.maxLength = 400;
  address.value = procedure.adres || "";
  const actionOf = source => {
    const plain = source.toLowerCase();
    if (/^(wyślij|wyslij|złóż|zloz|prześlij|przeslij)/.test(plain)) return "wyslij";
    if (/^(kliknij|naciśnij|nacisnij)/.test(plain)) return "kliknij";
    return "wpisz";
  };
  const approve = node("button", "primary", "Zatwierdzam procedurę");
  approve.onclick = run(async () => {
    const kroki = steps.value.split("\n").map(line => line.split("|").map(part => part.trim()))
      .filter(parts => parts[0]).map(parts => ({
        pole: parts[0], zrodlo: parts[1] || "", dlaczego: parts.slice(2).join(" | "), akcja: actionOf(parts[1] || "") }));
    const saved = await call("procedures/" + proposal.id + "/approve", "POST",
      { ...procedure, rodzaj: kind.value, adres: address.value.trim(), kroki });
    card.remove();
    bubble("Zatwierdzam procedurę", "me");
    bubble("Zapamiętałem procedurę „" + saved.name + "” (" + saved.steps + " kroków). Dla każdej sprawy napisz „wypełnij " + saved.name + "”: wpiszę dane sam i poczekam z wysłaniem na Twoje zatwierdzenie.", "them");
    render.buttons({ items: [{ label: "Wypełnij: " + saved.name, say: "wypełnij " + saved.name }] });
    status("Procedura zapisana w sejfie.");
  });
  card.append(node("p", "muted", "Przycisk, który wysyła albo składa wniosek, oznacz jako „wyślij”: na nim zawsze się zatrzymam i poczekam na Twoje zatwierdzenie."));
  card.append(field("Gdzie jest formularz", kind), field("Adres strony albo tytuł okna programu", address),
    field("Kroki procedury", steps), approve);
  show(card);
};

const FILL_STATES = {
  filled: ["✓", "wpisane"], clicked: ["→", "przeszedłem dalej"], missing: ["✗", "nie znalazłem tego pola"],
  differs: ["!", "pole pokazuje inną wartość"], "no-option": ["!", "nie ma takiej pozycji na liście"],
  refused: ["!", "pole nie przyjęło wartości"], empty: ["–", "brak danych w dokumentach"],
};

function screenshot(data, alt) {
  const image = node("img", "shot");
  image.alt = alt;
  image.src = "data:image/jpeg;base64," + data;
  image.onclick = () => image.classList.toggle("zoom");
  return image;
}

render.filled = block => {
  const card = node("div", "card them");
  card.append(node("p", "", block.procedure + (block.where ? " · " + block.where : "")));
  block.report.forEach(row => {
    const [mark, meaning] = FILL_STATES[row.state] || ["?", row.state];
    const line = node("div", "fill-row state-" + row.state);
    line.append(node("div", "fill-field", mark + " " + row.field));
    line.append(node("div", row.value ? "code" : "muted", row.value || meaning));
    if (row.state !== "filled" && row.value) line.append(node("div", "muted", meaning + (row.read ? ": " + row.read : "")));
    card.append(line);
  });
  if (block.image) card.append(screenshot(block.image, "Wypełniony formularz"));
  show(card);
};

render.image = block => {
  const card = node("div", "card them");
  card.append(screenshot(block.image, block.alt || "Zrzut ekranu"));
  show(card);
};

render.fill = block => {
  const card = node("div", "card them");
  card.append(node("p", "", block.name + (block.program ? " · " + block.program : "")));
  if (block.missing) card.append(node("p", "notice", "Brakuje wartości: " + block.missing + ". Tych danych nie ma w dokumentach sprawy."));
  if (block.unknown_placeholders.length) {
    card.append(node("p", "notice", "Sprawdź pola ze znacznikami w nawiasach kwadratowych: model użył nieznanych znaczników."));
  }
  block.items.forEach((item, index) => {
    const row = node("div", "fill-row");
    row.append(node("div", "fill-field", (index + 1) + ". " + item.field));
    const value = node("div", item.value ? "code" : "muted", item.value || "brak w dokumentach");
    row.append(value);
    if (item.value && item.value !== "kliknij") {
      const copy = node("button", "", "Kopiuj");
      copy.setAttribute("aria-label", "Kopiuj: " + item.field);
      copy.onclick = async () => {
        try {
          await navigator.clipboard.writeText(item.value);
          copy.textContent = "Skopiowano";
          status("Skopiowano „" + item.field + "”. Wklej w formularzu (Ctrl+V).");
        } catch {
          status("Zaznacz wartość i skopiuj ją ręcznie.");
        }
      };
      row.append(copy);
    }
    const note = [item.from && "z: " + item.from, item.why && "bo: " + item.why].filter(Boolean).join(" · ");
    if (note) row.append(node("div", "muted", note));
    card.append(row);
  });
  show(card);
};

// What the program is doing, in plain words, while it works; folded into „Jak to zrobiłem” afterwards.
let activitySeen = 0;

async function exchange(turn) {
  const waiting = node("div", "bubble them wait working");
  const head = node("div", "", "Myślę…");
  const steps = node("ol", "steps");
  waiting.append(head, steps);
  show(waiting);
  const said = [];
  let polling = true;
  const poll = (async () => {
    while (polling) {
      await new Promise(resolve => setTimeout(resolve, 600));
      if (!polling) break;
      try {
        const { lines } = await call("activity?after=" + activitySeen);
        for (const line of lines) {
          activitySeen = Math.max(activitySeen, line.n);
          said.push(line.text);
          steps.append(node("li", "", line.text));
          head.textContent = "Pracuję…";
          waiting.scrollIntoView({ block: "end" });
        }
      } catch { /* the answer matters more than the commentary */ }
    }
  })();
  let reply;
  try {
    reply = await call("chat", "POST", { case: currentCase(), names, ...turn });
  } finally {
    polling = false;
    await poll;
    try {
      const { lines } = await call("activity?after=" + activitySeen);
      for (const line of lines) { activitySeen = Math.max(activitySeen, line.n); said.push(line.text); }
    } catch { /* ignore */ }
    waiting.remove();
  }
  if (said.length) {
    const how = node("details", "how");
    how.append(node("summary", "", "Jak to zrobiłem (" + said.length + (said.length === 1 ? " krok)" : said.length < 5 ? " kroki)" : " kroków)")));
    const list = node("ol", "steps");
    for (const line of said) list.append(node("li", "", line));
    how.append(list);
    show(how);
  }
  for (const block of reply.blocks) await (render[block.type] || render.text)(block);
  if (reply.blocks.some(block => block.type === "case")) await refreshCases(currentCase());
  if (scope !== "listen") refreshAhead();
}

async function send(sentence, shown) {
  const text = sentence.trim();
  if (!text) return;
  const heard = el("prompt").dataset.heard;
  if (heard) {
    delete el("prompt").dataset.heard;
    if (heard.trim() && !text.includes(heard.trim()) && scope !== "read") {
      call("learning/dictation", "POST", { heard, final: text }).then(r => showLearned(r.learned)).catch(() => {});
    }
  }
  bubble(shown || text, "me");
  status("");
  await exchange({ text });
}

function shortcuts() {
  const items = [["Co mam dziś", "co mam dziś"], ["Wiadomości", "wiadomości"], ["Poczta", "poczta"], ["Dokumenty", "dokumenty"]];
  if (admin) items.push(["Stanowiska", "stanowiska"], ["Drukarki", "drukarki"], ["Mikrofony", "mikrofony"],
                        ["Gdzie są dane", "gdzie są dane"], ["Stan stanowiska", "stan"], ["Dodaj telefon", "dodaj telefon"]);
  items.push(["Co umiesz?", "pomoc"]);
  const buttons = items.map(([label, sentence]) => sayButton(label, sentence));
  if (scope !== "read") {
    const note = node("button", "", "Nowy dokument tekstowy");
    note.onclick = () => { if (mayDiscard()) showSheet(null, [], ""); };
    buttons.splice(3, 0, note);
  }
  el("shortcuts").replaceChildren(node("h2", "", "Na skróty"), ...buttons);
}

function chips() {
  const items = admin
    ? [["Stan", "stan"], ["Dodaj telefon", "dodaj telefon"], ["Zrób kopię", "zrób kopię"], ["Dziennik", "dziennik"], ["Dokumenty", "dokumenty"], ["Narzędzia", "narzędzia"], ["Pomoc", "pomoc"]]
    : [["Dokumenty", "dokumenty"], ["Sprawy", "sprawy"], ["Taksa", "taksa"], ["Narzędzia", "narzędzia"], ["Pomoc", "pomoc"]];
  const elements = items.map(([label, sentence]) => sayButton(label, sentence));
  if (scope !== "read") {
    const note = node("button", "", "Nowy dokument tekstowy");
    note.onclick = () => { if (mayDiscard()) showSheet(null, [], ""); };
    elements.splice(1, 0, note);
  }
  el("chips").replaceChildren(...elements);
}

// ---------------------------------------------------------------- document sheet
function mayDiscard() {
  const dirty = !el("sheet").hidden && !el("text-editor").hidden && scope !== "read" &&
    (el("name").value !== (opened?.name ?? "") || el("body").value !== originalText);
  return !dirty || window.confirm("Porzucić niezapisane zmiany?");
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

function showSheet(document, versions, localText) {
  opened = document;
  let text = localText;
  if (document && text === undefined && /\.txt$/i.test(document.name)) {
    try {
      text = new TextDecoder("utf-8", { fatal: true }).decode(decode(document.content_b64));
    } catch {
      // Non-UTF-8 files are available for download with their original bytes.
    }
  }
  const writer = scope !== "read";
  originalText = text ?? "";
  el("name").value = document?.name ?? "";
  el("body").value = originalText;
  el("name").readOnly = !writer;
  el("body").readOnly = !writer;
  el("text-editor").hidden = text === undefined;
  const writable = writer && (!document || document.version === versions[0]);
  el("save").hidden = !writable;
  el("replace-tools").hidden = !writable || !document;
  el("replacement").value = "";
  el("copy").hidden = !writer || !document;
  el("selected").textContent = document ? document.name + " · wersja " + document.version : "Nowy dokument";
  el("versions").replaceChildren(...versions.map(version =>
    new Option("Wersja " + version, version, false, version === document?.version)
  ));
  el("history").hidden = !document;
  el("sheet").hidden = false;
  el("sheet").scrollIntoView({ block: "nearest" });
}

function closeSheet() {
  opened = null;
  originalText = "";
  el("sheet").hidden = true;
}

async function openDocument(id, version) {
  if (!mayDiscard()) return;
  const [document, versions] = await Promise.all([
    call("documents/" + id + (version ? "?version=" + version : "")),
    call("documents/" + id + "/versions"),
  ]);
  showSheet(document, versions);
  status("Otwarto wersję " + document.version + ".");
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
  showSheet({ ...result, name, content_b64 }, versions, text);
  render.documents({ items: [{ id: result.id, name, version: result.version }] });
  status("Zapisano wersję " + result.version + ".");
}

async function saveText(current) {
  const name = el("name").value.trim();
  if (!/\.txt$/i.test(name)) throw new Error("Podaj nazwę pliku z rozszerzeniem .txt.");
  const text = el("body").value;
  await save(name, new TextEncoder().encode(text), current, text);
}

// ---------------------------------------------------------------- voice notes
const AUDIO = /\.(webm|ogg|opus|oga|m4a|mp3|wav|aac|amr|3gp|flac)$/i;
let voice = null;

function showVoiceResult(result) {
  bubble(result.text ? "Notatka głosowa:\n\n" + result.text : result.detail, "them");
  if (result.documents.length) render.documents({ items: result.documents });
  status(result.text ? "Zapisałem nagranie i tekst" + (currentCase() ? " w sprawie „" + currentCase() + "”." : ".") : result.detail);
}

async function sendVoice(bytes, name) {
  const waiting = bubble("Zapisuję notatkę głosową…", "them wait");
  let result;
  try {
    result = await call("voice", "POST", { audio_b64: encode(bytes), name, case: currentCase() });
  } finally {
    waiting.remove();
  }
  if (!result.job) {
    showVoiceResult(result);
    return;
  }
  // The cloud needs a while: keep working, the text arrives in the conversation by itself.
  const pending = bubble(result.detail, "them wait");
  status("Notatka zapisana. Możesz dalej pracować; tekst dopiszę, gdy będzie gotowy.");
  (async () => {
    for (let attempt = 0; attempt < 200; attempt++) {
      await new Promise(resolve => setTimeout(resolve, 3000));
      try {
        const answer = await call("voice/" + result.job);
        if (answer.done) {
          pending.remove();
          showVoiceResult(answer);
          return;
        }
      } catch {
        pending.textContent = "Nie mogę sprawdzić, czy tekst notatki jest gotowy. Spróbuję jeszcze raz.";
      }
    }
    pending.textContent = "Przepisywanie trwa wyjątkowo długo. Tekst znajdziesz w dokumentach sprawy, gdy będzie gotowy.";
  })();
}

// ---------------------------------------------------------------- live dictation into the message box
// Speak and the words appear in the box as you say them (speech in Frankfurt, nothing recorded).
// ✕ throws the dictation away, ■ stops so the text can be corrected, ↑ sends it at once.
const PIECE_MS = 250;
let dictation = null;

function downsample(input, rate) {
  const ratio = rate / 16000;
  const out = new Int16Array(Math.floor(input.length / ratio));
  for (let i = 0; i < out.length; i++) {
    const start = Math.floor(i * ratio), end = Math.min(input.length, Math.floor((i + 1) * ratio));
    let sum = 0;
    for (let j = start; j < end; j++) sum += input[j];
    const value = Math.max(-1, Math.min(1, sum / Math.max(1, end - start)));
    out[i] = value < 0 ? value * 0x8000 : value * 0x7fff;
  }
  return out;
}

function dictationBar(on) {
  el("dictation").hidden = !on;
  el("voice").hidden = on || scope === "listen";
  el("attach").hidden = on || scope === "read";
  el("send").hidden = on;
}

async function startDictation(target = el("prompt")) {
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
  } catch {
    throw new Error("Brak dostępu do mikrofonu. Zezwól na niego w ustawieniach przeglądarki.");
  }
  let id;
  try {
    ({ id } = await call("dictation", "POST", {}));
  } catch (error) {
    stream.getTracks().forEach(track => track.stop());
    bubble(error.message, "them");               // why there will be no text, said plainly in the conversation
    if (/zaloguj/i.test(error.message)) render.buttons({ items: [{ label: "Zaloguj", say: "zaloguj" }] });
    render.buttons({ items: [{ label: "Sprawdź mowę", say: "sprawdź mowę" }] });
    return;
  }
  const audio = new AudioContext();
  await audio.resume();
  const source = audio.createMediaStreamSource(stream);
  const processor = audio.createScriptProcessor(4096, 1, 1);
  const before = target.value.replace(/\s+$/, "");
  const state = { id, stream, audio, processor, pending: [], busy: false, closed: false, before, text: "", target };
  dictation = state;
  processor.onaudioprocess = event => {
    const samples = event.inputBuffer.getChannelData(0);
    let peak = 0;
    for (let i = 0; i < samples.length; i += 64) peak = Math.max(peak, Math.abs(samples[i]));
    drawLevel(peak);
    state.pending.push(downsample(samples, audio.sampleRate));
  };
  source.connect(processor);
  processor.connect(audio.destination);
  state.timer = setInterval(() => pushPiece(state, false).catch(() => {}), PIECE_MS);
  dictationBar(true);
  target.placeholder = "Mów, tekst pojawia się tutaj…";
  status("Słucham. ■ zatrzymuje, ↑ wysyła od razu, ✕ anuluje.");
}

function takePending(state) {
  const total = state.pending.reduce((sum, part) => sum + part.length, 0);
  const pcm = new Int16Array(total);
  let at = 0;
  for (const part of state.pending) { pcm.set(part, at); at += part.length; }
  state.pending = [];
  return new Uint8Array(pcm.buffer);
}

async function pushPiece(state, end) {
  if (state.busy && !end) return;
  while (state.busy) await new Promise(resolve => setTimeout(resolve, 50));
  state.busy = true;
  try {
    const answer = await call("dictation/" + state.id, "POST", { pcm_b64: encode(takePending(state)), end });
    if (dictation === state || end) {
      state.text = answer.text;
      state.target.value = (state.before ? state.before + " " : "") + answer.text;
      state.target.dispatchEvent(new Event("input"));
    }
    if (answer.error && !state.warned) {
      state.warned = true;                       // say it once, in the conversation, not only in the status line
      bubble(answer.error, "them");
      if (answer.login) {
        render.buttons({ items: [{ label: "Zaloguj", say: "zaloguj" }] });
        if (!end) stopDictation("cancel");
      }
    }
    if (answer.second_way) status("Szybkie połączenie nie działało: przepisałem nagranie drugą drogą.");
    return answer;
  } finally {
    state.busy = false;
  }
}

async function stopDictation(mode) {
  const state = dictation;
  if (!state) return;
  dictation = null;
  clearInterval(state.timer);
  state.processor.disconnect();
  state.stream.getTracks().forEach(track => track.stop());
  state.audio.close().catch(() => {});
  dictationBar(false);
  drawLevel(0);
  state.target.placeholder = state.target === el("prompt") ? "Napisz…" : "";
  if (mode === "cancel") {
    call("dictation/" + state.id, "DELETE").catch(() => {});
    state.target.value = state.before;
    state.target.dispatchEvent(new Event("input"));
    status("Dyktowanie anulowane.");
    return;
  }
  status("Kończę przepisywanie…");
  await pushPiece(state, true);
  status(state.target.value.trim() ? "Gotowe. Popraw tekst, jeśli trzeba." : "Nie usłyszałem słów. Spróbuj jeszcze raz.");
  state.target.dataset.heard = state.text;          // compared with what is finally sent: learning mode
  if (state.target !== el("prompt")) {
    state.target.focus();
    return;
  }
  if (mode === "send" && el("prompt").value.trim()) {
    const text = el("prompt").value;                 // not through the Send button: we are inside run() already
    el("prompt").value = "";
    el("prompt").style.height = "";
    await send(text);
  } else {
    el("prompt").focus();
  }
}

function drawLevel(peak) {
  const bars = el("dictation-level").children;
  for (let i = bars.length - 1; i > 0; i--) bars[i].style.height = bars[i - 1].style.height;
  if (bars.length) bars[0].style.height = Math.max(8, Math.min(100, peak * 260)) + "%";
}

el("voice").onclick = run(() => startDictation());
el("dictation-cancel").onclick = () => stopDictation("cancel");
el("dictation-stop").onclick = run(() => stopDictation("stop"));
el("dictation-send").onclick = run(() => stopDictation("send"));

async function saveFile(input, current) {
  const file = el(input).files[0];
  if (!file) throw new Error("Wybierz plik.");
  if (file.size > maxBytes) throw new Error("Limit rozmiaru pliku to 20 MiB.");
  if (!current && AUDIO.test(file.name)) {          // a recording from a dictaphone or a messenger
    bubble("🎤 " + file.name, "me");
    el(input).value = "";
    await sendVoice(new Uint8Array(await file.arrayBuffer()), file.name);
    return;
  }
  if (!mayDiscard()) return;
  if (!current) bubble("Dodaję plik " + file.name, "me");
  await save(file.name, new Uint8Array(await file.arrayBuffer()), current);
  el(input).value = "";
  if (!current) bubble("Dodałem " + file.name + (currentCase() ? " do sprawy „" + currentCase() + "”." : "."), "them");
}

// Files dropped, pasted or picked go straight into the conversation: saved in the vault (in the chosen
// case), recordings transcribed, documents offered for a summary or a check at once.
const READABLE = /\.(docx|pdf|txt|eml)$/i;

async function attachFiles(files) {
  files = Array.from(files || []);
  if (!files.length) return;
  if (scope === "read") throw new Error("To urządzenie ma dostęp tylko do odczytu.");
  for (const file of files) {
    if (file.size > maxBytes) {
      bubble(file.name + ": limit rozmiaru pliku to 20 MiB.", "them");
      continue;
    }
    const name = file.name && file.name !== "image.png" ? file.name
      : "wklejony-" + new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-") + "." + ((file.type.split("/")[1] || "bin").replace("jpeg", "jpg"));
    const bytes = new Uint8Array(await file.arrayBuffer());
    if (AUDIO.test(name)) {
      bubble("🎤 " + name, "me");
      await sendVoice(bytes, name);
      continue;
    }
    bubble("📎 " + name, "me");
    const result = await call("documents", "POST", { id: null, expected_version: 0, name, content_b64: encode(bytes), case: currentCase() });
    render.documents({ items: [{ id: result.id, name, version: result.version }] });
    bubble("Zapisałem " + name + (currentCase() ? " w sprawie „" + currentCase() + "”." : " w sejfie (bez sprawy).")
      + (READABLE.test(name) ? " Co z nim zrobić?" : ""), "them");
    if (READABLE.test(name)) {
      render.buttons({ items: [{ label: "Streść", say: "streść " + name }, { label: "Sprawdź błędy", say: "sprawdź " + name },
                               { label: "Otwórz", say: "otwórz " + name }] });
    }
  }
  status(files.length === 1 ? "Plik dodany." : "Dodano pliki: " + files.length + ".");
}

// ---------------------------------------------------------------- microphone mode
const SEGMENT_MS = window.NOTARAI_SEGMENT_MS || 20000;     // short pieces: a lost one loses little
const QUIET = 0.02;                                         // below this the piece is silence and is not sent
let listener = null;

async function startListener() {
  const state = await call("listen/state");
  el("listener-name").textContent = "Mikrofon: " + state.source;
  el("listener").hidden = false;
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
  } catch {
    el("listener-state").textContent = "Brak dostępu do mikrofonu. Zezwól na niego w ustawieniach przeglądarki i odśwież.";
    return;
  }
  const audio = new AudioContext();
  await audio.resume();
  const analyser = audio.createAnalyser();
  analyser.fftSize = 1024;
  audio.createMediaStreamSource(stream).connect(analyser);
  const samples = new Float32Array(analyser.fftSize);
  listener = { stream, audio, paused: false, lock: null, peak: 0, sent: 0, timer: null };

  const level = () => {
    analyser.getFloatTimeDomainData(samples);
    let sum = 0;
    for (const value of samples) sum += value * value;
    const rms = Math.sqrt(sum / samples.length);
    listener.peak = Math.max(listener.peak, rms);
    el("listener-level").style.width = Math.min(100, Math.round(rms * 400)) + "%";
  };
  listener.meter = setInterval(level, 200);

  const keepAwake = async () => {
    try { if ("wakeLock" in navigator) listener.lock = await navigator.wakeLock.request("screen"); } catch { /* optional */ }
  };
  document.addEventListener("visibilitychange", () => { if (!document.hidden && listener) keepAwake(); });
  await keepAwake();

  const piece = () => {
    if (!listener || listener.paused) return;
    const chunks = [];
    const recorder = new MediaRecorder(stream, { audioBitsPerSecond: 32000 });
    const started = Date.now();
    listener.peak = 0;
    recorder.ondataavailable = event => { if (event.data.size) chunks.push(event.data); };
    recorder.onstop = async () => {
      const loud = listener && listener.peak >= QUIET;
      if (listener && !listener.paused) piece();          // the next piece starts at once
      if (!loud) return;
      const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
      try {
        const answer = await call("listen", "POST", {
          audio_b64: encode(new Uint8Array(await blob.arrayBuffer())),
          suffix: /ogg/.test(blob.type) ? ".ogg" : /mp4/.test(blob.type) ? ".mp4" : ".webm",
          started_ms: started, duration_ms: Date.now() - started,
        });
        listener.sent += answer.accepted ? 1 : 0;
        el("listener-state").textContent = !answer.enabled ? "Nasłuch jest wyłączony w kancelarii."
          : answer.paused ? "Nasłuch wstrzymany w kancelarii." : "Słucham. Przesłane fragmenty rozmów: " + listener.sent + ".";
      } catch (error) {
        el("listener-state").textContent = "Nie mogę połączyć się z kancelarią. Próbuję dalej. (" + error.message + ")";
      }
    };
    recorder.start();
    listener.timer = setTimeout(() => recorder.state !== "inactive" && recorder.stop(), SEGMENT_MS);
    listener.recorder = recorder;
  };
  listener.piece = piece;
  el("listener-state").textContent = state.enabled ? (state.paused ? "Nasłuch wstrzymany w kancelarii." : "Słucham.")
    : "Nasłuch jest wyłączony w kancelarii. Włączysz go w panelu stanowiska.";
  piece();
}

el("listener-toggle").onclick = () => {
  if (!listener) return;
  listener.paused = !listener.paused;
  el("listener-toggle").textContent = listener.paused ? "Wznów" : "Wstrzymaj";
  if (listener.paused) {
    clearTimeout(listener.timer);
    if (listener.recorder && listener.recorder.state !== "inactive") listener.recorder.stop();
    el("listener-state").textContent = "Wstrzymane na tym urządzeniu. Nic nie przesyłam.";
  } else {
    el("listener-state").textContent = "Słucham.";
    listener.recorder = null;
    listener.piece();
  }
};

// ---------------------------------------------------------------- session
async function refreshCases(keep) {
  const cases = await call("cases");
  const state = await call("status");
  const options = [];
  if (state.cases === null) options.push(new Option("Wszystkie sprawy", ALL));
  cases.forEach(name => options.push(new Option(name, name)));
  if (keep && !cases.includes(keep)) options.push(new Option(keep, keep));
  if (state.station) el("station").textContent = " · " + state.station;
  el("case").replaceChildren(...options);
  if (keep) el("case").value = keep;
  // The side list on a wide screen: one click switches the case.
  el("case-list").replaceChildren(...options.map(option => {
    const item = node("li");
    const button = node("button", option.value === el("case").value ? "current" : "", option.text);
    button.onclick = () => {
      el("case").value = option.value;
      el("case").dispatchEvent(new Event("change"));
      for (const other of el("case-list").querySelectorAll("button")) other.classList.toggle("current", other === button);
    };
    item.append(button);
    return item;
  }));
  el("mode").hidden = state.mode !== "synthetic-only";
  el("mode").textContent = "Ta instalacja ma jeszcze stare ustawienie trybu próbnego: używaj fikcyjnych dokumentów.";
}

// Pairing is done once. A paired device stays connected across refreshes and restarts (localStorage)
// until "Rozłącz" or until the office revokes it. The office panel itself keeps its session only as long
// as its window (sessionStorage): the desktop icon opens it again without any code.
function sessionStore() {
  return admin ? sessionStorage : localStorage;
}

function remember(device) {
  try {
    if (device) sessionStore().setItem("notarai-session", JSON.stringify({ token: device.token, scope: device.scope }));
    else sessionStore().removeItem("notarai-session");
  } catch { /* private mode or blocked storage: the session simply ends with a refresh */ }
}

function remembered() {
  try { return JSON.parse(sessionStore().getItem("notarai-session") || "null"); } catch { return null; }
}

async function enter(device) {
  if (!tunnel && device.token) remember(device);
  token = device.token;
  scope = device.scope;
  el("pairing").hidden = true;
  if (scope === "listen") {          // a microphone: no chat, no documents
    el("mode").hidden = true;
    await startListener();
    return;
  }
  el("workspace").hidden = false;
  el("bar").hidden = false;
  el("attach").hidden = scope === "read";
  el("voice").hidden = !(navigator.mediaDevices && window.AudioContext);
  el("messages").replaceChildren();
  chips();
  shortcuts();
  refreshAgenda();
  if (scope !== "listen") refreshLearning();
  status(admin ? "Panel otwarty." : (scope === "write" ? "Połączono z prawem zapisu." : "Połączono w trybie odczytu."));
  await refreshCases();
  layout = await call("layout");
  drawTiles();
  await refreshRules();
  try { activitySeen = Math.max(0, ...(await call("activity")).lines.map(l => l.n)); } catch { activitySeen = 0; }
  await exchange({ hello: true });
  welcome();
}

function leave(message) {
  remember(null);
  token = "";
  scope = "";
  names = [];
  closeSheet();
  layout = { show: false, tiles: [] };
  drawTiles();
  el("rules-box").hidden = true;
  el("messages").replaceChildren();
  el("workspace").hidden = true;
  el("bar").hidden = true;
  el("pairing").hidden = false;
  status(message);
}

async function unlock(code) {
  // Never through call(): this must stay a plain local request even if a tunnel identity exists.
  const response = await fetch("/v2/devices/redeem", {
    method: "POST", headers: { "Content-Type": "application/json" }, cache: "no-store",
    credentials: "omit", body: JSON.stringify({ code }),
  });
  const session = response.ok ? await response.json() : null;
  if (!session || (admin && session.scope !== "admin") || (!admin && session.scope === "admin")) {
    throw new Error(admin ? "Kod panelu jest nieważny. Otwórz NotarAI ponownie ikoną na pulpicie albo z menu Start." : "Kod parowania jest nieważny albo wygasł.");
  }
  await enter(session);
}

async function enterRemote(session) {
  tunnel = session.tunnel;
  tunnel.onclose = () => {
    tunnel = null;
    leave("Połączenie z kancelarią zostało przerwane. Otwórz Pocket ponownie.");
  };
  await enter({ token: "", scope: session.device.scope });
}

async function start() {
  const fragment = window.location.hash;
  if (fragment) history.replaceState(null, "", window.location.pathname);
  if (admin && fragment.length > 1) {
    // The launcher opens this page with a one-time code in the fragment, which never reaches a server log.
    await unlock(fragment.slice(1));
    return;
  }
  const saved = remembered();
  if (saved && saved.token) {
    token = saved.token;
    // The office computer may still be starting: wait for it instead of forgetting the pairing.
    for (let attempt = 0; ; attempt++) {
      try {
        await call("status");
        await enter(saved);
        return;
      } catch (error) {
        if (error.code === 401 || error.code === 403 || attempt >= 20) {
          token = "";
          if (error.code === 401 || error.code === 403) remember(null);
          break;
        }
        status("Czekam na komputer kancelarii…");
        await new Promise(resolve => setTimeout(resolve, 3000));
      }
    }
  }
  if (admin) {
    // After a restart or an update the window reconnects by itself; no code to type.
    try {
      const response = await fetch("/v2/admin/reopen", { method: "POST", cache: "no-store", credentials: "omit" });
      if (response.ok) {
        await unlock((await response.json()).code);
        return;
      }
    } catch { /* the worker is still starting: say how to open it */ }
    status("Otwórz NotarAI ikoną na pulpicie albo z menu Start.");
    return;
  }
  const link = NotaraiTunnel.parseLink(fragment);
  if (link) {
    status("Łączę z kancelarią…");
    await enterRemote(await NotaraiTunnel.pair(link));
    status("Urządzenie sparowane. Następnym razem połączy się samo.");
  } else if (await NotaraiTunnel.hasIdentity()) {
    status("Łączę z kancelarią…");
    await enterRemote(await NotaraiTunnel.resume());
  } else if (!["127.0.0.1", "localhost"].includes(window.location.hostname)) {
    // Opened on the public address without a pairing: a typed code cannot work from here.
    el("pairing").replaceChildren(node("p", "",
      "To urządzenie nie jest jeszcze sparowane. W kancelarii napisz w panelu stanowiska „dodaj telefon” i zeskanuj kod QR aparatem tego telefonu."));
  }
}

el("pair").onclick = run(async () => {
  const code = el("code").value.trim();
  el("code").value = "";
  await unlock(code);
});
el("send").onclick = run(async () => {
  const text = el("prompt").value;
  el("prompt").value = "";
  el("prompt").style.height = "";
  await send(text);
});
el("prompt").addEventListener("keydown", event => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    el("send").click();
  }
});
el("prompt").addEventListener("input", () => {
  el("prompt").style.height = "auto";
  el("prompt").style.height = el("prompt").scrollHeight + "px";
});
el("case").onchange = run(async () => {
  closeSheet();
  bubble(currentCase() ? "Sprawa: " + currentCase() : "Wszystkie sprawy", "me");
  await exchange({ text: "dokumenty" });
});
el("attach").onclick = () => el("file").click();
el("file").onchange = run(async () => {
  const files = Array.from(el("file").files);
  el("file").value = "";
  if (mayDiscard()) await attachFiles(files);
});
// Drag files anywhere onto the conversation, or paste them (Ctrl+V) into the message box.
let dragDepth = 0;
el("workspace").addEventListener("dragenter", event => {
  if (![...event.dataTransfer.types].includes("Files")) return;
  event.preventDefault();
  dragDepth++;
  el("workspace").classList.add("dropping");
});
el("workspace").addEventListener("dragover", event => {
  if ([...event.dataTransfer.types].includes("Files")) event.preventDefault();
});
el("workspace").addEventListener("dragleave", () => {
  dragDepth = Math.max(0, dragDepth - 1);
  if (!dragDepth) el("workspace").classList.remove("dropping");
});
el("workspace").addEventListener("drop", event => {
  if (!event.dataTransfer.files.length) return;
  event.preventDefault();
  dragDepth = 0;
  el("workspace").classList.remove("dropping");
  run(() => attachFiles(event.dataTransfer.files))();
});
el("prompt").addEventListener("paste", event => {
  const files = event.clipboardData && event.clipboardData.files;
  if (files && files.length) {
    event.preventDefault();
    run(() => attachFiles(files))();
  }
});
el("logout").onclick = run(async () => {
  if (!mayDiscard()) return;
  if (tunnel) {
    if (!window.confirm("Rozłączyć i zapomnieć to urządzenie? Ponowne połączenie wymaga nowego kodu z kancelarii.")) return;
    tunnel.onclose = () => {};
    tunnel.close();
    tunnel = null;
    await NotaraiTunnel.forgetIdentity();
  }
  leave("Rozłączono.");
});
el("learning").onclick = run(async () => {
  const state = await call("learning");
  await send(state.pending ? "lekcje do potwierdzenia" : "tryb uczenia", state.pending ? "Lekcje do potwierdzenia" : "Tryb uczenia");
});
el("agenda-add").onclick = () => {
  // A chosen day is written in already: only the hour and what remain to say or type.
  const [y, m, d] = (cal.day || "").split("-");
  el("prompt").value = cal.day ? `termin ${d}.${m}.${y} ` : "termin ";
  el("prompt").focus();
  status("Dopisz godzinę i co się odbędzie, np. „10:00 podpisanie aktu Kowalski”, i wyślij. Możesz też podyktować 🎤.");
};
el("arrange").onclick = () => { arranging = !arranging; drawTiles(); };
el("add-tile").onclick = run(() => send("narzędzia", "Dodaj narzędzie"));
el("hide-tiles").onclick = run(() => send("ukryj kafelki", "Schowaj kafelki"));
el("close-sheet").onclick = () => { if (mayDiscard()) closeSheet(); };
el("open-version").onclick = run(() => openDocument(opened.id, el("versions").value));
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
el("replace").onclick = run(() => saveFile("replacement", opened));

if (!admin && "serviceWorker" in navigator) {
  navigator.serviceWorker.register("pocket-sw.js").catch(() => { /* optional */ });
}
run(start)();
