// Prawdziwe ekrany NotarAI do odc. 01, sceny 06–10, z PRAWDZIWYM modelem (Bedrock eu-central-1, bez atrapy).
// Marta: Weryfikacja odczytu -> „Wymagają uwagi” -> „Sporządź projekt” -> praca w kalendarzu -> powiadomienie
// -> „Projekt dokumentu” ze znacznikami -> „Pobierz jako Word”. Zapisuje zrzuty stanów, ramki i czas projektu.
// Użycie: node nagraj_ekrany_odc01_cz3.js <adres> <katalog_wyjscia>
const fs = require('fs'), path = require('path'), { chromium } = require('playwright');
const [ADRES, OUT] = process.argv.slice(2); fs.mkdirSync(OUT, { recursive: true });
const HASLO = 'Demo-Odc01!', SPRAWA = 'e01demo00001';
const STANY = [];
async function stan(s, nazwa, sel) {
  const plik = nazwa + '.png'; await s.screenshot({ path: path.join(OUT, plik) });
  let ramka = null; if (sel) { const l = typeof sel === 'string' ? s.locator(sel).first() : sel; ramka = await l.boundingBox(); }
  STANY.push({ nazwa, plik, viewport: s.viewportSize(), ramka }); fs.writeFileSync(path.join(OUT, 'stany.json'), JSON.stringify(STANY, null, 1));
}
(async () => {
  const prz = await chromium.launch();
  const kont = await prz.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, acceptDownloads: true });
  const s = await kont.newPage(); s.on('dialog', (d) => d.accept());
  await s.goto(ADRES + '/#sprawa=' + SPRAWA);
  await s.fill('#pole-email', 'marta@kancelaria-demo.test'); await s.fill('#pole-haslo', HASLO); await s.click('#btn-zaloguj');
  await s.waitForSelector('#brama', { state: 'hidden' }); await s.waitForSelector('#etap2:not([hidden])'); await s.waitForTimeout(800);
  await s.locator('#etap2 h2, #etap2 h1').first().scrollIntoViewIfNeeded().catch(() => {});
  await stan(s, 'W1_weryfikacja', '#etap2 .chip[data-f="uwaga"]');
  await s.click('#etap2 .chip[data-f="uwaga"]'); await s.waitForTimeout(600); await s.locator('#pola').scrollIntoViewIfNeeded();
  await stan(s, 'W2_wymagaja_uwagi', '#pola .wiersz:visible');
  await s.locator('#btn-generuj').scrollIntoViewIfNeeded(); await stan(s, 'W3_przed_sporzadz', '#btn-generuj');
  const t0 = Date.now(); await s.click('#btn-generuj');
  await s.locator('#stan2', { hasText: 'Sporządzam projekt' }).waitFor(); await s.waitForTimeout(1500);
  await stan(s, 'W4_sporzadzam', '#stan2');
  await s.click('.krok[data-etap="6"]'); await s.waitForTimeout(1500); await stan(s, 'W5_kalendarz_w_trakcie', null);
  await s.waitForSelector('#powiadomienie:not([hidden])', { timeout: 30 * 60000 });
  const czas = (Date.now() - t0) / 1000; fs.writeFileSync(path.join(OUT, 'czas_projektu.txt'), `${czas.toFixed(1)} s\n`);
  await s.waitForTimeout(500); await stan(s, 'W6_powiadomienie', '#powiadomienie');
  await s.click('#powiadomienie [data-akcja]'); await s.waitForSelector('#etap3:not([hidden])'); await s.waitForTimeout(1200);
  await stan(s, 'W7_projekt', '#projekt');
  const brak = s.locator('#projekt mark.brak').first(); if (await brak.count()) { await brak.scrollIntoViewIfNeeded(); await s.waitForTimeout(400); await stan(s, 'W8_projekt_brak', brak); }
  const wyb = s.locator('#projekt mark.wybor').first(); if (await wyb.count()) { await wyb.scrollIntoViewIfNeeded(); await s.waitForTimeout(400); await stan(s, 'W9_projekt_wybor', wyb); }
  fs.writeFileSync(path.join(OUT, 'projekt_tekst.txt'), await s.innerText('#projekt'));
  await s.locator('#btn-pobierz').scrollIntoViewIfNeeded(); await stan(s, 'W10_pobierz_word', '#btn-pobierz');
  const [pob] = await Promise.all([s.waitForEvent('download'), s.click('#btn-pobierz')]);
  await pob.saveAs(path.join(OUT, 'projekt_NOWAK_KACZMAREK_v1.docx'));
  console.log('czas projektu', czas.toFixed(1), 's; braki', await s.locator('#projekt mark.brak').count(), '; wybory', await s.locator('#projekt mark.wybor').count());
  await prz.close();
})().catch((e) => { console.error(e); process.exit(1); });
