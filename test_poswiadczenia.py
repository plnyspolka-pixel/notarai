"""Poswiadczenie kopii -> opis do repertorium A. Model zastapiony atrapa,
dane zmyslone (Sobczak/Pawlak)."""
import io
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
