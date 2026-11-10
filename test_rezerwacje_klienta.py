"""Rezerwacje klientow z aplikacji: lista kancelarii, wolne terminy, kod SMS,
rezerwacja, odwolanie, przelozenie, przypomnienia. SMS w trybie testowym
(nic nie wychodzi), e-mail podmieniony, dane fikcyjne."""
import logging
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import autoryzacja
import config
import kalendarz
import magazyn
import rezerwacje_hurtowe as h
import rezerwacje_klienta as rk
import sms
import wizyty

BAZA = {
    "miejscowosci": [{"slug": "lublin", "nazwa": "Lublin", "izba": "Lublinie", "liczba": 2},
                     {"slug": "pulawy", "nazwa": "Puławy", "izba": "Lublinie", "liczba": 1}],
    "kancelarie": [
        {"id": 1, "slug": "lublin", "miejscowosc": "Lublin", "nazwa": "Kancelaria Notarialna Anna Testowa",
         "email": "anna@kancelaria-testowa.test", "telefony": ["81 000 00 00"], "adres": "ul. Próbna 1, Lublin"},
        {"id": 2, "slug": "lublin", "miejscowosc": "Lublin", "nazwa": "Kancelaria Notarialna Jan Obcy",
         "email": "jan@obcy.test", "telefony": ["81 222 22 22"], "adres": "ul. Obca 2, Lublin"},
        {"id": 3, "slug": "pulawy", "miejscowosc": "Puławy", "nazwa": "Kancelaria Notarialna Ewa Daleka",
         "email": "", "telefony": [], "adres": ""},
    ],
}
REJESTR = {
    "x": {"id": "biuro-a", "nazwa": "Kancelaria Notarialna Anna Testowa", "aktywna": True,
          "umowa": {"zaakceptowano": "2026-11-01"}, "przechowywanie": "chmura",
          "dane": {"adres": "ul. Próbna 1, 20-001 Lublin", "notariusze": "Anna Testowa"},
          "mapa": {"adres": "ul. Próbna 1, 20-001 Lublin", "lat": 51.2465, "lon": 22.5684, "dokladnosc": "adres"},
          "zespol": [{"email": "anna@kancelaria-testowa.test", "rola": "wlasciciel"}]},
    "y": {"id": "biuro-b", "nazwa": "Kancelaria Notarialna Bez Klientow", "aktywna": True,
          "umowa": {"zaakceptowano": "2026-11-01"}, "przechowywanie": "chmura",
          "mapa": {"lat": 52.2297, "lon": 21.0122}, "zespol": []},
    "z": {"id": "biuro-c", "nazwa": "Kancelaria Lokalna", "aktywna": True,
          "umowa": {"zaakceptowano": "2026-11-01"}, "przechowywanie": "u-klienta", "zespol": []},
}
POLITYKA = {"wlaczone": False, "klienci": True, "miasto": "Lublin", "adres": "ul. Próbna 1, Lublin",
            "godziny": {str(i): ["09:00", "17:00"] for i in range(7)},
            "czas_minut": 60, "wyprzedzenie_godzin": 1, "max_dni": 60}


@pytest.fixture
def scena(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DANE", tmp_path)
    monkeypatch.setattr(autoryzacja, "ADMIN_TOKEN", "sekret-admina")
    monkeypatch.setattr(autoryzacja, "_CACHE", None)
    monkeypatch.setattr(autoryzacja, "_CACHE_S", 0.0)
    monkeypatch.setattr(sms, "TRYB", "test")
    monkeypatch.setattr(sms, "w_oknie", lambda teraz=None: True)
    monkeypatch.setattr(rk, "WEBHOOK_TOKEN", "hak-testowy")
    # Daty w testach licza sie od dzisiaj - w przeddzien swieta "jutro" nie moze byc dniem wolnym.
    monkeypatch.setattr(kalendarz, "swieto", lambda dzien: "")
    assert magazyn.TRYB == "lokalny"
    autoryzacja._zapisz_rejestr(REJESTR)
    for biuro, p in (("biuro-a", POLITYKA), ("biuro-b", {**POLITYKA, "klienci": False, "wlaczone": True}),
                     ("biuro-c", POLITYKA)):
        with h._WBiurze(biuro):
            magazyn.zmien_plik_kancelarii("rezerwacje_hurtowe", lambda aktualne, p=p: aktualne.update(p), {})
    wizyty._ustaw_baze(BAZA)
    sms.wyczysc()
    rk.limit_weryfikacji.wyczysc()
    rk.limit_rezerwacji.wyczysc()
    emaile = []
    monkeypatch.setattr(wizyty, "_wyslij_email", lambda do, temat, tresc: emaile.append((do, temat, tresc)) or True)
    monkeypatch.setattr(wizyty, "_emaile_kancelarii", lambda id_k: [f"wlasciciel@{id_k}.test"])
    import app
    klient = TestClient(app.app)
    klient.emaile = emaile
    klient.dzien = (datetime.now(h.STREFA) + timedelta(days=3)).date().isoformat()
    yield klient
    wizyty._ustaw_baze(None)
    sms.wyczysc()


ADMIN = {"Authorization": "Bearer sekret-admina"}
KLIENT = {"imie": "Jan Testowy", "telefon": "600 700 800", "email": "jan@klient.test",
          "rodzaj": "sprzedaż", "uwagi": "Kupuję na kredyt.", "zgoda": True}


def kod(klient, telefon="600 700 800"):
    odp = klient.post("/api/klient/weryfikacja", json={"telefon": telefon})
    assert odp.status_code == 201, odp.text
    return odp.json()


def rezerwuj(klient, godzina="10:00", **zmiany):
    w = kod(klient, zmiany.get("telefon", KLIENT["telefon"]))
    dane = {**KLIENT, "kancelaria": "biuro-a", "data": klient.dzien, "godzina": godzina,
            "weryfikacja": w["id"], "kod": w["kod_testowy"], **zmiany}
    return klient.post("/api/klient/rezerwacje", json=dane)


class TestKancelarie:
    def test_konfiguracja(self, scena):
        dane = scena.get("/api/klient/konfiguracja").json()
        assert dane["rezerwacje_online"] is True and "sprzedaż" in dane["rodzaje"]

    def test_miejscowosci(self, scena):
        assert [m["slug"] for m in scena.get("/api/klient/miejscowosci", params={"q": "lu"}).json()["miejscowosci"]] == ["lublin"]
        assert scena.get("/api/klient/miejscowosci", params={"q": "l"}).json()["miejscowosci"] == []

    def test_w_miescie_online_na_gorze_bez_duplikatu(self, scena):
        dane = scena.get("/api/klient/kancelarie", params={"miasto": "lublin"}).json()
        assert dane["miejscowosc"] == {"slug": "lublin", "nazwa": "Lublin"}
        lista = dane["kancelarie"]
        # biuro-a jest ta sama kancelaria co wpis 1 z bazy (ten sam e-mail) - raz, jako online
        assert [k["id"] for k in lista] == ["biuro-a", "baza-2"]
        assert lista[0]["online"] and lista[0]["baza_id"] == 1 and lista[0]["telefony"] == ["81 000 00 00"]
        assert lista[0]["lat"] == 51.2465 and lista[0]["czas_minut"] == 60
        assert not lista[1]["online"] and lista[1]["baza_id"] == 2 and lista[1]["telefony"] == ["81 222 22 22"]
        assert scena.get("/api/klient/kancelarie", params={"miasto": "nigdzie"}).status_code == 404

    def test_najblizsze(self, scena):
        dane = scena.get("/api/klient/kancelarie", params={"lat": 51.25, "lon": 22.57}).json()
        assert [k["id"] for k in dane["kancelarie"]] == ["biuro-a"]     # biuro-b nie przyjmuje klientow
        assert dane["kancelarie"][0]["odleglosc_km"] < 1
        assert scena.get("/api/klient/kancelarie", params={"lat": 51.25}).status_code == 400

    def test_bez_sms_nikt_nie_jest_online(self, scena, monkeypatch):
        monkeypatch.setattr(sms, "TRYB", "wylaczony")
        assert scena.get("/api/klient/konfiguracja").json()["rezerwacje_online"] is False
        lista = scena.get("/api/klient/kancelarie", params={"miasto": "lublin"}).json()["kancelarie"]
        assert [k["id"] for k in lista] == ["baza-1", "baza-2"] and not any(k["online"] for k in lista)
        assert scena.post("/api/klient/weryfikacja", json={"telefon": "600700800"}).status_code == 503

    def test_terminy(self, scena):
        dane = scena.get(f"/api/klient/kancelarie/biuro-a/terminy", params={"od": scena.dzien, "dni": 3}).json()
        assert dane["kancelaria"]["id"] == "biuro-a" and dane["czas_minut"] == 60 and len(dane["dni"]) == 3
        pierwszy = dane["dni"][0]
        assert pierwszy["data"] == scena.dzien and not pierwszy["nieczynne"]
        assert pierwszy["terminy"][0] == {"godzina": "09:00", "koniec": "10:00"}
        assert pierwszy["terminy"][-1]["godzina"] == "16:00" and len(pierwszy["terminy"]) == 15
        with h._WBiurze("biuro-a"):
            kalendarz.ustaw_dzien(scena.dzien, {"tytul": "urlop", "nieczynne": True})
        dane = scena.get(f"/api/klient/kancelarie/biuro-a/terminy", params={"od": scena.dzien, "dni": 1}).json()
        assert dane["dni"][0]["nieczynne"] and dane["dni"][0]["terminy"] == []
        assert scena.get("/api/klient/kancelarie/biuro-b/terminy").status_code == 404
        assert scena.get("/api/klient/kancelarie/biuro-c/terminy").status_code == 404
        assert scena.get("/api/klient/kancelarie/biuro-a/terminy", params={"od": "2020-01-01", "dni": 99}).json()["dni"].__len__() == 14


class TestWeryfikacja:
    def test_kod_i_pulapka(self, scena):
        w = kod(scena)
        assert len(w["id"]) == 16 and w["koncowka"] == "800" and w["kod_testowy"].isdigit()
        assert sms.wyslane_testowo[0]["numer"] == "+48600700800" and w["kod_testowy"] in sms.wyslane_testowo[0]["tresc"]
        assert scena.post("/api/klient/weryfikacja", json={"telefon": "600700800", "strona": "x"}).json()["id"] == ""
        assert scena.post("/api/klient/weryfikacja", json={"telefon": "12345678"}).status_code == 400

    def test_limit_aktywnych_kodow(self, scena):
        for _ in range(3):
            kod(scena)
        assert scena.post("/api/klient/weryfikacja", json={"telefon": "600 700 800"}).status_code == 429

    def test_bez_kodu_w_logach(self, scena, caplog):
        caplog.set_level(logging.INFO)
        w = kod(scena)
        assert w["kod_testowy"] not in caplog.text and "600700800" not in caplog.text
        assert "klient: weryfikacja" in caplog.text


class TestRezerwacja:
    def test_pelny_przeplyw(self, scena, caplog):
        caplog.set_level(logging.INFO)
        w = kod(scena)
        dane = {**KLIENT, "kancelaria": "biuro-a", "data": scena.dzien, "godzina": "10:00",
                "weryfikacja": w["id"], "kod": "000000" if w["kod_testowy"] != "000000" else "111111"}
        assert scena.post("/api/klient/rezerwacje", json=dane).status_code == 400   # zly kod
        dane["kod"] = w["kod_testowy"]
        odp = scena.post("/api/klient/rezerwacje", json=dane)
        assert odp.status_code == 201, odp.text
        r = odp.json()
        assert r["status"] == "potwierdzona" and r["data"] == scena.dzien and r["godzina"] == "10:00" and r["koniec"] == "11:00"
        assert r["kancelaria"]["nazwa"] == "Kancelaria Notarialna Anna Testowa" and len(r["token"]) >= 40
        assert "umówiona" in r["komunikat"]
        # wpis w kalendarzu kancelarii z telefonem klienta
        with h._WBiurze("biuro-a"):
            wpisy = kalendarz.lista()
        assert len(wpisy) == 1 and wpisy[0]["id"] == r["id"] and wpisy[0]["rodzaj"] == "sprzedaż"
        assert wpisy[0]["telefony"] == [{"imie": "Jan Testowy", "numer": "+48600700800"}]
        assert "Jan Testowy" in wpisy[0]["tytul"] and "jan@klient.test" in wpisy[0]["uwagi"]
        assert wpisy[0]["zrodlo"] == "klient" and wpisy[0]["token"] != r["token"]
        # SMS: kod + potwierdzenie; e-mail do kancelarii
        assert [s["kategoria"] for s in sms.wyslane_testowo] == ["krytyczny", "krytyczny"]
        assert "wizyta potwierdzona" in sms.wyslane_testowo[1]["tresc"] and scena.dzien in sms.wyslane_testowo[1]["tresc"]
        assert scena.emaile[0][0] == ["wlasciciel@biuro-a.test"] and "Jan Testowy" in scena.emaile[0][2]
        # termin zniknal z wolnych
        terminy = scena.get("/api/klient/kancelarie/biuro-a/terminy", params={"od": scena.dzien, "dni": 1}).json()
        assert "10:00" not in {t["godzina"] for t in terminy["dni"][0]["terminy"]}
        # powtorka tego samego zadania (np. po zerwanym polaczeniu) zwraca te sama rezerwacje
        powtor = scena.post("/api/klient/rezerwacje", json=dane)
        assert powtor.status_code == 201 and powtor.json()["id"] == r["id"] and powtor.json()["token"] == r["token"]
        assert len(sms.wyslane_testowo) == 2
        # ten sam kod na inna kancelarie - nie
        assert scena.post("/api/klient/rezerwacje", json={**dane, "kancelaria": "biuro-b"}).status_code == 404
        # dane osobowe poza logami
        assert "Jan Testowy" not in caplog.text and "600700800" not in caplog.text and "klient.test" not in caplog.text
        assert "klient: rezerwacja" in caplog.text

    def test_kolizja_i_walidacja(self, scena):
        assert rezerwuj(scena, "10:00").status_code == 201
        drugi = rezerwuj(scena, "10:00", telefon="600 700 801", imie="Anna Druga")
        assert drugi.status_code == 409
        assert rezerwuj(scena, "10:30", telefon="600 700 802").status_code == 409   # nachodzi na 10:00-11:00
        assert rezerwuj(scena, "11:00", telefon="600 700 803").status_code == 201
        assert rezerwuj(scena, "12:00", telefon="600 700 804", zgoda=False).status_code == 400
        assert rezerwuj(scena, "12:00", telefon="600 700 805", rodzaj="inne", rodzaj_inny="").status_code == 400
        assert rezerwuj(scena, "12:00", telefon="600 700 806", email="zle").status_code == 400
        assert rezerwuj(scena, "12:00", telefon="600 700 807", kancelaria="biuro-c").status_code == 404
        odp = rezerwuj(scena, "12:00", telefon="600 700 808", rodzaj="inne", rodzaj_inny="Umowa spółki", email="")
        assert odp.status_code == 201 and odp.json()["rodzaj_inny"] == "Umowa spółki"

    def test_kod_innego_numeru_nie_dziala(self, scena):
        w = kod(scena, "600 700 800")
        odp = scena.post("/api/klient/rezerwacje", json={**KLIENT, "telefon": "600 700 999", "kancelaria": "biuro-a",
                                                         "data": scena.dzien, "godzina": "10:00",
                                                         "weryfikacja": w["id"], "kod": w["kod_testowy"]})
        assert odp.status_code == 400 and "potwierdź numer" in odp.json()["detail"]

    def test_za_duzo_prob_kodu(self, scena):
        w = kod(scena)
        dane = {**KLIENT, "kancelaria": "biuro-a", "data": scena.dzien, "godzina": "10:00",
                "weryfikacja": w["id"], "kod": "999999" if w["kod_testowy"] != "999999" else "888888"}
        for _ in range(5):
            assert scena.post("/api/klient/rezerwacje", json=dane).status_code == 400
        assert scena.post("/api/klient/rezerwacje", json={**dane, "kod": w["kod_testowy"]}).status_code == 429

    def test_nieczynny_dzien(self, scena):
        with h._WBiurze("biuro-a"):
            kalendarz.ustaw_dzien(scena.dzien, {"tytul": "urlop", "nieczynne": True})
        assert rezerwuj(scena).status_code == 409

    def test_cors_dla_aplikacji_webowej(self, scena):
        odp = scena.options("/api/klient/kancelarie", headers={"Origin": "https://notarai.pl",
                                                               "Access-Control-Request-Method": "GET"})
        assert odp.status_code == 204 and odp.headers["access-control-allow-origin"] == "https://notarai.pl"


class TestZarzadzanie:
    def test_podglad_odwolanie(self, scena):
        r = rezerwuj(scena).json()
        dostep = {"kancelaria": "biuro-a", "token": r["token"]}
        assert scena.post(f"/api/klient/rezerwacje/{r['id']}/podglad", json=dostep).json()["status"] == "potwierdzona"
        assert scena.post(f"/api/klient/rezerwacje/{r['id']}/podglad", json={**dostep, "token": "x" * 40}).status_code == 404
        assert scena.post(f"/api/klient/rezerwacje/{r['id']}/anuluj", json={**dostep, "token": "x" * 40}).status_code == 404
        odp = scena.post(f"/api/klient/rezerwacje/{r['id']}/anuluj", json=dostep)
        assert odp.status_code == 200 and odp.json()["status"] == "anulowana"
        assert "odwolana" in sms.wyslane_testowo[-1]["tresc"]
        assert "odwołał" in scena.emaile[-1][1]
        terminy = scena.get("/api/klient/kancelarie/biuro-a/terminy", params={"od": scena.dzien, "dni": 1}).json()
        assert "10:00" in {t["godzina"] for t in terminy["dni"][0]["terminy"]}
        with h._WBiurze("biuro-a"):
            assert kalendarz.lista() == []
        ile = len(sms.wyslane_testowo)
        assert scena.post(f"/api/klient/rezerwacje/{r['id']}/anuluj", json=dostep).json()["status"] == "anulowana"
        assert len(sms.wyslane_testowo) == ile    # drugie odwolanie nic nie wysyla
        assert scena.put(f"/api/klient/rezerwacje/{r['id']}",
                         json={**dostep, "data": scena.dzien, "godzina": "12:00"}).status_code == 409

    def test_przelozenie(self, scena):
        r = rezerwuj(scena).json()
        rezerwuj(scena, "12:00", telefon="600 700 801")
        dostep = {"kancelaria": "biuro-a", "token": r["token"]}
        zajety = scena.put(f"/api/klient/rezerwacje/{r['id']}", json={**dostep, "data": scena.dzien, "godzina": "12:00"})
        assert zajety.status_code == 409
        odp = scena.put(f"/api/klient/rezerwacje/{r['id']}", json={**dostep, "data": scena.dzien, "godzina": "14:00"})
        assert odp.status_code == 200 and odp.json()["godzina"] == "14:00" and odp.json()["koniec"] == "15:00"
        assert "przelozona" in sms.wyslane_testowo[-1]["tresc"] and "14:00" in sms.wyslane_testowo[-1]["tresc"]
        assert "przełożył" in scena.emaile[-1][1]
        terminy = scena.get("/api/klient/kancelarie/biuro-a/terminy", params={"od": scena.dzien, "dni": 1}).json()
        godziny = {t["godzina"] for t in terminy["dni"][0]["terminy"]}
        assert "10:00" in godziny and "14:00" not in godziny

    def test_kancelaria_odwoluje_lub_przenosi(self, scena, monkeypatch):
        r = rezerwuj(scena).json()
        with h._WBiurze("biuro-a"):
            stary = next(w for w in kalendarz.lista() if w["id"] == r["id"])
            ile = len(sms.wyslane_testowo)
            rk.powiadom_o_zmianie_kancelarii(stary, {**stary, "godzina": "15:00"})
            assert "przeniosla" in sms.wyslane_testowo[-1]["tresc"] and "15:00" in sms.wyslane_testowo[-1]["tresc"]
            rk.powiadom_o_zmianie_kancelarii(stary, None)
            assert "odwolala" in sms.wyslane_testowo[-1]["tresc"] and len(sms.wyslane_testowo) == ile + 2
            rk.powiadom_o_zmianie_kancelarii(stary, dict(stary))        # bez zmiany terminu - cisza
            rk.powiadom_o_zmianie_kancelarii({"zrodlo": "hurtowe", "data": "x", "godzina": "y"}, None)
            assert len(sms.wyslane_testowo) == ile + 2

    def test_kalendarz_kancelarii_wysyla_sms_przy_usunieciu(self, scena, monkeypatch):
        """Kancelaria "lokalna" (tryb jednego stanowiska) usuwa wizyte klienta
        przez zwykle API kalendarza - klient dostaje SMS."""
        rejestr = {**REJESTR, "l": {**REJESTR["x"], "id": "lokalna", "nazwa": "Kancelaria Lokalna Testowa",
                                    "zespol": []}}
        autoryzacja._zapisz_rejestr(rejestr)
        with h._WBiurze("lokalna"):
            magazyn.zmien_plik_kancelarii("rezerwacje_hurtowe", lambda a: a.update(POLITYKA), {})
        r = rezerwuj(scena, kancelaria="lokalna").json()
        ile = len(sms.wyslane_testowo)
        assert scena.delete(f"/api/kalendarz/{r['id']}").status_code == 200
        assert len(sms.wyslane_testowo) == ile + 1 and "odwolala" in sms.wyslane_testowo[-1]["tresc"]
        assert "Kancelaria Lokalna Testowa" in sms.wyslane_testowo[-1]["tresc"]
        # Wpis zostaje jako odwolany: znika z kalendarza i wolnych terminow, a
        # aplikacja klienta widzi "anulowana" zamiast nieaktualnego potwierdzenia.
        assert all(w["id"] != r["id"] for w in scena.get("/api/kalendarz").json())
        assert "10:00" in [t["godzina"] for d in scena.get("/api/klient/kancelarie/lokalna/terminy",
                                                             params={"od": scena.dzien, "dni": 1}).json()["dni"]
                           for t in d["terminy"]]
        podglad = scena.post(f"/api/klient/rezerwacje/{r['id']}/podglad",
                             json={"kancelaria": "lokalna", "token": r["token"]}).json()
        assert podglad["status"] == "anulowana" and podglad["anulowal"] == "kancelaria"
        assert scena.delete(f"/api/kalendarz/{r['id']}").status_code == 404     # drugi raz - nie ma czego
        assert len(sms.wyslane_testowo) == ile + 1


class TestSwieta:
    def test_kalendarz_swiat(self):
        k = kalendarz                             # bez fikstury scena - prawdziwa funkcja
        assert k.swieto("2026-11-11") == "Święto Niepodległości"
        assert k.swieto("2026-04-06") == "Poniedziałek Wielkanocny"
        assert k.swieto("2026-06-04") == "Boże Ciało"
        assert k.swieto("2027-03-28") == "Wielkanoc"
        assert k.swieto("2025-12-24") == "Wigilia" and k.swieto("2024-12-24") == ""
        assert k.swieto("2026-11-10") == "" and k.swieto("zly-dzien") == ""

    def test_w_swieto_brak_terminow_i_rezerwacji(self, scena, monkeypatch):
        monkeypatch.setattr(kalendarz, "swieto", lambda dzien: "Testowe Święto" if str(dzien) == scena.dzien else "")
        dni = scena.get("/api/klient/kancelarie/biuro-a/terminy", params={"od": scena.dzien, "dni": 2}).json()["dni"]
        assert dni[0] == {"data": scena.dzien, "nieczynne": True, "swieto": "Testowe Święto", "terminy": []}
        assert dni[1]["terminy"] and dni[1]["swieto"] == ""
        odp = rezerwuj(scena)
        assert odp.status_code == 409 and "zajęty" in odp.json()["detail"]


class TestKokpitKancelarii:
    """Wizyta klienta w kalendarzu kancelarii (kokpit, /api/kalendarz): dane
    klienta widoczne, odcisk tokenu nie, SMS tylko przy zmianie terminu."""

    @pytest.fixture
    def wizyta(self, scena):
        rejestr = {**REJESTR, "l": {**REJESTR["x"], "id": "lokalna", "nazwa": "Kancelaria Lokalna Testowa",
                                    "zespol": []}}
        autoryzacja._zapisz_rejestr(rejestr)
        with h._WBiurze("lokalna"):
            magazyn.zmien_plik_kancelarii("rezerwacje_hurtowe", lambda a: a.update(POLITYKA), {})
        r = rezerwuj(scena, kancelaria="lokalna")
        assert r.status_code == 201, r.text
        return next(w for w in scena.get("/api/kalendarz").json() if w["id"] == r.json()["id"])

    @staticmethod
    def formularz(wpis, **zmiany):
        pola = ("data", "godzina", "koniec", "tytul", "rodzaj", "rodzaj_inny", "uczestnicy", "telefony", "uwagi")
        return {**{k: wpis[k] for k in pola}, **zmiany}

    def test_lista_z_danymi_klienta_bez_tokenu(self, wizyta):
        assert wizyta["zrodlo"] == "klient" and wizyta["status"] == "potwierdzona"
        assert wizyta["klient"]["email"] == "jan@klient.test" and wizyta["klient"]["uwagi"] == "Kupuję na kredyt."
        assert "token" not in wizyta and "weryfikacja" not in wizyta

    def test_zapis_bez_zmiany_terminu_bez_sms(self, scena, wizyta):
        ile = len(sms.wyslane_testowo)
        odp = scena.put(f"/api/kalendarz/{wizyta['id']}", json=self.formularz(wizyta, uwagi="Oddzwonić w sprawie KW."))
        assert odp.status_code == 200, odp.text
        assert "token" not in odp.json() and odp.json()["zrodlo"] == "klient"
        assert len(sms.wyslane_testowo) == ile
        po = next(w for w in scena.get("/api/kalendarz").json() if w["id"] == wizyta["id"])
        assert po["uwagi"] == "Oddzwonić w sprawie KW." and po["klient"]["telefon"]

    def test_przeniesienie_sms_i_przypomnienie_od_nowa(self, scena, wizyta):
        with h._WBiurze("lokalna"):
            magazyn.zmien_plik_kancelarii(
                "kalendarz", lambda wpisy: [w.update(przypomnienie="2026-11-09T10:00:00") for w in wpisy], [])
        nowy_dzien = (datetime.fromisoformat(wizyta["data"]) + timedelta(days=1)).date().isoformat()
        ile = len(sms.wyslane_testowo)
        odp = scena.put(f"/api/kalendarz/{wizyta['id']}",
                        json=self.formularz(wizyta, data=nowy_dzien, godzina="15:00", koniec="16:00"))
        assert odp.status_code == 200, odp.text
        assert len(sms.wyslane_testowo) == ile + 1
        assert "przeniosla" in sms.wyslane_testowo[-1]["tresc"] and nowy_dzien in sms.wyslane_testowo[-1]["tresc"]
        with h._WBiurze("lokalna"):
            wpis = next(w for w in kalendarz.lista() if w["id"] == wizyta["id"])
        assert wpis["przypomnienie"] is None and wpis["zrodlo"] == "klient"


class TestPrzypomnienia:
    def test_dzien_przed(self, scena):
        jutro = (datetime.now(h.STREFA) + timedelta(days=1)).date().isoformat()
        r = rezerwuj(scena, data=jutro).json()
        rezerwuj(scena, "12:00", telefon="600 700 801")          # za 3 dni - jeszcze nie
        teraz = datetime.now(h.STREFA).replace(hour=10, minute=0)
        wynik = rk.wyslij_przypomnienia(teraz)
        assert wynik == {"wyslane": 1, "pominiete": 0, "kancelarie": 1}
        assert sms.wyslane_testowo[-1]["kategoria"] == "automatyczny" and jutro in sms.wyslane_testowo[-1]["tresc"]
        assert sms.wyslane_testowo[-1]["numer"] == "+48600700800"
        with h._WBiurze("biuro-a"):
            wpis = next(w for w in kalendarz.lista() if w["id"] == r["id"])
        assert wpis["przypomnienie"]
        assert rk.wyslij_przypomnienia(teraz)["wyslane"] == 0        # raz na wizyte
        assert scena.post("/api/admin/klient/przypomnienia", headers=ADMIN).json()["wyslane"] == 0
        assert scena.post("/api/admin/klient/przypomnienia").status_code == 401

    def test_poza_oknem_nic(self, scena, monkeypatch):
        jutro = (datetime.now(h.STREFA) + timedelta(days=1)).date().isoformat()
        r = rezerwuj(scena, data=jutro).json()
        monkeypatch.setattr(sms, "w_oknie", lambda teraz=None: False)
        assert rk.wyslij_przypomnienia()["wyslane"] == 0
        with h._WBiurze("biuro-a"):
            assert next(w for w in kalendarz.lista() if w["id"] == r["id"])["przypomnienie"] is None

    def test_stop_wypisuje_z_przypomnien(self, scena):
        jutro = (datetime.now(h.STREFA) + timedelta(days=1)).date().isoformat()
        rezerwuj(scena, data=jutro)
        assert scena.post("/api/klient/sms-przychodzacy", params={"token": "zly"},
                          data={"From": "+48600700800", "Body": "STOP"}).status_code == 403
        odp = scena.post("/api/klient/sms-przychodzacy", params={"token": "hak-testowy"},
                         data={"From": "+48600700800", "Body": "STOP"})
        assert odp.status_code == 200 and "<Response>" in odp.text
        assert rk.wypisany("600 700 800") and not rk.wypisany("600 700 801")
        teraz = datetime.now(h.STREFA).replace(hour=10, minute=0)
        assert rk.wyslij_przypomnienia(teraz) == {"wyslane": 0, "pominiete": 1, "kancelarie": 1}
        # potwierdzenia dalej dochodza
        assert rezerwuj(scena, "13:00").status_code == 201

    def test_stan_dla_admina(self, scena):
        stan = scena.get("/api/admin/klient/stan", headers=ADMIN).json()
        assert stan["sms"] == {"tryb": "test", "gotowe": True, "brak": ""}
        assert [k["id"] for k in stan["kancelarie_online"]] == ["biuro-a"]
