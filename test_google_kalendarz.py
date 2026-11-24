"""Regresja: OAuth i synchronizacja Google nie eksportuja tajemnicy notarialnej."""
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from zoneinfo import ZoneInfo

DZIEN = (datetime.now(ZoneInfo('Europe/Warsaw')) + timedelta(days=2)).date().isoformat()
from fastapi.testclient import TestClient


@pytest.fixture
def srodowisko(tmp_path, monkeypatch):
    import config
    import magazyn
    import google_kalendarz as g
    monkeypatch.setattr(config, "DANE", tmp_path)
    monkeypatch.setattr(g.autoryzacja, "MULTI", False)
    monkeypatch.setattr(magazyn, "TRYB", "lokalny")
    monkeypatch.setenv("PIECZAPP_OAUTH_GOOGLE_KLIENT", "test-client-id")
    monkeypatch.setenv("PIECZAPP_OAUTH_GOOGLE_SEKRET", "test-client-secret")
    monkeypatch.setenv("PIECZAPP_ADRES", "http://127.0.0.1:8000")
    g.sejf_lokalny.dane.clear()
    znacznik = magazyn.kancelaria_var.set("lokalna")
    from app import app
    yield g, TestClient(app)
    magazyn.kancelaria_var.reset(znacznik)


def wydarzenie(id_g, dzien=DZIEN, od="09:00", do="10:00", tytul="Dane klienta: 12345678901"):
    return {"id": id_g, "summary": tytul,
            "start": {"dateTime": f"{dzien}T{od}:00+01:00"},
            "end": {"dateTime": f"{dzien}T{do}:00+01:00"}}


def test_start_wymaga_oauth_i_ma_pkce(srodowisko):
    g, klient = srodowisko
    url = klient.get("/api/google-kalendarz/start").json()["adres"]
    parsed = parse_qs(urlparse(url).query)
    assert parsed["client_id"] == ["test-client-id"]
    assert parsed["code_challenge_method"] == ["S256"]
    assert parsed["access_type"] == ["offline"]
    assert "https://www.googleapis.com/auth/calendar.events" in parsed["scope"][0]
    assert parsed["redirect_uri"] == ["http://127.0.0.1:8000/api/google-kalendarz/powrot"]
    assert "test-client-secret" not in url


def test_oauth_callback_jednorazowy_bez_sekretow_w_s3(srodowisko, monkeypatch):
    g, klient = srodowisko
    from types import SimpleNamespace
    url = klient.get("/api/google-kalendarz/start").json()["adres"]
    state = parse_qs(urlparse(url).query)["state"][0]
    calls = []
    def fake_post(url, data, timeout):
        calls.append(dict(data))
        return SimpleNamespace(status_code=200, json=lambda: {
            "access_token": "access-super-secret", "refresh_token": "refresh-super-secret"})
    def fake_get(*args, **kw):
        return SimpleNamespace(status_code=200, json=lambda: {"email": "notary@example.org"})
    monkeypatch.setattr(g.httpx, "post", fake_post)
    monkeypatch.setattr(g.httpx, "get", fake_get)
    wynik = klient.get("/api/google-kalendarz/powrot", params={"code": "code-once", "state": state},
                        follow_redirects=False)
    assert wynik.status_code == 303
    assert "polaczono" in wynik.headers["location"]
    assert calls[0]["code_verifier"]
    assert g.sejf_lokalny.wczytaj("lokalna") == {"refresh_token": "refresh-super-secret"}
    assert "refresh-super-secret" not in str(g._stan())
    assert "access-super-secret" not in str(g._stan())
    assert klient.get("/api/google-kalendarz/stan").json()["polaczono"]
    drugi = klient.get("/api/google-kalendarz/powrot", params={"code": "code-once", "state": state},
                        follow_redirects=False)
    assert drugi.status_code == 303
    assert "blad" in drugi.headers["location"]
    assert len(calls) == 1


def test_bledny_podpis_nie_wybiera_kancelarii(srodowisko):
    g, klient = srodowisko
    wynik = klient.get("/api/google-kalendarz/powrot",
                        params={"code": "fake", "state": "kancelaria-zewnetrzna"},
                        follow_redirects=False)
    assert wynik.status_code == 303
    assert "blad" in wynik.headers["location"]
    assert not g._stan().get("polaczono")


def test_eksport_tylko_blok_czasu(srodowisko, monkeypatch):
    g, klient = srodowisko
    from kalendarz import dodaj
    dodaj({"data": DZIEN, "godzina": "09:00", "koniec": "10:00",
           "tytul": "Sprawa Kowalskiej", "uczestnicy": "Anna Kowalska PESEL 12345678901",
           "telefony": [{"imie": "Anna", "numer": "600111222"}],
           "uwagi": "Sprzedaż nieruchomości"})
    monkeypatch.setattr(g, "_wydarzenia", lambda token: {})
    przeslane = []
    def fake_zadanie(token, metoda, adres, **kw):
        if metoda == "POST":
            przeslane.append(kw["json"])
            return {**kw["json"], "id": "g-id"}
        raise AssertionError((metoda, adres))
    monkeypatch.setattr(g, "_zadanie", fake_zadanie)
    wynik = g._sync("fake-access")
    assert wynik["dodano_w_google"] == 1
    assert len(przeslane) == 1
    assert przeslane[0]["summary"] == "Zajęte - NotarAI"
    zapis = str(przeslane)
    for poufne in ("Kowalska", "12345678901", "600111222", "Sprzedaż"):
        assert poufne not in zapis


def test_import_google_nie_kopiuje_tresci(srodowisko, monkeypatch):
    g, klient = srodowisko
    monkeypatch.setattr(g, "_wydarzenia", lambda token: {
        "g-123": wydarzenie("g-123", tytul="Wizyta osobista klienta z PESEL 11122233344")})
    wynik = g._sync("fake")
    assert wynik["dodano_w_notarai"] == 1
    terminy = klient.get("/api/kalendarz").json()
    assert len(terminy) == 1
    assert terminy[0]["tytul"] == "Zajęte w Google"
    assert "11122233344" not in str(g._stan())
    assert terminy[0]["uczestnicy"] == ""


def test_kolizja_nie_niszczy_wizyty(srodowisko, monkeypatch):
    g, klient = srodowisko
    from kalendarz import dodaj
    dodaj({"data": DZIEN, "godzina": "09:00", "koniec": "10:00",
           "tytul": "Termin NotarAI"})
    monkeypatch.setattr(g, "_wydarzenia", lambda token: {"g1": wydarzenie("g1")})
    def fake_zadanie(token, method, adres, **kw):
        if method == "POST":
            return {**kw["json"], "id": "lokalne-1"}
        raise AssertionError(method)
    monkeypatch.setattr(g, "_zadanie", fake_zadanie)
    wynik = g._sync("fake")
    assert wynik["konflikty"] == 1
    assert len(klient.get("/api/kalendarz").json()) == 1


def test_zmiana_godziny_przychodzi_z_google(srodowisko, monkeypatch):
    g, klient = srodowisko
    from kalendarz import dodaj
    lok = dodaj({"data": DZIEN, "godzina": "09:00", "koniec": "10:00",
                 "tytul": "Ważna sprawa"})
    ev = wydarzenie("g1", od="09:00", do="10:00")
    def zapisz(d):
        d["mapowania"] = {lok["id"]: {"google_id": "g1", "pochodzenie": "notarai",
                                       "lokalny": g._podpis(lok), "google": g._podpis_google(ev)}}
    g._zapisz(zapisz)
    monkeypatch.setattr(g, "_wydarzenia", lambda token: {
        "g1": wydarzenie("g1", od="11:00", do="12:00")})
    wynik = g._sync("fake")
    assert wynik["zmieniono"] == 1
    wpis = klient.get("/api/kalendarz").json()[0]
    assert wpis["godzina"] == "11:00"
    assert wpis["tytul"] == "Ważna sprawa"


def test_rownoczesne_zmiany_zglaszaja_konflikt(srodowisko, monkeypatch):
    g, klient = srodowisko
    import kalendarz
    lok = kalendarz.dodaj({"data": DZIEN, "godzina": "09:00", "koniec": "10:00",
                           "tytul": "Moja wizyta"})
    ev = wydarzenie("g1")
    g._zapisz(lambda d: d.update({"mapowania": {lok["id"]: {
        "google_id": "g1", "pochodzenie": "notarai",
        "lokalny": g._podpis(lok), "google": g._podpis_google(ev)}}}))
    kalendarz.zmien(lok["id"], {**lok, "godzina": "10:00", "koniec": "11:00"})
    monkeypatch.setattr(g, "_wydarzenia", lambda token: {
        "g1": wydarzenie("g1", od="12:00", do="13:00")})
    wynik = g._sync("fake")
    assert wynik["konflikty"] == 1
    assert klient.get("/api/kalendarz").json()[0]["godzina"] == "10:00"


def test_przesuniecie_wpisu_z_google_zachowuje_oryginalny_tytul(srodowisko, monkeypatch):
    g, klient = srodowisko
    import kalendarz
    lok = kalendarz.dodaj({"data": DZIEN, "godzina": "09:00", "koniec": "10:00",
                           "tytul": "Zajęte w Google"})
    oryginal = wydarzenie("g1", tytul="Osobisty prywatny tytuł w Google")
    g._zapisz(lambda d: d.update({"mapowania": {lok["id"]: {
        "google_id": "g1", "pochodzenie": "google",
        "lokalny": g._podpis(lok), "google": g._podpis_google(oryginal)}}}))
    kalendarz.zmien(lok["id"], {**lok, "godzina": "11:00", "koniec": "12:00"})
    monkeypatch.setattr(g, "_wydarzenia", lambda token: {"g1": oryginal})
    wyslane = []
    def zadanie(token, metoda, url, **kw):
        assert metoda == "PATCH"
        wyslane.append(kw["json"])
        return {**oryginal, "start": kw["json"]["start"], "end": kw["json"]["end"]}
    monkeypatch.setattr(g, "_zadanie", zadanie)
    wynik = g._sync("fake")
    assert wynik["zmieniono"] == 1
    assert len(wyslane) == 1
    assert "summary" not in wyslane[0]
    assert "description" not in wyslane[0]
