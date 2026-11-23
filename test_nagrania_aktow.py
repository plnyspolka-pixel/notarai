"""Nagrania odczytania aktu: fragmenty -> jeden plik w magazynie kancelarii.
Dane zmyślone (Sobczak/Pawlak), S3 zastąpione atrapą, bez sieci."""
import hashlib
import logging
import os
import shutil

import pytest
from fastapi.testclient import TestClient

import app as aplikacja
import config
import magazyn
import nagrania_aktow
import stanowiska
from test_magazyn import AtrapaS3

TYTUL = "Sprzedaż lokalu Sobczak - Pawlak"


class AtrapaS3Pliki(AtrapaS3):
    """Aplikacja wysyła pliki audio jako strumień, nie jako bajty."""

    def put_object(self, Bucket, Key, Body, **kw):
        return super().put_object(Bucket, Key, Body.read() if hasattr(Body, "read") else Body, **kw)


@pytest.fixture
def klient(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DANE", tmp_path)
    monkeypatch.setattr(config, "SPRAWY", tmp_path / "sprawy", raising=False)
    (tmp_path / "sprawy").mkdir(exist_ok=True)
    # Bez ffmpeg: sklejone fragmenty zostają bajt w bajt (łatwo sprawdzić skrót).
    monkeypatch.setattr(nagrania_aktow.shutil, "which", lambda _n: None)
    return TestClient(aplikacja.app)


@pytest.fixture
def s3(klient, monkeypatch):
    atrapa = AtrapaS3Pliki()
    monkeypatch.setattr(magazyn, "TRYB", "s3")
    monkeypatch.setattr(magazyn, "BUCKET", "testowy-bucket")
    monkeypatch.setattr(magazyn, "_s3", atrapa)
    return atrapa


def _nagraj(klient, czesci=(b"A" * 100, b"B" * 50, b"C" * 10), **pola):
    odp = klient.post("/api/nagrania", json={"tytul": TYTUL, "sygnatura": "1234/2026", "zgoda": True,
                                              "typ": "audio/webm;codecs=opus", **pola})
    assert odp.status_code == 200, odp.text
    id_n = odp.json()["id"]
    for nr, dane in enumerate(czesci):
        assert klient.put(f"/api/nagrania/{id_n}/czesci/{nr}", content=dane).status_code == 200
    return id_n


def test_bez_zgody_nie_zaczyna(klient):
    odp = klient.post("/api/nagrania", json={"tytul": TYTUL, "zgoda": False})
    assert odp.status_code == 400
    assert "zgodziły" in odp.json()["detail"]
    assert klient.get("/api/nagrania").json()["nagrania"] == []


def test_nieznany_format_odrzucony(klient):
    assert klient.post("/api/nagrania", json={"zgoda": True, "typ": "video/x-matroska"}).status_code == 415


def test_fragmenty_sklejone_w_jeden_plik(klient):
    czesci = (b"naglowek-webm" + b"1" * 500, b"2" * 400, b"3" * 30)
    id_n = _nagraj(klient, czesci)
    odp = klient.post(f"/api/nagrania/{id_n}/koniec", json={"czesci": 3, "czas_s": 45.04})
    assert odp.status_code == 200, odp.text
    wpis = odp.json()
    calosc = b"".join(czesci)
    assert wpis["stan"] == "gotowe"
    assert wpis["rozmiar"] == len(calosc)
    assert wpis["sha256"] == hashlib.sha256(calosc).hexdigest()
    assert wpis["czas_s"] == 45.0
    assert wpis["zgoda"]["potwierdzil"]
    # Fragmenty skasowane, został jeden plik.
    katalog = magazyn.katalog_kancelarii() / "nagrania" / id_n
    assert sorted(p.name for p in katalog.iterdir()) == ["nagranie.webm"]

    plik = klient.get(f"/api/nagrania/{id_n}/plik")
    assert plik.status_code == 200
    assert plik.content == calosc
    assert plik.headers["content-type"].startswith("audio/webm")
    # Tytuł bywa nazwiskiem: nie trafia do nazwy pobieranego pliku.
    assert "Sobczak" not in plik.headers["content-disposition"]

    lista = klient.get("/api/nagrania").json()
    assert lista["przechowywanie"] == "chmura"
    assert [n["tytul"] for n in lista["nagrania"]] == [TYTUL]


def test_ponowione_wyslanie_fragmentu_nadpisuje(klient):
    id_n = _nagraj(klient, (b"x" * 10, b"y" * 10))
    assert klient.put(f"/api/nagrania/{id_n}/czesci/1", content=b"y" * 10).status_code == 200
    wpis = klient.post(f"/api/nagrania/{id_n}/koniec", json={"czesci": 2}).json()
    assert wpis["rozmiar"] == 20


def test_brakujace_fragmenty_zwraca_liste(klient):
    id_n = _nagraj(klient, (b"x" * 10,))
    odp = klient.post(f"/api/nagrania/{id_n}/koniec", json={"czesci": 3})
    assert odp.status_code == 409
    assert odp.json()["detail"]["brakujace"] == [1, 2]
    # Przeglądarka dosyła z pamięci telefonu i kończy jeszcze raz.
    for nr in (1, 2):
        klient.put(f"/api/nagrania/{id_n}/czesci/{nr}", content=b"z")
    assert klient.post(f"/api/nagrania/{id_n}/koniec", json={"czesci": 3}).json()["rozmiar"] == 12


def test_zakonczone_nie_przyjmuje_fragmentow(klient):
    id_n = _nagraj(klient, (b"x",))
    klient.post(f"/api/nagrania/{id_n}/koniec", json={"czesci": 1})
    assert klient.put(f"/api/nagrania/{id_n}/czesci/1", content=b"x").status_code == 409
    # Ponowne zakończenie (np. po zerwanej odpowiedzi) zwraca to samo.
    assert klient.post(f"/api/nagrania/{id_n}/koniec", json={"czesci": 1}).json()["stan"] == "gotowe"


def test_niepoprawne_identyfikatory(klient):
    assert klient.put("/api/nagrania/..%2F..%2Fx/czesci/0", content=b"x").status_code in (400, 404)
    assert klient.get("/api/nagrania/ABC/plik").status_code == 400
    assert klient.put("/api/nagrania/0123456789abcdef/czesci/0", content=b"x").status_code == 404
    id_n = _nagraj(klient, ())
    assert klient.put(f"/api/nagrania/{id_n}/czesci/-1", content=b"x").status_code == 400
    assert klient.put(f"/api/nagrania/{id_n}/czesci/0", content=b"").status_code == 400


def test_usuniecie(klient):
    id_n = _nagraj(klient)
    klient.post(f"/api/nagrania/{id_n}/koniec", json={"czesci": 3})
    assert klient.delete(f"/api/nagrania/{id_n}").status_code == 200
    assert klient.get("/api/nagrania").json()["nagrania"] == []
    assert not (magazyn.katalog_kancelarii() / "nagrania" / id_n).exists()


def test_s3_fragmenty_i_plik_w_buckecie_kancelarii(klient, s3):
    id_n = _nagraj(klient)
    prefiks = f"kancelarie/lokalna/nagrania/{id_n}/"
    assert sorted(k for k in s3.obiekty if k.startswith(prefiks)) == [
        prefiks + "czesci/00000", prefiks + "czesci/00001", prefiks + "czesci/00002"]
    # Inna kopia aplikacji (pusty dysk) kończy nagranie: fragmenty schodzą z S3.
    shutil.rmtree(magazyn.katalog_kancelarii() / "nagrania" / id_n)
    wpis = klient.post(f"/api/nagrania/{id_n}/koniec", json={"czesci": 3}).json()
    assert wpis["stan"] == "gotowe"
    assert sorted(k for k in s3.obiekty if k.startswith(prefiks)) == [prefiks + "nagranie.webm"]
    assert s3.szyfrowanie[prefiks + "nagranie.webm"] in ("AES256", "aws:kms")
    assert s3.obiekty["kancelarie/lokalna/nagrania.json"]

    shutil.rmtree(magazyn.katalog_kancelarii() / "nagrania" / id_n)
    assert klient.get(f"/api/nagrania/{id_n}/plik").content == b"A" * 100 + b"B" * 50 + b"C" * 10

    klient.delete(f"/api/nagrania/{id_n}")
    assert not [k for k in s3.obiekty if k.startswith(prefiks)]


def test_kancelaria_u_klienta_nic_nie_zapisuje(klient, monkeypatch):
    znacznik = magazyn.przechowywanie_var.set("u-klienta")
    try:
        assert klient.get("/api/nagrania").json() == {"przechowywanie": "u-klienta", "nagrania": []}
        assert klient.post("/api/nagrania", json={"zgoda": True}).status_code == 409
    finally:
        magazyn.przechowywanie_var.reset(znacznik)
    with pytest.raises(RuntimeError):
        znacznik = magazyn.przechowywanie_var.set("u-klienta")
        try:
            magazyn.utrwal_plik("nagrania/x/nagranie.webm")
        finally:
            magazyn.przechowywanie_var.reset(znacznik)


def test_logi_bez_tytulu(klient, caplog):
    with caplog.at_level(logging.DEBUG):
        id_n = _nagraj(klient)
        klient.post(f"/api/nagrania/{id_n}/koniec", json={"czesci": 3})
    assert "Sobczak" not in caplog.text and "1234/2026" not in caplog.text


def test_usuwa_tylko_ten_kto_usuwa_pliki_spraw():
    assert stanowiska.wymagane("DELETE", "/api/nagrania/0123456789abcdef") == "usun_plik"
    assert "usun_plik" not in stanowiska.UPRAWNIENIA["sekretariat"]
    # Nagrywać i odsłuchiwać może każdy w zespole (sekretariat też podaje telefon).
    assert stanowiska.wymagane("POST", "/api/nagrania") is None
    assert stanowiska.wymagane("GET", "/api/nagrania/0123456789abcdef/plik") is None


def test_sciezka_pliku_kancelarii_bez_wyjscia_poza_katalog():
    for zla in ("../x", "/etc/passwd", "a//b", "a/./b", "a\\b", ""):
        with pytest.raises(ValueError):
            magazyn.pobierz_plik(zla)


def test_strona_jawna(klient):
    odp = klient.get("/nagrania")
    assert odp.status_code == 200
    assert "Nagranie aktu" in odp.text and "zgodziły" in odp.text


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="brak ffmpeg")
def test_ffmpeg_porzadkuje_prawdziwe_nagranie(tmp_path):
    """Prawdziwy Opus w WebM: po przepisaniu kontenera plik nadal jest dźwiękiem."""
    import subprocess
    zrodlo = tmp_path / "nagranie.webm"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
                    "-ac", "1", "-c:a", "libopus", "-b:a", "24k", str(zrodlo)], check=True)
    assert nagrania_aktow._uporzadkuj(zrodlo, "audio/webm")
    sonda = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                            str(zrodlo)], capture_output=True, text=True, check=True)
    assert 2.5 < float(sonda.stdout) < 3.5


def test_ui_nagrywa_wysyla_i_odtwarza(tmp_path, monkeypatch):
    """Prawdziwy Chromium z udawanym mikrofonem: nagranie w kilku fragmentach
    idzie na serwer, skleja się i daje odtworzyć."""
    playwright = pytest.importorskip("playwright.sync_api")
    from test_kalendarz_ui import serwer as _serwer
    gen = _serwer.__wrapped__(tmp_path, monkeypatch)
    adres = next(gen)
    try:
        with playwright.sync_playwright() as p:
            argumenty = ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"]
            try:
                przegladarka = p.chromium.launch(headless=True, args=argumenty)
            except Exception as blad:  # noqa: BLE001
                sciezka = os.getenv("PIECZAPP_CHROMIUM", "")
                if not sciezka:
                    pytest.skip(f"Brak Chromium dla Playwright: {blad}")
                przegladarka = p.chromium.launch(headless=True, args=argumenty, executable_path=sciezka)
            kontekst = przegladarka.new_context(permissions=["microphone"])
            strona = kontekst.new_page()
            bledy = []
            strona.on("pageerror", lambda b: bledy.append(str(b)))
            strona.on("dialog", lambda d: d.accept())
            strona.add_init_script("window.__fragmentMs = 700;")
            strona.goto(adres + "/nagrania")
            assert strona.is_disabled("#btn-nagraj")          # bez zgody nie ruszy
            strona.fill("#tytul", TYTUL)
            strona.check("#zgoda")
            strona.click("#btn-nagraj")
            strona.wait_for_function("document.body.classList.contains('trwa')")
            strona.wait_for_timeout(3000)
            assert strona.text_content("#zegar") != "0:00:00"
            strona.click("#btn-nagraj")
            strona.wait_for_selector("#stan.ok", timeout=20000)
            assert "Zapisane na serwerze" in strona.text_content("#stan")

            spis = magazyn.wczytaj_plik_kancelarii("nagrania", [])
            assert len(spis) == 1 and spis[0]["stan"] == "gotowe"
            assert spis[0]["rozmiar"] > 1000 and spis[0]["czas_s"] >= 2
            assert strona.is_hidden("#karta-lokalne")      # pamięć telefonu wyczyszczona
            assert not strona.is_checked("#zgoda") and strona.is_disabled("#btn-nagraj")  # nowy akt = nowa zgoda

            strona.click("#lista .wpis button:has-text('Odsłuchaj')")
            strona.wait_for_selector("#lista audio")
            strona.wait_for_function(
                "(() => { const a = document.querySelector('#lista audio'); return a && a.readyState >= 1; })()",
                timeout=10000)

            strona.click("#lista .wpis button:has-text('Usuń')")
            strona.wait_for_selector("#lista .pusto")
            assert magazyn.wczytaj_plik_kancelarii("nagrania", []) == []
            assert bledy == []
            przegladarka.close()
    finally:
        next(gen, None)
