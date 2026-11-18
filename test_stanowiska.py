"""Stanowiska w zespole: sekretariat, aplikant, notariusz.

Serwer odmawia (403) tego, czego stanowisko nie obejmuje - interfejs tylko
chowa przyciski. Wlasciciel i osoba bez stanowiska maja wszystko (zgodnosc
wstecz). Cognito zastapione atrapa (test_zespol), adresy fikcyjne.
"""
import pytest
from fastapi.testclient import TestClient

import stanowiska
from test_logowanie import _przywroc_moduly, logowanie_atrapa  # noqa: F401
from test_zespol import ADMIN, _kancelaria, jako, srodowisko  # noqa: F401

WLASCICIEL = "helena@kancelaria-pod7.test"
OSOBY = {"marta@kancelaria-pod7.test": "notariusz",
         "kuba@kancelaria-pod7.test": "aplikant",
         "basia@kancelaria-pod7.test": "sekretariat"}
SPRAWA = "abc123abc123"


class TestRegul:
    @pytest.mark.parametrize("metoda,sciezka,uprawnienie", [
        ("POST", "/api/sprawy", "sprawy_ai"),
        ("POST", "/api/odczyt", "sprawy_ai"),
        ("POST", f"/api/sprawy/{SPRAWA}/rozmowa", "sprawy_ai"),
        ("POST", f"/api/sprawy/{SPRAWA}/projekt", "projekt"),
        ("POST", "/api/projekt", "projekt"),
        ("POST", f"/api/sprawy/{SPRAWA}/krz", "rejestry"),
        ("POST", f"/api/sprawy/{SPRAWA}/sprawdzenia/decyzja", "rejestry"),
        ("DELETE", f"/api/sprawy/{SPRAWA}/pliki/zdjecie-1.jpg", "usun_plik"),
        ("DELETE", f"/api/sprawy/{SPRAWA}", "usun_sprawe"),
        ("GET", "/api/giif", "kancelaria"),
        ("POST", "/api/ksiegi-kancelarii/repertorium_a", "kancelaria"),
        ("PUT", "/api/personalizacja/zasady", "kancelaria"),
    ])
    def test_wymagane(self, metoda, sciezka, uprawnienie):
        assert stanowiska.wymagane(metoda, sciezka) == uprawnienie

    @pytest.mark.parametrize("metoda,sciezka", [
        ("GET", "/api/sprawy"), ("GET", f"/api/sprawy/{SPRAWA}"),
        ("GET", f"/api/sprawy/{SPRAWA}/plik"), ("GET", f"/api/sprawy/{SPRAWA}/projekt/stan"),
        ("POST", f"/api/sprawy/{SPRAWA}/pliki"), ("GET", f"/api/sprawy/{SPRAWA}/pliki/a.jpg"),
        ("POST", "/api/kalendarz"), ("PUT", "/api/kalendarz/x1"), ("DELETE", "/api/kalendarz/x1"),
        ("PUT", f"/api/sprawy/{SPRAWA}/sygnatura"), ("GET", "/api/ksiegi-kancelarii/repertorium_a"),
        ("GET", "/api/personalizacja/zasady"),
    ])
    def test_dla_kazdego_w_zespole(self, metoda, sciezka):
        assert stanowiska.wymagane(metoda, sciezka) is None

    def test_wlasciciel_i_bez_stanowiska_maja_wszystko(self):
        pelne = frozenset(stanowiska.WSZYSTKIE)
        assert stanowiska.uprawnienia({"rola": "wlasciciel", "stanowisko": "sekretariat"}) == pelne
        assert stanowiska.uprawnienia({"rola": "czlonek"}) == pelne
        assert stanowiska.uprawnienia(None) == pelne

    def test_nieznane_stanowisko_odrzucone(self):
        with pytest.raises(ValueError):
            stanowiska.sprawdz("prezes")
        assert stanowiska.sprawdz(" Aplikant ") == "aplikant"


@pytest.fixture
def zespol(srodowisko, monkeypatch):  # noqa: F811
    klient, atrapa = srodowisko
    import autoryzacja
    monkeypatch.setattr(autoryzacja, "umowa_zawarta", lambda kancelaria: True)
    app = klient.app
    # Atrapy tras spraw: liczy sie tylko, czy middleware wpusci zadanie.
    for metoda, sciezka in [("post", "/api/sprawy/{i}/projekt"), ("post", "/api/sprawy"),
                            ("delete", "/api/sprawy/{i}"), ("delete", "/api/sprawy/{i}/pliki/{n}"),
                            ("post", "/api/sprawy/{i}/pliki"), ("post", "/api/kalendarz"),
                            ("get", "/api/sprawy/{i}"), ("post", "/api/sprawy/{i}/krz"),
                            ("get", "/api/giif")]:
        getattr(app, metoda)(sciezka)(lambda: {"ok": True})
    klient = TestClient(app)
    kancelaria = _kancelaria(klient, WLASCICIEL)["id"]
    for email, stanowisko in OSOBY.items():
        odp = klient.post("/api/zespol", headers=jako(WLASCICIEL, kancelaria),
                          json={"email": email, "stanowisko": stanowisko})
        assert odp.status_code == 201, odp.text
        assert odp.json()["stanowisko"] == stanowisko
    return klient, kancelaria


def _status(klient, kancelaria, email, metoda, sciezka):
    return klient.request(metoda, sciezka, headers=jako(email, kancelaria)).status_code


@pytest.mark.parametrize("metoda,sciezka,kto_moze", [
    ("POST", f"/api/sprawy/{SPRAWA}/projekt", {"notariusz", "aplikant"}),
    ("POST", "/api/sprawy", {"notariusz", "aplikant"}),
    ("POST", f"/api/sprawy/{SPRAWA}/krz", {"notariusz", "aplikant"}),
    ("DELETE", f"/api/sprawy/{SPRAWA}/pliki/zdjecie.jpg", {"notariusz", "aplikant"}),
    ("DELETE", f"/api/sprawy/{SPRAWA}", {"notariusz"}),
    ("GET", "/api/giif", {"notariusz"}),
    ("POST", f"/api/sprawy/{SPRAWA}/pliki", {"notariusz", "aplikant", "sekretariat"}),
    ("POST", "/api/kalendarz", {"notariusz", "aplikant", "sekretariat"}),
    ("GET", f"/api/sprawy/{SPRAWA}", {"notariusz", "aplikant", "sekretariat"}),
])
def test_serwer_egzekwuje_stanowiska(zespol, metoda, sciezka, kto_moze):
    klient, kancelaria = zespol
    for email, stanowisko in OSOBY.items():
        status = _status(klient, kancelaria, email, metoda, sciezka)
        assert status == (200 if stanowisko in kto_moze else 403), (stanowisko, status)
    # Wlasciciel (Helena) - zawsze.
    assert _status(klient, kancelaria, WLASCICIEL, metoda, sciezka) == 200


def test_odmowa_mowi_co_i_nie_zdradza_adresu(zespol):
    klient, kancelaria = zespol
    odp = klient.post(f"/api/sprawy/{SPRAWA}/projekt", headers=jako("basia@kancelaria-pod7.test", kancelaria))
    assert odp.status_code == 403
    assert odp.json()["uprawnienie"] == "projekt"
    assert "sekretariat" in odp.json()["detail"] and "basia" not in odp.json()["detail"]


def test_moj_zespol_podaje_stanowisko_i_uprawnienia(zespol):
    klient, kancelaria = zespol
    ja = klient.get("/api/zespol", headers=jako("kuba@kancelaria-pod7.test", kancelaria)).json()
    assert ja["moje_stanowisko"] == "aplikant"
    assert "projekt" in ja["uprawnienia"] and "usun_sprawe" not in ja["uprawnienia"]
    basia = klient.get("/api/zespol", headers=jako("basia@kancelaria-pod7.test", kancelaria)).json()
    assert basia["uprawnienia"] == []
    helena = klient.get("/api/zespol", headers=jako(WLASCICIEL, kancelaria)).json()
    assert set(helena["uprawnienia"]) == set(stanowiska.WSZYSTKIE)


def test_stanowisko_zmienia_tylko_wlasciciel(zespol):
    klient, kancelaria = zespol
    sciezka = "/api/zespol/basia@kancelaria-pod7.test/stanowisko"
    odp = klient.put(sciezka, headers=jako("marta@kancelaria-pod7.test", kancelaria), json={"stanowisko": "notariusz"})
    assert odp.status_code == 403
    odp = klient.put(sciezka, headers=jako(WLASCICIEL, kancelaria), json={"stanowisko": "aplikant"})
    assert odp.status_code == 200 and odp.json()["stanowisko"] == "aplikant"
    assert _status(klient, kancelaria, "basia@kancelaria-pod7.test", "POST", f"/api/sprawy/{SPRAWA}/projekt") == 200
    assert klient.put(sciezka, headers=jako(WLASCICIEL, kancelaria), json={"stanowisko": "prezes"}).status_code == 400
    # Puste stanowisko = jak przed zmiana: pelne uprawnienia.
    assert klient.put(sciezka, headers=jako(WLASCICIEL, kancelaria), json={"stanowisko": ""}).json()["stanowisko"] == ""
    assert _status(klient, kancelaria, "basia@kancelaria-pod7.test", "DELETE", f"/api/sprawy/{SPRAWA}") == 200


def test_obca_kancelaria_nie_wchodzi(zespol):
    klient, kancelaria = zespol
    assert klient.post(f"/api/sprawy/{SPRAWA}/pliki", headers=jako("obcy@inna.test", "inna-kancelaria")).status_code == 401
