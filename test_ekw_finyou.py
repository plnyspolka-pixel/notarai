"""EKW przez Finance You (API partnerskie) - testy na atrapie klienta HTTP."""
import json

import pytest

import config
import ekw
import rejestry

KW = "WA4M/00160286/2"
PESEL = "44051401359"


class Odpowiedz:
    def __init__(self, status, dane=None):
        self.status_code, self._dane = status, dane

    def json(self):
        if self._dane is None:
            raise ValueError("brak JSON")
        return self._dane


def gotowa(**zmiany):
    dane = {
        "ok": True, "kw_number": KW, "status": "ready", "provider": "apify",
        "fetched_at": "2026-11-08T10:00:00.000Z", "error": None,
        "sections": {
            "okladka": {"label": "Okładka", "html": "<table/>", "empty": False,
                        "text": f"Numer księgi wieczystej | {KW}\nTyp księgi | NIERUCHOMOSC GRUNTOWA\n"
                                "Sąd rejonowy | SAD REJONOWY DLA WARSZAWY-MOKOTOWA W WARSZAWIE\n"
                                "Źródło treści | EKW przez Apify"},
            "dzial_1o": {"label": "Dział I-O — oznaczenie nieruchomości", "html": "<table/>", "empty": False,
                         "text": "Numer działki | 1\nObszar | 0,1234 HA"},
            "dzial_1s": {"label": "Dział I-Sp", "html": "<table/>", "empty": True, "text": "BRAK WPISÓW"},
            "dzial_2": {"label": "Dział II — własność", "html": "<table/>", "empty": False,
                        "text": f"Imię pierwsze | JAN\nNazwisko | TESTOWY\nPESEL | {PESEL}"},
            "dzial_3": {"label": "Dział III", "html": "<table/>", "empty": True, "text": "BRAK WPISÓW"},
            "dzial_4": {"label": "Dział IV — hipoteki", "html": "<table/>", "empty": False,
                        "text": "Suma | 300 000,00 ZŁ\nWierzyciel | BANK TESTOWY S.A."},
        },
    }
    dane.update(zmiany)
    return dane


class AtrapaFinyou:
    """Udaje /api/public/partner-kw: POST zleca, GET dopytuje."""

    def __init__(self, post=(200, None), gets=()):
        self.post_odp, self.gets, self.wywolania = post, list(gets), []

    def post(self, sciezka, json=None):
        self.wywolania.append(("POST", sciezka, json))
        return Odpowiedz(*self.post_odp)

    def get(self, sciezka, params=None):
        self.wywolania.append(("GET", sciezka, params))
        return Odpowiedz(*(self.gets.pop(0) if self.gets else (200, gotowa())))

    def close(self):
        self.wywolania.append(("CLOSE", "", None))


@pytest.fixture(autouse=True)
def srodowisko(monkeypatch, tmp_path):
    monkeypatch.setenv("PIECZAPP_FINYOU_URL", "https://finyou.test/")
    monkeypatch.setenv("PIECZAPP_FINYOU_TOKEN", "partner-token-testowy-1234")
    monkeypatch.delenv("PIECZAPP_APIFY_TOKEN", raising=False)
    monkeypatch.setattr(ekw, "ODSTEP_S", 0)
    monkeypatch.setattr(ekw, "ODSTEP_FINYOU_S", 0)
    monkeypatch.setattr(config, "SPRAWY", tmp_path)
    (tmp_path / "abc123").mkdir()


class TestWyborDostawcy:
    def test_finyou_ma_pierwszenstwo(self, monkeypatch):
        assert ekw.dostawca() == "finyou" and ekw.dostepne()
        monkeypatch.setenv("PIECZAPP_APIFY_TOKEN", "apify_api_x")
        assert ekw.dostawca() == "finyou"
        assert "Finance You" in ekw.zrodlo()

    def test_bez_finyou_zostaje_apify(self, monkeypatch):
        monkeypatch.delenv("PIECZAPP_FINYOU_TOKEN")
        assert ekw.dostawca() == ""
        monkeypatch.setenv("PIECZAPP_APIFY_TOKEN", "apify_api_x")
        assert ekw.dostawca() == "apify" and "Apify" in ekw.zrodlo()

    def test_pobierz_kieruje_do_finyou(self):
        k = AtrapaFinyou(post=(200, gotowa()))
        ksiega = ekw.pobierz(KW, k)
        assert ksiega["dostawca"] == "finyou"
        assert k.wywolania[0][:2] == ("POST", "/api/public/partner-kw")
        assert k.wywolania[0][2] == {"kw": KW, "wait_seconds": 50}
        assert ("CLOSE", "", None) not in k.wywolania


class TestPobierzFinyou:
    def test_gotowa_od_razu(self):
        ksiega = ekw.pobierz_finyou(KW, AtrapaFinyou(post=(200, gotowa())))
        assert ksiega["numer_kw"] == KW and ksiega["sad"].startswith("SAD REJONOWY") and ksiega["typ"] == "NIERUCHOMOSC GRUNTOWA"
        assert [d["oznaczenie"] for d in ksiega["dzialy"]] == ["I-O", "I-Sp", "II", "III", "IV"]
        assert ksiega["dzialy"][1]["pusty"] and ksiega["dzialy"][1]["tekst"] == "BRAK WPISÓW"
        assert PESEL in ksiega["dzialy"][2]["tekst"]
        assert "zrodlo pierwotne: apify" in ksiega["zrodlo"] and "Finance You" in ksiega["zrodlo"]

    def test_dopytuje_gdy_processing(self):
        k = AtrapaFinyou(post=(200, {"status": "processing", "kw_number": KW}),
                         gets=[(200, {"status": "processing", "kw_number": KW}), (200, gotowa(provider="easymkw"))])
        ksiega = ekw.pobierz_finyou(KW, k)
        assert [w[0] for w in k.wywolania] == ["POST", "GET", "GET"]
        assert k.wywolania[1][2] == {"kw": KW}
        assert "easymkw" in ksiega["zrodlo"]

    def test_przekroczony_czas_oczekiwania(self, monkeypatch):
        monkeypatch.setattr(ekw, "CZAS_S", 0)
        k = AtrapaFinyou(post=(200, {"status": "processing", "kw_number": KW}))
        with pytest.raises(ekw.BladEKW) as blad:
            ekw.pobierz_finyou(KW, k)
        assert blad.value.kod == "niedostepny" and "za chwile" in str(blad.value)

    def test_nie_znaleziono(self):
        with pytest.raises(ekw.BladEKW) as blad:
            ekw.pobierz_finyou(KW, AtrapaFinyou(post=(200, {"status": "not_found", "kw_number": KW})))
        assert blad.value.kod == "nie_znaleziono"

    def test_blad_dostawcy_z_powodem(self):
        odp = {"status": "error", "kw_number": KW, "error": "Apify: wyczerpany limit; EasyMKW: brak kredytow", "sections": None}
        with pytest.raises(ekw.BladEKW) as blad:
            ekw.pobierz_finyou(KW, AtrapaFinyou(post=(200, odp)))
        assert blad.value.kod == "niedostepny" and "brak kredytow" in str(blad.value)

    def test_odrzucony_token(self):
        with pytest.raises(ekw.BladEKW) as blad:
            ekw.pobierz_finyou(KW, AtrapaFinyou(post=(401, {"ok": False, "error": "unauthorized"})))
        assert blad.value.kod == "blad_tokenu"

    def test_inna_ksiega(self):
        with pytest.raises(ekw.BladEKW):
            ekw.pobierz_finyou(KW, AtrapaFinyou(post=(200, gotowa(kw_number="WA4M/00000001/1"))))

    def test_dzial_bez_tresci_i_bez_pustego(self):
        dane = gotowa()
        dane["sections"]["dzial_3"] = {"label": "III", "html": None, "text": None, "empty": False}
        with pytest.raises(ekw.BladEKW) as blad:
            ekw.pobierz_finyou(KW, AtrapaFinyou(post=(200, dane)))
        assert blad.value.kod == "niepelny" and "III" in str(blad.value)

    def test_bez_konfiguracji(self, monkeypatch):
        monkeypatch.delenv("PIECZAPP_FINYOU_URL")
        with pytest.raises(ekw.BladEKW) as blad:
            ekw.pobierz_finyou(KW, AtrapaFinyou())
        assert blad.value.kod == "brak_tokenu"


class TestZapisFinyou:
    def test_slad_wskazuje_finance_you(self):
        ksiega = ekw.pobierz_finyou(KW, AtrapaFinyou(post=(200, gotowa())))
        ekw.zapisz("abc123", ksiega)
        wpisy = rejestry.wczytaj_sprawdzenia("abc123")
        assert wpisy[0]["rejestr"] == "EKW" and wpisy[0]["status"] == "wpis"
        assert wpisy[0]["zrodlo"].startswith("Finance You") and PESEL not in json.dumps(wpisy)
        tekst = (config.SPRAWY / "abc123" / "ksiegi" / "WA4M_00160286_2.txt").read_text("utf-8")
        assert "Finance You" in tekst and "BANK TESTOWY" in tekst

    def test_wynik_bledu_ze_zrodlem_finyou(self):
        w = ekw.wynik_bledu(KW, ekw.BladEKW("niedostepny", "x"))
        assert w.zrodlo.startswith("Finance You")
