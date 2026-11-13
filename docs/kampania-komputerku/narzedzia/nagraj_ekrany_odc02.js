// Prawdziwe ekrany NotarAI do odc. 02, sc. 03–04 (Bedrock eu-central-1; skrzynka testowa .eml, bez IMAP).
// Kuba: „Poczta do przypisania” -> 3 maile z propozycją sprawy -> „Przypisz do sprawy” -> ustalenia ze źródłem.
// Sprawa: „Korespondencja sprawy” (role nadawców, ustalenia, cytaty) i komunikat przy polu terminu wydania w „Weryfikacji odczytu”.
// Marta: wpis w „Rozmowie o sprawie” (potwierdzenie Ireny) + odpowiedź asystenta. Basia: kalendarz z terminem 17.11 11:30.
// Użycie: node nagraj_ekrany_odc02.js <adres> <katalog_wyjscia>
const fs = require('fs'), path = require('path'), { chromium } = require('playwright');
const [ADRES, OUT] = process.argv.slice(2); fs.mkdirSync(OUT, { recursive: true });
const HASLO = 'Demo-Odc01!', SPRAWA = 'e01demo00001', DOM = 'kancelaria-demo.test';
const STANY = fs.existsSync(path.join(OUT, 'stany.json')) ? JSON.parse(fs.readFileSync(path.join(OUT, 'stany.json'))) : [];
async function stan(s, nazwa, sel) {
  const plik = nazwa + '.png'; await s.screenshot({ path: path.join(OUT, plik) });
  let ramka = null; if (sel) { const l = typeof sel === 'string' ? s.locator(sel).first() : sel; ramka = await l.boundingBox().catch(() => null); }
  STANY.push({ nazwa, plik, viewport: s.viewportSize(), ramka }); fs.writeFileSync(path.join(OUT, 'stany.json'), JSON.stringify(STANY, null, 1));
}
async function zaloguj(prz, kto, hash) {
  const kont = await prz.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  const s = await kont.newPage(); s.on('dialog', (d) => d.accept());
  await s.goto(ADRES + '/' + (hash || ''));
  await s.fill('#pole-email', `${kto}@${DOM}`); await s.fill('#pole-haslo', HASLO); await s.click('#btn-zaloguj');
  await s.waitForSelector('#brama', { state: 'hidden' }); await s.waitForTimeout(1000);
  return s;
}
const czekajNaStan = (s, id) => s.waitForFunction((id) => !/…/.test(document.getElementById(id).textContent), id, { timeout: 240000 });
(async () => {
  const prz = await chromium.launch();
  // --- Kuba: poczta ---
  const k = await zaloguj(prz, 'kuba');
  await k.click('.krok[data-etap="12"]'); await k.waitForSelector('#etap12:not([hidden])');
  const sa = await k.waitForSelector('#skrzynka-lista .kor-el', { timeout: 20000 }).then(() => true).catch(() => false);
  await k.waitForTimeout(800);
  if (sa && !process.env.TYLKO_DALEJ) await stan(k, 'M1_poczta_do_przypisania', '#skrzynka-lista .propozycja');
  const n = sa && !process.env.TYLKO_DALEJ ? await k.locator('#skrzynka-lista .kor-el').count() : 0;
  for (let i = 0; i < n; i++) {
    const b = k.locator('#skrzynka-lista .propozycja button').first();
    if (i === 0) await stan(k, 'M2_przed_przypisaniem', b);
    await b.click(); await k.waitForTimeout(400);
    await czekajNaStan(k, 'stan12'); await k.waitForTimeout(600);
  }
  if (n) await stan(k, 'M3_przypisane', '#stan12');
  // --- Kuba: sprawa -> korespondencja i pole terminu wydania ---
  await k.goto(ADRES + '/#sprawa=' + SPRAWA); await k.waitForSelector('#etap2:not([hidden])'); await k.waitForTimeout(1500);
  await k.waitForFunction(() => document.querySelectorAll('#kor-lista .kor-ustalenia li').length >= 2, null, { timeout: 240000 }).catch(() => {});
  await k.locator('#korespondencja-sprawy').scrollIntoViewIfNeeded(); await k.waitForTimeout(600);
  if (!process.env.TYLKO_DALEJ) await stan(k, 'K1_korespondencja', '#kor-lista');
  const pawel = k.locator('#kor-lista .kor-el', { hasText: 'Paweł' }).first();
  if (!process.env.TYLKO_DALEJ && await pawel.count()) { await pawel.scrollIntoViewIfNeeded(); await k.waitForTimeout(400); await stan(k, 'K2_mail_pawla', pawel); }
  await k.click('#etap2 .chip[data-f="uwaga"]').catch(() => {}); await k.waitForTimeout(700);
  const kom = k.locator('#pola .komunikat.korespondencja:visible').first();
  if (await kom.count()) { await kom.scrollIntoViewIfNeeded(); await k.waitForTimeout(500); await stan(k, 'K3_pole_termin_wydania', kom); }
  fs.writeFileSync(path.join(OUT, 'korespondencja.txt'), await k.innerText('#korespondencja-sprawy'));
  // --- Marta: rozmowa o sprawie ---
  const m = await zaloguj(prz, 'marta', '#sprawa=' + SPRAWA);
  await m.waitForSelector('#etap2:not([hidden])'); await m.locator('#msg2').scrollIntoViewIfNeeded(); await m.click('#msg2');
  await m.keyboard.type('Sprzedająca osobiście (17.11, rozmowa z notariuszem): wydanie lokalu 15 stycznia 2027. Termin 1 grudnia nie był przez nią zaakceptowany.', { delay: 18 });
  await stan(m, 'R1_wpis_marty', '#msg2');
  await m.click('#send2'); await m.locator('#stan2c', { hasText: 'odpowiada' }).waitFor().catch(() => {});
  await m.waitForFunction(() => !/odpowiada/i.test(document.getElementById('stan2c').textContent) && !/^\s*…\s*$/.test((document.querySelector('#czat2 > *:last-child') || {}).innerText || '…'), null, { timeout: 240000 });
  await m.waitForTimeout(800); await m.locator('#czat2').scrollIntoViewIfNeeded();
  await stan(m, 'R2_odpowiedz', '#czat2 > *:last-child');
  fs.writeFileSync(path.join(OUT, 'rozmowa.txt'), await m.innerText('#czat2'));
  // --- Basia: kalendarz, termin 17.11 11:30 ---
  const b = await zaloguj(prz, 'basia');
  await b.click('.krok[data-etap="6"]'); await b.waitForTimeout(1500);
  await stan(b, 'C1_kalendarz', null);
  console.log('gotowe', STANY.map((x) => x.nazwa).join(', '));
  await prz.close();
})().catch((e) => { console.error(e); process.exit(1); });
