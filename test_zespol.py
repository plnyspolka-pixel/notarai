"""Zespol kancelarii: wlasciciel zaprasza i usuwa osoby sam, bez administratora.
Cognito zastapione atrapa, bez sieci. Adresy fikcyjne."""
import importlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from test_logowanie import AtrapaCognito, _wyjatek, _przywroc_moduly, logowanie_atrapa  # noqa: F401

ADMIN = {"Authorization": "Bearer sekret-admina"}


class AtrapaZespolu(AtrapaCognito):
    def __init__(self):
        super().__init__()
        self.ponowione = []
        self.usunieci = []
        self.ustawione_haslo = set()

    def admin_create_user(self, **kw):
        if kw.get("MessageAction") == "RESEND":
            if kw["Username"] in self.ustawione_haslo:
                raise _wyjatek("UnsupportedUserStateException")
            self.ponowione.append(kw["Username"])
            return
        if kw["Username"] in self.utworzeni:
            raise _wyjatek("UsernameExistsException")
        super().admin_create_user(**kw)

    def admin_delete_user(self, **kw):
        self.usunieci.append(kw["Username"])


@pytest.fixture
def srodowisko(logowanie_atrapa, monkeypatch, tmp_path):
    logowanie, _ = logowanie_atrapa
    atrapa = AtrapaZespolu()
    monkeypatch.setenv("PIECZAPP_MULTI", "true")
    monkeypatch.setenv("PIECZAPP_ADMIN_TOKEN", "sekret-admina")
    monkeypatch.setenv("PIECZAPP_MAGAZYN", "lokalny")
    import config
    import magazyn
    import autoryzacja
    importlib.reload(magazyn)
    importlib.reload(autoryzacja)
    monkeypatch.setattr(config, "DANE", tmp_path)
    monkeypatch.setattr(autoryzacja.logowanie, "_klient", lambda: atrapa)
    # Token "jwt|<email>|<kancelaria>" udaje podpisany token tozsamosci.
    monkeypatch.setattr(autoryzacja.logowanie, "dane_z_tokenu",
                        lambda t: {"email": t.split("|")[1], "kancelaria": t.split("|")[2]})
    monkeypatch.setattr(autoryzacja.logowanie, "czy_jwt", lambda t: t.startswith("jwt|"))

    app = FastAPI()
    app.middleware("http")(autoryzacja.middleware)
    app.include_router(autoryzacja.router)
    app.include_router(autoryzacja.router_logowania)
    app.include_router(autoryzacja.router_zespolu)
    return TestClient(app), atrapa


def jako(email, kancelaria):
    return {"Authorization": f"Bearer jwt|{email}|{kancelaria}"}


def _kancelaria(klient, email="anna@kancelaria-sobczak.test"):
    odp = klient.post("/api/admin/kancelarie", headers=ADMIN,
                      json={"nazwa": "Kancelaria Sobczak", "email": email})
    assert odp.status_code == 201
    return odp.json()


def test_jeden_formularz_zaklada_kancelarie_i_zaprasza_wlasciciela(srodowisko):
    klient, atrapa = srodowisko
    dane = _kancelaria(klient, "Anna@Kancelaria-Sobczak.TEST")
    assert dane["zaproszono"] == "anna@kancelaria-sobczak.test"
    assert atrapa.utworzeni == ["anna@kancelaria-sobczak.test"]
    lista = klient.get("/api/admin/kancelarie", headers=ADMIN).json()
    assert lista[0]["zespol"][0]["rola"] == "wlasciciel"
    assert lista[0]["zespol"][0]["dolaczyl"] is None


def test_bledny_adres_nie_zostawia_kancelarii(srodowisko):
    klient, _ = srodowisko
    odp = klient.post("/api/admin/kancelarie", headers=ADMIN,
                      json={"nazwa": "Kancelaria Pawlak", "email": "to-nie-adres"})
    assert odp.status_code == 400
    assert klient.get("/api/admin/kancelarie", headers=ADMIN).json() == []


def test_wlasciciel_zaprasza_i_usuwa_czlonka(srodowisko):
    klient, atrapa = srodowisko
    k = _kancelaria(klient)["id"]
    wl = jako("anna@kancelaria-sobczak.test", k)

    odp = klient.post("/api/zespol", headers=wl, json={"email": "jan@kancelaria-sobczak.test"})
    assert odp.status_code == 201 and odp.json()["rola"] == "czlonek"
    zespol = klient.get("/api/zespol", headers=wl).json()
    assert zespol["jestem_wlascicielem"] is True
    assert [o["email"] for o in zespol["osoby"]] == [
        "anna@kancelaria-sobczak.test", "jan@kancelaria-sobczak.test"]

    assert klient.post("/api/zespol/jan@kancelaria-sobczak.test/ponow",
                       headers=wl).status_code == 200
    assert atrapa.ponowione == ["jan@kancelaria-sobczak.test"]

    assert klient.delete("/api/zespol/jan@kancelaria-sobczak.test", headers=wl).status_code == 200
    assert atrapa.usunieci == ["jan@kancelaria-sobczak.test"]
    assert len(klient.get("/api/zespol", headers=wl).json()["osoby"]) == 1


def test_czlonek_nie_zaprasza(srodowisko):
    klient, atrapa = srodowisko
    k = _kancelaria(klient)["id"]
    klient.post("/api/zespol", headers=jako("anna@kancelaria-sobczak.test", k),
                json={"email": "jan@kancelaria-sobczak.test"})
    czl = jako("jan@kancelaria-sobczak.test", k)
    assert klient.get("/api/zespol", headers=czl).json()["jestem_wlascicielem"] is False
    assert klient.post("/api/zespol", headers=czl,
                       json={"email": "obcy@example.test"}).status_code == 403
    assert klient.delete("/api/zespol/anna@kancelaria-sobczak.test", headers=czl).status_code == 403
    assert "obcy@example.test" not in atrapa.utworzeni


def test_wlasciciel_nie_usuwa_siebie(srodowisko):
    klient, _ = srodowisko
    k = _kancelaria(klient)["id"]
    wl = jako("anna@kancelaria-sobczak.test", k)
    assert klient.delete("/api/zespol/anna@kancelaria-sobczak.test", headers=wl).status_code == 400


def test_zespol_nie_siega_do_innej_kancelarii(srodowisko):
    """Kancelarie bierzemy z podpisanego tokenu, nie z zadania."""
    klient, _ = srodowisko
    k1 = _kancelaria(klient)["id"]
    k2 = klient.post("/api/admin/kancelarie", headers=ADMIN,
                     json={"nazwa": "Kancelaria Pawlak", "email": "ewa@kancelaria-pawlak.test"}
                     ).json()["id"]
    klient.post("/api/zespol", headers=jako("ewa@kancelaria-pawlak.test", k2),
                json={"email": "piotr@kancelaria-pawlak.test"})
    wl1 = jako("anna@kancelaria-sobczak.test", k1)
    assert klient.delete("/api/zespol/piotr@kancelaria-pawlak.test", headers=wl1).status_code == 404
    assert len(klient.get("/api/zespol", headers=wl1).json()["osoby"]) == 1


def test_administrator_nie_dopisze_osoby_do_zespolu(srodowisko):
    """Inaczej moglby dopisac siebie i czytac sprawy kancelarii."""
    klient, atrapa = srodowisko
    k = _kancelaria(klient)["id"]
    odp = klient.post("/api/admin/uzytkownicy", headers=ADMIN,
                      json={"email": "obcy@fundacja.test", "kancelaria": k})
    assert odp.status_code == 409
    odp = klient.put(f"/api/admin/kancelarie/{k}/zespol/obcy@fundacja.test",
                     headers=ADMIN, json={"rola": "czlonek"})
    assert odp.status_code == 404
    assert atrapa.utworzeni == ["anna@kancelaria-sobczak.test"]
    osoby = klient.get("/api/zespol", headers=jako("anna@kancelaria-sobczak.test", k)).json()["osoby"]
    assert [o["email"] for o in osoby] == ["anna@kancelaria-sobczak.test"]


def test_ponowienie_po_ustawieniu_hasla_tlumaczy_co_robic(srodowisko):
    klient, atrapa = srodowisko
    k = _kancelaria(klient)["id"]
    atrapa.ustawione_haslo.add("anna@kancelaria-sobczak.test")
    odp = klient.post(f"/api/admin/kancelarie/{k}/zespol/anna@kancelaria-sobczak.test/ponow",
                      headers=ADMIN)
    assert odp.status_code == 409 and "Nie pamietam hasla" in odp.json()["detail"]


def test_pierwsze_logowanie_konczy_zaproszenie(srodowisko, monkeypatch):
    klient, atrapa = srodowisko
    k = _kancelaria(klient)["id"]
    import autoryzacja
    monkeypatch.setattr(autoryzacja.logowanie, "zaloguj",
                        lambda e, h: {"token": f"jwt|{e}|{k}", "odnowienie": ""})
    klient.post("/api/logowanie", json={"email": "anna@kancelaria-sobczak.test", "haslo": "x"})
    osoba = klient.get("/api/admin/kancelarie", headers=ADMIN).json()[0]["zespol"][0]
    assert osoba["dolaczyl"]


def test_konto_sprzed_zespolow_dopisuje_sie_jako_czlonek(srodowisko, monkeypatch):
    """Wlasciciela wskazuje administrator - pierwsze logowanie nie nadaje praw."""
    klient, _ = srodowisko
    k = klient.post("/api/admin/kancelarie", headers=ADMIN,
                    json={"nazwa": "Kancelaria Pawlak"}).json()["id"]
    import autoryzacja
    monkeypatch.setattr(autoryzacja.logowanie, "zaloguj",
                        lambda e, h: {"token": f"jwt|{e}|{k}", "odnowienie": ""})
    klient.post("/api/logowanie", json={"email": "ewa@kancelaria-pawlak.test", "haslo": "x"})
    ja = jako("ewa@kancelaria-pawlak.test", k)
    assert klient.get("/api/zespol", headers=ja).json()["jestem_wlascicielem"] is False

    assert klient.put(f"/api/admin/kancelarie/{k}/zespol/ewa@kancelaria-pawlak.test",
                      headers=ADMIN, json={"rola": "wlasciciel"}).status_code == 200
    assert klient.get("/api/zespol", headers=ja).json()["jestem_wlascicielem"] is True


def test_wylaczenie_kancelarii_odcina_zalogowanych(srodowisko):
    klient, _ = srodowisko
    k = _kancelaria(klient)["id"]
    wl = jako("anna@kancelaria-sobczak.test", k)
    assert klient.get("/api/zespol", headers=wl).status_code == 200
    klient.delete(f"/api/admin/kancelarie/{k}", headers=ADMIN)
    assert klient.get("/api/zespol", headers=wl).status_code == 401
    klient.put(f"/api/admin/kancelarie/{k}/aktywna", headers=ADMIN)
    assert klient.get("/api/zespol", headers=wl).status_code == 200


def test_adresy_nie_trafiaja_do_logow(srodowisko, caplog):
    klient, _ = srodowisko
    caplog.set_level("INFO")
    k = _kancelaria(klient)["id"]
    klient.post("/api/zespol", headers=jako("anna@kancelaria-sobczak.test", k),
                json={"email": "jan@kancelaria-sobczak.test"})
    assert "@" not in caplog.text


class TestUsuniecieDanychKancelarii:
    """Koniec uslugi: umowa powierzenia obiecuje usuniecie wszystkich danych."""

    def _sciezka(self, klient, k):
        import config
        katalog = config.DANE / "kancelarie" / k / "sprawy" / "sprawa1"
        katalog.mkdir(parents=True)
        (katalog / "sprawa.json").write_text("{}")
        return katalog

    def test_kasuje_konta_pliki_i_wpis(self, srodowisko):
        klient, atrapa = srodowisko
        k = _kancelaria(klient)["id"]
        klient.post("/api/zespol", headers=jako("anna@kancelaria-sobczak.test", k),
                    json={"email": "jan@kancelaria-sobczak.test"})
        katalog = self._sciezka(klient, k)
        assert klient.delete(f"/api/admin/kancelarie/{k}", headers=ADMIN).status_code == 200

        odp = klient.post(f"/api/admin/kancelarie/{k}/usun-dane", headers=ADMIN,
                          json={"potwierdzenie": k})

        assert odp.status_code == 200
        assert odp.json()["konta"] == 2
        assert sorted(atrapa.usunieci) == ["anna@kancelaria-sobczak.test",
                                          "jan@kancelaria-sobczak.test"]
        assert not katalog.parent.parent.exists(), "na dysku nie moze nic zostac"
        assert klient.get("/api/admin/kancelarie", headers=ADMIN).json() == []

    def test_aktywnej_nie_usuwa(self, srodowisko):
        klient, atrapa = srodowisko
        k = _kancelaria(klient)["id"]
        odp = klient.post(f"/api/admin/kancelarie/{k}/usun-dane", headers=ADMIN,
                          json={"potwierdzenie": k})
        assert odp.status_code == 409
        assert atrapa.usunieci == []

    def test_wymaga_przepisania_identyfikatora(self, srodowisko):
        klient, atrapa = srodowisko
        k = _kancelaria(klient)["id"]
        katalog = self._sciezka(klient, k)
        klient.delete(f"/api/admin/kancelarie/{k}", headers=ADMIN)
        odp = klient.post(f"/api/admin/kancelarie/{k}/usun-dane", headers=ADMIN,
                          json={"potwierdzenie": "tak"})
        assert odp.status_code == 400
        assert katalog.exists() and atrapa.usunieci == []

    def test_wymaga_admina(self, srodowisko):
        klient, _ = srodowisko
        k = _kancelaria(klient)["id"]
        klient.delete(f"/api/admin/kancelarie/{k}", headers=ADMIN)
        odp = klient.post(f"/api/admin/kancelarie/{k}/usun-dane",
                          headers=jako("anna@kancelaria-sobczak.test", k),
                          json={"potwierdzenie": k})
        assert odp.status_code == 401

    def test_nie_rusza_innej_kancelarii(self, srodowisko):
        klient, atrapa = srodowisko
        k1 = _kancelaria(klient)["id"]
        k2 = klient.post("/api/admin/kancelarie", headers=ADMIN,
                         json={"nazwa": "Kancelaria Pawlak", "email": "ewa@kancelaria-pawlak.test"}
                         ).json()["id"]
        inna = self._sciezka(klient, k2)
        klient.delete(f"/api/admin/kancelarie/{k1}", headers=ADMIN)
        klient.post(f"/api/admin/kancelarie/{k1}/usun-dane", headers=ADMIN,
                    json={"potwierdzenie": k1})
        assert inna.exists()
        assert "ewa@kancelaria-pawlak.test" not in atrapa.usunieci
        assert [w["id"] for w in klient.get("/api/admin/kancelarie", headers=ADMIN).json()] == [k2]


def test_nazwa_admin_nie_zajmuje_zastrzezonego_obszaru(srodowisko):
    """Obszar "admin" w magazynie to rejestr kancelarii, nie kancelaria."""
    klient, _ = srodowisko
    odp = klient.post("/api/admin/kancelarie", headers=ADMIN, json={"nazwa": "Admin"})
    assert odp.status_code == 201
    assert odp.json()["id"] != "admin"
