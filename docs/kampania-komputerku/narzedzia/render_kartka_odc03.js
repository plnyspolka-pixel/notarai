// Wkładka odc. 03: wydruk § 5 Kuby na biurku Heleny (PNG 1620x2880, do najazdu zoompan w montażu).
// Trzy stany: a — czysta kartka, b — „w/w” obwiedzione piórem Heleny, c — dodatkowo podkreślone zdanie o własności.
// Treść zgodna z kanonem odcinka (sezon1/ODC03_SCENARIUSZ_V1.md); § 6 jak w prawdziwym projekcie z NotarAI.
// Użycie: node render_kartka_odc03.js <wyjscie_dir>
const fs = require('fs'), path = require('path'), { chromium } = require('playwright');
const OUT = path.resolve(process.argv[2]); fs.mkdirSync(OUT, { recursive: true });
const W = 1620, H = 2880;
const html = (stan) => `<!doctype html><html><head><meta charset="utf-8"><style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:${W}px;height:${H}px;overflow:hidden;background:radial-gradient(120% 90% at 50% 45%,#6b4529 0%,#4a2d19 60%,#2e1b0e 100%)}
#k{position:absolute;left:150px;top:330px;width:1320px;height:2260px;background:linear-gradient(180deg,#fdfbf6,#f6f1e6);transform:rotate(-1.6deg);
 box-shadow:0 40px 90px rgba(0,0,0,.55),0 4px 10px rgba(0,0,0,.35);padding:150px 130px;font-family:'Liberation Serif','DejaVu Serif',serif;color:#1d1d1f}
.n{font-size:34px;letter-spacing:.12em;text-transform:uppercase;color:#6b6b70}
.s{font-size:30px;color:#8a8a90;margin-top:12px}
.p{font-size:58px;line-height:1.55;margin-top:70px;text-align:left}
.f{opacity:.35;filter:blur(1.2px)}
svg{position:absolute;inset:0;overflow:visible}
</style></head><body><div id="k">
<div class="n">Projekt — wersja robocza</div><div class="s">S-041-2026 · NOWAK — KACZMAREK · poprawka § 5: K.</div>
<div class="p f">§ 4. Sposób zapłaty ceny — do uzupełnienia.</div>
<div class="p">§ 5. <span id="wl">Z dniem 15 stycznia 2027 r. Kupujący staną się właścicielami</span> <span id="ww">w/w</span> lokalu i otrzymają klucze.</div>
<div class="p">§ 6. Koszty tego aktu ponoszą kupujący.</div>
<div class="p f">§ 7. Akt ten został odczytany, przyjęty i podpisany.</div>
<svg id="r"></svg></div></body></html>`;
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: W, height: H } });
  for (const stan of ['a', 'b', 'c']) {
    const tmp = path.join(OUT, '_k.html'); fs.writeFileSync(tmp, html(stan)); await p.goto('file://' + tmp);
    await p.evaluate((stan) => {
      const kk = document.getElementById('k'), svg = document.getElementById('r'); kk.style.transform = 'none'; const kb = kk.getBoundingClientRect();
      // mierzymy przed obrotem; SVG leży w obróconej kartce, więc obraca się razem z tekstem
      const rel = (id) => [...document.getElementById(id).getClientRects()].map((r) => ({ x: r.left - kb.left, y: r.top - kb.top, w: r.width, h: r.height }));
      const atr = 'fill="none" stroke="#1b2f86" stroke-linecap="round" stroke-linejoin="round"';
      let s = '';
      if (stan !== 'a') { const r = rel('ww')[0]; const cx = r.x + r.w / 2, cy = r.y + r.h / 2;
        s += `<ellipse cx="${cx}" cy="${cy}" rx="${r.w / 2 + 14}" ry="${r.h / 2 + 2}" ${atr} stroke-width="7" transform="rotate(-4 ${cx} ${cy})"/>`;
}
      if (stan === 'c') for (const r of rel('wl')) { const y = r.y + r.h - 6; let d = `M${r.x} ${y}`;
        for (let x = r.x; x < r.x + r.w; x += 36) d += ` q 9 10 18 0 q 9 -10 18 0`; s += `<path d="${d}" ${atr} stroke-width="5"/>`; }
      svg.innerHTML = s; kk.style.transform = '';
    }, stan);
    await p.screenshot({ path: path.join(OUT, `kartka_${stan}.png`) });
  }
  fs.rmSync(path.join(OUT, '_k.html'), { force: true }); await b.close();
})();
