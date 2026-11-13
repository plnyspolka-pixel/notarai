"""Platnosci za kredyty przez Finance You (konto TPay Fundacji): zamowienie,
uzgodnienie stanu, ping, zwrot, kwoty. Abonamentu nie ma - kancelaria placi
wylacznie kredytami. Bez sieci: Finance You zastapiony atrapa. Kancelaria
i adresy fikcyjne."""
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
TOKEN = "token-partnera-0123456789"


# --- kwoty i adres -----------------------------------------------------------

def test_zwolnienie_z_vat_domyslnie(monkeypatch):
    """Fundacja jest zwolniona podmiotowo - cena pakietu to kwota do zaplaty."""
    monkeypatch.delenv("PIECZAPP_VAT", raising=False)
    assert importlib.reload(platnosci).VAT == 0
    assert platnosci.brutto(450) == Decimal("450.00")


def test_brutto_po_utracie_zwolnienia(monkeypatch):
    monkeypatch.setattr(platnosci, "VAT", Decimal("0.23"))
    assert platnosci.brutto(100) == Decimal("123.00")
    assert platnosci.brutto(450) == Decimal("553.50")


def test_adres_do_faktury():
    assert platnosci.adres_nabywcy("ul. Testowa 1/2, 00-001 Warszawa") == {
        "ulica": "ul. Testowa 1/2", "kod": "00-001", "miasto": "Warszawa"}
    assert platnosci.adres_nabywcy("Rynek 5") == {"ulica": "Rynek 5", "kod": None, "miasto": None}
    assert platnosci.adres_nabywcy("") == {"ulica": None, "kod": None, "miasto": None}


# --- atrapa Finance You --------------------------------------------------------

@pytest.fixture
def finyou(monkeypatch):
    """Atrapa endpointu partnerskiego Finance You. `stan["zamowienia"]` mozna
    zmieniac w tescie (np. oplacic albo zwrocic)."""
    monkeypatch.setenv("PIECZAPP_FINYOU_URL", "https://finyou.test")
    monkeypatch.setenv("PIECZAPP_FINYOU_TOKEN", TOKEN)
    monkeypatch.setattr(platnosci, "ADRES", "https://app.notarai.test")
    stan = {"zadania": [], "zamowienia": {}}

    def obsluz(z: httpx.Request):
        stan["zadania"].append(z)
        if z.headers.get("authorization") != f"Bearer {TOKEN}":
            return httpx.Response(401, json={"ok": False})
        if z.method == "POST":
            dane = json.loads(z.content)
            stan["zamowienia"][dane["zamowienie"]] = {
                "ok": True, "zamowienie": dane["zamowienie"], "status": "pending", "kredyty": dane["kredyty"],
                "kwota_grosz": dane["kwota_grosz"], "zaplacono_grosz": None, "oplacono": None,
                "transakcja": "TR-ABC-1", "faktura": None, "adres": "https://secure.tpay.test/?title=TR-ABC-1"}
            stan["ostatnie"] = dane
            return httpx.Response(201, json=stan["zamowienia"][dane["zamowienie"]])
        ref = z.url.params.get("zamowienie")
        if ref not in stan["zamowienia"]:
            return httpx.Response(404, json={"ok": False})
        return httpx.Response(200, json=stan["zamowienia"][ref])

    monkeypatch.setattr(platnosci, "_klient", lambda: httpx.Client(
        base_url=platnosci.finyou_adres(), transport=httpx.MockTransport(obsluz),
        headers={"Authorization": "Bearer " + platnosci.finyou_token()}))
    return stan


def oplac(stan, ref, grosze=None, faktura="FV/1/11/2026"):
    z = stan["zamowienia"][ref]
    z.update(status="paid", zaplacono_grosz=grosze or z["kwota_grosz"], oplacono="2026-11-13T10:01:00Z",
             faktura=faktura, adres=None)


def test_zamowienie_w_finyou(finyou, caplog):
    with caplog.at_level(logging.INFO):
        wynik = platnosci.utworz_zamowienie("sobczak:ab12cd34", 500, Decimal("450.00"), "Pakiet 500 kredytow",
                                            {"nazwa": "Kancelaria Sobczak", "email": WLASCICIEL})
    assert wynik["adres"].startswith("https://secure.tpay.test/")
    d = finyou["ostatnie"]
    assert d["kwota_grosz"] == 45000 and d["kredyty"] == 500 and d["zamowienie"] == "sobczak:ab12cd34"
    assert d["powrot_ok"] == "https://app.notarai.test/?kredyty=ok"
    assert d["powiadomienie"] == "https://app.notarai.test/api/finyou/platnosc"
    assert WLASCICIEL not in caplog.text and TOKEN not in caplog.text


def test_bez_konfiguracji_nie_ma_platnosci(monkeypatch):
    monkeypatch.delenv("PIECZAPP_FINYOU_TOKEN", raising=False)
    assert platnosci.wlaczone() is False
    with pytest.raises(platnosci.BladPlatnosci):
        platnosci.utworz_zamowienie("k:abcd", 1, Decimal("1"), "opis", {})


def test_odrzucenie_bez_danych_w_logach(finyou, monkeypatch, caplog):
    odpowiedz = httpx.Response(400, json={"ok": False, "error": f"Nieprawidlowy e-mail {WLASCICIEL}"})
    monkeypatch.setattr(platnosci, "_klient", lambda: httpx.Client(
        base_url="https://finyou.test", transport=httpx.MockTransport(lambda z: odpowiedz)))
    with caplog.at_level(logging.INFO), pytest.raises(platnosci.BladPlatnosci):
        platnosci.utworz_zamowienie("k:abcd", 1, Decimal("1"), "opis", {})
    assert "HTTP 400" in caplog.text and WLASCICIEL not in caplog.text


def test_finyou_nieosiagalny(finyou, monkeypatch):
    def awaria(z):
        raise httpx.ConnectError("brak sieci")
    monkeypatch.setattr(platnosci, "_klient", lambda: httpx.Client(
        base_url="https://finyou.test", transport=httpx.MockTransport(awaria)))
    with pytest.raises(platnosci.BladPlatnosci):
        platnosci.pobierz_zamowienie("k:abcd")


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
    app = FastAPI()
    app.middleware("http")(autoryzacja.middleware)
    for r in (autoryzacja.router, autoryzacja.router_logowania, autoryzacja.router_zespolu,
              tokenomia.router, tokenomia.router_admina, tokenomia.router_platnosci):
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


def _ping(klient, id_k, numer):
    return klient.post("/api/finyou/platnosc", json={"zamowienie": f"{id_k}:{numer}"})


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


def test_zakup_pakietu_od_zamowienia_do_kredytow(serwer, finyou):
    import tokenomia
    klient, id_k = serwer
    numer = _kup(klient, id_k)
    d = finyou["ostatnie"]
    assert d["nabywca"] == {"nazwa": "Sobczak", "email": WLASCICIEL, "nip": "1234563218",
                            "ulica": "ul. Testowa 1", "kod": "00-001", "miasto": "Warszawa"}
    assert d["opis"].startswith("Bon jednego przeznaczenia - pakiet 500 kredytów")
    przed = _saldo(klient, id_k)
    _ping(klient, id_k, numer)                                # jeszcze nie zaplacone
    assert _saldo(klient, id_k) == przed
    oplac(finyou, f"{id_k}:{numer}")
    assert _ping(klient, id_k, numer).json()["uzgodniono"] is True
    assert _saldo(klient, id_k) == przed + 500
    widok = klient.get("/api/kredyty", headers=jako(WLASCICIEL, id_k)).json()
    zakup = widok["zakupy"][-1]
    assert (zakup["status"], zakup["brutto"], zakup["faktura"]) == ("oplacone", "450.00", "FV/1/11/2026")
    assert widok["moge_kupic"] is True and widok["pakiety"]["500"]["brutto_zl"] == 450.0
    assert tokenomia.wczytaj_portfel(id_k)["zamowienia"][numer]["tytul"] == "TR-ABC-1"


def test_powtorzony_ping_liczy_sie_raz(serwer, finyou):
    klient, id_k = serwer
    numer = _kup(klient, id_k, "100")
    przed = _saldo(klient, id_k)
    oplac(finyou, f"{id_k}:{numer}")
    for _ in range(3):
        _ping(klient, id_k, numer)
    assert _saldo(klient, id_k) == przed + 100


def test_zgubiony_ping_uzgadnia_okno_kredytow(serwer, finyou):
    klient, id_k = serwer
    numer = _kup(klient, id_k, "100")
    przed = _saldo(klient, id_k)
    oplac(finyou, f"{id_k}:{numer}")
    assert _saldo(klient, id_k) == przed + 100                # sam odczyt /api/kredyty


def test_falszywy_ping_niczego_nie_dopisuje(serwer, finyou):
    """Ping jest otwarty, ale nic nie przesadza - stan daje Finance You."""
    klient, id_k = serwer
    numer = _kup(klient, id_k)
    przed = _saldo(klient, id_k)
    for cialo in ({"zamowienie": f"{id_k}:{numer}"}, {"zamowienie": f"{id_k}:nie-ma"}, {"zamowienie": "x"}):
        assert klient.post("/api/finyou/platnosc", json=cialo).status_code == 200
    assert _saldo(klient, id_k) == przed


def test_inna_kwota_w_finyou_nie_dopisuje(serwer, finyou):
    klient, id_k = serwer
    numer = _kup(klient, id_k)
    przed = _saldo(klient, id_k)
    oplac(finyou, f"{id_k}:{numer}", grosze=100)
    _ping(klient, id_k, numer)
    assert _saldo(klient, id_k) == przed


def test_zwrot_odbiera_kredyty_raz(serwer, finyou):
    klient, id_k = serwer
    numer = _kup(klient, id_k, "100")
    przed = _saldo(klient, id_k)
    oplac(finyou, f"{id_k}:{numer}")
    _ping(klient, id_k, numer)
    finyou["zamowienia"][f"{id_k}:{numer}"]["status"] = "refunded"
    for _ in range(2):
        _ping(klient, id_k, numer)
    assert _saldo(klient, id_k) == przed


def test_nieudana_transakcja_oznacza_zamowienie(serwer, finyou):
    import tokenomia
    klient, id_k = serwer
    numer = _kup(klient, id_k, "100")
    finyou["zamowienia"][f"{id_k}:{numer}"]["status"] = "failed"
    _ping(klient, id_k, numer)
    assert tokenomia.wczytaj_portfel(id_k)["zamowienia"][numer]["status"] == "blad"


def test_pakiet_kupuje_tylko_wlasciciel(serwer, finyou):
    klient, id_k = serwer
    assert klient.post("/api/kredyty/pakiet", headers=jako(CZLONEK, id_k), json={"pakiet": "500"}).status_code == 403
    assert klient.post("/api/kredyty/pakiet", headers=jako(WLASCICIEL, id_k), json={"pakiet": "zly"}).status_code == 400
    assert klient.get("/api/kredyty", headers=jako(CZLONEK, id_k)).json()["moge_kupic"] is False


def test_bez_konfiguracji_zakup_niedostepny(serwer, monkeypatch):
    klient, id_k = serwer
    monkeypatch.delenv("PIECZAPP_FINYOU_TOKEN", raising=False)
    assert klient.post("/api/kredyty/pakiet", headers=jako(WLASCICIEL, id_k), json={"pakiet": "500"}).status_code == 503


def test_blad_bramki_oznacza_zamowienie(serwer, finyou, monkeypatch):
    import tokenomia
    klient, id_k = serwer

    def odmowa(*a, **k):
        raise platnosci.BladPlatnosci("Bramka płatności nie przyjęła zlecenia.")
    monkeypatch.setattr(platnosci, "utworz_zamowienie", odmowa)
    assert klient.post("/api/kredyty/pakiet", headers=jako(WLASCICIEL, id_k), json={"pakiet": "100"}).status_code == 502
    assert [z["status"] for z in tokenomia.wczytaj_portfel(id_k)["zamowienia"].values()] == ["blad"]


def test_sprzedaz_dla_admina(serwer, finyou):
    klient, id_k = serwer
    numer = _kup(klient, id_k)
    oplac(finyou, f"{id_k}:{numer}")
    _ping(klient, id_k, numer)
    assert klient.get("/api/admin/sprzedaz", headers=jako(WLASCICIEL, id_k)).status_code in (401, 403)
    w = klient.get("/api/admin/sprzedaz", headers=ADMIN).json()["sprzedaz"]
    assert len(w) == 1
    assert (w[0]["netto"], w[0]["vat"], w[0]["brutto"]) == ("450.00", "0.00", "450.00")
    assert "art. 113 ust. 1" in w[0]["adnotacja"] and w[0]["faktura"] == "FV/1/11/2026"
    assert w[0]["nip"] == "1234563218" and w[0]["email"] == WLASCICIEL
    assert w[0]["pozycja"].startswith("Bon jednego przeznaczenia - pakiet 500 kredytów")
    assert w[0]["transakcja_tpay"] == "TR-ABC-1"
    assert klient.get("/api/admin/sprzedaz?miesiac=2000-01", headers=ADMIN).json()["sprzedaz"] == []


def test_lista_kancelarii_pokazuje_saldo(serwer):
    import tokenomia
    klient, id_k = serwer
    k = next(k for k in klient.get("/api/admin/kancelarie", headers=ADMIN).json() if k["id"] == id_k)
    assert k["kredyty"] == tokenomia.KREDYTY_PROBNE and "oplacono_do" not in k
