"""Strony publiczne do rekomendacji kancelarii:

/zasady-kolejnosci/ - regula kolejnosci (rekomendacje.py) i sprawdzarka:
    przegladarka sama liczy SHA-256 i porownuje z kolejnoscia z serwera, wiec
    kazdy (notariusz, izba, klient) moze sprawdzic, ze nikt nie jest wyzej
    za pieniadze. Pokazuje tez liczbe przydzialow z kolejki "dowolna kancelaria".
/wizyta/odwolaj/ - odwolanie rezerwacji online linkiem z e-maila (token
    w czesci # adresu, nie trafia do logow serwera strony).
"""
import json

import rekomendacje
from seo.strona import APLIKACJA, esc, szkielet

SCIEZKA_ZASAD = "/zasady-kolejnosci/"
SCIEZKA_ODWOLANIA = "/wizyta/odwolaj/"


def strona_zasad() -> str:
    w = rekomendacje.WERSJA
    tresc = f"""
<section class="hero" style="padding-bottom:20px"><div class="szer">
  <p class="okruszki"><a href="/">notarai</a> › Zasady kolejności</p>
  <h1>Jak ustalamy kolejność kancelarii</h1>
  <p class="wstep">Ta sama reguła dla każdej kancelarii z wykazu notariuszy, także takiej, która nie korzysta z notarai.
  Abonament, płatności, konto w notarai ani terminy z naszego kalendarza nie wpływają na miejsce na liście.
  Wersja reguł: <b>{esc(w)}</b>.</p>
</div></section>
<section class="sekcja-w"><div class="szer">
  <h2>Reguła</h2>
  <ol>
    <li><b>Odległość</b>, jeśli podasz swoje położenie (na mapie): w pasmach co {rekomendacje.PASMO_KM:g} km, żeby kilkaset metrów nie przesądzało.</li>
    <li><b>Kontakt</b>: kancelarie bez żadnego kontaktu w publicznych wykazach są na końcu, bo nie da się z nimi umówić.</li>
    <li><b>Codzienna rotacja</b>: dla każdej kancelarii liczymy <code>SHA-256("notarai|{esc(w)}|data|miejscowość|id")</code>
      i sortujemy rosnąco po pierwszych 8 bajtach. Każdego dnia wszyscy widzą tę samą kolejność, następnego dnia jest inna,
      a w długim okresie każda kancelaria jest pierwsza równie często.</li>
  </ol>
  <h2>„Dowolna kancelaria w miejscowości”</h2>
  <p>Zgłoszenie dostaje kancelaria, która w ostatnich {rekomendacje.OKNO_DNI} dniach dostała z tej kolejki najmniej zgłoszeń;
  remis rozstrzyga rotacja dnia. Kancelarie spoza notarai są w kolejce na równi z pozostałymi.</p>
  <h2>Czym różnią się kancelarie korzystające z notarai</h2>
  <p>Wyłącznie sposobem obsługi po wyborze: zgłoszenie trafia od razu do kancelarii, a jeśli kancelaria to włączyła,
  możesz od razu zarezerwować wolną godzinę i dostać przypomnienie. Nie mają lepszego miejsca na liście.</p>
</div></section>
<section class="sekcja-w tlo2" id="sprawdz"><div class="szer">
  <h2>Sprawdź sam</h2>
  <p class="wstep">Wpisz miejscowość (jak w adresie strony, np. <code>lublin</code>) i datę. Przeglądarka pobierze kolejność z serwera,
  policzy skróty SHA-256 samodzielnie i powie, czy kolejność zgadza się z regułą.</p>
  <form id="spr" class="dwie" style="max-width:640px">
    <label><span>Miejscowość</span><input id="spr-m" required maxlength="80" placeholder="lublin"></label>
    <label><span>Data</span><input id="spr-d" type="date"></label>
    <button class="przycisk" type="submit">Sprawdź</button>
  </form>
  <p id="spr-wynik" class="wstep"></p>
  <ol id="spr-lista"></ol>
  <h3>Przydziały z kolejki w ostatnich {rekomendacje.OKNO_DNI} dniach</h3>
  <ul id="spr-przydzialy"></ul>
</div></section>
<script>
'use strict';
const API = {json.dumps(APLIKACJA)};
const $ = id => document.getElementById(id);
async function sha(tekst) {{
  const b = new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(tekst)));
  let n = 0n; for (let i = 0; i < 8; i++) n = (n << 8n) | BigInt(b[i]); return n;
}}
$('spr-d').valueAsDate = new Date();
$('spr').addEventListener('submit', async e => {{
  e.preventDefault();
  const m = $('spr-m').value.trim().toLowerCase(), data = $('spr-d').value;
  $('spr-wynik').textContent = 'Liczę…'; $('spr-lista').textContent = ''; $('spr-przydzialy').textContent = '';
  try {{
    const odp = await fetch(API + '/api/wizyty/przejrzystosc?miejscowosc=' + encodeURIComponent(m) + '&data=' + data);
    const d = await odp.json();
    if (!odp.ok) {{ $('spr-wynik').textContent = d.detail || 'Błąd.'; return; }}
    const wlasne = await Promise.all(d.kolejnosc.map(async k => ({{ ...k, moj: await sha(`notarai|${{d.wersja}}|${{d.data}}|${{d.miejscowosc}}|${{k.id}}`) }})));
    const oczek = [...wlasne].sort((a, b) => (a.brak_kontaktu - b.brak_kontaktu) || (a.moj < b.moj ? -1 : a.moj > b.moj ? 1 : 0));
    const zgodne = oczek.every((k, i) => k.id === d.kolejnosc[i].id && BigInt(d.kolejnosc[i].los) === k.moj);
    $('spr-wynik').textContent = (zgodne ? '✔ Kolejność zgadza się z regułą ' : '✘ Kolejność NIE zgadza się z regułą ') + d.wersja + ' (' + d.data + ').';
    d.kolejnosc.forEach(k => {{ const li = document.createElement('li'); li.textContent = k.nazwa + (k.brak_kontaktu ? ' (brak kontaktu)' : ''); $('spr-lista').append(li); }});
    d.przydzialy.forEach(k => {{ const li = document.createElement('li'); li.textContent = k.nazwa + ': ' + k.liczba; $('spr-przydzialy').append(li); }});
  }} catch (err) {{ $('spr-wynik').textContent = 'Brak połączenia.'; }}
}});
</script>
"""
    return szkielet("Zasady kolejności kancelarii | notarai",
                    "Jak notarai ustala kolejność kancelarii notarialnych: jedna reguła dla wszystkich, codzienna rotacja, sprawdzarka.",
                    tresc, SCIEZKA_ZASAD, menu_aktywne="notariusz")


def strona_odwolania() -> str:
    tresc = f"""
<section class="hero"><div class="szer">
  <h1>Odwołanie wizyty</h1>
  <p class="wstep" id="o-opis">Kliknij, żeby odwołać wizytę zarezerwowaną przez notarai.pl. Termin wróci do kalendarza kancelarii.</p>
  <button class="przycisk" id="o-btn" type="button">Odwołaj wizytę</button>
  <p class="wstep" id="o-wynik"></p>
</div></section>
<script>
'use strict';
const API = {json.dumps(APLIKACJA)};
const token = location.hash.slice(1);
const btn = document.getElementById('o-btn'), wynik = document.getElementById('o-wynik');
if (!token) {{ btn.hidden = true; wynik.textContent = 'Brak kodu rezerwacji w adresie. Użyj linku z e-maila.'; }}
btn.addEventListener('click', async () => {{
  btn.disabled = true;
  try {{
    const odp = await fetch(API + '/api/wizyty/rezerwacja/odwolaj', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({{ token }}) }});
    const d = await odp.json().catch(() => ({{}}));
    wynik.textContent = odp.ok ? d.komunikat : (d.detail || 'Nie udało się odwołać. Zadzwoń do kancelarii.');
    if (odp.ok) btn.hidden = true; else btn.disabled = false;
  }} catch (err) {{ wynik.textContent = 'Brak połączenia.'; btn.disabled = false; }}
}});
</script>
"""
    html = szkielet("Odwołanie wizyty | notarai", "Odwołanie wizyty u notariusza zarezerwowanej przez notarai.pl.",
                    tresc, SCIEZKA_ODWOLANIA)
    return html.replace("<head>", '<head>\n<meta name="robots" content="noindex">', 1)
