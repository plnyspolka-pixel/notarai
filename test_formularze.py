"""Testy asysty formularzy i sladu audytowego. Wszystko na atrapach."""
import json
from dataclasses import replace

import pytest

import config
import rejestry
from formularze import silnik
from formularze.silnik import Mapowanie, PoleFormularza, BladMapowania, wypelnij, zaplanuj

MAPA = Mapowanie(
    system="test", opis="t", adres="https://przyklad.gov.pl/formularz", status="gotowe",
    gotowosc="#pesel", przycisk_wysylki="#wyslij",
    pola=[
        PoleFormularza("PESEL", "pesel", "#pesel", "tekst", "cyfry", wymagane=True),
        PoleFormularza("KW", "ggg: nr kw", "#kw", "tekst", "kw_bez_ukosnikow"),
        PoleFormularza("Zgoda", "zgoda", "#zgoda", "pole_wyboru"),
    ],
)


class Atrapa:
    def __init__(self, url="https://przyklad.gov.pl/formularz/1", elementy=("#pesel", "#kw", "#zgoda", "#wyslij")):
        self.url, self.elementy, self.wpisane, self.klikniete = url, set(elementy), {}, []
    def istnieje(self, s): return s in self.elementy
    def wpisz(self, s, w): self.wpisane[s] = w
    def wybierz(self, s, w): self.wpisane[s] = w
    def zaznacz(self, s, tak): self.wpisane[s] = tak
    def kliknij(self, s): self.klikniete.append(s)


DANE = {"pesel": "44051401359", "ggg: nr kw": "KR1K/00012345/7", "zgoda": "tak"}


class TestPodglad:
    def test_podglad_nie_dotyka_strony(self):
        strona = Atrapa()
        raport = wypelnij(MAPA, DANE, strona)  # domyslnie podglad
        assert raport.tryb == "podglad"
        assert strona.wpisane == {}
        assert raport.do_wpisania == 3

    def test_transformacje(self):
        raport = zaplanuj(MAPA, {"pesel": "440 514 01359", "ggg: nr kw": "kr1k/00012345/7"})
        assert raport.kroki[0].wartosc == "44051401359"
        assert raport.kroki[1].wartosc == "KR1K000123457"

    def test_brak_wymaganego_oznaczony(self):
        raport = zaplanuj(MAPA, {})
        assert raport.kroki[0].uwaga == "BRAK w sprawie"
        assert "PESEL" in raport.brakujace


class TestFaktyczny:
    def test_wypelnia_i_nie_klika_wysylki(self):
        strona = Atrapa()
        raport = wypelnij(MAPA, DANE, strona, tryb="faktyczny")
        assert strona.wpisane == {"#pesel": "44051401359", "#kw": "KR1K000123457", "#zgoda": True}
        assert strona.klikniete == []
        assert raport.zatrzymano_przed == "#wyslij"
        assert all(k.wykonano for k in raport.kroki)

    def test_szkic_blokuje_tryb_faktyczny(self):
        strona = Atrapa()
        raport = wypelnij(replace(MAPA, status="szkic"), DANE, strona, tryb="faktyczny")
        assert strona.wpisane == {}
        assert any("szkic" in b for b in raport.bledy)

    def test_zla_strona_zatrzymuje(self):
        strona = Atrapa(url="https://inna.pl/")
        raport = wypelnij(MAPA, DANE, strona, tryb="faktyczny")
        assert strona.wpisane == {}
        assert raport.bledy

    def test_formularz_niegotowy_zatrzymuje(self):
        strona = Atrapa(elementy=("#wyslij",))
        raport = wypelnij(MAPA, DANE, strona, tryb="faktyczny")
        assert strona.wpisane == {}

    def test_pole_na_przycisku_wysylki_odrzucone_przy_wczytaniu(self):
        with pytest.raises(BladMapowania):
            Mapowanie(system="x", opis="", adres="https://a", status="gotowe", gotowosc="#a",
                      przycisk_wysylki="#wyslij",
                      pola=[PoleFormularza("Z", "z", "#wyslij", "tekst")])

    def test_blad_pola_bez_danych_w_raporcie(self):
        class Psuje(Atrapa):
            def wpisz(self, s, w):
                raise TimeoutError(w)  # tresc bledu zawiera dane - nie moze wyciec
        raport = wypelnij(MAPA, DANE, Psuje(), tryb="faktyczny")
        assert "TimeoutError" in raport.bledy[0]
        assert "44051401359" not in json.dumps([k.uwaga for k in raport.kroki] + raport.bledy)


class TestMapowaniaZPlikow:
    def test_wszystkie_yaml_wczytuja_sie(self):
        systemy = silnik.dostepne_systemy()
        assert systemy
        assert all(s["status"] in ("szkic", "gotowe") for s in systemy), systemy

    def test_nazwa_systemu_walidowana(self):
        with pytest.raises(BladMapowania):
            silnik.wczytaj_mapowanie("../cos")


class TestRejestry:
    def test_maskowanie(self):
        assert rejestry.maskuj_pesel("44051401359") == "*******1359"
        assert rejestry.maskuj_pesel("440-514-01359") == "*******1359"
        assert rejestry.maskuj_pesel("123") == "***"

    def test_pelny_pesel_odrzucony(self):
        with pytest.raises(ValueError):
            rejestry.WynikSprawdzenia("ZASTRZEZENIA_PESEL", "44051401359", "brak_wpisu")

    def test_slad_audytowy(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "SPRAWY", tmp_path)
        w = rejestry.WynikSprawdzenia("ZASTRZEZENIA_PESEL", rejestry.maskuj_pesel("44051401359"),
                                      "brak_wpisu", "odczyt z ekranu", zrodlo="Rejestry Notarialne KRN")
        rejestry.zapisz_sprawdzenie("abc123", w)
        rejestry.zapisz_sprawdzenie("abc123", replace(w, status="wpis"))
        wpisy = rejestry.wczytaj_sprawdzenia("abc123")
        assert [x["status"] for x in wpisy] == ["brak_wpisu", "wpis"]
        assert "44051401359" not in (tmp_path / "abc123" / "sprawdzenia.json").read_text()

    def test_nieznany_status(self):
        with pytest.raises(ValueError):
            rejestry.WynikSprawdzenia("KRZ", "***", "cos")


class TestApi:
    @pytest.fixture
    def klient(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient
        import app as aplikacja
        monkeypatch.setattr(config, "SPRAWY", tmp_path)
        (tmp_path / "abc123").mkdir()
        return TestClient(aplikacja.app)

    def test_lista_systemow(self, klient):
        odp = klient.get("/api/formularze")
        assert odp.status_code == 200 and odp.json()[0]["system"] == "rejestry_notarialne_pesel"

    def test_podglad_bez_przegladarki(self, klient):
        odp = klient.post("/api/sprawy/abc123/formularze/rejestry_notarialne_pesel",
                          json={"pola": [{"nazwa": "pesel", "wartosc": "44051401359"}]})
        assert odp.status_code == 200
        assert odp.json()["tryb"] == "podglad" and odp.json()["kroki"][0]["wykonano"] is False

    def test_faktyczny_wymaga_potwierdzenia(self, klient):
        odp = klient.post("/api/sprawy/abc123/formularze/rejestry_notarialne_pesel",
                          json={"pola": [], "tryb": "faktyczny"})
        assert odp.status_code == 400

    def test_nieznany_system(self, klient):
        assert klient.post("/api/sprawy/abc123/formularze/nie_ma", json={"pola": []}).status_code == 404

    def test_sprawdzenie_zapis_i_odczyt(self, klient, tmp_path):
        odp = klient.post("/api/sprawy/abc123/sprawdzenia",
                          json={"rejestr": "ZASTRZEZENIA_PESEL", "pesel": "44051401359", "status": "brak_wpisu"})
        assert odp.status_code == 200 and odp.json()[0]["zapytanie"] == "*******1359"
        assert klient.get("/api/sprawy/abc123/sprawdzenia").json()[0]["status"] == "brak_wpisu"
        assert "44051401359" not in (tmp_path / "abc123" / "sprawdzenia.json").read_text()
