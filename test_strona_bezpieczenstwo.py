"""Podstrona notarai.pl/bezpieczenstwo/: pytanie, skan bez instalacji, odpowiedź „a u nas są”.

Statyczne sprawdzenia HTML i skryptów, bez sieci.
"""
import importlib.util
import re
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KATALOG = ROOT / "strona" / "bezpieczenstwo"
HTML = (KATALOG / "index.html").read_text(encoding="utf-8")
SKAN_JS = (KATALOG / "skan.js").read_text(encoding="utf-8")
KOMPUTER_JS = (KATALOG / "komputer.js").read_text(encoding="utf-8")
GLOWNA = (ROOT / "strona" / "index.html").read_text(encoding="utf-8")


def test_jeden_h1_i_trzy_czesci_w_kolejnosci():
    assert len(re.findall(r"<h1\b", HTML)) == 1
    assert '<h1 id="tytul">Czy Twoje dane są bezpieczne?</h1>' in HTML
    kolejnosc = [HTML.index(f'id="{i}"') for i in ("skan-strona", "skan-komputer", "glebiej", "u-nas")]
    assert kolejnosc == sorted(kolejnosc)


def test_pliki_strony_istnieja_i_sa_podpiete():
    for plik in ("bezpieczenstwo.css", "bezpieczenstwo.js", "komputer.css", "komputer.js", "skan.js"):
        assert (KATALOG / plik).is_file()
        assert f'"{plik}"' in HTML
    for wspolny in ("../pieczecie.css", "../pieczecie.js", "../style.css"):
        assert f'"{wspolny}"' in HTML


def test_skan_bez_instalacji_dwie_czesci():
    assert 'id="skaner"' in HTML and 'id="adres"' in HTML          # strona i poczta
    assert 'id="bz-start"' in HTML and 'id="bz-haslo-input"' in HTML  # ten komputer
    # haslo nie opuszcza przegladarki: wysylamy tylko 5 znakow skrotu
    assert "slice(0, 5)" in SKAN_JS or "substring(0, 5)" in SKAN_JS or "slice(0,5)" in SKAN_JS


def test_glebiej_bez_falszywego_linku_do_sklepu():
    """Rozszerzenia nie ma jeszcze w sklepach (NA-14): żadnego linku udającego instalację."""
    blok = HTML.split('id="glebiej-sklep"', 1)[1].split("</div>", 1)[0]
    assert "Wkrótce" in blok
    assert "chromewebstore.google.com" not in HTML and "microsoftedge.microsoft.com" not in HTML


def test_bez_obietnic_funkcji_ktorych_nie_ma():
    for zdanie in ("szyfrujemy dyski", "program do głębokiego skanu", "Żaden człowiek", "Włącz ochronę danych"):
        assert zdanie not in HTML, zdanie
        assert zdanie not in KOMPUTER_JS, zdanie


def test_bez_odczytu_karty_graficznej():
    """Odczyt modelu GPU to odcisk palca urządzenia - nie na stronie o prywatności."""
    for plik in (SKAN_JS, KOMPUTER_JS):
        assert "WEBGL_debug_renderer_info" not in plik
        assert "czytajGPU" not in plik


def test_bez_recznie_wpisanych_swiezych_cve():
    """Świeże luki wyłącznie z katalogu CISA (backend); w skrypcie tylko znane klasyki."""
    assert re.findall(r"CVE-\d{4}-\d+", SKAN_JS) == ["CVE-2017-0144", "CVE-2017-0144", "CVE-2019-0708",
                                                     "CVE-2019-0708", "CVE-2021-34527", "CVE-2021-34527"]


def test_a_u_nas_pieczecie_i_tarcze():
    u_nas = HTML.split('id="u-nas"', 1)[1]
    assert "A u nas są" in u_nas
    assert "Certyfikowany dostawca infrastruktury" in u_nas
    assert u_nas.count('class="nx-pieczec nx') == 10
    assert u_nas.count('class="nx-tarcza"') == 6
    assert "To nie są certyfikaty." in u_nas
    # uczciwie o tym, czego jeszcze nie ma
    assert "dwuskładnikowe jest w przygotowaniu" in u_nas


def test_generator_obsluguje_podstrone_bez_zmian():
    spec = importlib.util.spec_from_file_location("pieczecie_strony", ROOT / "scripts" / "pieczecie_strony.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    with tempfile.TemporaryDirectory() as katalog:
        kopia = Path(katalog) / "index.html"
        kopia.write_text(HTML, encoding="utf-8")
        modul.main(str(kopia))
        assert kopia.read_text(encoding="utf-8") == HTML


def test_strona_glowna_prowadzi_do_skanera():
    assert 'href="bezpieczenstwo/">Sprawdź swoją kancelarię</a>' in GLOWNA
    assert 'href="bezpieczenstwo/">Bezpieczeństwo kancelarii</a>' in GLOWNA


def test_analityka_bez_nagran_na_skanerze():
    analityka = (ROOT / "strona" / "analityka.js").read_text(encoding="utf-8")
    wzor = re.search(r"var BEZ_NAGRAN = /(.*)/;", analityka).group(1)
    assert re.search(wzor.replace("\\/", "/"), "/bezpieczenstwo/")
