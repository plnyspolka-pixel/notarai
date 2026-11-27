"""Podstrona notarai.pl/pocket/: statyczna powłoka aplikacji NotarAI Pocket (wersja 2.0).

Strona nie przechowuje danych i nie łączy się z niczym poza zaszyfrowanym tunelem przez
przekaźnik NotarAI. Pliki są kopią z gałęzi V2 (`python v2/tools/export_pocket.py strona/pocket`).
Statyczne sprawdzenia, bez sieci.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KATALOG = ROOT / "strona" / "pocket"
PRZEKAZNIK = "wss://qj7nel6in9.execute-api.eu-central-1.amazonaws.com"
PLIKI = ("index.html", "pocket.css", "pocket.js", "tunnel.js", "pocket-sw.js", "pocket.webmanifest", "pocket-icon.svg")


def test_wszystkie_pliki_powloki_sa_i_sa_podpiete():
    for plik in PLIKI:
        assert (KATALOG / plik).is_file(), plik
    html = (KATALOG / "index.html").read_text(encoding="utf-8")
    for plik in ("pocket.css", "pocket.js", "tunnel.js", "pocket.webmanifest", "logo-mark.svg"):   # ikona: sygnet NotarAI
        assert f'"{plik}"' in html, plik
    assert "/v2/" not in html      # na notarai.pl nie ma API stanowiska: tylko ścieżki względne


def test_bez_skryptow_i_stylow_inline_ani_obcych_zrodel():
    """Strona działa pod ścisłą polityką CSP (script-src 'self'), także gdy hosting jej nie ustawia."""
    html = (KATALOG / "index.html").read_text(encoding="utf-8")
    assert "<style" not in html and " style=" not in html and re.search(r"\son[a-z]+=", html) is None
    for src in re.findall(r'(?:src|href)="([^"]+)"', html):
        assert not re.match(r"(?:https?:)?//", src), src
    for plik in ("pocket.js", "tunnel.js", "pocket-sw.js"):
        kod = (KATALOG / plik).read_text(encoding="utf-8")
        assert "eval(" not in kod and "new Function" not in kod and "innerHTML" not in kod, plik


def test_polaczenia_tylko_przez_tunel_tls():
    tunel = (KATALOG / "tunnel.js").read_text(encoding="utf-8")
    assert 'generateKey({ name: "ECDSA", namedCurve: "P-256" }, false' in tunel   # klucz urządzenia nieeksportowalny
    assert re.search(r"https?://", (KATALOG / "pocket.js").read_text(encoding="utf-8")) is None


def test_service_worker_nie_przechowuje_odpowiedzi_api():
    sw = (KATALOG / "pocket-sw.js").read_text(encoding="utf-8")
    assert '"./"' in sw and "/v2/" not in sw
    assert 'event.request.method !== "GET"' in sw


def test_manifest_startuje_w_katalogu_pocket():
    manifest = json.loads((KATALOG / "pocket.webmanifest").read_text(encoding="utf-8"))
    assert manifest["start_url"] == "./" and manifest["scope"] == "./"
    assert manifest["display"] == "standalone" and manifest["lang"] == "pl"


def test_pocket_poza_wyszukiwarkami_i_sitemap():
    robots = (ROOT / "strona" / "robots.txt").read_text(encoding="utf-8")
    assert "Disallow: /pocket/" in robots
    zrodlo = (ROOT / "seo" / "generuj.py").read_text(encoding="utf-8")
    assert "Disallow: /pocket/" in zrodlo          # generator w workflow nie nadpisze tego wpisu
    sitemap = ROOT / "strona" / "sitemap.xml"
    if sitemap.is_file():
        assert "/pocket" not in sitemap.read_text(encoding="utf-8")


def test_wysylka_ftp_obejmuje_pliki_pocket():
    import importlib.util

    spec = importlib.util.spec_from_file_location("strona_ftp", ROOT / "infra" / "strona_ftp.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    lokalne = modul.pliki_lokalne(str(ROOT / "strona"))
    for plik in PLIKI:
        assert f"pocket/{plik}" in lokalne, plik


def test_adres_przekaznika_jest_tlsowym_adresem_z_instalacji():
    """Kod QR z panelu stanowiska prowadzi tu z adresem przekaźnika; strona musi przyjąć wss://."""
    tunel = (KATALOG / "tunnel.js").read_text(encoding="utf-8")
    assert re.search(r"\^wss:\\/\\/\[A-Za-z0-9\.-\]\+", tunel)
    assert PRZEKAZNIK.startswith("wss://")


def test_strona_niesie_wlasna_polityke_bezpieczenstwa():
    """Hosting nie ustawia nagłówka CSP, więc strona ma go w sobie; łączy się tylko z przekaźnikiem."""
    html = (KATALOG / "index.html").read_text(encoding="utf-8")
    csp = re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', html).group(1)
    assert "default-src 'none'" in csp and "script-src 'self';" in csp and "'unsafe" not in csp
    assert f"connect-src 'self' {PRZEKAZNIK};" in csp
    assert '<meta name="robots" content="noindex">' in html
