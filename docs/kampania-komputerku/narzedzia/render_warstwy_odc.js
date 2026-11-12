// Warstwy montażowe odcinka (PNG 1080x1920, przezroczyste): karty imion i podpis czasu.
// Użycie: node render_warstwy_odc.js <fonty_montserrat> <wyjscie>
const fs = require('fs'), path = require('path'), { chromium } = require('playwright');
const [FONTS, OUT] = process.argv.slice(2); fs.mkdirSync(OUT, { recursive: true });
const ff = [500, 700, 800].map((w) => `@font-face{font-family:M;font-weight:${w};src:url(file://${path.resolve(FONTS, `montserrat-latin-ext-${w}-normal.woff2`)}) format('woff2');unicode-range:U+0100-02AF}@font-face{font-family:M;font-weight:${w};src:url(file://${path.resolve(FONTS, `montserrat-latin-${w}-normal.woff2`)}) format('woff2')}`).join('');
const css = `${ff}*{margin:0;padding:0;box-sizing:border-box}html,body{width:1080px;height:1920px;background:transparent;font-family:M,sans-serif}`;
// Karta imienia w stylu OVERLAY_TRANSPARENT (biała karta, pasek gradientu z lewej), pozycja jak w pakiecie.
const karta = (imie, rola) => `<div style="position:absolute;left:135px;top:2064px"></div><div style="position:absolute;left:135px;top:1380px;display:flex;background:#fff;border-radius:30px;overflow:hidden;box-shadow:0 18px 44px rgba(6,23,68,.25)">
 <div style="width:16px;background:linear-gradient(180deg,#1C1CC0,#2197D3)"></div>
 <div style="padding:26px 44px 28px 32px"><div style="font-weight:800;font-size:58px;letter-spacing:-.04em;color:#071D49;line-height:1">${imie}</div>
 <div style="font-weight:500;font-size:34px;color:#647392;margin-top:10px">${rola}</div></div></div>`;
const czas = (t1, t2) => `<div style="position:absolute;left:0;right:0;bottom:250px;text-align:center;color:#fff;text-shadow:0 2px 18px rgba(0,0,0,.6)">
 <div style="font-weight:700;font-size:40px;letter-spacing:.14em;text-transform:uppercase;opacity:.92">${t1}</div>
 <div style="font-weight:800;font-size:120px;letter-spacing:-.03em;line-height:1.05">${t2}</div></div>`;
const W = { karta_basia: karta('Basia', 'sekretariat'), karta_pawel: karta('Paweł Nowak', 'syn pani Ireny'),
  karta_marta: karta('Marta', 'notariuszka'), karta_kuba: karta('Kuba', 'aplikant'), czas_0857: czas('Poniedziałek', '8:57'),
  karta_helena: karta('Helena Radecka', 'notariusz'), czas_0924: czas('Poniedziałek', '9:24'),
  zap_naglowek: `<div style="position:absolute;left:0;right:0;top:300px;text-align:center;color:#fff;text-shadow:0 2px 22px rgba(0,0,0,.7)">
   <div style="font-weight:700;font-size:40px;letter-spacing:.24em;text-transform:uppercase">W następnym odcinku</div>
   <div style="width:90px;height:5px;margin:22px auto 0;border-radius:3px;background:linear-gradient(90deg,#1C1CC0,#00BFE8)"></div></div>`,
  zap_tytul: `<div style="position:absolute;inset:0;background:radial-gradient(120% 80% at 50% 40%,#13246b 0%,#071D49 60%,#030b22 100%)"></div>
   <div style="position:absolute;left:90px;right:90px;top:760px;color:#fff">
   <div style="font-weight:700;font-size:34px;letter-spacing:.22em;text-transform:uppercase;color:#7fd8ff">Kancelaria pod Siódemką · odcinek 02</div>
   <div style="font-weight:800;font-size:104px;letter-spacing:-.03em;line-height:1.02;margin-top:30px">„Proszę nie<br>przy nim”</div></div>`,
  outro_napis: `<div style="position:absolute;left:92px;right:92px;top:1105px;color:#fff;font-weight:700;font-size:44px;line-height:1.25;letter-spacing:-.01em">Mniej chaosu.<br>Więcej czasu na to, co ważne.</div>
   <div style="position:absolute;left:92px;top:1790px;color:#fff;font-weight:500;font-size:36px;opacity:.9">Ciąg dalszy nastąpi…</div>` };
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
  for (const [n, h] of Object.entries(W)) {
    const tmp = path.resolve(OUT, '_w.html'); fs.writeFileSync(tmp, `<!doctype html><html><head><meta charset="utf-8"><style>${css}</style></head><body>${h}</body></html>`);
    await p.goto('file://' + tmp);
    await p.evaluate(() => document.fonts.ready);
    await p.screenshot({ path: path.join(OUT, n + '.png'), omitBackground: true });
  }
  fs.rmSync(path.resolve(OUT, '_w.html'), { force: true }); await b.close();
})();
