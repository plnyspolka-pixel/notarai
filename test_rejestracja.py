"""Rejestracja kancelarii i dokumenty akceptowane w aplikacji, bez papieru.
Cognito zastapione atrapa, bez sieci. Dane fikcyjne (Sobczak, Pawlak)."""
import importlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import dokumenty_prawne
from test_logowanie import _przywroc_moduly, logowanie_atrapa  # noqa: F401
from test_zespol import ADMIN, AtrapaZespolu, jako

FORMULARZ = {
    "nazwa": "Kancelaria Notarialna Anna Sobczak",
    "notariusze": "Anna Sobczak",
    "adres": "ul. Fikcyjna 1, 20-001 Lublin",
    "nip": "",
    "email": "Anna@Kancelaria-Sobczak.TEST",
    "akceptuje": True,
}


@pytest.fixture
def srodowisko(logowanie_atrapa, monkeypatch, tmp_path):
    atrapa = AtrapaZespolu()
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
    monkeypatch.setattr(autoryzacja.logowanie, "_klient", lambda: atrapa)
    monkeypatch.setattr(autoryzacja.logowanie, "dane_z_tokenu",
                        lambda t: {"email": t.split("|")[1], "kancelaria": t.split("|")[2]})
    monkeypatch.setattr(autoryzacja.logowanie, "czy_jwt", lambda t: t.startswith("jwt|"))
    monkeypatch.setattr(rejestracja, "WLACZONA", True)
    rejestracja._wyczysc_limity()

    app = FastAPI()
    app.middleware("http")(autoryzacja.middleware)
    app.include_router(autoryzacja.router)
    app.include_router(autoryzacja.router_zespolu)
    app.include_router(rejestracja.router)
    app.include_router(rejestracja.router_dokumentow)

    @app.get("/api/sprawy")
    def sprawy():
        return []

    return TestClient(app), atrapa, autoryzacja


def _zarejestruj(klient, **zmiany):
    return klient.post("/api/rejestracja", json={**FORMULARZ, **zmiany})


def _id(klient):
    return klient.get("/api/admin/kancelarie", headers=ADMIN).json()[0]["id"]


class TestRejestracja:
    def test_formularz_zaklada_kancelarie_z_zawarta_umowa(self, srodowisko):
        klient, atrapa, autoryzacja = srodowisko
        odp = _zarejestruj(klient)
        assert odp.status_code == 201
        assert atrapa.utworzeni == ["anna@kancelaria-sobczak.test"]
        wpis = next(iter(autoryzacja._wczytaj_rejestr().values()))
        assert wpis["dane"] == {"notariusze": "Anna Sobczak", "adres": "ul. Fikcyjna 1, 20-001 Lublin",
                                "nip": ""}
        assert wpis["umowa"]["umowa"] == dokumenty_prawne.wersja("umowa")
        assert wpis["umowa"]["regulamin"] == dokumenty_prawne.wersja("regulamin")
        assert wpis["umowa"]["ip"] == "testclient"
        assert wpis["zespol"][0]["rola"] == "wlasciciel"
        # Wlasciciel od razu pracuje - umowa jest zawarta
        assert klient.get("/api/sprawy", headers=jako("anna@kancelaria-sobczak.test", wpis["id"])).status_code == 200

    def test_bez_akceptacji_nic_nie_powstaje(self, srodowisko):
        klient, atrapa, autoryzacja = srodowisko
        assert _zarejestruj(klient, akceptuje=False).status_code == 400
        assert atrapa.utworzeni == [] and autoryzacja._wczytaj_rejestr() == {}

    def test_zajety_adres_nie_zostawia_kancelarii(self, srodowisko):
        klient, atrapa, autoryzacja = srodowisko
        atrapa.utworzeni.append("anna@kancelaria-sobczak.test")
        assert _zarejestruj(klient).status_code == 409
        assert autoryzacja._wczytaj_rejestr() == {}

    def test_automat_dostaje_sukces_i_niczego_nie_zaklada(self, srodowisko):
        klient, atrapa, autoryzacja = srodowisko
        assert _zarejestruj(klient, strona="http://spam.test").status_code == 201
        assert atrapa.utworzeni == [] and autoryzacja._wczytaj_rejestr() == {}

    def test_limit_na_adres_ip(self, srodowisko):
        klient, _, _ = srodowisko
        for n in range(3):
            assert _zarejestruj(klient, email=f"osoba{n}@kancelaria-pawlak.test",
                                nazwa=f"Kancelaria Pawlak {n}").status_code == 201
        assert _zarejestruj(klient, email="kolejna@kancelaria-pawlak.test").status_code == 429

    def test_bledny_nip_i_braki_danych(self, srodowisko):
        klient, _, _ = srodowisko
        assert _zarejestruj(klient, nip="1234567890").status_code == 400
        assert _zarejestruj(klient, notariusze="").status_code == 400
        assert _zarejestruj(klient, adres="Lublin").status_code == 400

    def test_wylaczona(self, srodowisko, monkeypatch):
        klient, _, _ = srodowisko
        import rejestracja
        monkeypatch.setattr(rejestracja, "WLACZONA", False)
        assert klient.get("/api/rejestracja").json()["wlaczona"] is False
        assert _zarejestruj(klient).status_code == 503


class TestKancelariaZalozonaPrzezAdmina:
    def _kancelaria(self, klient):
        odp = klient.post("/api/admin/kancelarie", headers=ADMIN,
                          json={"nazwa": "Kancelaria Pawlak", "email": "jan@kancelaria-pawlak.test"})
        assert odp.status_code == 201
        return odp.json()["id"]

    def test_bez_umowy_sprawy_sa_zamkniete_do_akceptacji(self, srodowisko):
        klient, _, _ = srodowisko
        k = self._kancelaria(klient)
        wlasciciel = jako("jan@kancelaria-pawlak.test", k)
        assert klient.get("/api/sprawy", headers=wlasciciel).status_code == 428
        stan = klient.get("/api/dokumenty", headers=wlasciciel).json()
        assert stan["umowa_zawarta"] is False and "umowa" in stan["do_akceptacji"]

        # Brak danych notariusza - akceptacja ich wymaga
        assert klient.post("/api/dokumenty/umowa", headers=wlasciciel,
                           json={"akceptuje": True}).status_code == 400
        odp = klient.post("/api/dokumenty/umowa", headers=wlasciciel,
                          json={"akceptuje": True, "notariusze": "Jan Pawlak",
                                "adres": "ul. Testowa 2, 00-001 Warszawa"})
        assert odp.status_code == 200
        assert klient.get("/api/sprawy", headers=wlasciciel).status_code == 200
        lista = klient.get("/api/admin/kancelarie", headers=ADMIN).json()
        assert lista[0]["umowa"]

    def test_czlonek_zespolu_nie_akceptuje_za_kancelarie(self, srodowisko):
        klient, _, _ = srodowisko
        k = self._kancelaria(klient)
        wlasciciel = jako("jan@kancelaria-pawlak.test", k)
        klient.post("/api/zespol", headers=wlasciciel, json={"email": "ewa@kancelaria-pawlak.test"})
        czlonek = jako("ewa@kancelaria-pawlak.test", k)
        assert klient.post("/api/dokumenty/umowa", headers=czlonek,
                           json={"akceptuje": True, "notariusze": "Jan Pawlak",
                                 "adres": "ul. Testowa 2, 00-001 Warszawa"}).status_code == 403

    def test_jedyna_osoba_bez_wlasciciela_zostaje_wlascicielem(self, srodowisko):
        """Kancelaria sprzed zespolow: jedno konto, rola czlonek, nikt nie moze
        zaakceptowac umowy. To konto przejmuje role wlasciciela."""
        klient, _, autoryzacja = srodowisko
        k = self._kancelaria(klient)
        rejestr = autoryzacja._wczytaj_rejestr()
        next(iter(rejestr.values()))["zespol"][0]["rola"] = "czlonek"
        autoryzacja._zapisz_rejestr(rejestr)
        jan = jako("jan@kancelaria-pawlak.test", k)
        stan = klient.get("/api/dokumenty", headers=jan).json()
        assert stan["jestem_wlascicielem"] is True and "umowa" in stan["do_akceptacji"]
        assert next(iter(autoryzacja._wczytaj_rejestr().values()))["zespol"][0]["rola"] == "wlasciciel"

    def test_czlonek_nie_przejmuje_kancelarii_z_kilkoma_osobami(self, srodowisko):
        klient, _, autoryzacja = srodowisko
        k = self._kancelaria(klient)
        klient.post("/api/zespol", headers=jako("jan@kancelaria-pawlak.test", k),
                    json={"email": "ewa@kancelaria-pawlak.test"})
        rejestr = autoryzacja._wczytaj_rejestr()
        for osoba in next(iter(rejestr.values()))["zespol"]:
            osoba["rola"] = "czlonek"
        autoryzacja._zapisz_rejestr(rejestr)
        stan = klient.get("/api/dokumenty", headers=jako("ewa@kancelaria-pawlak.test", k)).json()
        assert stan["jestem_wlascicielem"] is False

    def test_administrator_nie_dostaje_klucza_do_spraw(self, srodowisko):
        """Zalozenie kancelarii nie oddaje administratorowi niczego, czym
        moglby otworzyc jej sprawy."""
        klient, _, _ = srodowisko
        odp = klient.post("/api/admin/kancelarie", headers=ADMIN, json={"nazwa": "Kancelaria Pawlak"})
        assert "token" not in odp.json()
        assert klient.get("/api/sprawy", headers=ADMIN).status_code == 401


class TestDokumenty:
    def _wlasciciel(self, klient, **zmiany):
        _zarejestruj(klient, **zmiany)
        return jako("anna@kancelaria-sobczak.test", _id(klient))

    def test_instrukcje_potwierdza_kazda_osoba(self, srodowisko):
        klient, _, _ = srodowisko
        wlasciciel = self._wlasciciel(klient)
        assert "instrukcja" in klient.get("/api/dokumenty", headers=wlasciciel).json()["do_akceptacji"]
        assert klient.post("/api/dokumenty/instrukcja", headers=wlasciciel).status_code == 200
        assert "instrukcja" not in klient.get("/api/dokumenty", headers=wlasciciel).json()["do_akceptacji"]
        osoba = klient.get("/api/zespol", headers=wlasciciel).json()["osoby"][0]
        assert osoba["instrukcja"]["wersja"] == dokumenty_prawne.wersja("instrukcja")

    def test_dpia_przyjmuje_wlasciciel(self, srodowisko):
        klient, _, _ = srodowisko
        wlasciciel = self._wlasciciel(klient)
        k = _id(klient)
        klient.post("/api/zespol", headers=wlasciciel, json={"email": "ewa@kancelaria-sobczak.test"})
        assert klient.post("/api/dokumenty/dpia", headers=jako("ewa@kancelaria-sobczak.test", k)).status_code == 403
        assert klient.post("/api/dokumenty/dpia", headers=wlasciciel).status_code == 200
        strona = klient.get("/api/dokumenty/dpia", headers=wlasciciel).text
        assert "Kancelaria Notarialna Anna Sobczak" in strona and "{{" not in strona
        assert dokumenty_prawne.PUSTE_POLE not in strona

    def test_umowa_ma_dane_stron_i_date_zawarcia(self, srodowisko):
        klient, _, _ = srodowisko
        wlasciciel = self._wlasciciel(klient)
        strona = klient.get("/api/dokumenty/umowa", headers=wlasciciel).text
        assert "Strony i potwierdzenie zawarcia" in strona
        assert "Anna Sobczak" in strona and "ul. Fikcyjna 1" in strona
        assert "formularz rejestracji" in strona

    def test_dane_z_formularza_nie_staja_sie_kodem(self, srodowisko):
        klient, _, _ = srodowisko
        wlasciciel = self._wlasciciel(
            klient, nazwa="<script>alert(1)</script> [klik](javascript:alert(2))",
            notariusze="Anna **Sobczak** <img src=x onerror=alert(3)>")
        for dokument in ("umowa", "dpia", "komplet"):
            strona = klient.get(f"/api/dokumenty/{dokument}", headers=wlasciciel).text
            assert "<script>alert" not in strona and "<img" not in strona
            assert 'href="javascript' not in strona

    def test_nieznany_dokument(self, srodowisko):
        klient, _, _ = srodowisko
        wlasciciel = self._wlasciciel(klient)
        assert klient.get("/api/dokumenty/sekret", headers=wlasciciel).status_code == 404

    def test_komplet_wszystkie_dokumenty_po_kolei_z_danymi_kancelarii(self, srodowisko):
        klient, _, _ = srodowisko
        wlasciciel = self._wlasciciel(klient)
        klient.post("/api/dokumenty/instrukcja", headers=wlasciciel)
        strona = klient.get("/api/dokumenty/komplet", headers=wlasciciel).text
        import rejestracja
        pozycje = [strona.index(f"<h1>{dokumenty_prawne.html_dokumentu(n).split('<h1>')[1].split('</h1>')[0]}</h1>")
                   for n in rejestracja.KOMPLET]
        assert pozycje == sorted(pozycje)
        assert "Strony i potwierdzenie zawarcia" in strona and "Anna Sobczak" in strona
        assert "{{" not in strona and dokumenty_prawne.PUSTE_POLE not in strona.split("Ocena")[0]
        assert "Potwierdzenia instrukcji" in strona and "anna@kancelaria-sobczak.test" in strona

    def test_czlonek_pobiera_komplet_bez_listy_potwierdzen(self, srodowisko):
        klient, _, _ = srodowisko
        wlasciciel = self._wlasciciel(klient)
        k = _id(klient)
        klient.post("/api/zespol", headers=wlasciciel, json={"email": "ewa@kancelaria-sobczak.test"})
        odp = klient.get("/api/dokumenty/komplet", headers=jako("ewa@kancelaria-sobczak.test", k))
        assert odp.status_code == 200 and "Potwierdzenia instrukcji" not in odp.text


def test_usuniecie_danych_zostawia_wpis_w_rejestrze_umow(srodowisko):
    klient, _, _ = srodowisko
    _zarejestruj(klient)
    k = _id(klient)
    klient.delete(f"/api/admin/kancelarie/{k}", headers=ADMIN)
    assert klient.post(f"/api/admin/kancelarie/{k}/usun-dane", headers=ADMIN,
                       json={"potwierdzenie": k}).status_code == 200
    rejestr = klient.get("/api/admin/rejestr-umow", headers=ADMIN).json()
    assert len(rejestr) == 1
    assert rejestr[0]["id"] == k and rejestr[0]["usunieto"] and rejestr[0]["zawarto"]
    assert rejestr[0]["notariusze"] == "Anna Sobczak"


def test_kazdy_dokument_ma_wersje():
    from datetime import date
    for nazwa in dokumenty_prawne.DOKUMENTY:
        assert date.fromisoformat(dokumenty_prawne.wersja(nazwa)) >= date(2026, 10, 24)


def test_odnosniki_tylko_bezpieczne():
    assert 'href="javascript' not in dokumenty_prawne.wiersz("[x](javascript:alert(1))")
    assert '<a href="https://notarai.pl">' in dokumenty_prawne.wiersz("[x](https://notarai.pl)")
