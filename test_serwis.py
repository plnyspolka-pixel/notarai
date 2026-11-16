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
    assert historia[0]["uzyli"][0]["sprawy"] == [] and historia[0]["uzyli"][0]["zmiany"] is False


def test_kancelaria_widzi_zakres_dostepu(srodowisko):
    """Ktore sprawy obsluga otworzyla, jakie dane i czy cos zmieniala."""
    klient, k, aut = srodowisko
    klient.post("/api/serwis", headers=jako(WLASCICIEL, k), json={})
    klient.get("/api/sprawy/7f3a91c2/plik", headers=serwisant(k))
    klient.get("/api/sprawy/7f3a91c2", headers=serwisant(k))
    klient.put("/api/kalendarz/1", headers=serwisant(k), json={})
    osoba = klient.get("/api/serwis", headers=jako(WLASCICIEL, k)).json()["historia"][0]["uzyli"][0]
    assert osoba["sprawy"] == ["7f3a91c2"]
    assert osoba["obszary"] == ["sprawy", "kalendarz"]
    assert osoba["zmiany"] is True


def test_odmowa_nie_poszerza_zakresu(srodowisko):
    klient, k, _ = srodowisko
    klient.post("/api/serwis", headers=jako(WLASCICIEL, k), json={})
    klient.post("/api/zespol", headers=serwisant(k), json={"email": "x@y.test"})
    assert klient.get("/api/serwis", headers=jako(WLASCICIEL, k)).json()["historia"][0]["uzyli"] == []


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
                          ("post", "/api/zespol"), ("get", "/api/kredyty"), ("post", "/api/kredyty/pakiet"),
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


# --- dziennik nie do nadpisania -------------------------------------------------


@pytest.fixture
def dziennik(srodowisko):
    import dziennik_serwisu
    importlib.reload(dziennik_serwisu)
    return dziennik_serwisu


def test_kazde_zdarzenie_serwisu_trafia_do_dziennika(srodowisko, dziennik, caplog):
    klient, k, _ = srodowisko
    with caplog.at_level("INFO", logger="pieczapp.serwis"):
        klient.post("/api/serwis", headers=jako(WLASCICIEL, k), json={"godziny": 2})
        klient.get("/api/sprawy", headers=serwisant(k))
        klient.get("/api/sprawy", headers=serwisant(k))            # nic nowego - bez wpisu
        klient.get("/api/sprawy/7f3a91c2", headers=serwisant(k))   # nowa sprawa - wpis
        klient.delete("/api/serwis", headers=jako(WLASCICIEL, k))
    odp = klient.get("/api/admin/serwis/dziennik", headers=ADMIN).json()
    assert [w["rodzaj"] for w in odp["wpisy"]] == ["wlaczono", "wejscie", "zakres", "odwolano"]
    assert odp["wpisy"][2]["sprawa"] == "7f3a91c2" and odp["wpisy"][1]["kto"] == SERWISANT
    assert odp["sprawdzenie"]["caly"] is True and odp["sprawdzenie"]["wpisow"] == 4
    swiadkowie = [r.getMessage() for r in caplog.records if r.getMessage().startswith("serwis-dziennik")]
    assert len(swiadkowie) == 4
    assert "@" not in "".join(swiadkowie)
    assert not any(c.isdigit() for s in swiadkowie for c in s.split("skrot=")[1])


def test_dziennik_dostepny_tylko_dla_administratora(srodowisko, dziennik):
    klient, k, _ = srodowisko
    assert klient.get("/api/admin/serwis/dziennik", headers=jako(WLASCICIEL, k)).status_code == 401


def test_zmiana_albo_usuniecie_wpisu_zrywa_lancuch(srodowisko, dziennik):
    klient, k, _ = srodowisko
    klient.post("/api/serwis", headers=jako(WLASCICIEL, k), json={})
    klient.get("/api/sprawy/7f3a91c2", headers=serwisant(k))
    klient.delete("/api/serwis", headers=jako(WLASCICIEL, k))
    lista = dziennik.wpisy()
    assert dziennik.sprawdz(lista)["caly"]
    zmieniona = [dict(w) for w in lista]
    zmieniona[1]["sprawa"] = "inna"
    assert not dziennik.sprawdz(zmieniona)["caly"]
    assert not dziennik.sprawdz([lista[0], lista[2]])["caly"]
    assert not dziennik.sprawdz(lista[1:])["caly"]


def test_wpisu_nie_da_sie_nadpisac(srodowisko, dziennik):
    klient, k, _ = srodowisko
    klient.post("/api/serwis", headers=jako(WLASCICIEL, k), json={})
    assert dziennik._zapisz_nowy(1, {"nr": 1}) is False
    assert dziennik.wpisy()[0]["rodzaj"] == "wlaczono"


def test_bez_wpisu_w_dzienniku_administrator_nie_wchodzi(srodowisko, dziennik, monkeypatch):
    klient, k, aut = srodowisko
    klient.post("/api/serwis", headers=jako(WLASCICIEL, k), json={})

    def awaria(*a, **kw):
        raise OSError("dysk")
    monkeypatch.setattr(dziennik, "_zapisz_nowy", awaria)
    assert klient.get("/api/sprawy", headers=serwisant(k)).status_code == 403
    assert klient.get("/api/serwis", headers=jako(WLASCICIEL, k)).json()["historia"][0]["uzyli"] == []
    # wlaczenie tez wymaga wpisu, odwolanie - nie
    assert klient.post("/api/serwis", headers=jako(WLASCICIEL, k), json={}).status_code == 503
    assert klient.delete("/api/serwis", headers=jako(WLASCICIEL, k)).json()["wlaczony"] is False
