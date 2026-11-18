#!/usr/bin/env python3
"""Składa propozycję strony głównej v2 (strona/v2/index.html) z obecnej strona/index.html.

Treść ma jedno źródło: obecną stronę główną. Skrypt zmienia tylko oprawę:
dopina premium.css i premium.js, zamienia sekcję "tematy" w akordeon i cennik w karty pakietów.
Każda zamiana jest sprawdzana; gdy strona główna zmieni się tak, że wzorzec nie pasuje,
skrypt kończy się błędem zamiast wygenerować coś po cichu.

    python3 tools/web-factory/v2/buduj.py
"""
from __future__ import annotations

import re
from pathlib import Path

KORZEN = Path(__file__).resolve().parents[3]
ZRODLO = KORZEN / "strona" / "index.html"
CEL = KORZEN / "strona" / "v2" / "index.html"


def zamien(tekst: str, stare: str, nowe: str, ile: int = 1) -> str:
    if tekst.count(stare) != ile:
        raise SystemExit(f"Wzorzec występuje {tekst.count(stare)} razy zamiast {ile}: {stare[:70]!r}")
    return tekst.replace(stare, nowe)


def przepnij_sciezki(tekst: str) -> str:
    """Strona leży katalog niżej, więc lokalne adresy dostają '../'."""
    def popraw(m: re.Match) -> str:
        atrybut, adres = m.group(1), m.group(2)
        if adres.startswith(("http:", "https:", "mailto:", "tel:", "#", "data:", "../")) or adres == "./":
            return m.group(0)
        return f'{atrybut}="../{adres}"'
    return re.sub(r'\b(href|src)="([^"]*)"', popraw, tekst)


def akordeon(tekst: str) -> str:
    poczatek = tekst.index('<div class="tematy">')
    koniec = tekst.index('<div class="ramka">', poczatek)
    blok = tekst[poczatek:koniec]
    artykuly = re.findall(r'<article( class="pakiet")?>\s*<h3>(.*?)</h3>(.*?)</article>', blok, re.S)
    if len(artykuly) != 6:
        raise SystemExit(f"Sekcja 'tematy' ma {len(artykuly)} artykułów zamiast 6")
    czesci = []
    for nr, (pakiet, tytul, reszta) in enumerate(artykuly):
        klasa = "p-temat pakiet" if pakiet else "p-temat"
        otwarty = " open" if nr == 0 else ""
        czesci.append(
            f'      <details class="{klasa}" name="zgodnosc"{otwarty}>\n'
            f'        <summary><h3>{tytul}</h3></summary>{reszta.rstrip()}\n'
            f'      </details>')
    nowy = '<div class="tematy">\n' + "\n".join(czesci) + '\n    </div>\n\n    '
    return tekst[:poczatek] + nowy + tekst[koniec:]


CENNIK = '''<section id="cennik" class="sekcja">
  <div class="szer p-cennik">
    <div>
      <h2>Płacisz za to, z czego korzystasz</h2>
      <p class="wstep">Bez abonamentu. Odczyt skanu, rozmowa o sprawie czy projekt aktu kosztują kredyty, a czynność, która się nie uda, nic nie kosztuje. Pakiety kupujesz w aplikacji (BLIK, przelew, karta), fakturę dostajesz e-mailem. Jesteśmy zwolnieni z VAT, więc cena pakietu to cała kwota.</p>
    </div>
    <div class="p-pakiety">
      <article class="p-pakiet p-pakiet--start">
        <small>Na start</small>
        <strong>150 kr.</strong>
        <b>0 zł</b>
        <span>Za darmo, bez karty.</span>
        <a class="przycisk pelny" href="https://app.notarai.pl/rejestracja">Załóż konto i wypróbuj</a>
      </article>
      <article class="p-pakiet">
        <small>Pakiet</small>
        <strong>100 kr.</strong>
        <b>100 zł</b>
        <span>1,00 zł za kredyt</span>
      </article>
      <article class="p-pakiet">
        <small>Pakiet</small>
        <strong>500 kr.</strong>
        <b>450 zł</b>
        <span>0,90 zł za kredyt</span>
      </article>
      <article class="p-pakiet">
        <small>Pakiet</small>
        <strong>2000 kr.</strong>
        <b>1600 zł</b>
        <span>0,80 zł za kredyt</span>
      </article>
    </div>
    <ul class="p-cennik__uwagi">
      <li>Typowa sprawa z projektem aktu: ok. 65–80 kredytów</li>
      <li>Kalendarz, sprawy i konta dla całego zespołu bez opłat</li>
    </ul>
  </div>
</section>'''


def cennik(tekst: str) -> str:
    poczatek = tekst.index('<section id="cennik" class="sekcja">')
    koniec = tekst.index('</section>', poczatek) + len('</section>')
    stary = tekst[poczatek:koniec]
    # Ceny są przepisane do kart; gdy zmienią się w źródle, skrypt ma to zauważyć.
    for fakt in ("100 kr. za 100 zł", "500 kr. za 450 zł", "2000 kr. za 1600 zł",
                 "150 kredytów na start za darmo, bez karty", "ok. 65–80 kredytów",
                 "Kalendarz, sprawy i konta dla całego zespołu bez opłat", "od 0,80 zł"):
        if fakt not in stary:
            raise SystemExit(f"Cennik w źródle się zmienił, brak: {fakt!r}. Popraw karty w buduj.py.")
    return tekst[:poczatek] + CENNIK + tekst[koniec:]


def buduj() -> str:
    t = ZRODLO.read_text(encoding="utf-8")
    t = przepnij_sciezki(t)
    t = zamien(t, '<link rel="stylesheet" href="../brand-site.css">',
               '<link rel="stylesheet" href="../brand-site.css">\n'
               '<link rel="preload" href="../fonts/montserrat-latin-wght-normal.woff2" as="font" type="font/woff2" crossorigin>\n'
               '<link rel="stylesheet" href="premium.css">\n'
               '<meta name="robots" content="noindex">\n'
               '<link rel="canonical" href="https://notarai.pl/">')
    t = zamien(t, '<body>', '<body class="v2">\n<div class="p-postep" aria-hidden="true"></div>')
    t = zamien(t, '<a class="brand-logo" href="./"', '<a class="brand-logo" href="../"')
    t = zamien(t, '<a class="brand-logo brand-logo--inverse" href="./"', '<a class="brand-logo brand-logo--inverse" href="../"')
    t = zamien(t, 'Nowoczesna obsługa notarialna <span>z mocą AI</span>',
               'Nowoczesna obsługa notarialna <span class="p-akcent">z mocą AI</span>')
    t = akordeon(t)
    t = cennik(t)
    t = zamien(t, '</script>\n</body>', '</script>\n<script src="premium.js" defer></script>\n</body>')
    return t


if __name__ == "__main__":
    CEL.parent.mkdir(parents=True, exist_ok=True)
    wynik = buduj()
    wynik = wynik.replace("<!doctype html>", "<!doctype html>\n<!-- Plik generowany: python3 tools/web-factory/v2/buduj.py. Nie edytuj ręcznie. -->", 1)
    CEL.write_text(wynik, encoding="utf-8")
    print(f"Zapisano {CEL.relative_to(KORZEN)} ({len(wynik)} znaków)")
