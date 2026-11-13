"""Bramka TPay: suma kontrolna powiadomienia, kwoty brutto, transakcja,
zakup pakietu kredytow od zamowienia do dopisania kredytow. Abonamentu nie
ma - kancelaria placi wylacznie kredytami. Bez sieci: TPay zastapiony
atrapa. Kancelaria i adresy fikcyjne."""
import hashlib
import importlib
import json
import logging
from decimal import Decimal

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import platnosci
from test_logowanie import AtrapaCognito, _przywroc_moduly, logowanie_atrapa  # noqa: F401

ADMIN = {"Authorization": "Bearer sekret-admina"}
WLASCICIEL = "anna@kancelaria-sobczak.test"
CZLONEK = "piotr@kancelaria-sobczak.test"
KOD = "kod-bezpieczenstwa-testowy"
KONFIGURACJA = {"CLIENT_ID": "01-klient", "CLIENT_SECRET": "sekret-api", "KOD_BEZPIECZENSTWA": KOD,
                "API": "https://api.tpay.test", "ADRES": "https://app.notarai.test"}


def md5sum(pola: dict, kod=KOD) -> str:
    return hashlib.md5((pola["id"] + pola["tr_id"] + pola["tr_amount"] + pola["tr_crc"] + kod).encode()).hexdigest()


def powiadomienie(crc: str, kwota: str, status="TRUE", kod=KOD, **inne) -> dict:
    pola = {"id": "12345", "tr_id": "TR-ABC-1", "tr_date": "2026-11-13 10:00:00", "tr_crc": crc,
            "tr_amount": kwota, "tr_paid": kwota, "tr_desc": "notarai", "tr_status": status,
            "tr_error": "none", "tr_email": WLASCICIEL, "test_mode": "0", **inne}
    pola["md5sum"] = md5sum(pola, kod)
    return pola


# --- kwoty i suma kontrolna --------------------------------------------------

def test_zwolnienie_z_vat_domyslnie():
    """Uslugodawca (Fundacja) jest zwolniony podmiotowo - cena pakietu to kwota do zaplaty."""
    import importlib
    assert importlib.reload(platnosci).VAT == 0
    assert platnosci.brutto(450) == Decimal("450.00")


def test_brutto_po_utracie_zwolnienia(monkeypatch):
    monkeypatch.setattr(platnosci, "VAT", Decimal("0.23"))
    assert platnosci.brutto(100) == Decimal("123.00")
    assert platnosci.brutto(450) == Decimal("553.50")
    assert platnosci.brutto("0.01") == Decimal("0.01")


def test_poprawna_suma_kontrolna():
    platnosci.sprawdz_powiadomienie(powiadomienie("k:1", "123.00"), KOD)


def test_zmieniona_kwota_odrzucona():
    pola = powiadomienie("k:1", "123.00")
    pola["tr_amount"] = "1.00"
    with pytest.raises(platnosci.BladPodpisu):
        platnosci.sprawdz_powiadomienie(pola, KOD)


def test_zmienione_zamowienie_odrzucone():
    pola = powiadomienie("k:1", "123.00")
    pola["tr_crc"] = "inna:2"
    with pytest.raises(platnosci.BladPodpisu):
        platnosci.sprawdz_powiadomienie(pola, KOD)


def test_obcy_kod_odrzucony():
    with pytest.raises(platnosci.BladPodpisu):
        platnosci.sprawdz_powiadomienie(powiadomienie("k:1", "123.00", kod="obcy"), KOD)


def test_bez_kodu_nic_nie_przechodzi():
    with pytest.raises(platnosci.BladPodpisu):
        platnosci.sprawdz_powiadomienie(powiadomienie("k:1", "123.00", kod=""), "")


def test_bez_sumy_odrzucone():
    pola = powiadomienie("k:1", "123.00")
    del pola["md5sum"]
    with pytest.raises(platnosci.BladPodpisu):
        platnosci.sprawdz_powiadomienie(pola, KOD)


# --- API TPay ----------------------------------------------------------------

@pytest.fixture
def tpay_atrapa(monkeypatch):
    """Atrapa TPay: token OAuth, nowa transakcja, odczyt transakcji."""
    for nazwa, wartosc in KONFIGURACJA.items():
        monkeypatch.setattr(platnosci, nazwa, wartosc)
    monkeypatch.setattr(platnosci, "_token", {"wartosc": "", "wygasa": 0.0})
    stan = {"zadania": [], "status": "correct"}

    def obsluz(zadanie: httpx.Request):
        stan["zadania"].append(zadanie)
        if zadanie.url.path == "/oauth/auth":
            return httpx.Response(200, json={"access_token": "tok-1", "expires_in": 7200, "token_type": "Bearer"})
        if zadanie.method == "POST" and zadanie.url.path == "/transactions":
            return httpx.Response(200, json={"result": "success", "status": "pending",
                                             "transactionId": "01TRANS", "title": "TR-ABC-1",
                                             "transactionPaymentUrl": "https://secure.tpay.test/?title=TR-ABC-1"})
        if zadanie.url.path == "/transactions/01TRANS":
            return httpx.Response(200, json={"result": "success", "transactionId": "01TRANS",
                                             "status": stan["status"]})
        return httpx.Response(404, json={"result": "failed"})

    monkeypatch.setattr(platnosci, "_klient", lambda: httpx.Client(transport=httpx.MockTransport(obsluz)))
    return stan


def test_transakcja_w_tpay(tpay_atrapa, caplog):
    with caplog.at_level(logging.INFO):
        wynik = platnosci.utworz_transakcje(Decimal("553.50"), "notarai - 500 kredytów", "sobczak:ab12",
                                            WLASCICIEL, "Kancelaria Sobczak")
    assert wynik == {"adres": "https://secure.tpay.test/?title=TR-ABC-1", "transakcja": "01TRANS",
                     "tytul": "TR-ABC-1"}
    token, transakcja = tpay_atrapa["zadania"]
    assert token.url.path == "/oauth/auth" and b"client_secret=sekret-api" in token.content
    assert transakcja.headers["authorization"] == "Bearer tok-1"
    dane = json.loads(transakcja.content)
    assert dane["amount"] == 553.5 and dane["hiddenDescription"] == "sobczak:ab12"
    assert dane["payer"] == {"email": WLASCICIEL, "name": "Kancelaria Sobczak"}
    assert dane["callbacks"]["notification"]["url"] == "https://app.notarai.test/api/tpay/powiadomienie"
    assert dane["callbacks"]["payerUrls"]["success"] == "https://app.notarai.test/?kredyty=ok"
    assert WLASCICIEL not in caplog.text and "sekret-api" not in caplog.text


def test_token_uzywany_ponownie(tpay_atrapa):
    platnosci.pobierz_transakcje("01TRANS")
    platnosci.pobierz_transakcje("01TRANS")
    assert [z.url.path for z in tpay_atrapa["zadania"]].count("/oauth/auth") == 1


def test_bez_konfiguracji_nie_ma_platnosci(monkeypatch):
    monkeypatch.setattr(platnosci, "KOD_BEZPIECZENSTWA", "")
    assert platnosci.wlaczone() is False
    with pytest.raises(platnosci.BladPlatnosci):
        platnosci.utworz_transakcje(Decimal("1"), "x", "k:1", WLASCICIEL, "")


def test_odrzucenie_bez_danych_w_logach(tpay_atrapa, monkeypatch, caplog):
    odpowiedz = httpx.Response(400, json={"result": "failed", "errors": [
        {"errorCode": "payer_email_invalid", "errorMessage": f"Invalid email {WLASCICIEL}"}]})

    def obsluz(z):
        if z.url.path == "/oauth/auth":
            return httpx.Response(200, json={"access_token": "t", "expires_in": 7200})
        return odpowiedz
    monkeypatch.setattr(platnosci, "_klient", lambda: httpx.Client(transport=httpx.MockTransport(obsluz)))
    with caplog.at_level(logging.INFO), pytest.raises(platnosci.BladPlatnosci):
        platnosci.utworz_transakcje(Decimal("1"), "x", "k:1", WLASCICIEL, "")
    assert "payer_email_invalid" in caplog.text and WLASCICIEL not in caplog.text


# --- serwer: zakup pakietu ------------------------------------------------------

@pytest.fixture
def serwer(logowanie_atrapa, monkeypatch, tmp_path):
    monkeypatch.setenv("PIECZAPP_MULTI", "true")
    monkeypatch.setenv("PIECZAPP_ADMIN_TOKEN", "sekret-admina")
    monkeypatch.setenv("PIECZAPP_MAGAZYN", "lokalny")
    import config
    import magazyn
    import autoryzacja
    import tokenomia
    importlib.reload(magazyn)
    importlib.reload(autoryzacja)
    monkeypatch.setattr(config, "DANE", tmp_path)
    monkeypatch.setattr(tokenomia, "WLACZONA", True)
    monkeypatch.setattr(autoryzacja.logowanie, "_klient", lambda: AtrapaCognito())
    monkeypatch.setattr(autoryzacja.logowanie, "dane_z_tokenu",
                        lambda t: {"email": t.split("|")[1], "kancelaria": t.split("|")[2]})
    monkeypatch.setattr(autoryzacja.logowanie, "czy_jwt", lambda t: t.startswith("jwt|"))
    for nazwa, wartosc in KONFIGURACJA.items():
        monkeypatch.setattr(platnosci, nazwa, wartosc)

    app = FastAPI()
    app.middleware("http")(autoryzacja.middleware)
    for r in (autoryzacja.router, autoryzacja.router_logowania, autoryzacja.router_zespolu,
              tokenomia.router, tokenomia.router_admina, tokenomia.router_tpay):
        app.include_router(r)

    @app.get("/api/sprawy")
    def sprawy():
        return []

    klient = TestClient(app)
    odp = klient.post("/api/admin/kancelarie", headers=ADMIN, json={"nazwa": "Sobczak"})
    assert odp.status_code == 201
    id_k = odp.json()["id"]
    # Tu sprawdzamy platnosci, nie zespol (test_zespol.py) ani akceptacje
    # umowy (test_rejestracja.py) - oba wpisujemy wprost do rejestru.
    rejestr = autoryzacja._wczytaj_rejestr()
    wpis = autoryzacja._znajdz(rejestr, id_k)[1]
    wpis["zespol"] = [{"email": e, "rola": r, "zaproszono": None, "dolaczyl": None}
                      for e, r in ((WLASCICIEL, "wlasciciel"), (CZLONEK, "czlonek"))]
    wpis["umowa"] = {"zaakceptowano": "2026-10-24T10:00:00"}
    wpis["dane"] = {"nip": "1234563218", "adres": "ul. Testowa 1, 00-001 Warszawa"}
    autoryzacja._zapisz_rejestr(rejestr)
    return klient, id_k


def jako(email, id_k):
    return {"Authorization": f"Bearer jwt|{email}|{id_k}"}


def _kup(klient, id_k, pakiet="500"):
    odp = klient.post("/api/kredyty/pakiet", headers=jako(WLASCICIEL, id_k), json={"pakiet": pakiet})
    assert odp.status_code == 201, odp.text
    return odp.json()["zamowienie"]


def _powiadom(klient, pola):
    return klient.post("/api/tpay/powiadomienie", data=pola)


def _saldo(klient, id_k):
    return klient.get("/api/kredyty", headers=jako(CZLONEK, id_k)).json()["saldo"]


def test_nowa_kancelaria_ma_kredyty_startowe_i_zadnego_abonamentu(serwer):
    import tokenomia
    klient, id_k = serwer
    assert _saldo(klient, id_k) == tokenomia.KREDYTY_PROBNE
    assert klient.get("/api/sprawy", headers=jako(CZLONEK, id_k)).status_code == 200
    assert klient.get("/api/abonament", headers=jako(WLASCICIEL, id_k)).status_code == 404


def test_bez_kredytow_sprawy_dalej_otwarte(serwer):
    """Brak kredytow blokuje tylko czynnosci platne (402 z tokenomii), nie dostep."""
    import tokenomia
    klient, id_k = serwer
    tokenomia.doladuj(id_k, -tokenomia.KREDYTY_PROBNE - 50, "test")
    assert klient.get("/api/sprawy", headers=jako(CZLONEK, id_k)).status_code == 200
    assert klient.get("/api/zespol", headers=jako(CZLONEK, id_k)).status_code == 200


def test_zakup_pakietu_od_zamowienia_do_kredytow(serwer, tpay_atrapa):
    import tokenomia
    klient, id_k = serwer
    numer = _kup(klient, id_k)
    przed = _saldo(klient, id_k)
    odp = _powiadom(klient, powiadomienie(f"{id_k}:{numer}", "450.00"))
    assert odp.status_code == 200 and odp.text == "TRUE"
    assert _saldo(klient, id_k) == przed + 500
    widok = klient.get("/api/kredyty", headers=jako(WLASCICIEL, id_k)).json()
    assert widok["zakupy"][-1]["status"] == "oplacone" and widok["zakupy"][-1]["brutto"] == "450.00"
    assert widok["moge_kupic"] is True and widok["pakiety"]["500"]["brutto_zl"] == 450.0
    portfel = tokenomia.wczytaj_portfel(id_k)
    assert portfel["zamowienia"][numer]["transakcja"] == "01TRANS"


def test_powtorzone_powiadomienie_liczy_sie_raz(serwer, tpay_atrapa):
    klient, id_k = serwer
    numer = _kup(klient, id_k, "100")
    przed = _saldo(klient, id_k)
    for _ in range(3):
        assert _powiadom(klient, powiadomienie(f"{id_k}:{numer}", "100.00")).text == "TRUE"
    assert _saldo(klient, id_k) == przed + 100


def test_falszywe_powiadomienie_odrzucone(serwer, tpay_atrapa):
    klient, id_k = serwer
    numer = _kup(klient, id_k)
    przed = _saldo(klient, id_k)
    odp = _powiadom(klient, powiadomienie(f"{id_k}:{numer}", "450.00", kod="zgadniety"))
    assert odp.status_code == 400 and _saldo(klient, id_k) == przed


def test_bez_potwierdzenia_z_tpay_nie_dopisujemy(serwer, tpay_atrapa):
    """Nawet z poprawna suma (np. wyciek kodu) kredyty wymagaja wplaty w TPay."""
    klient, id_k = serwer
    numer = _kup(klient, id_k)
    przed = _saldo(klient, id_k)
    tpay_atrapa["status"] = "pending"
    odp = _powiadom(klient, powiadomienie(f"{id_k}:{numer}", "450.00"))
    assert odp.status_code >= 400 and _saldo(klient, id_k) == przed
    tpay_atrapa["status"] = "correct"              # TPay ponawia - teraz wplata jest
    assert _powiadom(klient, powiadomienie(f"{id_k}:{numer}", "450.00")).text == "TRUE"
    assert _saldo(klient, id_k) == przed + 500


def test_kwota_nizsza_niz_cena_nie_dopisuje(serwer, tpay_atrapa):
    klient, id_k = serwer
    numer = _kup(klient, id_k)
    przed = _saldo(klient, id_k)
    assert _powiadom(klient, powiadomienie(f"{id_k}:{numer}", "1.00")).text == "TRUE"
    assert _saldo(klient, id_k) == przed


def test_nieznane_zamowienie_konczy_ponawianie(serwer, tpay_atrapa):
    klient, id_k = serwer
    odp = _powiadom(klient, powiadomienie(f"{id_k}:nie-ma", "123.00"))
    assert odp.status_code == 200 and odp.text == "TRUE"


def test_zwrot_odbiera_kredyty_raz(serwer, tpay_atrapa):
    klient, id_k = serwer
    numer = _kup(klient, id_k, "100")
    przed = _saldo(klient, id_k)
    _powiadom(klient, powiadomienie(f"{id_k}:{numer}", "100.00"))
    for _ in range(2):
        _powiadom(klient, powiadomienie(f"{id_k}:{numer}", "100.00", status="CHARGEBACK"))
    assert _saldo(klient, id_k) == przed


def test_pakiet_kupuje_tylko_wlasciciel(serwer, tpay_atrapa):
    klient, id_k = serwer
    assert klient.post("/api/kredyty/pakiet", headers=jako(CZLONEK, id_k), json={"pakiet": "500"}).status_code == 403
    assert klient.post("/api/kredyty/pakiet", headers=jako(WLASCICIEL, id_k), json={"pakiet": "zly"}).status_code == 400
    assert klient.get("/api/kredyty", headers=jako(CZLONEK, id_k)).json()["moge_kupic"] is False


def test_bez_konfiguracji_tpay_zakup_niedostepny(serwer, monkeypatch):
    klient, id_k = serwer
    monkeypatch.setattr(platnosci, "CLIENT_ID", "")
    assert klient.post("/api/kredyty/pakiet", headers=jako(WLASCICIEL, id_k), json={"pakiet": "500"}).status_code == 503


def test_blad_bramki_oznacza_zamowienie(serwer, monkeypatch):
    import tokenomia
    klient, id_k = serwer

    def odmowa(*a, **k):
        raise platnosci.BladPlatnosci("Bramka płatności nie przyjęła zlecenia.")
    monkeypatch.setattr(platnosci, "utworz_transakcje", odmowa)
    assert klient.post("/api/kredyty/pakiet", headers=jako(WLASCICIEL, id_k), json={"pakiet": "100"}).status_code == 502
    assert [z["status"] for z in tokenomia.wczytaj_portfel(id_k)["zamowienia"].values()] == ["blad"]


def test_sprzedaz_do_faktur_dla_admina(serwer, tpay_atrapa):
    klient, id_k = serwer
    numer = _kup(klient, id_k)
    _powiadom(klient, powiadomienie(f"{id_k}:{numer}", "450.00"))
    assert klient.get("/api/admin/sprzedaz", headers=jako(WLASCICIEL, id_k)).status_code in (401, 403)
    w = klient.get("/api/admin/sprzedaz", headers=ADMIN).json()["sprzedaz"]
    assert len(w) == 1
    assert (w[0]["netto"], w[0]["vat"], w[0]["brutto"]) == ("450.00", "0.00", "450.00")
    assert "art. 113 ust. 1" in w[0]["adnotacja"]
    assert w[0]["nip"] == "1234563218" and w[0]["email"] == WLASCICIEL
    assert w[0]["pozycja"].startswith("Bon jednego przeznaczenia - pakiet 500 kredytów")
    assert w[0]["transakcja_tpay"] == "TR-ABC-1"
    assert klient.get("/api/admin/sprzedaz?miesiac=2000-01", headers=ADMIN).json()["sprzedaz"] == []


def test_lista_kancelarii_pokazuje_saldo(serwer):
    import tokenomia
    klient, id_k = serwer
    k = next(k for k in klient.get("/api/admin/kancelarie", headers=ADMIN).json() if k["id"] == id_k)
    assert k["kredyty"] == tokenomia.KREDYTY_PROBNE and "oplacono_do" not in k
