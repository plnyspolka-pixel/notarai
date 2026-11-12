// Animacja prawdziwych ekranów NotarAI (zrzuty stanów + ramki elementów z nagraj_ekrany_*.js) do 9:16.
// Każdy klip: wycinek zrzutu z płynnym najazdem, opcjonalne „stuknięcie” w element, podpis prawdziwości.
// Użycie: node render_ekrany_odc.js <katalog_zrzutow> <fonty> <plan.json> <wyjscie_dir>
const fs = require('fs'), path = require('path'), { spawn } = require('child_process'), { chromium } = require('playwright');
const [DIR, FONTS, PLAN, OUT] = process.argv.slice(2); fs.mkdirSync(OUT, { recursive: true });
const STANY = Object.fromEntries(JSON.parse(fs.readFileSync(path.join(DIR, 'stany.json'))).map((s) => [s.nazwa, s]));
const W = 1080, H = 1920, FPS = 30;
const cl = (x) => Math.max(0, Math.min(1, x)), io = (x) => { x = cl(x); return x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
const lerp = (a, b, x) => a + (b - a) * x;
const ff = [600, 700].map((w) => `@font-face{font-family:M;font-weight:${w};src:url(file://${path.resolve(FONTS, `montserrat-latin-ext-${w}-normal.woff2`)}) format('woff2');unicode-range:U+0100-02AF}@font-face{font-family:M;font-weight:${w};src:url(file://${path.resolve(FONTS, `montserrat-latin-${w}-normal.woff2`)}) format('woff2')}`).join('');
// okno 9:16 w pikselach zrzutu, wyśrodkowane na punkcie (cx, cy), skala z (1 = cała wysokość/szerokość)
function okno(st, img, cx, cy, z, panel) {
  const sk = img.w / st.viewport.width; let w, h;
  if (panel) { w = img.w * z; h = w * 10 / 16; if (h > img.h) { h = img.h; w = h * 16 / 10; } }
  else if (img.w / img.h > W / H) { h = img.h * z; w = h * W / H; } else { w = img.w * z; h = w * H / W; }
  let x = cx * sk - w / 2, y = cy * sk - h / 2;
  x = Math.max(0, Math.min(img.w - w, x)); y = Math.max(0, Math.min(img.h - h, y));
  return { x, y, w, h, sk };
}
(async () => {
  const plan = JSON.parse(fs.readFileSync(PLAN));
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: W, height: H } });
  for (const klip of plan) {
    const st = STANY[klip.stan], plik = 'file://' + path.resolve(DIR, st.plik);
    const tmp = path.join(OUT, '_s.html');
    const laduj = async (html) => { fs.writeFileSync(tmp, html); await p.goto('file://' + tmp); await p.evaluate(() => document.fonts.ready);
      await p.waitForFunction(() => document.getElementById('i').complete && document.getElementById('i').naturalWidth > 0); };
    const img = await (async () => { await laduj(`<img id=i src="${plik}">`);
      return p.evaluate(() => ({ w: document.getElementById('i').naturalWidth, h: document.getElementById('i').naturalHeight })); })();
    const r = st.ramka || { x: st.viewport.width / 2, y: st.viewport.height / 2, width: 0, height: 0 };
    const cx = klip.cx ?? (r.x + r.width / 2), cy = klip.cy ?? (r.y + r.height / 2);
    const PAN = !!klip.panel, PH = W * 10 / 16, PY = (H - PH) / 2 - 60;
    const kx = klip.kx ?? cx, ky = klip.ky ?? cy;
    const o0 = okno(st, img, kx, ky, klip.z0 ?? 1, PAN), o1 = okno(st, img, kx, ky, klip.z1 ?? 1, PAN);
    await laduj(`<!doctype html><html><head><meta charset=utf-8><style>${ff}*{margin:0}html,body{width:${W}px;height:${H}px;overflow:hidden;background:#F5F7FC;font-family:M}
      #v{position:absolute;inset:0;overflow:hidden}#tlo{position:absolute;inset:-60px;background-size:cover;background-position:center;filter:blur(28px) brightness(.45) saturate(1.1)}#v.panel{top:${PY}px;bottom:auto;height:${PH}px;border-radius:26px;box-shadow:0 30px 80px rgba(0,0,0,.45);left:0;right:0}#v img{position:absolute;transform-origin:0 0}
      #tap{position:absolute;border-radius:50%;border:6px solid #2B52D9;background:rgba(43,82,217,.18);opacity:0}
      #hl{position:absolute;border-radius:14px;border:5px solid #00BFE8;box-shadow:0 0 0 9999px rgba(6,23,68,0);opacity:0}
      #pod{position:absolute;left:0;right:0;bottom:0;height:150px;background:linear-gradient(180deg,rgba(6,23,68,0),rgba(6,23,68,.55));color:#fff;font-weight:600;font-size:26px;letter-spacing:.02em;display:flex;align-items:flex-end;justify-content:center;padding-bottom:48px}
      </style></head><body>${PAN ? `<div id=tlo style="background-image:url(${plik})"></div>` : ''}<div id=v class="${PAN ? 'panel' : ''}"><img id=i src="${plik}"></div><div id=hl></div><div id=tap></div><div id=pod>Prawdziwy ekran NotarAI · dane demonstracyjne</div></body></html>`);
    const N = Math.round(klip.t * FPS), surowy = path.join(OUT, klip.nazwa + '.mp4');
    const f = spawn('ffmpeg', ['-y', '-v', 'error', '-f', 'image2pipe', '-framerate', '' + FPS, '-c:v', 'mjpeg', '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', '16', '-pix_fmt', 'yuv420p', '-r', '' + FPS, surowy], { stdio: ['pipe', 'inherit', 'inherit'] });
    for (let i = 0; i < N; i++) {
      const t = i / FPS, k = io(t / klip.t);
      const o = { x: lerp(o0.x, o1.x, k), y: lerp(o0.y, o1.y, k), w: lerp(o0.w, o1.w, k) };
      const s = W / o.w;
      const oy = PAN ? PY : 0; const tapX = (cx * o0.sk - o.x) * s, tapY = (cy * o0.sk - o.y) * s + oy;
      const tt = klip.tap != null ? (t - klip.tap) / 0.45 : -1;
      const hk = klip.hl != null ? Math.sin(Math.PI * Math.min(1, Math.max(0, (t - klip.hl) / 1.2))) : 0;
      await p.evaluate(([o, s, tapX, tapY, tt, hk, rr]) => {
        const im = document.getElementById('i'); im.style.transform = `translate(${-o.x * s}px,${-o.y * s}px) scale(${s})`;
        const tp = document.getElementById('tap'); const R = 70 + 60 * Math.max(0, tt);
        tp.style.width = tp.style.height = 2 * R + 'px'; tp.style.left = tapX - R + 'px'; tp.style.top = tapY - R + 'px';
        tp.style.opacity = tt >= 0 && tt <= 1 ? (1 - tt) : 0;
        const hl = document.getElementById('hl'); hl.style.opacity = hk;
        hl.style.left = (rr.x - 10) + 'px'; hl.style.top = (rr.y - 10) + 'px'; hl.style.width = (rr.w + 20) + 'px'; hl.style.height = (rr.h + 20) + 'px';
      }, [o, s, tapX, tapY, tt, hk, { x: (r.x * o0.sk - o.x) * s, y: (r.y * o0.sk - o.y) * s + oy, w: r.width * o0.sk * s, h: r.height * o0.sk * s }]);
      const buf = await p.screenshot({ type: 'jpeg', quality: 94 });
      if (!f.stdin.write(buf)) await new Promise((rs) => f.stdin.once('drain', rs));
    }
    f.stdin.end(); await new Promise((rs) => f.on('close', rs)); console.log(klip.nazwa);
  }
  await b.close();
})();
