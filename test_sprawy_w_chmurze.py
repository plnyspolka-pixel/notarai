"""Sprawy w chmurze: odczyt, rozmowa i projekt zawsze przy sprawie na serwerze.

Do 23.11.2026 byl tez tryb "pliki u siebie" (punkty /api/odczyt, /api/projekt,
/api/rozmowa bez zapisu). Wycofany - wszystkie kancelarie pracuja w chmurze,
a dawne sprawy z komputera przenosi przeniesienie.py (testy na koncu pliku).
Dane fikcyjne, bez Bedrock i bez AWS."""
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




def _nowa_sprawa(klient, **kw) -> dict:
    with patch("bedrock.odczytaj_sprawe", return_value=(ODCZYT, [])), \
         patch("bedrock.rozmawiaj", return_value="Czego brakuje?"):
        odp = klient.post("/api/sprawy", files={"wzor": _wzor(), "skany": _skan()}, **kw)
    assert odp.status_code == 200, odp.text
    return odp.json()


class TestOdczyt:
    def test_tworzy_sprawe_z_rozmowa(self, klient, tmp_path):
        wynik = _nowa_sprawa(klient, data={"polecenie": "sprzedaz"})
        assert wynik["pola"][0]["wartosc"] == "Jan Kowalski"
        assert wynik["rozmowa"][0]["rola"] == "asystent"
        assert (tmp_path / wynik["id"] / "sprawa.json").exists()

    def test_blad_modelu_to_502(self, klient):
        with patch("bedrock.odczytaj_sprawe", side_effect=RuntimeError("model padl")), \
             patch("bedrock.rozmawiaj", return_value="x"):
            odp = klient.post("/api/sprawy", files={"wzor": _wzor(), "skany": _skan()})
        assert odp.status_code == 502


class TestOdczytStrumieniem:
    """Duza sprawa czyta sie dluzej niz ALB trzyma cisze - postep idzie strumieniem."""

    def test_postep_i_wynik_w_liniach_json(self, klient):
        def odczyt(strony, pola, polecenie, legenda, postep, wysilek):
            assert wysilek == "high"
            postep("transkrypcja", 1, 1)
            postep("zestawienie", 0, 1)
            return ODCZYT, []

        with patch("bedrock.odczytaj_sprawe", side_effect=odczyt), \
             patch("bedrock.rozmawiaj", return_value="Czego brakuje?"):
            odp = klient.post("/api/sprawy", files={"wzor": _wzor(), "skany": _skan()},
                              data={"wysilek": "high"}, headers={"Accept": "application/x-ndjson"})
        assert odp.status_code == 200
        linie = [json.loads(l) for l in odp.text.splitlines() if l.strip()]
        assert linie[0] == {"postep": {"etap": "transkrypcja", "gotowe": 1, "wszystkie": 1}}
        assert linie[-1]["wynik"]["pola"][0]["wartosc"] == "Jan Kowalski"

    def test_blad_jako_ostatnia_linia(self, klient):
        with patch("bedrock.odczytaj_sprawe", side_effect=RuntimeError("model padl")), \
             patch("bedrock.rozmawiaj", return_value="x"):
            odp = klient.post("/api/sprawy", files={"wzor": _wzor(), "skany": _skan()},
                              headers={"Accept": "application/x-ndjson"})
        ostatnia = json.loads(odp.text.strip().splitlines()[-1])
        assert ostatnia["kod"] == 502 and ostatnia["blad"]


class TestRozmowaIProjekt:
    def test_rozmowa_przy_sprawie(self, klient):
        id_s = _nowa_sprawa(klient)["id"]
        with patch("bedrock.rozmawiaj", return_value="Rozumiem.") as model:
            odp = klient.post(f"/api/sprawy/{id_s}/rozmowa", json={"tresc": "Cena 50 000"})
        assert odp.status_code == 200 and odp.json()["rozmowa"][-1]["tresc"] == "Rozumiem."
        assert model.call_args.args[1][0]["tresc"] == "Czego brakuje?", "historia z serwera, nie z przegladarki"

    def test_pusta_wiadomosc(self, klient):
        id_s = _nowa_sprawa(klient)["id"]
        assert klient.post(f"/api/sprawy/{id_s}/rozmowa", json={"tresc": "  "}).status_code == 400

    def test_projekt_strumieniem_zostaje_przy_sprawie(self, klient, tmp_path):
        id_s = _nowa_sprawa(klient)["id"]
        with patch("bedrock.sporzadz_projekt", return_value="AKT NOTARIALNY\n\nTresc."):
            odp = klient.post(f"/api/sprawy/{id_s}/projekt", json={"pola": ODCZYT["pola"]},
                              headers={"Accept": "application/x-ndjson"})
        assert "ndjson" in odp.headers["content-type"]
        assert json.loads(odp.text.strip().splitlines()[-1])["wynik"]["tekst"].startswith("AKT NOTARIALNY")
        assert (tmp_path / id_s / "projekt.docx").read_bytes()[:2] == b"PK"

    def test_punkty_bez_zapisu_wycofane(self, klient):
        for adres in ("/api/odczyt", "/api/projekt", "/api/rozmowa"):
            assert klient.post(adres, json={}).status_code in (404, 405)


class TestKancelariaWDawnymTrybie:
    """Kancelaria, ktora miala pliki u siebie, do przeniesienia nic nie zapisuje."""

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

    def test_nowa_sprawa_kaze_najpierw_przeniesc(self, klient):
        import magazyn
        znacznik = magazyn.przechowywanie_var.set("u-klienta")
        try:
            odp = klient.post("/api/sprawy", files={"wzor": _wzor(), "skany": _skan()})
            assert odp.status_code == 409
            assert "przenies" in odp.json()["detail"]
        finally:
            magazyn.przechowywanie_var.reset(znacznik)


class TestPrzeniesienie:
    @pytest.fixture
    def dawna(self, klient, tmp_path, monkeypatch):
        import autoryzacja
        import config
        monkeypatch.setattr(config, "DANE", tmp_path / "dane")
        (tmp_path / "dane").mkdir()
        autoryzacja._zapisz_rejestr({"x": {"id": "lokalna", "nazwa": "K", "aktywna": True,
                                           "przechowywanie": "u-klienta"}})
        autoryzacja._uniewaznij_rejestr()
        return klient

    def _pliki(self):
        return [("pliki", ("sprawa.json", b'{"id": "abc123", "utworzono": "2026-01-01T10:00:00"}', "application/json")),
                ("pliki", ("skany/akt.png", _skan()[1], "image/png")),
                ("pliki", ("projekt.txt", "AKT".encode(), "text/plain"))]

    def test_sprawa_z_folderu_trafia_do_chmury(self, dawna, tmp_path):
        odp = dawna.post("/api/przeniesienie/sprawy/abc123", files=self._pliki())
        assert odp.status_code == 200, odp.text
        assert (tmp_path / "abc123" / "skany" / "akt.png").exists()
        assert (tmp_path / "abc123" / "projekt.txt").read_text() == "AKT"
        # Powtorka niczego nie psuje (przerwane przenoszenie mozna wznowic).
        assert dawna.post("/api/przeniesienie/sprawy/abc123", files=self._pliki()).status_code == 200

    def test_zle_sciezki_odrzucone(self, dawna):
        for zla in ("../poza.txt", "/etc/passwd", ".ukryty", "a/../../b"):
            pliki = self._pliki() + [("pliki", (zla, b"x", "text/plain"))]
            assert dawna.post("/api/przeniesienie/sprawy/abc123", files=pliki).status_code == 400, zla
        assert dawna.post("/api/przeniesienie/sprawy/zly.id", files=self._pliki()).status_code in (400, 404)

    def test_bez_sprawa_json_odrzucone(self, dawna):
        odp = dawna.post("/api/przeniesienie/sprawy/abc123",
                         files=[("pliki", ("projekt.txt", b"x", "text/plain"))])
        assert odp.status_code == 400

    def test_zakonczenie_przelacza_na_chmure_i_zamyka_przenoszenie(self, dawna):
        import autoryzacja
        assert dawna.post("/api/przeniesienie/zakoncz").json() == {"przechowywanie": "chmura"}
        assert autoryzacja._przechowywanie("lokalna") == "chmura"
        assert dawna.post("/api/przeniesienie/sprawy/abc123", files=self._pliki()).status_code == 409

    def test_nowej_kancelarii_nie_da_sie_zalozyc_u_klienta(self):
        import autoryzacja
        assert autoryzacja.NowaKancelaria(nazwa="K").przechowywanie == "chmura"
