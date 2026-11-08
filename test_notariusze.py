"""Mapa notariuszy: polozenie kancelarii z adresu i publiczna wyszukiwarka
najblizszej. Geokoder (Nominatim) zastapiony atrapa transportu HTTP, bez
sieci. Cognito zastapione atrapa. Dane fikcyjne (Sobczak, Pawlak)."""
import importlib
import logging
import re
import time

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import notariusze
from test_logowanie import _przywroc_moduly, logowanie_atrapa  # noqa: F401
from test_zespol import ADMIN, AtrapaZespolu, jako

ADRES_LUBLIN = "ul. Fikcyjna 1, 20-001 Lublin"
ADRES_WARSZAWA = "al. Zmyślona 2, 00-001 Warszawa"
LUBLIN = ("51.2465", "22.5684")
WARSZAWA = ("52.2297", "21.0122")
WLASCICIELKA = "anna@kancelaria-sobczak.test"

FORMULARZ = {
    "nazwa": "Kancelaria Notarialna Anna Sobczak",
    "notariusze": "Anna Sobczak",
    "adres": ADRES_LUBLIN,
    "nip": "",
    "email": WLASCICIELKA,
    "akceptuje": True,
}


class AtrapaGeokodera:
    """Udaje Nominatim: zna zapytania ze slownika {tekst: (lat, lon)}."""

    def __init__(self, znane=None):
        self.znane = dict(znane or {})
        self.blad = None
        self.zadania: list[httpx.Request] = []

    def __call__(self, zadanie: httpx.Request) -> httpx.Response:
        self.zadania.append(zadanie)
        if self.blad:
            raise self.blad
        q = zadanie.url.params.get("q")
        if q in self.znane:
            lat, lon = self.znane[q]
            return httpx.Response(200, json=[{"lat": lat, "lon": lon, "display_name": q, "type": "house"}])
        return httpx.Response(200, json=[])

    @property
    def zapytania(self) -> list[str]:
        return [z.url.params.get("q") for z in self.zadania]


@pytest.fixture
def geokoder(monkeypatch):
    """Wlacza geokodowanie (conftest je wylacza) i podstawia atrape sieci."""
    atrapa = AtrapaGeokodera({ADRES_LUBLIN: LUBLIN, ADRES_WARSZAWA: WARSZAWA})
    monkeypatch.setattr(notariusze, "GEOKODER", "https://geokoder.test/search")
    monkeypatch.setattr(notariusze, "ODSTEP_S", 0)
    monkeypatch.setattr(notariusze, "_transport", httpx.MockTransport(atrapa))
    return atrapa


@pytest.fixture
def srodowisko(logowanie_atrapa, geokoder, monkeypatch, tmp_path):
    cognito = AtrapaZespolu()
    monkeypatch.setenv("PIECZAPP_MULTI", "true")
    monkeypatch.setenv("PIECZAPP_ADMIN_TOKEN", "sekret-admina")
    monkeypatch.setenv("PIECZAPP_MAGAZYN", "lokalny")
    import config
    import magazyn
    import autoryzacja
    import rejestracja
    importlib.reload(magazyn)
    importlib.reload(autoryzacja)
    monkeypatch.setattr(config, "DANE", tmp_path)
    monkeypatch.setattr(autoryzacja.logowanie, "_klient", lambda: cognito)
    monkeypatch.setattr(autoryzacja.logowanie, "dane_z_tokenu",
                        lambda t: {"email": t.split("|")[1], "kancelaria": t.split("|")[2]})
    monkeypatch.setattr(autoryzacja.logowanie, "czy_jwt", lambda t: t.startswith("jwt|"))
    monkeypatch.setattr(rejestracja, "WLACZONA", True)
    rejestracja._wyczysc_limity()

    app = FastAPI()
    app.middleware("http")(autoryzacja.middleware)
    for r in (autoryzacja.router, autoryzacja.router_zespolu, rejestracja.router,
              rejestracja.router_dokumentow, notariusze.router, notariusze.router_kancelarii,
              notariusze.router_admina):
        app.include_router(r)
    return TestClient(app), geokoder, autoryzacja


def _zarejestruj(klient, _publikuj=True, **zmiany):
    odp = klient.post("/api/rejestracja", json={**FORMULARZ, **zmiany})
    assert odp.status_code == 201, odp.text
    # W produkcji widocznosc nie jest domyslna: kancelaria swiadomie wlacza ja
    # jako wlasciciel. Stare testy katalogu publikuja jawnie przez to API.
    if _publikuj:
        import autoryzacja
        id_k = _wpis(autoryzacja, nazwa=zmiany.get("nazwa", FORMULARZ["nazwa"]))["id"]
        email = zmiany.get("email", WLASCICIELKA)
        wynik = klient.put("/api/mapa", headers=jako(email, id_k),
                           json={"na_mapie": True})
        assert wynik.status_code == 200, wynik.text
    return odp


def _wpis(autoryzacja, nazwa=FORMULARZ["nazwa"]):
    return next(w for w in autoryzacja._wczytaj_rejestr().values() if w["nazwa"] == nazwa)


def _publiczne(klient, **params):
    odp = klient.get("/api/notariusze", params=params)   # bez naglowka Authorization
    assert odp.status_code == 200, odp.text
    return odp.json()["kancelarie"]


class TestWarianty:
    def test_pelny_adres_potem_uproszczony_potem_miejscowosc(self):
        assert notariusze._warianty("ul.  Fikcyjna 1, 20-001 Lublin") == [
            ("ul. Fikcyjna 1, 20-001 Lublin", "adres"),
            ("Fikcyjna 1, Lublin", "adres"),
            ("Lublin", "miejscowosc"),
        ]

    def test_adres_bez_przecinka_miejscowosc_po_kodzie(self):
        assert notariusze._warianty("Rynek 5 20-111 Lublin")[-1] == ("Lublin", "miejscowosc")

    def test_sama_miejscowosc_bez_powtorzen(self):
        assert notariusze._warianty("Lublin") == [("Lublin", "adres")]


class TestGeokoduj:
    def test_wspolrzedne_z_pierwszej_proby(self, geokoder):
        assert notariusze.geokoduj(ADRES_LUBLIN) == {"lat": 51.2465, "lon": 22.5684, "dokladnosc": "adres"}
        assert geokoder.zapytania == [ADRES_LUBLIN]

    def test_miejscowosc_gdy_geokoder_nie_zna_ulicy(self, geokoder):
        geokoder.znane = {"Lublin": LUBLIN}
        wynik = notariusze.geokoduj(ADRES_LUBLIN)
        assert wynik["dokladnosc"] == "miejscowosc" and wynik["lat"] == 51.2465
        assert geokoder.zapytania == [ADRES_LUBLIN, "Fikcyjna 1, Lublin", "Lublin"]

    def test_nic_gdy_nic_nie_znaleziono(self, geokoder):
        geokoder.znane = {}
        assert notariusze.geokoduj("ul. Nieistniejąca 9, 99-999 Nigdzie") is None

    def test_zapytanie_identyfikuje_usluge_i_ogranicza_do_polski(self, geokoder):
        notariusze.geokoduj(ADRES_LUBLIN)
        zadanie = geokoder.zadania[0]
        assert zadanie.headers["user-agent"] == "notarai.pl (kontakt@notarai.pl)"
        assert zadanie.url.host == "geokoder.test"
        assert dict(zadanie.url.params) == {"q": ADRES_LUBLIN, "format": "jsonv2", "limit": "1", "countrycodes": "pl"}

    def test_odstep_miedzy_zapytaniami(self, geokoder, monkeypatch):
        monkeypatch.setattr(notariusze, "ODSTEP_S", 0.05)
        monkeypatch.setattr(notariusze, "_ostatnie", 0.0)
        notariusze.geokoduj(ADRES_LUBLIN)
        start = time.monotonic()
        notariusze.geokoduj(ADRES_WARSZAWA)
        assert time.monotonic() - start >= 0.045, "drugie zapytanie ma poczekac na odstep"

    def test_blad_sieci_idzie_do_wywolujacego(self, geokoder):
        geokoder.blad = httpx.ConnectError("odmowa")
        with pytest.raises(httpx.ConnectError):
            notariusze.geokoduj(ADRES_LUBLIN)


class TestUstalPolozenie:
    def _wpis(self, adres=ADRES_LUBLIN):
        return {"id": "k1", "nazwa": "Kancelaria", "dane": {"notariusze": "Anna Sobczak", "adres": adres, "nip": ""}}

    def test_zapisuje_polozenie_w_wpisie(self, geokoder):
        wpis = self._wpis()
        mapa = notariusze.ustal_polozenie(wpis)
        assert wpis["mapa"] is mapa
        assert mapa["lat"] == 51.2465 and mapa["lon"] == 22.5684 and mapa["dokladnosc"] == "adres"
        assert mapa["adres"] == ADRES_LUBLIN and mapa["sprawdzono"]
        assert "blad" not in mapa
        # dane kancelarii bez zmian - wspolrzedne leza osobno
        assert wpis["dane"] == {"notariusze": "Anna Sobczak", "adres": ADRES_LUBLIN, "nip": ""}

    def test_ten_sam_adres_nie_pyta_ponownie(self, geokoder):
        wpis = self._wpis()
        notariusze.ustal_polozenie(wpis)
        notariusze.ustal_polozenie(wpis)
        assert len(geokoder.zadania) == 1

    def test_nowy_adres_pyta_ponownie(self, geokoder):
        wpis = self._wpis()
        notariusze.ustal_polozenie(wpis)
        wpis["dane"]["adres"] = ADRES_WARSZAWA
        assert notariusze.ustal_polozenie(wpis)["lat"] == 52.2297
        assert geokoder.zapytania == [ADRES_LUBLIN, ADRES_WARSZAWA]

    def test_wymus_pyta_mimo_tego_samego_adresu(self, geokoder):
        wpis = self._wpis()
        notariusze.ustal_polozenie(wpis)
        notariusze.ustal_polozenie(wpis, wymus=True)
        assert len(geokoder.zadania) == 2

    def test_awaria_geokodera_nie_rzuca_tylko_odnotowuje(self, geokoder):
        geokoder.blad = httpx.ReadTimeout("za dlugo")
        wpis = self._wpis()
        mapa = notariusze.ustal_polozenie(wpis)
        assert mapa["blad"] == "geokoder niedostepny" and "lat" not in mapa
        assert mapa["adres"] == ADRES_LUBLIN

    def test_nieznany_adres_odnotowany(self, geokoder):
        geokoder.znane = {}
        assert notariusze.ustal_polozenie(self._wpis())["blad"] == "adres nieznany geokoderowi"

    def test_po_awarii_ten_sam_adres_jest_sprawdzany_ponownie(self, geokoder):
        wpis = self._wpis()
        geokoder.blad = httpx.ConnectError("x")
        notariusze.ustal_polozenie(wpis)
        geokoder.blad = None
        assert notariusze.ustal_polozenie(wpis)["lat"] == 51.2465

    def test_wylaczony_geokoder_nic_nie_robi(self, monkeypatch):
        # Wyłączenie geokodera powinno być jawne, nie zależeć od conftest.
        monkeypatch.setattr(notariusze, "GEOKODER", "")
        wpis = self._wpis()
        assert notariusze.ustal_polozenie(wpis) is None and "mapa" not in wpis

    def test_bez_adresu_nic_nie_robi(self, geokoder):
        wpis = {"id": "k1", "nazwa": "Kancelaria"}
        assert notariusze.ustal_polozenie(wpis) is None and not geokoder.zadania

    def test_adres_nie_trafia_do_logow(self, geokoder, caplog):
        caplog.set_level(logging.DEBUG, logger="pieczapp.notariusze")
        notariusze.ustal_polozenie(self._wpis())
        geokoder.blad = httpx.ConnectError("odmowa dla ul. Fikcyjna")
        notariusze.ustal_polozenie(self._wpis(ADRES_WARSZAWA))
        geokoder.blad = None
        geokoder.znane = {}
        notariusze.ustal_polozenie(self._wpis("ul. Tajna 7, 20-002 Lublin"))
        assert caplog.text, "operacje maja zostawic slad w dzienniku"
        for slowo in ("Fikcyjna", "Zmyślona", "Tajna", "Lublin", "Warszawa", "odmowa"):
            assert slowo not in caplog.text


class TestOdleglosc:
    def test_lublin_warszawa_okolo_153_km(self):
        d = notariusze.odleglosc_km(51.2465, 22.5684, 52.2297, 21.0122)
        assert 150 < d < 157

    def test_ten_sam_punkt_zero(self):
        assert notariusze.odleglosc_km(51.0, 22.0, 51.0, 22.0) == 0


class TestRejestracjaNaMapie:
    def test_nowej_kancelarii_nie_publikujemy_bez_zgody(self, srodowisko):
        klient, _, autoryzacja = srodowisko
        _zarejestruj(klient, _publikuj=False)
        wpis = _wpis(autoryzacja)
        assert wpis.get("na_mapie", False) is False
        assert _publiczne(klient) == []
        assert klient.get("/api/mapa", headers=jako(WLASCICIELKA, wpis["id"])).json()["na_mapie"] is False

    def test_rejestracja_ustala_polozenie_poza_danymi_umowy(self, srodowisko):
        klient, geokoder, autoryzacja = srodowisko
        _zarejestruj(klient)
        wpis = _wpis(autoryzacja)
        assert wpis["mapa"]["lat"] == 51.2465 and wpis["mapa"]["adres"] == ADRES_LUBLIN
        assert wpis["dane"] == {"notariusze": "Anna Sobczak", "adres": ADRES_LUBLIN, "nip": ""}
        assert wpis.get("na_mapie", False) is True

    def test_publiczna_lista_bez_logowania_i_bez_danych_poufnych(self, srodowisko):
        klient, _, _ = srodowisko
        _zarejestruj(klient)
        lista = _publiczne(klient)
        assert lista == [{"nazwa": FORMULARZ["nazwa"], "notariusze": "Anna Sobczak", "adres": ADRES_LUBLIN,
                          "lat": 51.2465, "lon": 22.5684, "dokladnosc": "adres"}]
        tresc = klient.get("/api/notariusze").text
        assert "@" not in tresc and "kancelaria-notarialna-anna-sobczak" not in tresc

    def test_strona_mapy_otwarta_bez_logowania(self, srodowisko):
        klient, _, _ = srodowisko
        # Sciezka otwarta w middleware - serwer bez tej trasy odpowie 404, nie 401.
        assert klient.get("/notariusze").status_code == 404
        assert klient.get("/api/mapa").status_code == 401, "ustawienia kancelarii wymagaja logowania"

    def test_najblizsza_pierwsza_z_odlegloscia(self, srodowisko):
        klient, _, _ = srodowisko
        _zarejestruj(klient)
        _zarejestruj(klient, nazwa="Kancelaria Notarialna Jan Pawlak", notariusze="Jan Pawlak",
                     adres=ADRES_WARSZAWA, email="jan@kancelaria-pawlak.test")
        lista = _publiczne(klient, lat=51.25, lon=22.57)
        assert [k["nazwa"] for k in lista] == [FORMULARZ["nazwa"], "Kancelaria Notarialna Jan Pawlak"]
        assert lista[0]["odleglosc_km"] < 1 and 150 < lista[1]["odleglosc_km"] < 157
        # z Warszawy odwrotnie
        assert _publiczne(klient, lat=52.23, lon=21.01)[0]["nazwa"] == "Kancelaria Notarialna Jan Pawlak"
        # bez polozenia: alfabetycznie, bez odleglosci
        assert [k["nazwa"] for k in _publiczne(klient)] == [FORMULARZ["nazwa"], "Kancelaria Notarialna Jan Pawlak"]
        assert "odleglosc_km" not in _publiczne(klient)[0]

    def test_lat_bez_lon_odrzucone(self, srodowisko):
        klient, _, _ = srodowisko
        assert klient.get("/api/notariusze", params={"lat": 51}).status_code == 400
        assert klient.get("/api/notariusze", params={"lat": 91, "lon": 0}).status_code == 400

    def test_awaria_geokodera_nie_blokuje_rejestracji(self, srodowisko):
        klient, geokoder, autoryzacja = srodowisko
        geokoder.blad = httpx.ConnectError("odmowa")
        _zarejestruj(klient)
        assert _wpis(autoryzacja)["mapa"]["blad"] == "geokoder niedostepny"
        assert _publiczne(klient) == []

    def test_zmiana_adresu_przenosi_kancelarie(self, srodowisko):
        klient, geokoder, autoryzacja = srodowisko
        _zarejestruj(klient)
        id_k = _wpis(autoryzacja)["id"]
        odp = klient.post("/api/dokumenty/dane", headers=jako(WLASCICIELKA, id_k),
                          json={"notariusze": "Anna Sobczak", "adres": ADRES_WARSZAWA, "nip": ""})
        assert odp.status_code == 200, odp.text
        assert _publiczne(klient)[0]["lat"] == 52.2297
        assert geokoder.zapytania == [ADRES_LUBLIN, ADRES_WARSZAWA]


class TestUstawieniaKancelarii:
    def _kancelaria(self, klient, autoryzacja):
        _zarejestruj(klient)
        return _wpis(autoryzacja)["id"]

    def test_wlasciciel_widzi_stan(self, srodowisko):
        klient, _, autoryzacja = srodowisko
        id_k = self._kancelaria(klient, autoryzacja)
        stan = klient.get("/api/mapa", headers=jako(WLASCICIELKA, id_k)).json()
        assert stan["na_mapie"] is True and stan["publikowana"] is True and stan["geokoder"] is True
        assert stan["lat"] == 51.2465 and stan["adres"] == ADRES_LUBLIN and stan["blad"] is None

    def test_wlasciciel_zdejmuje_i_przywraca_kancelarie(self, srodowisko):
        klient, _, autoryzacja = srodowisko
        id_k = self._kancelaria(klient, autoryzacja)
        odp = klient.put("/api/mapa", headers=jako(WLASCICIELKA, id_k), json={"na_mapie": False})
        assert odp.status_code == 200 and odp.json()["publikowana"] is False
        assert _publiczne(klient) == []
        assert _wpis(autoryzacja)["na_mapie"] is False
        klient.put("/api/mapa", headers=jako(WLASCICIELKA, id_k), json={"na_mapie": True})
        assert len(_publiczne(klient)) == 1

    def test_czlonek_zespolu_nie_zmienia_ustawien(self, srodowisko):
        klient, _, autoryzacja = srodowisko
        id_k = self._kancelaria(klient, autoryzacja)
        czlonek = "jan@kancelaria-sobczak.test"
        assert klient.post("/api/zespol", headers=jako(WLASCICIELKA, id_k), json={"email": czlonek}).status_code == 201
        assert klient.get("/api/mapa", headers=jako(czlonek, id_k)).status_code == 200
        assert klient.put("/api/mapa", headers=jako(czlonek, id_k), json={"na_mapie": False}).status_code == 403
        assert klient.post("/api/mapa/odswiez", headers=jako(czlonek, id_k)).status_code == 403
        assert len(_publiczne(klient)) == 1

    def test_odswiezenie_po_awarii_geokodera(self, srodowisko):
        klient, geokoder, autoryzacja = srodowisko
        geokoder.blad = httpx.ConnectError("odmowa")
        id_k = self._kancelaria(klient, autoryzacja)
        assert _publiczne(klient) == []
        geokoder.blad = None
        odp = klient.post("/api/mapa/odswiez", headers=jako(WLASCICIELKA, id_k))
        assert odp.status_code == 200 and odp.json()["lat"] == 51.2465 and odp.json()["blad"] is None
        assert len(_publiczne(klient)) == 1

    def test_wylaczona_kancelaria_znika_z_mapy(self, srodowisko):
        klient, _, autoryzacja = srodowisko
        id_k = self._kancelaria(klient, autoryzacja)
        assert klient.delete("/api/admin/kancelarie/" + id_k, headers=ADMIN).status_code == 200
        assert _publiczne(klient) == []

    def test_po_terminie_abonamentu_znika_z_mapy(self, srodowisko, monkeypatch):
        klient, _, autoryzacja = srodowisko
        self._kancelaria(klient, autoryzacja)
        monkeypatch.setattr(notariusze.platnosci, "wlaczone", lambda: True)
        rejestr = autoryzacja._wczytaj_rejestr()
        _wpis(autoryzacja)["oplacono_do"] = "2020-01-01"
        autoryzacja._zapisz_rejestr(rejestr)
        assert _publiczne(klient) == []


class TestPanelAdministratora:
    def test_lista_kancelarii_pokazuje_stan_mapy(self, srodowisko):
        klient, _, _ = srodowisko
        _zarejestruj(klient)
        k = klient.get("/api/admin/kancelarie", headers=ADMIN).json()[0]
        assert k["mapa"] == {"na_mapie": True, "polozenie": True, "blad": None}

    def test_uzupelnia_polozenie_kancelariom_sprzed_mapy(self, srodowisko):
        klient, geokoder, autoryzacja = srodowisko
        # Kancelaria zalozona przez administratora, umowa z danymi zaakceptowana
        # w czasie awarii geokodera - tak wygladaja wpisy sprzed mapy.
        k = klient.post("/api/admin/kancelarie", headers=ADMIN,
                        json={"nazwa": "Kancelaria Pawlak", "email": "jan@kancelaria-pawlak.test"}).json()
        geokoder.blad = httpx.ConnectError("odmowa")
        odp = klient.post("/api/dokumenty/umowa", headers=jako("jan@kancelaria-pawlak.test", k["id"]),
                          json={"akceptuje": True, "notariusze": "Jan Pawlak", "adres": ADRES_WARSZAWA, "nip": ""})
        assert odp.status_code == 200, odp.text
        geokoder.blad = None
        _zarejestruj(klient)                       # ta ma polozenie od razu
        del geokoder.zadania[:]

        assert klient.post("/api/admin/mapa").status_code == 401
        wynik = klient.post("/api/admin/mapa", headers=ADMIN).json()
        assert wynik == {"ustalono": 1, "aktualne": 1, "bez_adresu": 0, "bez_polozenia": []}
        assert geokoder.zapytania == [ADRES_WARSZAWA], "kancelarii z aktualnym polozeniem nie pytamy ponownie"
        # Nowe kancelarie nie sa publiczne bez zgody. Wlasciciel Pawlaka
        # wlacza publikacje swiadomie po ponownym wyznaczeniu polozenia.
        assert [w["nazwa"] for w in _publiczne(klient)] == [FORMULARZ["nazwa"]]
        odp = klient.put("/api/mapa", headers=jako("jan@kancelaria-pawlak.test", k["id"]),
                         json={"na_mapie": True})
        assert odp.status_code == 200
        assert sorted(w["nazwa"] for w in _publiczne(klient)) == ["Kancelaria Notarialna Anna Sobczak", "Kancelaria Pawlak"]

    def test_wszystkie_wyznacza_od_nowa_i_wymienia_nieznane(self, srodowisko):
        klient, geokoder, _ = srodowisko
        _zarejestruj(klient)
        geokoder.znane = {}
        wynik = klient.post("/api/admin/mapa", headers=ADMIN, params={"wszystkie": "true"}).json()
        assert wynik["ustalono"] == 0 and wynik["bez_polozenia"] == [FORMULARZ["nazwa"]]
        assert _publiczne(klient) == [], "stare polozenie nie zostaje, gdy adresu nie da sie juz znalezc"


class TestStronaMapy:
    """Trasy w prawdziwej aplikacji (tryb lokalny, bez logowania)."""

    @pytest.fixture
    def klient(self, monkeypatch, tmp_path):
        import config
        monkeypatch.setattr(config, "DANE", tmp_path)
        import app as aplikacja
        return TestClient(aplikacja.app)

    def test_strona_i_biblioteka_mapy_z_tego_serwera(self, klient):
        odp = klient.get("/notariusze")
        assert odp.status_code == 200 and "text/html" in odp.headers["content-type"]
        assert "/static/leaflet/leaflet.js" in odp.text and 'fetch("/api/notariusze")' in odp.text
        zrodla = re.findall(r'<(?:script|link)\b[^>]*?(?:src|href)="([^"]+)"', odp.text)
        assert zrodla and all(z.startswith("/static/") for z in zrodla), zrodla
        assert odp.text.count("tile.openstreetmap.org") == 1, "jedyne zrodlo zewnetrzne to kafelki mapy"
        js = klient.get("/static/leaflet/leaflet.js")
        assert js.status_code == 200 and "Leaflet 1.9.4" in js.text
        assert klient.get("/static/leaflet/images/marker-icon.png").status_code == 200

    def test_pusta_lista_w_trybie_lokalnym(self, klient):
        assert klient.get("/api/notariusze").json() == {"kancelarie": []}
