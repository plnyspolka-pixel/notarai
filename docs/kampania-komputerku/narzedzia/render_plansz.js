// Renderuje plansze kampanii "Komputerku…" z prawdziwym Montserratem.
// Użycie: node render.js <katalog_pakietu> <katalog_fontow> <katalog_wyjscia>
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const [PAK, FONTS, OUT] = process.argv.slice(2);
const url = (p) => 'file://' + path.resolve(PAK, p);
const SYGNET = url('01_marki/oryginalny_sygnet_z_repo.svg');
const TEAM = url('07_referencje_fotograficzne/kancelaria_zespol_kadr_glowny.jpg');
const REF = (n) => url(`02_bohaterowie/${n}_ref.jpg`);

const fontFaces = [400, 500, 600, 700, 800].map((w) => `
@font-face{font-family:Montserrat;font-weight:${w};font-style:normal;
src:url(file://${path.resolve(FONTS, `montserrat-latin-ext-${w}-normal.woff2`)}) format('woff2');unicode-range:U+0100-02AF,U+0304,U+0308,U+0329,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF;}
@font-face{font-family:Montserrat;font-weight:${w};font-style:normal;
src:url(file://${path.resolve(FONTS, `montserrat-latin-${w}-normal.woff2`)}) format('woff2');}`).join('');

const CSS = `${fontFaces}
:root{--deep:#061744;--navy:#071D49;--ink:#0D193C;--indigo:#1C1CC0;--blue:#2B52D9;--azure:#2197D3;--cyan:#00CFFF;
--wcyan:#00BFE8;--bg:#F5F7FC;--stroke:#D9E5F4;--muted:#647392;--success:#23764B;
--grad:linear-gradient(115deg,#1C1CC0,#2463CC 54%,#2197D3 100%);}
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:transparent}
body{font-family:Montserrat,sans-serif;color:var(--ink);-webkit-font-smoothing:antialiased}
.stage{position:relative;overflow:hidden}
.logo{display:inline-flex;align-items:center;gap:.3em;white-space:nowrap}
.logo img{width:1.55em;height:1.55em;display:block}
.logo b{font-weight:800;letter-spacing:-.055em;color:var(--navy);line-height:1}
.logo b i{font-style:normal;color:var(--wcyan)}
.logo.inv b{color:#fff}.logo.inv b i{color:#2AD9F2}
.tile{background:#fff;border-radius:.32em;padding:.14em;display:inline-flex}
.eyebrow{font-weight:700;letter-spacing:.16em;text-transform:uppercase}
.photo{position:absolute;background-size:cover;background-repeat:no-repeat}
.pill{display:inline-flex;align-items:center;justify-content:center;border-radius:999px}
.mic{display:inline-flex;align-items:center;justify-content:center;border-radius:50%;background:var(--indigo);flex:none}
.mic svg{width:46%;height:46%}
.bars{display:flex;align-items:center;gap:6%;height:100%}
.bars span{display:block;width:5%;background:var(--cyan);border-radius:9px}
`;

const micSvg = (c = '#fff') => `<svg viewBox="0 0 24 24" fill="none" stroke="${c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v4"/></svg>`;
const checkSvg = `<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.2 4.2L19 7"/></svg>`;
const barsSvg = `<svg viewBox="0 0 24 24" fill="#fff"><rect x="3" y="9" width="2.4" height="6" rx="1.2"/><rect x="7.4" y="5" width="2.4" height="14" rx="1.2"/><rect x="11.8" y="7.5" width="2.4" height="9" rx="1.2"/><rect x="16.2" y="4" width="2.4" height="16" rx="1.2"/><rect x="20.6" y="10" width="1.4" height="4" rx=".7"/></svg>`;
const logo = (px, inv = false) => `<span class="logo${inv ? ' inv' : ''}" style="font-size:${px}px">${inv ? `<span class="tile"><img src="${SYGNET}"></span>` : `<img src="${SYGNET}">`}<b>notar<i>ai</i></b></span>`;
const wave = (n = 11, h = [.35, .6, .9, .55, 1, .7, .95, .5, .8, .45, .3]) =>
  `<div class="bars">${Array.from({ length: n }, (_, i) => `<span style="height:${h[i % h.length] * 100}%"></span>`).join('')}</div>`;

// ── Plansze wideo ───────────────────────────────────────────────────────────
const FMT = { '9x16': [1080, 1920], '16x9': [1920, 1080], '1x1': [1080, 1080] };

function intro(W, H, f) {
  const u = Math.min(W, H) / 1080; // jednostka skali
  const land = f === '16x9';
  const photo = land
    ? `<div class="photo" style="left:0;top:0;width:${W * .6}px;height:${H}px;background-image:url(${TEAM});background-position:32% 40%"></div>
       <div style="position:absolute;left:${W * .6 - 260 * u}px;top:0;width:${260 * u}px;height:${H}px;background:linear-gradient(90deg,rgba(28,28,192,0),#1C1CC0)"></div>`
    : `<div class="photo" style="left:0;top:0;width:${W}px;height:${H * (f === '1x1' ? .56 : .6)}px;background-image:url(${TEAM});background-position:${f === '1x1' ? '45% 35%' : '30% 30%'}"></div>
       <div style="position:absolute;left:0;top:${H * (f === '1x1' ? .56 : .6) - 240 * u}px;width:${W}px;height:${240 * u}px;background:linear-gradient(180deg,rgba(28,28,192,0),#1C1CC0)"></div>`;
  const panel = land ? `left:${W * .6}px;top:0;width:${W * .4}px;height:${H}px;padding:${90 * u}px ${80 * u}px` :
    `left:0;top:${H * (f === '1x1' ? .56 : .6)}px;width:${W}px;height:${H * (f === '1x1' ? .44 : .4)}px;padding:${(f === '1x1' ? 50 : 80) * u}px ${90 * u}px`;
  return `<div class="stage" style="width:${W}px;height:${H}px;background:#1C1CC0">${photo}
  <div style="position:absolute;${panel};background:var(--grad);display:flex;flex-direction:column;justify-content:space-between;color:#fff">
    <div>${logo(46 * u, true)}</div>
    <div>
      <div class="eyebrow" style="font-size:${22 * u}px;color:#9FEFFF;margin-bottom:${22 * u}px">Seria NotarAI · Komputerku…</div>
      <div style="font-weight:800;font-size:${(land ? 74 : 92) * u}px;line-height:1.02;letter-spacing:-.045em">Kancelaria<br>pod Siódemką</div>
      <div style="font-weight:500;font-size:${30 * u}px;margin-top:${24 * u}px;color:#DCEBFF">Odcinek 1 · Księga nadawcza w pięć minut</div>
    </div>
    <div style="font-weight:500;font-size:${19 * u}px;color:#BFD6FF">Postacie i kancelaria są fikcyjne · obraz wygenerowany przez AI</div>
  </div></div>`;
}

function outro(W, H, f) {
  const u = Math.min(W, H) / 1080;
  return `<div class="stage" style="width:${W}px;height:${H}px;background:var(--grad);color:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:${90 * u}px">
  <div style="position:absolute;inset:0;background:radial-gradient(circle at 78% 18%,rgba(0,207,255,.35),transparent 45%),radial-gradient(circle at 10% 95%,rgba(6,23,68,.45),transparent 50%)"></div>
  <div style="position:relative;display:flex;flex-direction:column;align-items:center;gap:${(f === '9x16' ? 60 : 38) * u}px">
    <div style="background:#fff;border-radius:${36 * u}px;padding:${26 * u}px ${44 * u}px">${logo(70 * u)}</div>
    <div style="font-weight:800;font-size:${(f === '16x9' ? 96 : 104) * u}px;letter-spacing:-.045em;line-height:1">Komputerku…</div>
    <div style="font-weight:500;font-size:${34 * u}px;line-height:1.35;max-width:${860 * u}px;color:#E3EEFF">NotarAI przygotuje projekt.<br>Decyzję zawsze podejmuje notariusz.</div>
    <div class="pill" style="background:#fff;color:var(--navy);font-weight:800;font-size:${46 * u}px;letter-spacing:-.03em;padding:${22 * u}px ${64 * u}px;box-shadow:0 ${20 * u}px ${50 * u}px rgba(6,23,68,.3)">notarai.pl</div>
  </div>
  <div style="position:absolute;bottom:${46 * u}px;left:0;right:0;font-weight:500;font-size:${19 * u}px;color:#BFD6FF">Postacie fikcyjne, wygenerowane przez AI · ekrany: demonstracja na danych fikcyjnych</div>
  </div>`;
}

function miniatura(W, H, f) {
  const u = Math.min(W, H) / 1080;
  const land = f === '16x9';
  return `<div class="stage" style="width:${W}px;height:${H}px;background:#0D193C">
  <div class="photo" style="inset:0;background-image:url(${TEAM});background-position:${land ? '50% 35%' : '32% 30%'}"></div>
  <div style="position:absolute;inset:0;background:${land ? 'linear-gradient(90deg,rgba(6,23,68,0) 30%,rgba(6,23,68,.92) 72%)' : 'linear-gradient(180deg,rgba(6,23,68,0) 38%,rgba(6,23,68,.94) 74%)'}"></div>
  <div style="position:absolute;${land ? `right:${80 * u}px;top:0;bottom:0;width:${W * .42}px;justify-content:center` : `left:${90 * u}px;right:${90 * u}px;bottom:${(f === '9x16' ? 260 : 80) * u}px`};display:flex;flex-direction:column;gap:${26 * u}px;color:#fff">
    <div class="pill" style="align-self:flex-start;background:var(--cyan);color:var(--deep);font-weight:800;font-size:${24 * u}px;padding:${10 * u}px ${26 * u}px;letter-spacing:.06em">ODCINEK 1</div>
    <div style="font-weight:800;font-size:${(f === '9x16' ? 104 : 86) * u}px;line-height:1;letter-spacing:-.045em">Komputerku,<br><span style="color:var(--cyan)">przygotuj</span><br>projekt…</div>
    <div style="font-weight:600;font-size:${30 * u}px;color:#DCEBFF">Księga nadawcza w pięć minut</div>
  </div>
  <div style="position:absolute;left:${(land ? 60 : 90) * u}px;top:${(f === '9x16' ? 150 : 60) * u}px;background:#fff;border-radius:${22 * u}px;padding:${14 * u}px ${24 * u}px">${logo(38 * u)}</div>
  </div>`;
}

// Nakładka na cały film: logo, belka z imieniem, znaczek AI (jak w rolkach Studia: prawy górny róg, pod paskiem aplikacji).
function overlay(W, H, f) {
  const u = Math.min(W, H) / 1080;
  const side = f === '9x16' ? 90 : 70;
  const top = f === '9x16' ? 210 : 60;
  return `<div class="stage" style="width:${W}px;height:${H}px">
  <div style="position:absolute;left:${side * u}px;top:${top * u}px;background:rgba(255,255,255,.94);border-radius:${18 * u}px;padding:${10 * u}px ${18 * u}px">${logo(30 * u)}</div>
  ${aiPill(u, W - side * u - 96 * u, top * u + 6 * u)}
  <div style="position:absolute;left:${side * u}px;bottom:${(f === '9x16' ? 430 : 90) * u}px;display:flex;align-items:stretch;background:#fff;border-radius:${20 * u}px;overflow:hidden;box-shadow:0 ${14 * u}px ${36 * u}px rgba(6,23,68,.28)">
    <div style="width:${12 * u}px;background:var(--grad)"></div>
    <div style="padding:${18 * u}px ${30 * u}px">
      <div style="font-weight:800;font-size:${38 * u}px;letter-spacing:-.03em;color:var(--navy)">Helena</div>
      <div style="font-weight:600;font-size:${22 * u}px;color:var(--muted);margin-top:${4 * u}px">pani rejent · postać fikcyjna</div>
    </div>
  </div></div>`;
}
const aiPill = (u, x, y) => `<div class="pill" style="position:absolute;left:${x}px;top:${y}px;width:${96 * u}px;height:${54 * u}px;border-radius:${15 * u}px;background:rgba(0,0,0,.3);border:${2 * u}px solid rgba(255,255,255,.7);color:#fff;font-weight:800;font-size:${30 * u}px;letter-spacing:.02em">AI</div>`;

// Oznaczenie AI na pierwsze 5 s (osobna warstwa; wchodzi od 0 s, schodzi ok. 5 s).
function oznaczenieAI(W, H, f) {
  const u = Math.min(W, H) / 1080;
  const side = f === '9x16' ? 90 : 70;
  const top = f === '9x16' ? 300 : (f === '1x1' ? 130 : 120);
  return `<div class="stage" style="width:${W}px;height:${H}px">
  <div style="position:absolute;left:${side * u}px;right:${side * u}px;top:${top * u}px;display:flex;justify-content:center">
   <div style="display:flex;align-items:center;gap:${22 * u}px;background:rgba(6,23,68,.78);border:${2 * u}px solid rgba(255,255,255,.35);border-radius:${26 * u}px;padding:${20 * u}px ${30 * u}px;color:#fff;max-width:${(f === '16x9' ? 1100 : 900) * u}px">
    <div class="pill" style="flex:none;width:${84 * u}px;height:${50 * u}px;border-radius:${14 * u}px;background:var(--cyan);color:var(--deep);font-weight:800;font-size:${28 * u}px">AI</div>
    <div>
      <div style="font-weight:800;font-size:${31 * u}px;letter-spacing:-.02em;line-height:1.15">Treść wygenerowana przez AI</div>
      <div style="font-weight:500;font-size:${22 * u}px;color:#CFE0FF;margin-top:${6 * u}px;line-height:1.3">Postacie i kancelaria są fikcyjne. Ekrany NotarAI pokazano na danych testowych.</div>
    </div>
   </div>
  </div></div>`;
}

// ── Grafika systemowa ───────────────────────────────────────────────────────
function statusBar(W, H, icon, text, sub, iconBg) {
  return `<div class="stage" style="width:${W}px;height:${H}px;padding:20px">
  <div style="height:100%;display:flex;align-items:center;gap:34px;background:#fff;border:2px solid var(--stroke);border-radius:36px;padding:0 44px;box-shadow:0 16px 40px rgba(10,40,91,.14)">
    <div class="mic" style="width:116px;height:116px;background:${iconBg}">${icon}</div>
    <div style="flex:1">
      <div style="font-weight:800;font-size:58px;letter-spacing:-.035em;color:var(--navy);line-height:1.05">${text}</div>
      ${sub ? `<div style="font-weight:600;font-size:24px;color:var(--muted);margin-top:8px">${sub}</div>` : ''}
    </div>
    ${text.startsWith('Słucham') || text.startsWith('Już') ? `<div style="width:190px;height:80px">${wave()}</div>` : ''}
  </div></div>`;
}
const dymek = (W, H) => `<div class="stage" style="width:${W}px;height:${H}px;padding:20px 20px 20px">
  <div style="height:100%;display:flex;align-items:center;gap:36px;background:var(--grad);border-radius:44px 44px 44px 12px;padding:0 50px;box-shadow:0 18px 44px rgba(28,28,192,.32)">
   <div class="mic" style="width:120px;height:120px;background:#fff">${micSvg('#1C1CC0')}</div>
   <div style="font-weight:800;font-size:72px;letter-spacing:-.04em;color:#fff">Komputerku…</div>
   <div style="flex:1"></div><div style="width:220px;height:90px">${wave()}</div>
  </div></div>`;
const mikrofon = (W, H) => `<div class="stage" style="width:${W}px;height:${H}px;display:flex;align-items:center;justify-content:center">
  <div style="position:absolute;width:440px;height:440px;border-radius:50%;border:6px solid rgba(0,207,255,.35)"></div>
  <div style="position:absolute;width:380px;height:380px;border-radius:50%;border:6px solid rgba(0,207,255,.6)"></div>
  <div class="mic" style="width:310px;height:310px;background:var(--grad);box-shadow:0 24px 60px rgba(28,28,192,.35)">${micSvg()}</div></div>`;

function uiMakieta(W, H) {
  const item = (t, a) => `<div style="padding:16px 26px;border-radius:14px;font-weight:${a ? 700 : 500};font-size:25px;color:${a ? 'var(--blue)' : 'var(--muted)'};background:${a ? '#E8F0FF' : 'transparent'}">${t}</div>`;
  const card = (t, s) => `<div style="display:flex;gap:22px;align-items:center;border:2px solid var(--stroke);border-radius:18px;padding:26px 26px;background:#fff">
     <div style="width:58px;height:58px;border-radius:50%;border:4px solid var(--cyan);background:var(--bg);flex:none"></div>
     <div><div style="font-weight:800;font-size:30px;letter-spacing:-.02em;color:var(--navy)">${t}</div><div style="font-weight:500;font-size:21px;color:var(--muted);margin-top:6px">${s}</div></div></div>`;
  return `<div class="stage" style="width:${W}px;height:${H}px;padding:24px;background:#fff">
  <div style="display:flex;height:100%;border:2px solid var(--stroke);border-radius:26px;overflow:hidden">
   <div style="width:356px;background:var(--bg);padding:36px 22px;display:flex;flex-direction:column;gap:6px">
     <div style="padding:0 12px 34px">${logo(44)}</div>
     ${['Panel główny', 'Moje sprawy', 'Dokumenty', 'Sprawdzenia AML', 'Księgi i repertoria', 'Przesyłki', 'Poświadczenia', 'GIIF'].map((t, i) => item(t, i === 1)).join('')}
   </div>
   <div style="flex:1;padding:70px 60px 40px;position:relative">
     <div style="font-weight:800;font-size:56px;letter-spacing:-.045em;color:var(--navy)">Witaj w notarai</div>
     <div style="font-weight:500;font-size:24px;color:var(--muted);margin-top:8px">Dokumenty i sprawy kancelarii w jednym miejscu.</div>
     <div style="display:flex;align-items:center;gap:28px;margin-top:44px;background:var(--bg);border:2px solid var(--stroke);border-radius:18px;padding:22px 30px">
       <div class="mic" style="width:62px;height:62px">${micSvg()}</div>
       <div style="font-weight:600;font-size:27px;color:var(--ink)">Komputerku, przygotuj projekt…</div>
     </div>
     <div style="display:grid;grid-template-columns:1fr 1fr;gap:26px;margin-top:44px">
       ${card('Moje sprawy', 'Odczyt i projekty')}${card('Dokumenty', 'Analiza skanów')}${card('AML / PEP', 'Weryfikacja stron')}${card('Wniosek KW', 'Pakiet do portalu')}
     </div>
     <div style="position:absolute;right:34px;bottom:30px;transform:rotate(-4deg);border:4px solid var(--alert,#B52E44);color:#B52E44;border-radius:14px;padding:10px 22px;font-weight:800;font-size:26px;letter-spacing:.08em;background:rgba(255,255,255,.9)">MAKIETA POGLĄDOWA<div style="font-weight:600;font-size:16px;letter-spacing:.02em;margin-top:2px">nie jest zrzutem ekranu aplikacji</div></div>
   </div>
  </div></div>`;
}

// ── Marka ───────────────────────────────────────────────────────────────────
const logoPoziome = (W, H, dark) => `<div class="stage" style="width:${W}px;height:${H}px;display:flex;align-items:center;justify-content:center;${dark ? 'background:transparent' : ''}">${logo(112, dark)}</div>`;

const CAST = [['helena', 'Helena', 'pani rejent, 56'], ['marta', 'Marta', 'notariuszka, 38'], ['basia', 'Basia', 'sekretariat, 51'], ['kuba', 'Kuba', 'aplikant, 28']];
function obsada(W, H) {
  return `<div class="stage" style="width:${W}px;height:${H}px;background:var(--bg);padding:56px 60px">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <div><div class="eyebrow" style="font-size:20px;color:var(--blue)">Stała obsada · Kancelaria pod Siódemką</div>
    <div style="font-weight:800;font-size:54px;letter-spacing:-.045em;color:var(--navy);margin-top:8px">Bohaterowie serii „Komputerku…”</div></div>
    ${logo(40)}
  </div>
  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:28px;margin-top:40px">
   ${CAST.map(([k, n, r]) => `<div style="background:#fff;border:2px solid var(--stroke);border-radius:24px;padding:14px;overflow:hidden">
     <div style="height:520px;border-radius:14px;background:url(${REF(k)}) center 25%/cover"></div>
     <div style="padding:18px 8px 6px"><div style="font-weight:800;font-size:36px;letter-spacing:-.03em;color:var(--navy)">${n}</div>
     <div style="font-weight:600;font-size:21px;color:var(--muted);margin-top:4px">${r}</div></div></div>`).join('')}
  </div>
  <div style="margin-top:26px;font-weight:500;font-size:19px;color:var(--muted)">Postacie fikcyjne, wygenerowane przez AI. Nie przedstawiają prawdziwych notariuszy ani pracowników kancelarii.</div>
  </div>`;
}

function keyVisual(W, H) {
  return `<div class="stage" style="width:${W}px;height:${H}px;background:var(--grad)">
  <div class="photo" style="right:0;top:0;width:${W * .66}px;height:${H}px;background-image:url(${TEAM});background-position:40% 40%;-webkit-mask-image:linear-gradient(90deg,transparent,#000 32%);mask-image:linear-gradient(90deg,transparent,#000 32%)"></div>
  <div style="position:absolute;left:110px;top:0;bottom:0;width:${W * .38}px;display:flex;flex-direction:column;justify-content:center;gap:34px;color:#fff">
    <div style="align-self:flex-start;background:#fff;border-radius:26px;padding:16px 28px">${logo(52)}</div>
    <div style="font-weight:800;font-size:120px;letter-spacing:-.05em;line-height:.98">Komputerku…</div>
    <div style="font-weight:500;font-size:36px;line-height:1.35;color:#E3EEFF">Projekt przygotuje NotarAI.<br>Decyzję podejmuje notariusz.</div>
    <div style="display:flex;align-items:center;gap:22px;background:#fff;border-radius:24px;padding:18px 26px;align-self:flex-start;box-shadow:0 18px 40px rgba(6,23,68,.3)">
      <div class="mic" style="width:64px;height:64px">${micSvg()}</div>
      <div style="font-weight:700;font-size:30px;color:var(--navy)">Już sprawdzam…</div>
      <div style="width:120px;height:46px">${wave()}</div>
    </div>
  </div>
  <div style="position:absolute;right:40px;bottom:30px;font-weight:500;font-size:18px;color:#fff;text-shadow:0 1px 6px rgba(0,0,0,.5)">Postacie fikcyjne · obraz wygenerowany przez AI</div>
  </div>`;
}

function brandBoard(W, H) {
  const sw = [['NAVY', '#071D49'], ['INDIGO', '#1C1CC0'], ['BLUE', '#2B52D9'], ['AZURE', '#2197D3'], ['CYAN', '#00CFFF'], ['BG', '#F5F7FC'], ['STROKE', '#D9E5F4']];
  const box = (inner, st = '') => `<div style="background:#fff;border:2px solid var(--stroke);border-radius:26px;padding:34px;${st}">${inner}</div>`;
  const h = (t) => `<div class="eyebrow" style="font-size:20px;color:var(--blue);margin-bottom:22px">${t}</div>`;
  const st = (icon, bg, t) => `<div style="display:flex;align-items:center;gap:20px;border:2px solid var(--stroke);border-radius:18px;padding:16px 22px;margin-bottom:14px">
     <div class="mic" style="width:56px;height:56px;background:${bg}">${icon}</div><div style="font-weight:800;font-size:30px;letter-spacing:-.03em;color:var(--navy)">${t}</div></div>`;
  return `<div class="stage" style="width:${W}px;height:${H}px;background:var(--bg);padding:30px;display:grid;grid-template-columns:1.08fr 1fr;grid-template-rows:118px 400px 1fr;gap:26px">
  ${box(`<div style="display:flex;align-items:center;justify-content:space-between;height:100%">${logo(50)}<div style="font-weight:800;font-size:46px;letter-spacing:-.04em;color:var(--navy)">Kampania · Komputerku…</div></div>`, 'grid-column:1/3;padding:22px 40px')}
  ${box(`<div style="height:100%;border-radius:16px;background:url(${TEAM}) center 38%/cover"></div>`, 'padding:14px')}
  ${box(`${h('Kolor z produktu')}<div style="display:flex;gap:14px">${sw.map(([n, c]) => `<div style="flex:1"><div style="height:110px;border-radius:16px;background:${c};border:2px solid var(--stroke)"></div><div style="font-weight:700;font-size:16px;color:var(--muted);margin-top:10px">${n}</div><div style="font-weight:600;font-size:15px;color:var(--ink)">${c}</div></div>`).join('')}</div>
     <div style="margin-top:34px;display:flex;align-items:baseline;gap:26px"><div style="font-weight:800;font-size:64px;letter-spacing:-.05em;color:var(--navy)">Aa</div><div style="font-weight:600;font-size:22px;color:var(--muted)">Montserrat 500 / 600 / 800 · nagłówki z ciasnym światłem (−0,045 em)</div></div>`)}
  ${box(`${h('Bohaterowie i stała scenografia')}<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:18px">${CAST.map(([k, n, r]) => `<div><div style="height:390px;border-radius:14px;background:url(${REF(k)}) center 25%/cover"></div><div style="font-weight:800;font-size:28px;color:var(--navy);margin-top:12px">${n}</div><div style="font-weight:600;font-size:17px;color:var(--muted)">${r}</div></div>`).join('')}</div>`)}
  ${box(`${h('Język animacji i plansz')}${st(micSvg(), 'var(--indigo)', 'Słucham…')}${st(barsSvg, 'var(--blue)', 'Już sprawdzam…')}${st(checkSvg, 'var(--success)', 'Projekt do weryfikacji')}
     <div style="font-weight:600;font-size:21px;color:var(--muted);margin-top:22px">Polecenie → działanie → rezultat do kontroli notariusza</div>
     <div style="font-weight:500;font-size:17px;color:var(--muted);margin-top:14px">Postacie fikcyjne, wygenerowane przez AI. Oryginalny sygnet NotarAI bez zmian.</div>`)}
  </div>`;
}

// ── Lista zadań renderu ─────────────────────────────────────────────────────
const jobs = [];
for (const [f, [W, H]] of Object.entries(FMT)) {
  jobs.push([`03_plansze_video/${f}/INTRO_kancelaria_pod_siodemka.png`, W, H, intro(W, H, f), false]);
  jobs.push([`03_plansze_video/${f}/OUTRO_komputerku.png`, W, H, outro(W, H, f), false]);
  jobs.push([`03_plansze_video/${f}/MINIATURA_odcinek_przyklad.png`, W, H, miniatura(W, H, f), false]);
  jobs.push([`03_plansze_video/${f}/OVERLAY_TRANSPARENT.png`, W, H, overlay(W, H, f), true]);
  jobs.push([`03_plansze_video/${f}/OZNACZENIE_AI_pierwsze_5s.png`, W, H, oznaczenieAI(W, H, f), true]);
}
jobs.push(['04_grafika_systemowa/dymek_komputerku_transparent.png', 1280, 220, dymek(1280, 220), true]);
jobs.push(['04_grafika_systemowa/mikrofon_komputerku_transparent.png', 512, 512, mikrofon(512, 512), true]);
jobs.push(['04_grafika_systemowa/status_slucham_transparent.png', 1180, 220, statusBar(1180, 220, micSvg(), 'Słucham…', 'Komputerku, przygotuj projekt…', 'var(--indigo)'), true]);
jobs.push(['04_grafika_systemowa/status_sprawdzam_transparent.png', 1180, 220, statusBar(1180, 220, barsSvg, 'Już sprawdzam…', 'Czytam akta sprawy', 'var(--blue)'), true]);
jobs.push(['04_grafika_systemowa/status_gotowe_transparent.png', 1180, 220, statusBar(1180, 220, checkSvg, 'Projekt do weryfikacji', 'Decyzję podejmuje notariusz', 'var(--success)'), true]);
jobs.push(['04_grafika_systemowa/ui_koncepcyjne_zgodne_z_kolorystyka.png', 1500, 900, uiMakieta(1500, 900), false]);
jobs.push(['01_marki/logo_kampanijne_poziome_light.png', 1000, 230, logoPoziome(1000, 230, false), true]);
jobs.push(['01_marki/logo_kampanijne_poziome_dark.png', 1000, 230, logoPoziome(1000, 230, true), true]);
jobs.push(['01_marki/KEY_VISUAL_16x9.png', 2000, 1100, keyVisual(2000, 1100), false]);
jobs.push(['01_marki/BRAND_BOARD_POPRAWIONY.png', 1920, 1280, brandBoard(1920, 1280), false]);
jobs.push(['02_bohaterowie/obsada_4_postacie.png', 1600, 980, obsada(1600, 980), false]);

(async () => {
  const only = process.env.ONLY;
  const browser = await chromium.launch();
  const page = await browser.newPage({ deviceScaleFactor: 1 });
  for (const [out, W, H, body, transparent] of jobs) {
    if (only && !out.includes(only)) continue;
    await page.setViewportSize({ width: W, height: H });
    const tmp = path.join(__dirname, '_tmp.html');
    fs.writeFileSync(tmp, `<!doctype html><html lang="pl"><head><meta charset="utf-8"><style>${CSS}</style></head><body>${body}</body></html>`);
    await page.goto('file://' + tmp, { waitUntil: 'load' });
    await page.evaluate(() => Promise.all([...document.fonts].map((f) => f.load().catch(() => null))));
    await page.evaluate(() => document.fonts.ready);
    const ok = await page.evaluate(() => [...document.fonts].some((f) => f.family.includes('Montserrat') && f.weight === '800' && f.status === 'loaded'));
    if (!ok) throw new Error('Montserrat nie załadowany: ' + out);
    const dest = path.join(OUT, out);
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    await page.screenshot({ path: dest, omitBackground: transparent, clip: { x: 0, y: 0, width: W, height: H } });
    console.log('ok', out);
  }
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
