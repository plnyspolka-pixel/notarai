"""SMS przez Twilio: normalizacja numerow, hamulec, tryb testowy i atrapa
transportu HTTP. Zadna wiadomosc nie wychodzi, numery sa fikcyjne."""
import logging

import httpx
import pytest

import sms


@pytest.fixture(autouse=True)
def czysto(monkeypatch):
    sms.wyczysc()
    monkeypatch.setattr(sms, "NA_NUMER_GODZINA", 5)
    monkeypatch.setattr(sms, "NA_DOBE", 2000)
    yield
    sms.wyczysc()


class TestNumery:
    def test_polskie_zapisy(self):
        assert sms.normalizuj_numer("600 000 000") == "+48600000000"
        assert sms.normalizuj_numer("+48 600-000-000") == "+48600000000"
        assert sms.normalizuj_numer("48600000000") == "+48600000000"
        assert sms.normalizuj_numer("0048600000000") == "+48600000000"

    def test_zagraniczne_i_zle(self):
        assert sms.normalizuj_numer("+49 30 1234567") == "+49301234567"
        assert sms.normalizuj_numer("12345") is None
        assert sms.normalizuj_numer("") is None
        assert sms.normalizuj_numer("6000000001") is None   # 10 cyfr bez prefiksu

    def test_koncowka_i_skrot(self):
        assert sms.koncowka("+48600000123") == "123"
        assert sms.skrot("600 000 000") == sms.skrot("+48600000000")
        assert sms.skrot("600 000 000") != sms.skrot("600 000 001")
        assert len(sms.kod_weryfikacyjny()) == 6 and sms.kod_weryfikacyjny().isdigit()

    def test_bez_ogonkow(self):
        assert sms.bez_ogonkow("Zażółć gęślą jaźń") == "Zazolc gesla jazn"


class TestTrybTestowy:
    def test_wylaczony_domyslnie(self, monkeypatch):
        monkeypatch.setattr(sms, "TRYB", "wylaczony")
        assert not sms.wlaczone()
        assert sms.wyslij("600000000", "x")["powod"] == "wylaczone"

    def test_test_odklada_wiadomosc(self, monkeypatch):
        monkeypatch.setattr(sms, "TRYB", "test")
        wynik = sms.wyslij("600 000 000", "notarai: Twój kod 123456", sms.KRYTYCZNY)
        assert wynik["wyslano"] and wynik["tryb"] == "test"
        assert sms.wyslane_testowo == [{"numer": "+48600000000", "tresc": "notarai: Twoj kod 123456",
                                        "kategoria": "krytyczny"}]

    def test_limit_na_numer(self, monkeypatch):
        monkeypatch.setattr(sms, "TRYB", "test")
        for _ in range(5):
            assert sms.wyslij("600000000", "kod")["wyslano"]
        assert sms.wyslij("600000000", "kod")["powod"] == "limit_numeru"
        assert sms.wyslij("600000001", "kod")["wyslano"]

    def test_automatyczne_okno_i_powtorka(self, monkeypatch):
        monkeypatch.setattr(sms, "TRYB", "test")
        monkeypatch.setattr(sms, "w_oknie", lambda teraz=None: False)
        assert sms.wyslij("600000000", "przypomnienie", sms.AUTOMATYCZNY)["powod"] == "poza_oknem"
        monkeypatch.setattr(sms, "w_oknie", lambda teraz=None: True)
        assert sms.wyslij("600000000", "przypomnienie", sms.AUTOMATYCZNY)["wyslano"]
        assert sms.wyslij("600000000", "Przypomnienie!", sms.AUTOMATYCZNY)["powod"] == "powtorka"
        assert sms.wyslij("600000000", "inna tresc", sms.AUTOMATYCZNY)["wyslano"]

    def test_wypisany_dostaje_tylko_krytyczne(self, monkeypatch):
        monkeypatch.setattr(sms, "TRYB", "test")
        monkeypatch.setattr(sms, "w_oknie", lambda teraz=None: True)
        assert sms.wyslij("600000000", "przypomnienie", sms.AUTOMATYCZNY, wypisany=True)["powod"] == "wypisany"
        assert sms.wyslij("600000000", "kod", sms.KRYTYCZNY, wypisany=True)["wyslano"]

    def test_zly_numer_i_pusta_tresc(self, monkeypatch):
        monkeypatch.setattr(sms, "TRYB", "test")
        assert sms.wyslij("123", "kod")["powod"] == "zly_numer"
        assert sms.wyslij("600000000", "   ")["powod"] == "pusta_tresc"

    def test_stop(self):
        assert sms.stop_w_tresci("STOP") and sms.stop_w_tresci(" wypisz mnie")
        assert not sms.stop_w_tresci("dziekuje, bede")


class TestTwilio:
    @pytest.fixture
    def twilio(self, monkeypatch):
        zadania = []

        def odpowiedz(zadanie: httpx.Request) -> httpx.Response:
            zadania.append(zadanie)
            if b"To=%2B48600000999" in zadanie.content:
                return httpx.Response(400, json={"code": 21211, "message": "Invalid 'To' Phone Number"})
            return httpx.Response(201, json={"sid": "SM123", "status": "queued"})
        monkeypatch.setattr(sms, "TRYB", "twilio")
        monkeypatch.setattr(sms, "KONTO", "ACtest")
        monkeypatch.setattr(sms, "TOKEN", "sekret")
        monkeypatch.setattr(sms, "KLUCZ_SID", "")
        monkeypatch.setattr(sms, "KLUCZ_SEKRET", "")
        monkeypatch.setattr(sms, "NADAWCA", "+48700000000")
        monkeypatch.setattr(sms, "USLUGA", "")
        monkeypatch.setattr(sms, "_transport", httpx.MockTransport(odpowiedz))
        return zadania

    def test_gotowe(self, monkeypatch, twilio):
        assert sms.gotowe() == ""
        monkeypatch.setattr(sms, "NADAWCA", "")
        assert "PIECZAPP_TWILIO_NUMER" in sms.gotowe()
        monkeypatch.setattr(sms, "KONTO", "")
        assert "ACCOUNT_SID" in sms.gotowe()

    def test_wysylka(self, twilio, caplog):
        caplog.set_level(logging.INFO)
        wynik = sms.wyslij("600 000 000", "notarai: kod 123456", sms.KRYTYCZNY)
        assert wynik == {"wyslano": True, "powod": "", "sid": "SM123"}
        zadanie = twilio[0]
        assert zadanie.url.path == "/2010-04-01/Accounts/ACtest/Messages.json"
        assert zadanie.headers["authorization"].startswith("Basic ")
        assert b"From=%2B48700000000" in zadanie.content and b"To=%2B48600000000" in zadanie.content
        assert b"Body=notarai%3A+kod+123456" in zadanie.content
        # numer i tresc nie trafiaja do logow
        assert "600000000" not in caplog.text and "123456" not in caplog.text and "SM123" in caplog.text

    def test_messaging_service_zamiast_numeru(self, monkeypatch, twilio):
        monkeypatch.setattr(sms, "USLUGA", "MGabc")
        assert sms.wyslij("600000000", "kod")["wyslano"]
        assert b"MessagingServiceSid=MGabc" in twilio[0].content and b"From=" not in twilio[0].content

    def test_blad_twilio(self, twilio, caplog):
        caplog.set_level(logging.INFO)
        wynik = sms.wyslij("600000999", "kod")
        assert wynik["powod"] == "blad_twilio" and wynik["http"] == 400 and wynik["kod"] == "21211"
        assert "600000999" not in caplog.text

    def test_blad_sieci(self, monkeypatch, twilio):
        def pad(zadanie):
            raise httpx.ConnectError("brak sieci")
        monkeypatch.setattr(sms, "_transport", httpx.MockTransport(pad))
        assert sms.wyslij("600000000", "kod")["powod"] == "blad_sieci"
