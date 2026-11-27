"""NotarAI Pocket na Androida: powłoka TWA w `android/pocket/` i jej powiązanie ze stroną.

Aplikacja nie ma własnego kodu: otwiera https://notarai.pl/pocket/ w Chrome telefonu. Pasek adresu
znika tylko wtedy, gdy strona i aplikacja wskazują na siebie nawzajem, więc pilnujemy obu połówek.
Statyczne sprawdzenia, bez sieci i bez Android SDK.
"""
import json
import re
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
    assert meta["android.support.customtabs.trusted.DEFAULT_URL"] == "https://notarai.pl/pocket/"
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


def test_klucz_podpisu_nie_lezy_w_repozytorium():
    sledzone = subprocess.run(["git", "ls-files", "android"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    assert not [p for p in sledzone if p.endswith((".jks", ".keystore", ".p12", ".apk", ".aab"))]
    gradle = (ANDROID / "app" / "build.gradle").read_text(encoding="utf-8")
    assert 'System.getenv("NOTARAI_POCKET_KEYSTORE_HASLO")' in gradle
    assert re.search(r'(storePassword|keyPassword)\s+"', gradle) is None
