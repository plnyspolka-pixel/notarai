"""Abonament przez Tpay: daty, podpis JWS powiadomien, blokada po terminie.
Bez sieci: certyfikaty z wlasnego CA testowego, Tpay zastapiony atrapa.
Kancelaria i adresy fikcyjne."""
import base64
import importlib
import json
import logging
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID
from fastapi import FastAPI
from fastapi.testclient import TestClient

import platnosci
from test_logowanie import AtrapaCognito, _przywroc_moduly, logowanie_atrapa  # noqa: F401

ADMIN = {"Authorization": "Bearer sekret-admina"}
WLASCICIEL = "anna@kancelaria-sobczak.test"
CZLONEK = "piotr@kancelaria-sobczak.test"
X5U = "https://secure.tpay.com/x509/notifications-jws.pem"


# --- certyfikaty testowe -----------------------------------------------------

def _klucz():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _cert(nazwa, klucz, wystawca=None, klucz_wystawcy=None, dni=30):
    teraz = datetime.now(timezone.utc)
    podmiot = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, nazwa)])
    return (x509.CertificateBuilder()
            .subject_name(podmiot)
            .issuer_name(wystawca.subject if wystawca else podmiot)
            .public_key(klucz.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(teraz - timedelta(days=1))
            .not_valid_after(teraz + timedelta(days=dni))
            .sign(klucz_wystawcy or klucz, hashes.SHA256()))


@pytest.fixture(scope="module")
def pki():
    klucz_ca = _klucz()
    ca = _cert("Testowe CA", klucz_ca)
    klucz = _klucz()
    cert = _cert("notification.tpay.com", klucz, ca, klucz_ca)
    return {"ca": ca, "klucz_ca": klucz_ca, "klucz": klucz, "cert": cert}


def _b64(dane: bytes) -> str:
    return base64.urlsafe_b64encode(dane).decode().rstrip("=")


def podpisz(tresc: bytes, klucz, x5u=X5U) -> str:
    naglowek = _b64(json.dumps({"alg": "RS256", "x5u": x5u}).encode())
    podpis = klucz.sign((naglowek + "." + _b64(tresc)).encode(), padding.PKCS1v15(), hashes.SHA256())
    return f"{naglowek}..{_b64(podpis)}"


# --- daty --------------------------------------------------------------------

def test_wplata_przed_terminem_dolicza_miesiac_do_konca_okresu():
    assert platnosci.przedluz("2026-11-10", date(2026, 11, 1)) == "2026-12-10"


def test_wplata_po_terminie_liczy_miesiac_od_dzis():
    assert platnosci.przedluz("2026-09-01", date(2026, 10, 23)) == "2026-11-23"


def test_pierwsza_wplata_bez_terminu():
    assert platnosci.przedluz(None, date(2026, 10, 23)) == "2026-11-23"


def test_koniec_miesiaca_i_roku():
    assert platnosci.przedluz(None, date(2027, 1, 31)) == "2027-02-28"
    assert platnosci.przedluz(None, date(2028, 1, 31)) == "2028-02-29"
    assert platnosci.przedluz(None, date(2026, 12, 15)) == "2027-01-15"


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


# --- podpis JWS --------------------------------------------------------------

def test_poprawny_podpis(pki):
    tresc = b"id=1&tr_id=TR-1"
    platnosci.sprawdz_podpis(tresc, podpisz(tresc, pki["klucz"]), cert=pki["cert"])


def test_zmieniona_tresc_odrzucona(pki):
    jws = podpisz(b"tr_amount=1.00", pki["klucz"])
    with pytest.raises(platnosci.BladPodpisu):
        platnosci.sprawdz_podpis(b"tr_amount=9999.00", jws, cert=pki["cert"])


def test_podpis_obcym_kluczem_odrzucony(pki):
    tresc = b"id=1"
    with pytest.raises(platnosci.BladPodpisu):
        platnosci.sprawdz_podpis(tresc, podpisz(tresc, _klucz()), cert=pki["cert"])


def test_brak_podpisu(pki):
    with pytest.raises(platnosci.BladPodpisu):
        platnosci.sprawdz_podpis(b"id=1", "", cert=pki["cert"])


@pytest.mark.parametrize("x5u", [
    "https://secure.tpay.com.zly.pl/x509/notifications-jws.pem",
    "https://zly.pl/x509/notifications-jws.pem",
    "http://secure.tpay.com/x509/notifications-jws.pem",
])
def test_certyfikat_tylko_z_hosta_tpay(pki, x5u):
    tresc = b"id=1"
    with pytest.raises(platnosci.BladPodpisu, match="x5u"):
        platnosci.sprawdz_podpis(tresc, podpisz(tresc, pki["klucz"], x5u))


def test_certyfikat_od_ca_tpay(pki):
    platnosci.sprawdz_certyfikat(pki["cert"], [pki["ca"]])


def test_certyfikat_od_obcego_ca(pki):
    klucz = _klucz()
    obcy = _cert("notification.tpay.com", klucz)   # sam sie podpisal
    with pytest.raises(platnosci.BladPodpisu, match="CA"):
        platnosci.sprawdz_certyfikat(obcy, [pki["ca"]])


def test_certyfikat_nie_dla_powiadomien(pki):
    inny = _cert("sklep.tpay.com", _klucz(), pki["ca"], pki["klucz_ca"])
    with pytest.raises(platnosci.BladPodpisu, match="powiadomien"):
        platnosci.sprawdz_certyfikat(inny, [pki["ca"]])


def test_ca_z_repozytorium_wczytuje_sie():
    assert len(platnosci._zaufane_ca()) >= 1


def test_suma_md5_gdy_jest_kod(pki, monkeypatch):
    monkeypatch.setattr(platnosci, "_certyfikat", lambda x5u: pki["cert"])
    monkeypatch.setattr(platnosci, "KOD_BEZPIECZENSTWA", "kod-testowy")
    pola = {"id": "1010", "tr_id": "TR-ABC", "tr_amount": "199.00",
            "tr_crc": "abonament|sobczak|ab12", "tr_status": "TRUE", "md5sum": "zla"}
    tresc = urlencode(pola).encode()
    with pytest.raises(platnosci.BladPodpisu, match="md5"):
        platnosci.odczytaj_powiadomienie(tresc, podpisz(tresc, pki["klucz"]))
    import hashlib
    pola["md5sum"] = hashlib.md5(b"1010TR-ABC199.00abonament|sobczak|ab12kod-testowy").hexdigest()
    tresc = urlencode(pola).encode()
    assert platnosci.odczytaj_powiadomienie(tresc, podpisz(tresc, pki["klucz"]))["tr_id"] == "TR-ABC"


# --- serwer ------------------------------------------------------------------

@pytest.fixture
def serwer(logowanie_atrapa, monkeypatch, tmp_path, pki):
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
    for nazwa, wartosc in {"CLIENT_ID": "id-testowy", "CLIENT_SECRET": "sekret-testowy",
                           "CENA": "199", "ADRES": "https://app.notarai.test",
                           "KOD_BEZPIECZENSTWA": ""}.items():
        monkeypatch.setattr(platnosci, nazwa, wartosc)
    monkeypatch.setattr(platnosci, "_certyfikat", lambda x5u: pki["cert"])

    app = FastAPI()
    app.middleware("http")(autoryzacja.middleware)
    for r in (autoryzacja.router, autoryzacja.router_logowania, autoryzacja.router_zespolu,
              autoryzacja.router_abonamentu, autoryzacja.router_tpay):
        app.include_router(r)

    @app.get("/api/sprawy")
    def sprawy():
        return []

    klient = TestClient(app)
    odp = klient.post("/api/admin/kancelarie", headers=ADMIN, json={"nazwa": "Sobczak"})
    assert odp.status_code == 201
    id_k = odp.json()["id"]
    for email, rola in ((WLASCICIEL, "wlasciciel"), (CZLONEK, "czlonek")):
        klient.put(f"/api/admin/kancelarie/{id_k}/zespol/{email}", headers=ADMIN, json={"rola": rola})
    return klient, id_k, autoryzacja


def jako(email, id_k):
    return {"Authorization": f"Bearer jwt|{email}|{id_k}"}


def _termin(klient, id_k):
    return next(k for k in klient.get("/api/admin/kancelarie", headers=ADMIN).json()
                if k["id"] == id_k)["oplacono_do"]


def _ustaw_termin(klient, id_k, termin):
    assert klient.put(f"/api/admin/kancelarie/{id_k}/abonament", headers=ADMIN,
                      json={"oplacono_do": termin}).status_code == 200


def _powiadom(klient, pki, id_k, tr_id="TR-0001", status="TRUE", klucz=None):
    tresc = urlencode({"id": "1010", "tr_id": tr_id, "tr_date": "2026-10-23 12:00:00",
                       "tr_crc": f"abonament|{id_k}|ab12", "tr_amount": "199.00",
                       "tr_paid": "199.00", "tr_desc": "notarai", "tr_status": status,
                       "tr_error": "none", "tr_email": WLASCICIEL, "md5sum": "x",
                       "test_mode": "0"}).encode()
    return klient.post("/api/tpay/powiadomienie", content=tresc,
                       headers={"Content-Type": "application/x-www-form-urlencoded",
                                "X-JWS-Signature": podpisz(tresc, klucz or pki["klucz"])})


def test_nowa_kancelaria_dostaje_okres_probny(serwer):
    klient, id_k, _ = serwer
    assert _termin(klient, id_k) == platnosci.na_probe()


def test_powiadomienie_przedluza_abonament(serwer, pki):
    klient, id_k, _ = serwer
    _ustaw_termin(klient, id_k, "2026-01-10")
    odp = _powiadom(klient, pki, id_k)
    assert odp.status_code == 200 and odp.text == "TRUE"
    assert _termin(klient, id_k) == platnosci.przedluz("2026-01-10")


def test_powtorzone_powiadomienie_liczy_sie_raz(serwer, pki):
    klient, id_k, _ = serwer
    _powiadom(klient, pki, id_k)
    po_pierwszym = _termin(klient, id_k)
    assert _powiadom(klient, pki, id_k).text == "TRUE"
    assert _termin(klient, id_k) == po_pierwszym


def test_falszywe_powiadomienie_odrzucone(serwer, pki):
    klient, id_k, _ = serwer
    przed = _termin(klient, id_k)
    odp = _powiadom(klient, pki, id_k, klucz=_klucz())
    assert odp.status_code == 400
    assert _termin(klient, id_k) == przed


def test_zwrot_nie_przedluza(serwer, pki):
    klient, id_k, _ = serwer
    przed = _termin(klient, id_k)
    assert _powiadom(klient, pki, id_k, status="chargeback").text == "TRUE"
    assert _termin(klient, id_k) == przed


def test_wplata_nieznanej_kancelarii_potwierdzona_bez_zmian(serwer, pki):
    klient, _, _ = serwer
    assert _powiadom(klient, pki, "nie-ma-takiej").text == "TRUE"


def test_po_terminie_blokada_ale_abonament_otwarty(serwer):
    klient, id_k, _ = serwer
    _ustaw_termin(klient, id_k, "2020-01-01")
    odp = klient.get("/api/sprawy", headers=jako(CZLONEK, id_k))
    assert odp.status_code == 402 and odp.json()["abonament"] is True
    stan = klient.get("/api/abonament", headers=jako(CZLONEK, id_k)).json()
    assert stan["wazny"] is False and stan["moge_zaplacic"] is False
    assert klient.get("/api/zespol", headers=jako(CZLONEK, id_k)).status_code == 200


def test_bez_platnosci_nikogo_nie_blokujemy(serwer, monkeypatch):
    klient, id_k, _ = serwer
    _ustaw_termin(klient, id_k, "2020-01-01")
    monkeypatch.setattr(platnosci, "CLIENT_ID", "")
    assert klient.get("/api/sprawy", headers=jako(CZLONEK, id_k)).status_code == 200


def test_kancelaria_bez_terminu_nie_placi(serwer):
    klient, id_k, _ = serwer
    _ustaw_termin(klient, id_k, "")
    assert klient.get("/api/sprawy", headers=jako(CZLONEK, id_k)).status_code == 200
    assert klient.get("/api/abonament", headers=jako(WLASCICIEL, id_k)).json()["wymagany"] is False


def test_zly_format_daty(serwer):
    klient, id_k, _ = serwer
    assert klient.put(f"/api/admin/kancelarie/{id_k}/abonament", headers=ADMIN,
                      json={"oplacono_do": "jutro"}).status_code == 400


def test_placi_tylko_wlasciciel(serwer, monkeypatch):
    klient, id_k, _ = serwer
    monkeypatch.setattr(platnosci, "utworz_transakcje",
                        lambda k, n, e: {"adres": "https://secure.tpay.com/?title=TR-1", "tytul": "TR-1"})
    assert klient.post("/api/abonament", headers=jako(CZLONEK, id_k)).status_code == 403
    odp = klient.post("/api/abonament", headers=jako(WLASCICIEL, id_k))
    assert odp.status_code == 201 and odp.json()["adres"].startswith("https://secure.tpay.com/")


def test_transakcja_w_tpay(monkeypatch, caplog):
    for nazwa, wartosc in {"CLIENT_ID": "id-testowy", "CLIENT_SECRET": "sekret-testowy",
                           "CENA": "199", "ADRES": "https://app.notarai.test"}.items():
        monkeypatch.setattr(platnosci, nazwa, wartosc)
    monkeypatch.setitem(platnosci._TOKEN, "wartosc", "")
    zadania = []

    def tpay(zadanie: httpx.Request):
        zadania.append(zadanie)
        if zadanie.url.path == "/oauth/auth":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 7200})
        assert zadanie.headers["authorization"] == "Bearer tok"
        return httpx.Response(200, json={"result": "success", "title": "TR-XYZ",
                                         "transactionPaymentUrl": "https://secure.tpay.com/?title=TR-XYZ"})

    monkeypatch.setattr(platnosci, "_klient", lambda: httpx.Client(transport=httpx.MockTransport(tpay)))
    with caplog.at_level(logging.INFO):
        wynik = platnosci.utworz_transakcje("sobczak", "Kancelaria Sobczak", WLASCICIEL)
    assert wynik["adres"] == "https://secure.tpay.com/?title=TR-XYZ"
    tresc = json.loads(zadania[1].content)
    assert tresc["amount"] == 199.0
    assert tresc["hiddenDescription"].startswith("abonament|sobczak|")
    assert tresc["callbacks"]["notification"]["url"] == "https://app.notarai.test/api/tpay/powiadomienie"
    assert tresc["payer"]["email"] == WLASCICIEL
    assert WLASCICIEL not in caplog.text and "sekret-testowy" not in caplog.text


def test_odrzucona_transakcja_bez_danych_w_logach(monkeypatch, caplog):
    for nazwa, wartosc in {"CLIENT_ID": "id-testowy", "CLIENT_SECRET": "sekret-testowy",
                           "CENA": "199", "ADRES": "https://app.notarai.test"}.items():
        monkeypatch.setattr(platnosci, nazwa, wartosc)
    monkeypatch.setitem(platnosci._TOKEN, "wartosc", "tok")
    monkeypatch.setitem(platnosci._TOKEN, "wygasa", float("inf"))
    odpowiedz = httpx.Response(400, json={"result": "failed",
                                          "errors": [{"errorCode": "field_invalid", "fieldName": "payer.email"}]})
    monkeypatch.setattr(platnosci, "_klient",
                        lambda: httpx.Client(transport=httpx.MockTransport(lambda z: odpowiedz)))
    with caplog.at_level(logging.INFO), pytest.raises(platnosci.BladPlatnosci):
        platnosci.utworz_transakcje("sobczak", "Kancelaria Sobczak", WLASCICIEL)
    assert "field_invalid" in caplog.text and WLASCICIEL not in caplog.text
