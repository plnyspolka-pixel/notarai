"""Narzedzia agenta glosowego (ElevenLabs): koszt, dokumenty, kancelarie,
terminy, rezerwacja, zgloszenie, kontakt kancelarii, token i limity.
Dane fikcyjne, e-mail nie wychodzi."""
import logging

import pytest
from fastapi.testclient import TestClient

import agent_glosowy as ag
import app as aplikacja
import autoryzacja
import config
import kalkulator
import magazyn
import rezerwacje_hurtowe as hurt
import wizyty
from test_rezerwacje_klientow import POLITYKA, REJESTR, _jutro
from test_wizyty import BAZA

KLIENT = {"imie": "Zenobiusz Testowy", "telefon": "600 700 800", "email": "zenobiusz@klient.test",
          "czynnosc": "zakup mieszkania", "zgoda": True}


@pytest.fixture
def k(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DANE", tmp_path)
    monkeypatch.setattr(autoryzacja, "_wczytaj_rejestr", lambda: REJESTR)
    monkeypatch.setattr(autoryzacja, "ADMIN_TOKEN", "sekret-admina")
    monkeypatch.setattr(autoryzacja, "STALI_ADMINI", ["admin@notarai.test"])
    monkeypatch.setattr(wizyty, "NADAWCA", "notarai <zapytania@notarai.test>")
    monkeypatch.setattr(wizyty, "KOPIA", "zgloszenia@notarai.test")
    monkeypatch.setattr(wizyty, "DOWOLNA", "kolejka")
    monkeypatch.setattr(wizyty, "limit_zgloszen", wizyty.Limit(100, 1000))
    monkeypatch.setattr(ag, "TOKEN", "")
    monkeypatch.setattr(ag, "limit_odczytow", kalkulator.Limit(60, 5000))
    monkeypatch.setattr(ag, "limit_zapisow", kalkulator.Limit(3, 200))
    wizyty._ustaw_baze(BAZA)
    with hurt._WBiurze("lokalna"):
        magazyn.zmien_plik_kancelarii(hurt.PLIK_USTAWIEN, lambda a: a.update(POLITYKA), {})
    wyslane = []
    monkeypatch.setattr(wizyty, "_wyslij_email", lambda do, temat, tresc: wyslane.append((do, temat, tresc)) or True)
    klient = TestClient(aplikacja.app)
    klient.wyslane = wyslane
    yield klient
    wizyty._ustaw_baze(None)


def _post(k, narzedzie, **dane):
    return k.post(f"/api/agent-glosowy/{narzedzie}", json={"rozmowa": "conv_test1", **dane})


class TestKoszt:
    def test_sprzedaz_lokalu_liczy_taksa_py_i_podaje_dokumenty(self, k):
        d = _post(k, "koszt", czynnosc="sprzedaz_lokalu", wartosc=500000).json()
        assert d["razem"] == "12 808 zł 91 gr"
        assert any(p.startswith("taksa notarialna") and "1 703 zł 55 gr" in p for p in d["pozycje"])
        assert any("Dowody osobiste" in x for x in d["dokumenty"])
        assert "maksymalnych stawek" in d["do_powiedzenia"]

    def test_czynnosc_z_wartoscia_bez_wartosci_prosi_o_nia(self, k):
        d = _post(k, "koszt", czynnosc="darowizna_inna").json()
        assert d["ok"] is False and "wartość" in d["do_powiedzenia"]

    def test_czynnosc_stala_bez_wartosci(self, k):
        d = _post(k, "koszt", czynnosc="testament").json()
        assert d["razem"].endswith("zł") or " gr" in d["razem"]
        assert d["pozycje"]

    def test_nieznana_czynnosc(self, k):
        d = _post(k, "koszt", czynnosc="lot_na_ksiezyc").json()
        assert d["ok"] is False and "Nieznana" in d["do_powiedzenia"]

    def test_dokumenty_do_spadku(self, k):
        d = _post(k, "dokumenty", czynnosc="apd").json()
        assert any("aktu zgonu" in x for x in d["dokumenty"])

    def test_kwota_na_glos(self):
        assert ag.zl_na_glos(1234567.5) == "1 234 567 zł 50 gr"
        assert ag.zl_na_glos(200) == "200 zł"


class TestKancelarie:
    def test_miejscowosc_bez_ogonkow_i_z_przyimkiem(self, k):
        assert ag.znajdz_miejscowosc("w Puławach")[0] is None   # odmiana - agent ma podac mianownik
        assert ag.znajdz_miejscowosc("Pulawy")[0] == "pulawy"
        assert ag.znajdz_miejscowosc("puławy")[0] == "pulawy"
        assert ag.znajdz_miejscowosc("Lubin")[1] == ["Lublin"] or ag.znajdz_miejscowosc("Lubin")[0] == "lublin"

    def test_lista_w_kolejnosci_strony_z_flagami(self, k):
        d = _post(k, "kancelarie", miejscowosc="Lublin").json()
        assert d["znaleziono"] and d["liczba"] == 2
        strona = k.get("/api/wizyty/kancelarie", params={"miejscowosc": "lublin"}).json()["kolejnosc"]
        assert [x["kancelaria_id"] for x in d["kancelarie"]] == strona   # ta sama neutralna kolejnosc
        testowa = next(x for x in d["kancelarie"] if x["kancelaria_id"] == 1)
        assert testowa["rezerwacja_online"] and testowa["telefon"] == "81 000 00 00"

    def test_tylko_rezerwacja_online(self, k):
        d = _post(k, "kancelarie", miejscowosc="Lublin", tylko_rezerwacja_online=True).json()
        assert [x["kancelaria_id"] for x in d["kancelarie"]] == [1]

    def test_nieznana_miejscowosc_z_podpowiedzia(self, k):
        d = _post(k, "kancelarie", miejscowosc="Atlantyda").json()
        assert d["znaleziono"] is False and "Nie znalazłam" in d["do_powiedzenia"]


class TestTerminyIRezerwacja:
    def test_wolne_godziny_pogrupowane_po_dniach(self, k):
        d = _post(k, "terminy", kancelaria_id=1, od=_jutro(), dni=1).json()
        assert d["rezerwacja_online"] and d["wolne"][0]["data"] == _jutro()
        assert d["wolne"][0]["godziny"][:2] == ["09:00", "09:30"]

    def test_kancelaria_bez_rezerwacji(self, k):
        d = _post(k, "terminy", kancelaria_id=2).json()
        assert d["rezerwacja_online"] is False and "prośbę o kontakt" in d["do_powiedzenia"]

    def test_nieznana_kancelaria(self, k):
        d = _post(k, "terminy", kancelaria_id=999).json()
        assert d["ok"] is False and "Nie znamy kancelarii" in d["do_powiedzenia"]

    def test_rezerwacja_wchodzi_do_kalendarza_i_wysyla_potwierdzenie(self, k):
        d = _post(k, "rezerwacja", kancelaria_id=1, data=_jutro(), godzina="10:00", **KLIENT).json()
        assert d["ok"] and "zarezerwowana" in d["do_powiedzenia"]
        zgl = wizyty._wczytaj()["zgloszenia"][-1]
        assert zgl["zrodlo"] == "rezerwacja" and "asystenta głosowego" in zgl["wiadomosc"]
        assert any(do == ["zenobiusz@klient.test"] for do, _, _ in k.wyslane)
        # ten sam termin drugi raz: agent dostaje zwykla odpowiedz do przeczytania
        d2 = _post(k, "rezerwacja", kancelaria_id=1, data=_jutro(), godzina="10:00",
                   **{**KLIENT, "email": "inny@klient.test"}).json()
        assert d2["ok"] is False and "zajął" in d2["do_powiedzenia"]

    def test_rezerwacja_bez_emaila_i_bez_zgody(self, k):
        d = _post(k, "rezerwacja", kancelaria_id=1, data=_jutro(), godzina="10:00", **{**KLIENT, "email": ""}).json()
        assert d["ok"] is False and "e-mail" in d["do_powiedzenia"]
        d = _post(k, "rezerwacja", kancelaria_id=1, data=_jutro(), godzina="10:00", **{**KLIENT, "zgoda": False}).json()
        assert d["ok"] is False and "zgoda" in d["do_powiedzenia"].lower()


class TestZgloszenie:
    def test_do_wybranej_kancelarii(self, k):
        d = _post(k, "zgloszenie", kancelaria_id=2, termin="w przyszłym tygodniu", **KLIENT).json()
        assert d["ok"] and "Jan Obcy" in d["do_powiedzenia"]
        assert wizyty._wczytaj()["zgloszenia"][-1]["zrodlo"] == "agent_glosowy"

    def test_dowolna_kancelaria_w_miejscowosci(self, k):
        d = _post(k, "zgloszenie", miejscowosc="Puławy", **KLIENT).json()
        assert d["ok"] and "Puławy" in d["do_powiedzenia"]

    def test_bez_kontaktu(self, k):
        d = _post(k, "zgloszenie", kancelaria_id=2, **{**KLIENT, "telefon": "", "email": ""}).json()
        assert d["ok"] is False and "telefon albo e-mail" in d["do_powiedzenia"]

    def test_limit_zapisow_na_rozmowe(self, k):
        for _ in range(3):
            assert _post(k, "zgloszenie", kancelaria_id=2, **KLIENT).json()["ok"]
        assert _post(k, "zgloszenie", kancelaria_id=2, **KLIENT).status_code == 429
        # inna rozmowa ma wlasny limit
        odp = k.post("/api/agent-glosowy/zgloszenie", json={"rozmowa": "conv_inna", "kancelaria_id": 2, **KLIENT})
        assert odp.json()["ok"]


class TestKontaktNotarai:
    def test_prosba_kancelarii_idzie_mailem_do_zespolu(self, k):
        d = _post(k, "kontakt-notarai", imie="Anna Notariusz", kancelaria="KN Anna Notariusz",
                  telefon="601 000 000", temat="demo i cena", zgoda=True).json()
        assert d["ok"]
        do, temat, tresc = k.wyslane[-1]
        assert do == ["zgloszenia@notarai.test", "admin@notarai.test"] and "demo i cena" in tresc

    def test_bez_zgody(self, k):
        d = _post(k, "kontakt-notarai", imie="Anna", telefon="601 000 000").json()
        assert d["ok"] is False and not k.wyslane


class TestDostep:
    def test_token_wymagany_gdy_ustawiony(self, k, monkeypatch):
        monkeypatch.setattr(ag, "TOKEN", "tajny-token-agenta-123")
        assert _post(k, "koszt", czynnosc="testament").status_code == 401
        odp = k.post("/api/agent-glosowy/koszt", json={"czynnosc": "testament"},
                     headers={"X-Notarai-Agent": "tajny-token-agenta-123"})
        assert odp.status_code == 200
        assert k.get("/api/agent-glosowy").json()["token_wymagany"] is True

    def test_trasy_otwarte_w_trybie_saas(self, k, monkeypatch):
        monkeypatch.setattr(autoryzacja, "MULTI", True)
        assert _post(k, "koszt", czynnosc="testament").status_code == 200

    def test_dane_klienta_nie_trafiaja_do_logow(self, k, caplog):
        with caplog.at_level(logging.DEBUG):
            _post(k, "zgloszenie", kancelaria_id=2, **KLIENT)
            _post(k, "rezerwacja", kancelaria_id=1, data=_jutro(), godzina="11:00", **KLIENT)
        tekst = caplog.text
        for wartosc in ("Zenobiusz", "600 700 800", "zenobiusz@klient.test", "zakup mieszkania"):
            assert wartosc not in tekst
