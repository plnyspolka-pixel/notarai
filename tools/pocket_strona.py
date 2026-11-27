"""Dodatki strony notarai.pl/pocket/, których nie ma w eksporcie z gałęzi V2.

`v2/tools/export_pocket.py` nadpisuje index.html, manifest i service worker. Po każdym eksporcie:

    python3 tools/pocket_strona.py

Skrypt jest powtarzalny (drugie uruchomienie nic nie zmienia) i dopisuje:
- ikony PNG do manifestu (instalacja na Androidzie),
- skrypt aktualizacja.js (informacja o nowszej paczce aplikacji),
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
    {"src": "pocket-icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any"},
    {"src": "pocket-icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
    {"src": "pocket-icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
    {"src": "pocket-icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
]


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
    plik.write_text(html, encoding="utf-8")

    plik = katalog / "pocket-sw.js"
    sw = plik.read_text(encoding="utf-8")
    sw = _zamien(sw, '"tunnel.js", ', '"tunnel.js", "aktualizacja.js", ', plik.name)
    sw = _zamien(sw, '"aktualizacja.js", ', '"aktualizacja.js", "powitanie.js", "powitanie.css", ', plik.name)
    sw = _zamien(sw, "event.respondWith(fetch(event.request).then(",
                 'event.respondWith(fetch(event.request, { cache: "no-cache" }).then(', plik.name)
    sw, zmian = re.subn(r'const SHELL = "pocket-shell-v\d+";', 'const SHELL = "pocket-shell-v4";', sw)
    if zmian != 1:
        raise SystemExit(f"{plik.name}: nie znaleziono nazwy pamięci powłoki; eksport z V2 się zmienił.")
    plik.write_text(sw, encoding="utf-8")


if __name__ == "__main__":
    dopisz()
