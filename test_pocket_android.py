"""NotarAI Pocket na Androida: powłoka TWA w `android/pocket/` i jej powiązanie ze stroną.

Aplikacja nie ma własnego kodu: otwiera https://notarai.pl/pocket/ w Chrome telefonu. Pasek adresu
znika tylko wtedy, gdy strona i aplikacja wskazują na siebie nawzajem, więc pilnujemy obu połówek.
Statyczne sprawdzenia, bez sieci i bez Android SDK.
"""
import json
import re
import hashlib
import struct
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ANDROID = ROOT / "android" / "pocket"
STRONA = ROOT / "strona"
NS = "{http://schemas.android.com/apk/res/android}"
PAKIET = "pl.notarai.pocket"


def _manifest_aplikacji():
    return ET.parse(ANDROID / "app" / "src" / "main" / "AndroidManifest.xml").getroot()


def _meta(aktywnosc):
    return {m.get(NS + "name"): m.get(NS + "value") for m in aktywnosc.findall("meta-data")}


def test_aplikacja_otwiera_pocket_na_notarai_pl():
    gradle = (ANDROID / "app" / "build.gradle").read_text(encoding="utf-8")
    assert f'applicationId "{PAKIET}"' in gradle and f'namespace "{PAKIET}"' in gradle
    aktywnosc = next(a for a in _manifest_aplikacji().iter("activity") if a.get(NS + "name").endswith("LauncherActivity"))
    meta = _meta(aktywnosc)
    # Powłoka podaje stronie swój numer paczki; strona porównuje go z wersja.json.
    assert meta["android.support.customtabs.trusted.DEFAULT_URL"] == "https://notarai.pl/pocket/?apk=${kodWersji}"
    assert "manifestPlaceholders = [kodWersji: kodWersji.toString()]" in gradle and "versionCode kodWersji" in gradle
    # Bez Chrome strona idzie do karty przeglądarki, nigdy do WebView: klucz urządzenia zostaje w przeglądarce.
    assert meta["android.support.customtabs.trusted.FALLBACK_STRATEGY"] == "customtabs"


def test_kod_qr_otwiera_aplikacje_tylko_dla_pocket():
    filtry = [f for f in _manifest_aplikacji().iter("intent-filter") if f.get(NS + "autoVerify") == "true"]
    assert len(filtry) == 1
    dane = filtry[0].find("data")
    assert (dane.get(NS + "scheme"), dane.get(NS + "host"), dane.get(NS + "pathPrefix")) == ("https", "notarai.pl", "/pocket/")


def test_aplikacja_nie_prosi_o_uprawnienia_i_nie_robi_kopii():
    korzen = _manifest_aplikacji()
    for wpis in korzen.findall("uses-permission"):
        assert wpis.get("{http://schemas.android.com/tools}node") == "remove", wpis.get(NS + "name")
    aplikacja = korzen.find("application")
    assert aplikacja.get(NS + "allowBackup") == "false"
    assert aplikacja.get(NS + "usesCleartextTraffic") == "false"


def test_strona_potwierdza_aplikacje_w_assetlinks():
    wpisy = json.loads((STRONA / ".well-known" / "assetlinks.json").read_text(encoding="utf-8"))
    cele = [w["target"] for w in wpisy if "delegate_permission/common.handle_all_urls" in w["relation"]]
    assert [c["package_name"] for c in cele] == [PAKIET]
    odciski = cele[0]["sha256_cert_fingerprints"]
    assert odciski and all(re.fullmatch(r"(?:[0-9A-F]{2}:){31}[0-9A-F]{2}", o) for o in odciski)
    zasoby = (ANDROID / "app" / "src" / "main" / "res" / "values" / "zasoby.xml").read_text(encoding="utf-8")
    assert "https://notarai.pl" in zasoby and "delegate_permission/common.handle_all_urls" in zasoby


def test_wysylka_ftp_obejmuje_assetlinks_ale_nie_inne_ukryte(tmp_path):
    from infra import strona_ftp

    assert ".well-known/assetlinks.json" in strona_ftp.pliki_lokalne(str(STRONA))
    (tmp_path / ".well-known").mkdir()
    (tmp_path / ".well-known" / "assetlinks.json").write_text("[]")
    (tmp_path / ".well-known" / ".ukryty").write_text("x")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("x")
    (tmp_path / ".htaccess").write_text("x")
    (tmp_path / "index.html").write_text("x")
    assert sorted(strona_ftp.pliki_lokalne(str(tmp_path))) == [".well-known/assetlinks.json", "index.html"]


def test_manifest_strony_ma_ikony_png_dla_androida():
    """Bez ikon PNG 192 i 512 Chrome na Androidzie nie proponuje pełnej instalacji.
    Po `export_pocket.py` z gałęzi V2 ikony trzeba zachować; ten test o tym przypomina."""
    katalog = STRONA / "pocket"
    ikony = json.loads((katalog / "pocket.webmanifest").read_text(encoding="utf-8"))["icons"]
    png = {(i["sizes"], i["purpose"]): i["src"] for i in ikony if i["type"] == "image/png"}
    assert {("192x192", "any"), ("512x512", "any"), ("512x512", "maskable")} <= set(png)
    for (rozmiar, _), plik in png.items():
        dane = (katalog / plik).read_bytes()
        assert dane[:8] == b"\x89PNG\r\n\x1a\n", plik
        assert "%dx%d" % struct.unpack(">II", dane[16:24]) == rozmiar, plik


def _odcisk_certyfikatu_apk(dane: bytes) -> str:
    """SHA-256 certyfikatu z podpisu APK v2 (blok przed katalogiem centralnym ZIP)."""
    koniec = dane.rindex(b"PK\x05\x06")
    katalog = struct.unpack("<I", dane[koniec + 16:koniec + 20])[0]
    assert dane[katalog - 16:katalog] == b"APK Sig Block 42"
    rozmiar = struct.unpack("<Q", dane[katalog - 24:katalog - 16])[0]
    pary, i = dane[katalog - rozmiar:katalog - 24], 0
    while i < len(pary):
        dlugosc, klucz = struct.unpack("<QI", pary[i:i + 12])
        if klucz == 0x7109871A:
            # podpisujący > pierwszy podpisujący > dane podpisane > skróty, potem certyfikaty
            p = i + 12 + 4 + 4 + 4
            p += 4 + struct.unpack("<I", pary[p:p + 4])[0]
            n = struct.unpack("<I", pary[p + 4:p + 8])[0]
            return hashlib.sha256(pary[p + 8:p + 8 + n]).hexdigest().upper()
        i += 8 + dlugosc
    raise AssertionError("brak podpisu APK v2")


def test_apk_na_stronie_jest_podpisane_kluczem_z_assetlinks():
    """Paczka do pobrania z notarai.pl: podpisana tym samym kluczem, który strona potwierdza.
    Inny klucz oznacza pasek adresu w aplikacji i odmowę aktualizacji na telefonach."""
    from infra import strona_ftp

    dane = (STRONA / "pocket" / "NotarAI-Pocket.apk").read_bytes()
    odcisk = _odcisk_certyfikatu_apk(dane)
    wpisy = json.loads((STRONA / ".well-known" / "assetlinks.json").read_text(encoding="utf-8"))
    assert ":".join(odcisk[i:i + 2] for i in range(0, 64, 2)) in wpisy[0]["target"]["sha256_cert_fingerprints"]
    assert "pocket/NotarAI-Pocket.apk" in strona_ftp.pliki_lokalne(str(STRONA))
    html = (STRONA / "do-pobrania" / "index.html").read_text(encoding="utf-8")
    assert 'href="../pocket/NotarAI-Pocket.apk"' in html
    gradle = (ANDROID / "app" / "build.gradle").read_text(encoding="utf-8")
    wersja = re.search(r'versionName "([^"]+)"', gradle).group(1)
    assert f"Wersja {wersja}" in html
    # Ten sam numer w paczce i na stronie; inaczej telefony dostaną fałszywą informację o aktualizacji.
    opis = json.loads((STRONA / "pocket" / "wersja.json").read_text(encoding="utf-8"))
    assert opis == {"versionCode": int(re.search(r"def kodWersji = (\d+)", gradle).group(1)), "versionName": wersja}
    import io
    import zipfile

    binarny = zipfile.ZipFile(io.BytesIO(dane)).read("AndroidManifest.xml")
    adres = f"https://notarai.pl/pocket/?apk={opis['versionCode']}"      # paczka na stronie ma ten sam numer
    assert adres.encode("utf-8") + b"\x00" in binarny or adres.encode("utf-16-le") + b"\x00\x00" in binarny


def test_nowe_funkcje_trafiaja_do_wszystkich_bez_nowej_paczki():
    """Aplikacja wyświetla stronę, więc aktualizuje się razem z nią. Service worker pobiera powłokę
    z pominięciem pamięci HTTP (nowa wersja przy najbliższym otwarciu), a o nowszej paczce informuje
    aktualizacja.js. Po eksporcie z V2 te dodatki dopisuje tools/pocket_strona.py."""
    katalog = STRONA / "pocket"
    sw = (katalog / "pocket-sw.js").read_text(encoding="utf-8")
    assert 'fetch(event.request, { cache: "no-cache" })' in sw and '"aktualizacja.js"' in sw
    assert "self.skipWaiting()" in sw and "self.clients.claim()" in sw
    html = (katalog / "index.html").read_text(encoding="utf-8")
    assert html.index('src="aktualizacja.js"') < html.index('src="pocket.js"')
    kod = (katalog / "aktualizacja.js").read_text(encoding="utf-8")
    assert 'fetch("wersja.json", { cache: "no-store" })' in kod and "innerHTML" not in kod and "eval(" not in kod
    assert re.search(r"https?://", kod) is None           # tylko własne pliki, zgodnie z CSP strony
    przed = {p.name: p.read_bytes() for p in katalog.iterdir()}
    import importlib.util

    spec = importlib.util.spec_from_file_location("pocket_strona", ROOT / "tools" / "pocket_strona.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    modul.dopisz()                                         # powtarzalne: nic nie zmienia w gotowej stronie
    assert przed == {p.name: p.read_bytes() for p in katalog.iterdir()}


def test_klucz_podpisu_nie_lezy_w_repozytorium():
    sledzone = subprocess.run(["git", "ls-files", "android"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    assert not [p for p in sledzone if p.endswith((".jks", ".keystore", ".p12", ".apk", ".aab"))]
    gradle = (ANDROID / "app" / "build.gradle").read_text(encoding="utf-8")
    assert 'System.getenv("NOTARAI_POCKET_KEYSTORE_HASLO")' in gradle
    assert re.search(r'(storePassword|keyPassword)\s+"', gradle) is None


def test_niesparowany_telefon_dostaje_instrukcje_i_skaner():
    """Kto dopiero pobrał aplikację, widzi, czym ona jest i jak połączyć ją z kancelarią (powitanie.js).
    Skaner przyjmuje wyłącznie kod parowania prowadzący na tę samą stronę."""
    from infra import strona_ftp

    katalog = STRONA / "pocket"
    html = (katalog / "index.html").read_text(encoding="utf-8")
    assert 'href="powitanie.css"' in html
    assert html.index('src="pocket.js"') < html.index('src="powitanie.js"')     # po pocket.js i tunnel.js
    sw = (katalog / "pocket-sw.js").read_text(encoding="utf-8")
    assert '"powitanie.js"' in sw and '"powitanie.css"' in sw
    kod = (katalog / "powitanie.js").read_text(encoding="utf-8")
    assert "innerHTML" not in kod and "eval(" not in kod
    assert set(re.findall(r"https?://[^\s\"']+", kod)) == {"https://app.notarai.pl/"}     # jedyny obcy adres: konto kancelarii
    assert "adres.origin !== window.location.origin || adres.pathname !== window.location.pathname" in kod
    assert "NotaraiTunnel.parseLink(adres.hash)" in kod and "window.NotaraiTunnel" not in kod
    assert "„dodaj telefon”" in kod and "„cofnij telefon”" in kod
    assert "audio: false" in kod                                              # skaner nie włącza mikrofonu
    lokalne = strona_ftp.pliki_lokalne(str(STRONA))
    assert "pocket/powitanie.js" in lokalne and "pocket/powitanie.css" in lokalne


def test_pocket_ma_identyfikacje_wizualna_notarai():
    """Aplikacja i strona Pocket wyglądają jak NotarAI: sygnet, granat i niebieski z notarai.pl, krój
    Montserrat, nazwa NotarAI pod ikoną. Zielona paleta prototypu nie wraca po eksporcie z V2."""
    katalog = STRONA / "pocket"
    assert (katalog / "logo-mark.svg").read_bytes() == (STRONA / "logo-mark.svg").read_bytes()
    html = (katalog / "index.html").read_text(encoding="utf-8")
    assert 'href="marka.css"' in html and html.index('href="pocket.css"') < html.index('href="marka.css"')
    assert '<h1 class="marka"><img src="logo-mark.svg"' in html and "notar<strong>ai</strong>" in html
    assert '<meta name="theme-color" content="#071d49">' in html and "font-src 'self';" in html
    assert "#0d6b57" not in html
    marka = (katalog / "marka.css").read_text(encoding="utf-8")
    assert "--accent: #234bd2" in marka and "../fonts/montserrat-latin-ext-wght-normal.woff2" in marka
    assert (STRONA / "fonts" / "montserrat-latin-ext-wght-normal.woff2").is_file()
    manifest = json.loads((katalog / "pocket.webmanifest").read_text(encoding="utf-8"))
    assert (manifest["name"], manifest["theme_color"]) == ("NotarAI", "#071d49")
    zasoby = (ANDROID / "app" / "src" / "main" / "res" / "values" / "zasoby.xml").read_text(encoding="utf-8")
    assert '<string name="nazwa" translatable="false">NotarAI</string>' in zasoby
    assert '<color name="granat">#071D49</color>' in zasoby and "0D6B57" not in zasoby
    znak = (ANDROID / "app" / "src" / "main" / "res" / "drawable" / "ikona_znak.xml").read_text(encoding="utf-8")
    assert "M16 16h104c0 13-9 23-23 23H29c-10 0-17 6-21 16C0 39 7 16 16 16Z" in znak      # geometria sygnetu


def test_konto_kancelarii_dziala_w_aplikacji_bez_komputera():
    """Druga droga na ekranie startowym: konto kancelarii (app.notarai.pl). Aplikacja ufa tej domenie,
    a domena potwierdza aplikację tym samym plikiem co notarai.pl, więc nie ma paska adresu."""
    from fastapi.testclient import TestClient

    import app as aplikacja
    import autoryzacja

    kod = (STRONA / "pocket" / "powitanie.js").read_text(encoding="utf-8")
    assert 'const KONTO = "https://app.notarai.pl/";' in kod and "window.location.assign(KONTO)" in kod
    assert 'parametry.has("wybor")' in kod and "window.notaraiNowaPaczka" in kod   # powrót do wyboru, aktualizacja
    assert "window.notaraiNowaPaczka = (() => {" in (STRONA / "pocket" / "aktualizacja.js").read_text(encoding="utf-8")

    zasoby = (ANDROID / "app" / "src" / "main" / "res" / "values" / "zasoby.xml").read_text(encoding="utf-8")
    assert "<item>https://app.notarai.pl</item>" in zasoby
    assert zasoby.count("delegate_permission/common.handle_all_urls") == 2
    manifest = (ANDROID / "app" / "src" / "main" / "AndroidManifest.xml").read_text(encoding="utf-8")
    assert "android.support.customtabs.trusted.ADDITIONAL_TRUSTED_ORIGINS" in manifest
    skroty = ET.parse(ANDROID / "app" / "src" / "main" / "res" / "xml" / "skroty.xml").getroot()
    adresy = {i.get(NS + "data") for i in skroty.iter("intent")}
    assert adresy == {"https://app.notarai.pl/", "https://notarai.pl/pocket/?wybor=1"}
    assert {i.get(NS + "targetPackage") for i in skroty.iter("intent")} == {PAKIET}

    assert "/.well-known/assetlinks.json" in autoryzacja._OTWARTE         # publiczne, bez logowania
    odpowiedz = TestClient(aplikacja.app).get("/.well-known/assetlinks.json")
    assert odpowiedz.status_code == 200 and odpowiedz.headers["content-type"].startswith("application/json")
    assert odpowiedz.json() == json.loads((STRONA / ".well-known" / "assetlinks.json").read_text(encoding="utf-8"))


def test_iphone_instaluje_z_safari_a_publikacja_sprawdza_paczke():
    html = (STRONA / "pocket" / "index.html").read_text(encoding="utf-8")
    assert '<link rel="apple-touch-icon" href="pocket-icon-180.png">' in html
    dane = (STRONA / "pocket" / "pocket-icon-180.png").read_bytes()
    assert struct.unpack(">II", dane[16:24]) == (180, 180)
    pobieranie = (STRONA / "do-pobrania" / "index.html").read_text(encoding="utf-8")
    assert "NotarAI na iPhonie" in pobieranie and "Do ekranu początkowego" in pobieranie
    publikacja = (ROOT / ".github" / "workflows" / "strona.yml").read_text(encoding="utf-8")
    for plik in ("pocket/NotarAI-Pocket.apk", "pocket/wersja.json", ".well-known/assetlinks.json"):
        assert plik in publikacja, plik
