"""Strona /przygotuj-sprawe/: klient przygotowuje sprawe do notariusza
z asystentem (teczka.py). Rozmowa, wgrywanie dokumentow, lista dokumentow
i brakow na zywo, podglad zapytania, wysylka do kancelarii.

Wszystko, co przychodzi od modelu albo z plikow, wstawiamy przez textContent
(nigdy innerHTML). Token teczki trzymamy w localStorage, zeby odswiezenie
strony nie gubilo sprawy; bez localStorage strona dziala, tylko bez tego.
"""
import json

from seo.strona import APLIKACJA, szkielet

SCIEZKA = "/przygotuj-sprawe/"

CSS = """
.tk { display:grid; grid-template-columns:minmax(0,1.25fr) minmax(0,1fr); gap:20px; align-items:start; margin:22px 0 40px; }
.tk-panel { background:var(--karta); border:1px solid var(--linia); border-radius:14px; padding:16px; box-shadow:0 12px 35px -29px rgba(13,61,129,.22); }
.tk-boczny { position:sticky; top:84px; max-height:calc(100vh - 100px); overflow-y:auto; }
.tk-czat { display:flex; flex-direction:column; height:min(72vh,680px); }
.tk-log { flex:1; overflow-y:auto; display:flex; flex-direction:column; gap:10px; padding:4px 2px 10px; }
.tk-msg { max-width:88%; padding:10px 13px; border-radius:12px; white-space:pre-wrap; line-height:1.45; font-size:.95rem; }
.tk-msg.asystent { background:var(--akcent-tlo); align-self:flex-start; }
.tk-msg.klient { background:#fff; border:1px solid var(--linia); align-self:flex-end; }
.tk-msg.blad { background:#fff1f1; color:#8a1f1f; align-self:center; }
.tk-wpis { display:flex; gap:8px; align-items:flex-end; border-top:1px solid var(--linia); padding-top:10px; }
.tk-wpis textarea { flex:1; resize:vertical; min-height:46px; max-height:160px; font:inherit; padding:9px 11px; border:1px solid var(--linia); border-radius:10px; }
.tk-plik { cursor:pointer; border:1px dashed var(--akcent); color:var(--akcent); border-radius:10px; padding:10px 12px; font-size:.9rem; white-space:nowrap; }
.tk-plik input { display:none; }
.tk h3 { margin:14px 0 8px; font-size:1rem; } .tk h3:first-child { margin-top:0; }
.tk-dok { list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:6px; }
.tk-dok li { display:grid; grid-template-columns:auto 1fr; gap:4px 10px; padding:8px 10px; border:1px solid var(--linia); border-radius:10px; font-size:.9rem; }
.tk-dok .skad { grid-column:2; color:var(--tekst3); font-size:.8rem; }
.tk-dok .opcje { grid-column:2; display:flex; gap:6px; flex-wrap:wrap; }
.tk-dok .opcje button { font:inherit; font-size:.78rem; padding:2px 9px; border-radius:999px; border:1px solid var(--linia); background:#fff; cursor:pointer; }
.tk-dok .opcje button.on { background:var(--akcent); border-color:var(--akcent); color:#fff; }
.tk-znak { font-weight:700; width:1.4em; text-align:center; }
.tk-znak.ok { color:#1d7a46; } .tk-znak.nie { color:#b04a00; } .tk-znak.moze { color:var(--tekst3); }
.tk-braki { margin:0; padding-left:18px; font-size:.9rem; color:var(--tekst2); }
.tk-braki .wymagane { color:#b04a00; font-weight:600; }
.tk-zap { white-space:pre-wrap; font-size:.82rem; background:var(--tlo); border:1px solid var(--linia); border-radius:10px; padding:10px; max-height:300px; overflow:auto; }
.tk-wyslij label { display:block; margin:8px 0; font-size:.9rem; }
.tk-wyslij input[type=text], .tk-wyslij input[type=tel], .tk-wyslij input[type=email] { width:100%; box-sizing:border-box; font:inherit; padding:8px 10px; border:1px solid var(--linia); border-radius:8px; }
.tk-pliki { list-style:none; padding:0; margin:0; font-size:.88rem; }
.tk-pliki li { display:flex; justify-content:space-between; gap:8px; padding:4px 0; border-bottom:1px solid var(--linia); }
.tk-pliki button, .tk-usun { background:none; border:0; color:var(--tekst3); cursor:pointer; font:inherit; font-size:.85rem; text-decoration:underline; }
.tk-stan { font-size:.85rem; color:var(--tekst3); min-height:1.2em; }
@media (max-width: 860px) { .tk { grid-template-columns:minmax(0,1fr); } .tk-czat { height:auto; min-height:60vh; } .tk-boczny { position:static; max-height:none; } .tk-wpis { flex-wrap:wrap; } .tk-wpis textarea { flex-basis:100%; } .tk-wpis .przycisk { flex:1; } }
"""


def strona() -> str:
    tresc = f"""
<section class="hero" style="padding-bottom:12px"><div class="szer">
  <p class="okruszki"><a href="/">notarai</a> › Przygotuj sprawę</p>
  <h1>Przygotuj sprawę do notariusza</h1>
  <p class="wstep">Opisz sprawę zwykłymi słowami albo wgraj dokumenty, które już masz. Asystent powie, jakie dokumenty
  przygotować i skąd je wziąć, zbierze dane nieruchomości i przygotuje zapytanie do kancelarii. Bez rejestracji.
  Nie podawaj numeru PESEL ani numeru dowodu – kancelaria spisze je przy wizycie.</p>
  <p class="wstep" id="tk-kancelaria" hidden></p>
</div></section>
<div class="szer">
<div class="tk">
  <section class="tk-panel tk-czat" aria-label="Rozmowa z asystentem">
    <div class="tk-log" id="tk-log" aria-live="polite"></div>
    <form class="tk-wpis" id="tk-form">
      <textarea id="tk-tekst" maxlength="2000" placeholder="Np. sprzedaję mieszkanie po mamie w Lublinie, kupujący bierze kredyt" aria-label="Wiadomość"></textarea>
      <label class="tk-plik" title="PDF, JPG lub PNG, do 10 MB">📎 Dokument<input type="file" id="tk-plik" accept=".pdf,.jpg,.jpeg,.png" multiple></label>
      <button class="przycisk" type="submit" id="tk-wyslij-wiad">Wyślij</button>
    </form>
    <p class="tk-stan" id="tk-stan"></p>
  </section>
  <aside class="tk-panel tk-boczny" aria-label="Teczka sprawy">
    <h3>Sprawa</h3>
    <p id="tk-czynnosc" style="margin:0;font-size:.95rem">jeszcze nie ustalona</p>
    <h3>Dokumenty</h3>
    <ul class="tk-dok" id="tk-dok"></ul>
    <h3>Wgrane pliki</h3>
    <ul class="tk-pliki" id="tk-pliki"><li>brak</li></ul>
    <h3>Do ustalenia</h3>
    <ul class="tk-braki" id="tk-braki"></ul>
    <h3>Zapytanie do kancelarii</h3>
    <div class="tk-zap" id="tk-zap"></div>
    <form class="tk-wyslij" id="tk-wyslij" hidden>
      <h3>Wyślij do kancelarii</h3>
      <label>Imię<input type="text" id="tk-imie" maxlength="80" required></label>
      <label>Telefon<input type="tel" id="tk-telefon" maxlength="40"></label>
      <label>E-mail<input type="email" id="tk-email" maxlength="120"></label>
      <input class="pulapka" type="text" id="tk-pulapka" tabindex="-1" autocomplete="off" aria-hidden="true">
      <label class="chk"><input type="checkbox" id="tk-zgoda" required> Zgadzam się na przekazanie zapytania i moich danych
        kontaktowych <span id="tk-komu">kancelarii notarialnej</span> w celu umówienia wizyty
        (<a href="/prywatnosc/" target="_blank" rel="noopener">polityka prywatności</a>).</label>
      <button class="przycisk" type="submit">Wyślij zapytanie</button>
    </form>
    <p class="tk-stan" id="tk-wynik"></p>
    <p><button class="tk-usun" type="button" id="tk-usun">Usuń teczkę i pliki</button> · <button class="tk-usun" type="button" id="tk-nowa">Zacznij od nowa</button></p>
  </aside>
</div>
</div>
<script>
'use strict';
const API = {json.dumps(APLIKACJA)};
const $ = id => document.getElementById(id);
const q = new URLSearchParams(location.search);
const KANCELARIA = q.get('kancelaria'), NAZWA = q.get('nazwa') || '', MIASTO = q.get('miejscowosc') || '';
const KLUCZ = 'notarai_teczka';
let token = null, zajety = false;
const pamiec = {{
  get() {{ try {{ return localStorage.getItem(KLUCZ); }} catch (e) {{ return null; }} }},
  set(v) {{ try {{ v ? localStorage.setItem(KLUCZ, v) : localStorage.removeItem(KLUCZ); }} catch (e) {{}} }},
}};
if (KANCELARIA && NAZWA) {{ $('tk-kancelaria').hidden = false; $('tk-kancelaria').textContent = 'Zapytanie trafi do: ' + NAZWA; $('tk-komu').textContent = 'kancelarii ' + NAZWA; }}

async function api(sciezka, cialo, plik) {{
  const opcje = {{ method: 'POST' }};
  if (plik) {{ const f = new FormData(); f.append('token', token); f.append('plik', plik); opcje.body = f; }}
  else {{ opcje.headers = {{ 'Content-Type': 'application/json' }}; opcje.body = JSON.stringify({{ token, ...cialo }}); }}
  const odp = await fetch(API + '/api/teczka' + sciezka, opcje);
  const d = await odp.json().catch(() => ({{}}));
  if (!odp.ok) throw Object.assign(new Error(typeof d.detail === 'string' ? d.detail : 'Coś poszło nie tak.'), {{ status: odp.status }});
  return d;
}}
function wiadomosc(rola, tekst) {{
  const el = document.createElement('div'); el.className = 'tk-msg ' + rola; el.textContent = tekst;
  $('tk-log').append(el); $('tk-log').scrollTop = $('tk-log').scrollHeight;
}}
const ZNAKI = {{ wgrany: ['✓', 'ok', 'wgrany'], podany: ['✓', 'ok', 'podany'], mam: ['✓', 'ok', 'masz'], 'nie mam': ['!', 'nie', 'do zdobycia'], brak: ['○', 'moze', ''] }};
function rysuj(s) {{
  $('tk-log').textContent = ''; s.rozmowa.forEach(w => wiadomosc(w.rola === 'klient' ? 'klient' : 'asystent', w.tresc));
  const d = s.dane, z = s.zapytanie;
  $('tk-czynnosc').textContent = z.czynnosc ? z.czynnosc + (d.miejsce.tekst ? ' · ' + d.miejsce.tekst : '') : 'jeszcze nie ustalona';
  const ul = $('tk-dok'); ul.textContent = '';
  s.dokumenty.forEach(x => {{
    const li = document.createElement('li'); const [znak, klasa, opis] = ZNAKI[x.stan] || ZNAKI.brak;
    const z1 = document.createElement('span'); z1.className = 'tk-znak ' + klasa; z1.textContent = znak; z1.title = opis;
    const n = document.createElement('span'); n.textContent = x.nazwa + (opis ? ' (' + opis + ')' : '');
    const sk = document.createElement('span'); sk.className = 'skad';
    sk.textContent = (x.potrzebny === 'jesli' ? 'Jeśli dotyczy: ' + x.dlaczego + '. ' : (x.dlaczego ? x.dlaczego + '. ' : '')) + 'Skąd: ' + x.skad;
    li.append(z1, n, sk);
    if (x.stan !== 'wgrany' && x.stan !== 'podany') {{
      const op = document.createElement('span'); op.className = 'opcje';
      ['mam', 'nie mam'].forEach(v => {{ const b = document.createElement('button'); b.type = 'button'; b.textContent = v;
        if (x.stan === v) b.className = 'on';
        b.addEventListener('click', () => ustal({{ deklaracje: {{ [x.id]: v }} }})); op.append(b); }});
      li.append(op);
    }}
    ul.append(li);
  }});
  if (!s.dokumenty.length) {{ const li = document.createElement('li'); li.textContent = 'Lista pojawi się, gdy ustalimy rodzaj sprawy.'; ul.append(li); }}
  const pl = $('tk-pliki'); pl.textContent = '';
  s.pliki.forEach(p => {{ const li = document.createElement('li'); const t = document.createElement('span');
    t.textContent = p.nazwa + (p.opis ? ' – ' + p.opis : '');
    const b = document.createElement('button'); b.type = 'button'; b.textContent = 'usuń';
    b.addEventListener('click', () => wykonaj(() => api('/usun-plik', {{ id: p.id }})));
    li.append(t, b); pl.append(li); }});
  if (!s.pliki.length) {{ const li = document.createElement('li'); li.textContent = 'brak'; pl.append(li); }}
  const br = $('tk-braki'); br.textContent = '';
  s.braki.forEach(b => {{ const li = document.createElement('li'); li.textContent = b.opis; if (b.waga === 'wymagane') li.className = 'wymagane'; br.append(li); }});
  if (!s.braki.length) {{ const li = document.createElement('li'); li.textContent = 'nic – zapytanie jest kompletne'; br.append(li); }}
  $('tk-zap').textContent = z.tekst;
  $('tk-wyslij').hidden = !z.gotowe || Boolean(s.wyslano);
  const blok = Boolean(s.wyslano); $('tk-tekst').disabled = blok; $('tk-plik').disabled = blok; $('tk-wyslij-wiad').disabled = blok;
  if (s.wyslano && !$('tk-wynik').textContent) $('tk-wynik').textContent = 'Zapytanie wysłane ' + s.wyslano.replace('T', ' ') + '.';
}}
async function wykonaj(akcja, stan) {{
  if (zajety) return; zajety = true; $('tk-stan').textContent = stan || '';
  try {{ rysuj(await akcja()); }}
  catch (e) {{
    if (e.status === 404) {{ pamiec.set(null); token = null; await start(); }}
    wiadomosc('blad', e.message);
  }} finally {{ zajety = false; $('tk-stan').textContent = ''; }}
}}
const ustal = u => wykonaj(() => api('/ustal', {{ ustalenia: u }}));
async function start() {{
  token = pamiec.get();
  if (token) {{ try {{ rysuj(await api('/stan', {{}})); return; }} catch (e) {{ token = null; pamiec.set(null); }} }}
  try {{
    const odp = await fetch(API + '/api/teczka', {{ method: 'POST' }}); const d = await odp.json();
    if (!odp.ok) throw new Error(d.detail || 'Nie udało się założyć teczki.');
    token = d.token; pamiec.set(token); rysuj(d);
    if (MIASTO) ustal({{ miejsce: MIASTO }});
  }} catch (e) {{ wiadomosc('blad', e.message || 'Brak połączenia. Odśwież stronę.'); }}
}}
$('tk-form').addEventListener('submit', e => {{
  e.preventDefault(); const t = $('tk-tekst').value.trim(); if (!t || !token) return;
  $('tk-tekst').value = ''; wiadomosc('klient', t);
  wykonaj(() => api('/wiadomosc', {{ wiadomosc: t }}), 'Asystent pisze…');
}});
$('tk-tekst').addEventListener('keydown', e => {{ if (e.key === 'Enter' && !e.shiftKey) {{ e.preventDefault(); $('tk-form').requestSubmit(); }} }});
$('tk-plik').addEventListener('change', async e => {{
  for (const plik of [...e.target.files]) await wykonaj(() => api('/plik', null, plik), 'Czytam „' + plik.name + '”…');
  e.target.value = '';
}});
$('tk-wyslij').addEventListener('submit', async e => {{
  e.preventDefault();
  await wykonaj(async () => {{
    const d = await api('/wyslij', {{ imie: $('tk-imie').value, telefon: $('tk-telefon').value, email: $('tk-email').value,
      zgoda: $('tk-zgoda').checked, kancelaria: KANCELARIA || null, miejscowosc: MIASTO, strona: $('tk-pulapka').value }});
    $('tk-wynik').textContent = d.komunikat || 'Wysłane.'; return d;
  }}, 'Wysyłam…');
}});
$('tk-usun').addEventListener('click', async () => {{
  if (!token || !confirm('Usunąć teczkę razem z wgranymi plikami?')) return;
  try {{ await api('/usun', {{}}); }} catch (e) {{}}
  pamiec.set(null); token = null; start();
}});
$('tk-nowa').addEventListener('click', () => {{ pamiec.set(null); token = null; start(); }});
start();
</script>
"""
    return szkielet("Przygotuj sprawę do notariusza | notarai",
                    "Opisz sprawę albo wgraj dokumenty: asystent powie, jakie dokumenty przygotować, i przygotuje zapytanie do kancelarii notarialnej.",
                    tresc, SCIEZKA, css=CSS, menu_aktywne="notariusz")
