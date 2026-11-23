"""Stenogram odczytania aktu: nagranie -> zanonimizowany tekst przy sprawie.
Dane zmyślone (Sobczak/Pawlak), S3 i Transcribe zastąpione atrapami, bez sieci."""
import json
import logging
import os

import pytest
from fastapi.testclient import TestClient

import anonimizacja
import app as aplikacja
import config
import magazyn
import stanowiska
import stenogramy
import transkrypcja
from test_magazyn import AtrapaS3

PESEL = "80010112345"
SUROWE = [
    {"start": 0.0, "mowca": "", "tekst": "Stawiający Jan Sobczak, PESEL 80 01 01 123 45, zamieszkały przy ulicy Lipowej 7 m. 3."},
    {"start": 12.5, "mowca": "", "tekst": "Kupująca pani Anna Pawlak, telefon 600 100 200, pan Sobczaka zna od lat."},
    {"start": 30.0, "mowca": "", "tekst": "Cena wynosi 450 000 zł, nowa umowa wchodzi w życie dziś."},
]
# Co wskazałby model (atrapa): fragmenty dokładnie tak, jak w tekście.
WSKAZANE = ["Jan Sobczak", "Anna Pawlak", "Lipowej 7 m. 3"]


class AtrapaS3Pliki(AtrapaS3):
    def put_object(self, Bucket, Key, Body, **kw):
        return super().put_object(Bucket, Key, Body.read() if hasattr(Body, "read") else Body, **kw)


def _sprawa(katalog, id_sprawy="spr1"):
    k = katalog / id_sprawy
    k.mkdir(parents=True)
    (k / "sprawa.json").write_text(json.dumps({"id": id_sprawy, "nazwa": "Sobczak - Pawlak",
                                               "utworzono": "2026-11-20T10:00:00"}), "utf-8")
    (k / "odczyt.json").write_text(json.dumps({"pola": [
        {"nazwa": "aaa: zbywca", "wartosc": "Jan Sobczak"},
        {"nazwa": "+ PESEL zbywcy", "wartosc": PESEL},
        {"nazwa": "bbb: nabywcy", "wartosc": "Anna Pawlak, zam. Lublin"},
        {"nazwa": "cena", "wartosc": "450 000 zł"},
    ]}), "utf-8")
    return k


@pytest.fixture
def klient(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DANE", tmp_path)
    if "SPRAWY" in vars(config):
        monkeypatch.delattr(config, "SPRAWY")
    _sprawa(tmp_path / "sprawy")
    monkeypatch.setenv("PIECZAPP_STENOGRAM_SILNIK", "whisper")
    monkeypatch.setattr(transkrypcja, "dostepna", lambda: True)
    monkeypatch.setattr(transkrypcja, "segmenty_pliku", lambda sciezka: [dict(s) for s in SUROWE])
    monkeypatch.setattr(anonimizacja, "wskaz_dane", lambda segmenty: list(WSKAZANE))
    # Przetwarzanie od razu, w tym samym wątku.
    monkeypatch.setattr(stenogramy, "_w_tle", stenogramy.przetworz)
    return TestClient(aplikacja.app)


@pytest.fixture
def s3(klient, monkeypatch):
    atrapa = AtrapaS3Pliki()
    monkeypatch.setattr(magazyn, "TRYB", "s3")
    monkeypatch.setattr(magazyn, "BUCKET", "testowy-bucket")
    monkeypatch.setattr(magazyn, "_s3", atrapa)
    return atrapa


def _nagraj(klient, czesci=(b"A" * 100, b"B" * 50, b"C" * 10), sesje=None, **pola):
    odp = klient.post("/api/stenogramy", json={"sprawa": "spr1", "sygnatura": "1234/2026", "zgoda": True,
                                               "typ": "audio/webm;codecs=opus", **pola})
    assert odp.status_code == 200, odp.text
    id_s = odp.json()["id"]
    for nr, dane in enumerate(czesci):
        assert klient.put(f"/api/stenogramy/{id_s}/czesci/{nr}", content=dane).status_code == 200
    return id_s, sesje or [{"od": 0, "do": len(czesci), "czas_s": 42.0}]


def _zakoncz(klient, id_s, sesje):
    odp = klient.post(f"/api/stenogramy/{id_s}/koniec", json={"sesje": sesje})
    assert odp.status_code == 200, odp.text
    return klient.get(f"/api/stenogramy/{id_s}").json()


# --- przebieg ------------------------------------------------------------------

def test_stenogram_przy_sprawie_bez_danych_osobowych(klient, tmp_path):
    wpis = _zakoncz(klient, *_nagraj(klient))
    assert wpis["stan"] == "gotowe", wpis
    assert wpis["plik"].startswith("zalaczniki/stenogram-")

    tekst = klient.get(f"/api/stenogramy/{wpis['id']}/tekst").text
    assert "STENOGRAM ODCZYTANIA AKTU" in tekst and "Repertorium A nr 1234/2026" in tekst
    # Początek i koniec zostają: kto zna akt, dopasuje osobę do roli.
    assert "Stawiający J*n S*****k, PESEL 80 ** ** *** 45, zamieszkały przy ulicy L*****j 7 m. 3." in tekst
    assert "Kupująca pani A**a P****k, telefon 60* *** *00, pan S******a zna od lat." in tekst
    for dana in ("Sobczak", "Pawlak", "Lipowej", "80 01 01", "600 100 200"):
        assert dana not in tekst, dana
    assert "450 000 zł" in tekst and "nowa umowa" in tekst     # treść czynności zostaje
    assert "[0:00:12]" in tekst

    # Stenogram widać w plikach sprawy.
    pliki = klient.get("/api/sprawy/spr1/pliki").json()
    assert [p["nazwa"] for p in pliki] == [wpis["plik"].split("/")[1]]
    # Nagrania nie ma: katalog roboczy usunięty.
    assert not (magazyn.katalog_kancelarii() / "stenogramy-robocze" / wpis["id"]).exists()
    # Surowy tekst nigdzie na dysku (poza danymi sprawy, które już tam były).
    for plik in tmp_path.rglob("*"):
        if plik.is_file() and plik.name not in ("odczyt.json", "sprawa.json"):
            assert b"Lipowej" not in plik.read_bytes(), plik


def test_wiele_sesji_przesuwa_czas(klient, monkeypatch):
    wywolania = []

    def segmenty(sciezka):
        wywolania.append(sciezka.name)
        return [{"start": 5.0, "mowca": "", "tekst": f"sesja {len(wywolania)}"}]
    monkeypatch.setattr(transkrypcja, "segmenty_pliku", segmenty)
    id_s, _ = _nagraj(klient, (b"a", b"b", b"c"))
    wpis = _zakoncz(klient, id_s, [{"od": 0, "do": 2, "czas_s": 3000}, {"od": 2, "do": 3, "czas_s": 60}])
    assert wywolania == ["sesja-0.webm", "sesja-1.webm"]
    tekst = klient.get(f"/api/stenogramy/{wpis['id']}/tekst").text
    assert "[0:00:05] sesja 1" in tekst and "[0:50:05] sesja 2" in tekst
    assert wpis["czas_s"] == 3060


def test_bez_zgody_nie_zaczyna(klient):
    odp = klient.post("/api/stenogramy", json={"sprawa": "spr1", "zgoda": False})
    assert odp.status_code == 400 and "zgodziły" in odp.json()["detail"]


def test_sprawa_musi_istniec(klient):
    assert klient.post("/api/stenogramy", json={"sprawa": "nieMa1", "zgoda": True}).status_code == 404
    assert klient.post("/api/stenogramy", json={"sprawa": "../x", "zgoda": True}).status_code == 400


def test_bez_silnika_503(klient, monkeypatch):
    monkeypatch.setattr(transkrypcja, "dostepna", lambda: False)
    assert klient.post("/api/stenogramy", json={"sprawa": "spr1", "zgoda": True}).status_code == 503
    assert klient.get("/api/stenogramy").json()["wlaczone"] is False


def test_transcribe_dopiero_po_rezygnacji_z_uczenia(s3, monkeypatch):
    monkeypatch.setenv("PIECZAPP_STENOGRAM_SILNIK", "")
    monkeypatch.delenv("PIECZAPP_TRANSCRIBE_OPTOUT", raising=False)
    assert stenogramy.silnik() is None
    monkeypatch.setenv("PIECZAPP_TRANSCRIBE_OPTOUT", "1")
    assert stenogramy.silnik() == "transcribe"


def test_brakujace_fragmenty_zwraca_liste(klient):
    id_s, _ = _nagraj(klient, (b"x",))
    odp = klient.post(f"/api/stenogramy/{id_s}/koniec", json={"sesje": [{"od": 0, "do": 3}]})
    assert odp.status_code == 409 and odp.json()["detail"]["brakujace"] == [1, 2]
    for nr in (1, 2):
        klient.put(f"/api/stenogramy/{id_s}/czesci/{nr}", content=b"z")
    assert _zakoncz(klient, id_s, [{"od": 0, "do": 3}])["stan"] == "gotowe"


def test_zly_podzial_na_sesje(klient):
    id_s, _ = _nagraj(klient, (b"x", b"y"))
    for sesje in ([], [{"od": 1, "do": 2}], [{"od": 0, "do": 1}, {"od": 0, "do": 2}], [{"od": 0, "do": 0}]):
        assert klient.post(f"/api/stenogramy/{id_s}/koniec", json={"sesje": sesje}).status_code == 400


def test_blad_modelu_nic_nie_zapisuje_i_daje_ponowic(klient, monkeypatch):
    def padnij(_s):
        raise RuntimeError("Bedrock nie odpowiada")
    monkeypatch.setattr(anonimizacja, "wskaz_dane", padnij)
    id_s, sesje = _nagraj(klient)
    wpis = _zakoncz(klient, id_s, sesje)
    assert wpis["stan"] == "blad" and "Spróbuj ponownie" in wpis["komunikat"]
    assert klient.get("/api/sprawy/spr1/pliki").json() == []
    # Audio czeka na ponowienie.
    assert (magazyn.katalog_kancelarii() / "stenogramy-robocze" / id_s / "sesja-0.webm").exists()

    monkeypatch.setattr(anonimizacja, "wskaz_dane", lambda s: list(WSKAZANE))
    assert klient.post(f"/api/stenogramy/{id_s}/ponow").status_code == 200
    assert klient.get(f"/api/stenogramy/{id_s}").json()["stan"] == "gotowe"


def test_usuniecie_kasuje_tez_plik_sprawy(klient):
    wpis = _zakoncz(klient, *_nagraj(klient))
    assert klient.delete(f"/api/stenogramy/{wpis['id']}").status_code == 200
    assert klient.get("/api/stenogramy").json()["stenogramy"] == []
    assert klient.get("/api/sprawy/spr1/pliki").json() == []


def test_lista_filtruje_po_sprawie(klient, tmp_path):
    _sprawa(tmp_path / "sprawy", "spr2")
    _zakoncz(klient, *_nagraj(klient))
    assert len(klient.get("/api/stenogramy?sprawa=spr1").json()["stenogramy"]) == 1
    assert klient.get("/api/stenogramy?sprawa=spr2").json()["stenogramy"] == []


def test_porzucone_nagranie_znika_po_dwoch_dobach(klient):
    id_s, _ = _nagraj(klient)

    def postarz(spis):
        spis[0]["utworzono"] = "2020-01-01T00:00:00+00:00"
    magazyn.zmien_plik_kancelarii("stenogramy", postarz, [])
    assert klient.get("/api/stenogramy").json()["stenogramy"] == []
    assert not (magazyn.katalog_kancelarii() / "stenogramy-robocze" / id_s).exists()


def test_kancelaria_u_klienta(klient):
    znacznik = magazyn.przechowywanie_var.set("u-klienta")
    try:
        assert klient.get("/api/stenogramy").json() == {"wlaczone": False, "stenogramy": []}
        assert klient.post("/api/stenogramy", json={"sprawa": "spr1", "zgoda": True}).status_code == 409
    finally:
        magazyn.przechowywanie_var.reset(znacznik)


def test_logi_bez_danych(klient, caplog):
    with caplog.at_level(logging.DEBUG):
        _zakoncz(klient, *_nagraj(klient))
    for dana in ("Sobczak", "Pawlak", "1234/2026", "80 01 01"):
        assert dana not in caplog.text


def test_usuwa_tylko_ten_kto_usuwa_pliki_spraw():
    assert stanowiska.wymagane("DELETE", "/api/stenogramy/0123456789abcdef") == "usun_plik"
    assert "usun_plik" not in stanowiska.UPRAWNIENIA["sekretariat"]
    assert stanowiska.wymagane("POST", "/api/stenogramy") is None


def test_strona_jawna(klient):
    odp = klient.get("/stenogramy")
    assert odp.status_code == 200 and "Stenogram aktu" in odp.text and "zgodziły" in odp.text


# --- AWS Transcribe (atrapa, parametry sprawdzane przez botocore) ---------------

def _wynik_transcribe():
    def slowo(tekst, start, mowca):
        return {"type": "pronunciation", "start_time": str(start), "speaker_label": mowca,
                "alternatives": [{"content": tekst}]}
    return {"results": {"transcripts": [{"transcript": "..."}], "items": [
        slowo("Stawiający", 0.5, "spk_0"), slowo("Jan", 1.0, "spk_0"), slowo("Sobczak", 1.3, "spk_0"),
        {"type": "punctuation", "alternatives": [{"content": ","}]},
        slowo("PESEL", 2.0, "spk_0"), slowo("80010112345", 2.5, "spk_0"),
        {"type": "punctuation", "alternatives": [{"content": "."}]},
        slowo("Potwierdzam", 4.0, "spk_1"),
        {"type": "punctuation", "alternatives": [{"content": "."}]},
    ]}}


class AtrapaTranscribe:
    def __init__(self, s3, nieudane_z_mowcami=False):
        self.s3, self.zadania, self.usuniete = s3, {}, []
        self.nieudane_z_mowcami = nieudane_z_mowcami
        import boto3
        self._api = boto3.client("transcribe", region_name="eu-central-1").meta.service_model

    def start_transcription_job(self, **kw):
        from botocore.validate import validate_parameters
        validate_parameters(kw, self._api.operation_model("StartTranscriptionJob").input_shape)
        assert kw["Media"]["MediaFileUri"][len("s3://testowy-bucket/"):] in self.s3.obiekty
        if self.nieudane_z_mowcami and "Settings" in kw:
            self.zadania[kw["TranscriptionJobName"]] = {"TranscriptionJobStatus": "FAILED", "FailureReason": "x"}
            return {}
        self.s3.obiekty[kw["OutputKey"]] = json.dumps(_wynik_transcribe()).encode()
        self.zadania[kw["TranscriptionJobName"]] = {"TranscriptionJobStatus": "COMPLETED"}
        return {}

    def get_transcription_job(self, TranscriptionJobName):
        if TranscriptionJobName not in self.zadania:
            blad = Exception("nie ma")
            blad.response = {"Error": {"Code": "BadRequestException"}}
            raise blad
        return {"TranscriptionJob": self.zadania[TranscriptionJobName]}

    def delete_transcription_job(self, TranscriptionJobName):
        self.usuniete.append(TranscriptionJobName)


@pytest.mark.parametrize("nieudane_z_mowcami", [False, True])
def test_transcribe_caly_przebieg_i_sprzatanie(klient, s3, monkeypatch, nieudane_z_mowcami):
    monkeypatch.setenv("PIECZAPP_STENOGRAM_SILNIK", "transcribe")
    monkeypatch.setenv("PIECZAPP_TRANSCRIBE_OPTOUT", "1")
    atrapa = AtrapaTranscribe(s3, nieudane_z_mowcami)
    monkeypatch.setattr(stenogramy, "_transcribe", atrapa)
    monkeypatch.setattr(anonimizacja, "wskaz_dane", lambda s: ["Jan Sobczak"])
    id_s, sesje = _nagraj(klient)
    wpis = _zakoncz(klient, id_s, sesje)
    assert wpis["stan"] == "gotowe", wpis

    tekst = klient.get(f"/api/stenogramy/{id_s}/tekst").text
    assert "Mówca 1: Stawiający J*n S*****k, PESEL 80*******45." in tekst
    assert "Mówca 2: Potwierdzam." in tekst
    # Audio i surowy wynik Transcribe skasowane, zadania usunięte; stenogram w S3 przy sprawie.
    assert not [k for k in s3.obiekty if "stenogramy-robocze" in k]
    assert set(atrapa.usuniete) == set(atrapa.zadania)
    assert [k for k in s3.obiekty if k.startswith("kancelarie/lokalna/sprawy/spr1/zalaczniki/stenogram-")]


def test_wynik_transcribe_bez_mowcow():
    assert stenogramy.segmenty_transcribe({"results": {"transcripts": [{"transcript": "Ala ma kota."}]}}) == [
        {"start": 0.0, "mowca": "", "tekst": "Ala ma kota."}]


# --- anonimizacja ----------------------------------------------------------------

def test_dane_ze_sprawy_w_odmianie(tmp_path):
    k = _sprawa(tmp_path)
    znane = anonimizacja.znane_z_sprawy(k)
    assert {"Sobczak", "Pawlak", "Lublin", PESEL} <= set(znane)
    assert "Kancelaria" not in znane
    wynik = anonimizacja.anonimizuj([{"start": 0, "mowca": "", "tekst":
                                      "Pana Sobczaka i panią Pawlakową, nowa umowa, numer 8001 0112 345."}],
                                    znane, z_modelem=False)[0]["tekst"]
    assert wynik == "Pana S******a i panią P*******ą, nowa umowa, numer 80** **** *45."


def test_wzorce_bez_modelu():
    tekst = ("PESEL 80 01 01 123 45, dowód ABC 123456, księga LU1I/00012345/6, tel. +48 600-100-200, "
             "konto 12 3456 7890 1234 5678 9012 3456, e-mail jan@example.com, ulica Lipowa 7 m. 3, 20-001")
    wynik = anonimizacja.anonimizuj([{"start": 0, "mowca": "", "tekst": tekst}], [], z_modelem=False)[0]["tekst"]
    assert wynik == ("PESEL 80 ** ** *** 45, dowód A*C 12**56, księga L*1I/00****45/6, tel. +48 ***-***-*00, "
                     "konto 12 **** **** **** **** **** **56, e-mail j*n@e*****e.c*m, ulica L****a 7 m. 3, 2*-**1")


def test_fragmenty_modelu_cale_slowa():
    wynik = anonimizacja._maskuj_fragmenty("Jan i Janina, Jan.", ["Jan"])
    assert wynik == "J*n i Janina, J*n."


def test_kwoty_i_tresc_zostaja():
    tekst = "Cena 450 000 000 zł, na ulicy w dniu dzisiejszym, nowa umowa, Rep. A nr 1234/2026."
    assert anonimizacja.anonimizuj([{"start": 0, "mowca": "", "tekst": tekst}], [], z_modelem=False)[0]["tekst"] == tekst


def test_maska_krotkich():
    assert anonimizacja.zamaskuj("Jo") == "J*"
    assert anonimizacja.zamaskuj("ul. 7") == "u*. 7"
    assert anonimizacja.zamaskuj("123") == "1*3"


def test_model_stenogramu_tylko_eu():
    with pytest.raises(RuntimeError):
        anonimizacja._model_z_env("anthropic.claude-sonnet-4-6")


def test_ui_nagrywa_w_sesjach_i_pokazuje_stenogram(klient, tmp_path, monkeypatch):
    """Prawdziwy Chromium z udawanym mikrofonem: dwie sesje, wysyłka, stenogram."""
    playwright = pytest.importorskip("playwright.sync_api")
    monkeypatch.setattr(stenogramy, "_w_tle", stenogramy.przetworz)
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
            strona = przegladarka.new_context(permissions=["microphone"]).new_page()
            bledy = []
            strona.on("pageerror", lambda b: bledy.append(str(b)))
            strona.on("dialog", lambda d: d.accept())
            strona.add_init_script("window.__fragmentMs = 500; window.__sesjaMs = 1800; window.__odswiezMs = 300;")
            strona.goto(adres + "/stenogramy")
            strona.wait_for_selector("#sprawa option[value='spr1']", state="attached")
            strona.check("#zgoda")
            assert strona.is_disabled("#btn-nagraj")          # bez sprawy nie ruszy
            strona.select_option("#sprawa", "spr1")
            strona.click("#btn-nagraj")
            strona.wait_for_function("document.body.classList.contains('trwa')")
            strona.wait_for_timeout(4000)                      # > 2 sesje po 1,8 s
            strona.click("#btn-nagraj")
            strona.wait_for_selector("#stan.ok", timeout=20000)
            assert not strona.is_checked("#zgoda")             # nowy akt = nowa zgoda

            spis = magazyn.wczytaj_plik_kancelarii("stenogramy", [])
            assert len(spis) == 1 and len(spis[0]["sesje"]) >= 2
            strona.wait_for_selector("#lista button:has-text('Pokaż')", timeout=10000)
            strona.click("#lista button:has-text('Pokaż')")
            strona.wait_for_selector("#lista .tekst")
            tekst = strona.text_content("#lista .tekst")
            assert "J*n S*****k" in tekst and "Sobczak" not in tekst
            assert strona.is_hidden("#karta-lokalne")
            assert bledy == []
            przegladarka.close()
    finally:
        next(gen, None)
