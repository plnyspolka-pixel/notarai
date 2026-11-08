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
        assert dane["notarai"] is True and "dotarło do kancelarii" in dane["komunikat"]
        # e-maile: do wlasciciela kancelarii, kopia do notarai, potwierdzenie do klienta
        adresaci = [tuple(w[0]) for w in klient.wyslane]
        assert adresaci == [("anna@kancelaria-testowa.test",), ("zapytania@notarai.test",), ("zenobiusz@klient.test",)]
        tresc = klient.wyslane[0][2]
        assert "Zenobiusz" in tresc and "600 700 800" in tresc and "RAZEM" in tresc and "450" in tresc
        zapis = wizyty._wczytaj()["zgloszenia"][0]
        assert zapis["kancelaria_id"] == "lokalna" and zapis["status"] == "nowa"
        assert zapis["kalkulacja"]["razem"] > 0 and zapis["wartosc"] == 450000.0
        assert zapis["powiadomiono"] == {"kancelaria": True, "notarai": True, "klient": True}

    def test_kancelaria_spoza_notarai_nie_przyjmuje_zgloszen(self, klient):
        """Neutralnosc: nie zbieramy zgloszen dla obcych kancelarii i nie przekazujemy
        ich dalej. Klient dostaje publiczne dane kontaktowe, nic nie zapisujemy."""
        odp = klient.post("/api/wizyty/zgloszenie", json={**ZGLOSZENIE, "kancelaria": 2})
        assert odp.status_code == 409
        assert "nie przyjmuje zgłoszeń online" in odp.json()["detail"] and "Jan Obcy" in odp.json()["detail"]
        assert klient.wyslane == [] and wizyty._wczytaj()["zgloszenia"] == []

    def test_bez_wyboru_kancelarii_nie_dobieramy(self, klient):
        odp = klient.post("/api/wizyty/zgloszenie", json={**ZGLOSZENIE, "kancelaria": None, "miejscowosc": "pulawy"})
        assert odp.status_code == 400 and wizyty._wczytaj()["zgloszenia"] == []

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
        klient.post("/api/wizyty/zgloszenie", json=ZGLOSZENIE)
        assert len(wizyty._wczytaj()["zgloszenia"]) == 1


class TestZapytaniaKancelarii:
    def test_lista_tylko_swoje(self, klient, monkeypatch):
        klient.post("/api/wizyty/zgloszenie", json=ZGLOSZENIE)
        monkeypatch.setattr(wizyty, "kancelarie_notarai", lambda: {1: "lokalna", 2: "inna"})
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

    def test_cudze_i_zly_status(self, klient, monkeypatch):
        monkeypatch.setattr(wizyty, "kancelarie_notarai", lambda: {2: "inna"})
        klient.post("/api/wizyty/zgloszenie", json={**ZGLOSZENIE, "kancelaria": 2})
        ident = wizyty._wczytaj()["zgloszenia"][0]["id"]
        assert klient.put(f"/api/zapytania/{ident}", json={"status": "kontakt"}).status_code == 404
        assert klient.put(f"/api/zapytania/{ident}", json={"status": "dziwny"}).status_code == 400

    def test_bez_logowania_w_trybie_multi(self, monkeypatch, klient):
        monkeypatch.setattr(autoryzacja, "MULTI", True)
        assert klient.get("/api/zapytania").status_code == 401
        assert klient.post("/api/wizyty/zgloszenie", json=ZGLOSZENIE).status_code == 201


class TestAdmin:
    def test_lista_dla_admina(self, klient):
        klient.post("/api/wizyty/zgloszenie", json=ZGLOSZENIE)
        assert klient.get("/api/admin/wizyty").status_code == 401
        dane = klient.get("/api/admin/wizyty", headers=ADMIN).json()
        assert len(dane["zgloszenia"]) == 1 and dane["kancelarie_notarai"] == {"lokalna": 1}

    def test_nie_ma_przekazywania_obcym_kancelariom(self, klient):
        klient.post("/api/wizyty/zgloszenie", json=ZGLOSZENIE)
        ident = wizyty._wczytaj()["zgloszenia"][0]["id"]
        assert klient.post(f"/api/admin/wizyty/{ident}/przekaz", headers=ADMIN).status_code in (404, 405)

    def test_powiazanie_kieruje_do_aplikacji(self, klient):
        odp = klient.put("/api/admin/wizyty/powiazania/2", json={"kancelaria_id": "lokalna"}, headers=ADMIN)
        assert odp.status_code == 200 and odp.json()["powiazania"] == {"2": "lokalna"}
        assert klient.get("/api/wizyty/kancelarie", params={"miejscowosc": "lublin"}).json()["notarai"] == [1, 2]
        odp = klient.post("/api/wizyty/zgloszenie", json={**ZGLOSZENIE, "kancelaria": 2})
        assert odp.json()["notarai"] is True
        klient.put("/api/admin/wizyty/powiazania/2", json={"kancelaria_id": ""}, headers=ADMIN)
        assert klient.get("/api/wizyty/kancelarie", params={"miejscowosc": "lublin"}).json()["notarai"] == [1]
        assert klient.put("/api/admin/wizyty/powiazania/999", json={"kancelaria_id": "x"}, headers=ADMIN).status_code == 404

    def test_przypisanie_tylko_do_wybranej_kancelarii(self, klient, monkeypatch):
        """Admin moze dopiac zgloszenie do kancelarii powiazanej z pozycja, ktora
        wybral klient (np. po zmianie powiazania), ale nie skierowac go gdzie indziej."""
        klient.post("/api/wizyty/zgloszenie", json=ZGLOSZENIE)
        ident = wizyty._wczytaj()["zgloszenia"][0]["id"]
        odp = klient.put(f"/api/admin/wizyty/{ident}", json={"kancelaria_id": "inna"}, headers=ADMIN)
        assert odp.status_code == 400
        assert wizyty._wczytaj()["zgloszenia"][0]["kancelaria_id"] == "lokalna"
        klient.wyslane.clear()
        odp = klient.put(f"/api/admin/wizyty/{ident}", json={"kancelaria_id": "lokalna", "uwagi": "ponowne powiadomienie"}, headers=ADMIN)
        assert odp.status_code == 200 and odp.json()["kancelaria_id"] == "lokalna"
        assert klient.wyslane and klient.wyslane[0][0] == ["anna@kancelaria-testowa.test"]
        assert klient.put(f"/api/admin/wizyty/{ident}", json={"status": "zamknieta"}, headers=ADMIN).json()["status"] == "zamknieta"
