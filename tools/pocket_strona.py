"""Dodatki strony notarai.pl/pocket/, których nie ma w eksporcie z gałęzi V2.

`v2/tools/export_pocket.py` nadpisuje index.html, manifest i service worker. Po każdym eksporcie:

    python3 tools/pocket_strona.py

Skrypt jest powtarzalny (drugie uruchomienie nic nie zmienia) i dopisuje:
- ikony PNG do manifestu (instalacja na Androidzie),
- skrypt aktualizacja.js (informacja o nowszej paczce aplikacji),
- ikonę i tryb pełnoekranowy dla iPhone'a,
- marka.css, sygnet i nazwa NotarAI (identyfikacja wizualna jak na notarai.pl),
- powitanie.js i powitanie.css (ekran niesparowanego telefonu: jak połączyć go z kancelarią),
- pobieranie powłoki z pominięciem pamięci podręcznej HTTP, żeby nowa wersja strony trafiała do
  wszystkich przy najbliższym otwarciu, a nie po wygaśnięciu kopii w telefonie.
Pilnuje tego test_pocket_android.py.
"""
import json
import re
from pathlib import Path

KATALOG = Path(__file__).resolve().parents[1] / "strona" / "pocket"
IKONY = [
    {"src": "logo-mark.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any"},
    {"src": "pocket-icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
    {"src": "pocket-icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
    {"src": "pocket-icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
]
# Identyfikacja wizualna NotarAI (strona/brand-site.css): granat paska systemowego i jasne tło.
MARKA = {"name": "NotarAI", "short_name": "NotarAI", "theme_color": "#071d49", "background_color": "#f4f7fc"}
NAGLOWEK = ('    <h1 class="marka"><img src="logo-mark.svg" alt="" width="34" height="34">'
            '<span>notar<strong>ai</strong></span><span class="marka-dopisek">Pocket</span></h1>')


def _zamien(tekst: str, stare: str, nowe: str, plik: str) -> str:
    if nowe in tekst:
        return tekst
    if stare not in tekst:
        raise SystemExit(f"{plik}: nie znaleziono miejsca na zmianę ({stare!r}); eksport z V2 się zmienił.")
    return tekst.replace(stare, nowe, 1)


def dopisz(katalog: Path = KATALOG) -> None:
    plik = katalog / "pocket.webmanifest"
    manifest = json.loads(plik.read_text(encoding="utf-8"))
    manifest["icons"] = IKONY
    manifest.update(MARKA)
    wiersze = [f"  {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}," for k, v in manifest.items() if k != "icons"]
    ikony = ",\n".join("    " + json.dumps(i) for i in IKONY)
    plik.write_text("{\n" + "\n".join(wiersze) + '\n  "icons": [\n' + ikony + "\n  ]\n}\n", encoding="utf-8")

    plik = katalog / "index.html"
    html = _zamien(plik.read_text(encoding="utf-8"), '  <script src="tunnel.js"></script>',
                   '  <script src="aktualizacja.js"></script>\n  <script src="tunnel.js"></script>', plik.name)
    html = _zamien(html, '  <script src="pocket.js"></script>',
                   '  <script src="pocket.js"></script>\n  <script src="powitanie.js"></script>', plik.name)
    html = _zamien(html, '  <link rel="stylesheet" href="pocket.css">',
                   '  <link rel="stylesheet" href="pocket.css">\n  <link rel="stylesheet" href="powitanie.css">', plik.name)
    html = _zamien(html, '  <link rel="stylesheet" href="powitanie.css">',
                   '  <link rel="stylesheet" href="powitanie.css">\n  <link rel="stylesheet" href="marka.css">', plik.name)
    html = _zamien(html, "    <h1>NotarAI Pocket</h1>", NAGLOWEK, plik.name)
    html = _zamien(html, '<meta name="theme-color" content="#0d6b57">', '<meta name="theme-color" content="#071d49">', plik.name)
    html = _zamien(html, '<link rel="icon" href="pocket-icon.svg" type="image/svg+xml">',
                   '<link rel="icon" href="logo-mark.svg" type="image/svg+xml">', plik.name)
    html = _zamien(html, "<title>NotarAI Pocket</title>", "<title>NotarAI</title>", plik.name)
    # iPhone: ikona i tryb pełnoekranowy po „Dodaj do ekranu początkowego” w Safari.
    html = _zamien(html, '  <link rel="manifest" href="pocket.webmanifest">',
                   '  <link rel="manifest" href="pocket.webmanifest">\n'
                   '  <link rel="apple-touch-icon" href="pocket-icon-180.png">\n'
                   '  <meta name="apple-mobile-web-app-capable" content="yes">\n'
                   '  <meta name="apple-mobile-web-app-title" content="NotarAI">', plik.name)
    # Krój Montserrat leży na tej samej domenie (strona/fonts); bez tego wpisu CSP by go zablokowała.
    html = _zamien(html, "style-src 'self'; img-src", "style-src 'self'; font-src 'self'; img-src", plik.name)
    plik.write_text(html, encoding="utf-8")

    plik = katalog / "pocket-sw.js"
    sw = plik.read_text(encoding="utf-8")
    sw = _zamien(sw, '"tunnel.js", ', '"tunnel.js", "aktualizacja.js", ', plik.name)
    sw = _zamien(sw, '"aktualizacja.js", ', '"aktualizacja.js", "powitanie.js", "powitanie.css", ', plik.name)
    sw = _zamien(sw, '"powitanie.css", ', '"powitanie.css", "marka.css", "logo-mark.svg", ', plik.name)
    sw = _zamien(sw, "event.respondWith(fetch(event.request).then(",
                 'event.respondWith(fetch(event.request, { cache: "no-cache" }).then(', plik.name)
    sw, zmian = re.subn(r'const SHELL = "pocket-shell-v\d+";', 'const SHELL = "pocket-shell-v5";', sw)
    if zmian != 1:
        raise SystemExit(f"{plik.name}: nie znaleziono nazwy pamięci powłoki; eksport z V2 się zmienił.")
    plik.write_text(sw, encoding="utf-8")


if __name__ == "__main__":
    dopisz()
