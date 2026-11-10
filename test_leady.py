"""Gielda leadow (leady.py) i webhook Meta (meta_leady.py). E-mail i Graph API
zastapione atrapami, dane fikcyjne."""
import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

import app as aplikacja
import autoryzacja
import config
import leady
import meta_leady
import wizyty
from test_wizyty import REJESTR

BAZA = {
    "miejscowosci": [{"slug": "lublin", "nazwa": "Lublin", "izba": "Lublinie", "liczba": 3},
                     {"slug": "pulawy", "nazwa": "Puławy", "izba": "Lublinie", "liczba": 1}],
    "kancelarie": [
        {"id": 1, "slug": "lublin", "miejscowosc": "Lublin", "nazwa": "Kancelaria Anna Testowa",
         "email": "anna@kancelaria-testowa.test", "telefony": ["81 000 00 00"], "adres": "ul. Próbna 1, Lublin"},
        {"id": 2, "slug": "lublin", "miejscowosc": "Lublin", "nazwa": "Kancelaria Jan Obcy",
         "email": "jan@obcy.test", "telefony": ["81 222 22 22"], "adres": "ul. Inna 2, Lublin"},
        {"id": 4, "slug": "lublin", "miejscowosc": "Lublin", "nazwa": "Kancelaria Bez Maila",
         "email": "", "telefony": ["81 333"], "adres": ""},
        {"id": 3, "slug": "pulawy", "miejscowosc": "Puławy", "nazwa": "Kancelaria Ewa",
         "email": "ewa@pulawy.test", "telefony": [], "adres": ""},
    ],
}
KLIENT = {"imie": "Zenobiusz", "nazwisko": "Testowy", "telefon": "600 700 800", "email": "z@klient.test"}


@pytest.fixture
def k(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DANE", tmp_path)
    monkeypatch.setattr(autoryzacja, "_wczytaj_rejestr", lambda: REJESTR)
    monkeypatch.setattr(autoryzacja, "ADMIN_TOKEN", "sekret-admina")
    monkeypatch.setattr(wizyty, "NADAWCA", "notarai <zapytania@notarai.test>")
    monkeypatch.setattr(wizyty, "KOPIA", "")
    wyslane = []
    monkeypatch.setattr(wizyty, "_wyslij_email", lambda do, temat, tresc: wyslane.append((do, temat, tresc)) or True)
    wizyty._ustaw_baze(BAZA)
    wizyty.limit_zgloszen.wyczysc()
    klient = TestClient(aplikacja.app)
    klient.wyslane = wyslane
    yield klient
    wizyty._ustaw_baze(None)


def _token(wyslane, adres):
    tresc = next(t for do, _, t in wyslane if do == [adres])
    return tresc.split("/lead/#")[1].split()[0]


def _lead(**zm):
    return leady.nowy(**{"klient": KLIENT, "sprawa": "Sprzedaż mieszkania", "opis": "Mieszkanie po mamie, 450 tys.",
                         "miejscowosc": "Lublin", "zrodlo": "test", **zm})


class TestRozsylka:
    def test_wszystkie_kancelarie_z_mailem_bez_kontaktu_klienta(self, k):
        lead = _lead()
        adresaci = sorted(w[0][0] for w in k.wyslane)
        assert adresaci == ["anna@kancelaria-testowa.test", "jan@obcy.test"]
        for _, temat, tresc in k.wyslane:
            assert "600 700 800" not in tresc and "z@klient.test" not in tresc and "Testowy" not in tresc
            assert "Sprzedaż / kupno nieruchomości" in tresc and "/lead/#" in tresc
        assert lead["sprawa"] == "sprzedaz" and lead["wyslano"] == 2

    def test_nieznana_miejscowosc_bez_rozsylki(self, k):
        lead = _lead(miejscowosc="Nibylandia")
        assert lead["wyslano"] == 0 and lead["miejscowosc"] is None

    def test_brak_danych_klienta_w_logach(self, k, caplog):
        caplog.set_level(logging.INFO)
        _lead()
        assert "Zenobiusz" not in caplog.text and "600 700 800" not in caplog.text


class TestOkno:
    def test_odpowiedz_w_oknie_odslania_kontakt_i_powiadamia_klienta(self, k):
        _lead()
        token = _token(k.wyslane, "jan@obcy.test")
        z = k.post("/api/leady/zaproszenie", json={"token": token}).json()
        assert z["otwarte"] and "klient" not in z["lead"] and z["kancelaria"] == "Kancelaria Jan Obcy"
        k.wyslane.clear()
        odp = k.post("/api/leady/odpowiedz", json={"token": token, "tresc": "Zapraszamy w czwartek", "termin": "czw 10:00"})
        assert odp.status_code == 200, odp.text
        assert odp.json()["lead"]["klient"]["telefon"] == "600 700 800"
        assert k.wyslane[0][0] == ["z@klient.test"] and "Kancelaria Jan Obcy" in k.wyslane[0][2]
        assert k.post("/api/leady/odpowiedz", json={"token": token}).status_code == 409

    def test_kilka_kancelarii_moze_odpowiedziec(self, k):
        _lead()
        for adres in ("jan@obcy.test", "anna@kancelaria-testowa.test"):
            assert k.post("/api/leady/odpowiedz", json={"token": _token(k.wyslane, adres)}).status_code == 200
        assert len(leady._wczytaj()["leady"][0]["odpowiedzi"]) == 2

    def test_po_godzinie_link_nie_dziala(self, k, monkeypatch):
        _lead()
        token = _token(k.wyslane, "jan@obcy.test")
        monkeypatch.setattr(leady, "_teraz", lambda: datetime.now() + timedelta(minutes=leady.OKNO_MIN + 1))
        assert k.post("/api/leady/zaproszenie", json={"token": token}).json()["otwarte"] is False
        assert k.post("/api/leady/odpowiedz", json={"token": token}).status_code == 410

    def test_zly_token(self, k):
        assert k.post("/api/leady/zaproszenie", json={"token": "x" * 24}).status_code == 404


class TestGielda:
    """Kancelaria "lokalna" (REJESTR) to w bazie id 1 - przez e-mail wlascicielki."""

    def test_otwarte_bez_kontaktu_archiwum_dla_oplaconej(self, k, monkeypatch):
        _lead()
        g = k.get("/api/gielda").json()
        assert len(g["otwarte"]) == 1 and "klient" not in g["otwarte"][0]
        monkeypatch.setattr(leady, "_teraz", lambda: datetime.now() + timedelta(hours=2))
        monkeypatch.setattr(autoryzacja, "_oplacona", lambda id_k: True)
        g = k.get("/api/gielda").json()
        assert g["otwarte"] == [] and g["archiwum"][0]["klient"]["email"] == "z@klient.test"

    def test_archiwum_zamkniete_bez_abonamentu(self, k, monkeypatch):
        lead = _lead()
        monkeypatch.setattr(leady, "_teraz", lambda: datetime.now() + timedelta(hours=2))
        monkeypatch.setattr(autoryzacja, "_oplacona", lambda id_k: False)
        g = k.get("/api/gielda").json()
        assert g["archiwum"] == [] and g["oplacona"] is False
        assert k.post(f"/api/gielda/{lead['id']}/odpowiedz", json={}).status_code == 402

    def test_oplacona_odpowiada_z_archiwum(self, k, monkeypatch):
        lead = _lead()
        monkeypatch.setattr(leady, "_teraz", lambda: datetime.now() + timedelta(hours=2))
        monkeypatch.setattr(autoryzacja, "_oplacona", lambda id_k: True)
        odp = k.post(f"/api/gielda/{lead['id']}/odpowiedz", json={"tresc": "Możemy jutro"})
        assert odp.status_code == 200 and odp.json()["odpowiedz"]["w_oknie"] is False

    def test_w_oknie_odpowiedz_w_aplikacji_bez_abonamentu(self, k, monkeypatch):
        lead = _lead()
        monkeypatch.setattr(autoryzacja, "_oplacona", lambda id_k: False)
        odp = k.post(f"/api/gielda/{lead['id']}/odpowiedz", json={"tresc": "Zapraszamy"})
        assert odp.status_code == 200 and odp.json()["lead"]["klient"]["imie"] == "Zenobiusz"


class TestStronaIGielda:
    def test_dowolna_kancelaria_ze_strony_idzie_na_gielde(self, k):
        odp = k.post("/api/wizyty/zgloszenie", json={"imie": "Zenobiusz", "telefon": "600 700 800", "czynnosc": "testament",
                                                     "zgoda": True, "miejscowosc": "lublin"})
        assert odp.status_code == 201 and odp.json()["gielda"] and "wszystkie kancelarie" in odp.json()["komunikat"]
        assert leady._wczytaj()["leady"][0]["sprawa"] == "testament"

    def test_wybrana_kancelaria_dalej_bezposrednio(self, k):
        odp = k.post("/api/wizyty/zgloszenie", json={"imie": "Zenobiusz", "telefon": "600 700 800", "czynnosc": "testament",
                                                     "zgoda": True, "kancelaria": 2})
        assert odp.status_code == 201 and not odp.json().get("gielda")


# ---------------------------------------------------------------- Meta

SEKRET = "app-secret-test"
LEAD_META = {"id": "123456789", "created_time": "2026-11-08T10:00:00+0000", "form_id": "f1", "ad_id": "a1",
             "campaign_name": "Notariusz Lublin", "platform": "fb", "field_data": [
                 {"name": "full_name", "values": ["Zenobiusz Testowy"]},
                 {"name": "phone_number", "values": ["+48600700800"]},
                 {"name": "email", "values": ["z@klient.test"]},
                 {"name": "city", "values": ["Lublin"]},
                 {"name": "jaka_sprawa", "values": ["darowizna_mieszkania"]},
                 {"name": "opis_sprawy", "values": ["Chcę przekazać mieszkanie synowi"]},
                 {"name": "kiedy", "values": ["w tym miesiącu"]}]}


@pytest.fixture
def meta(k, monkeypatch):
    monkeypatch.setenv("PIECZAPP_META_APP_SECRET", SEKRET)
    monkeypatch.setenv("PIECZAPP_META_VERIFY", "weryfikacja")
    monkeypatch.setenv("PIECZAPP_META_TOKEN", "token-strony")
    zadania = []

    def graph(req: httpx.Request):
        zadania.append(req)
        return httpx.Response(200, json=LEAD_META)
    monkeypatch.setattr(meta_leady, "_transport", httpx.MockTransport(graph))
    k.graph = zadania
    return k


def _podpisz(cialo: bytes) -> str:
    return "sha256=" + hmac.new(SEKRET.encode(), cialo, hashlib.sha256).hexdigest()


WEBHOOK = json.dumps({"object": "page", "entry": [{"changes": [{"field": "leadgen", "value": {
    "leadgen_id": "123456789", "form_id": "f1", "page_id": "p1"}}]}]}).encode()


class TestMeta:
    def test_weryfikacja_subskrypcji(self, meta):
        ok = meta.get("/api/meta/leadgen", params={"hub.mode": "subscribe", "hub.verify_token": "weryfikacja", "hub.challenge": "42"})
        assert ok.status_code == 200 and ok.text == "42"
        assert meta.get("/api/meta/leadgen", params={"hub.mode": "subscribe", "hub.verify_token": "zly"}).status_code == 403

    def test_lead_z_formularza_trafia_na_gielde(self, meta):
        odp = meta.post("/api/meta/leadgen", content=WEBHOOK, headers={"X-Hub-Signature-256": _podpisz(WEBHOOK)})
        assert odp.status_code == 200, odp.text
        lead = leady._wczytaj()["leady"][0]
        assert lead["zrodlo"] == "meta" and lead["sprawa"] == "darowizna" and lead["miejscowosc"] == "lublin"
        assert lead["klient"] == {"imie": "Zenobiusz", "nazwisko": "Testowy", "telefon": "+48600700800", "email": "z@klient.test"}
        assert "kiedy: w tym miesiącu" in lead["opis"] and lead["meta"]["campaign_name"] == "Notariusz Lublin"
        assert meta.graph[0].headers["authorization"] == "Bearer token-strony" and "token" not in str(meta.graph[0].url)
        assert lead["wyslano"] == 2

    def test_zly_podpis_odrzucony(self, meta):
        assert meta.post("/api/meta/leadgen", content=WEBHOOK, headers={"X-Hub-Signature-256": "sha256=00"}).status_code == 403
        assert leady._wczytaj()["leady"] == []

    def test_ponowiony_webhook_nie_dubluje(self, meta):
        for _ in range(2):
            meta.post("/api/meta/leadgen", content=WEBHOOK, headers={"X-Hub-Signature-256": _podpisz(WEBHOOK)})
        assert len(leady._wczytaj()["leady"]) == 1 and len(meta.graph) == 1


def test_admin_dodaje_lead_recznie(k):
    odp = k.post("/api/admin/leady", headers={"Authorization": "Bearer sekret-admina"},
                 json={"imie": "Zenobiusz", "telefon": "600", "sprawa": "spadek", "miejscowosc": "Puławy"})
    assert odp.status_code == 201 and odp.json()["wyslano"] == 1
    lista = k.get("/api/admin/leady", headers={"Authorization": "Bearer sekret-admina"}).json()
    assert lista["podsumowanie"]["leady"] == 1 and "zaproszenia" not in lista["leady"][0]


class TestPrzezFinyou:
    SEKRET = "sekret-testowy"

    @pytest.fixture
    def fy(self, k, monkeypatch):
        monkeypatch.setattr(meta_leady, "SKROT_SEKRETU_FINYOU", hashlib.sha256(self.SEKRET.encode()).hexdigest())
        return k

    PAYLOAD = {"meta_lead_id": "987", "imie": "Zenobiusz Testowy", "telefon": "+48600700800", "email": "z@klient.test",
               "utworzono": "2026-11-08T10:00:00+0000", "kampania_id": "c1", "reklama_id": "a1", "formularz_id": "f9",
               "pola": [{"nazwa": "full_name", "wartosc": "Zenobiusz Testowy"}, {"nazwa": "city", "wartosc": "Lublin"},
                        {"nazwa": "jaka_sprawa", "wartosc": "Spadek, poświadczenie dziedziczenia"},
                        {"nazwa": "opis_sprawy", "wartosc": "Po tacie, dwoje rodzeństwa"}]}

    def test_lead_z_finyou(self, fy):
        odp = fy.post("/api/meta/finyou", json=self.PAYLOAD, headers={"x-lead-secret": self.SEKRET})
        assert odp.status_code == 200 and odp.json()["wyslano"] == 2
        lead = leady._wczytaj()["leady"][0]
        assert lead["sprawa"] == "spadek" and lead["miejscowosc"] == "lublin"
        assert lead["klient"]["nazwisko"] == "Testowy" and lead["meta"]["przez"] == "finyou"
        assert fy.post("/api/meta/finyou", json=self.PAYLOAD, headers={"x-lead-secret": self.SEKRET}).json()["duplikat"]

    def test_zly_sekret(self, fy):
        assert fy.post("/api/meta/finyou", json=self.PAYLOAD, headers={"x-lead-secret": "zly"}).status_code == 403
        assert fy.post("/api/meta/finyou", json=self.PAYLOAD).status_code == 403
