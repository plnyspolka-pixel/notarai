"""Dostep serwisowy: jedyna droga administratora do spraw kancelarii.
Wlacza go wlasciciel kancelarii, na okreslony czas. Cognito zastapione
atrapa, bez sieci. Adresy fikcyjne."""
import importlib
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from test_logowanie import _przywroc_moduly, logowanie_atrapa  # noqa: F401
from test_zespol import ADMIN, AtrapaZespolu, jako

WLASCICIEL = "anna@kancelaria-sobczak.test"
CZLONEK = "jan@kancelaria-sobczak.test"
SERWISANT = "serwis@fundacja.test"


@pytest.fixture
def srodowisko(logowanie_atrapa, monkeypatch, tmp_path):
    atrapa = AtrapaZespolu()
    monkeypatch.setenv("PIECZAPP_MULTI", "true")
    monkeypatch.setenv("PIECZAPP_ADMIN_TOKEN", "sekret-admina")
    monkeypatch.setenv("PIECZAPP_MAGAZYN", "lokalny")
    monkeypatch.setenv("PIECZAPP_ADMINI", SERWISANT)
    import config
    import magazyn
    import autoryzacja
    importlib.reload(magazyn)
    importlib.reload(autoryzacja)
    monkeypatch.setattr(config, "DANE", tmp_path)
    monkeypatch.setattr(autoryzacja.logowanie, "_klient", lambda: atrapa)
    monkeypatch.setattr(autoryzacja.logowanie, "dane_z_tokenu",
                        lambda t: {"email": t.split("|")[1], "kancelaria": t.split("|")[2]})
    monkeypatch.setattr(autoryzacja.logowanie, "czy_jwt", lambda t: t.startswith("jwt|"))

    app = FastAPI()
    app.middleware("http")(autoryzacja.middleware)
    for r in (autoryzacja.router, autoryzacja.router_zespolu, autoryzacja.router_serwisu):
        app.include_router(r)

    @app.get("/api/sprawy")
    def sprawy():
        return {"kancelaria": magazyn.kancelaria_var.get()}

    klient = TestClient(app)
    k = klient.post("/api/admin/kancelarie", headers=ADMIN,
                    json={"nazwa": "Kancelaria Sobczak", "email": WLASCICIEL}).json()["id"]
    rejestr = autoryzacja._wczytaj_rejestr()
    wpis = autoryzacja._znajdz(rejestr, k)[1]
    wpis["zespol"].append({"email": CZLONEK, "rola": "czlonek", "zaproszono": None, "dolaczyl": None})
    wpis["umowa"] = {"zaakceptowano": "2026-10-24T10:00:00"}
    autoryzacja._zapisz_rejestr(rejestr)
    yield klient, k, autoryzacja
    monkeypatch.delenv("PIECZAPP_ADMINI", raising=False)


def serwisant(k, email=SERWISANT):
    return {**jako(email, "_administracja"), "X-Serwis-Kancelaria": k}


def test_bez_zgody_kancelarii_administrator_nie_wejdzie(srodowisko):
    klient, k, _ = srodowisko
    assert klient.get("/api/sprawy", headers=serwisant(k)).status_code == 403
    # ani tokenem awaryjnym, ani bez naglowka serwisu
    assert klient.get("/api/sprawy", headers=ADMIN).status_code == 401
    assert klient.get("/api/sprawy", headers=jako(SERWISANT, "_administracja")).status_code == 401


def test_wlasciciel_wlacza_i_administrator_widzi_tylko_te_kancelarie(srodowisko):
    klient, k, _ = srodowisko
    odp = klient.post("/api/serwis", headers=jako(WLASCICIEL, k), json={"godziny": 2})
    assert odp.status_code == 201 and odp.json()["wlaczony"] is True

    odp = klient.get("/api/sprawy", headers=serwisant(k))
    assert odp.status_code == 200 and odp.json()["kancelaria"] == k

    inna = klient.post("/api/admin/kancelarie", headers=ADMIN,
                       json={"nazwa": "Kancelaria Pawlak"}).json()["id"]
    assert klient.get("/api/sprawy", headers=serwisant(inna)).status_code == 403

    lista = klient.get("/api/admin/kancelarie", headers=ADMIN).json()
    assert next(x for x in lista if x["id"] == k)["serwis_do"]


def test_kancelaria_widzi_kto_skorzystal(srodowisko):
    klient, k, _ = srodowisko
    klient.post("/api/serwis", headers=jako(WLASCICIEL, k), json={"godziny": 2})
    klient.get("/api/sprawy", headers=serwisant(k))
    klient.get("/api/sprawy", headers=serwisant(k))
    historia = klient.get("/api/serwis", headers=jako(CZLONEK, k)).json()["historia"]
    assert historia[0]["wlaczyl"] == WLASCICIEL
    assert [u["email"] for u in historia[0]["uzyli"]] == [SERWISANT], "jedno wejscie na osobe"


def test_wlacza_i_odwoluje_tylko_wlasciciel(srodowisko):
    klient, k, _ = srodowisko
    assert klient.post("/api/serwis", headers=jako(CZLONEK, k), json={}).status_code == 403
    klient.post("/api/serwis", headers=jako(WLASCICIEL, k), json={})
    assert klient.delete("/api/serwis", headers=jako(CZLONEK, k)).status_code == 403
    assert klient.delete("/api/serwis", headers=jako(WLASCICIEL, k)).json()["wlaczony"] is False
    assert klient.get("/api/sprawy", headers=serwisant(k)).status_code == 403


def test_czas_dostepu_ograniczony(srodowisko):
    klient, k, _ = srodowisko
    for godziny in (0, 7 * 24 + 1):
        assert klient.post("/api/serwis", headers=jako(WLASCICIEL, k),
                           json={"godziny": godziny}).status_code == 400


def test_dostep_wygasa_sam(srodowisko):
    klient, k, aut = srodowisko
    klient.post("/api/serwis", headers=jako(WLASCICIEL, k), json={"godziny": 1})
    rejestr = aut._wczytaj_rejestr()
    wczoraj = (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds")
    aut._znajdz(rejestr, k)[1]["serwis"][-1]["do"] = wczoraj
    aut._zapisz_rejestr(rejestr)
    assert klient.get("/api/sprawy", headers=serwisant(k)).status_code == 403
    assert klient.get("/api/serwis", headers=jako(WLASCICIEL, k)).json()["wlaczony"] is False


def test_administrator_nie_przedluzy_sobie_dostepu(srodowisko):
    """Ani zespolu, ani dostepu serwisowego nie zmieni sie z jego wnetrza."""
    klient, k, _ = srodowisko
    klient.post("/api/serwis", headers=jako(WLASCICIEL, k), json={"godziny": 1})
    for metoda, adres in (("post", "/api/serwis"), ("get", "/api/zespol"),
                          ("post", "/api/zespol"), ("get", "/api/abonament"),
                          ("post", "/api/dokumenty/umowa"), ("get", "/api/pomocnik/zlecenia")):
        dodatki = {"json": {"godziny": 168}} if metoda == "post" else {}
        odp = getattr(klient, metoda)(adres, headers=serwisant(k), **dodatki)
        assert odp.status_code == 403, adres


def test_cudzy_uzytkownik_nie_udaje_serwisu(srodowisko):
    """Naglowek serwisu nic nie daje komus, kto nie jest administratorem."""
    klient, k, _ = srodowisko
    klient.post("/api/serwis", headers=jako(WLASCICIEL, k), json={})
    obcy = {**jako("ewa@kancelaria-pawlak.test", "kancelaria-pawlak"), "X-Serwis-Kancelaria": k}
    assert klient.get("/api/sprawy", headers=obcy).status_code == 403
    podszyty = {**jako("ewa@kancelaria-pawlak.test", "_administracja"), "X-Serwis-Kancelaria": k}
    assert klient.get("/api/sprawy", headers=podszyty).status_code == 403


def test_wylaczona_kancelaria_zamyka_dostep(srodowisko):
    klient, k, aut = srodowisko
    klient.post("/api/serwis", headers=jako(WLASCICIEL, k), json={})
    klient.delete(f"/api/admin/kancelarie/{k}", headers=ADMIN)
    assert klient.get("/api/sprawy", headers=serwisant(k)).status_code == 403
