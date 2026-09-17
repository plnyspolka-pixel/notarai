"""Testy autoryzacji SaaS - middleware i panel admina. Bez sieci, bez Bedrock."""
import importlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _przywroc_moduly():
    """Po kazdym tescie przeladowuje magazyn i autoryzacje z przywroconym
    srodowiskiem. Bez tego ostatni reload z PIECZAPP_MULTI=true zostawia
    autoryzacja.MULTI=True i testy API w innych plikach dostaja 401."""
    yield
    import magazyn
    import autoryzacja
    importlib.reload(magazyn)
    importlib.reload(autoryzacja)


def _apka(monkeypatch, tmp_path, multi: bool, admin: str = "sekret-admina"):
    monkeypatch.setenv("PIECZAPP_MULTI", "true" if multi else "false")
    monkeypatch.setenv("PIECZAPP_ADMIN_TOKEN", admin)
    monkeypatch.setenv("PIECZAPP_MAGAZYN", "lokalny")

    import config
    import magazyn
    import autoryzacja
    importlib.reload(magazyn)
    importlib.reload(autoryzacja)
    # rejestr kancelarii w katalogu tymczasowym
    monkeypatch.setattr(config, "DANE", tmp_path)

    app = FastAPI()
    app.middleware("http")(autoryzacja.middleware)
    app.include_router(autoryzacja.router)

    @app.get("/api/sprawy")
    def sprawy():
        return {"kancelaria": magazyn.kancelaria_var.get()}

    @app.get("/zdrowie")
    def zdrowie():
        return {"status": "ok"}

    return TestClient(app), autoryzacja


def test_tryb_lokalny_bez_tokenu(monkeypatch, tmp_path):
    klient, _ = _apka(monkeypatch, tmp_path, multi=False)
    assert klient.get("/api/sprawy").status_code == 200


def test_multi_wymaga_tokenu(monkeypatch, tmp_path):
    klient, _ = _apka(monkeypatch, tmp_path, multi=True)
    assert klient.get("/api/sprawy").status_code == 401
    assert klient.get("/api/sprawy", headers={"Authorization": "Bearer zly"}).status_code == 401
    # zdrowie otwarte dla sondy App Runner
    assert klient.get("/zdrowie").status_code == 200


def test_admin_dodaje_kancelarie_i_token_dziala(monkeypatch, tmp_path):
    klient, aut = _apka(monkeypatch, tmp_path, multi=True)
    naglowki_admina = {"Authorization": "Bearer sekret-admina"}

    # bez tokenu admina - odmowa
    assert klient.get("/api/admin/kancelarie").status_code == 401

    odp = klient.post("/api/admin/kancelarie", json={"nazwa": "Kancelaria Kowalski"},
                      headers=naglowki_admina)
    assert odp.status_code == 201
    dane = odp.json()
    assert dane["id"].startswith("kancelaria-kowalski")
    token = dane["token"]
    assert len(token) == 64

    # token kancelarii otwiera /api/* i ustawia kontekst kancelarii
    odp = klient.get("/api/sprawy", headers={"Authorization": f"Bearer {token}"})
    assert odp.status_code == 200
    assert odp.json()["kancelaria"] == dane["id"]

    # rejestr trzyma hash, nie token
    zapis = (tmp_path / "kancelarie.json").read_text("utf-8")
    assert token not in zapis

    # lista widoczna dla admina
    lista = klient.get("/api/admin/kancelarie", headers=naglowki_admina).json()
    assert [k["id"] for k in lista] == [dane["id"]]


def test_dezaktywacja_odbiera_dostep(monkeypatch, tmp_path):
    klient, aut = _apka(monkeypatch, tmp_path, multi=True)
    naglowki_admina = {"Authorization": "Bearer sekret-admina"}
    dane = klient.post("/api/admin/kancelarie", json={"nazwa": "Testowa"},
                       headers=naglowki_admina).json()
    token = {"Authorization": f"Bearer {dane['token']}"}
    assert klient.get("/api/sprawy", headers=token).status_code == 200

    assert klient.delete(f"/api/admin/kancelarie/{dane['id']}",
                         headers=naglowki_admina).status_code == 200
    aut._CACHE = None  # w produkcji cache wygasa po 60 s
    assert klient.get("/api/sprawy", headers=token).status_code == 401


class _Zadanie:
    """Minimalna atrapa Request - liczy sie tylko naglowek Authorization."""

    def __init__(self, naglowek: str = ""):
        self.headers = {"authorization": naglowek}


def test_czy_admin_bez_wyjatku(monkeypatch, tmp_path):
    _, aut = _apka(monkeypatch, tmp_path, multi=True)
    assert aut.czy_admin(_Zadanie("Bearer sekret-admina")) is True
    assert aut.czy_admin(_Zadanie("Bearer zly")) is False
    assert aut.czy_admin(_Zadanie()) is False


def test_czy_admin_bez_ustawionego_tokenu(monkeypatch, tmp_path):
    """Bez PIECZAPP_ADMIN_TOKEN nikt nie jest adminem - takze z pustym naglowkiem."""
    _, aut = _apka(monkeypatch, tmp_path, multi=True, admin="")
    assert aut.czy_admin(_Zadanie()) is False
    assert aut.czy_admin(_Zadanie("Bearer ")) is False


def test_sonda_zdrowia_nie_zdradza_konfiguracji(monkeypatch, tmp_path):
    """Sonda jest otwarta, wiec publicznie oddaje sam status.

    Tryb magazynu, model i region to informacje o wnetrzu uslugi - widzi je
    tylko administrator.
    """
    import importlib

    monkeypatch.setenv("PIECZAPP_MULTI", "true")
    monkeypatch.setenv("PIECZAPP_ADMIN_TOKEN", "sekret-admina")
    monkeypatch.setenv("PIECZAPP_MAGAZYN", "lokalny")
    import magazyn
    import autoryzacja
    importlib.reload(magazyn)
    importlib.reload(autoryzacja)
    import app as aplikacja
    importlib.reload(aplikacja)

    klient = TestClient(aplikacja.app)

    jawne = klient.get("/zdrowie")
    assert jawne.status_code == 200
    assert jawne.json() == {"status": "ok"}

    zly = klient.get("/zdrowie", headers={"Authorization": "Bearer zly"})
    assert zly.json() == {"status": "ok"}

    admin = klient.get("/zdrowie", headers={"Authorization": "Bearer sekret-admina"}).json()
    assert admin["status"] == "ok"
    assert {"magazyn", "multi", "model", "region"} <= set(admin)
