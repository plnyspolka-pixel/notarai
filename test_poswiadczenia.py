"""Poswiadczenie kopii -> opis do repertorium A. Model zastapiony atrapa,
dane zmyslone (Sobczak/Pawlak)."""
import io
import os
import json
import logging
from datetime import date
from unittest.mock import patch

import fitz
import pytest
from fastapi.testclient import TestClient
from PIL import Image

import app as aplikacja
import poswiadczenia
import prompty
from test_kalendarz_ui import serwer  # noqa: F401

FAKTURA = {
    "strona_od": 1, "strona_do": 2, "nazwa": "faktura VAT", "numer": "FV/1/2026",
    "data": "2026-11-05", "data_slownie": "5 listopada 2026 r.",
    "wystawca": "Sobczak Transport sp. z o.o. w Poznaniu", "dotyczy": "sprzedaży usług transportowych",
    "przedmiot_dopelniacz": "faktury VAT nr FV/1/2026 z dnia 5 listopada 2026 r., wystawionej przez "
                            "Sobczak Transport sp. z o.o. w Poznaniu, dotyczącej sprzedaży usług transportowych.",
    "postac": "oryginał", "jezyk": "polski", "cechy": ["odręczny dopisek na stronie 2"], "niepewne": [],
}
UMOWA = {"strona_od": 3, "strona_do": 3, "nazwa": "umowa najmu", "numer": None, "data": "null",
         "data_slownie": None, "przedmiot_dopelniacz": "umowy najmu lokalu zawartej przez Tomasza Pawlaka"}


def jpg() -> bytes:
    bufor = io.BytesIO()
    Image.new("RGB", (400, 560), "white").save(bufor, format="JPEG")
    return bufor.getvalue()


def pdf(stron: int) -> bytes:
    dokument = fitz.open()
    for _ in range(stron):
        dokument.new_page()
    return dokument.tobytes()


@pytest.fixture
def klient():
    return TestClient(aplikacja.app)


class TestOpis:
    def test_tresc_repertorium_z_kodu(self):
        opis = poswiadczenia.opis_repertorium(FAKTURA, "odpis", 2)
        assert opis == ("Poświadczenie zgodności odpisu z okazanym dokumentem – faktury VAT nr FV/1/2026 "
                        "z dnia 5 listopada 2026 r., wystawionej przez Sobczak Transport sp. z o.o. "
                        "w Poznaniu, dotyczącej sprzedaży usług transportowych (2 strony)")

    def test_bez_przedmiotu_sklada_z_pol(self):
        opis = poswiadczenia.opis_repertorium(
            {"nazwa": "świadectwo pracy", "numer": "12/2025", "data_slownie": "1 marca 2025 r."}, "data", 5)
        assert opis == "Poświadczenie daty okazania dokumentu – świadectwo pracy nr 12/2025 z dnia 1 marca 2025 r. (5 stron)"

    @pytest.mark.parametrize("n, tekst", [(1, "1 strona"), (3, "3 strony"), (5, "5 stron"),
                                          (12, "12 stron"), (22, "22 strony")])
    def test_odmiana_stron(self, n, tekst):
        assert poswiadczenia._strony_slownie(n) == tekst


class TestPodzialStron:
    def test_kazda_strona_w_jednym_dokumencie(self):
        wynik = poswiadczenia.zloz_wynik({"dokumenty": [UMOWA, FAKTURA]}, 4, "odpis", date(2026, 11, 8))
        zakresy = [(d["strona_od"], d["strona_do"]) for d in wynik["dokumenty"]]
        assert zakresy == [(1, 2), (3, 4)]          # posortowane, ostatni do konca skanu
        assert wynik["dokumenty"][1]["data"] == "" and wynik["dokumenty"][1]["numer"] == ""

    def test_nakladki_i_luki(self):
        odp = {"dokumenty": [{"strona_od": 2, "strona_do": 3}, {"strona_od": 3, "strona_do": 4},
                             {"strona_od": 7, "strona_do": 9}]}
        wynik = poswiadczenia.zloz_wynik(odp, 8, "odpis", date(2026, 11, 8))
        assert [(d["strona_od"], d["strona_do"]) for d in wynik["dokumenty"]] == [(1, 3), (4, 6), (7, 8)]
        assert sum(d["stron"] for d in wynik["dokumenty"]) == 8

    def test_pusta_odpowiedz_to_jeden_dokument(self):
        wynik = poswiadczenia.zloz_wynik({}, 3, "kopia", date(2026, 11, 8))
        assert len(wynik["dokumenty"]) == 1 and wynik["dokumenty"][0]["stron"] == 3
        assert wynik["dokumenty"][0]["opis"].startswith("Poświadczenie zgodności kopii")

    def test_taksa_od_stron(self):
        wynik = poswiadczenia.zloz_wynik({"dokumenty": [FAKTURA]}, 2, "odpis", date(2026, 11, 8))
        d = wynik["dokumenty"][0]
        assert d["taksa_netto"] > 0 and d["taksa_brutto"] > d["taksa_netto"]
        assert wynik["razem_brutto"] == d["taksa_brutto"]


class TestApi:
    def test_strona(self, klient):
        odp = klient.get("/poswiadczenia")
        assert odp.status_code == 200 and "/api/poswiadczenia/opis" in odp.text

    def test_zdjecia_telefonu(self, klient, caplog):
        caplog.set_level(logging.INFO)
        with patch("bedrock._rozmowa", return_value=json.dumps({"dokumenty": [FAKTURA]})) as model:
            odp = klient.post("/api/poswiadczenia/opis", data={"rodzaj": "odpis"}, files=[
                ("pliki", ("Sobczak faktura 1.jpg", jpg(), "image/jpeg")),
                ("pliki", ("Sobczak faktura 2.jpg", jpg(), "image/jpeg"))])
        assert odp.status_code == 200, odp.text
        wynik = odp.json()
        assert wynik["stron"] == 2 and len(wynik["dokumenty"]) == 1
        assert wynik["dokumenty"][0]["opis"].endswith("(2 strony)")
        assert wynik["dokumenty"][0]["cechy"] == ["odręczny dopisek na stronie 2"]
        system, tresc = model.call_args.args[:2]
        assert system == prompty.POSWIADCZENIE
        assert sum(1 for t in tresc if "image" in t) == 2
        assert model.call_args.kwargs["model"].startswith("eu.")
        # do logow tylko liczby - bez nazw plikow i tresci dokumentu
        logi = caplog.text
        assert "Sobczak" not in logi and "FV/1/2026" not in logi and "stron=2" in logi

    def test_skan_z_kopiarki_kilka_dokumentow(self, klient):
        with patch("bedrock._rozmowa", return_value=json.dumps({"dokumenty": [FAKTURA, UMOWA]})):
            odp = klient.post("/api/poswiadczenia/opis", files=[("pliki", ("skan.pdf", pdf(3), "application/pdf"))])
        assert odp.status_code == 200, odp.text
        assert [d["stron"] for d in odp.json()["dokumenty"]] == [2, 1]

    def test_pliki_tymczasowe_usuwane(self, klient, tmp_path, monkeypatch):
        monkeypatch.setattr("tempfile.tempdir", str(tmp_path))
        with patch("bedrock._rozmowa", return_value="{}"):
            klient.post("/api/poswiadczenia/opis", files=[("pliki", ("a.jpg", jpg(), "image/jpeg"))])
        with patch("bedrock._rozmowa", side_effect=RuntimeError("awaria")):
            odp = klient.post("/api/poswiadczenia/opis", files=[("pliki", ("a.jpg", jpg(), "image/jpeg"))])
        assert odp.status_code == 500 and "awaria" not in odp.text
        assert list(tmp_path.iterdir()) == []

    def test_odrzuca_zly_format_i_rodzaj(self, klient):
        odp = klient.post("/api/poswiadczenia/opis", files=[("pliki", ("a.docx", b"x", "application/msword"))])
        assert odp.status_code == 415
        odp = klient.post("/api/poswiadczenia/opis", data={"rodzaj": "inne"},
                          files=[("pliki", ("a.jpg", jpg(), "image/jpeg"))])
        assert odp.status_code == 400

    def test_za_duzo_stron(self, klient):
        with patch("bedrock._rozmowa") as model:
            odp = klient.post("/api/poswiadczenia/opis", files=[("pliki", ("s.pdf", pdf(25), "application/pdf"))])
        assert odp.status_code == 422 and "podziel" in odp.json()["detail"]
        model.assert_not_called()

    def test_wymaga_logowania_w_saas(self, klient, monkeypatch):
        import autoryzacja
        monkeypatch.setattr(autoryzacja, "MULTI", True)
        assert klient.get("/poswiadczenia").status_code == 200
        odp = klient.post("/api/poswiadczenia/opis", files=[("pliki", ("a.jpg", jpg(), "image/jpeg"))])
        assert odp.status_code == 401


def test_model_musi_byc_z_ue():
    with pytest.raises(RuntimeError):
        poswiadczenia._model_z_env("anthropic.claude-sonnet-4-6")
    assert poswiadczenia._model_z_env("") == ""


class TestKlauzula:
    def test_odpis_z_cechami_i_taksa(self):
        d = poswiadczenia.zloz_wynik({"dokumenty": [FAKTURA]}, 2, "odpis", date(2026, 11, 8))["dokumenty"][0]
        k = d["klauzula"]
        assert k.startswith("Repertorium A nr [nr]\n")
        assert "Poświadczam zgodność niniejszego odpisu z okazanym mi dokumentem – faktury VAT nr FV/1/2026" in k
        assert "(2 strony)." in k and "Okazany dokument: oryginał." in k
        assert "Na dokumencie: odręczny dopisek na stronie 2." in k
        assert f"{d['taksa_netto']:.2f}".replace(".", ",") + " zł na podstawie § 13 pkt 2" in k
        assert f"{d['taksa_vat']:.2f}".replace(".", ",") + " zł." in k
        assert k.endswith("[miejscowość], dnia 8 listopada 2026 r.")
        assert d["podstawa"] == "§ 13 pkt 2"

    def test_bez_cech_i_data_okazania(self):
        bez_cech = {**FAKTURA, "cechy": []}
        k = poswiadczenia.zloz_wynik({"dokumenty": [bez_cech]}, 1, "kopia", date(2026, 1, 2))["dokumenty"][0]["klauzula"]
        assert "niniejszej kopii" in k and "nie zawiera dopisków, poprawek ani uszkodzeń" in k
        d = poswiadczenia.zloz_wynik({"dokumenty": [bez_cech]}, 1, "data", date(2026, 1, 2))["dokumenty"][0]
        assert "okazano mi dokument – faktury VAT" in d["klauzula"] and "2 stycznia 2026 r." in d["klauzula"]
        assert d["podstawa"] == "§ 13 pkt 3" and "Okazany dokument" not in d["klauzula"]


class TestObrazy:
    def test_pasy_w_limicie_obrazow(self, tmp_path):
        # wysoka strona A4 w 300 dpi - dzieli sie na pasy
        sciezki = []
        for nr in range(1, 4):
            sciezka = tmp_path / f"{nr}.png"
            Image.new("L", (2480, 3508), 255).save(sciezka)
            sciezki.append(sciezka)
        tresc = poswiadczenia._tresc_dla_modelu(poswiadczenia.dokumenty.opisz_strony(sciezki))
        obrazy = sum(1 for t in tresc if "image" in t)
        assert 3 < obrazy <= poswiadczenia.bedrock.MAX_OBRAZOW
        assert any("pas 1 z" in t.get("text", "") for t in tresc)


ODPOWIEDZ_UI = {"rodzaj": "odpis", "stron": 1, "razem_brutto": 7.38, "znaczniki": {"nr": "[nr]", "miejscowosc": "[miejscowość]"},
                "dokumenty": [{"nr": 1, "strona_od": 1, "strona_do": 1, "stron": 1, "nazwa": "faktura VAT", "numer": "FV/1/2026",
                               "opis": "Poświadczenie zgodności odpisu z okazanym dokumentem – faktury VAT nr FV/1/2026 (1 strona)",
                               "klauzula": "Repertorium A nr [nr]\nPoświadczam ...\n[miejscowość], dnia 8 listopada 2026 r.",
                               "taksa_netto": 6.0, "taksa_vat": 1.38, "taksa_brutto": 7.38, "podstawa": "§ 13 pkt 2",
                               "cechy": [], "niepewne": []}]}

# Atrapa folderu kopiarki: jeden skan, ktory "kopiarka" juz skonczyla zapisywac.
ATRAPA_FOLDERU = """
window.__przeniesione = [];
const plik = new File([new Uint8Array([37,80,68,70])], "Sobczak.pdf", {type: "application/pdf", lastModified: Date.now() - 60000});
let jest = true;
const wpis = {kind: "file", name: "Sobczak.pdf", getFile: async () => plik,
              move: async () => { jest = false; window.__przeniesione.push("Sobczak.pdf"); }};
const folder = {kind: "directory", name: "Skany", queryPermission: async () => "granted",
  requestPermission: async () => "granted",
  getDirectoryHandle: async () => ({name: "odczytane"}),
  entries: async function* () { if (jest) yield ["Sobczak.pdf", wpis]; }};
window.showDirectoryPicker = async () => folder;
"""


def test_ui_folder_kopiarki_numeracja_i_klauzula(serwer):  # noqa: F811
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as p:
        try:
            przegladarka = p.chromium.launch(headless=True)
        except Exception as blad:  # noqa: BLE001
            # Wersja Playwright inna niz zainstalowanej przegladarki: sciezka wprost.
            sciezka = os.getenv("PIECZAPP_CHROMIUM", "")
            if not sciezka:
                pytest.skip(f"Brak Chromium dla Playwright: {blad}")
            przegladarka = p.chromium.launch(headless=True, executable_path=sciezka)
        strona = przegladarka.new_page()
        bledy = []
        strona.on("pageerror", lambda b: bledy.append(str(b)))
        strona.add_init_script(ATRAPA_FOLDERU)
        strona.route("**/api/poswiadczenia/opis", lambda t: t.fulfill(json=ODPOWIEDZ_UI))
        strona.goto(serwer + "/poswiadczenia")
        strona.fill("#miejscowosc", "Poznań")
        strona.fill("#nastepny-nr", "0099/2026")
        strona.click("#btn-folder")
        strona.wait_for_function("window.__przeniesione.length === 1", timeout=20000)
        strona.wait_for_selector(".wpis textarea.klauzula", state="attached")
        assert strona.input_value(".wpis-nr input") == "0099/2026"
        assert strona.input_value("#nastepny-nr") == "0100/2026"
        klauzula = strona.input_value(".wpis textarea.klauzula")
        assert klauzula.startswith("Repertorium A nr 0099/2026") and "Poznań, dnia" in klauzula
        assert "Nasłuchuję" in strona.text_content("#folder-stan")
        assert bledy == []
        przegladarka.close()
