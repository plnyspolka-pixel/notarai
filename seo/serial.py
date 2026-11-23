"""Serial „Kancelaria pod Siódemką” na notarai.pl.

Źródło prawdy to kolejka `serial/odcinki.json` (poza katalogiem `strona/`, więc
odcinki przed premierą nigdy nie trafiają na serwer). Generator buduje
`strona/serial/` wyłącznie z odcinków, które:
  * mają status "gotowy",
  * mają `publish_at` w przeszłości (porównanie w strefie Europe/Warsaw),
  * mają plik wideo (lokalny w repo albo adres https).
Odcinek z brakującym wideo jest pomijany i zapisany w logu, nigdy nie jest
publikowany częściowo.

Polecenia:
    python -I seo/serial.py zbuduj [--teraz 2026-11-23T16:05:00+01:00]
    python -I seo/serial.py czy-pora [--teraz ...]   # kod 0 = jest pora publikacji (9:xx albo 16:xx)
    python -I seo/serial.py plan                       # lista kolejki z decyzją dla każdego odcinka

`strona/serial/` jest w całości generowane (w .gitignore), tak jak blog i katalog.
"""

from __future__ import annotations

import html
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

KORZEN = Path(__file__).resolve().parent.parent
KOLEJKA = KORZEN / "serial" / "odcinki.json"
ZASOBY = KORZEN / "serial" / "zasoby"
CEL = KORZEN / "strona" / "serial"
STRONA = "https://notarai.pl"
STREFA = ZoneInfo("Europe/Warsaw")
GODZINY_PUBLIKACJI = (9, 16)

TYTUL_SERII = "Kancelaria pod Siódemką"
NAPIS_KONCOWY = "Na motywach prawdziwych spraw z polskich sądów. Osoby i szczegóły zmienione."
WYMAGANE_POLA = ("id", "sezon", "odcinek", "tytul", "publish_at", "pliki", "status")


def esc(t) -> str:
    return html.escape(str(t), quote=True)


def teraz_warszawa(tekst: str | None = None) -> datetime:
    if tekst:
        dt = datetime.fromisoformat(tekst)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=STREFA)
        return dt.astimezone(STREFA)
    return datetime.now(STREFA)


def wczytaj(sciezka: Path = KOLEJKA) -> dict:
    dane = json.loads(sciezka.read_text(encoding="utf-8"))
    widziane = set()
    for o in dane.get("odcinki", []):
        brak = [p for p in WYMAGANE_POLA if p not in o]
        if brak:
            raise ValueError(f"odcinek {o.get('id', '?')}: brak pól {brak}")
        if o["id"] in widziane:
            raise ValueError(f"powtórzony id {o['id']}")
        widziane.add(o["id"])
        if datetime.fromisoformat(o["publish_at"]).tzinfo is None:
            raise ValueError(f"odcinek {o['id']}: publish_at bez strefy czasowej")
        if "wideo" not in o["pliki"]:
            raise ValueError(f"odcinek {o['id']}: brak pliki.wideo")
    return dane


def _jest(plik: str | None, korzen: Path) -> bool:
    if not plik:
        return False
    if plik.startswith("https://"):
        return True
    return (korzen / plik).is_file()


def decyzja(o: dict, teraz: datetime, korzen: Path = KORZEN) -> tuple[bool, str]:
    """Czy odcinek jest opublikowany w chwili `teraz` i dlaczego."""
    if o["status"] != "gotowy":
        return False, f"status {o['status']}"
    termin = datetime.fromisoformat(o["publish_at"]).astimezone(STREFA)
    if termin > teraz:
        return False, f"premiera {termin:%Y-%m-%d %H:%M}"
    if not _jest(o["pliki"].get("wideo"), korzen):
        return False, f"BRAK WIDEO {o['pliki'].get('wideo')} - pominięty"
    return True, "opublikowany"


def opublikowane(dane: dict, teraz: datetime, korzen: Path = KORZEN, log=print) -> list[dict]:
    wynik = []
    for o in dane.get("odcinki", []):
        ok, powod = decyzja(o, teraz, korzen)
        if ok:
            # plakat i napisy są opcjonalne: do strony trafiają tylko istniejące pliki
            pliki = {k: v for k, v in o["pliki"].items() if _jest(v, korzen)}
            wynik.append(dict(o, pliki=pliki))
        elif powod.startswith("BRAK"):
            log(f"serial: {o['id']}: {powod}")
    return sorted(wynik, key=lambda o: (o["publish_at"], o["sezon"], o["odcinek"]))


def czy_pora(teraz: datetime) -> bool:
    return teraz.hour in GODZINY_PUBLIKACJI


def _url_pliku(plik: str | None, o: dict) -> str | None:
    """Adres pliku na stronie: lokalne pliki lądują w /serial/media/."""
    if not plik:
        return None
    if plik.startswith("https://"):
        return plik
    return f"/serial/media/{Path(plik).name}"


def utm(adres: str, zrodlo: str, tresc: str) -> str:
    znak = "&" if "?" in adres else "?"
    return f"{adres}{znak}utm_source={zrodlo}&utm_medium=serial&utm_campaign=komputerku&utm_content={tresc}"


def _kod(o: dict) -> str:
    return f"S{int(o['sezon']):02d}E{int(o['odcinek']):02d}"


def _data(o: dict) -> str:
    dt = datetime.fromisoformat(o["publish_at"]).astimezone(STREFA)
    return f"{dt:%d.%m.%Y, %H:%M}"


def _odtwarzacz(o: dict) -> str:
    p = o["pliki"]
    plakat = _url_pliku(p.get("plakat"), o)
    napisy = _url_pliku(p.get("napisy"), o)
    sciezka = (f'<track kind="subtitles" srclang="pl" label="Polski" src="{esc(napisy)}" default>'
               if napisy else "")
    atr_plakat = f' poster="{esc(plakat)}"' if plakat else ""
    return (f'<figure class="odtwarzacz">'
            f'<video id="wideo" controls playsinline preload="metadata" width="540" height="960"{atr_plakat} '
            f'data-odcinek="{esc(o["id"])}" aria-label="{esc(_kod(o) + " " + o["tytul"])}">'
            f'<source src="{esc(_url_pliku(p["wideo"], o))}" type="video/mp4">{sciezka}'
            f'Twoja przeglądarka nie odtwarza wideo. <a href="{esc(_url_pliku(p["wideo"], o))}">Pobierz plik</a>.'
            f'</video>'
            f'<span class="znaczek-ai" aria-label="Treść wygenerowana z pomocą AI">AI</span>'
            f'<figcaption>{esc(NAPIS_KONCOWY)}</figcaption></figure>')


def _lista(odcinki: list[dict], biezacy: str) -> str:
    if len(odcinki) < 2:
        return ""
    wiersze = []
    for o in reversed(odcinki):
        aktualny = ' aria-current="page"' if o["id"] == biezacy else ""
        wiersze.append(
            f'<li><a href="/serial/{esc(o["id"])}/" data-zdarzenie="serial_lista" data-odcinek="{esc(o["id"])}"{aktualny}>'
            f'<span class="kod">{_kod(o)}</span> {esc(o["tytul"])}</a>'
            f'<span class="data">{_data(o)}</span></li>')
    return f'<section class="lista" aria-labelledby="lista-t"><h2 id="lista-t">Wszystkie odcinki</h2><ol>{"".join(wiersze)}</ol></section>'


def strona_odcinka(o: dict, odcinki: list[dict], glowna: bool) -> str:
    idx = [x["id"] for x in odcinki].index(o["id"])
    poprz = odcinki[idx - 1] if idx > 0 else None
    nast = odcinki[idx + 1] if idx + 1 < len(odcinki) else None
    nawig = []
    if poprz:
        nawig.append(f'<a class="przycisk drugi" href="/serial/{esc(poprz["id"])}/" data-zdarzenie="serial_poprzedni" '
                     f'data-odcinek="{esc(poprz["id"])}">← {_kod(poprz)}</a>')
    if nast:
        nawig.append(f'<a class="przycisk" href="/serial/{esc(nast["id"])}/" data-zdarzenie="serial_nastepny" '
                     f'data-odcinek="{esc(nast["id"])}">Następny odcinek: {_kod(nast)} →</a>')
    else:
        nawig.append('<p class="kolejny">Kolejne odcinki codziennie o 9:00 i 16:00.</p>')
    demo = utm("https://app.notarai.pl/rejestracja", "notarai_pl", o["id"].lower())
    tytul_strony = (f"{TYTUL_SERII}: serial dla notariuszy - notarai" if glowna
                    else f"{_kod(o)} {o['tytul']} - {TYTUL_SERII} - notarai")
    kanon = f"{STRONA}/serial/" if glowna else f"{STRONA}/serial/{o['id']}/"
    opis = o.get("opis") or "Mikroserial o pracy kancelarii notarialnej."
    kotwica = f'<p class="kotwica">{esc(o["kotwica"])}</p>' if o.get("kotwica") else ""
    return f"""<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(tytul_strony)}</title>
<meta name="description" content="{esc(opis)}">
<link rel="canonical" href="{esc(kanon)}">
<link rel="alternate" type="application/rss+xml" title="{esc(TYTUL_SERII)}" href="/serial/rss.xml">
<link rel="icon" type="image/svg+xml" href="/logo-mark.svg">
<link rel="stylesheet" href="/style.css">
<link rel="stylesheet" href="/serial/serial.css">
<script src="/analityka.js" defer></script>
<script src="/serial/serial.js" defer></script>
</head>
<body>
<header class="naglowek">
  <div class="szer naglowek-w rozsun">
    <a class="marka" href="/">
      <img src="/logo-mark.svg" alt="" width="32" height="32">
      <span>notar<strong>ai</strong></span>
    </a>
    <a class="przycisk maly" href="{esc(demo)}" data-zdarzenie="serial_cta">Wypróbuj<span class="dluzsze"> w kancelarii</span></a>
  </div>
</header>
<main class="szer serial">
  <section class="naglowek-serialu">
    <p class="znacznik">Serial dla notariuszy i zespołów kancelarii</p>
    <h1>{esc(TYTUL_SERII)}</h1>
    <p class="wstep">Krótkie odcinki o zwykłym dniu kancelarii: terminy, dokumenty, ludzie i decyzje, które zawsze należą do notariusza. Nowy odcinek codziennie o 9:00 i 16:00.</p>
  </section>
  <article class="odcinek" aria-labelledby="odc-t">
    {_odtwarzacz(o)}
    <div class="opis">
      <p class="kod-odcinka">{_kod(o)} · {_data(o)}</p>
      <h2 id="odc-t">{esc(o["tytul"])}</h2>
      <p>{esc(opis)}</p>
      {kotwica}
      <nav class="nawigacja-odcinkow" aria-label="Odcinki">{"".join(nawig)}</nav>
      <div class="cta">
        <p>NotarAI porządkuje dokumenty, terminy i projekty aktów. Każdy projekt weryfikuje notariusz.</p>
        <a class="przycisk" href="{esc(demo)}" data-zdarzenie="serial_cta">Załóż konto kancelarii</a>
      </div>
    </div>
  </article>
  {_lista(odcinki, o["id"])}
  <p class="uwagi">Postacie i kancelaria są fikcyjne. Ekrany programu pochodzą z wersji demonstracyjnej na danych testowych. Film nie jest poradą prawną. <a href="/serial/rss.xml">RSS</a></p>
</main>
<footer class="stopka">
  <div class="szer stopka-w">
    <p>notarai.pl prowadzi Fundacja Krzewienia Edukacji Finansowej im. Pieczaka, Lublin.</p>
    <p><a href="/prywatnosc/">Polityka prywatności</a> · <a href="#cookies">Ustawienia cookie</a></p>
  </div>
</footer>
</body>
</html>
"""


def rss(odcinki: list[dict]) -> str:
    pozycje = []
    for o in reversed(odcinki):
        dt = datetime.fromisoformat(o["publish_at"]).astimezone(STREFA)
        adres = f"{STRONA}/serial/{o['id']}/"
        wideo = _url_pliku(o["pliki"]["wideo"], o)
        wideo_abs = wideo if wideo.startswith("https://") else STRONA + wideo
        pozycje.append(
            f"<item><title>{esc(_kod(o) + ' ' + o['tytul'])}</title><link>{esc(adres)}</link>"
            f"<guid isPermaLink=\"true\">{esc(adres)}</guid>"
            f"<pubDate>{dt.strftime('%a, %d %b %Y %H:%M:%S %z')}</pubDate>"
            f"<description>{esc(o.get('opis', ''))}</description>"
            f"<enclosure url=\"{esc(wideo_abs)}\" type=\"video/mp4\" length=\"0\"/></item>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel>'
            f"<title>{esc(TYTUL_SERII)}</title><link>{STRONA}/serial/</link>"
            "<description>Serial NotarAI dla notariuszy. Nowe odcinki o 9:00 i 16:00.</description>"
            f"<language>pl</language>{''.join(pozycje)}</channel></rss>\n")


def strona_przed_premiera() -> str:
    return f"""<!doctype html>
<html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(TYTUL_SERII)} - wkrótce - notarai</title><meta name="robots" content="noindex">
<link rel="icon" type="image/svg+xml" href="/logo-mark.svg"><link rel="stylesheet" href="/style.css">
<link rel="stylesheet" href="/serial/serial.css"><script src="/analityka.js" defer></script></head>
<body><main class="szer serial"><section class="naglowek-serialu"><p class="znacznik">Serial dla notariuszy</p>
<h1>{esc(TYTUL_SERII)}</h1><p class="wstep">Pierwszy odcinek już wkrótce. Nowe odcinki codziennie o 9:00 i 16:00.</p>
<p><a class="przycisk" href="/">Wróć na notarai.pl</a></p></section></main></body></html>
"""


def dopisz_do_sitemap(odcinki: list[dict], sitemap: Path) -> bool:
    if not sitemap.is_file() or not odcinki:
        return False
    tresc = sitemap.read_text(encoding="utf-8")
    dzis = datetime.now(STREFA).date().isoformat()
    adresy = [f"{STRONA}/serial/"] + [f"{STRONA}/serial/{o['id']}/" for o in odcinki]
    nowe = "".join(f"<url><loc>{esc(a)}</loc><lastmod>{dzis}</lastmod></url>\n"
                   for a in adresy if f"<loc>{esc(a)}</loc>" not in tresc)
    if not nowe:
        return False
    sitemap.write_text(tresc.replace("</urlset>", nowe + "</urlset>"), encoding="utf-8")
    return True


def zbuduj(teraz: datetime, kolejka: Path = KOLEJKA, cel: Path = CEL, korzen: Path = KORZEN,
           zasoby: Path = ZASOBY, log=print) -> list[dict]:
    # Pliki wrzucone ręcznie do strona/serial/media/ przenosimy do źródła serial/media/,
    # bo katalog strona/serial/ jest w całości generowany (i kasowany przy każdej budowie).
    zrodlo_media = korzen / "serial" / "media"
    if (cel / "media").is_dir():
        zrodlo_media.mkdir(parents=True, exist_ok=True)
        for plik in (cel / "media").iterdir():
            if plik.is_file() and not (zrodlo_media / plik.name).exists():
                shutil.copy2(plik, zrodlo_media / plik.name)
                log(f"serial: {plik.name} przeniesiony do serial/media/")
    dane = wczytaj(kolejka)
    odcinki = opublikowane(dane, teraz, korzen, log)
    if cel.exists():
        shutil.rmtree(cel)
    (cel / "media").mkdir(parents=True)
    for plik in ("serial.css", "serial.js"):
        shutil.copyfile(zasoby / plik, cel / plik)
    for o in odcinki:
        for plik in o["pliki"].values():
            if plik and not plik.startswith("https://"):
                shutil.copyfile(korzen / plik, cel / "media" / Path(plik).name)
        (cel / o["id"]).mkdir()
        (cel / o["id"] / "index.html").write_text(strona_odcinka(o, odcinki, False), encoding="utf-8")
    if odcinki:
        (cel / "index.html").write_text(strona_odcinka(odcinki[-1], odcinki, True), encoding="utf-8")
    else:
        (cel / "index.html").write_text(strona_przed_premiera(), encoding="utf-8")
    (cel / "rss.xml").write_text(rss(odcinki), encoding="utf-8")
    publiczne = [{k: o[k] for k in ("id", "sezon", "odcinek", "tytul", "publish_at")}
                 | {"adres": f"{STRONA}/serial/{o['id']}/"} for o in odcinki]
    (cel / "odcinki.json").write_text(json.dumps({"seria": TYTUL_SERII, "odcinki": publiczne},
                                                 ensure_ascii=False, indent=1), encoding="utf-8")
    dopisz_do_sitemap(odcinki, korzen / "strona" / "sitemap.xml")
    log(f"serial: opublikowanych odcinków {len(odcinki)} (stan na {teraz:%Y-%m-%d %H:%M} Europe/Warsaw)")
    return odcinki


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    t = teraz_warszawa(argv[argv.index("--teraz") + 1] if "--teraz" in argv else None)
    if argv[0] == "zbuduj":
        zbuduj(t)
        return 0
    if argv[0] == "czy-pora":
        pora = czy_pora(t)
        print(f"{t:%Y-%m-%d %H:%M} Europe/Warsaw: {'pora publikacji' if pora else 'poza oknem 9:xx/16:xx'}")
        return 0 if pora else 1
    if argv[0] == "plan":
        for o in wczytaj().get("odcinki", []):
            print(f"{o['id']}: {decyzja(o, t)[1]}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
