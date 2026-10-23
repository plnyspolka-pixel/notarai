"""Administrator wchodzi do /admin e-mailem i haslem, token jest awaryjny.
Cognito zastapione atrapa, bez sieci. Adresy fikcyjne."""
from test_zespol import ADMIN, jako, srodowisko  # noqa: F401
from test_logowanie import _przywroc_moduly, logowanie_atrapa  # noqa: F401

ADMINKA = "anna.pieczak@example.test"


def _jako_admin(email=ADMINKA):
    return jako(email, "_administracja")


def _dodaj(klient, email=ADMINKA, naglowki=ADMIN):
    return klient.post("/api/admin/administratorzy", headers=naglowki, json={"email": email})


def test_token_awaryjny_dodaje_pierwszego_administratora(srodowisko):
    klient, atrapa = srodowisko
    assert _dodaj(klient).status_code == 201
    assert ADMINKA in atrapa.utworzeni
    lista = klient.get("/api/admin/administratorzy", headers=ADMIN).json()
    assert lista == {"ja": "", "administratorzy": [ADMINKA]}


def test_administrator_po_zalogowaniu_zaklada_kancelarie(srodowisko):
    klient, _ = srodowisko
    _dodaj(klient)
    odp = klient.post("/api/admin/kancelarie", headers=_jako_admin(),
                      json={"nazwa": "Kancelaria Pawlak", "email": "ewa@kancelaria-pawlak.test"})
    assert odp.status_code == 201
    assert klient.get("/api/admin/administratorzy", headers=_jako_admin()).json()["ja"] == ADMINKA


def test_spoza_listy_nie_wejdzie(srodowisko):
    klient, _ = srodowisko
    _dodaj(klient)
    assert klient.get("/api/admin/kancelarie", headers=_jako_admin("obcy@example.test")).status_code == 401


def test_notariusz_nie_jest_administratorem(srodowisko):
    """Ten sam adres w kancelarii nie daje praw - liczy sie obszar konta."""
    klient, _ = srodowisko
    _dodaj(klient)
    k = klient.post("/api/admin/kancelarie", headers=ADMIN, json={"nazwa": "Kancelaria Sobczak"}).json()["id"]
    assert klient.get("/api/admin/kancelarie", headers=jako(ADMINKA, k)).status_code == 401


def test_konto_administratora_nie_otwiera_spraw(srodowisko):
    klient, _ = srodowisko
    _dodaj(klient)
    assert klient.get("/api/zespol", headers=_jako_admin()).status_code == 401


def test_administrator_dodaje_i_usuwa_innego(srodowisko):
    klient, atrapa = srodowisko
    _dodaj(klient)
    assert _dodaj(klient, "marek@example.test", _jako_admin()).status_code == 201
    assert _dodaj(klient, "marek@example.test", _jako_admin()).status_code == 409
    assert klient.post("/api/admin/administratorzy/marek@example.test/ponow",
                       headers=_jako_admin()).status_code == 200
    assert klient.delete("/api/admin/administratorzy/marek@example.test",
                         headers=_jako_admin()).status_code == 200
    assert "marek@example.test" in atrapa.usunieci
    assert klient.get("/api/admin/kancelarie", headers=_jako_admin("marek@example.test")).status_code == 401


def test_nie_usuwa_samego_siebie(srodowisko):
    klient, _ = srodowisko
    _dodaj(klient)
    assert klient.delete(f"/api/admin/administratorzy/{ADMINKA}",
                         headers=_jako_admin()).status_code == 400


def test_adres_zajety_przez_notariusza(srodowisko):
    klient, _ = srodowisko
    klient.post("/api/admin/kancelarie", headers=ADMIN,
                json={"nazwa": "Kancelaria Sobczak", "email": ADMINKA})
    odp = _dodaj(klient)
    assert odp.status_code == 409 and "osobnego adresu" in odp.json()["detail"]
    assert klient.get("/api/admin/administratorzy", headers=ADMIN).json()["administratorzy"] == []
