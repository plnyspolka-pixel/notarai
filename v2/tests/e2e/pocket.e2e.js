// Browser check of Pocket and the workstation panel against a real worker with a fake model.
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
  await page.waitForFunction(expected => document.getElementById("status").textContent.includes(expected), text, { timeout: 10000 })
    .catch(async () => { throw new Error(`status "${await page.textContent("#status")}" lacks "${text}"`); });
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
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, acceptDownloads: true });
    const page = await context.newPage();
    page.on("console", message => { if (message.type() === "error") problems.push(message.text()); });
    page.on("pageerror", error => problems.push(String(error)));
    page.on("dialog", dialog => dialog.accept());

    // ---- Pocket: pair, create a case, add a source document
    await page.goto(info.url + "/pocket");
    await page.getByLabel("Kod parowania").fill(info.write);
    await page.getByRole("button", { name: "Połącz" }).click();
    await statusIs(page, "Połączono z prawem zapisu.");
    await page.locator(".notice", { hasText: "kodu odzyskiwania" }).waitFor();
    await page.getByLabel("Nowa sprawa").fill("sprawa-1");
    await page.getByRole("button", { name: "Dodaj sprawę" }).click();
    await page.getByRole("button", { name: "Nowy dokument tekstowy" }).click();
    await page.getByLabel("Nazwa dokumentu tekstowego").fill("notatka.txt");
    await page.getByLabel("Treść", { exact: true }).fill("Sprzedający Jan Kowalski, PESEL 44051401359, zbywa lokal nr 5.");
    await page.getByRole("button", { name: "Zapisz nową wersję" }).click();
    await statusIs(page, "Zapisano wersję 1.");
    await page.getByRole("button", { name: "notatka.txt · wersja 1" }).waitFor();

    // ---- assistant: question, then a draft that is edited and approved
    await page.getByLabel("Strony i inne osoby").fill("Jan Kowalski");
    await page.getByLabel("Pytanie albo polecenie").fill("Kto sprzedaje?");
    await page.getByRole("button", { name: "Zapytaj" }).click();
    await page.locator("#answer", { hasText: "Sprzedającym jest Jan Kowalski." }).waitFor();
    await page.getByLabel("Pytanie albo polecenie").fill("Przygotuj umowę sprzedaży.");
    await page.getByRole("button", { name: "Przygotuj projekt" }).click();
    await statusIs(page, "Nic nie zostało jeszcze zapisane.");
    const draft = await page.getByLabel("Treść projektu").inputValue();
    assert(draft.includes("Jan Kowalski, PESEL 44051401359, sprzedaje lokal."), "placeholders not restored: " + draft);
    assert(!draft.includes("WYCIEK"), "personal data reached the model");
    assert(await page.locator("#proposal-notes .notice", { hasText: "Miejsca do uzupełnienia: 1" }).count() === 1, "gap warning");
    await page.getByLabel("Treść projektu").fill(draft.replace("[DO UZUPEŁNIENIA: cena]", "500 000 zł"));
    await page.getByLabel("Nazwa pliku").fill("umowa.docx");
    if (shots) await page.screenshot({ path: path.join(shots, "pocket-projekt.png"), fullPage: true });
    await page.getByRole("button", { name: "Zatwierdzam i zapisuję" }).click();
    await statusIs(page, "potwierdzono odczytem kontrolnym");
    await page.getByRole("button", { name: "umowa.docx · wersja 1" }).click();
    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: "Pobierz otwartą wersję" }).click();
    const file = await (await download).path();
    assert(fs.readFileSync(file).subarray(0, 2).toString() === "PK", "downloaded file is not a DOCX package");

    // ---- fee calculator
    await page.getByLabel("Wartość (zł)").fill("500 000");
    await page.getByRole("button", { name: "Policz" }).click();
    await page.locator("#fee-result", { hasText: "RAZEM" }).waitFor();

    // ---- conflict: a second session saves first
    const other = await context.newPage();
    other.on("dialog", dialog => dialog.accept());
    await other.goto(info.url + "/pocket");
    await other.getByLabel("Kod parowania").fill(info.read);
    await other.getByRole("button", { name: "Połącz" }).click();
    await statusIs(other, "Połączono w trybie odczytu.");
    await other.locator("#docs li").first().waitFor();
    await other.locator("#fee-kind option").first().waitFor({ state: "attached" });
    assert(await other.getByRole("button", { name: "Nowy dokument tekstowy" }).isHidden(), "reader can write");
    assert(await other.getByRole("button", { name: "Przygotuj projekt" }).isHidden(), "reader can draft");
    assert(await other.locator("#case option").count() === 1, "case-limited device sees other cases");
    await other.close();

    // ---- workstation panel
    const admin = await browser.newContext({ viewport: { width: 1100, height: 900 } });
    const panel = await admin.newPage();
    panel.on("console", message => { if (message.type() === "error") problems.push(message.text()); });
    panel.on("pageerror", error => problems.push(String(error)));
    panel.on("dialog", dialog => dialog.accept());
    await panel.goto(info.url + "/admin#" + info.admin);
    await statusIs(panel, "Panel otwarty.");
    assert(!panel.url().includes("#"), "one-time code left in the address bar");
    await panel.getByRole("button", { name: "Utwórz kod odzyskiwania" }).click();
    await statusIs(panel, "Kod utworzony.");
    const code = await panel.textContent("#recovery-code");
    assert(/^([A-Z2-7]{4}-){13}[A-Z2-7]{4}$/.test(code), "recovery code format: " + code);
    if (shots) await panel.screenshot({ path: path.join(shots, "panel.png"), fullPage: true });
    await panel.getByRole("button", { name: "Kod jest bezpiecznie zapisany" }).click();
    assert(await panel.textContent("#recovery-code") === "", "code still in the page");
    await panel.getByLabel("Katalog kopii").fill(info.backups);
    await panel.getByRole("button", { name: "Zapisz katalog" }).click();
    await statusIs(panel, "Katalog kopii zapisany.");
    await panel.getByRole("button", { name: "Zrób kopię teraz" }).click();
    await statusIs(panel, "Kopia zapisana:");
    assert(fs.readdirSync(info.backups).some(name => name.endsWith(".notarai-backup")), "no backup file");
    await panel.locator("#devices tr", { hasText: "telefon" }).getByRole("button", { name: "Cofnij dostęp" }).click();
    await statusIs(panel, "Dostęp cofnięty.");
    await panel.locator("#audit tr", { hasText: "kopia zapasowa" }).first().waitFor();
    await panel.locator("#usage tr", { hasText: "draft" }).waitFor();
    await panel.getByLabel("Nowe urządzenie – nazwa").fill("Laptop");
    await panel.getByRole("button", { name: "Wydaj kod parowania" }).click();
    await panel.locator("#pair-code:not([hidden])").waitFor();

    // ---- remote access: enable the tunnel, pair a phone from the QR link, reconnect by device key
    await panel.getByLabel("Adres przekaźnika").fill("ws://127.0.0.1:" + relayPort);
    await panel.getByLabel("Adres strony Pocket").fill(info.url + "/pocket");
    await panel.getByLabel("Zezwól na dostęp spoza kancelarii").check();
    await panel.locator("#save-tunnel").click();
    await statusIs(panel, "Dostęp spoza kancelarii włączony.");
    await panel.locator("#tunnel-state", { hasText: "Połączono z przekaźnikiem." }).waitFor();
    await panel.getByLabel("Nowe urządzenie – nazwa").fill("Telefon zdalny");
    await panel.getByLabel("Dostęp", { exact: true }).selectOption("write");
    await panel.getByRole("button", { name: "Wydaj kod parowania" }).click();
    await panel.locator("#remote-pair:not([hidden])").waitFor();
    const link = await panel.locator("#pair-qr").getAttribute("data-link");
    assert(link.includes("#r=ws") && link.includes("&c="), "pairing link: " + link);
    if (shots) await panel.locator("#remote-pair").screenshot({ path: path.join(shots, "qr.png") });

    const phone = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const remote = await phone.newPage();
    remote.on("console", message => { if (message.type() === "error") problems.push("remote: " + message.text()); });
    remote.on("pageerror", error => problems.push("remote: " + String(error)));
    remote.on("dialog", dialog => dialog.accept());
    const api = [];
    remote.on("request", request => { if (/\/v2\/(documents|cases|status|drafts|taksa)/.test(request.url())) api.push(request.url()); });
    await remote.goto(link);
    await statusIs(remote, "Urządzenie sparowane.");
    assert(!remote.url().includes("#"), "pairing link left in the address bar");
    await remote.getByRole("button", { name: "umowa.docx · wersja 1" }).waitFor();
    await remote.reload();
    await statusIs(remote, "Połączono z prawem zapisu.");
    await remote.getByRole("button", { name: "notatka.txt · wersja 1" }).click();
    await remote.waitForFunction(() => document.getElementById("body").value.includes("Jan Kowalski"));
    await remote.getByLabel("Treść", { exact: true }).fill("Zmiana z telefonu poza kancelarią.");
    await remote.getByRole("button", { name: "Zapisz nową wersję" }).click();
    await statusIs(remote, "Zapisano wersję 2.");
    assert(api.length === 0, "remote Pocket bypassed the tunnel: " + api.join(", "));
    await panel.getByRole("button", { name: "Odśwież dziennik" }).click();
    await panel.locator("#audit tr", { hasText: "Telefon zdalny" }).first().waitFor();
    await panel.locator("#devices tr", { hasText: "Telefon zdalny" }).getByRole("button", { name: "Cofnij dostęp" }).click();
    await statusIs(panel, "Dostęp cofnięty.");
    await remote.getByRole("button", { name: "Odśwież listę" }).click();
    await statusIs(remote, "dostęp został cofnięty");
    await remote.reload();
    await statusIs(remote, "Kancelaria odrzuciła połączenie.");

    // ---- the revoked phone is cut off
    await page.getByRole("button", { name: "Odśwież listę" }).click();
    await statusIs(page, "dostęp został cofnięty");

    // ---- used panel code cannot be replayed
    const replay = await admin.newPage();
    replay.on("dialog", dialog => dialog.accept());
    await replay.goto(info.url + "/admin#" + info.admin);
    await statusIs(replay, "Kod panelu jest nieważny.");

    const expected = problems.filter(text => !/401|403|409/.test(text));
    assert(expected.length === 0, "browser errors: " + expected.join(" | "));
    console.log("E2E OK: pairing, case, draft with approval, fee, limited device, panel, backup, revocation, remote tunnel.");
  } finally {
    await browser.close();
    server.kill();
    relay.kill();
  }
})().catch(error => { console.error(error.message || error); process.exit(1); });
