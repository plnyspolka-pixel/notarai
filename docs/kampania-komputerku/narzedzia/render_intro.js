// Renderuje 5 krótkich intro serii „Kancelaria pod Siódemką” (9:16, 1080x1920, 30 kl./s, ok. 6 s).
// Materiały wyłącznie z pakietu kampanii: scenografia-v2 (K1–K9), obsada-v2 (kadry postaci),
// tokeny marki, oryginalny sygnet, warstwa logo + znaczek AI. Animacja liczona klatka po klatce
// (deterministycznie), dźwięk składany w ffmpeg z ambience kancelarii, krótkich efektów
// syntetyzowanych na miejscu i głosu Marty („Komputerku…”, ElevenLabs, voice_id z obsady-v2).
//
// Użycie: node render_intro.js <katalog_fontow_montserrat> <katalog_wyjscia> [nr_intro …]
//   EPIZOD="Odcinek 1 · Księga nadawcza w pięć minut"   (podtytuł; pusty = bez podtytułu)
//   GLOS_KOMPUTERKU=<plik mp3>                         (domyślnie glosy_v2/zrodla/komputerku_marta_intro.mp3)
const fs = require('fs');
const path = require('path');
const { spawn, execFileSync } = require('child_process');
const { chromium } = require('playwright');

const K = path.resolve(__dirname, '..');
const PAK = path.join(K, 'pakiet');
const [FONTS, OUT, ...WYBOR] = process.argv.slice(2);
if (!FONTS || !OUT) { console.error('node render_intro.js <fonty> <wyjscie> [1..5]'); process.exit(1); }
fs.mkdirSync(OUT, { recursive: true });
const EPIZOD = process.env.EPIZOD ?? 'Odcinek 1 · Księga nadawcza w pięć minut';
const GLOS = process.env.GLOS_KOMPUTERKU || path.join(K, 'glosy_v2/zrodla/komputerku_marta_intro.mp3');
const AMB = path.join(K, 'glosy_v2/zrodla/ambience_kancelaria_22s.mp3');

const W = 1080, H = 1920, FPS = 30;
const f = (p) => 'file://' + path.join(PAK, p);
const IMG = {
  K1: f('09_scenografia_v2/plansze/K1.jpg'), K3: f('09_scenografia_v2/plansze/K3.jpg'),
  K6: f('09_scenografia_v2/plansze/K6.jpg'), K7: f('09_scenografia_v2/plansze/K7.jpg'),
  K8: f('09_scenografia_v2/plansze/K8.jpg'), K9: f('09_scenografia_v2/plansze/K9.jpg'),
  helena: f('10_obsada_v2/postacie/helena/kadr_K2m.jpg'), marta: f('10_obsada_v2/postacie/marta/kadr_K5m.jpg'),
  basia: f('10_obsada_v2/postacie/basia/kadr_K3m.jpg'), kuba: f('10_obsada_v2/postacie/kuba/kadr_K6m.jpg'),
  sygnet: f('01_marki/oryginalny_sygnet_z_repo.svg'),
  pasek: 'file://' + path.join(K, 'narzedzia/warstwy/warstwa_logo_ai.png'),
};

// ── czas i ruch ─────────────────────────────────────────────────────────────
const cl = (x) => Math.max(0, Math.min(1, x));
const outC = (x) => 1 - Math.pow(1 - cl(x), 3);              // ease-out
const inC = (x) => Math.pow(cl(x), 3);                        // ease-in
const io = (x) => { x = cl(x); return x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
const p = (t, a, d) => cl((t - a) / d);                       // postęp odcinka [a, a+d]
const lerp = (a, b, x) => a + (b - a) * x;
const wej = (t, a, d = .22, dy = 36) => `opacity:${outC(p(t, a, d))};transform:translateY(${(1 - outC(p(t, a, d))) * dy}px)`;

// ── CSS i klocki graficzne (te same co render_plansz.js) ────────────────────
const fontFaces = [500, 600, 700, 800].map((w) => `
@font-face{font-family:Montserrat;font-weight:${w};src:url(file://${path.resolve(FONTS, `montserrat-latin-ext-${w}-normal.woff2`)}) format('woff2');unicode-range:U+0100-02AF,U+0304,U+0308,U+0329,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF;}
@font-face{font-family:Montserrat;font-weight:${w};src:url(file://${path.resolve(FONTS, `montserrat-latin-${w}-normal.woff2`)}) format('woff2');}`).join('');
const CSS = `${fontFaces}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:${W}px;height:${H}px;overflow:hidden;background:#061744}
body{font-family:Montserrat,sans-serif;color:#0D193C;-webkit-font-smoothing:antialiased}
#s{position:absolute;inset:0;overflow:hidden}
.abs{position:absolute}
.ph{position:absolute;inset:0;background-size:cover;background-position:center;will-change:transform}
.grad{background:linear-gradient(115deg,#1C1CC0,#2463CC 54%,#2197D3 100%)}
.logo{display:inline-flex;align-items:center;gap:.3em;white-space:nowrap}
.logo img{width:1.55em;height:1.55em;display:block}
.logo b{font-weight:800;letter-spacing:-.055em;color:#071D49;line-height:1}
.logo b i{font-style:normal;color:#00BFE8}
.logo.inv b{color:#fff}.logo.inv b i{color:#2AD9F2}
.tile{background:#fff;border-radius:.32em;padding:.14em;display:inline-flex}
.eyebrow{font-weight:700;letter-spacing:.16em;text-transform:uppercase}
.tytul{font-weight:800;line-height:1.02;letter-spacing:-.045em}
.karta{background:#fff;border-radius:22px;box-shadow:0 18px 40px rgba(6,23,68,.22);overflow:hidden;display:flex}
.karta .pas{width:12px;background:linear-gradient(180deg,#1C1CC0,#2197D3)}
`;
const logo = (px, inv = false) => `<span class="logo${inv ? ' inv' : ''}" style="font-size:${px}px">${inv ? `<span class="tile"><img src="${IMG.sygnet}"></span>` : `<img src="${IMG.sygnet}">`}<b>notar<i>ai</i></b></span>`;
const pasek = (t, a = .2) => `<img class="abs" src="${IMG.pasek}" style="left:0;top:0;width:${W}px;height:${H}px;opacity:${outC(p(t, a, .25))}">`;
const zdjecie = (src, s, ox = 50, oy = 50, extra = '') =>
  `<div class="ph" style="background-image:url(${src});transform-origin:${ox}% ${oy}%;transform:scale(${s});${extra}"></div>`;
const micSvg = (c = '#1C1CC0') => `<svg viewBox="0 0 24 24" width="56" height="56" fill="none" stroke="${c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v4"/></svg>`;
const checkSvg = `<svg viewBox="0 0 24 24" width="58" height="58" fill="none" stroke="#fff" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.2 4.2L19 7"/></svg>`;
const zegarSvg = `<svg viewBox="0 0 24 24" width="34" height="34" fill="none" stroke="#1C1CC0" stroke-width="2.4" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>`;
// 11 słupków; amplituda animowana pętlą 1,1 s (biblia wizualna, stan 2)
const BASE = [.35, .6, .9, .55, 1, .7, .95, .5, .8, .45, .3];
const slupki = (t, ruch, h = 96, kolor = '#00CFFF') => `<div style="display:flex;align-items:center;gap:9px;height:${h}px">${BASE.map((b, i) => {
  const a = ruch ? .45 + .55 * Math.abs(Math.sin((t / 1.1) * Math.PI * 2 + i * .7)) : 1;
  return `<span style="display:block;width:7px;border-radius:9px;background:${kolor};height:${Math.max(.12, b * a) * 100}%"></span>`;
}).join('')}</div>`;

// Blok tytułu serii (wspólny dla wszystkich intro); a = start animacji
function tytul(t, a, { kolor = '#fff', eyebrowKolor = '#9FEFFF', podKolor = '#DCEBFF', rozmiar = 112, srodek = false } = {}) {
  const al = srodek ? 'center' : 'left';
  return `<div style="text-align:${al};color:${kolor}">
    <div class="eyebrow" style="font-size:26px;color:${eyebrowKolor};margin-bottom:26px;${wej(t, a, .22, 24)}">Seria NotarAI · Komputerku…</div>
    <div class="tytul" style="font-size:${rozmiar}px">
      <div style="${wej(t, a + .12, .25, 50)}">Kancelaria</div>
      <div style="${wej(t, a + .24, .25, 50)}">pod Siódemką</div>
    </div>
    ${EPIZOD ? `<div style="font-weight:500;font-size:34px;margin-top:30px;color:${podKolor};${wej(t, a + .45, .22, 20)}">${EPIZOD}</div>` : ''}
  </div>`;
}

// ── 5 intro ─────────────────────────────────────────────────────────────────
// Każde: { slug, nazwa, D, scena(t) → html, dzwiek: { sting, swisty[], blipy[], glos? } }
const INTRO = [];

// 1. „Siódemka” — wejście do kancelarii (K7), na drzwiach rysuje się siódemka, potem plansza tytułowa.
INTRO.push({
  slug: '1_siodemka', nazwa: 'Siódemka (drzwi)', D: 6,
  dzwiek: { sting: 2.75, swisty: [2.5], blipy: [] },
  scena(t) {
    const rys = io(p(t, .45, 1.3));                          // rysowanie konturu
    const wyp = outC(p(t, 1.6, .5));                          // wypełnienie
    const znik = inC(p(t, 2.55, .3));
    const panel = outC(p(t, 2.5, .5));
    const ph = H * .44;
    return `${zdjecie(IMG.K7, lerp(1.0, 1.2, io(p(t, 0, 6))), 50, 56)}
    <div class="abs" style="inset:0;background:radial-gradient(ellipse at 50% 55%,rgba(6,23,68,0) 30%,rgba(6,23,68,${.15 + .35 * io(p(t, 1, 1.5))}) 100%)"></div>
    <svg class="abs" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" style="left:0;top:0;opacity:${1 - znik};transform:translateY(${-znik * 80}px) scale(${1 + .05 * wyp})">
      <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#00CFFF"/><stop offset=".55" stop-color="#2463CC"/><stop offset="1" stop-color="#1C1CC0"/></linearGradient></defs>
      <path d="M300 560 H800 V700 L560 1360 H390 L625 700 H300 Z" pathLength="1000"
        fill="url(#g)" fill-opacity="${.88 * wyp}" stroke="#fff" stroke-width="7" stroke-linejoin="round"
        stroke-dasharray="1000" stroke-dashoffset="${1000 * (1 - rys)}"/>
    </svg>
    <div class="abs grad" style="left:0;width:${W}px;top:${H - ph * panel}px;height:${ph}px;padding:70px 90px;display:flex;flex-direction:column;justify-content:center;gap:0">
      <div class="abs" style="left:0;right:0;top:-220px;height:220px;background:linear-gradient(180deg,rgba(28,28,192,0),#1C1CC0);opacity:${panel}"></div>
      <div style="margin-bottom:56px;${wej(t, 2.8, .22, 20)}">${logo(50, true)}</div>
      ${tytul(t, 2.9)}
    </div>
    ${pasek(t, .25)}`;
  },
});

// 2. „Obsada” — cztery stałe postacie w szybkich ujęciach z kartami imion, potem plansza z twarzami.
const OBSADA = [
  { k: 'helena', imie: 'Helena', rola: 'pani rejent', fx: .50, fy: .40, s: 3.4 },
  { k: 'marta', imie: 'Marta', rola: 'notariuszka', fx: .45, fy: .30, s: 3.2 },
  { k: 'basia', imie: 'Basia', rola: 'sekretariat', fx: .46, fy: .32, s: 3.4 },
  { k: 'kuba', imie: 'Kuba', rola: 'aplikant', fx: .56, fy: .25, s: 3.6 },
];
function twarz(o, C) {
  const iw = C * o.s, ih = iw * 2752 / 1536;
  return `background-image:url(${IMG[o.k]});background-size:${iw}px ${ih}px;background-position:${C / 2 - o.fx * iw}px ${C / 2 - o.fy * ih}px`;
}
INTRO.push({
  slug: '2_obsada', nazwa: 'Obsada', D: 6,
  dzwiek: { sting: 3.55, swisty: [.78, 1.63, 2.48, 3.3], blipy: [] },
  scena(t) {
    const L = .85, KON = 4 * L;
    let h = '';
    if (t < KON + .3) {
      const i = Math.min(3, Math.floor(t / L)), o = OBSADA[i], t0 = i * L, lt = t - t0;
      const ogn = [[50, 30], [50, 40], [38, 30], [76, 22]][i];
      h += zdjecie(IMG[o.k], lerp(1.12, 1.02, outC(lt / L)), ogn[0], ogn[1]);
      h += `<div class="abs karta" style="left:90px;top:1380px;${`opacity:${outC(p(lt, .1, .2))};transform:translateX(${(1 - outC(p(lt, .1, .22))) * -60}px)`}">
        <div class="pas"></div><div style="padding:24px 40px 26px 30px"><div style="font-weight:800;font-size:56px;letter-spacing:-.04em;color:#071D49;line-height:1">${o.imie}</div>
        <div style="font-weight:500;font-size:32px;color:#647392;margin-top:10px">${o.rola}</div></div></div>`;
      // przejście: ukośny pas w barwach marki przelatuje przez kadr na cięciu
      for (let c = 1; c <= 4; c++) {
        const x = p(t, c * L - .12, .26);
        if (x > 0 && x < 1) h += `<div class="abs grad" style="top:-300px;height:${H + 600}px;width:520px;left:${lerp(-700, W + 200, io(x))}px;transform:skewX(-14deg);box-shadow:0 0 120px rgba(0,207,255,.5)"></div>`;
      }
      h += pasek(t, .1);
    }
    if (t >= KON) {
      const C = 210, g = 34, x0 = (W - 4 * C - 3 * g) / 2;
      h += `<div class="abs grad" style="inset:0">
        <div class="abs" style="inset:0;background:radial-gradient(circle at 78% 18%,rgba(0,207,255,.35),transparent 45%),radial-gradient(circle at 10% 95%,rgba(6,23,68,.45),transparent 50%)"></div>
        <div class="abs" style="left:90px;top:200px;${wej(t, KON + .1, .22, 20)}">${logo(50, true)}</div>
        ${OBSADA.map((o, i) => { const s = outC(p(t, KON + .15 + i * .09, .25));
          return `<div class="abs" style="left:${x0 + i * (C + g)}px;top:560px;width:${C}px;text-align:center;opacity:${s};transform:scale(${lerp(.6, 1, s)})">
            <div style="width:${C}px;height:${C}px;border-radius:50%;border:6px solid #fff;box-shadow:0 14px 34px rgba(6,23,68,.35);${twarz(o, C - 12)}"></div>
            <div style="color:#fff;font-weight:700;font-size:30px;margin-top:18px">${o.imie}</div></div>`; }).join('')}
        <div class="abs" style="left:90px;right:90px;top:1000px">${tytul(t, KON + .5)}</div>
      </div>`;
    }
    return h;
  },
});

// 3. „Komputerku…” — Marta przy stole roboczym, dymek przechodzi przez trzy stany z biblii wizualnej.
INTRO.push({
  slug: '3_komputerku', nazwa: 'Komputerku…', D: 6,
  dzwiek: { sting: 3.45, swisty: [3.15], blipy: [1.35, 2.5], glos: .5 },
  scena(t) {
    const we = outC(p(t, .4, .22));
    const stan = t < 1.35 ? 0 : t < 2.5 ? 1 : 2;
    const fade = (a) => outC(p(t, a, .15));
    const teksty = ['Komputerku…', 'Już sprawdzam…', 'Gotowe do sprawdzenia'];
    const wyb = [1 - (t >= 1.35 ? fade(1.35) : 0), stan === 1 ? fade(1.35) * (1 - fade(2.5)) : 0, stan === 2 ? fade(2.5) : 0];
    const zakryj = io(p(t, 3.1, .45));
    const dymek = `<div class="abs" style="left:70px;right:70px;top:${lerp(1420, 1300, we)}px;opacity:${we * (1 - inC(p(t, 3.1, .25)))}">
      <div class="grad" style="border-radius:44px;height:190px;display:flex;align-items:center;padding:0 44px 0 34px;gap:30px;box-shadow:0 24px 60px rgba(6,23,68,.35)">
        <div style="width:122px;height:122px;border-radius:50%;flex:none;display:flex;align-items:center;justify-content:center;background:${stan === 2 ? '#23764B' : '#fff'}">${stan === 2 ? checkSvg : micSvg()}</div>
        <div style="position:relative;flex:1;height:120px">
          ${teksty.map((tx, i) => `<div class="abs" style="left:0;top:50%;transform:translateY(-50%);white-space:nowrap;color:#fff;font-weight:800;letter-spacing:-.04em;font-size:${i === 2 ? 50 : 62}px;opacity:${wyb[i]}">${tx}</div>`).join('')}
        </div>
        <div style="opacity:${stan === 2 ? 1 - fade(2.5) : 1}">${slupki(t, stan === 1, 96)}</div>
      </div></div>`;
    return `${zdjecie(IMG.marta, lerp(1.04, 1.14, io(p(t, 0, 3.6))), 50, 38)}
      <div class="abs" style="inset:0;background:linear-gradient(180deg,rgba(6,23,68,0) 55%,rgba(6,23,68,.45) 100%)"></div>
      ${dymek}
      ${pasek(t, .15)}
      <div class="abs grad" style="left:0;width:${W}px;height:${H}px;top:${H * (1 - zakryj)}px">
        <div class="abs" style="inset:0;background:radial-gradient(circle at 78% 18%,rgba(0,207,255,.35),transparent 45%),radial-gradient(circle at 10% 95%,rgba(6,23,68,.45),transparent 50%)"></div>
        <div class="abs" style="left:90px;right:90px;top:620px;text-align:center">
          <div style="display:inline-block;background:#fff;border-radius:30px;padding:22px 38px;margin-bottom:70px;${wej(t, 3.45, .22, 20)}">${logo(58)}</div>
          ${tytul(t, 3.55, { srodek: true, rozmiar: 116 })}
          <div style="font-weight:500;font-size:30px;color:#fff;opacity:.9;margin-top:56px;line-height:1.45;${wej(t, 4.2, .25, 16)}">Komputer przygotuje projekt.<br>Decyzję zawsze podejmuje notariusz.</div>
        </div>
      </div>`;
  },
});

// 4. „Plan kancelarii” — rzut pokoju rysuje się liniami marki, kamera K1 wjeżdża w prawdziwe wnętrze.
INTRO.push({
  slug: '4_plan', nazwa: 'Plan kancelarii', D: 6,
  dzwiek: { sting: 3.25, swisty: [2.3], blipy: [1.75] },
  scena(t) {
    const d = (a, dl = .6) => io(p(t, a, dl));
    // rzut 900x1200 w kadrze, współrzędne wg plan.png (biblioteka z lewej, okna z prawej, drzwi NW, sekretariat SE)
    const X = 90, Y = 360, PW = 900, PH = 1200;
    const r = (x, y, w, h, a, kol = '#2B52D9', fill = 'rgba(43,82,217,.08)') => {
      const per = 2 * (w + h), k = d(a);
      return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="10" fill="${fill}" fill-opacity="${k}" stroke="${kol}" stroke-width="5" stroke-dasharray="${per}" stroke-dashoffset="${per * (1 - k)}"/>`;
    };
    const lab = (x, y, tx, a, anchor = 'middle', rot = 0) => `<text x="${x}" y="${y}" text-anchor="${anchor}" transform="rotate(${rot} ${x} ${y})" font-family="Montserrat" font-weight="700" font-size="30" letter-spacing="3" fill="#071D49" opacity="${outC(p(t, a, .25))}">${tx}</text>`;
    const cam = outC(p(t, 1.75, .25)), puls = (Math.sin(t * 9) + 1) / 2;
    const zoom = io(p(t, 2.2, .8)), prz = io(p(t, 2.45, .6));
    const kx = X + PW / 2, ky = Y + PH - 40;
    const plan = `<svg class="abs" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" style="left:0;top:0;transform-origin:${kx}px ${ky}px;transform:scale(${1 + 2.2 * zoom})">
      <rect x="${X}" y="${Y}" width="${PW}" height="${PH}" fill="#fff" fill-opacity="${d(.1)}" stroke="#071D49" stroke-width="12" stroke-dasharray="4200" stroke-dashoffset="${4200 * (1 - d(0, .9))}"/>
      ${r(X + 10, Y + 10, 90, PH - 220, .5)}${lab(X + 62, Y + 520, 'BIBLIOTEKA', .9, 'middle', -90)}
      ${r(X + PW - 50, Y + 80, 40, PH - 260, .6, '#00BFE8', 'rgba(0,207,255,.18)')}${lab(X + PW - 70, Y + 560, 'OKNA', 1, 'middle', 90)}
      ${r(X + 150, Y + 10, 200, 26, .65)}${lab(X + 250, Y + 80, 'DRZWI', 1.05)}
      ${r(X + 330, Y + 300, 300, 150, .75, '#1C1CC0', 'rgba(28,28,192,.12)')}${lab(X + 480, Y + 385, 'BIURKO', 1.1)}
      ${r(X + 150, Y + 760, 260, 160, .85)}${lab(X + 280, Y + 850, 'STÓŁ', 1.2)}
      ${r(X + 620, Y + 820, 240, 170, .95, '#2197D3', 'rgba(33,151,211,.14)')}${lab(X + 740, Y + 915, 'SEKRETARIAT', 1.3)}
      <g opacity="${cam}">
        <path d="M${kx} ${ky} L${kx - 190} ${Y + 420} L${kx + 190} ${Y + 420} Z" fill="rgba(0,207,255,${.10 + .08 * puls})" stroke="#00CFFF" stroke-width="3"/>
        <circle cx="${kx}" cy="${ky}" r="${18 + 6 * puls}" fill="#1C1CC0" stroke="#fff" stroke-width="5"/>
        <text x="${kx + 34}" y="${ky + 12}" font-family="Montserrat" font-weight="800" font-size="34" fill="#1C1CC0">K1</text>
      </g>
    </svg>`;
    const dol = outC(p(t, 3.0, .5));
    return `<div class="abs" style="inset:0;background:#F5F7FC"></div>
      <div class="abs" style="left:90px;top:200px;opacity:${1 - prz}">${logo(46)}</div>
      ${plan}
      <div style="opacity:${prz}">${zdjecie(IMG.K1, lerp(1.25, 1.04, io(p(t, 2.45, 3.4))), 50, 70)}</div>
      <div class="abs" style="left:0;right:0;bottom:0;height:${H * .55}px;opacity:${dol};background:linear-gradient(180deg,rgba(28,28,192,0) 0%,rgba(28,28,192,.82) 42%,#1C1CC0 100%)"></div>
      <div class="abs" style="left:90px;right:90px;bottom:170px">${tytul(t, 3.15)}</div>
      ${t > 2.45 ? pasek(t, 2.6) : ''}`;
  },
});

// 5. „Poranek w kancelarii” — trzy szybkie ujęcia z godziną, potem szklana karta tytułowa.
INTRO.push({
  slug: '5_poranek', nazwa: 'Poranek w kancelarii', D: 6,
  dzwiek: { sting: 3.5, swisty: [1.1, 2.2, 3.25], blipy: [.25, 1.35, 2.45] },
  scena(t) {
    const UJ = [
      { src: IMG.K8, g: '8:00', tx: 'Otwieramy kancelarię', ox: 50, oy: 45 },
      { src: IMG.K9, g: '8:05', tx: 'Kawa i pierwsze akta', ox: 60, oy: 60 },
      { src: IMG.K3, g: '8:15', tx: 'Sekretariat już działa', ox: 70, oy: 55 },
    ];
    const L = 1.1, KON = 3 * L, PRZ = .28;
    let h = '';
    for (let i = 0; i < 3; i++) {
      const a = i * L, b = a + L;
      if (t < a - PRZ || t > b + PRZ) continue;
      // wjazd z prawej (push), wyjazd w lewo
      const wjazd = i === 0 ? 1 : io(p(t, a - PRZ, PRZ));
      const wyjazd = i === 2 ? 0 : io(p(t, b - PRZ, PRZ));
      const x = (1 - wjazd) * W - wyjazd * W;
      const u = UJ[i], lt = t - a;
      h += `<div class="abs" style="inset:0;transform:translateX(${x}px);overflow:hidden">${zdjecie(u.src, lerp(1.1, 1.0, outC(p(t, a - PRZ, L + PRZ))), u.ox, u.oy)}
        <div class="abs" style="left:90px;top:360px;display:flex;align-items:center;gap:18px;background:#fff;border-radius:999px;padding:16px 34px 16px 22px;box-shadow:0 14px 34px rgba(6,23,68,.25);${wej(lt, .12, .22, 18)}">
          ${zegarSvg}<span style="font-weight:800;font-size:38px;color:#071D49;letter-spacing:-.02em">${u.g}</span>
          <span style="width:2px;height:34px;background:#D9E5F4"></span>
          <span style="font-weight:600;font-size:32px;color:#647392">${u.tx}</span></div></div>`;
    }
    if (t > KON - PRZ) {
      const k = io(p(t, KON - PRZ, .4));
      h += `<div class="abs" style="inset:0;opacity:${k}">${zdjecie(IMG.K1, lerp(1.15, 1.05, io(p(t, KON, 2.7))), 50, 60, 'filter:blur(16px) saturate(1.1)')}
        <div class="abs" style="inset:0;background:rgba(6,23,68,.5)"></div>
        <div class="abs" style="left:70px;right:70px;top:540px;background:rgba(255,255,255,.94);border-radius:44px;padding:70px 70px 76px;box-shadow:0 30px 80px rgba(6,23,68,.4);${wej(t, KON, .3, 60)}">
          <div style="margin-bottom:60px">${logo(56)}</div>
          ${tytul(t, KON + .15, { kolor: '#071D49', eyebrowKolor: '#2B52D9', podKolor: '#647392', rozmiar: 108 })}
          <div style="height:10px;border-radius:9px;margin-top:56px;width:${outC(p(t, KON + .6, .5)) * 100}%" class="grad"></div>
        </div></div>`;
    }
    return h + pasek(t, .15);
  },
});

// ── dźwięk ──────────────────────────────────────────────────────────────────
// sting: akord C–G–C (sinusy z wygaszaniem) + miękki bas; świst: szum różowy z filtrem; blip: krótki ton
function dzwiek(intro, plikWideo, wynik) {
  const { D } = intro, z = intro.dzwiek, IN = [], FC = [];
  let n = 0; const mix = [];
  const dodaj = (args, filtr) => { IN.push(...args); const i = n++; FC.push(`[${i}:a]${filtr}[a${i}]`); mix.push(`[a${i}]`); };
  dodaj(['-stream_loop', '-1', '-i', AMB], `atrim=0:${D},volume=0.5,afade=t=in:d=0.4,afade=t=out:st=${D - .7}:d=0.7,aformat=sample_rates=48000:channel_layouts=stereo`);
  const ms = (s) => Math.round(s * 1000);
  const sting = `0.16*sin(2*PI*523.25*t)*exp(-2.6*t)+0.12*sin(2*PI*783.99*(t-0.07))*exp(-2.4*(t-0.07))*gte(t,0.07)+0.10*sin(2*PI*1046.5*(t-0.14))*exp(-2.2*(t-0.14))*gte(t,0.14)+0.18*sin(2*PI*130.81*t)*(1-exp(-12*t))*exp(-1.1*t)`;
  dodaj(['-f', 'lavfi', '-t', '2.6', '-i', `aevalsrc=${sting.replace(/,/g, '\\,')}:s=48000`], `aformat=sample_rates=48000:channel_layouts=stereo,adelay=${ms(z.sting)}|${ms(z.sting)},volume=1.6`);
  for (const s of z.swisty) dodaj(['-f', 'lavfi', '-t', '0.45', '-i', 'anoisesrc=color=pink:amplitude=0.6:r=48000'],
    `highpass=f=900,lowpass=f=6000,afade=t=in:d=0.25:curve=exp,afade=t=out:st=0.25:d=0.2,volume=0.22,aformat=sample_rates=48000:channel_layouts=stereo,adelay=${ms(s - .2)}|${ms(s - .2)}`);
  for (const s of z.blipy) dodaj(['-f', 'lavfi', '-t', '0.18', '-i', 'aevalsrc=0.2*sin(2*PI*1318.5*t)*exp(-28*t)+0.12*sin(2*PI*1975.5*t)*exp(-34*t):s=48000'],
    `aformat=sample_rates=48000:channel_layouts=stereo,adelay=${ms(s)}|${ms(s)}`);
  if (z.glos != null && fs.existsSync(GLOS)) dodaj(['-i', GLOS], `aformat=sample_rates=48000:channel_layouts=stereo,volume=1.5,adelay=${ms(z.glos)}|${ms(z.glos)}`);
  FC.push(`${mix.join('')}amix=inputs=${mix.length}:duration=first:normalize=0,atrim=0:${D},loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[a]`);
  execFileSync('ffmpeg', ['-y', '-v', 'error', '-i', plikWideo, ...IN.flatMap((x) => x).map(String),
    '-filter_complex', FC.join(';').replace(/\[(\d+):a\]/g, (_, i) => `[${+i + 1}:a]`),
    '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-movflags', '+faststart', '-t', String(D), wynik]);
}

// ── render ──────────────────────────────────────────────────────────────────
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  const tmp = path.join(OUT, '.robocze'); fs.mkdirSync(tmp, { recursive: true });
  const strona = path.join(tmp, 'scena.html');
  fs.writeFileSync(strona, `<!doctype html><html><head><meta charset="utf-8"><style>${CSS}</style></head><body><div id="s"></div>
    ${Object.values(IMG).map((u) => `<img src="${u}" style="position:absolute;width:1px;height:1px;opacity:0">`).join('')}</body></html>`);
  await page.goto('file://' + strona);
  await page.evaluate(() => document.fonts.ready);
  await page.waitForLoadState('networkidle');
  const lista = WYBOR.length ? INTRO.filter((_, i) => WYBOR.includes(String(i + 1))) : INTRO;
  for (const intro of lista) {
    const surowy = path.join(tmp, `${intro.slug}_v.mp4`);
    const ff = spawn('ffmpeg', ['-y', '-v', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-',
      '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', '-r', String(FPS), surowy], { stdio: ['pipe', 'inherit', 'inherit'] });
    const N = Math.round(intro.D * FPS);
    for (let i = 0; i < N; i++) {
      const t = i / FPS;
      await page.evaluate((html) => { document.getElementById('s').innerHTML = html; }, intro.scena(t));
      await page.evaluate(() => Promise.all([...document.images].map((im) => im.decode().catch(() => {}))));
      const buf = await page.screenshot({ type: 'jpeg', quality: 93 });
      if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
      if (i === Math.round(N * .75)) fs.writeFileSync(path.join(tmp, `${intro.slug}_klatka.jpg`), buf);
    }
    ff.stdin.end(); await new Promise((r, j) => ff.on('close', (c) => (c ? j(new Error('ffmpeg ' + c)) : r())));
    const wynik = path.join(OUT, `INTRO_${intro.slug}_9x16.mp4`);
    dzwiek(intro, surowy, wynik);
    console.log(`${intro.nazwa}: ${wynik}`);
  }
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
