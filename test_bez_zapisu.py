"""Praca bez zapisu: pliki zostaja u kancelarii, serwer niczego nie trzyma."""
import importlib
import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _przywroc_moduly():
    yield
    import autoryzacja
    import magazyn
    import app as aplikacja
    importlib.reload(magazyn)
    importlib.reload(autoryzacja)
    importlib.reload(aplikacja)


def _wzor(tresc="Dnia __ przed notariuszem __ stawil sie {{zbywca}}.") -> tuple:
    from docx import Document
    dokument = Document()
    dokument.add_paragraph(tresc)
    bufor = io.BytesIO()
    dokument.save(bufor)
    return ("wzor.docx", bufor.getvalue(),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document")


def _skan() -> tuple:
    from PIL import Image
    bufor = io.BytesIO()
    Image.new("L", (900, 1200), 255).save(bufor, format="PNG")
    return ("skan.png", bufor.getvalue(), "image/png")


@pytest.fixture
def klient(tmp_path, monkeypatch):
    import config
    import app as aplikacja
    monkeypatch.setattr(config, "SPRAWY", tmp_path, raising=False)
    return TestClient(aplikacja.app)


ODCZYT = {"pola": [{"nr": 1, "nazwa": "zbywca", "wartosc": "Jan Kowalski"}],
          "braki": [], "rozbieznosci": []}


class TestOdczytBezZapisu:
    def test_nie_zostawia_nic_na_dysku(self, klient, tmp_path):
        """Po odczycie w katalogu spraw nie moze pojawic sie nowa sprawa."""
        przed = set(p.name for p in tmp_path.iterdir()) if tmp_path.exists() else set()
        with patch("bedrock.odczytaj_dane", return_value=ODCZYT), \
             patch("bedrock.rozmawiaj", return_value="Czego brakuje?"):
            odp = klient.post("/api/odczyt",
                              files={"wzor": _wzor(), "skany": _skan()},
                              data={"polecenie": "sprzedaz"})
        assert odp.status_code == 200
        wynik = odp.json()
        assert "id" not in wynik, "tryb bez zapisu nie tworzy sprawy"
        assert wynik["pola"][0]["wartosc"] == "Jan Kowalski"
        assert wynik["kontekst"], "przegladarka potrzebuje kontekstu do dalszej rozmowy"
        assert wynik["rozmowa"][0]["rola"] == "asystent"
        po = set(p.name for p in tmp_path.iterdir()) if tmp_path.exists() else set()
        assert po == przed, "na serwerze nie moze zostac zaden plik"

    def test_katalog_tymczasowy_znika_takze_po_bledzie(self, klient, tmp_path):
        import tempfile
        przed = set(Path(tempfile.gettempdir()).glob("notarai-*"))
        with patch("bedrock.odczytaj_dane", side_effect=RuntimeError("model padl")), \
             patch("bedrock.rozmawiaj", return_value="x"):
            odp = klient.post("/api/odczyt", files={"wzor": _wzor(), "skany": _skan()})
        assert odp.status_code == 502
        assert set(Path(tempfile.gettempdir()).glob("notarai-*")) == przed


class TestProjektBezZapisu:
    def test_zwraca_plik_do_zapisania_u_siebie(self, klient):
        with patch("bedrock.sporzadz_projekt", return_value="AKT NOTARIALNY\n\nTresc."):
            odp = klient.post("/api/projekt", files={"wzor": _wzor()},
                              data={"pola": json.dumps([{"nazwa": "zbywca", "wartosc": "Jan"}]),
                                    "polecenie": "", "rozmowa": "[]"})
        assert odp.status_code == 200
        wynik = odp.json()
        assert wynik["tekst"].startswith("AKT NOTARIALNY")
        import base64
        assert base64.b64decode(wynik["docx"])[:2] == b"PK", "docx to archiwum zip"

    def test_zly_format_pol(self, klient):
        odp = klient.post("/api/projekt", files={"wzor": _wzor()},
                          data={"pola": "to nie json"})
        assert odp.status_code == 400


class TestRozmowaBezZapisu:
    def test_historia_przychodzi_z_przegladarki(self, klient):
        with patch("bedrock.rozmawiaj", return_value="Rozumiem.") as rozmowa:
            odp = klient.post("/api/rozmowa", json={
                "kontekst": "DANE: x",
                "historia": [{"rola": "asystent", "tresc": "Czego brakuje?"}],
                "tresc": "Cena 50 000",
            })
        assert odp.status_code == 200 and odp.json()["odpowiedz"] == "Rozumiem."
        assert rozmowa.call_args.args[1] == [{"rola": "asystent", "tresc": "Czego brakuje?"}]

    def test_pusta_wiadomosc(self, klient):
        assert klient.post("/api/rozmowa", json={"kontekst": "x", "tresc": "  "}).status_code == 400


class TestZakazZapisu:
    """Kancelaria trzymajaca pliki u siebie nie moze nic zapisac w chmurze."""

    def test_magazyn_odmawia_utrwalenia(self, tmp_path):
        import magazyn
        importlib.reload(magazyn)
        znacznik = magazyn.przechowywanie_var.set("u-klienta")
        try:
            katalog = tmp_path / "abc123"
            katalog.mkdir()
            (katalog / "sprawa.json").write_text("{}")
            with pytest.raises(RuntimeError, match="u siebie"):
                magazyn.utrwal_sprawe(katalog)
        finally:
            magazyn.przechowywanie_var.reset(znacznik)

    def test_tworzenie_sprawy_odrzucone(self, klient):
        import magazyn
        znacznik = magazyn.przechowywanie_var.set("u-klienta")
        try:
            odp = klient.post("/api/sprawy", files={"wzor": _wzor(), "skany": _skan()})
            assert odp.status_code == 409
            assert "u siebie" in odp.json()["detail"]
        finally:
            magazyn.przechowywanie_var.reset(znacznik)
