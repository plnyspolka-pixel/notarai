// Browser check of the chat UI (Pocket and the workstation panel) against a real worker with a fake model.
// Run: node tests/e2e/pocket.e2e.js [python]   (from v2/)
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const python = process.argv[2] || "python3";
const shots = process.env.NOTARAI_E2E_SHOTS;

function assert(condition, message) {
  if (!condition) throw new Error("ASSERT: " + message);
}

async function statusIs(page, text) {
  await page.waitForFunction(expected => document.getElementById("status").textContent.includes(expected), text, { timeout: 15000 })
    .catch(async () => { throw new Error(`status "${await page.textContent("#status")}" lacks "${text}"`); });
}

// Type a sentence the way a notary would and wait for an answer containing `expected`.
async function say(page, sentence, expected) {
  const before = await page.locator("#messages .bubble.them").count();
  await page.getByLabel("Napisz polecenie albo pytanie").fill(sentence);
  await page.getByLabel("Napisz polecenie albo pytanie").press("Enter");
  if (expected) await answered(page, expected, before);
}

async function answered(page, expected, from = 0) {
  await page.waitForFunction(([text, start]) =>
    [...document.querySelectorAll("#messages .bubble.them, #messages .card.them")].slice(start).some(n => n.textContent.includes(text)),
    [expected, from], { timeout: 15000 })
    .catch(async () => { throw new Error(`no answer with "${expected}"; last: ${(await page.locator("#messages > *").allTextContents()).slice(-4).join(" | ")}`); });
}

function watch(page, problems, label) {
  page.on("console", message => { if (message.type() === "error") problems.push(label + message.text()); });
  page.on("pageerror", error => problems.push(label + String(error)));
  page.on("dialog", dialog => dialog.accept());
}

(async () => {
  const server = spawn(python, [path.join(__dirname, "serve.py")], { stdio: ["ignore", "pipe", "inherit"] });
  const info = await new Promise((resolve, reject) => {
    server.stdout.once("data", chunk => resolve(JSON.parse(chunk.toString().split("\n")[0])));
    server.once("exit", code => reject(new Error("server exited " + code)));
  });
  const relay = spawn(python, [path.join(__dirname, "relay_serve.py")], { stdio: ["ignore", "pipe", "inherit"] });
  const relayPort = await new Promise(resolve => relay.stdout.once("data", chunk => resolve(chunk.toString().trim())));
  const browser = await chromium.launch();
  const problems = [];
  try {
    // ---- Pocket on the office computer: pair, then do everything by talking
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, acceptDownloads: true });
    const page = await context.newPage();
    watch(page, problems, "pocket: ");
    await page.goto(info.url + "/pocket");
    await page.getByLabel("Kod parowania").fill(info.write);
    await page.getByRole("button", { name: "Połącz" }).click();
    await statusIs(page, "Połączono z prawem zapisu.");
    await answered(page, "sejf nie ma kodu odzyskiwania");
    assert(await page.locator("table").count() === 0, "tables in the chat UI");

    await say(page, "nowa sprawa sprawa-1", "Sprawa „sprawa-1”");
    assert(await page.locator("#case").inputValue() === "sprawa-1", "case not selected");
    await say(page, "notatka: Sprzedający Jan Kowalski, PESEL 44051401359, zbywa lokal nr 5.", "Zapisałem notatkę");
    await say(page, "strony: Jan Kowalski", "Zapamiętałem");
    await say(page, "Kto sprzedaje?", "Sprzedającym jest Jan Kowalski.");
    await say(page, "Przygotuj umowę sprzedaży lokalu", "Projekt gotowy");
    const draft = await page.getByLabel("Treść projektu").inputValue();
    assert(draft.includes("Jan Kowalski, PESEL 44051401359, sprzedaje lokal."), "placeholders not restored: " + draft);
    assert(!draft.includes("WYCIEK"), "personal data reached the model");
    await page.locator(".notice", { hasText: "Miejsca do uzupełnienia: 1" }).waitFor();
    await page.getByLabel("Treść projektu").fill(draft.replace("[DO UZUPEŁNIENIA: cena]", "500 000 zł"));
    await page.getByLabel("Nazwa pliku").fill("umowa.docx");
    if (shots) await page.screenshot({ path: path.join(shots, "pocket-czat.png"), fullPage: true });
    await page.getByRole("button", { name: "Zatwierdzam i zapisuję" }).click();
    await statusIs(page, "potwierdzono odczytem kontrolnym");
    await page.getByRole("button", { name: "umowa.docx · wersja 1" }).last().click();
    await statusIs(page, "Otwarto wersję 1.");
    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: "Pobierz otwartą wersję" }).click();
    assert(fs.readFileSync(await (await download).path()).subarray(0, 2).toString() === "PK", "not a DOCX package");
    await page.getByRole("button", { name: "Zamknij" }).click();

    await say(page, "policz taksę od sprzedaży lokalu mieszkalnego za 500 tys.", "RAZEM");
    await page.getByRole("button", { name: "Taksa", exact: true }).click();
    await answered(page, "Podaj wartość");

    // The classic text note still works from a suggestion chip.
    await page.getByRole("button", { name: "Nowy dokument tekstowy" }).click();
    await page.getByLabel("Nazwa dokumentu tekstowego").fill("uwagi.txt");
    await page.getByLabel("Treść", { exact: true }).fill("Uwagi do sprawy.");
    await page.getByRole("button", { name: "Zapisz nową wersję" }).click();
    await statusIs(page, "Zapisano wersję 1.");
    await page.getByRole("button", { name: "Zamknij" }).click();

    // ---- a read-only device limited to one case
    const other = await context.newPage();
    watch(other, problems, "reader: ");
    await other.goto(info.url + "/pocket");
    await other.getByLabel("Kod parowania").fill(info.read);
    await other.getByRole("button", { name: "Połącz" }).click();
    await statusIs(other, "Połączono w trybie odczytu.");
    await other.getByRole("button", { name: "umowa.docx · wersja 1" }).waitFor();
    assert(await other.getByRole("button", { name: "Nowy dokument tekstowy" }).count() === 0, "reader can write");
    assert(await other.locator("#attach").isHidden(), "reader can attach");
    assert(await other.locator("#case option").count() === 1, "case-limited device sees other cases");
    await say(other, "przygotuj umowę", "tylko do odczytu");
    await say(other, "kod odzyskiwania", "");
    await other.waitForTimeout(500);
    assert(await other.locator(".code").count() === 0, "a device obtained a recovery code");
    await other.close();

    // ---- the workstation panel, also by talking
    const desk = await browser.newContext({ viewport: { width: 1000, height: 900 } });
    const panel = await desk.newPage();
    watch(panel, problems, "panel: ");
    await panel.goto(info.url + "/admin#" + info.admin);
    await statusIs(panel, "Panel otwarty.");
    assert(!panel.url().includes("#"), "one-time code left in the address bar");
    await panel.getByRole("button", { name: "Utwórz kod odzyskiwania" }).click();
    await answered(panel, "Kod odzyskiwania sejfu NotarAI");
    const code = await panel.locator(".code").textContent();
    assert(/^([A-Z2-7]{4}-){13}[A-Z2-7]{4}$/.test(code), "recovery code format: " + code);
    await panel.getByRole("button", { name: "Kod jest bezpiecznie zapisany" }).click();
    assert(await panel.locator(".code").count() === 0, "code still on the page");
    await say(panel, "katalog kopii " + info.backups, "Kopie będą trafiać");
    await panel.getByRole("button", { name: "Zrób kopię", exact: true }).last().click();
    await answered(panel, "Kopia zapisana na dysku");
    assert(fs.readdirSync(info.backups).some(name => name.endsWith(".notarai-backup")), "no backup file");

    await say(panel, "otwórz notatka w Wordzie", "w edytorze");
    const copies = path.join(info.home, "workcopies");
    const folder = path.join(copies, fs.readdirSync(copies)[0]);
    const working = fs.readdirSync(folder).find(name => name.endsWith(".txt"));
    fs.writeFileSync(path.join(folder, working), "Sprzedający Jan Kowalski, PESEL 44051401359, zbywa lokal nr 5. Dopisek z edytora.");
    await say(panel, "otwarte", "zmieniony, niezapisany w sejfie");
    await say(panel, "zapisz do sejfu", "jako wersję 2");
    assert(fs.readdirSync(copies).length === 0, "working copy left on disk");

    // ---- remote access: a phone pairs from the QR link and reconnects with its key
    await panel.evaluate(async ([relayUrl, pocketUrl]) => {
      // Addresses come with the installation; here the test supplies local ones through the same API.
      const headers = { Authorization: "Bearer " + token, "Content-Type": "application/json" };
      const current = await (await fetch("/v2/settings", { headers })).json();
      await fetch("/v2/settings", { method: "PUT", headers, body: JSON.stringify(
        { ...current, tunnel: { enabled: false, relay_url: relayUrl, pocket_url: pocketUrl } }) });
    }, ["ws://127.0.0.1:" + relayPort, info.url + "/pocket"]);
    await say(panel, "włącz dostęp spoza kancelarii", "Dostęp spoza kancelarii włączony");
    await say(panel, "stan", "połączony z przekaźnikiem");
    await say(panel, "dodaj telefon o nazwie Telefon zdalny", "Urządzenie „Telefon zdalny” (odczyt i zapis, wszystkie sprawy)");
    const link = await panel.locator("canvas").last().getAttribute("data-link");
    assert(link.includes("#r=ws") && link.includes("&c="), "pairing link: " + link);
    if (shots) await panel.screenshot({ path: path.join(shots, "panel-czat.png"), fullPage: true });

    const phone = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const remote = await phone.newPage();
    watch(remote, problems, "remote: ");
    const api = [];
    remote.on("request", request => { if (/\/v2\/(documents|cases|status|drafts|taksa|chat)/.test(request.url())) api.push(request.url()); });
    await remote.goto(link);
    await statusIs(remote, "Urządzenie sparowane.");
    assert(!remote.url().includes("#"), "pairing link left in the address bar");
    await remote.getByRole("button", { name: "umowa.docx · wersja 1" }).first().waitFor();
    await remote.reload();
    await statusIs(remote, "Połączono z prawem zapisu.");
    await say(remote, "sprawa sprawa-1", "Sprawa „sprawa-1”");
    await say(remote, "Kto sprzedaje?", "Sprzedającym jest");
    await say(remote, "notatka: Dopisek z telefonu poza kancelarią.", "Zapisałem notatkę");
    assert(api.length === 0, "remote Pocket bypassed the tunnel: " + api.join(", "));

    await say(panel, "kto czytał?", "Telefon zdalny");
    assert(!(await panel.locator("#messages").textContent()).includes("kontrola po zapisie"), "internal read shown in the journal");
    await say(panel, "cofnij telefon zdalny", "Cofnąć dostęp urządzenia „Telefon zdalny”?");
    await panel.getByRole("button", { name: "Tak, cofnij dostęp" }).click();
    await answered(panel, "Cofnąłem dostęp");
    await say(remote, "dokumenty", "");
    await statusIs(remote, "dostęp został cofnięty");
    await remote.reload();
    await statusIs(remote, "Kancelaria odrzuciła połączenie.");

    // ---- used panel code cannot be replayed
    const replay = await desk.newPage();
    replay.on("dialog", dialog => dialog.accept());
    await replay.goto(info.url + "/admin#" + info.admin);
    await statusIs(replay, "Kod panelu jest nieważny.");

    const unexpected = problems.filter(text => !/401|403|409/.test(text));
    assert(unexpected.length === 0, "browser errors: " + unexpected.join(" | "));
    console.log("E2E OK: chat in Pocket and panel; draft with approval, fee, limited device, recovery code, backup, editing, remote tunnel, revocation.");
  } finally {
    await browser.close();
    server.kill();
    relay.kill();
  }
})().catch(error => { console.error(error.message || error); process.exit(1); });
