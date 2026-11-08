"""Rezerwacja online dla klientow, przypomnienia, odwolanie, filtr, strona
przejrzystosci, audyt kolejki i mapa z calego wykazu. Dane fikcyjne,
e-mail nie wychodzi, geokoder bez sieci."""
import json
from collections import Counter
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import app as aplikacja
import autoryzacja
import config
import magazyn
import notariusze
import rekomendacje
import rezerwacje_hurtowe as hurt
import rezerwacje_klientow as rk
import wizyty
from test_wizyty import BAZA, ZGLOSZENIE

REJESTR = {"skrot-a": {"id": "lokalna", "nazwa": "Kancelaria Testowa", "aktywna": True, "przechowywanie": "chmura",
                       "umowa": {"zaakceptowano": "2026-11-01"}, "na_mapie": True,
                       "dane": {"notariusze": "Anna Testowa", "adres": "ul. Próbna 1, Lublin"},
                       "mapa": {"adres": "ul. Próbna 1, Lublin", "lat": 51.25, "lon": 22.57},
                       "zespol": [{"email": "anna@kancelaria-testowa.test", "rola": "wlasciciel"}]}}
POLITYKA = {"wlaczone": False, "klienci": True, "miasto": "Lublin", "adres": "ul. Próbna 1, Lublin",
            "godziny": {str(i): ["09:00", "12:00"] for i in range(7)}, "czas_minut": 60,
            "wyprzedzenie_godzin": 1, "max_dni": 30}
ADMIN = {"Authorization": "Bearer sekret-admina"}


@pytest.fixture
def klient(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DANE", tmp_path)
    monkeypatch.setattr(autoryzacja, "_wczytaj_rejestr", lambda: REJESTR)
    monkeypatch.setattr(autoryzacja, "ADMIN_TOKEN", "sekret-admina")
    monkeypatch.setattr(wizyty, "NADAWCA", "notarai <zapytania@notarai.test>")
    monkeypatch.setattr(wizyty, "KOPIA", "")
    monkeypatch.setattr(wizyty, "limit_zgloszen", wizyty.Limit(100, 1000))
    monkeypatch.setattr(notariusze, "PLIK_POLOZEN", tmp_path / "polozenia.json")
    wizyty._ustaw_baze(BAZA)
    with hurt._WBiurze("lokalna"):
        magazyn.zmien_plik_kancelarii(hurt.PLIK_USTAWIEN, lambda a: a.update(POLITYKA), {})
    wyslane = []
    monkeypatch.setattr(wizyty, "_wyslij_email", lambda do, temat, tresc: wyslane.append((do, temat, tresc)) or True)
    k = TestClient(aplikacja.app)
    k.wyslane = wyslane
    yield k
    wizyty._ustaw_baze(None)


def _jutro() -> str:
    return (datetime.now(hurt.STREFA) + timedelta(days=1)).date().isoformat()


def _rezerwuj(klient, **zmiany):
    return klient.post("/api/wizyty/rezerwacja", json={**ZGLOSZENIE, "data": _jutro(), "godzina": "10:00", **zmiany})


class TestTerminy:
    def test_wolne_godziny_tylko_dla_kancelarii_z_wlaczona_rezerwacja(self, klient):
        d = klient.get("/api/wizyty/terminy", params={"kancelaria": 1, "od": _jutro(), "dni": 1}).json()
        assert d["online"] and [t["godzina"] for t in d["terminy"]] == ["09:00", "09:30", "10:00", "10:30", "11:00"]
        assert klient.get("/api/wizyty/terminy", params={"kancelaria": 2}).json() == {"online": False, "terminy": []}

    def test_bez_przelacznika_klienci_nie_ma_rezerwacji(self, klient):
        with hurt._WBiurze("lokalna"):
            magazyn.zmien_plik_kancelarii(hurt.PLIK_USTAWIEN, lambda a: a.update(klienci=False), {})
        assert klient.get("/api/wizyty/terminy", params={"kancelaria": 1}).json()["online"] is False

    def test_bez_umowy_powierzenia_nie_ma_rezerwacji(self, klient, monkeypatch):
        monkeypatch.setattr(autoryzacja, "umowa_zawarta", lambda id_k: False)
        assert klient.get("/api/wizyty/terminy", params={"kancelaria": 1}).json()["online"] is False


class TestRezerwacja:
    def test_rezerwacja_zajmuje_godzine_w_kalendarzu(self, klient):
        odp = _rezerwuj(klient)
        assert odp.status_code == 201, odp.text
        assert odp.json()["koniec"] == "11:00"
        with hurt._WBiurze("lokalna"):
            wpis = [w for w in __import__("kalendarz").lista() if w.get("zrodlo") == "klient"][0]
        assert wpis["godzina"] == "10:00" and wpis["rodzaj"] == "sprzedaż" and wpis["status"] == "potwierdzona"
        # zajete 10:00-11:00 znika z wolnych; 09:30 tez (nachodzi)
        wolne = [t["godzina"] for t in klient.get("/api/wizyty/terminy", params={"kancelaria": 1, "od": _jutro(), "dni": 1}).json()["terminy"]]
        assert wolne == ["09:00", "11:00"]
        z = wizyty._wczytaj()["zgloszenia"][0]
        assert z["status"] == "umowiona" and z["kancelaria_id"] == "lokalna" and len(z["token"]) == 64
        assert [w[0] for w in klient.wyslane] == [["anna@kancelaria-testowa.test"], ["zenobiusz@klient.test"]]
        assert "/wizyta/odwolaj/#" in klient.wyslane[1][2]

    def test_ta_sama_godzina_dwa_razy(self, klient):
        assert _rezerwuj(klient).status_code == 201
        assert _rezerwuj(klient, email="inny@klient.test").status_code == 409

    def test_wymaga_emaila_i_kancelarii_online(self, klient):
        assert _rezerwuj(klient, email="").status_code == 400
        assert _rezerwuj(klient, kancelaria=2).status_code == 409
        assert _rezerwuj(klient, kancelaria=None).status_code == 400
        assert _rezerwuj(klient, godzina="13:00").status_code == 409

    def test_odwolanie_zwalnia_termin(self, klient):
        _rezerwuj(klient)
        token = klient.wyslane[1][2].split("/wizyta/odwolaj/#")[1].split()[0]
        assert klient.post("/api/wizyty/rezerwacja/odwolaj", json={"token": "x" * 32}).status_code == 404
        odp = klient.post("/api/wizyty/rezerwacja/odwolaj", json={"token": token})
        assert odp.status_code == 200, odp.text
        assert klient.post("/api/wizyty/rezerwacja/odwolaj", json={"token": token}).status_code == 409
        wolne = klient.get("/api/wizyty/terminy", params={"kancelaria": 1, "od": _jutro(), "dni": 1}).json()["terminy"]
        assert "10:00" in [t["godzina"] for t in wolne]

    def test_dane_klienta_nie_w_logach(self, klient, caplog):
        import logging
        caplog.set_level(logging.INFO)
        _rezerwuj(klient)
        assert "Zenobiusz" not in caplog.text and "klient.test" not in caplog.text


class TestPrzypomnienia:
    def test_raz_i_tylko_jutrzejsze(self, klient):
        _rezerwuj(klient)
        klient.wyslane.clear()
        assert klient.post("/api/admin/wizyty/przypomnienia").status_code == 401
        wynik = klient.post("/api/admin/wizyty/przypomnienia", headers=ADMIN).json()
        assert wynik["wyslane"] == 1 and "Jutro wizyta" in klient.wyslane[0][1]
        assert klient.post("/api/admin/wizyty/przypomnienia", headers=ADMIN).json()["wyslane"] == 0
        # pojutrze juz nic
        assert rk.przypomnij(datetime.now() + timedelta(days=1))["do_wyslania"] == 0


class TestListaIFiltr:
    def test_rezerwacja_nie_zmienia_kolejnosci_a_filtr_tylko_zaweza(self, klient):
        d = klient.get("/api/wizyty/kancelarie", params={"miejscowosc": "lublin"}).json()
        assert d["rezerwacja"] == [1] and sorted(d["kolejnosc"]) == [1, 2]
        neutralna = [k["id"] for k in rekomendacje.kolejnosc([BAZA["kancelarie"][0], BAZA["kancelarie"][1]], "lublin")]
        assert d["kolejnosc"] == neutralna
        f = klient.get("/api/wizyty/kancelarie", params={"miejscowosc": "lublin", "tylko_online": True}).json()
        assert f["kolejnosc"] == [1] and f["filtr"] == "tylko_online"


class TestPrzejrzystosc:
    def test_kolejnosc_do_przeliczenia_i_przydzialy(self, klient):
        for _ in range(4):
            klient.post("/api/wizyty/zgloszenie", json={**ZGLOSZENIE, "kancelaria": None, "miejscowosc": "lublin"})
        d = klient.get("/api/wizyty/przejrzystosc", params={"miejscowosc": "lublin", "data": "2026-11-08"}).json()
        assert d["wersja"] == rekomendacje.WERSJA and d["data"] == "2026-11-08"
        import hashlib
        for k in d["kolejnosc"]:
            tekst = f"notarai|{d['wersja']}|{d['data']}|lublin|{k['id']}"
            assert int(k["los"]) == int.from_bytes(hashlib.sha256(tekst.encode()).digest()[:8], "big")
        assert [k["liczba"] for k in d["przydzialy"]] == [2, 2]
        tekst = json.dumps(d, ensure_ascii=False)
        assert "Zenobiusz" not in tekst and "600 700 800" not in tekst
        assert klient.get("/api/wizyty/przejrzystosc", params={"miejscowosc": "nigdzie"}).status_code == 404

    def test_audyt_rownosci(self, klient):
        for _ in range(5):
            klient.post("/api/wizyty/zgloszenie", json={**ZGLOSZENIE, "kancelaria": None, "miejscowosc": "lublin"})
        d = klient.get("/api/admin/wizyty/rownosc", headers=ADMIN).json()
        lublin = next(m for m in d["miejscowosci"] if m["miejscowosc"] == "lublin")
        assert lublin["przydzialy"] == 5 and lublin["roznica"] == 1 and d["naruszenia"] == []

        def ingerencja(dane):   # ktos recznie dopisal przydzialy jednej kancelarii
            for _ in range(3):
                dane["zgloszenia"].append({**dane["zgloszenia"][0], "baza_id": 1, "id": "x"})
        wizyty._zmien(ingerencja)
        assert klient.get("/api/admin/wizyty/rownosc", headers=ADMIN).json()["naruszenia"][0]["miejscowosc"] == "lublin"

    def test_strony_publiczne_sie_generuja(self):
        from seo import przejrzystosc
        zasady = przejrzystosc.strona_zasad()
        assert "crypto.subtle" in zasady and rekomendacje.WERSJA in zasady and "/api/wizyty/przejrzystosc" in zasady
        assert 'name="robots" content="noindex"' in przejrzystosc.strona_odwolania()


class TestMapaZWykazu:
    def test_bez_pliku_polozen_jak_dotad(self, klient):
        lista = klient.get("/api/notariusze").json()["kancelarie"]
        assert [k["nazwa"] for k in lista] == ["Kancelaria Testowa"]

    def test_caly_wykaz_a_notarai_tylko_ze_znacznikiem(self, klient, tmp_path):
        (tmp_path / "polozenia.json").write_text(json.dumps({"polozenia": {
            "1": {"adres": "x", "lat": 51.25, "lon": 22.57}, "2": {"adres": "y", "lat": 51.24, "lon": 22.56},
            "3": {"adres": "z", "lat": None, "blad": "nieznany"}}}), "utf-8")
        lista = klient.get("/api/notariusze", params={"lat": 51.25, "lon": 22.57}).json()["kancelarie"]
        assert sorted(k["id"] for k in lista) == [1, 2], "z wykazu, bez dubla z rejestru notarai"
        assert {k["id"]: k["online"] for k in lista} == {1: True, 2: False}
        # obie w tym samym pasmie odleglosci: kolejnosc z rotacji, nie z online
        pierwsze = Counter()
        from datetime import date
        for n in range(200):
            dzien = date(2026, 1, 1) + timedelta(days=n)
            pierwsze[rekomendacje.kolejnosc(lista, "mapa", dzien, klucz_id="nazwa")[0]["id"]] += 1
        assert 70 < pierwsze[1] < 130
        assert "@" not in json.dumps(lista)


class TestGeokodowanieWykazu:
    def test_porcjami_i_wznawialnie(self, tmp_path, monkeypatch):
        from seo import geokoduj_wykaz as g
        baza = tmp_path / "baza.json"
        baza.write_text(json.dumps(BAZA), "utf-8")
        cel = tmp_path / "poz.json"
        zapytania = []
        monkeypatch.setattr(notariusze, "geokoduj", lambda a: zapytania.append(a) or (
            {"lat": 51.0, "lon": 22.0, "dokladnosc": "adres"} if "Próbna" in a else None))
        w = g.uruchom(limit=1, baza=baza, cel=cel, wypisz=lambda *_: None)
        assert w["ustalono"] == 1 and len(zapytania) == 1
        w = g.uruchom(baza=baza, cel=cel, wypisz=lambda *_: None)
        assert len(zapytania) == 2 and w["na_mapie"] == 1 and w["nieznane"] == 1   # id 2 bez adresu pominiete
        g.uruchom(baza=baza, cel=cel, wypisz=lambda *_: None)
        assert len(zapytania) == 2, "nic od nowa"
        g.uruchom(ponow_bledy=True, baza=baza, cel=cel, wypisz=lambda *_: None)
        assert len(zapytania) == 3


def test_petla_przypomnien_tylko_na_zyczenie(monkeypatch):
    monkeypatch.delenv("PIECZAPP_PRZYPOMNIENIA", raising=False)
    assert rk.uruchom_przypomnienia() is None
    monkeypatch.setenv("PIECZAPP_PRZYPOMNIENIA", "true")
    stop = rk.uruchom_przypomnienia()
    assert stop is not None
    stop.set()
