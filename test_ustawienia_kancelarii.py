"""Ustawienia ogolne kancelarii: domyslna dokladnosc odczytu (z trybem
automatycznym), wzor nazwy pliku Word i ich uzycie w API.

Dane zmyslone, bez Bedrock, bez AWS. Pliki kancelarii leza w tmp_path.
"""
import io
import json
from pathlib import Path
from unittest.mock import patch

import fitz
import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

import app as aplikacja
import config
import dokumenty
import nazwy
import ustawienia_kancelarii as ustawienia


@pytest.fixture
def klient(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DANE", tmp_path)
    monkeypatch.setattr(config, "SPRAWY", tmp_path / "sprawy", raising=False)
    (tmp_path / "sprawy").mkdir(exist_ok=True)
    return TestClient(aplikacja.app)


def _pdf_z_tekstem(sciezka: Path, stron: int = 2) -> Path:
    pdf = fitz.open()
    for _ in range(stron):
        strona = pdf.new_page()
        strona.insert_textbox(fitz.Rect(60, 60, 540, 760), "Tresc dokumentu elektronicznego. " * 20)
    pdf.save(sciezka)
    return sciezka


def _pdf_skan(sciezka: Path, stron: int = 1) -> Path:
    pdf = fitz.open()
    for _ in range(stron):
        pdf.new_page()
    pdf.save(sciezka)
    return sciezka


# ---------------------------------------------------------------- przechowywanie

class TestPrzechowywanie:
    def test_domyslne_gdy_brak_pliku(self, klient):
        assert ustawienia.wczytaj() == {"dokladnosc": "auto", "nazwa_pliku": nazwy.DOMYSLNY_WZOR_NAZWY}

    def test_zapis_i_odczyt(self, klient, tmp_path):
        wynik = ustawienia.zapisz({"dokladnosc": "medium", "nazwa_pliku": "{strony} - {czynnosc}"})
        assert wynik == {"dokladnosc": "medium", "nazwa_pliku": "{strony} - {czynnosc}"}
        assert ustawienia.wczytaj()["dokladnosc"] == "medium"
        assert (tmp_path / "ustawienia.json").exists(), "plik kancelarii, jak kalendarz czy zasady"

    def test_zapis_czesciowy_nie_rusza_reszty(self, klient):
        ustawienia.zapisz({"nazwa_pliku": "{sygnatura}"})
        ustawienia.zapisz({"dokladnosc": "high"})
        assert ustawienia.wczytaj() == {"dokladnosc": "high", "nazwa_pliku": "{sygnatura}"}

    def test_nieznana_dokladnosc_odrzucona(self, klient):
        with pytest.raises(ValueError):
            ustawienia.zapisz({"dokladnosc": "ultra"})

    def test_nieznane_pole_we_wzorze_odrzucone(self, klient):
        with pytest.raises(ValueError) as blad:
            ustawienia.zapisz({"nazwa_pliku": "{zbywca} - {klient}"})
        assert "{klient}" in str(blad.value)

    def test_pusty_wzor_wraca_do_domyslnego(self, klient):
        assert ustawienia.zapisz({"nazwa_pliku": "   "})["nazwa_pliku"] == nazwy.DOMYSLNY_WZOR_NAZWY

    def test_uszkodzony_plik_nie_wywraca_odczytu(self, klient, tmp_path):
        (tmp_path / "ustawienia.json").write_text('{"dokladnosc": "cokolwiek", "nazwa_pliku": 7}', "utf-8")
        assert ustawienia.wczytaj() == ustawienia.domyslne()


# ---------------------------------------------------------------- dokladnosc

class TestDokladnoscOdczytu:
    def test_wybrana_recznie_ma_pierwszenstwo(self, klient):
        ustawienia.zapisz({"dokladnosc": "medium"})
        assert ustawienia.dokladnosc_odczytu("max", []) == ("max", "wybrana")

    def test_pusta_bierze_domyslna_kancelarii(self, klient):
        ustawienia.zapisz({"dokladnosc": "high"})
        assert ustawienia.dokladnosc_odczytu("", []) == ("high", "domyslna")
        assert ustawienia.dokladnosc_odczytu("nieznana", []) == ("high", "domyslna")

    def test_auto_dokumenty_elektroniczne_czyta_szybko(self, klient, tmp_path):
        strony = dokumenty.opisz_strony([_pdf_z_tekstem(tmp_path / "kw.pdf")])
        assert ustawienia.dokladnosc_odczytu("auto", strony) == ("medium", "auto_elektroniczne")

    def test_auto_skany_czyta_dokladnie(self, klient, tmp_path):
        strony = dokumenty.opisz_strony([_pdf_z_tekstem(tmp_path / "kw.pdf"), _pdf_skan(tmp_path / "skan.pdf")])
        assert ustawienia.dokladnosc_odczytu("auto", strony) == ("high", "auto_skany")

    def test_auto_zdjecie_to_skan(self, klient, tmp_path):
        from PIL import Image
        Image.new("L", (40, 40), 255).save(tmp_path / "zdjecie.png")
        strony = dokumenty.opisz_strony([tmp_path / "zdjecie.png"])
        assert ustawienia.dokladnosc_odczytu("auto", strony) == ("high", "auto_skany")

    def test_auto_bez_stron_i_przy_bledzie_pliku(self, klient, tmp_path):
        assert ustawienia.dokladnosc_odczytu("auto", []) == ("high", "auto_skany")
        zly = [{"dokument": "x.pdf", "strona": 1, "sciezka": tmp_path / "nie-ma.pdf"}]
        assert ustawienia.dokladnosc_odczytu("auto", zly) == ("high", "auto_skany")

    def test_udzial_warstwy_tekstowej(self, tmp_path):
        strony = dokumenty.opisz_strony([_pdf_z_tekstem(tmp_path / "a.pdf", 3), _pdf_skan(tmp_path / "b.pdf", 1)])
        assert dokumenty.udzial_warstwy_tekstowej(strony) == pytest.approx(0.75)
        assert dokumenty.udzial_warstwy_tekstowej([]) == 0.0

    def test_opis_wyboru_po_polsku(self):
        assert "elektroniczne" in ustawienia.opis_wyboru("medium", "auto_elektroniczne")
        assert "skany" in ustawienia.opis_wyboru("high", "auto_skany")
        assert "kancelarii" in ustawienia.opis_wyboru("max", "domyslna")
        assert ustawienia.opis_wyboru("high", "wybrana") == "Dokładność wysoka."


# ---------------------------------------------------------------- API

class TestApi:
    def test_get_daje_ustawienia_i_pola(self, klient):
        odp = klient.get("/api/ustawienia/ogolne")
        assert odp.status_code == 200
        dane = odp.json()
        assert dane["dokladnosc"] == "auto"
        assert dane["moge_zmieniac"] is True
        assert "zbywca" in dane["pola_nazwy"]
        assert dane["przyklad_nazwy"].endswith(".docx")

    def test_put_zapisuje(self, klient):
        odp = klient.put("/api/ustawienia/ogolne", json={"dokladnosc": "medium", "nazwa_pliku": "{strony}"})
        assert odp.status_code == 200
        assert odp.json()["dokladnosc"] == "medium"
        assert odp.json()["przyklad_nazwy"] == "Sobczak - Pawlak.docx"
        assert klient.get("/api/ustawienia").json()["ogolne"] == {"dokladnosc": "medium", "nazwa_pliku": "{strony}"}

    def test_put_odrzuca_zle_dane(self, klient):
        assert klient.put("/api/ustawienia/ogolne", json={"dokladnosc": "ultra"}).status_code == 400
        assert klient.put("/api/ustawienia/ogolne", json={"nazwa_pliku": "{foo}"}).status_code == 400
        assert klient.put("/api/ustawienia/ogolne", json={}).status_code == 400

    def test_ustawienia_przegladarki_niosa_ogolne(self, klient):
        assert klient.get("/api/ustawienia").json()["ogolne"] == ustawienia.domyslne()

    def test_u_klienta_serwer_nie_zapisuje(self, klient):
        import magazyn
        znacznik = magazyn.przechowywanie_var.set("u-klienta")
        try:
            assert klient.put("/api/ustawienia/ogolne", json={"dokladnosc": "medium"}).status_code == 409
        finally:
            magazyn.przechowywanie_var.reset(znacznik)


# ---------------------------------------------------------------- nazwa pliku w sprawie

def _sprawa(tmp_path: Path, identyfikator: str, meta_dodatkowe: dict | None = None) -> Path:
    from docx import Document
    katalog = tmp_path / "sprawy" / identyfikator
    (katalog / "skany").mkdir(parents=True)
    dokument = Document()
    dokument.add_paragraph("aaa - zbywca (Jan Kowalski)")
    dokument.add_paragraph("bbb - nabywca (Anna Nowak)")
    dokument.add_paragraph("")
    dokument.add_paragraph("UMOWA SPRZEDAŻY")
    dokument.add_paragraph("aaa sprzedaje bbb nieruchomość położoną w ?? za cenę ?? zł.")
    dokument.save(katalog / "wzor.docx")
    meta = {"id": identyfikator, "nazwa": "Sobczak – Pawlak", "sygnatura": "A 7/2026",
            "utworzono": "2026-11-13T10:00:00", "polecenie": "", "wzor": "wzor.docx",
            "skany": ["skan.pdf"], "stron": 1, "wysilek": "medium"}
    meta.update(meta_dodatkowe or {})
    (katalog / "sprawa.json").write_text(json.dumps(meta), "utf-8")
    (katalog / "odczyt.json").write_text(json.dumps({"pola": [
        {"nazwa": "STALE: nazwiska stron czynnosci - SAME nazwiska", "wartosc": "Sobczak - Pawlak"},
        {"nazwa": "STALE: miejscowosc polozenia nieruchomosci - obreb", "wartosc": "Zalesie: dz. 12/3"},
    ], "braki": [], "rozbieznosci": []}), "utf-8")
    projekt = "UMOWA SPRZEDAŻY\nTomasz Sobczak sprzedaje Grzegorzowi Pawlakowi nieruchomość w Zalesiu."
    (katalog / "projekt.txt").write_text(projekt, "utf-8")
    dokumenty.tekst_na_docx(projekt, katalog / "projekt.docx", wzor=katalog / "wzor.docx")
    return katalog


class TestNazwaPlikuWSprawie:
    def test_pobranie_ma_nazwe_wg_wzoru(self, klient, tmp_path):
        _sprawa(tmp_path, "abc123")
        odp = klient.get("/api/sprawy/abc123/plik")
        assert odp.status_code == 200
        naglowek = odp.headers["content-disposition"]
        assert "Sobczak%20-%20Pawlak%20-%20sprzeda%C5%BC%20-%20Zalesie.docx" in naglowek

    def test_zapisana_nazwa_ma_pierwszenstwo(self, klient, tmp_path):
        _sprawa(tmp_path, "abc124", {"nazwa_pliku": "Moja nazwa"})
        odp = klient.get("/api/sprawy/abc124/plik")
        assert "Moja%20nazwa.docx" in odp.headers["content-disposition"]
        assert klient.get("/api/sprawy/abc124").json()["nazwa_pliku"] == "Moja nazwa"

    def test_wzor_kancelarii_z_ustawien(self, klient, tmp_path):
        ustawienia.zapisz({"nazwa_pliku": "{sygnatura} {nazwa}"})
        _sprawa(tmp_path, "abc125")
        dane = klient.get("/api/sprawy/abc125").json()
        assert dane["nazwa_pliku"] == "A 7-2026 Sobczak – Pawlak"
        assert dane["wysilek"] == "medium"

    def test_bez_projektu_nie_ma_nazwy(self, klient, tmp_path):
        katalog = _sprawa(tmp_path, "abc126")
        (katalog / "projekt.docx").unlink()
        assert klient.get("/api/sprawy/abc126").json()["nazwa_pliku"] is None
        assert klient.get("/api/sprawy/abc126/plik").status_code == 404

    def test_projekt_zapisuje_nazwe_i_formatuje_na_wzorze(self, klient, tmp_path):
        from docx import Document
        katalog = _sprawa(tmp_path, "abc127")
        with patch("bedrock.sporzadz_projekt", return_value="UMOWA SPRZEDAŻY\nTomasz Sobczak sprzedaje."):
            odp = klient.post("/api/sprawy/abc127/projekt", json={"pola": json.loads(
                (katalog / "odczyt.json").read_text("utf-8"))["pola"], "polecenie": ""})
        assert odp.status_code == 200, odp.text
        assert odp.json()["nazwa_pliku"] == "Sobczak - Pawlak - sprzedaż - Zalesie"
        meta = json.loads((katalog / "sprawa.json").read_text("utf-8"))
        assert meta["nazwa_pliku"] == "Sobczak - Pawlak - sprzedaż - Zalesie"
        assert Document(katalog / "projekt.docx").paragraphs[0].text == "UMOWA SPRZEDAŻY"


# ---------------------------------------------------------------- bledy Bedrock w API

class TestBledyBedrockPoPolsku:
    @staticmethod
    def _wzor():
        from docx import Document
        dokument = Document()
        dokument.add_paragraph("Dnia ?? stawil sie {{zbywca}}.")
        bufor = io.BytesIO()
        dokument.save(bufor)
        return ("wzor.docx", bufor.getvalue(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    @staticmethod
    def _skan():
        from PIL import Image
        bufor = io.BytesIO()
        Image.new("L", (20, 20), 255).save(bufor, format="PNG")
        return ("skan.png", bufor.getvalue(), "image/png")

    def test_za_duza_sprawa_ma_rade_zamiast_tekstu_boto(self, klient):
        blad = ClientError({"Error": {"Code": "ValidationException",
                                      "Message": "Input is too long for requested model."}}, "ConverseStream")
        with patch("bedrock.odczytaj_sprawe", side_effect=blad), patch("bedrock.rozmawiaj", return_value="x"):
            odp = klient.post("/api/odczyt", files={"wzor": self._wzor(), "skany": self._skan()})
        assert odp.status_code == 502
        assert "Podziel skany" in odp.json()["detail"]
        assert "ConverseStream" not in odp.json()["detail"]

    def test_blad_przejsciowy_mowi_sprobuj_ponownie(self, klient):
        blad = ClientError({"Error": {"Code": "modelStreamErrorException", "Message": "x"}}, "ConverseStream")
        with patch("bedrock.odczytaj_sprawe", side_effect=blad), patch("bedrock.rozmawiaj", return_value="x"):
            odp = klient.post("/api/odczyt", files={"wzor": self._wzor(), "skany": self._skan()})
        assert odp.status_code == 502
        assert "spróbuj ponownie" in odp.json()["detail"].lower()
