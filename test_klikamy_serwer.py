"""Serwerowa polowa sekcji "Klikamy".

Model stoi na serwerze, bo tu jest dostep do Bedrocka. Komputer notariusza
dostaje gotowa czynnosc do wykonania, a nie klucze do modelu. Te testy
pilnuja tej granicy i tego, co serwer robi, gdy nie ma komu zlecic.
"""
import pytest

import bedrock
import config
import zlecenia


@pytest.fixture
def klient(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import app as aplikacja

    monkeypatch.setattr(config, "SPRAWY", tmp_path)
    (tmp_path / "abc123").mkdir()
    monkeypatch.setattr(zlecenia, "dostepne", lambda: True)
    monkeypatch.setattr(aplikacja, "_pomocnik_pod_reka", lambda: True)
    monkeypatch.setattr(aplikacja, "_odnotuj_pomocnika", lambda *a, **k: None)

    zlozone = []
    monkeypatch.setattr(zlecenia, "zloz",
                        lambda rodzaj, sprawa, tresc: zlozone.append(
                            {"rodzaj": rodzaj, "sprawa": sprawa, "tresc": tresc})
                        or {"id": "z1", "rodzaj": rodzaj, "sprawa": sprawa, "tresc": tresc})
    monkeypatch.setattr(zlecenia, "wynik",
                        lambda identyfikator: {"id": identyfikator, "stan": "czeka"}
                        if identyfikator == "z1" else None)
    return TestClient(aplikacja.app), zlozone, monkeypatch, aplikacja


class TestZlecaniaKlikania:
    def test_sklada_zlecenie_z_celem(self, klient):
        klient_http, zlozone, _, _ = klient
        odp = klient_http.post("/api/sprawy/abc123/klikamy",
                               json={"cel": "znajdz dzialke 123/4"})
        assert odp.status_code == 202 and odp.json()["zlecenie"] == "z1"
        assert zlozone[0]["rodzaj"] == "klikamy"
        assert zlozone[0]["tresc"]["cel"] == "znajdz dzialke 123/4"

    def test_pusty_cel_to_blad(self, klient):
        klient_http, _, _, _ = klient
        odp = klient_http.post("/api/sprawy/abc123/klikamy", json={"cel": "   "})
        assert odp.status_code == 400

    def test_bez_pomocnika_nie_skladamy_zlecen_w_prozne(self, klient):
        klient_http, zlozone, monkeypatch, aplikacja = klient
        monkeypatch.setattr(aplikacja, "_pomocnik_pod_reka", lambda: False)
        odp = klient_http.post("/api/sprawy/abc123/klikamy", json={"cel": "cokolwiek"})
        assert odp.status_code == 409 and "pomocnik" in odp.json()["detail"].lower()
        assert zlozone == []

    def test_lista_dozwolonych_adresow_przechodzi_do_zlecenia(self, klient):
        klient_http, zlozone, _, _ = klient
        klient_http.post("/api/sprawy/abc123/klikamy",
                         json={"cel": "sprawdz", "dozwolone_hosty": ["geoportal.gov.pl", " "]})
        assert zlozone[0]["tresc"]["dozwolone_hosty"] == ["geoportal.gov.pl"]

    def test_nieznana_sprawa(self, klient):
        klient_http, _, _, _ = klient
        assert klient_http.post("/api/sprawy/niemasprawy/klikamy",
                                json={"cel": "x"}).status_code == 404


class TestKrokuAgenta:
    def _widok(self):
        return {
            "cel": "znajdz dzialke",
            "stan": {"adres": "https://mapy.geoportal.gov.pl/",
                     "tekst": "Wyszukiwarka dzialek",
                     "elementy": [{"nr": 1, "rola": "input:text", "opis": "Numer dzialki"}]},
            "kroki": [],
        }

    def test_oddaje_czynnosc_wskazana_przez_model(self, klient, monkeypatch):
        klient_http, _, _, _ = klient
        monkeypatch.setattr(bedrock, "nastepny_krok",
                            lambda cel, stan, kroki: {"akcja": "wpisz", "nr": 1, "tekst": "123/4"})
        odp = klient_http.post("/api/pomocnik/klikamy/z1/krok", json=self._widok())
        assert odp.status_code == 200
        assert odp.json() == {"akcja": "wpisz", "nr": 1, "tekst": "123/4"}

    def test_model_dostaje_cel_i_stan_strony(self, klient, monkeypatch):
        klient_http, _, _, _ = klient
        widziane = {}
        monkeypatch.setattr(bedrock, "nastepny_krok",
                            lambda cel, stan, kroki: widziane.update(cel=cel, stan=stan)
                            or {"akcja": "czytaj"})
        klient_http.post("/api/pomocnik/klikamy/z1/krok", json=self._widok())
        assert widziane["cel"] == "znajdz dzialke"
        assert widziane["stan"]["elementy"][0]["opis"] == "Numer dzialki"

    def test_nieznane_zlecenie(self, klient, monkeypatch):
        klient_http, _, _, _ = klient
        monkeypatch.setattr(bedrock, "nastepny_krok", lambda *a: {"akcja": "czytaj"})
        odp = klient_http.post("/api/pomocnik/klikamy/nie-ma/krok", json=self._widok())
        assert odp.status_code == 404

    def test_przeciazony_model_prosi_o_ponowienie(self, klient, monkeypatch):
        """Pomocnik ma poczekac i sprobowac jeszcze raz, a nie uznac, ze koniec."""
        klient_http, _, _, _ = klient

        def przeciazony(cel, stan, kroki):
            raise bedrock.Przeciazenie("model zajety")

        monkeypatch.setattr(bedrock, "nastepny_krok", przeciazony)
        odp = klient_http.post("/api/pomocnik/klikamy/z1/krok", json=self._widok())
        assert odp.status_code == 503 and odp.headers.get("Retry-After") == "30"
