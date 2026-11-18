// Nagranie ujęcia u5 odcinka 1 z PRAWDZIWEJ aplikacji NotarAI (widok „Przesyłki
// i korespondencja”, układ telefonu 9:16) z nałożonym paskiem trybu „Komputerku…”.
// Na końcu pokazujemy prawdziwy PDF pocztowej książki nadawczej, który aplikacja
// wygenerowała z dzisiejszych wpisów (dane testowe).
//
// Wymaga działającej aplikacji (python app.py, port 8000) z wpisami testowymi
// i PNG pierwszej strony PDF (/api/przesylki/ksiazka-nadawcza.pdf?dzien=…).
// Użycie: node nagraj_komputerku.js <pdf_png> <katalog_klatek> [sekundy=9.6] [fps=25]
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const [PDF_PNG, OUT, SEK = '9.6', FPS = '25'] = process.argv.slice(2);
const POLECENIE = 'Komputerku, przygotuj książkę nadawczą z dzisiejszych przesyłek.';
const clamp = (x) => Math.max(0, Math.min(1, x));
const ease = (x) => { x = clamp(x); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const pdf = 'data:image/png;base64,' + fs.readFileSync(PDF_PNG).toString('base64');
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 432, height: 768 }, deviceScaleFactor: 2.5 });
  await page.goto('http://127.0.0.1:8000/', { waitUntil: 'networkidle' });
  await page.evaluate(() => document.querySelector(".krok[data-etap='8']").click());
  await page.waitForTimeout(1500);

  // Pozycje w przewijanym <main> (liczone na żywo, żeby nie zgadywać).
  const poz = await page.evaluate(() => {
    const m = document.querySelector('main');
    const top = (el) => el.getBoundingClientRect().top + m.scrollTop - m.getBoundingClientRect().top;
    const s = document.getElementById('etap8');
    const h2 = [...s.querySelectorAll('h2')];
    const wpisy = h2.find((e) => e.innerText.trim() === 'Wpisy');
    const wydruki = h2.find((e) => e.innerText.trim() === 'Wydruki');
    const tabela = s.querySelector('table');
    return { wpisy: Math.max(top(wpisy) - 70, top(tabela) - 120), wydruki: top(wydruki) - 90, max: m.scrollHeight - m.clientHeight };
  });

  // Pasek „Komputerku” i arkusz z PDF — w stylu aplikacji (granat, gradient, białe karty).
  await page.addStyleTag({ content: `
    #komp{position:fixed;left:12px;right:12px;bottom:12px;z-index:99999;font-family:Inter,Montserrat,system-ui,sans-serif;
      background:#fff;border:1px solid #cbd9f1;border-radius:22px;padding:14px 16px;box-shadow:0 18px 50px -18px rgba(13,25,60,.45)}
    #komp .row{display:flex;gap:12px;align-items:center}
    #komp .ico{width:46px;height:46px;border-radius:50%;flex:none;display:flex;align-items:center;justify-content:center;background:linear-gradient(115deg,#1c1cc0,#2463cc 54%,#2197d3)}
    #komp .lab{font-weight:800;font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#2463cc}
    #komp .txt{font-weight:600;font-size:15px;line-height:1.3;color:#0d193c;margin-top:2px}
    #komp .bars{display:flex;gap:3px;align-items:center;height:30px;margin-left:auto}#komp .bars i{width:3px;border-radius:3px;background:#2197d3}
    #komp .spin{width:22px;height:22px;border-radius:50%;border:3px solid rgba(255,255,255,.35);border-top-color:#fff}
    #komp .steps{margin-top:10px;display:flex;flex-direction:column;gap:6px;font-size:13px;font-weight:600;color:#0d193c}
    #komp .steps div{display:flex;gap:8px;align-items:center}#komp .steps b{width:18px;height:18px;border-radius:50%;background:#23764b;color:#fff;font-size:11px;display:flex;align-items:center;justify-content:center}
    #komp .steps em{font-style:normal;margin-left:auto;color:#647392;font-weight:500}
    #arkusz{position:fixed;left:12px;right:12px;top:72px;bottom:150px;z-index:99998;background:#fff;border:1px solid #cbd9f1;border-radius:20px;overflow:hidden;
      box-shadow:0 24px 60px -20px rgba(13,25,60,.5)}
    #arkusz .h{padding:12px 14px;border-bottom:1px solid #e3ebf7;font-family:Inter,system-ui,sans-serif;display:flex;justify-content:space-between;align-items:center}
    #arkusz .h b{font-size:14px;color:#0d193c}#arkusz .h span{font-size:12px;color:#647392}
    #arkusz img{width:175%;max-width:none;display:block}
    .komp-hl{outline:3px solid #2197d3 !important;outline-offset:3px;border-radius:12px}
    tr.komp-row td{background:#e8f4fd !important;transition:none}
  `});
  await page.evaluate(() => { const d = document.createElement('div'); d.id = 'komp'; document.body.appendChild(d); });

  const mic = '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v4"/></svg>';
  const check = '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round"><path d="M5 12.5l4.2 4.2L19 7"/></svg>';

  const n = Math.round(Number(SEK) * Number(FPS));
  for (let i = 0; i < n; i++) {
    const t = i / Number(FPS);
    // Przewijanie: góra → tabela wpisów (2.2–3.6 s) → wydruki (5.2–6.4 s).
    let y = 0;
    if (t >= 2.2) y = poz.wpisy * ease((t - 2.2) / 1.4);
    if (t >= 5.2) y = poz.wpisy + (poz.wydruki - poz.wpisy) * ease((t - 5.2) / 1.2);
    const rowsLit = t >= 3.7 && t < 5.4 ? Math.min(3, Math.floor((t - 3.7) / 0.35) + 1) : 0;
    const hlBtn = t >= 6.4 && t < 7.0;
    const pdfOp = ease((t - 6.9) / 0.6);
    const pan = ease((t - 7.6) / 1.9);
    const gotowe = t >= 7.2;
    const sluchanie = t < 1.8;
    const typed = POLECENIE.slice(0, Math.round(POLECENIE.length * clamp(t / 1.6)));
    const bars = sluchanie ? `<div class="bars">${Array.from({ length: 9 }, (_, k) => `<i style="height:${8 + 20 * Math.abs(Math.sin(t * 9 + k))}px"></i>`).join('')}</div>` : '';
    const steps = [[2.6, 'Dziennik przesyłanych dokumentów', '3 polecone'], [3.3, 'Dziennik korespondencyjny', '4 polecone'], [4.6, 'Zestawienie na dziś', '7 przesyłek']]
      .filter(([s]) => t >= s && !gotowe).map(([, a, b]) => `<div><b>✓</b>${a}<em>${b}</em></div>`).join('');
    const ico = gotowe ? `<div class="ico" style="background:#23764b">${check}</div>`
      : sluchanie ? `<div class="ico">${mic}</div>` : `<div class="ico"><div class="spin" style="transform:rotate(${t * 420}deg)"></div></div>`;
    const lab = gotowe ? '<span style="color:#23764b">Projekt do weryfikacji</span>' : sluchanie ? 'Słucham…' : 'Już sprawdzam…';
    const txt = gotowe ? 'Książka nadawcza na 12.11.2026 — 7 przesyłek z obu dzienników. Wydruk i nadanie zatwierdza notariusz.'
      : `„${typed}${sluchanie ? '▍' : ''}”`;
    const slide = ease(t / 0.35);
    await page.evaluate(({ pan, y, html, rowsLit, hlBtn, pdfOp, pdf, slide }) => {
      const m = document.querySelector('main'); m.scrollTop = y;
      const k = document.getElementById('komp'); k.innerHTML = html; k.style.transform = `translateY(${(1 - slide) * 160}px)`;
      document.querySelectorAll('#etap8 table tr').forEach((tr, j) => tr.classList.toggle('komp-row', j > 0 && j <= rowsLit));
      const btn = [...document.querySelectorAll('#etap8 button')].find((b) => b.innerText.trim() === 'Drukuj książkę nadawczą');
      if (btn) btn.classList.toggle('komp-hl', hlBtn);
      let a = document.getElementById('arkusz');
      if (pdfOp > 0) {
        if (!a) { a = document.createElement('div'); a.id = 'arkusz'; a.innerHTML = `<div class="h"><b>Pocztowa książka nadawcza.pdf</b><span>podgląd</span></div><img src="${pdf}">`; document.body.appendChild(a); }
        a.style.opacity = pdfOp; a.style.transform = `translateY(${(1 - pdfOp) * 40}px)`;
        a.querySelector('img').style.transform = `translateX(${-pan * 22}%)`;
      } else if (a) a.remove();
    }, { pan, y, html: `<div class="row">${ico}<div><div class="lab">${lab}</div><div class="txt">${txt}</div></div>${bars}</div>${steps ? `<div class="steps">${steps}</div>` : ''}`, rowsLit, hlBtn, pdfOp, pdf, slide });
    await page.screenshot({ path: path.join(OUT, `f_${String(i).padStart(4, '0')}.png`) });
  }
  await browser.close();
  console.log('klatki:', n, JSON.stringify(poz));
})().catch((e) => { console.error(e); process.exit(1); });
