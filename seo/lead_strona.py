"""Strona /lead/#token: kancelaria z linku w e-mailu widzi sprawe (bez
kontaktu), odpowiada w oknie i dopiero wtedy dostaje kontakt klienta.
Tresci wstawiamy przez textContent."""
import json

from seo.strona import APLIKACJA, szkielet

SCIEZKA = "/lead/"

CSS = """
.ld { max-width:720px; margin:24px auto 48px; background:var(--karta); border:1px solid var(--linia); border-radius:14px; padding:20px; }
.ld dl { display:grid; grid-template-columns:max-content 1fr; gap:6px 14px; margin:0 0 14px; }
.ld dt { color:var(--tekst3); } .ld dd { margin:0; white-space:pre-wrap; }
.ld label { display:block; margin:10px 0; font-size:.92rem; }
.ld textarea, .ld input { width:100%; box-sizing:border-box; font:inherit; padding:8px 10px; border:1px solid var(--linia); border-radius:8px; }
.ld-czas { font-weight:700; color:var(--akcent); }
.ld-kontakt { background:var(--akcent-tlo); border-radius:10px; padding:12px; margin-top:12px; }
@media (max-width:560px) { .ld dl { grid-template-columns:1fr; } }
"""


def strona() -> str:
    tresc = f"""
<div class="szer"><section class="ld" aria-live="polite">
  <h1 style="font-size:1.4rem;margin-top:0">Zapytanie klienta</h1>
  <p id="ld-stan">Wczytuję…</p>
  <dl id="ld-dane" hidden><dt>Sprawa</dt><dd id="ld-sprawa"></dd><dt>Miejscowość</dt><dd id="ld-miasto"></dd>
    <dt>Opis</dt><dd id="ld-opis"></dd><dt>Odpowiedzi innych</dt><dd id="ld-ile"></dd></dl>
  <form id="ld-form" hidden>
    <p>Do końca okna: <span class="ld-czas" id="ld-czas"></span>. Po odpowiedzi zobaczysz dane kontaktowe klienta,
      a klient dostanie Twoją wiadomość.</p>
    <label>Wiadomość do klienta<textarea id="ld-tresc" rows="4" maxlength="1500" placeholder="Np. Chętnie się zajmiemy. Proszę przygotować numer KW i podstawę nabycia."></textarea></label>
    <label>Proponowany termin (opcjonalnie)<input id="ld-termin" maxlength="200" placeholder="np. czwartek 10:00 albo w przyszłym tygodniu"></label>
    <label>Kontakt do kancelarii dla klienta (opcjonalnie, domyślnie z wykazu)<input id="ld-kontakt" maxlength="200"></label>
    <button class="przycisk" type="submit">Odpowiedz klientowi</button>
  </form>
  <div class="ld-kontakt" id="ld-klient" hidden></div>
</section></div>
<script>
'use strict';
const API = {json.dumps(APLIKACJA)};
const $ = id => document.getElementById(id);
const token = location.hash.slice(1);
let koniec = null;
async function post(sciezka, cialo) {{
  const odp = await fetch(API + '/api/leady' + sciezka, {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({{ token, ...cialo }}) }});
  const d = await odp.json().catch(() => ({{}}));
  if (!odp.ok) throw new Error(typeof d.detail === 'string' ? d.detail : 'Coś poszło nie tak.');
  return d;
}}
function pokazKlienta(lead) {{
  const k = lead.klient || {{}}; const box = $('ld-klient'); box.hidden = false; box.textContent = '';
  const h = document.createElement('b'); h.textContent = 'Klient: ' + [k.imie, k.nazwisko].filter(Boolean).join(' ');
  box.append(h);
  [['Telefon', k.telefon], ['E-mail', k.email]].filter(x => x[1]).forEach(([n, v]) => {{
    const p = document.createElement('p'); p.style.margin = '6px 0 0'; p.textContent = n + ': ' + v; box.append(p); }});
}}
function licz() {{
  if (!koniec) return; const s = Math.max(0, Math.floor((koniec - Date.now()) / 1000));
  $('ld-czas').textContent = Math.floor(s / 60) + ' min ' + String(s % 60).padStart(2, '0') + ' s';
  if (!s) {{ $('ld-form').hidden = true; $('ld-stan').textContent = 'Minęła godzina na odpowiedź. Zapytanie jest w archiwum dla kancelarii korzystających z notarai.pl.'; koniec = null; }}
}}
(async () => {{
  if (!token) {{ $('ld-stan').textContent = 'Brak kodu w adresie. Użyj linku z e-maila.'; return; }}
  try {{
    const d = await post('/zaproszenie', {{}});
    const l = d.lead; $('ld-dane').hidden = false;
    $('ld-sprawa').textContent = l.sprawa; $('ld-miasto').textContent = l.miejscowosc; $('ld-opis').textContent = l.opis || '–';
    $('ld-ile').textContent = String(l.odpowiedzi);
    if (l.zapytanie) {{ const pre = document.createElement('pre'); pre.style.whiteSpace = 'pre-wrap'; pre.style.fontSize = '.8rem'; pre.textContent = l.zapytanie; $('ld-dane').after(pre); }}
    $('ld-stan').textContent = d.kancelaria ? 'Dla: ' + d.kancelaria : '';
    if (d.odpowiedz) {{ $('ld-stan').textContent = 'Twoja kancelaria już odpowiedziała.'; pokazKlienta(l); return; }}
    if (!d.otwarte) {{ $('ld-stan').textContent = 'Minęła godzina na odpowiedź. Zapytanie jest w archiwum dla kancelarii korzystających z notarai.pl.'; return; }}
    koniec = new Date(l.okno_do).getTime(); $('ld-form').hidden = false; licz(); setInterval(licz, 1000);
  }} catch (e) {{ $('ld-stan').textContent = e.message; }}
}})();
$('ld-form').addEventListener('submit', async e => {{
  e.preventDefault();
  try {{
    const d = await post('/odpowiedz', {{ tresc: $('ld-tresc').value, termin: $('ld-termin').value, kontakt: $('ld-kontakt').value }});
    $('ld-form').hidden = true; koniec = null; $('ld-stan').textContent = d.komunikat; pokazKlienta(d.lead);
  }} catch (err) {{ $('ld-stan').textContent = err.message; }}
}});
</script>
"""
    html = szkielet("Zapytanie klienta | notarai", "Zapytanie klienta do kancelarii notarialnej.", tresc, SCIEZKA, css=CSS)
    return html.replace("<head>", '<head>\n<meta name="robots" content="noindex">', 1)
