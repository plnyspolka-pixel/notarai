"""Umawianie wizyt: zgloszenia ze strony, routing do kancelarii notarai,
panel kancelarii i admina. Baza i rejestr z atrap, e-mail nie wychodzi.
Dane fikcyjne."""
import logging
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import app as aplikacja
import autoryzacja
import config
import kalendarz
import wizyty

BAZA = {
    "miejscowosci": [{"slug": "lublin", "nazwa": "Lublin", "izba": "Lublinie", "liczba": 2},
                     {"slug": "pulawy", "nazwa": "Puławy", "izba": "Lublinie", "liczba": 1}],
    "kancelarie": [
        {"id": 1, "slug": "lublin", "miejscowosc": "Lublin", "nazwa": "Kancelaria Notarialna Anna Testowa",
         "email": "anna@kancelaria-testowa.test", "telefony": ["81 000 00 00"], "adres": "ul. Próbna 1, Lublin"},
        {"id": 2, "slug": "lublin", "miejscowosc": "Lublin", "nazwa": "Kancelaria Notarialna Jan Obcy",
         "email": "jan@obcy.test", "telefony": [], "adres": ""},
        {"id": 3, "slug": "pulawy", "miejscowosc": "Puławy", "nazwa": "Kancelaria Notarialna Ewa Bez-Maila",
         "email": "", "telefony": ["81 111 11 11"], "adres": "ul. Druga 2, Puławy"},
    ],
}
# "lokalna" = kancelaria biezaca w trybie lokalnym, wiec jej zapytania widac bez logowania.
REJESTR = {"skrot-a": {"id": "lokalna", "nazwa": "Kancelaria Testowa", "aktywna": True,
                       "zespol": [{"email": "anna@kancelaria-testowa.test", "rola": "wlasciciel"},
                                  {"email": "asystent@kancelaria-testowa.test", "rola": "pracownik"}]}}

ZGLOSZENIE = {"imie": "Zenobiusz", "telefon": "600 700 800", "email": "zenobiusz@klient.test",
              "czynnosc": "zakup mieszkania", "wartosc": 450000, "termin": "przyszły tydzień po 16",
              "wiadomosc": "Kupuję na kredyt.", "zgoda": True, "kancelaria": 1,
              "parametry": {"czynnosci": [{"rodzaj": "sprzedaz_lokalu", "wartosc": 450000}]},
              "zrodlo": "kalkulator"}


@pytest.fixture
def klient(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DANE", tmp_path)
    monkeypatch.setattr(autoryzacja, "_wczytaj_rejestr", lambda: REJESTR)
    monkeypatch.setattr(autoryzacja, "ADMIN_TOKEN", "sekret-admina")
    monkeypatch.setattr(wizyty, "NADAWCA", "notarai <zapytania@notarai.test>")
    monkeypatch.setattr(wizyty, "KOPIA", "zapytania@notarai.test")
    wizyty._ustaw_baze(BAZA)
    wizyty.limit_zgloszen.wyczysc()
    wyslane = []
    monkeypatch.setattr(wizyty, "_wyslij_email", lambda do, temat, tresc: wyslane.append((do, temat, tresc)) or True)
    k = TestClient(aplikacja.app)
    k.wyslane = wyslane
    yield k
    wizyty._ustaw_baze(None)


ADMIN = {"Authorization": "Bearer sekret-admina"}


class TestZgloszenie:
    def test_do_kancelarii_notarai(self, klient):
        odp = klient.post("/api/wizyty/zgloszenie", json=ZGLOSZENIE)
        assert odp.status_code == 201, odp.text
        dane = odp.json()
        assert dane["notarai"] is True and "korzysta z notarai" in dane["komunikat"]
        # e-maile: do wlasciciela kancelarii, kopia do notarai, potwierdzenie do klienta
        adresaci = [tuple(w[0]) for w in klient.wyslane]
        assert adresaci == [("anna@kancelaria-testowa.test",), ("zapytania@notarai.test",), ("zenobiusz@klient.test",)]
        tresc = klient.wyslane[0][2]
        assert "Zenobiusz" in tresc and "600 700 800" in tresc and "RAZEM" in tresc and "450" in tresc
        zapis = wizyty._wczytaj()["zgloszenia"][0]
        assert zapis["kancelaria_id"] == "lokalna" and zapis["status"] == "nowa"
        assert zapis["kalkulacja"]["razem"] > 0 and zapis["wartosc"] == 450000.0
        assert zapis["powiadomiono"] == {"kancelaria": True, "notarai": True, "klient": True}

    def test_do_kancelarii_spoza_notarai(self, klient):
        odp = klient.post("/api/wizyty/zgloszenie", json={**ZGLOSZENIE, "kancelaria": 2, "email": ""})
        assert odp.status_code == 201
        assert odp.json()["notarai"] is False and "Przekażemy" in odp.json()["komunikat"]
        assert [tuple(w[0]) for w in klient.wyslane] == [("zapytania@notarai.test",)]
        assert "NIE korzysta" in klient.wyslane[0][2]

    def test_tylko_miejscowosc(self, klient):
        odp = klient.post("/api/wizyty/zgloszenie", json={**ZGLOSZENIE, "kancelaria": None, "miejscowosc": "pulawy"})
        assert odp.status_code == 201 and "Puławy" in odp.json()["komunikat"]

    def test_walidacja(self, klient):
        assert klient.post("/api/wizyty/zgloszenie", json={**ZGLOSZENIE, "zgoda": False}).status_code == 400
        assert klient.post("/api/wizyty/zgloszenie", json={**ZGLOSZENIE, "telefon": "", "email": ""}).status_code == 400
        assert klient.post("/api/wizyty/zgloszenie", json={**ZGLOSZENIE, "kancelaria": 999}).status_code == 400
        assert klient.post("/api/wizyty/zgloszenie", json={**ZGLOSZENIE, "kancelaria": None, "miejscowosc": "nigdzie"}).status_code == 400
        assert klient.post("/api/wizyty/zgloszenie", json={**ZGLOSZENIE, "imie": "A"}).status_code == 400
        assert klient.post("/api/wizyty/zgloszenie", json={**ZGLOSZENIE, "email": "zle"}).status_code == 400
        assert klient.post("/api/wizyty/zgloszenie", json={**ZGLOSZENIE, "telefon": "12"}).status_code == 400
        assert wizyty._wczytaj()["zgloszenia"] == []

    def test_pulapka_i_limit(self, klient, monkeypatch):
        odp = klient.post("/api/wizyty/zgloszenie", json={**ZGLOSZENIE, "strona": "http://spam"})
        assert odp.status_code == 201 and odp.json()["id"] == "" and wizyty._wczytaj()["zgloszenia"] == []
        monkeypatch.setattr(wizyty, "limit_zgloszen", wizyty.Limit(1, 100))
        assert klient.post("/api/wizyty/zgloszenie", json=ZGLOSZENIE).status_code == 201
        assert klient.post("/api/wizyty/zgloszenie", json=ZGLOSZENIE).status_code == 429

    def test_dane_klienta_nie_w_logach(self, klient, caplog):
        caplog.set_level(logging.INFO)
        klient.post("/api/wizyty/zgloszenie", json=ZGLOSZENIE)
        assert "Zenobiusz" not in caplog.text and "600 700 800" not in caplog.text and "klient.test" not in caplog.text
        assert "wizyty: zgloszenie" in caplog.text

    def test_kancelarie_notarai_w_miejscowosci(self, klient):
        assert klient.get("/api/wizyty/kancelarie", params={"miejscowosc": "lublin"}).json() == {"miejscowosc": "lublin", "notarai": [1]}
        assert klient.get("/api/wizyty/kancelarie", params={"miejscowosc": "pulawy"}).json()["notarai"] == []

    def test_cors_dla_wizyt(self, klient):
        odp = klient.options("/api/wizyty/zgloszenie", headers={"Origin": "https://notarai.pl",
                                                                "Access-Control-Request-Method": "POST"})
        assert odp.status_code == 204 and odp.headers["access-control-allow-origin"] == "https://notarai.pl"

    def test_stare_zgloszenia_znikaja(self, klient, monkeypatch):
        klient.post("/api/wizyty/zgloszenie", json=ZGLOSZENIE)
        dawno = (datetime.now() - timedelta(days=wizyty.RETENCJA_DNI + 1)).isoformat(timespec="seconds")

        def postarz(d):
            d["zgloszenia"][0]["utworzono"] = dawno
        wizyty._w_obszarze_admina(wizyty.magazyn.zmien_plik_kancelarii, wizyty.PLIK, postarz, wizyty._pusty())
        klient.post("/api/wizyty/zgloszenie", json={**ZGLOSZENIE, "kancelaria": 2})
        assert len(wizyty._wczytaj()["zgloszenia"]) == 1


class TestZapytaniaKancelarii:
    def test_lista_tylko_swoje(self, klient):
        klient.post("/api/wizyty/zgloszenie", json=ZGLOSZENIE)
        klient.post("/api/wizyty/zgloszenie", json={**ZGLOSZENIE, "kancelaria": 2})
        lista = klient.get("/api/zapytania").json()
        assert len(lista) == 1 and lista[0]["kancelaria_id"] == "lokalna" and lista[0]["klient"]["imie"] == "Zenobiusz"

    def test_umowienie_tworzy_wpis_w_kalendarzu(self, klient):
        ident = klient.post("/api/wizyty/zgloszenie", json=ZGLOSZENIE).json()["id"]
        assert klient.get("/api/zapytania").json()[0]["id"] == ident
        odp = klient.put(f"/api/zapytania/{ident}", json={"status": "umowiona", "data": "2026-12-01", "godzina": "10:00", "uwagi": "potwierdzone telefonicznie"})
        assert odp.status_code == 200, odp.text
        assert odp.json()["status"] == "umowiona" and odp.json()["kalendarz"]["data"] == "2026-12-01"
        wpisy = kalendarz.lista()
        assert len(wpisy) == 1 and wpisy[0]["rodzaj"] == "sprzedaż" and wpisy[0]["telefony"][0]["numer"] == "600 700 800"
        assert "Zenobiusz" in wpisy[0]["tytul"]

    def test_cudze_i_zly_status(self, klient):
        klient.post("/api/wizyty/zgloszenie", json={**ZGLOSZENIE, "kancelaria": 2})
        ident = wizyty._wczytaj()["zgloszenia"][0]["id"]
        assert klient.put(f"/api/zapytania/{ident}", json={"status": "kontakt"}).status_code == 404
        assert klient.put(f"/api/zapytania/{ident}", json={"status": "dziwny"}).status_code == 400

    def test_bez_logowania_w_trybie_multi(self, monkeypatch, klient):
        monkeypatch.setattr(autoryzacja, "MULTI", True)
        assert klient.get("/api/zapytania").status_code == 401
        assert klient.post("/api/wizyty/zgloszenie", json=ZGLOSZENIE).status_code == 201


class TestAdmin:
    def test_lista_i_przekazanie(self, klient):
        klient.post("/api/wizyty/zgloszenie", json={**ZGLOSZENIE, "kancelaria": 2})
        assert klient.get("/api/admin/wizyty").status_code == 401
        dane = klient.get("/api/admin/wizyty", headers=ADMIN).json()
        assert len(dane["zgloszenia"]) == 1 and dane["zgloszenia"][0]["kancelaria_email"] == "jan@obcy.test"
        assert dane["kancelarie_notarai"] == {"lokalna": 1}
        ident = dane["zgloszenia"][0]["id"]
        klient.wyslane.clear()
        odp = klient.post(f"/api/admin/wizyty/{ident}/przekaz", headers=ADMIN)
        assert odp.status_code == 200 and odp.json()["przekazano"] and odp.json()["status"] == "kontakt"
        assert klient.wyslane[0][0] == ["jan@obcy.test"] and "notarai.pl to asystent" in klient.wyslane[0][2]

    def test_przekazanie_bez_adresu_i_bez_nadawcy(self, klient, monkeypatch):
        klient.post("/api/wizyty/zgloszenie", json={**ZGLOSZENIE, "kancelaria": 3})
        ident = wizyty._wczytaj()["zgloszenia"][0]["id"]
        assert klient.post(f"/api/admin/wizyty/{ident}/przekaz", headers=ADMIN).status_code == 409
        klient.post("/api/wizyty/zgloszenie", json={**ZGLOSZENIE, "kancelaria": 2})
        ident2 = [z["id"] for z in wizyty._wczytaj()["zgloszenia"] if z["baza_id"] == 2][0]
        monkeypatch.setattr(wizyty, "NADAWCA", "")
        assert klient.post(f"/api/admin/wizyty/{ident2}/przekaz", headers=ADMIN).status_code == 503

    def test_powiazanie_kieruje_do_aplikacji(self, klient):
        odp = klient.put("/api/admin/wizyty/powiazania/2", json={"kancelaria_id": "lokalna"}, headers=ADMIN)
        assert odp.status_code == 200 and odp.json()["powiazania"] == {"2": "lokalna"}
        assert klient.get("/api/wizyty/kancelarie", params={"miejscowosc": "lublin"}).json()["notarai"] == [1, 2]
        odp = klient.post("/api/wizyty/zgloszenie", json={**ZGLOSZENIE, "kancelaria": 2})
        assert odp.json()["notarai"] is True
        klient.put("/api/admin/wizyty/powiazania/2", json={"kancelaria_id": ""}, headers=ADMIN)
        assert klient.get("/api/wizyty/kancelarie", params={"miejscowosc": "lublin"}).json()["notarai"] == [1]
        assert klient.put("/api/admin/wizyty/powiazania/999", json={"kancelaria_id": "x"}, headers=ADMIN).status_code == 404

    def test_reczne_skierowanie_i_status(self, klient):
        klient.post("/api/wizyty/zgloszenie", json={**ZGLOSZENIE, "kancelaria": 2})
        ident = wizyty._wczytaj()["zgloszenia"][0]["id"]
        klient.wyslane.clear()
        odp = klient.put(f"/api/admin/wizyty/{ident}", json={"kancelaria_id": "lokalna", "uwagi": "kancelaria dołączyła"}, headers=ADMIN)
        assert odp.status_code == 200 and odp.json()["kancelaria_id"] == "lokalna"
        assert klient.wyslane and klient.wyslane[0][0] == ["anna@kancelaria-testowa.test"]
        assert klient.get("/api/zapytania").json()[0]["id"] == ident
        assert klient.put(f"/api/admin/wizyty/{ident}", json={"status": "zamknieta"}, headers=ADMIN).json()["status"] == "zamknieta"
        assert klient.put(f"/api/admin/wizyty/{ident}", json={"status": "x"}, headers=ADMIN).status_code == 400


class TestBaza:
    def test_prawdziwa_baza_sie_laduje(self):
        wizyty._ustaw_baze(None)
        b = wizyty.baza()
        assert len(b["kancelarie"]) > 3000 and "lublin" in b["miejscowosci"]
        assert all("@" not in k["nazwa"] for k in b["kancelarie"].values())
        wizyty._ustaw_baze(None)
