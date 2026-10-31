"""Smoke testy kalendarza i plikow sprawy przez API. Dane zmyslone
(zestaw Sobczak/Pawlak).

Scenariusz z 1.11.2026: przy edycji terminu klik w wolna godzine po cichu
przenosil termin, a jego dawne godziny wygladaly na wolne. Serwer pilnuje,
zeby zmiana jednego terminu nie ruszala innych - tu to sprawdzamy; zachowanie
okna dnia sprawdza test_kalendarz_ui.py.
"""
import importlib
import json

import pytest
from fastapi.testclient import TestClient

DZIEN = "2026-11-03"


@pytest.fixture
def klient(tmp_path, monkeypatch):
    import config
    import magazyn
    monkeypatch.setattr(config, "DANE", tmp_path)
    # Inne testy zostawiaja po sobie config.SPRAWY wskazujace prawdziwe dane.
    if "SPRAWY" in vars(config):
        monkeypatch.delattr(config, "SPRAWY")
    assert config.SPRAWY.is_relative_to(tmp_path)
    assert magazyn.TRYB == "lokalny"
    import app as aplikacja
    return TestClient(aplikacja.app)


def zarezerwuj(klient, godzina, koniec, **pola):
    odp = klient.post("/api/kalendarz", json={"data": DZIEN, "godzina": godzina, "koniec": koniec, **pola})
    assert odp.status_code == 200, odp.text
    return odp.json()


def godziny(klient):
    return {w["uczestnicy"]: (w["godzina"], w["koniec"]) for w in klient.get("/api/kalendarz").json()}


class TestRezerwacje:
    def test_przeniesienie_terminu_nie_rusza_innych(self, klient):
        zarezerwuj(klient, "09:00", "10:00", uczestnicy="Sobczak, Pawlak", rodzaj="dział spadku")
        zarezerwuj(klient, "10:00", "10:30", uczestnicy="Pawlak Ewa", rodzaj="testament")
        kiks = zarezerwuj(klient, "10:30", "11:00", uczestnicy="Sobczak Tomasz", rodzaj="poświadczenie podpisów")

        odp = klient.put(f"/api/kalendarz/{kiks['id']}", json={**kiks, "godzina": "12:30", "koniec": "13:30"})
        assert odp.status_code == 200
        assert godziny(klient) == {"Sobczak, Pawlak": ("09:00", "10:00"),
                                   "Pawlak Ewa": ("10:00", "10:30"),
                                   "Sobczak Tomasz": ("12:30", "13:30")}
        # Zwolniona godzina jest naprawde wolna.
        zarezerwuj(klient, "10:30", "11:00", uczestnicy="Pawlak Grzegorz", rodzaj="darowizna")

    def test_kolizje_odrzucone_bez_zmian(self, klient):
        pierwszy = zarezerwuj(klient, "10:00", "11:00", uczestnicy="Sobczak Tomasz", rodzaj="sprzedaż")
        drugi = zarezerwuj(klient, "11:00", "11:30", uczestnicy="Pawlak Ewa", rodzaj="testament")
        przed = klient.get("/api/kalendarz").json()

        assert klient.post("/api/kalendarz", json={"data": DZIEN, "godzina": "10:30", "koniec": "11:00",
                                                   "uczestnicy": "Ktoś"}).status_code == 400
        # Przedluzenie na cudza godzine - odmowa, termin zostaje jak byl.
        odp = klient.put(f"/api/kalendarz/{pierwszy['id']}", json={**pierwszy, "koniec": "11:30"})
        assert odp.status_code == 400 and "zajęte" in odp.json()["detail"]
        assert klient.get("/api/kalendarz").json() == przed
        # Przedluzenie na wolna godzine - w porzadku; ten sam dzien, inny wpis bez zmian.
        assert klient.put(f"/api/kalendarz/{drugi['id']}", json={**drugi, "koniec": "12:30"}).status_code == 200
        assert godziny(klient)["Sobczak Tomasz"] == ("10:00", "11:00")

    def test_usuniecie(self, klient):
        wpis = zarezerwuj(klient, "10:00", "10:30", uczestnicy="Pawlak Ewa", rodzaj="testament")
        assert klient.delete(f"/api/kalendarz/{wpis['id']}").status_code == 200
        assert klient.delete(f"/api/kalendarz/{wpis['id']}").status_code == 404
        assert klient.put(f"/api/kalendarz/{wpis['id']}", json=wpis).status_code == 404
        assert klient.get("/api/kalendarz").json() == []


class TestTelefony:
    def test_kilka_telefonow_z_imionami(self, klient):
        wpis = zarezerwuj(klient, "10:00", "10:30", uczestnicy="Sobczak, Pawlak", rodzaj="sprzedaż", telefony=[
            {"imie": "Tomasz", "numer": "600 100 200"},
            {"imie": "", "numer": ""},                  # pusty wiersz formularza
            {"imie": "Ewa", "numer": "+48 601 200 300"},
        ])
        assert wpis["telefony"] == [{"imie": "Tomasz", "numer": "600 100 200"},
                                    {"imie": "Ewa", "numer": "+48 601 200 300"}]
        assert "telefon" not in wpis

    @pytest.mark.parametrize("telefony, blad", [
        ([{"imie": "Ewa", "numer": ""}], "Podaj numer"),
        ([{"imie": "Ewa", "numer": "abc"}], "Nieprawidłowy numer"),
        ([{"imie": "", "numer": "600100200"}] * 11, "Najwyżej"),
    ])
    def test_bledne_telefony(self, klient, telefony, blad):
        odp = klient.post("/api/kalendarz", json={"data": DZIEN, "godzina": "10:00", "uczestnicy": "Pawlak Ewa",
                                                  "telefony": telefony})
        assert odp.status_code == 400 and blad in odp.json()["detail"]

    def test_dawny_pojedynczy_telefon(self, klient, tmp_path):
        # Wpis sprzed zmiany: jedno pole "telefon".
        (tmp_path / "kalendarz.json").write_text(json.dumps([{
            "id": "abc123abc123", "data": DZIEN, "godzina": "10:00", "koniec": "10:30", "tytul": "",
            "rodzaj": "testament", "rodzaj_inny": "", "uczestnicy": "Pawlak Ewa", "telefon": "600 100 200",
            "sprawa": "", "uwagi": ""}]), "utf-8")
        wpis = klient.get("/api/kalendarz").json()[0]
        assert wpis["telefony"] == [{"imie": "", "numer": "600 100 200"}] and "telefon" not in wpis
        # Stary klient wysyla jeszcze "telefon" - trafia na liste.
        odp = klient.put("/api/kalendarz/abc123abc123", json={**wpis, "telefony": None, "telefon": "601 200 300"})
        assert odp.json()["telefony"] == [{"imie": "", "numer": "601 200 300"}]
        zapisany = json.loads((tmp_path / "kalendarz.json").read_text("utf-8"))[0]
        assert "telefon" not in zapisany


@pytest.fixture
def sprawa(klient, tmp_path):
    import config
    katalog = config.SPRAWY / "aaa111aaa111"
    (katalog / "skany").mkdir(parents=True)
    (katalog / "sprawa.json").write_text(json.dumps({"id": "aaa111aaa111", "nazwa": "Sobczak - Pawlak"}), "utf-8")
    return katalog


class TestPlikiSprawy:
    ADRES = "/api/sprawy/aaa111aaa111/pliki"

    def test_dodaj_pobierz_usun(self, klient, sprawa):
        assert klient.get(self.ADRES).json() == []
        odp = klient.post(self.ADRES, files=[("pliki", ("wypis Sobczak.pdf", b"%PDF-1", "application/pdf")),
                                             ("pliki", ("zaświadczenie.jpg", b"jpg", "image/jpeg"))])
        assert odp.status_code == 200
        assert [p["nazwa"] for p in odp.json()] == ["wypis Sobczak.pdf", "zaświadczenie.jpg"]
        # Drugi plik o tej samej nazwie nie nadpisuje pierwszego.
        odp = klient.post(self.ADRES, files=[("pliki", ("wypis Sobczak.pdf", b"%PDF-2", "application/pdf"))])
        assert [p["nazwa"] for p in odp.json()] == ["wypis Sobczak (2).pdf", "wypis Sobczak.pdf", "zaświadczenie.jpg"]

        assert klient.get(self.ADRES + "/wypis Sobczak.pdf").content == b"%PDF-1"
        assert klient.get(self.ADRES + "/wypis Sobczak (2).pdf").content == b"%PDF-2"

        odp = klient.delete(self.ADRES + "/wypis Sobczak.pdf")
        assert [p["nazwa"] for p in odp.json()] == ["wypis Sobczak (2).pdf", "zaświadczenie.jpg"]
        assert klient.get(self.ADRES + "/wypis Sobczak.pdf").status_code == 404
        assert klient.delete(self.ADRES + "/wypis Sobczak.pdf").status_code == 404
        # Pliki sa czescia sprawy - znikaja razem z nia.
        assert klient.delete("/api/sprawy/aaa111aaa111?potwierdzam=true").status_code == 200
        assert not sprawa.exists()

    def test_nazwy_nie_wychodza_poza_sprawe(self, klient, sprawa):
        (sprawa / "sprawa.json").read_text("utf-8")
        odp = klient.post(self.ADRES, files=[("pliki", ("../../sprawa.json", b"x", "text/plain"))])
        assert [p["nazwa"] for p in odp.json()] == ["sprawa.json"]
        assert json.loads((sprawa / "sprawa.json").read_text("utf-8"))["id"] == "aaa111aaa111"
        assert klient.get(self.ADRES + "/..%2Fsprawa.json").status_code in (400, 404)
        assert klient.post(self.ADRES, files=[("pliki", ("...", b"x", "text/plain"))]).status_code == 400
        assert klient.get("/api/sprawy/brak/pliki").status_code == 404

    def test_za_duzy_plik(self, klient, sprawa, monkeypatch):
        import app as aplikacja
        monkeypatch.setattr(aplikacja, "MAKS_ZALACZNIK", 10)
        odp = klient.post(self.ADRES, files=[("pliki", ("maly.txt", b"x", "text/plain")),
                                             ("pliki", ("duzy.pdf", b"x" * 11, "application/pdf"))])
        assert odp.status_code == 413
        assert klient.get(self.ADRES).json() == []   # nic nie zapisano, takze malego

    def test_kancelaria_u_siebie(self, klient, sprawa):
        import magazyn
        znacznik = magazyn.przechowywanie_var.set("u-klienta")
        try:
            assert klient.post(self.ADRES, files=[("pliki", ("a.pdf", b"x", "application/pdf"))]).status_code == 409
            assert klient.delete(self.ADRES + "/a.pdf").status_code == 409
        finally:
            magazyn.przechowywanie_var.reset(znacznik)


def test_usuniecie_pliku_z_s3_ze_starszymi_wersjami(tmp_path, monkeypatch):
    from test_magazyn import AtrapaS3
    monkeypatch.setenv("PIECZAPP_MAGAZYN", "s3")
    monkeypatch.setenv("PIECZAPP_S3_BUCKET", "testowy-bucket")
    import magazyn
    importlib.reload(magazyn)
    try:
        atrapa = AtrapaS3()
        monkeypatch.setattr(magazyn, "_s3", atrapa)
        katalog = tmp_path / "aaa111aaa111"
        (katalog / "zalaczniki").mkdir(parents=True)
        (katalog / "sprawa.json").write_text("{}", "utf-8")
        (katalog / "zalaczniki" / "wypis.pdf").write_bytes(b"1")
        (katalog / "zalaczniki" / "wypis.pdf.bak").write_bytes(b"2")
        magazyn.utrwal_sprawe(katalog)

        magazyn.usun_plik_sprawy(katalog, "zalaczniki/wypis.pdf")
        assert not (katalog / "zalaczniki" / "wypis.pdf").exists()
        assert sorted(k.rsplit("/", 2)[-1] for k in atrapa.obiekty) == ["sprawa.json", "wypis.pdf.bak"]
        # Znacznik zgodny z S3 - kopia lokalna nie jest pobierana od nowa.
        pobrania = atrapa.pobrania
        assert magazyn.pobierz_sprawe(katalog) and atrapa.pobrania == pobrania
    finally:
        monkeypatch.setenv("PIECZAPP_MAGAZYN", "lokalny")
        importlib.reload(magazyn)
