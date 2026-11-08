"""EKW przez dostawce (Apify) - testy na atrapie klienta HTTP. Zero polaczen."""
import json
import logging

import pytest

import config
import ekw
import rejestry

KW = "WA4M/00160286/2"
PESEL = "44051401359"


class Odpowiedz:
    def __init__(self, status, dane=None, tekst=""):
        self.status_code, self._dane, self.text = status, dane, tekst

    def json(self):
        if self._dane is None:
            raise ValueError("brak JSON")
        return self._dane


class AtrapaKlienta:
    """Udaje api.apify.com: run-sync, odczyt zbioru, zapis ERRORS, kasowanie."""

    def __init__(self, rekordy=None, status_zadania="SUCCEEDED", kod_startu=201,
                 bledy="", komunikat=""):
        self.rekordy, self.status_zadania, self.kod_startu = rekordy, status_zadania, kod_startu
        self.bledy, self.komunikat = bledy, komunikat
        self.wywolania = []

    def post(self, sciezka, params=None, json=None):
        self.wywolania.append(("POST", sciezka, json))
        if self.kod_startu >= 400:
            return Odpowiedz(self.kod_startu, {"error": {"type": "x"}})
        return Odpowiedz(201, {"data": {"id": "run1", "status": self.status_zadania,
                                        "statusMessage": self.komunikat,
                                        "defaultDatasetId": "ds1", "defaultKeyValueStoreId": "kv1"}})

    def get(self, sciezka, params=None):
        self.wywolania.append(("GET", sciezka, None))
        if sciezka == "/datasets/ds1/items":
            return Odpowiedz(200, self.rekordy or [])
        if sciezka == "/key-value-stores/kv1/records/ERRORS":
            return Odpowiedz(200 if self.bledy else 404, None, self.bledy)
        return Odpowiedz(404, None)

    def delete(self, sciezka):
        self.wywolania.append(("DELETE", sciezka, None))
        return Odpowiedz(204, None)

    def close(self):
        self.wywolania.append(("CLOSE", "", None))


def rekord(**zmiany):
    r = {
        "kwNumber": KW, "courtCode": "WA4M",
        "courtName": "SAD REJONOWY DLA WARSZAWY-MOKOTOWA W WARSZAWIE",
        "propertyType": "NIERUCHOMOSC GRUNTOWA", "viewType": "aktualna", "success": True,
        "dzialIO": {"available": True, "empty": False, "title": "DZIAL I-O - OZNACZENIE NIERUCHOMOSCI",
                    "entries": [{"label": "Numer dzialki", "value": "1"},
                                {"label": "Obszar", "value": "0,1234 HA"}]},
        "dzialISp": {"available": True, "empty": True, "title": "DZIAL I-SP", "rawText": "BRAK WPISOW"},
        "dzialII": {"available": True, "empty": False, "title": "DZIAL II - WLASNOSC",
                    "entries": [f"Jan Testowy, PESEL {PESEL}, udzial 1/1"]},
        "dzialIII": {"available": True, "empty": True, "title": "DZIAL III", "rawText": "BRAK WPISOW"},
        "dzialIV": {"available": True, "empty": True, "title": "DZIAL IV - HIPOTEKA", "rawText": "BRAK WPISOW"},
    }
    r.update(zmiany)
    return r


@pytest.fixture(autouse=True)
def srodowisko(monkeypatch, tmp_path):
    monkeypatch.setenv("PIECZAPP_APIFY_TOKEN", "apify_api_test")
    monkeypatch.setattr(ekw, "ODSTEP_S", 0)
    monkeypatch.setattr(config, "SPRAWY", tmp_path)
    (tmp_path / "abc123").mkdir()


class TestNumer:
    def test_porzadkuje_wielkosc_liter_i_spacje(self):
        assert ekw.normalizuj_numer(" wa4m/00160286/2 ") == KW

    def test_zla_cyfra_kontrolna(self):
        with pytest.raises(ValueError):
            ekw.normalizuj_numer("WA4M/00160286/3")

    def test_zly_format(self):
        with pytest.raises(ValueError):
            ekw.normalizuj_numer("WA4M-00160286-2")


class TestPobierz:
    def test_pelna_ksiega(self):
        k = AtrapaKlienta([rekord()])
        ksiega = ekw.pobierz(KW, k)
        assert ksiega["numer_kw"] == KW and ksiega["kod_sadu"] == "WA4M"
        assert [d["oznaczenie"] for d in ksiega["dzialy"]] == ["I-O", "I-Sp", "II", "III", "IV"]
        io, isp, ii = ksiega["dzialy"][0], ksiega["dzialy"][1], ksiega["dzialy"][2]
        assert io["tekst"] == "Numer dzialki: 1\nObszar: 0,1234 HA" and not io["pusty"]
        assert isp["pusty"] and isp["tekst"] == "BRAK WPISÓW"
        assert PESEL in ii["tekst"]

    def test_wysyla_jeden_numer_widok_aktualny(self):
        k = AtrapaKlienta([rekord()])
        ekw.pobierz(KW, k)
        metoda, sciezka, cialo = k.wywolania[0]
        assert (metoda, sciezka) == ("POST", f"/acts/{ekw.AKTOR}/run-sync")
        assert cialo["kwNumbers"] == [KW] and cialo["viewType"] == "aktualna"
        assert cialo["includeRawHtml"] is False

    def test_kasuje_dane_u_dostawcy_takze_po_bledzie(self):
        k = AtrapaKlienta([rekord(kwNumber="WA4M/00000001/1")])
        with pytest.raises(ekw.BladEKW):
            ekw.pobierz(KW, k)
        usuniete = [s for m, s, _ in k.wywolania if m == "DELETE"]
        assert usuniete == ["/datasets/ds1", "/key-value-stores/kv1"]
        # Klient podany z zewnatrz nie jest zamykany - zamyka go wlasciciel.
        assert ("CLOSE", "", None) not in k.wywolania

    def test_bez_tokenu(self, monkeypatch):
        monkeypatch.delenv("PIECZAPP_APIFY_TOKEN")
        assert not ekw.dostepne()
        with pytest.raises(ekw.BladEKW) as blad:
            ekw.pobierz(KW, AtrapaKlienta([rekord()]))
        assert blad.value.kod == "brak_tokenu"

    def test_odrzucony_token(self):
        with pytest.raises(ekw.BladEKW) as blad:
            ekw.pobierz(KW, AtrapaKlienta(kod_startu=401))
        assert blad.value.kod == "blad_tokenu"

    def test_brak_srodkow(self):
        with pytest.raises(ekw.BladEKW) as blad:
            ekw.pobierz(KW, AtrapaKlienta(kod_startu=402))
        assert blad.value.kod == "limit"

    def test_ksiegi_nie_ma_w_rejestrze(self):
        k = AtrapaKlienta([], status_zadania="FAILED", bledy=json.dumps(
            [{"kwNumber": KW, "reason": "KW not found in registry"}]))
        with pytest.raises(ekw.BladEKW) as blad:
            ekw.pobierz(KW, k)
        assert blad.value.kod == "nie_znaleziono"

    def test_pusty_wynik_bez_wyjasnienia_to_niedostepny(self):
        with pytest.raises(ekw.BladEKW) as blad:
            ekw.pobierz(KW, AtrapaKlienta([], status_zadania="FAILED"))
        assert blad.value.kod == "niedostepny" and "FAILED" in str(blad.value)

    def test_limit_bezplatnego_planu(self):
        k = AtrapaKlienta([], komunikat="Free-plan preview allowance of 25 KW numbers reached")
        with pytest.raises(ekw.BladEKW) as blad:
            ekw.pobierz(KW, k)
        assert blad.value.kod == "limit"

    def test_dzial_nieodczytany_odrzuca_ksiege(self):
        k = AtrapaKlienta([rekord(dzialIV={"available": False})])
        with pytest.raises(ekw.BladEKW) as blad:
            ekw.pobierz(KW, k)
        assert blad.value.kod == "niepelny" and "IV" in str(blad.value)

    def test_dzial_bez_tresci_i_bez_brak_wpisow_odrzuca_ksiege(self):
        k = AtrapaKlienta([rekord(dzialIII={"available": True, "empty": False, "entries": []})])
        with pytest.raises(ekw.BladEKW) as blad:
            ekw.pobierz(KW, k)
        assert blad.value.kod == "niepelny"

    def test_inny_widok_niz_aktualna(self):
        with pytest.raises(ekw.BladEKW):
            ekw.pobierz(KW, AtrapaKlienta([rekord(viewType="zupelna")]))

    def test_logi_bez_numeru_kw_i_pesel(self, caplog):
        with caplog.at_level(logging.DEBUG, logger="pieczapp.ekw"):
            ekw.pobierz(KW, AtrapaKlienta([rekord()]))
            with pytest.raises(ekw.BladEKW):
                ekw.pobierz(KW, AtrapaKlienta([], status_zadania="FAILED"))
        assert "00160286" not in caplog.text and PESEL not in caplog.text


class TestTekstIPodsumowanie:
    def test_tekst_jak_wydruk(self):
        ksiega = ekw.z_rekordu(rekord(), KW)
        tekst = ekw.do_tekstu(ksiega)
        assert tekst.startswith(f"KSIĘGA WIECZYSTA {KW}\n")
        assert "DZIAL II - WLASNOSC\nJan Testowy" in tekst
        assert "DZIAL IV - HIPOTEKA\nBRAK WPISÓW" in tekst
        assert "nie jest odpis" in tekst

    def test_bez_obciazen(self):
        status, opis = ekw.podsumowanie(ekw.z_rekordu(rekord(), KW))
        assert status == "brak_wpisu" and "dz. IV: brak wpisów" in opis and PESEL not in opis

    def test_hipoteka_to_wpis(self):
        hipoteka = {"available": True, "empty": False, "title": "DZIAL IV",
                    "entries": [{"label": "Suma", "value": "300 000 PLN"}]}
        status, opis = ekw.podsumowanie(ekw.z_rekordu(rekord(dzialIV=hipoteka), KW))
        assert status == "wpis" and "dz. IV: wpisy" in opis


class TestZapis:
    def test_pliki_i_slad(self, tmp_path):
        ksiega = ekw.z_rekordu(rekord(), KW)
        plik = ekw.zapisz("abc123", ksiega)
        katalog = tmp_path / "abc123" / "ksiegi"
        assert plik == katalog / "WA4M_00160286_2.json"
        assert (katalog / "WA4M_00160286_2.txt").read_text("utf-8").startswith("KSIĘGA WIECZYSTA")
        wpisy = rejestry.wczytaj_sprawdzenia("abc123")
        assert len(wpisy) == 1 and wpisy[0]["rejestr"] == "EKW" and wpisy[0]["zapytanie"] == KW
        assert wpisy[0]["status"] == "brak_wpisu" and PESEL not in json.dumps(wpisy)

    def test_wczytaj_od_najnowszej(self):
        starsza = ekw.z_rekordu(rekord(kwNumber="WA4M/00000001/1"), "WA4M/00000001/1")
        starsza["pobrano"] = "2026-01-01T10:00:00"
        ekw.zapisz("abc123", starsza)
        ekw.zapisz("abc123", ekw.z_rekordu(rekord(), KW))
        assert [k["numer_kw"] for k in ekw.wczytaj("abc123")] == [KW, "WA4M/00000001/1"]
        assert ekw.wczytaj("nieistniejaca") == []

    def test_wynik_bledu(self):
        w = ekw.wynik_bledu(KW, ekw.BladEKW("niedostepny", "Portal EKW nie odpowiedzial"))
        assert w.rejestr == "EKW" and w.status == "niedostepny" and w.zapytanie == KW
        assert ekw.wynik_bledu(KW, ekw.BladEKW("nie_znaleziono", "x")).status == "blad"


@pytest.fixture
def klient_http(monkeypatch):
    from fastapi.testclient import TestClient
    import app as aplikacja
    return TestClient(aplikacja.app), aplikacja


class TestEndpointy:
    def test_ustawienia_mowia_o_ekw(self, klient_http, monkeypatch):
        klient, _ = klient_http
        assert klient.get("/api/ustawienia").json()["ekw"] is True
        monkeypatch.delenv("PIECZAPP_APIFY_TOKEN")
        assert klient.get("/api/ustawienia").json()["ekw"] is False

    def test_bez_tokenu_409(self, klient_http, monkeypatch):
        klient, _ = klient_http
        monkeypatch.delenv("PIECZAPP_APIFY_TOKEN")
        odp = klient.post("/api/sprawy/abc123/ekw", json={"numer_kw": KW, "potwierdzam": True})
        assert odp.status_code == 409 and "APIFY" in odp.json()["detail"]

    def test_bez_potwierdzenia_400(self, klient_http):
        klient, _ = klient_http
        assert klient.post("/api/sprawy/abc123/ekw", json={"numer_kw": KW}).status_code == 400

    def test_zly_numer_400(self, klient_http):
        klient, _ = klient_http
        odp = klient.post("/api/sprawy/abc123/ekw", json={"numer_kw": "WA4M/00160286/3", "potwierdzam": True})
        assert odp.status_code == 400 and "kontroln" in odp.json()["detail"]

    def test_nieznana_sprawa_404(self, klient_http):
        klient, _ = klient_http
        odp = klient.post("/api/sprawy/brak999/ekw", json={"numer_kw": KW, "potwierdzam": True})
        assert odp.status_code == 404

    def test_pobranie_zapisuje_ksiege_i_slad(self, klient_http, monkeypatch, tmp_path):
        klient, _ = klient_http
        monkeypatch.setattr(ekw, "pobierz", lambda numer, klient=None: ekw.z_rekordu(rekord(), numer))
        odp = klient.post("/api/sprawy/abc123/ekw", json={"numer_kw": " wa4m/00160286/2", "potwierdzam": True})
        assert odp.status_code == 200
        dane = odp.json()
        assert dane["ksiega"]["numer_kw"] == KW and dane["sprawdzenia"][0]["rejestr"] == "EKW"
        assert (tmp_path / "abc123" / "ksiegi" / "WA4M_00160286_2.txt").exists()
        lista = klient.get("/api/sprawy/abc123/ksiegi").json()
        assert len(lista) == 1 and lista[0]["numer_kw"] == KW

    def test_blad_dostawcy_zostaje_w_sladzie(self, klient_http, monkeypatch):
        klient, _ = klient_http

        def pada(numer, klient=None):
            raise ekw.BladEKW("niedostepny", "Portal EKW nie odpowiedzial w czasie")
        monkeypatch.setattr(ekw, "pobierz", pada)
        odp = klient.post("/api/sprawy/abc123/ekw", json={"numer_kw": KW, "potwierdzam": True})
        assert odp.status_code == 502
        wpisy = klient.get("/api/sprawy/abc123/sprawdzenia").json()
        assert wpisy[0]["rejestr"] == "EKW" and wpisy[0]["status"] == "niedostepny"

    def test_ksiegi_nie_ma_404(self, klient_http, monkeypatch):
        klient, _ = klient_http

        def brak(numer, klient=None):
            raise ekw.BladEKW("nie_znaleziono", "Ksiegi o tym numerze nie ma w rejestrze")
        monkeypatch.setattr(ekw, "pobierz", brak)
        odp = klient.post("/api/sprawy/abc123/ekw", json={"numer_kw": KW, "potwierdzam": True})
        assert odp.status_code == 404

    def test_kancelaria_z_plikami_u_siebie_409(self, klient_http, monkeypatch):
        klient, _ = klient_http
        import magazyn
        monkeypatch.setattr(magazyn, "u_klienta", lambda: True)
        odp = klient.post("/api/sprawy/abc123/ekw", json={"numer_kw": KW, "potwierdzam": True})
        assert odp.status_code == 409
