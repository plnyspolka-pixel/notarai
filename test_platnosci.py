"""Abonament w Stripe: podpis webhooka, subskrypcja, faktury, blokada po terminie.
Bez sieci: Stripe zastapiony atrapa. Kancelaria i adresy fikcyjne."""
import hashlib
import hmac
import importlib
import json
import logging
import time
from datetime import date, datetime, timedelta, timezone
from urllib.parse import parse_qs

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import platnosci
from test_logowanie import AtrapaCognito, _przywroc_moduly, logowanie_atrapa  # noqa: F401

ADMIN = {"Authorization": "Bearer sekret-admina"}
WLASCICIEL = "anna@kancelaria-sobczak.test"
CZLONEK = "piotr@kancelaria-sobczak.test"
WHSEC = "whsec_testowy"
KONFIGURACJA = {"KLUCZ": "sk_test_atrapa", "WEBHOOK_SEKRET": WHSEC, "CENA_ID": "price_atrapa",
                "CENA": "600", "ADRES": "https://app.notarai.test"}


def podpisz(tresc: bytes, sekret=WHSEC, czas=None) -> str:
    czas = int(czas or time.time())
    podpis = hmac.new(sekret.encode(), f"{czas}.".encode() + tresc, hashlib.sha256).hexdigest()
    return f"t={czas},v1={podpis}"


def _ts(dzien: date) -> int:
    return int(datetime.combine(dzien, datetime.min.time(), timezone.utc).timestamp())


# --- daty --------------------------------------------------------------------

def test_karencja_po_terminie(monkeypatch):
    monkeypatch.setattr(platnosci, "KARENCJA_DNI", 3)
    wpis = {"oplacono_do": "2026-10-20"}
    assert platnosci.stan(wpis, date(2026, 10, 20))["po_terminie"] is False
    s = platnosci.stan(wpis, date(2026, 10, 23))
    assert s["po_terminie"] and s["wazny"]
    assert platnosci.stan(wpis, date(2026, 10, 24))["wazny"] is False


def test_bez_terminu_abonament_nie_jest_wymagany():
    assert platnosci.stan({}) == {"wymagany": False, "oplacono_do": None,
                                  "wazny": True, "po_terminie": False}


def test_koniec_okresu_z_pozycji_faktury():
    faktura = {"lines": {"data": [{"period": {"start": _ts(date(2026, 10, 24)), "end": _ts(date(2026, 11, 24))}},
                                  {"period": {"start": 1, "end": _ts(date(2026, 11, 20))}}]}}
    assert platnosci.koniec_okresu(faktura) == "2026-11-24"
    assert platnosci.koniec_okresu({}) is None


def test_kancelaria_i_subskrypcja_z_faktury():
    faktura = {"parent": {"subscription_details": {"metadata": {"kancelaria": "sobczak"},
                                                   "subscription": "sub_1"}}}
    assert platnosci.kancelaria_faktury(faktura) == "sobczak"
    assert platnosci.subskrypcja_faktury(faktura) == "sub_1"
    assert platnosci.kancelaria_faktury({"parent": None}) == ""


def test_formularz_stripe():
    pary = platnosci._formularz({"a": 1, "b": {"c": [{"d": "x"}]}, "e": True, "f": None})
    assert pary == [("a", "1"), ("b[c][0][d]", "x"), ("e", "true")]


# --- podpis webhooka ---------------------------------------------------------

def test_poprawny_podpis():
    platnosci.sprawdz_podpis(b'{"a":1}', podpisz(b'{"a":1}'), WHSEC)


def test_zmieniona_tresc_odrzucona():
    with pytest.raises(platnosci.BladPodpisu):
        platnosci.sprawdz_podpis(b'{"a":2}', podpisz(b'{"a":1}'), WHSEC)


def test_obcy_klucz_odrzucony():
    with pytest.raises(platnosci.BladPodpisu):
        platnosci.sprawdz_podpis(b"{}", podpisz(b"{}", "whsec_obcy"), WHSEC)


def test_stary_podpis_odrzucony():
    with pytest.raises(platnosci.BladPodpisu, match="przeterminowany"):
        platnosci.sprawdz_podpis(b"{}", podpisz(b"{}", czas=time.time() - 600), WHSEC)


def test_jeden_z_kilku_podpisow_wystarczy():
    # Przy wymianie klucza Stripe wysyla kilka v1.
    czas = int(time.time())
    dobry = podpisz(b"{}", czas=czas).split("v1=")[1]
    platnosci.sprawdz_podpis(b"{}", f"t={czas},v1=deadbeef,v1={dobry}", WHSEC)


@pytest.mark.parametrize("naglowek", ["", "t=abc,v1=x", "v1=abc", "t=123"])
def test_brak_podpisu(naglowek):
    with pytest.raises(platnosci.BladPodpisu):
        platnosci.sprawdz_podpis(b"{}", naglowek, WHSEC)


def test_bez_sekretu_nic_nie_przechodzi():
    with pytest.raises(platnosci.BladPodpisu):
        platnosci.sprawdz_podpis(b"{}", podpisz(b"{}", ""), "")


# --- API Stripe --------------------------------------------------------------

@pytest.fixture
def stripe_atrapa(monkeypatch):
    for nazwa, wartosc in KONFIGURACJA.items():
        monkeypatch.setattr(platnosci, nazwa, wartosc)
    zadania = []

    def obsluz(zadanie: httpx.Request):
        zadania.append(zadanie)
        if zadanie.url.path == "/v1/checkout/sessions":
            return httpx.Response(200, json={"id": "cs_1", "url": "https://checkout.stripe.com/c/pay/cs_1"})
        return httpx.Response(200, json={"id": "bps_1", "url": "https://billing.stripe.com/p/session/1"})

    monkeypatch.setattr(platnosci, "_klient", lambda: httpx.Client(transport=httpx.MockTransport(obsluz)))
    return zadania


def _pola(zadanie):
    return {k: v[0] for k, v in parse_qs(zadanie.content.decode()).items()}


def test_sesja_platnosci(stripe_atrapa, caplog):
    with caplog.at_level(logging.INFO):
        wynik = platnosci.utworz_checkout("sobczak", WLASCICIEL)
    assert wynik["adres"].startswith("https://checkout.stripe.com/")
    z = stripe_atrapa[0]
    assert z.headers["authorization"] == "Bearer sk_test_atrapa"
    assert z.headers["stripe-version"] == platnosci.WERSJA_API
    pola = _pola(z)
    assert pola["mode"] == "subscription"
    assert pola["line_items[0][price]"] == "price_atrapa"
    assert pola["subscription_data[metadata][kancelaria]"] == "sobczak"
    assert pola["client_reference_id"] == "sobczak"
    assert pola["automatic_tax[enabled]"] == "true"
    assert pola["tax_id_collection[enabled]"] == "true"
    assert pola["customer_email"] == WLASCICIEL
    assert pola["success_url"] == "https://app.notarai.test/?platnosc=ok"
    assert "subscription_data[trial_end]" not in pola
    assert WLASCICIEL not in caplog.text and "sk_test" not in caplog.text


def test_okres_probny_przechodzi_do_stripe(stripe_atrapa):
    za_tydzien = (platnosci.dzis() + timedelta(days=7)).isoformat()
    platnosci.utworz_checkout("sobczak", WLASCICIEL, oplacono_do=za_tydzien)
    assert _pola(stripe_atrapa[0])["subscription_data[trial_end]"] == str(_ts(date.fromisoformat(za_tydzien)))


def test_okres_probny_za_krotki_dla_stripe(stripe_atrapa):
    jutro = (platnosci.dzis() + timedelta(days=1)).isoformat()
    platnosci.utworz_checkout("sobczak", WLASCICIEL, oplacono_do=jutro)
    assert "subscription_data[trial_end]" not in _pola(stripe_atrapa[0])


def test_znany_klient_bez_ponownego_emaila(stripe_atrapa):
    platnosci.utworz_checkout("sobczak", WLASCICIEL, klient="cus_1")
    pola = _pola(stripe_atrapa[0])
    assert pola["customer"] == "cus_1" and "customer_email" not in pola
    assert pola["customer_update[address]"] == "auto"


def test_portal(stripe_atrapa):
    assert platnosci.utworz_portal("cus_1")["adres"].startswith("https://billing.stripe.com/")
    assert _pola(stripe_atrapa[0])["customer"] == "cus_1"


def test_odrzucenie_bez_danych_w_logach(monkeypatch, caplog):
    for nazwa, wartosc in KONFIGURACJA.items():
        monkeypatch.setattr(platnosci, nazwa, wartosc)
    odpowiedz = httpx.Response(400, json={"error": {"type": "invalid_request_error", "code": "email_invalid",
                                                    "message": f"Invalid email {WLASCICIEL}"}})
    monkeypatch.setattr(platnosci, "_klient",
                        lambda: httpx.Client(transport=httpx.MockTransport(lambda z: odpowiedz)))
    with caplog.at_level(logging.INFO), pytest.raises(platnosci.BladPlatnosci):
        platnosci.utworz_checkout("sobczak", WLASCICIEL)
    assert "email_invalid" in caplog.text and WLASCICIEL not in caplog.text


# --- serwer ------------------------------------------------------------------

@pytest.fixture
def serwer(logowanie_atrapa, monkeypatch, tmp_path):
    monkeypatch.setenv("PIECZAPP_MULTI", "true")
    monkeypatch.setenv("PIECZAPP_ADMIN_TOKEN", "sekret-admina")
    monkeypatch.setenv("PIECZAPP_MAGAZYN", "lokalny")
    import config
    import magazyn
    import autoryzacja
    importlib.reload(magazyn)
    importlib.reload(autoryzacja)
    monkeypatch.setattr(config, "DANE", tmp_path)
    monkeypatch.setattr(autoryzacja.logowanie, "_klient", lambda: AtrapaCognito())
    monkeypatch.setattr(autoryzacja.logowanie, "dane_z_tokenu",
                        lambda t: {"email": t.split("|")[1], "kancelaria": t.split("|")[2]})
    monkeypatch.setattr(autoryzacja.logowanie, "czy_jwt", lambda t: t.startswith("jwt|"))
    for nazwa, wartosc in KONFIGURACJA.items():
        monkeypatch.setattr(platnosci, nazwa, wartosc)

    app = FastAPI()
    app.middleware("http")(autoryzacja.middleware)
    for r in (autoryzacja.router, autoryzacja.router_logowania, autoryzacja.router_zespolu,
              autoryzacja.router_abonamentu, autoryzacja.router_stripe):
        app.include_router(r)

    @app.get("/api/sprawy")
    def sprawy():
        return []

    klient = TestClient(app)
    odp = klient.post("/api/admin/kancelarie", headers=ADMIN, json={"nazwa": "Sobczak"})
    assert odp.status_code == 201
    id_k = odp.json()["id"]
    # Tu sprawdzamy platnosci, nie zespol (test_zespol.py) ani akceptacje
    # umowy (test_rejestracja.py) - oba wpisujemy wprost do rejestru.
    rejestr = autoryzacja._wczytaj_rejestr()
    wpis = autoryzacja._znajdz(rejestr, id_k)[1]
    wpis["zespol"] = [{"email": e, "rola": r, "zaproszono": None, "dolaczyl": None}
                      for e, r in ((WLASCICIEL, "wlasciciel"), (CZLONEK, "czlonek"))]
    wpis["umowa"] = {"zaakceptowano": "2026-10-24T10:00:00"}
    autoryzacja._zapisz_rejestr(rejestr)
    return klient, id_k


def jako(email, id_k):
    return {"Authorization": f"Bearer jwt|{email}|{id_k}"}


def _kancelaria(klient, id_k):
    return next(k for k in klient.get("/api/admin/kancelarie", headers=ADMIN).json() if k["id"] == id_k)


def _ustaw_termin(klient, id_k, termin):
    assert klient.put(f"/api/admin/kancelarie/{id_k}/abonament", headers=ADMIN,
                      json={"oplacono_do": termin}).status_code == 200


def _wyslij(klient, typ, obiekt, sekret=WHSEC):
    tresc = json.dumps({"id": "evt_1", "type": typ, "data": {"object": obiekt}}).encode()
    return klient.post("/api/stripe/webhook", content=tresc,
                       headers={"Content-Type": "application/json", "Stripe-Signature": podpisz(tresc, sekret)})


def _faktura(id_k, numer="in_1", koniec=date(2027, 1, 24), kwota=60000):
    return {"id": numer, "object": "invoice", "customer": "cus_1", "amount_paid": kwota,
            "hosted_invoice_url": f"https://invoice.stripe.com/i/{numer}",
            "parent": {"subscription_details": {"metadata": {"kancelaria": id_k}, "subscription": "sub_1"}},
            "lines": {"data": [{"period": {"start": _ts(koniec - timedelta(days=31)), "end": _ts(koniec)}}]}}


def test_nowa_kancelaria_dostaje_okres_probny(serwer):
    klient, id_k = serwer
    assert _kancelaria(klient, id_k)["oplacono_do"] == platnosci.na_probe()


def test_oplacona_faktura_ustawia_termin_i_historie(serwer):
    klient, id_k = serwer
    assert _wyslij(klient, "invoice.paid", _faktura(id_k)).status_code == 200
    stan = klient.get("/api/abonament", headers=jako(WLASCICIEL, id_k)).json()
    assert stan["oplacono_do"] == "2027-01-24"
    assert stan["subskrypcja"] == "active"
    assert stan["historia"][-1]["kwota"] == "600.00"
    assert stan["historia"][-1]["faktura"] == "https://invoice.stripe.com/i/in_1"


def test_powtorzony_webhook_liczy_sie_raz(serwer):
    klient, id_k = serwer
    _wyslij(klient, "invoice.paid", _faktura(id_k))
    _wyslij(klient, "invoice.paid", _faktura(id_k))
    stan = klient.get("/api/abonament", headers=jako(WLASCICIEL, id_k)).json()
    assert len([p for p in stan["historia"] if p["status"] == "true"]) == 1


def test_starsza_faktura_nie_cofa_terminu(serwer):
    klient, id_k = serwer
    _wyslij(klient, "invoice.paid", _faktura(id_k, "in_2", date(2027, 2, 24)))
    _wyslij(klient, "invoice.paid", _faktura(id_k, "in_1", date(2027, 1, 24)))
    assert _kancelaria(klient, id_k)["oplacono_do"] == "2027-02-24"


def test_faktura_zerowa_bez_wpisu_w_historii(serwer):
    klient, id_k = serwer
    _wyslij(klient, "invoice.paid", _faktura(id_k, kwota=0, koniec=date(2027, 3, 1)))
    stan = klient.get("/api/abonament", headers=jako(WLASCICIEL, id_k)).json()
    assert stan["oplacono_do"] == "2027-03-01"
    assert not [p for p in stan["historia"] if p["status"] == "true"]


def test_falszywy_webhook_odrzucony(serwer):
    klient, id_k = serwer
    przed = _kancelaria(klient, id_k)["oplacono_do"]
    assert _wyslij(klient, "invoice.paid", _faktura(id_k), sekret="whsec_obcy").status_code == 400
    assert _kancelaria(klient, id_k)["oplacono_do"] == przed


def test_webhook_nieznanej_kancelarii(serwer):
    klient, _ = serwer
    assert _wyslij(klient, "invoice.paid", _faktura("nie-ma-takiej")).status_code == 200


def test_zakonczona_sesja_zapisuje_klienta(serwer):
    klient, id_k = serwer
    _wyslij(klient, "checkout.session.completed",
            {"client_reference_id": id_k, "customer": "cus_9", "subscription": "sub_9",
             "payment_status": "no_payment_required"})
    stan = klient.get("/api/abonament", headers=jako(WLASCICIEL, id_k)).json()
    assert stan["subskrypcja"] == "trialing"


def test_rezygnacja_i_koniec_subskrypcji(serwer):
    klient, id_k = serwer
    _wyslij(klient, "invoice.paid", _faktura(id_k))
    _wyslij(klient, "customer.subscription.updated",
            {"id": "sub_1", "customer": "cus_1", "status": "active", "cancel_at_period_end": True,
             "metadata": {"kancelaria": id_k}})
    stan = klient.get("/api/abonament", headers=jako(WLASCICIEL, id_k)).json()
    assert stan["konczy_sie"] is True and stan["subskrypcja"] == "active"
    # Zdarzenie bez metadanych - kancelarie wskazuje zapisany klient Stripe.
    _wyslij(klient, "customer.subscription.deleted", {"id": "sub_1", "customer": "cus_1", "status": "canceled"})
    stan = klient.get("/api/abonament", headers=jako(WLASCICIEL, id_k)).json()
    assert stan["subskrypcja"] is None
    assert stan["oplacono_do"] == "2027-01-24"     # oplacony okres zostaje


def test_wlaczenie_abonamentu_tylko_wlasciciel(serwer, monkeypatch):
    klient, id_k = serwer
    wywolania = []
    monkeypatch.setattr(platnosci, "utworz_checkout",
                        lambda *a: wywolania.append(a) or {"adres": "https://checkout.stripe.com/x"})
    assert klient.post("/api/abonament", headers=jako(CZLONEK, id_k)).status_code == 403
    odp = klient.post("/api/abonament", headers=jako(WLASCICIEL, id_k))
    assert odp.status_code == 201 and odp.json()["adres"].startswith("https://checkout.stripe.com/")
    assert wywolania[0][:2] == (id_k, WLASCICIEL)


def test_trwajaca_subskrypcja_prowadzi_do_portalu(serwer, monkeypatch):
    klient, id_k = serwer
    _wyslij(klient, "invoice.paid", _faktura(id_k))
    monkeypatch.setattr(platnosci, "utworz_checkout", lambda *a: pytest.fail("druga subskrypcja"))
    monkeypatch.setattr(platnosci, "utworz_portal", lambda k: {"adres": f"https://billing.stripe.com/{k}"})
    assert klient.post("/api/abonament", headers=jako(WLASCICIEL, id_k)).json()["adres"].endswith("cus_1")
    assert klient.post("/api/abonament/portal", headers=jako(WLASCICIEL, id_k)).status_code == 201


def test_portal_bez_klienta_stripe(serwer):
    klient, id_k = serwer
    assert klient.post("/api/abonament/portal", headers=jako(WLASCICIEL, id_k)).status_code == 409


def test_po_terminie_blokada_ale_abonament_otwarty(serwer):
    klient, id_k = serwer
    _ustaw_termin(klient, id_k, "2020-01-01")
    odp = klient.get("/api/sprawy", headers=jako(CZLONEK, id_k))
    assert odp.status_code == 402 and odp.json()["abonament"] is True
    stan = klient.get("/api/abonament", headers=jako(CZLONEK, id_k)).json()
    assert stan["wazny"] is False and stan["moge_zaplacic"] is False
    assert klient.get("/api/zespol", headers=jako(CZLONEK, id_k)).status_code == 200


def test_bez_platnosci_nikogo_nie_blokujemy(serwer, monkeypatch):
    klient, id_k = serwer
    _ustaw_termin(klient, id_k, "2020-01-01")
    monkeypatch.setattr(platnosci, "KLUCZ", "")
    assert klient.get("/api/sprawy", headers=jako(CZLONEK, id_k)).status_code == 200


def test_kancelaria_bez_terminu_nie_placi(serwer):
    klient, id_k = serwer
    _ustaw_termin(klient, id_k, "")
    assert klient.get("/api/sprawy", headers=jako(CZLONEK, id_k)).status_code == 200
    assert klient.get("/api/abonament", headers=jako(WLASCICIEL, id_k)).json()["wymagany"] is False


def test_zly_format_daty(serwer):
    klient, id_k = serwer
    assert klient.put(f"/api/admin/kancelarie/{id_k}/abonament", headers=ADMIN,
                      json={"oplacono_do": "jutro"}).status_code == 400
