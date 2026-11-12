// Nagranie prawdziwych ekranów NotarAI do odc. 01, sceny 03–05 (dane demo zgodne z kanonem sezonu).
// Serwer demo z gałęzi kodu: scripts/demo_odcinek01.py przygotuj --dzien 2026-11-16, potem serwer --port 8765.
// Sztuczna kamera pokazuje fikcyjne zaświadczenie od zarządcy (D08) z pliku .y4m.
// Użycie: node nagraj_ekrany_odc01_cz2.js <adres> <plik_y4m> <katalog_wyjscia>
const fs = require('fs'), path = require('path'), { chromium } = require('playwright');
const [ADRES, Y4M, OUT] = process.argv.slice(2); fs.mkdirSync(OUT, { recursive: true });
const HASLO = 'Demo-Odc01!', SPRAWA = 'e01demo00001';
const CZAS = new Date('2026-11-16T09:00:40+01:00');
const BIURKO = { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, recordVideo: { size: { width: 1440, height: 900 } } };
const TELEFON = { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 3, recordVideo: { size: { width: 780, height: 1688 } } };
const zn = (n, t0) => fs.appendFileSync(path.join(OUT, 'znaczniki.txt'), `${n}\t${((Date.now() - t0) / 1000).toFixed(2)}\n`);
const czekaj = (s, ms) => s.waitForTimeout(ms);
const STANY = [];
async function stan(s, nazwa, sel) {
  const plik = nazwa + '.png'; await s.screenshot({ path: path.join(OUT, plik) });
  let ramka = null;
  if (sel) { const l = typeof sel === 'string' ? s.locator(sel).first() : sel; ramka = await l.boundingBox(); }
  STANY.push({ nazwa, plik, viewport: s.viewportSize(), ramka });
  fs.writeFileSync(path.join(OUT, 'stany.json'), JSON.stringify(STANY, null, 1));
}
async function strona(prz, opcje, nazwa, email, hasz = '') {
  const kont = await prz.newContext({ ...opcje, recordVideo: { ...opcje.recordVideo, dir: path.join(OUT, nazwa) } });
  const s = await kont.newPage();
  await s.clock.install({ time: CZAS });
  s.on('dialog', (d) => d.accept());
  await s.goto(ADRES + '/' + hasz);
  await s.fill('#pole-email', email); await s.fill('#pole-haslo', HASLO); await s.click('#btn-zaloguj');
  await s.waitForSelector('#brama', { state: 'hidden' });
  await s.clock.resume();
  return [kont, s, Date.now()];
}
(async () => {
  const prz = await chromium.launch({ args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', `--use-file-for-fake-video-capture=${Y4M}`] });
  // sc. 03: Basia - kalendarz -> termin wtorek 11:30 -> „Otwórz sprawę”
  let [kb, basia, t0] = await strona(prz, BIURKO, 'basia_kalendarz', 'basia@kancelaria-demo.test');
  zn('basia_start', t0);
  await basia.click('.krok[data-etap="6"]'); await czekaj(basia, 1200);
  const termin = basia.locator('#kal-najblizsze .termin', { hasText: '11:30' }); await termin.waitFor();
  await termin.scrollIntoViewIfNeeded(); await czekaj(basia, 300); zn('basia_termin', t0);
  await stan(basia, 'K1_kalendarz_termin', termin.getByRole('button', { name: 'Otwórz sprawę' }));
  await termin.hover(); await czekaj(basia, 2200);
  await termin.getByRole('button', { name: 'Otwórz sprawę' }).click(); zn('basia_otworz', t0);
  await basia.waitForSelector('#etap2:not([hidden])'); await czekaj(basia, 800); await stan(basia, 'K2_sprawa_otwarta', '#oznaczenie2'); await czekaj(basia, 1700); zn('basia_koniec', t0);
  await kb.close();
  // Marta ma sprawę otwartą na komputerze
  let [km, marta, tm] = await strona(prz, BIURKO, 'marta_pliki', 'marta@kancelaria-demo.test', '#sprawa=' + SPRAWA);
  await marta.waitForSelector('#etap2:not([hidden])'); await marta.locator('#pliki-sprawy').scrollIntoViewIfNeeded(); await czekaj(marta, 500); await stan(marta, 'M1_pliki_puste', '#pliki-sprawy');
  // sc. 04–05: Basia na telefonie - ta sama sprawa, „Aparatem”, zdjęcie, „Wyślij”
  let [kt, tel, t1] = await strona(prz, { ...TELEFON, permissions: ['camera'] }, 'basia_telefon', 'basia@kancelaria-demo.test', '#sprawa=' + SPRAWA);
  await tel.waitForSelector('#etap2:not([hidden])'); await czekaj(tel, 1800); zn('tel_sprawa', t1); await stan(tel, 'P1_sprawa_telefon', '#oznaczenie2');
  await tel.locator('#pliki-sprawy').scrollIntoViewIfNeeded(); await czekaj(tel, 1200); zn('tel_pliki', t1); await tel.locator('#btn-aparat').scrollIntoViewIfNeeded(); await stan(tel, 'P2_pliki_telefon', '#btn-aparat');
  await tel.click('#btn-aparat'); await tel.waitForFunction(() => document.getElementById('aparat-wideo').videoWidth > 0);
  await czekaj(tel, 1500); zn('tel_aparat', t1); await stan(tel, 'P3_aparat', '#aparat-migawka');
  await tel.click('#aparat-migawka'); await czekaj(tel, 1200); zn('tel_migawka', t1); await stan(tel, 'P4_wyslij', '#aparat-wyslij');
  await tel.click('#aparat-wyslij'); zn('tel_wyslij', t1);
  await tel.waitForSelector('#okno-aparat', { state: 'hidden' }); await tel.locator('#pliki-lista .zal-el').first().waitFor();
  await tel.locator('#pliki-sprawy').scrollIntoViewIfNeeded(); await czekaj(tel, 800); await stan(tel, 'P5_zdjecie_w_sprawie', '#pliki-lista .zal-el'); await czekaj(tel, 1200); zn('tel_koniec', t1);
  await kt.close();
  zn('marta_przed_zdjeciem', tm);
  await marta.locator('#pliki-lista .zal-el', { hasText: '.jpg' }).waitFor({ timeout: 30000 }); zn('marta_zdjecie', tm); await czekaj(marta, 400); await stan(marta, 'M2_zdjecie_u_marty', '#pliki-lista .zal-el');
  await czekaj(marta, 2500); zn('marta_koniec', tm);
  await km.close(); await prz.close();
  console.log(fs.readFileSync(path.join(OUT, 'znaczniki.txt'), 'utf8'));
})().catch((e) => { console.error(e); process.exit(1); });
