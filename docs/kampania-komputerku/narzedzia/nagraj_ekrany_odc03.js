// Prawdziwe ekrany NotarAI do odc. 03 „U nas się tak nie pisze” (Bedrock eu-central-1; atrapa EKW; dane demo).
// Kuba pobiera księgę z EKW (bez zrzutu, stan jak po odc. 01), Marta sporządza projekt v1, potem w „Poprawkach do projektu”
// wpisuje poprawkę § 5 i klika „Popraw i sporządź ponownie” -> projekt v2 z raportem zgodności. Na końcu „Styl i zasady kancelarii”.
// Użycie: node nagraj_ekrany_odc03.js <adres> <katalog_wyjscia>
const fs = require('fs'), path = require('path'), { chromium } = require('playwright');
const [ADRES, OUT] = process.argv.slice(2); fs.mkdirSync(OUT, { recursive: true });
const HASLO = 'Demo-Odc01!', SPRAWA = 'e01demo00001', DOM = 'kancelaria-demo.test', KW = 'WA4M/00077777/2';
const POPRAWKA = '§ 5: wydanie lokalu 15 stycznia 2027 r. na podstawie protokołu zdawczo-odbiorczego; do tego dnia sprzedająca opróżni lokal. '
  + 'Termin potwierdziła sprzedająca osobiście 17.11, kupujący jeszcze nie — oznacz do potwierdzenia przez kupujących. Własność przechodzi z chwilą zawarcia aktu.';
const STANY = [];
async function stan(s, nazwa, sel) {
  await s.screenshot({ path: path.join(OUT, nazwa + '.png') });
  let ramka = null; if (sel) { const l = typeof sel === 'string' ? s.locator(sel).first() : sel; ramka = await l.boundingBox().catch(() => null); }
  STANY.push({ nazwa, plik: nazwa + '.png', viewport: s.viewportSize(), ramka }); fs.writeFileSync(path.join(OUT, 'stany.json'), JSON.stringify(STANY, null, 1));
}
async function zaloguj(prz, kto, hash) {
  const s = await (await prz.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, acceptDownloads: true })).newPage();
  s.on('dialog', (d) => d.accept());
  await s.goto(ADRES + '/' + (hash || ''));
  await s.fill('#pole-email', `${kto}@${DOM}`); await s.fill('#pole-haslo', HASLO); await s.click('#btn-zaloguj');
  await s.waitForSelector('#brama', { state: 'hidden' }); await s.waitForTimeout(1200); return s;
}
(async () => {
  const prz = await chromium.launch();
  // Kuba: księga z EKW (jak w odc. 01)
  if (!process.env.DALEJ) {
    const k = await zaloguj(prz, 'kuba', '#sprawa=' + SPRAWA);
    await k.click('.krok[data-etap="4"]'); await k.waitForSelector('#ekw-karta:not([hidden])');
    await k.fill('#ekw-numer', KW); await k.click('#btn-ekw'); await k.waitForSelector('#ekw-lista .ekw-ksiega', { timeout: 120000 });
  }
  // Marta: projekt v1
  const m = await zaloguj(prz, 'marta', '#sprawa=' + SPRAWA);
  // projekt v1: gdy już sporządzony (DALEJ), aplikacja otwiera od razu etap 3; inaczej generujemy i czekamy na etap 3 albo powiadomienie
  if (!process.env.DALEJ) {
    await m.waitForSelector('#etap2:not([hidden])'); await m.locator('#btn-generuj').scrollIntoViewIfNeeded(); await m.click('#btn-generuj');
    await m.waitForFunction(() => !document.querySelector('#etap3').hidden || !document.querySelector('#powiadomienie').hidden, null, { timeout: 30 * 60000 });
    if (await m.isVisible('#powiadomienie [data-akcja]')) await m.click('#powiadomienie [data-akcja]');
  }
  await m.waitForSelector('#etap3:not([hidden])', { timeout: 60000 });
  await m.waitForFunction(() => document.querySelector('#projekt') && document.querySelector('#projekt').innerText.length > 200, null, { timeout: 60000 });
  await m.waitForTimeout(1500);
  fs.writeFileSync(path.join(OUT, 'projekt_v1.txt'), await m.innerText('#projekt'));
  await m.locator('#projekt').scrollIntoViewIfNeeded(); await stan(m, 'P1_projekt_v1', '#projekt');
  if (process.env.TYLKO_V2) return await koncowka(prz, m, Date.now());
  // Marta: poprawka § 5
  await m.locator('#msg3').scrollIntoViewIfNeeded(); await m.click('#msg3');
  await m.keyboard.type(POPRAWKA, { delay: 12 }); await stan(m, 'P2_poprawka', '#msg3');
  const t0 = Date.now(); await m.click('#send3'); await m.waitForTimeout(1500); await stan(m, 'P3_sporzadzam_ponownie', '#send3');
  // po ponownym sporządzeniu aplikacja zgłasza gotowość powiadomieniem (tekst #projekt nie podmienia się sam)
  await m.waitForFunction((stary) => (document.querySelector('#projekt') && document.querySelector('#projekt').innerText !== stary)
    || !document.querySelector('#powiadomienie').hidden, fs.readFileSync(path.join(OUT, 'projekt_v1.txt'), 'utf8'), { timeout: 30 * 60000 });
  if (await m.isVisible('#powiadomienie [data-akcja]')) { await stan(m, 'P3b_powiadomienie', '#powiadomienie'); await m.click('#powiadomienie [data-akcja]'); }
  await koncowka(prz, m, t0);
})().catch((e) => { console.error(e); process.exit(1); });
async function koncowka(prz, m, t0) {
  await m.waitForTimeout(3000);
  if (!process.env.TYLKO_V2) fs.writeFileSync(path.join(OUT, 'czas_v2.txt'), ((Date.now() - t0) / 1000).toFixed(1) + ' s\n');
  fs.writeFileSync(path.join(OUT, 'projekt_v2.txt'), await m.innerText('#projekt'));
  await m.locator('#projekt').scrollIntoViewIfNeeded(); await stan(m, 'P4_projekt_v2', '#projekt');
  const p5 = m.locator('#projekt', { hasText: '§ 5' });
  const z = m.locator('.zgodnosc, #zgodnosc, [id*="zgodn"]').first(); if (await z.count()) { await z.scrollIntoViewIfNeeded(); await stan(m, 'P5_zgodnosc', z); }
  // Styl i zasady kancelarii
  const h = await zaloguj(prz, 'helena');
  await h.click('.krok[data-etap="9"]'); await h.waitForTimeout(2000); await stan(h, 'Z1_styl_i_zasady', null);
  fs.writeFileSync(path.join(OUT, 'zasady.txt'), await h.innerText('body'));
  console.log('gotowe', STANY.map((x) => x.nazwa).join(', '));
  await prz.close();
}
