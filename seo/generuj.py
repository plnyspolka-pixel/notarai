"""Strony miejscowosci (programmatic SEO) dla notarai.pl.

    py -3 seo\\generuj.py              -> strona/notariusz/<miasto>/index.html, hub, sitemap, robots

Kazda strona ma to, czego nie ma zadna inna: liste kancelarii z tej
miejscowosci z adresami i telefonami (z wykazu izb i dane.gov.pl), liczbe,
izbe, formularz umowienia wizyty w konkretnej kancelarii.

Neutralnosc (zakaz reklamy notariuszy): lista ma te sama kolejnosc dla
wszystkich kancelarii, bez odznak i wyroznien. Przycisk "Umow wizyte" pojawia
sie tylko przy kancelariach, ktore przyjmuja zgloszenia online; przy
pozostalych sa adres i telefon. notarai nie dobiera kancelarii za klienta. Wspolne sa
przyklady kosztow (taksa jest ogolnopolska) i pytania. E-maile kancelarii
nie trafiaja na strony - sluza tylko aplikacji do przekazywania zgloszen.
"""
import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from seo import baza as moduł_bazy  # noqa: E402
from seo.strona import (APLIKACJA, KATALOG_STRONY, STRONA, esc, markdown, odmiana,  # noqa: E402
                        przyklady_kosztow, stawki_etykieta, szkielet, tabela_kosztow, zl)

import taksa  # noqa: E402

CZYNNOSCI_FORMULARZA = [
    "zakup lub sprzedaż mieszkania", "zakup lub sprzedaż domu", "zakup lub sprzedaż działki",
    "darowizna nieruchomości", "umowa deweloperska lub odbiór od dewelopera", "testament",
    "pełnomocnictwo", "poświadczenie dziedziczenia (spadek)", "umowa majątkowa małżeńska",
    "poświadczenie podpisu lub odpisu", "umowa spółki", "inna czynność",
]

FAQ = [
    ("Ile kosztuje notariusz w {miasto}?",
     "Wynagrodzenie notariusza (taksę) ogranicza rozporządzenie Ministra Sprawiedliwości, takie samo dla całej Polski. "
     "Przy zakupie mieszkania za 400 000 zł taksa z wypisami to około {taksa_mieszkanie}, do tego podatek PCC 2 % i opłaty sądowe. "
     "Kancelarie w {miasto} mogą policzyć mniej niż stawka maksymalna, więc warto zapytać o wycenę."),
    ("Czy mogę umówić wizytę u notariusza online?",
     "W części kancelarii tak: przy nich na liście jest przycisk „Umów wizytę”. Zostawiasz imię, telefon albo e-mail i opis sprawy, "
     "a zgłoszenie trafia prosto do kancelarii. Z pozostałymi skontaktuj się telefonicznie, numery są na liście."),
    ("Jakie dokumenty zabrać do notariusza?",
     "Zawsze dowód osobisty lub paszport. Przy nieruchomości: dokument nabycia, numer księgi wieczystej, zaświadczenia z urzędu gminy "
     "(plan zagospodarowania, rewitalizacja), ze spółdzielni lub wspólnoty o braku zaległości i o zameldowaniu, a przy kredycie umowę z bankiem. "
     "Dokładną listę kalkulator pokazuje przy wyniku."),
    ("Kto płaci za notariusza przy sprzedaży mieszkania?",
     "Zwyczajowo koszty aktu ponosi kupujący, ale strony mogą umówić się inaczej. Podatek PCC płaci zawsze kupujący, "
     "a opłaty sądowe za wpis w księdze wieczystej ten, na czyją rzecz wpis następuje."),
    ("Czy wycena z tej strony jest wiążąca?",
     "Nie. To szacunek według stawek maksymalnych z rozporządzenia, liczony przez kalkulator notarai. "
     "Ostateczny koszt ustala kancelaria na podstawie treści aktu i liczby wypisów."),
]


def _czytaj_baze() -> dict:
    return moduł_bazy.wczytaj_json()


def formularz_html(slug_miasta: str, nazwa_miasta: str) -> str:
    opcje = "".join(f'<option value="{esc(c)}">{esc(c)}</option>' for c in CZYNNOSCI_FORMULARZA)
    return f"""
<dialog class="umow" id="umow">
  <form id="umow-form" method="dialog" autocomplete="off">
    <h2>Umów wizytę u notariusza</h2>
    <p id="umow-kancelaria" style="color:var(--tekst2);margin:0 0 4px"></p>
    <input type="hidden" id="u-kancelaria" value="">
    <input type="hidden" id="u-parametry" value="">
    <div class="dwie">
      <label><span>Imię</span><input type="text" id="u-imie" required maxlength="80"></label>
      <label><span>Telefon</span><input type="tel" id="u-telefon" maxlength="40" placeholder="np. 600 700 800"></label>
    </div>
    <label><span>E-mail (opcjonalnie, dostaniesz potwierdzenie)</span><input type="email" id="u-email" maxlength="120"></label>
    <div class="dwie">
      <label><span>Czynność</span><select id="u-czynnosc">{opcje}</select></label>
      <label><span>Wartość (zł, jeśli dotyczy)</span><input type="text" id="u-wartosc" inputmode="decimal" placeholder="np. 450 000"></label>
    </div>
    <label><span>Preferowany termin</span><input type="text" id="u-termin" maxlength="200" placeholder="np. w przyszłym tygodniu po 15:00"></label>
    <label><span>Wiadomość (opcjonalnie)</span><textarea id="u-wiadomosc" rows="3" maxlength="2000" placeholder="Krótko o sprawie: strony, kredyt, czy akt ma być pilnie"></textarea></label>
    <input class="pulapka" type="text" id="u-pulapka" tabindex="-1" autocomplete="off" aria-hidden="true">
    <label class="chk"><input type="checkbox" id="u-zgoda" required> <span>Zgadzam się na przekazanie moich danych wybranej kancelarii notarialnej w celu umówienia wizyty. Administratorem danych jest Fundacja Krzewienia Edukacji Finansowej im. Pieczaka (<a href="/prywatnosc/" target="_blank" rel="noopener">polityka prywatności</a>).</span></label>
    <div class="akcje">
      <button class="przycisk" type="submit" id="u-wyslij">Wyślij zgłoszenie</button>
      <button class="przycisk drugi" type="button" id="u-zamknij">Anuluj</button>
    </div>
    <div class="wynik" id="u-wynik" hidden></div>
  </form>
</dialog>
<script>
'use strict';
const API = {json.dumps(APLIKACJA)};
const SLUG = {json.dumps(slug_miasta)};
const $ = id => document.getElementById(id);
const liczba = s => {{ const n = Number(String(s).replace(/\\s|\\u00a0/g, '').replace(',', '.')); return isFinite(n) && n > 0 ? n : null; }};
const q = new URLSearchParams(location.search);
function otworz(id, nazwa) {{
  $('u-kancelaria').value = id || '';
  if (!id) return;
  $('umow-kancelaria').textContent = 'Kancelaria: ' + nazwa;
  $('u-wynik').hidden = true; $('u-wyslij').disabled = false;
  if (q.get('czynnosc')) {{ const sel = $('u-czynnosc'); const o = [...sel.options].find(o => q.get('czynnosc').toLowerCase().includes(o.value.split(' ')[0])); if (o) sel.value = o.value; }}
  if (q.get('wartosc')) $('u-wartosc').value = q.get('wartosc');
  if (q.get('p')) $('u-parametry').value = q.get('p');
  $('umow').showModal(); $('u-imie').focus();
}}
document.querySelectorAll('[data-umow]').forEach(b => b.addEventListener('click', () => otworz(b.dataset.umow, b.dataset.nazwa)));
$('u-zamknij').addEventListener('click', () => $('umow').close());
$('umow-form').addEventListener('submit', async e => {{
  e.preventDefault();
  const wynik = $('u-wynik'); wynik.hidden = true; wynik.classList.remove('blad');
  let parametry = null;
  try {{ parametry = $('u-parametry').value ? JSON.parse($('u-parametry').value) : null; }} catch (err) {{ parametry = null; }}
  const dane = {{ imie: $('u-imie').value, telefon: $('u-telefon').value, email: $('u-email').value,
    czynnosc: $('u-czynnosc').value, wartosc: liczba($('u-wartosc').value), termin: $('u-termin').value,
    wiadomosc: $('u-wiadomosc').value, zgoda: $('u-zgoda').checked, kancelaria: $('u-kancelaria').value || null,
    miejscowosc: SLUG, parametry, zrodlo: q.get('p') ? 'kalkulator' : 'strona', strona: $('u-pulapka').value }};
  $('u-wyslij').disabled = true;
  try {{
    const odp = await fetch(API + '/api/wizyty/zgloszenie', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify(dane) }});
    const w = await odp.json().catch(() => ({{}}));
    wynik.hidden = false;
    if (!odp.ok) {{ wynik.classList.add('blad'); wynik.textContent = typeof w.detail === 'string' ? w.detail : 'Nie udało się wysłać. Zadzwoń do kancelarii.'; $('u-wyslij').disabled = false; return; }}
    wynik.textContent = w.komunikat || 'Zgłoszenie przyjęte.';
    $('u-zamknij').textContent = 'Zamknij';
  }} catch (err) {{
    wynik.hidden = false; wynik.classList.add('blad'); wynik.textContent = 'Brak połączenia. Spróbuj ponownie albo zadzwoń do kancelarii.'; $('u-wyslij').disabled = false;
  }}
}});
// Kancelarie przyjmujace zgloszenia online: tylko odsloniety przycisk.
// Kolejnosc listy i wyglad karty zostaja takie same jak u pozostalych.
fetch(API + '/api/wizyty/kancelarie?miejscowosc=' + encodeURIComponent(SLUG)).then(r => r.json()).then(d => {{
  (d.notarai || []).forEach(id => {{
    const b = document.querySelector('#k-' + id + ' [data-umow]'); if (b) b.hidden = false;
  }});
}}).catch(() => {{}});
</script>
"""


def karta_kancelarii(k: dict) -> str:
    telefony = " · ".join(f'<a href="tel:{esc(re.sub(r"[^\d+]", "", t))}">{esc(t)}</a>' for t in k["telefony"])
    linie = [f'<h3>{esc(k["nazwa"])}</h3>']
    if k["adres"]:
        linie.append(f'<p>{esc(k["adres"])}</p>')
    if telefony:
        linie.append(f'<p class="tel">{telefony}</p>')
    if k["www"]:
        linie.append(f'<p><a href="{esc(k["www"])}" rel="nofollow noopener" target="_blank">strona kancelarii</a></p>')
    if k.get("brak_kontaktu"):
        linie.append('<p class="brak">Brak danych kontaktowych w publicznych wykazach. Kancelario, jeśli to Ty: napisz na kontakt@notarai.pl.</p>')
    else:
        linie.append(f'<div class="akcje"><button class="przycisk" type="button" data-umow="{k["id"]}" data-nazwa="{esc(k["nazwa"])}" hidden>Umów wizytę</button>'
                     + ('' if k["zweryfikowany"] else '<span class="brak">dane z katalogu branżowego, do potwierdzenia</span>') + '</div>')
    return f'<article id="k-{k["id"]}">' + "".join(linie) + "</article>"


def strona_miejscowosci(m: dict, kancelarie: list[dict], okolice: list[dict], przyklady: list[dict], izby: dict) -> str:
    miasto = m["nazwa"]
    n = len(kancelarie)
    izba = izby.get(m["izba"], m["izba"])
    ile = odmiana(n, "kancelaria notarialna", "kancelarie notarialne", "kancelarii notarialnych")
    tytul = f"Notariusz {miasto}: {odmiana(n, 'kancelaria', 'kancelarie', 'kancelarii')}, koszty aktu, umów wizytę"
    opis = (f"{ile} w miejscowości {miasto} z adresami i telefonami. Ile kosztuje notariusz w {miasto}: "
            f"taksa od 5 listopada 2026 r., PCC, opłaty sądowe. Umów wizytę online w wybranej kancelarii.")
    sciezka = f"/notariusz/{m['slug']}/"
    taksa_mieszkanie = zl(przyklady[0]["taksa"])
    faq_html = "".join(
        f"<details><summary>{esc(p.format(miasto=miasto))}</summary><p>{esc(o.format(miasto=miasto, taksa_mieszkanie=taksa_mieszkanie))}</p></details>"
        for p, o in FAQ)
    okolice_html = "".join(f'<a href="/notariusz/{o["slug"]}/">{esc(o["nazwa"])} <small>({o["liczba"]})</small></a>' for o in okolice)
    jsonld = [
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "notarai", "item": STRONA + "/"},
            {"@type": "ListItem", "position": 2, "name": "Notariusze", "item": STRONA + "/notariusz/"},
            {"@type": "ListItem", "position": 3, "name": miasto, "item": STRONA + sciezka}]},
        {"@context": "https://schema.org", "@type": "ItemList", "name": f"Kancelarie notarialne w {miasto}",
         "numberOfItems": n, "itemListElement": [
             {"@type": "ListItem", "position": i + 1, "item": {
                 "@type": "Notary", "name": k["nazwa"],
                 **({"address": {"@type": "PostalAddress", "streetAddress": k["adres"], "addressLocality": miasto, "addressCountry": "PL"}} if k["adres"] else {}),
                 **({"telephone": "+48 " + k["telefony"][0]} if k["telefony"] else {}),
                 **({"url": k["www"]} if k["www"] else {})}}
             for i, k in enumerate(kancelarie)]},
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": p.format(miasto=miasto),
             "acceptedAnswer": {"@type": "Answer", "text": o.format(miasto=miasto, taksa_mieszkanie=taksa_mieszkanie)}}
            for p, o in FAQ]},
    ]
    tresc = f"""
<section class="hero" style="padding-bottom:28px">
  <div class="szer">
    <p class="okruszki"><a href="/">notarai</a> › <a href="/notariusz/">Notariusze</a> › {esc(miasto)}</p>
    <p class="znacznik">{esc(izba)}</p>
    <h1>Notariusz {esc(miasto)}: <em>{esc(ile)}</em>, koszty aktu i umówienie wizyty</h1>
    <p class="wstep">W miejscowości {esc(miasto)} działa {esc(ile)} wpisan{'a' if n == 1 else ('e' if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else 'ych')} do wykazu notariuszy
      (stan na 31 grudnia 2025 r.). Niżej znajdziesz adresy i telefony, orientacyjne koszty najczęstszych czynności według
      stawek obowiązujących od 5 listopada 2026 r. oraz formularz, którym umówisz wizytę w wybranej kancelarii bez dzwonienia.</p>
    <ul class="odznaki"><li>Wykaz izb notarialnych i dane.gov.pl</li><li>Koszty liczone przez kalkulator notarai</li><li>Umówienie wizyty bez rejestracji</li></ul>
  </div>
</section>

<section class="sekcja-w" id="kancelarie">
  <div class="szer">
    <h2>Kancelarie notarialne w {esc(miasto)}</h2>
    <p class="wstep">Kolejność: najpierw kancelarie z potwierdzonymi danymi z wykazu izby. Kancelarie korzystające z notarai dostają zgłoszenie od razu w swojej aplikacji.</p>
    <div class="kanc" id="lista-kancelarii">{"".join(karta_kancelarii(k) for k in kancelarie)}</div>
  </div>
</section>

<section class="sekcja-w tlo2" id="koszty">
  <div class="szer">
    <h2>Ile kosztuje notariusz w {esc(miasto)}?</h2>
    <p class="wstep">Taksa notarialna jest ograniczona rozporządzeniem i taka sama w całym kraju; kancelaria może policzyć mniej. Do taksy dochodzą wypisy, VAT 23 %, podatek PCC (przy zakupie z rynku wtórnego) i opłaty sądowe za wpis w księdze wieczystej. Przykłady według {esc(stawki_etykieta().lower())}:</p>
    {tabela_kosztow(przyklady)}
    <div class="cta-pasek"><p><strong>Masz inną wartość albo sprawę?</strong> Kalkulator policzy taksę, PCC i opłaty sądowe dla Twojej czynności i pokaże, co zabrać do kancelarii.</p><a class="przycisk" href="/kalkulator/">Policz koszty</a></div>
  </div>
</section>

<section class="sekcja-w" id="umow-wizyte">
  <div class="szer">
    <h2>Jak umówić wizytę u notariusza w {esc(miasto)}</h2>
    <ol class="kroki-u">
      <li><b>Wybierz kancelarię</b>Przy kancelariach, które przyjmują zgłoszenia online, kliknij „Umów wizytę”. Do pozostałych zadzwoń, numery są na liście.</li>
      <li><b>Opisz sprawę</b>Imię, telefon lub e-mail, rodzaj czynności i preferowany termin. Bez PESEL-u i bez skanów.</li>
      <li><b>Potwierdzenie</b>Zgłoszenie trafia prosto do wybranej kancelarii, która kontaktuje się z Tobą i potwierdza termin.</li>
    </ol>
  </div>
</section>

<section class="sekcja-w tlo2 faq" id="faq">
  <div class="szer">
    <h2>Najczęstsze pytania o notariusza w {esc(miasto)}</h2>
    {faq_html}
  </div>
</section>

<section class="sekcja-w" id="okolice">
  <div class="szer">
    <h2>Notariusze w okolicy</h2>
    <p class="wstep">Inne miejscowości w okręgu: {esc(izba)}.</p>
    <div class="okolice">{okolice_html}<a href="/notariusz/">wszystkie miejscowości</a></div>
  </div>
</section>
{formularz_html(m["slug"], miasto)}
"""
    return szkielet(tytul, opis, tresc, sciezka, jsonld, menu_aktywne="notariusz")


def strona_hub(miejscowosci: list[dict], izby: dict, liczba_kancelarii: int) -> str:
    wg_izby: dict[str, list[dict]] = defaultdict(list)
    for m in miejscowosci:
        wg_izby[m["izba"]].append(m)
    najwieksze = sorted(miejscowosci, key=lambda m: -m["liczba"])[:16]
    bloki = ""
    for izba, lista in sorted(wg_izby.items(), key=lambda p: izby.get(p[0], p[0])):
        linki = "".join(f'<a href="/notariusz/{m["slug"]}/" data-nazwa="{esc(m["nazwa"].lower())}">{esc(m["nazwa"])} <small>{m["liczba"]}</small></a>'
                        for m in sorted(lista, key=lambda m: m["nazwa"]))
        bloki += f'<div class="izba"><h3>{esc(izby.get(izba, izba))} <small style="color:var(--tekst3);font-weight:400">({odmiana(len(lista), "miejscowość", "miejscowości", "miejscowości")})</small></h3><div class="miasta">{linki}</div></div>'
    duze = "".join(f'<a href="/notariusz/{m["slug"]}/">{esc(m["nazwa"])} <small>({m["liczba"]})</small></a>' for m in najwieksze)
    tytul = f"Notariusze w Polsce: kancelarie notarialne w {len(miejscowosci)} miejscowościach, koszty i umówienie wizyty"
    opis = (f"Wykaz {liczba_kancelarii} kancelarii notarialnych w {len(miejscowosci)} miejscowościach z adresami i telefonami. "
            "Sprawdź koszty aktu według stawek od 5 listopada 2026 r. i umów wizytę online.")
    jsonld = [{"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "notarai", "item": STRONA + "/"},
        {"@type": "ListItem", "position": 2, "name": "Notariusze", "item": STRONA + "/notariusz/"}]}]
    tresc = f"""
<section class="hero" style="padding-bottom:28px">
  <div class="szer">
    <p class="okruszki"><a href="/">notarai</a> › Notariusze</p>
    <p class="znacznik">Wykaz kancelarii notarialnych</p>
    <h1>Notariusz w Twojej miejscowości: <em>{liczba_kancelarii} kancelarii</em> w {len(miejscowosci)} miejscowościach</h1>
    <p class="wstep">Wybierz miejscowość. Na każdej stronie: lista kancelarii z wykazu izby notarialnej, orientacyjne koszty aktu według stawek obowiązujących od 5 listopada 2026 r. i formularz umówienia wizyty w wybranej kancelarii.</p>
    <input class="szukaj-m" type="search" id="szukaj" placeholder="Wpisz miejscowość, np. Lublin" aria-label="Szukaj miejscowości">
    <div class="okolice" id="najwieksze">{duze}</div>
  </div>
</section>
<section class="sekcja-w" id="miejscowosci">
  <div class="szer">
    <h2>Wszystkie miejscowości według izb notarialnych</h2>
    <div id="wykaz">{bloki}</div>
    <p class="przypis">Źródło: oficjalny wykaz notariuszy (dane.gov.pl, zbiór 22657) i wyszukiwarki izb notarialnych, stan na 31 grudnia 2025 r. Część kontaktów pochodzi z katalogu branżowego i jest oznaczona do potwierdzenia. Zmiany prosimy zgłaszać na kontakt@notarai.pl.</p>
    <div class="cta-pasek"><p><strong>Ile zapłacisz u notariusza?</strong> Opisz sprawę zwykłym językiem, a kalkulator policzy taksę, podatek i opłaty sądowe oraz pokaże, co zabrać do kancelarii.</p><a class="przycisk" href="/kalkulator/">Otwórz kalkulator</a></div>
  </div>
</section>
<script>
'use strict';
const q = new URLSearchParams(location.search);
if ([...q.keys()].length) document.querySelectorAll('#wykaz a, #najwieksze a').forEach(a => {{ a.href += (a.href.includes('?') ? '&' : '?') + q.toString(); }});
const pole = document.getElementById('szukaj');
const norm = s => s.toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').replace(/ł/g, 'l');
pole.addEventListener('input', () => {{
  const f = norm(pole.value.trim());
  document.querySelectorAll('#wykaz .miasta a').forEach(a => {{ a.style.display = !f || norm(a.textContent).includes(f) ? '' : 'none'; }});
  document.querySelectorAll('#wykaz .izba').forEach(b => {{ b.style.display = [...b.querySelectorAll('a')].some(a => a.style.display !== 'none') ? '' : 'none'; }});
}});
</script>
"""
    return szkielet(tytul, opis, tresc, "/notariusz/", jsonld, menu_aktywne="notariusz")


def sitemap(miejscowosci: list[dict]) -> str:
    dzis = date.today().isoformat()
    adresy = ["/", "/kalkulator/", "/notariusz/", "/blog/", "/regulamin/", "/prywatnosc/", "/umowa-powierzenia/", "/instrukcja-ai/"]
    adresy += [f"/notariusz/{m['slug']}/" for m in miejscowosci]
    for wpis in sorted((KATALOG_STRONY / "blog").glob("*/index.html")):
        adresy.append(f"/blog/{wpis.parent.name}/")
    linie = "".join(f"<url><loc>{esc(STRONA + a)}</loc><lastmod>{dzis}</lastmod></url>\n" for a in adresy)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{linie}</urlset>\n'


def generuj(dane: dict | None = None, cel: Path = KATALOG_STRONY) -> dict:
    dane = dane or _czytaj_baze()
    izby = dane["izby"]
    miejscowosci = dane["miejscowosci"]
    wg_slug: dict[str, list[dict]] = defaultdict(list)
    for k in dane["kancelarie"]:
        wg_slug[k["slug"]].append(k)
    wg_izby: dict[str, list[dict]] = defaultdict(list)
    for m in miejscowosci:
        wg_izby[m["izba"]].append(m)
    przyklady = przyklady_kosztow()
    katalog = cel / "notariusz"
    katalog.mkdir(parents=True, exist_ok=True)
    for m in miejscowosci:
        okolice = [o for o in sorted(wg_izby[m["izba"]], key=lambda o: -o["liczba"]) if o["slug"] != m["slug"]][:12]
        html = strona_miejscowosci(m, wg_slug[m["slug"]], okolice, przyklady, izby)
        (katalog / m["slug"]).mkdir(exist_ok=True)
        (katalog / m["slug"] / "index.html").write_text(html, encoding="utf-8")
    (katalog / "index.html").write_text(strona_hub(miejscowosci, izby, len(dane["kancelarie"])), encoding="utf-8")
    (cel / "sitemap.xml").write_text(sitemap(miejscowosci), encoding="utf-8")
    (cel / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {STRONA}/sitemap.xml\n", encoding="utf-8")
    return {"miejscowosci": len(miejscowosci), "kancelarie": len(dane["kancelarie"])}


if __name__ == "__main__":
    wynik = generuj()
    print(f"strony miejscowosci: {wynik['miejscowosci']}, kancelarii: {wynik['kancelarie']}, sitemap i robots gotowe")
