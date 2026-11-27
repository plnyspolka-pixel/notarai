"use strict";
// One chat window for Pocket (a paired device) and for the workstation panel (data-mode="admin").
// The page sends sentences to /v2/chat and renders the blocks it gets back.

const el = id => document.getElementById(id);
const admin = document.body.dataset.mode === "admin";
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
        ? (admin ? "Sesja panelu wygasła. Otwórz panel ponownie z menu Start."
                 : "Sesja wygasła lub dostęp został cofnięty. Skopiuj niezapisany tekst przed rozłączeniem.")
        : code === 409 && detail === "revision conflict"
          ? "Konflikt wersji. Zachowano edytowany tekst i wybrany plik. Możesz zapisać zmiany jako osobny dokument."
          // Messages written for the notary are Polish sentences; protocol errors stay generic.
          : (/[ąćęłńóśźż .]/i.test(detail) && detail.length > 20 ? detail : "Nie udało się wykonać operacji (HTTP " + code + ")."));
    error.challenge = body && body.challenge;
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
      print.onclick = () => {
        card.classList.add("printing");
        window.print();
        card.classList.remove("printing");
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

async function exchange(turn) {
  const waiting = bubble("Piszę…", "them wait");
  let reply;
  try {
    reply = await call("chat", "POST", { case: currentCase(), names, ...turn });
  } finally {
    waiting.remove();
  }
  for (const block of reply.blocks) await (render[block.type] || render.text)(block);
  if (reply.blocks.some(block => block.type === "case")) await refreshCases(currentCase());
}

async function send(sentence, shown) {
  const text = sentence.trim();
  if (!text) return;
  bubble(shown || text, "me");
  status("");
  await exchange({ text });
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

async function sendVoice(bytes, name) {
  const waiting = bubble("Przepisuję notatkę głosową na komputerze kancelarii…", "them wait");
  let result;
  try {
    result = await call("voice", "POST", { audio_b64: encode(bytes), name, case: currentCase() });
  } finally {
    waiting.remove();
  }
  bubble(result.text ? "Notatka głosowa:\n\n" + result.text : result.detail, "them");
  render.documents({ items: result.documents });
  status(result.text ? "Zapisałem nagranie i tekst" + (currentCase() ? " w sprawie „" + currentCase() + "”." : ".") : result.detail);
}

el("voice").onclick = run(async () => {
  if (voice) {                       // second tap: stop and send
    const finished = voice;
    voice = null;
    await finished.stop();
    return;
  }
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch {
    throw new Error("Brak dostępu do mikrofonu. Zezwól na niego w ustawieniach przeglądarki.");
  }
  const chunks = [];
  const recorder = new MediaRecorder(stream, { audioBitsPerSecond: 32000 });
  recorder.ondataavailable = event => { if (event.data.size) chunks.push(event.data); };
  const limit = setTimeout(() => el("voice").click(), 10 * 60 * 1000);
  const done = new Promise(resolve => { recorder.onstop = resolve; });
  voice = {
    stop: async () => {
      clearTimeout(limit);
      recorder.stop();
      await done;
      stream.getTracks().forEach(track => track.stop());
      el("voice").textContent = "🎤";
      el("voice").classList.remove("recording");
      el("voice").setAttribute("aria-label", "Nagraj notatkę głosową");
      const audio = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
      const extension = /ogg/.test(audio.type) ? ".ogg" : /mp4|aac/.test(audio.type) ? ".m4a" : ".webm";
      bubble("🎤 Notatka głosowa (" + Math.max(1, Math.round(audio.size / 4000)) + " s)", "me");
      await sendVoice(new Uint8Array(await audio.arrayBuffer()), "notatka" + extension);
    },
  };
  recorder.start(1000);
  el("voice").textContent = "■";
  el("voice").classList.add("recording");
  el("voice").setAttribute("aria-label", "Zakończ i zapisz notatkę głosową");
  el("voice").disabled = false;
  status("Nagrywam notatkę. Dotknij ■, żeby zakończyć.");
});

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
  el("case").replaceChildren(...options);
  if (keep) el("case").value = keep;
  el("mode").textContent = state.mode === "synthetic-only"
    ? "Tryb próbny. Używaj wyłącznie fikcyjnych dokumentów."
    : "Dokumenty są przechowywane na komputerze kancelarii.";
}

async function enter(device) {
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
  el("voice").hidden = scope === "read" || !(navigator.mediaDevices && window.MediaRecorder);
  el("messages").replaceChildren();
  chips();
  status(admin ? "Panel otwarty." : (scope === "write" ? "Połączono z prawem zapisu." : "Połączono w trybie odczytu."));
  await refreshCases();
  layout = await call("layout");
  drawTiles();
  await refreshRules();
  await exchange({ hello: true });
}

function leave(message) {
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
    throw new Error(admin ? "Kod panelu jest nieważny. Otwórz panel ponownie z menu Start." : "Kod parowania jest nieważny albo wygasł.");
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
  if (admin) {
    // The launcher opens this page with a one-time code in the fragment, which never reaches a server log.
    if (fragment.length > 1) await unlock(fragment.slice(1));
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
el("file").onchange = run(() => saveFile("file", null));
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
