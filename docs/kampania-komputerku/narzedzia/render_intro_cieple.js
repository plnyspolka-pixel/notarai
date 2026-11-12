// Intro v2 „Kancelaria pod Siódemką”: ciepłe, witające. Postacie obsady-v2 same witają widza
// (HeyGen Avatar 6 Model API z kadrów wzorcowych + głosy ElevenLabs v2), złote światło z okna,
// miękkie przenikania, ciepła muzyka (ElevenLabs Music). Marka: oryginalne logo i znaczek „AI”.
//
// Użycie: node render_intro_cieple.js <fonty_montserrat> <katalog_klipow> <wyjscie> [nr …]
//   <katalog_klipow>: helena.mp4 basia.mp4 kuba.mp4 marta.mp4 marta_witamy.mp4 (ujęcia mówione 1080x1920)
//                     oraz muzyka.mp3 (podkład). Klatki ujęć wyciągane są do .robocze/klatki.
//   EPIZOD="Odcinek 1 · Księga nadawcza w pięć minut"  (pusty = bez podtytułu)
const fs = require('fs');
const path = require('path');
const { spawn, execFileSync } = require('child_process');
const { chromium } = require('playwright');

const K = path.resolve(__dirname, '..');
const PAK = path.join(K, 'pakiet');
const [FONTS, KLIPY, OUT, ...WYBOR] = process.argv.slice(2);
if (!FONTS || !KLIPY || !OUT) { console.error('node render_intro_cieple.js <fonty> <klipy> <wyjscie> [1..5]'); process.exit(1); }
const EPIZOD = process.env.EPIZOD ?? 'Odcinek 1 · Księga nadawcza w pięć minut';
const AMB = path.join(K, 'glosy_v2/zrodla/ambience_kancelaria_22s.mp3');
const MUZ = path.join(KLIPY, 'muzyka.mp3');
const W = 1080, H = 1920, FPS = 30;
const TMP = path.join(OUT, '.robocze'); fs.mkdirSync(path.join(TMP, 'klatki'), { recursive: true });
const furl = (p) => 'file://' + p;
const pk = (p) => furl(path.join(PAK, p));
const IMG = {
  K1: pk('09_scenografia_v2/plansze/K1.jpg'), K7: pk('09_scenografia_v2/plansze/K7.jpg'),
  K8: pk('09_scenografia_v2/plansze/K8.jpg'), K9: pk('09_scenografia_v2/plansze/K9.jpg'),
  helena: pk('10_obsada_v2/postacie/helena/kadr_K2m.jpg'), marta: pk('10_obsada_v2/postacie/marta/kadr_K5m.jpg'),
  basia: pk('10_obsada_v2/postacie/basia/kadr_K3m.jpg'), kuba: pk('10_obsada_v2/postacie/kuba/kadr_K6m.jpg'),
  sygnet: pk('01_marki/oryginalny_sygnet_z_repo.svg'),
  pasek: furl(path.join(K, 'narzedzia/warstwy/warstwa_logo_ai.png')),
};

// ── ujęcia mówione → klatki ─────────────────────────────────────────────────
const KLIP = {};
for (const n of ['helena', 'basia', 'kuba', 'marta', 'marta_witamy']) {
  const src = path.join(KLIPY, `${n}.mp4`), dir = path.join(TMP, 'klatki', n);
  if (!fs.existsSync(src)) continue;
  if (!fs.existsSync(path.join(dir, '0001.jpg'))) {
    fs.mkdirSync(dir, { recursive: true });
    execFileSync('ffmpeg', ['-v', 'error', '-y', '-i', src, '-vf', `fps=${FPS},scale=${W}:${H}:force_original_aspect_ratio=increase,crop=${W}:${H}`, '-q:v', '3', path.join(dir, '%04d.jpg')]);
  }
  const n_kl = fs.readdirSync(dir).filter((x) => x.endsWith('.jpg')).length;
  KLIP[n] = { dir, n: n_kl, D: n_kl / FPS, audio: src };
}
// klatka ujęcia w chwili lt (po końcu trzyma ostatnią — „zamrożony uśmiech” z lekkim najazdem)
const klatka = (n, lt) => { const k = KLIP[n]; const i = Math.max(1, Math.min(k.n, Math.floor(lt * FPS) + 1)); return furl(path.join(k.dir, String(i).padStart(4, '0') + '.jpg')); };

// ── ruch ────────────────────────────────────────────────────────────────────
const cl = (x) => Math.max(0, Math.min(1, x));
const outC = (x) => 1 - Math.pow(1 - cl(x), 3);
const io = (x) => { x = cl(x); return x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
const p = (t, a, d) => cl((t - a) / d);
const lerp = (a, b, x) => a + (b - a) * x;
const wej = (t, a, d = .5, dy = 24) => `opacity:${outC(p(t, a, d))};transform:translateY(${(1 - outC(p(t, a, d))) * dy}px)`;
// pseudolosowe, ale powtarzalne
const rnd = (i, s = 1) => { const x = Math.sin(i * 127.1 + s * 311.7) * 43758.5453; return x - Math.floor(x); };

// ── CSS ─────────────────────────────────────────────────────────────────────
const fontFaces = [500, 600, 700, 800].map((w) => `
@font-face{font-family:Montserrat;font-weight:${w};src:url(file://${path.resolve(FONTS, `montserrat-latin-ext-${w}-normal.woff2`)}) format('woff2');unicode-range:U+0100-02AF,U+0304,U+0308,U+0329,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF;}
@font-face{font-family:Montserrat;font-weight:${w};src:url(file://${path.resolve(FONTS, `montserrat-latin-${w}-normal.woff2`)}) format('woff2');}`).join('');
const CSS = `${fontFaces}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:${W}px;height:${H}px;overflow:hidden;background:#1b120b}
body{font-family:Montserrat,sans-serif;-webkit-font-smoothing:antialiased}
#s{position:absolute;inset:0;overflow:hidden}
.abs{position:absolute}
.ph{position:absolute;inset:0;background-size:cover;background-position:center}
.logo{display:inline-flex;align-items:center;gap:.3em;white-space:nowrap}
.logo img{width:1.55em;height:1.55em;display:block}
.logo b{font-weight:800;letter-spacing:-.055em;color:#071D49;line-height:1}
.logo b i{font-style:normal;color:#00BFE8}
.cien{text-shadow:0 2px 18px rgba(30,16,4,.55),0 1px 3px rgba(30,16,4,.45)}
`;
const logo = (px) => `<span class="logo" style="font-size:${px}px"><img src="${IMG.sygnet}"><b>notar<i>ai</i></b></span>`;
const logoKafel = (px) => `<span style="display:inline-flex;background:#fff;border-radius:${px * .5}px;padding:${px * .32}px ${px * .55}px;box-shadow:0 10px 30px rgba(30,16,4,.25)">${logo(px)}</span>`;
const pasek = (o = 1) => `<img class="abs" src="${IMG.pasek}" style="left:0;top:0;width:${W}px;height:${H}px;opacity:${o}">`;
const foto = (src, s, ox = 50, oy = 50, extra = '') => `<div class="ph" style="background-image:url(${src});transform-origin:${ox}% ${oy}%;transform:scale(${s});${extra}"></div>`;
const klipImg = (n, lt, s = 1, ox = 50, oy = 40) => `<img class="abs" src="${klatka(n, lt)}" style="left:0;top:0;width:${W}px;height:${H}px;transform-origin:${ox}% ${oy}%;transform:scale(${s})">`;

// Ciepła „gradacja”: złote światło z okna (prawa strona), winieta, drobny kurz w smudze światła.
function cieplo(t, sila = 1, kurz = true) {
  let h = `<div class="abs" style="inset:0;background:linear-gradient(180deg,rgba(255,196,120,.10),rgba(255,160,80,.10));mix-blend-mode:soft-light"></div>
  <div class="abs" style="inset:0;background:radial-gradient(ellipse 70% 55% at ${88 + 4 * Math.sin(t * .6)}% 22%,rgba(255,206,140,${.30 * sila}),rgba(255,190,110,0) 70%);mix-blend-mode:screen"></div>
  <div class="abs" style="inset:0;background:radial-gradient(ellipse 85% 75% at 50% 45%,rgba(0,0,0,0) 55%,rgba(36,20,8,${.42 * sila}) 100%)"></div>`;
  if (kurz) {
    for (let i = 0; i < 34; i++) {
      const x = 380 + rnd(i) * 700 + 30 * Math.sin(t * .5 + i);
      const y = ((rnd(i, 2) * H - t * (18 + rnd(i, 3) * 26)) % H + H) % H;
      const r = 2 + rnd(i, 4) * 4, a = (.18 + .35 * rnd(i, 5)) * (0.5 + 0.5 * Math.sin(t * 1.3 + i)) * sila;
      h += `<div class="abs" style="left:${x}px;top:${y}px;width:${r * 2}px;height:${r * 2}px;border-radius:50%;background:rgba(255,232,190,${a});filter:blur(${r * .6}px)"></div>`;
    }
  }
  return h;
}
// para nad filiżanką (K9, filiżanka ok. x=600, y=1010 w kadrze 1080x1920)
function para(t, x = 600, y = 1000, o = 1) {
  let h = '';
  for (let i = 0; i < 7; i++) {
    const f = ((t * .55 + i / 7) % 1);
    const xx = x + Math.sin(f * 5 + i * 1.7) * 22 * f + (rnd(i) - .5) * 20;
    const yy = y - f * 260;
    const r = 26 + f * 60;
    h += `<div class="abs" style="left:${xx - r}px;top:${yy - r}px;width:${r * 2}px;height:${r * 2}px;border-radius:50%;background:rgba(255,255,255,${.22 * Math.sin(f * Math.PI) * o});filter:blur(${14 + f * 18}px)"></div>`;
  }
  return h;
}
// tytuł serii, ciepło: biały z miękkim cieniem, kremowe akcenty
function tytul(t, a, { rozmiar = 104, srodek = true } = {}) {
  return `<div class="cien" style="text-align:${srodek ? 'center' : 'left'};color:#fff">
    <div style="font-weight:600;font-size:30px;letter-spacing:.08em;color:#FFE9C7;margin-bottom:22px;${wej(t, a, .6, 16)}">serial NotarAI</div>
    <div style="font-weight:800;font-size:${rozmiar}px;line-height:1.04;letter-spacing:-.035em">
      <div style="${wej(t, a + .15, .7, 30)}">Kancelaria</div>
      <div style="${wej(t, a + .32, .7, 30)}">pod Siódemką</div>
    </div>
    ${EPIZOD ? `<div style="font-weight:500;font-size:34px;margin-top:30px;color:#FFF4E2;${wej(t, a + .7, .6, 14)}">${EPIZOD}</div>` : ''}
  </div>`;
}
// dolna ciepła poświata pod tytułem
const poswiata = (o) => `<div class="abs" style="left:0;right:0;bottom:0;height:${H * .55}px;opacity:${o};background:linear-gradient(180deg,rgba(40,22,8,0) 0%,rgba(40,22,8,.55) 45%,rgba(30,16,6,.85) 100%)"></div>`;
// karta imienia: biała pigułka, bez gradientów
const imie = (t, a, n, r, mul = 1) => `<div class="abs" style="left:90px;top:1400px;opacity:${outC(p(t, a, .45)) * mul};transform:translateY(${(1 - outC(p(t, a, .45))) * 18}px)">
  <div style="display:inline-flex;align-items:baseline;gap:16px;background:rgba(255,255,255,.95);border-radius:999px;padding:18px 36px;box-shadow:0 12px 30px rgba(30,16,4,.25)">
    <span style="font-weight:800;font-size:46px;color:#071D49;letter-spacing:-.03em">${n}</span>
    <span style="font-weight:500;font-size:30px;color:#7A6A58">${r}</span></div></div>`;
// przenikanie: zwraca krycie warstwy wchodzącej
const xf = (t, a, d = .6) => io(p(t, a, d));

// ── 5 intro ─────────────────────────────────────────────────────────────────
// glosy: [klip, start]; muzyka od 0; D — długość
const INTRO = [];

// 1. Zaproszenie — wchodzimy przez drzwi, Helena podnosi wzrok i zaprasza.
INTRO.push({
  slug: '1_zaproszenie', nazwa: 'Helena zaprasza', D: 7.6, glosy: [['helena', 1.0]],
  scena(t) {
    const hS = 1.0, hl = t - hS;
    let h = foto(IMG.K7, lerp(1.0, 1.22, io(p(t, 0, 1.6))), 50, 52);
    h += `<div style="opacity:${xf(t, .7, .7)}">${klipImg('helena', hl, lerp(1.0, 1.06, io(p(t, hS, 6.5))), 50, 30)}</div>`;
    h += cieplo(t) + pasek(outC(p(t, .2, .6)));
    h += poswiata(outC(p(t, 4.6, .9)));
    h += `<div class="abs" style="left:90px;right:90px;bottom:200px">${tytul(t, 4.8)}</div>`;
    return `<div style="opacity:${outC(p(t, 0, .6))}">${h}</div>`;
  },
});

// 2. Kawa — poranna kawa na biurku, Basia odwraca się od drukarki i zaprasza.
INTRO.push({
  slug: '2_kawa', nazwa: 'Basia i kawa', D: 7.8, glosy: [['basia', 1.5]],
  scena(t) {
    const bS = 1.5, bl = t - bS;
    let h = foto(IMG.K9, lerp(1.0, 1.08, io(p(t, 0, 2.2))), 56, 52) + para(t, 610, 1010, 1 - xf(t, 1.2));
    h += `<div style="opacity:${xf(t, 1.2, .7)}">${klipImg('basia', bl, lerp(1.0, 1.05, io(p(t, bS, 6))), 40, 30)}</div>`;
    h += cieplo(t) + pasek(outC(p(t, .2, .6)));
    h += imie(t, 2.0, 'Basia', 'sekretariat', 1 - outC(p(t, 4.6, .4)));
    h += poswiata(outC(p(t, 5.0, .8)));
    h += `<div class="abs" style="left:90px;right:90px;bottom:200px">${tytul(t, 5.1)}</div>`;
    return `<div style="opacity:${outC(p(t, 0, .6))}">${h}</div>`;
  },
});

// 3. Cały zespół — każdy wita się po swojemu, na końcu wspólna karta.
INTRO.push({
  slug: '3_zespol', nazwa: 'Cały zespół się wita', D: 9.0,
  glosy: [['helena', 0.3, 1.1], ['marta_witamy', 1.55], ['kuba', 2.85], ['basia', 4.45]],
  scena(t) {
    const UJ = [['helena', .3, 1.25, 'Helena', 'pani rejent'], ['marta_witamy', 1.55, 1.3, 'Marta', 'notariuszka'],
      ['kuba', 2.85, 1.6, 'Kuba', 'aplikant'], ['basia', 4.45, 3.2, 'Basia', 'sekretariat']];
    let h = '';
    UJ.forEach(([n, a, d, im, rola], i) => {
      const od = i === 0 ? 0 : a - .25, wej_ = i === 0 ? 1 : xf(t, od, .35);
      if (t < od || t > a + d + .6) return;
      h += `<div style="opacity:${wej_}">${klipImg(n, t - a, lerp(1.03, 1.0, outC(p(t, od, d))), 50, 32)}</div>`;
      h += imie(t, a + .1, im, rola, 1 - outC(p(t, a + d - .3, .3)));
    });
    h += cieplo(t, .9) + pasek(outC(p(t, .1, .4)) * (1 - outC(p(t, 7.3, .4))));
    // karta zespołu
    const kS = 7.2, k = xf(t, kS - .2, .6);
    if (k > 0) {
      const C = 200, g = 34, x0 = (W - 4 * C - 3 * g) / 2;
      const twarze = [['helena', .50, .40, 3.4], ['marta', .45, .30, 3.2], ['basia', .46, .32, 3.4], ['kuba', .56, .25, 3.6]];
      h += `<div class="abs" style="inset:0;opacity:${k}">${foto(IMG.K1, lerp(1.12, 1.06, p(t, kS, 2)), 50, 60, 'filter:blur(14px) saturate(1.15) brightness(.9)')}
        <div class="abs" style="inset:0;background:rgba(40,22,8,.45)"></div>${cieplo(t, 1, false)}
        <div class="abs" style="left:0;right:0;top:220px;text-align:center;${wej(t, kS, .5, 12)}">${logoKafel(46)}</div>
        ${twarze.map(([n, fx, fy, s], i) => { const C2 = C - 10, iw = C2 * s, ih = iw * 2752 / 1536, o = outC(p(t, kS + .1 + i * .08, .45));
          return `<div class="abs" style="left:${x0 + i * (C + g)}px;top:560px;width:${C}px;height:${C}px;border-radius:50%;border:5px solid #FFF4E2;box-shadow:0 14px 34px rgba(30,16,4,.4);opacity:${o};transform:scale(${lerp(.8, 1, o)});background-image:url(${IMG[n]});background-size:${iw}px ${ih}px;background-position:${C2 / 2 - fx * iw}px ${C2 / 2 - fy * ih}px"></div>`; }).join('')}
        <div class="abs" style="left:80px;right:80px;top:880px">${tytul(t, kS + .3)}</div></div>`;
    }
    return `<div style="opacity:${outC(p(t, 0, .4))}">${h}</div>`;
  },
});

// 4. Poranek — słońce wpada przez okno, para nad kawą, Kuba wita w drzwiach biblioteki.
INTRO.push({
  slug: '4_poranek', nazwa: 'Poranek w kancelarii', D: 8.0, glosy: [['kuba', 3.9]],
  scena(t) {
    let h = foto(IMG.K8, lerp(1.0, 1.1, io(p(t, 0, 2.6))), 55, 40);
    // promienie słońca z okna
    h += `<div class="abs" style="inset:-200px;background:repeating-linear-gradient(115deg,rgba(255,226,170,0) 0 90px,rgba(255,226,170,${.10 + .05 * Math.sin(t * 1.4)}) 90px 150px,rgba(255,226,170,0) 150px 260px);filter:blur(22px);mix-blend-mode:screen;transform:translateX(${t * 12}px);opacity:${1 - xf(t, 1.9)}"></div>`;
    h += `<div style="opacity:${xf(t, 1.9, .7)}">${foto(IMG.K9, lerp(1.06, 1.0, io(p(t, 1.9, 2.2))), 56, 52)}${para(t, 610, 1010)}</div>`;
    h += `<div style="opacity:${xf(t, 3.6, .5)}">${klipImg('kuba', t - 3.9, lerp(1.04, 1.0, outC(p(t, 3.6, 3))), 70, 25)}</div>`;
    h += cieplo(t) + pasek(outC(p(t, .2, .6)));
    h += imie(t, 4.0, 'Kuba', 'aplikant', 1 - outC(p(t, 5.2, .4)));
    h += poswiata(outC(p(t, 5.3, .8)));
    h += `<div class="abs" style="left:90px;right:90px;bottom:200px">${tytul(t, 5.4)}</div>`;
    return `<div style="opacity:${outC(p(t, 0, .8))}">${h}</div>`;
  },
});

// 5. Komputerku — Marta prosi komputer, żeby się przywitał; dymek odpowiada „Dzień dobry!”.
INTRO.push({
  slug: '5_komputerku', nazwa: 'Komputerku, przywitaj się', D: 8.0, glosy: [['marta', .4]], dzwonek: 3.0,
  scena(t) {
    let h = klipImg('marta', t - .4, lerp(1.0, 1.07, io(p(t, 0, 7))), 50, 35);
    h += cieplo(t) + pasek(outC(p(t, .2, .5)));
    // ciepły dymek komputera: biały, zaokrąglony, pisze się litera po literze
    const tx = 'Dzień dobry! Miło Państwa widzieć.', ile = Math.floor(cl((t - 3.15) / 1.1) * tx.length);
    const o = outC(p(t, 2.95, .35)) * (1 - outC(p(t, 5.3, .4)));
    h += `<div class="abs" style="left:110px;right:110px;top:${lerp(1280, 1240, o)}px;opacity:${o}">
      <div style="background:#fff;border-radius:40px 40px 40px 10px;padding:34px 40px;box-shadow:0 20px 50px rgba(30,16,4,.30);display:flex;gap:26px;align-items:center">
        <div style="flex:none;width:96px;height:96px;border-radius:50%;background:#F5F7FC;border:2px solid #D9E5F4;display:flex;align-items:center;justify-content:center">
          <img src="${IMG.sygnet}" style="width:60px;height:60px"></div>
        <div style="font-weight:700;font-size:46px;line-height:1.2;color:#0D193C;letter-spacing:-.02em">${tx.slice(0, ile)}<span style="opacity:${ile < tx.length ? (Math.floor(t * 3) % 2) : 0};color:#2B52D9">|</span></div>
      </div></div>`;
    h += poswiata(outC(p(t, 5.3, .8)));
    h += `<div class="abs" style="left:90px;right:90px;bottom:200px">${tytul(t, 5.45)}</div>`;
    return `<div style="opacity:${outC(p(t, 0, .5))}">${h}</div>`;
  },
});

// ── dźwięk: muzyka + ambience + głosy (+ cichy dzwoneczek) ─────────────────
function dzwiek(intro, wideo, wynik) {
  const D = intro.D, IN = [], FC = [], mix = [];
  let n = 1;
  const add = (args, filtr) => { IN.push(...args); FC.push(`[${n}:a]${filtr}[a${n}]`); mix.push(`[a${n}]`); n++; };
  const ms = (s) => Math.round(s * 1000);
  add(['-i', MUZ], `atrim=0:${D},volume=0.55,afade=t=in:d=0.6,afade=t=out:st=${D - 1.2}:d=1.2,aformat=sample_rates=48000:channel_layouts=stereo`);
  add(['-stream_loop', '-1', '-i', AMB], `atrim=0:${D},volume=0.22,aformat=sample_rates=48000:channel_layouts=stereo`);
  for (const [k, start, dl] of intro.glosy) {
    add(['-i', KLIP[k].audio], `${dl ? `atrim=0:${dl},afade=t=out:st=${(dl - .08).toFixed(3)}:d=0.08,` : ''}aformat=sample_rates=48000:channel_layouts=stereo,volume=1.9,adelay=${ms(start)}|${ms(start)}`);
  }
  if (intro.dzwonek != null) {
    const e = '0.10*sin(2*PI*1568*t)*exp(-6*t)+0.07*sin(2*PI*2093*t)*exp(-7*t)+0.05*sin(2*PI*1046.5*t)*exp(-5*t)'.replace(/,/g, '\\,');
    add(['-f', 'lavfi', '-t', '1.2', '-i', `aevalsrc=${e}:s=48000`], `aformat=sample_rates=48000:channel_layouts=stereo,adelay=${ms(intro.dzwonek)}|${ms(intro.dzwonek)}`);
  }
  FC.push(`${mix.join('')}amix=inputs=${mix.length}:duration=first:normalize=0,atrim=0:${D},loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[a]`);
  execFileSync('ffmpeg', ['-y', '-v', 'error', '-i', wideo, ...IN, '-filter_complex', FC.join(';'),
    '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-movflags', '+faststart', '-t', String(D), wynik]);
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  const strona = path.join(TMP, 'scena_cieple.html');
  fs.writeFileSync(strona, `<!doctype html><html><head><meta charset="utf-8"><style>${CSS}</style></head><body><div id="s"></div>
    ${Object.values(IMG).map((u) => `<img src="${u}" style="position:absolute;width:1px;height:1px;opacity:0">`).join('')}</body></html>`);
  await page.goto(furl(strona));
  await page.evaluate(() => document.fonts.ready);
  await page.waitForLoadState('networkidle');
  const lista = WYBOR.length ? INTRO.filter((_, i) => WYBOR.includes(String(i + 1))) : INTRO;
  for (const intro of lista) {
    const surowy = path.join(TMP, `${intro.slug}_v.mp4`);
    const ff = spawn('ffmpeg', ['-y', '-v', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-',
      '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', '-r', String(FPS), surowy], { stdio: ['pipe', 'inherit', 'inherit'] });
    const N = Math.round(intro.D * FPS);
    for (let i = 0; i < N; i++) {
      await page.evaluate((html) => { document.getElementById('s').innerHTML = html; }, intro.scena(i / FPS));
      await page.evaluate(() => Promise.all([...document.images].map((im) => im.decode().catch(() => {}))));
      const buf = await page.screenshot({ type: 'jpeg', quality: 93 });
      if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
    }
    ff.stdin.end(); await new Promise((r, j) => ff.on('close', (c) => (c ? j(new Error('ffmpeg ' + c)) : r())));
    const wynik = path.join(OUT, `INTRO_${intro.slug}_9x16.mp4`);
    dzwiek(intro, surowy, wynik);
    console.log(`${intro.nazwa}: ${wynik}`);
  }
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
