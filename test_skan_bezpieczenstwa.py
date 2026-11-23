"""Skaner bezpieczenstwa kancelarii - bez sieci (DNS, TLS, HTTP, HIBP i CISA KEV na atrapach).

Czesc 1: strona i poczta kancelarii (POST /api/skan).
Czesc 2 na koncu pliku: ten komputer (/ip, /hibp-haslo, /luki)."""
from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient

import skan_bezpieczenstwa as s


@pytest.fixture(autouse=True)
def czysto():
    s._CACHE.clear()
    s.limit_skanu.wyczysc()
    yield
    s._CACHE.clear()


# --- adres i SSRF ----------------------------------------------------------

@pytest.mark.parametrize("wejscie,oczekiwane", [
    ("kancelaria-x.pl", "kancelaria-x.pl"),
    ("https://www.Kancelaria-X.pl/kontakt?a=1", "www.kancelaria-x.pl"),
    ("  http://notariusz.lublin.pl/  ", "notariusz.lublin.pl"),
    ("kancelaria-żółw.pl", "kancelaria-żółw.pl".encode("idna").decode()),
])
def test_normalizacja_adresu(wejscie, oczekiwane):
    assert s.normalizuj_domene(wejscie) == oczekiwane


@pytest.mark.parametrize("zly", ["", "localhost", "127.0.0.1", "http://10.0.0.1/", "[::1]",
                                 "x.local", "serwer.internal", "a..pl", "kancelaria", "http://x.pl:8080/",
                                 "-zla-.pl", "a" * 400 + ".pl"])
def test_odrzucone_adresy(zly):
    with pytest.raises(s.BladSkanu):
        s.normalizuj_domene(zly)


@pytest.mark.parametrize("adres", ["127.0.0.1", "10.1.2.3", "169.254.169.254", "192.168.0.10", "::1"])
def test_nazwa_wskazujaca_siec_wewnetrzna_jest_blokowana(monkeypatch, adres):
    monkeypatch.setattr(s.socket, "getaddrinfo", lambda h, p: [(None, None, None, "", (adres, 0))])
    with pytest.raises(s.BladSkanu):
        s.adresy_publiczne("zly.example.pl")


def test_przekierowanie_do_sieci_wewnetrznej_jest_blokowane(monkeypatch):
    def getaddrinfo(host, port):
        ip = "93.184.216.34" if host == "kancelaria-x.pl" else "169.254.169.254"
        return [(None, None, None, "", (ip, 0))]
    monkeypatch.setattr(s.socket, "getaddrinfo", getaddrinfo)
    wolane = []

    def obsluga(req):
        wolane.append(str(req.url))
        return httpx.Response(302, headers={"location": "http://metadane.example/latest/"})
    prawdziwy = httpx.Client
    monkeypatch.setattr(s.httpx, "Client", lambda **kw: prawdziwy(transport=httpx.MockTransport(obsluga), **kw))
    with pytest.raises(s.BladSkanu):
        s.pobierz("http://kancelaria-x.pl/")
    assert wolane == ["http://kancelaria-x.pl/"]   # do metadanych nie poszlo zadne zadanie


def test_domena_glowna():
    assert s.domena_glowna("www.kancelaria-x.pl") == "kancelaria-x.pl"
    assert s.domena_glowna("www.pl") == "www.pl"


# --- ocena poczty ----------------------------------------------------------

def _poczta(**dns_):
    baza = {"mx": ["10 mx.kancelaria-x.pl."], "txt": [], "dmarc": [], "mta_sts": [], "dkim": []}
    baza.update(dns_)
    o = s.Ocena()
    s.ocen_poczte(o, "kancelaria-x.pl", baza)
    return o, {u["id"]: u for u in o.ustalenia}


def test_brak_dmarc_i_spf_to_podszywanie():
    o, u = _poczta()
    assert u["spf"]["poziom"] == "krytyczne"
    assert u["dmarc"]["poziom"] == "krytyczne"
    assert "biuro@kancelaria-x.pl" in u["dmarc"]["tytul"]
    assert "_dmarc.kancelaria-x.pl" in u["dmarc"]["naprawa"]
    assert o.punkty["poczta"][0] == 0


@pytest.mark.parametrize("spf,poziom", [
    ("v=spf1 include:_spf.google.com -all", "ok"),
    ("v=spf1 include:_spf.google.com ~all", "ok"),
    ("v=spf1 a mx ?all", "uwaga"),
    ("v=spf1 +all", "krytyczne"),
    ("v=spf1 mx all", "krytyczne"),
    ("v=spf1 mx", "uwaga"),
])
def test_spf(spf, poziom):
    _, u = _poczta(txt=[spf, "google-site-verification=abc"])
    assert u["spf"]["poziom"] == poziom


def test_dwa_rekordy_spf_to_blad():
    _, u = _poczta(txt=["v=spf1 -all", "v=spf1 mx -all"])
    assert u["spf"]["poziom"] == "krytyczne"


@pytest.mark.parametrize("dmarc,poziom,punkty", [
    ("v=DMARC1; p=reject; rua=mailto:d@kancelaria-x.pl", "ok", 14),
    ("v=DMARC1; p=quarantine; rua=mailto:d@kancelaria-x.pl", "ok", 11),
    ("v=DMARC1; p=none", "uwaga", 5),
])
def test_dmarc(dmarc, poziom, punkty):
    o, u = _poczta(txt=["v=spf1 -all"], dmarc=[dmarc], dkim=["google"])
    assert u["dmarc"]["poziom"] == poziom
    assert o.punkty["poczta"][0] == 10 + punkty + 4
    assert ("dmarc_rua" in u) == ("rua=" not in dmarc)


def test_dkim_w_zbiorze_rekordow(monkeypatch):
    def txt(nazwa):
        return {"selector1._domainkey.kancelaria-x.pl": ["v=DKIM1; k=rsa; p=MIGfMA0"],
                "google._domainkey.kancelaria-x.pl": ["v=DKIM1; p="]}.get(nazwa, [])
    monkeypatch.setattr(s, "txt", txt)
    monkeypatch.setattr(s, "rekordy", lambda n, t: [])
    assert s.zbierz_dns("kancelaria-x.pl")["dkim"] == ["selector1"]   # pusty klucz = odwolany


# --- strona ----------------------------------------------------------------

STRONA = """<!doctype html><html><head>
<meta name="generator" content="WordPress 6.2.1">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Lato">
<script async src="https://www.googletagmanager.com/gtag/js?id=G-1"></script>
<script src="https://connect.facebook.net/en_US/fbevents.js"></script>
<script src="/wp-includes/js/jquery.js"></script>
<img src="http://kancelaria-x.pl/logo.png">
</head><body><form action="http://kancelaria-x.pl/wyslij"></form></body></html>"""


def test_analiza_html():
    h = s.analizuj_html(STRONA, "https://www.kancelaria-x.pl/")
    nazwy = {z["nazwa"]: z["rodzaj"] for z in h["zewnetrzne"]}
    assert nazwy == {"Google Tag Manager": "sledzenie", "Piksel Meta (Facebook)": "sledzenie",
                     "Google Fonts": "czcionki"}
    assert h["cms"] == "WordPress" and h["generator"] == "WordPress 6.2.1"
    assert h["mieszane"] == 1 and h["formularze_http"] == 1


def test_przestarzale_php_i_ujawnione_wersje():
    o = s.Ocena()
    odp = {"url": "https://kancelaria-x.pl/", "naglowki": httpx.Headers(
        {"server": "Apache/2.4.41 (Ubuntu)", "x-powered-by": "PHP/7.4.3"}), "ciasteczka": []}
    s.ocen_prywatnosc(o, odp, s.analizuj_html(STRONA, odp["url"]), date(2026, 11, 23))
    u = {x["id"]: x for x in o.ustalenia}
    assert u["php"]["poziom"] == "krytyczne" and "28.11.2022" in u["php"]["opis"]
    assert "Apache/2.4.41" in u["wersje"]["opis"] and "WordPress 6.2.1" in u["wersje"]["opis"]
    assert u["sledzenie"]["poziom"] == "uwaga" and u["czcionki"]["poziom"] == "uwaga"


def test_aktualne_php_nie_jest_krytyczne():
    o = s.Ocena()
    odp = {"url": "https://k.pl/", "naglowki": httpx.Headers({"x-powered-by": "PHP/8.3.12"}), "ciasteczka": []}
    s.ocen_prywatnosc(o, odp, s.analizuj_html("<html></html>", odp["url"]), date(2026, 11, 23))
    assert "php" not in {x["id"] for x in o.ustalenia}


def test_naglowki_dobrze_ustawione():
    o = s.Ocena()
    s.ocen_naglowki(o, {"url": "https://k.pl/", "ciasteczka": ["sid=1; Secure; HttpOnly; SameSite=Lax"],
                        "naglowki": httpx.Headers({
                            "content-security-policy": "default-src 'self'; frame-ancestors 'self'",
                            "x-content-type-options": "nosniff", "referrer-policy": "no-referrer"})})
    assert all(u["poziom"] == "ok" for u in o.ustalenia)
    assert o.punkty["naglowki"][0] == o.punkty["naglowki"][1]


def test_https_bez_certyfikatu():
    o = s.Ocena()
    s.ocen_https(o, {"dziala": False, "blad_certyfikatu": "wygasl"}, None, None)
    assert o.ustalenia[0]["poziom"] == "krytyczne" and "wygasł" in o.ustalenia[0]["opis"]
    assert o.punkty["https"] == [0, 26]


# --- caly skan i API -------------------------------------------------------

def _atrapy(monkeypatch, dns_, tls, strona_https, strona_http):
    monkeypatch.setattr(s, "adresy_publiczne", lambda h: ["93.184.216.34"])
    monkeypatch.setattr(s, "zbierz_dns", lambda d: dns_)
    monkeypatch.setattr(s, "sprawdz_tls", lambda h: tls)
    monkeypatch.setattr(s, "sprobuj", lambda url: strona_https if url.startswith("https") else strona_http)


def _strona(url, naglowki, html="<html></html>"):
    return {"url": url, "status": 200, "naglowki": httpx.Headers(naglowki), "ciasteczka": [],
            "html": html, "historia": []}


def test_slaba_kancelaria_dostaje_f(monkeypatch):
    https = _strona("https://kancelaria-x.pl/", {"x-powered-by": "PHP/7.4.3"}, STRONA)
    _atrapy(monkeypatch, {"mx": ["10 mx.home.pl."], "txt": [], "dmarc": [], "mta_sts": [], "dkim": [],
                          "caa": [], "dnskey": []},
            {"dziala": True, "wersja": "TLSv1.2", "wystawca": "Let's Encrypt", "wazny_do": "2027-01-10", "dni": 48},
            https, _strona("http://kancelaria-x.pl/", {}))
    w = s.skanuj("kancelaria-x.pl", dzis=date(2026, 11, 23))
    assert w["ocena"] == "F" and w["werdykt"] == "Stan opłakany"
    assert w["krytyczne"] >= 3
    assert w["ustalenia"][0]["poziom"] == "krytyczne"
    assert w["fakty"]["poczta"] == ["mx.home.pl"]


def test_wzorowa_kancelaria_dostaje_a(monkeypatch):
    naglowki = {"strict-transport-security": "max-age=31536000",
                "content-security-policy": "default-src 'self'; frame-ancestors 'none'",
                "x-content-type-options": "nosniff", "referrer-policy": "strict-origin-when-cross-origin"}
    https = _strona("https://kancelaria-x.pl/", naglowki)
    _atrapy(monkeypatch, {"mx": ["10 aspmx.l.google.com."], "txt": ["v=spf1 include:_spf.google.com -all"],
                          "dmarc": ["v=DMARC1; p=reject; rua=mailto:d@kancelaria-x.pl"],
                          "mta_sts": ["v=STSv1; id=1"], "dkim": ["google"], "caa": ["0 issue \"pki.goog\""],
                          "dnskey": ["257 3 13 abc"]},
            {"dziala": True, "wersja": "TLSv1.3", "wystawca": "Google Trust Services", "wazny_do": "2027-01-10",
             "dni": 48}, https, https)
    w = s.skanuj("kancelaria-x.pl")
    assert w["wynik"] == 100 and w["ocena"] == "A" and w["krytyczne"] == 0


@pytest.fixture
def klient(monkeypatch):
    import app
    monkeypatch.setattr(s, "skanuj", lambda adres: {"domena": adres, "wynik": 40, "ocena": "E", "werdykt": "x",
                                                    "krytyczne": 2, "ustalenia": []})
    return TestClient(app.app)


def test_api_skanu(klient):
    odp = klient.post("/api/skan", json={"adres": "kancelaria-x.pl"})
    assert odp.status_code == 200 and odp.json()["ocena"] == "E" and odp.json()["wycieki"] is None


def test_api_cors_dla_notarai(klient):
    odp = klient.options("/api/skan", headers={"Origin": "https://notarai.pl",
                                                "Access-Control-Request-Method": "POST"})
    assert odp.headers.get("access-control-allow-origin") == "https://notarai.pl"


def test_api_email_wymaga_zgody(klient):
    odp = klient.post("/api/skan", json={"adres": "kancelaria-x.pl", "email": "biuro@kancelaria-x.pl"})
    assert odp.status_code == 400 and "zgod" in odp.json()["detail"]


def test_api_wycieki_bez_klucza(klient, monkeypatch):
    monkeypatch.setattr(s, "HIBP_KLUCZ", "")
    odp = klient.post("/api/skan", json={"adres": "kancelaria-x.pl", "email": "biuro@kancelaria-x.pl",
                                         "zgoda_wycieki": True})
    assert odp.json()["wycieki"] == {"dostepne": False}


def test_api_limit(klient, monkeypatch):
    monkeypatch.setattr(s, "limit_skanu", s.Limit(2, 100))
    for _ in range(2):
        assert klient.post("/api/skan", json={"adres": "k.pl"}).status_code == 200
    assert klient.post("/api/skan", json={"adres": "k.pl"}).status_code == 429


def test_api_blad_adresu(monkeypatch):
    import app
    odp = TestClient(app.app).post("/api/skan", json={"adres": "localhost"})
    assert odp.status_code == 400


def test_bez_domeny_w_logach(klient, caplog):
    with caplog.at_level("INFO", logger="pieczapp.skan"):
        klient.post("/api/skan", json={"adres": "jan-kowalski-notariusz.pl"})
    assert "kowalski" not in caplog.text and "ocena=E" in caplog.text


# --- ten komputer: IP, haslo, luki Windows ----------------------------------

import app as aplikacja  # noqa: E402
import skan_bezpieczenstwa as skan  # noqa: E402


@pytest.fixture
def k(monkeypatch):
    skan.limit_hibp.wyczysc()
    skan.limit_luki.wyczysc()
    skan._kev_cache["ts"] = 0.0
    skan._kev_cache["dane"] = None
    monkeypatch.setattr(skan, "TRANSPORT", None)
    return TestClient(aplikacja.app)


KEV_PROBKA = {"vulnerabilities": [
    {"cveID": "CVE-2026-96951", "vendorProject": "Microsoft", "product": "Windows",
     "vulnerabilityName": "Windows Shell Security Feature Bypass", "dateAdded": "2026-10-13",
     "shortDescription": "Windows Shell contains a security feature bypass vulnerability."},
    {"cveID": "CVE-2026-11111", "vendorProject": "Microsoft", "product": "Office",
     "vulnerabilityName": "Office RCE", "dateAdded": "2026-01-01", "shortDescription": "Office."},
    {"cveID": "CVE-2026-22222", "vendorProject": "Adobe", "product": "Acrobat",
     "vulnerabilityName": "Acrobat", "dateAdded": "2026-02-02", "shortDescription": "Acrobat."},
    {"cveID": "CVE-2025-00001", "vendorProject": "Microsoft", "product": "Windows 10",
     "vulnerabilityName": "Older Windows bug", "dateAdded": "2025-09-01", "shortDescription": "Older."},
]}


def test_ip_zwraca_adres(k):
    odp = k.get("/api/skan/ip")
    assert odp.status_code == 200
    assert odp.json()["ip"]


def test_hibp_odrzuca_zly_prefiks(k):
    assert k.get("/api/skan/hibp-haslo", params={"prefiks": "XYZ"}).status_code == 400
    assert k.get("/api/skan/hibp-haslo", params={"prefiks": "ABCDEF"}).status_code == 400
    assert k.get("/api/skan/hibp-haslo", params={"prefiks": "ZZZZZ"}).status_code == 400


def test_hibp_przekazuje_wynik_i_wymusza_wielkie_litery(k, monkeypatch):
    trafione = []

    def obsluz(zadanie):
        trafione.append(str(zadanie.url))
        return httpx.Response(200, text="0018A45C4D1:3\nFEDCBA98765:9\n")

    monkeypatch.setattr(skan, "TRANSPORT", httpx.MockTransport(obsluz))
    odp = k.get("/api/skan/hibp-haslo", params={"prefiks": "abcde"})
    assert odp.status_code == 200
    assert "0018A45C4D1:3" in odp.text
    assert trafione and trafione[0].endswith("/range/ABCDE")


def test_do_backendu_trafia_tylko_prefiks_nie_haslo(k, monkeypatch):
    widziane = []

    def obsluz(zadanie):
        widziane.append(str(zadanie.url).rsplit("/", 1)[1])
        return httpx.Response(200, text="")

    monkeypatch.setattr(skan, "TRANSPORT", httpx.MockTransport(obsluz))
    k.get("/api/skan/hibp-haslo", params={"prefiks": "A1B2C"})
    assert widziane == ["A1B2C"]
    assert all(len(w) == 5 for w in widziane)


def test_hibp_gdy_usluga_pada(k, monkeypatch):
    monkeypatch.setattr(skan, "TRANSPORT", httpx.MockTransport(lambda z: httpx.Response(503)))
    assert k.get("/api/skan/hibp-haslo", params={"prefiks": "ABCDE"}).status_code == 502


def test_luki_tylko_windows_z_kev(k, monkeypatch):
    monkeypatch.setattr(skan, "TRANSPORT", httpx.MockTransport(lambda z: httpx.Response(200, json=KEV_PROBKA)))
    odp = k.get("/api/skan/luki")
    assert odp.status_code == 200
    d = odp.json()
    assert d["zrodlo"] == "CISA KEV"
    ids = [l["id"] for l in d["luki"]]
    # tylko Microsoft/Windows, bez Office i Adobe; najnowsze pierwsze
    assert ids == ["CVE-2026-96951", "CVE-2025-00001"]
    assert d["luki"][0]["url"].endswith("/CVE-2026-96951")
    assert "security feature bypass" in d["luki"][0]["opis"].lower()


def test_luki_filtr_po_dacie_konca_wsparcia(k, monkeypatch):
    monkeypatch.setattr(skan, "TRANSPORT", httpx.MockTransport(lambda z: httpx.Response(200, json=KEV_PROBKA)))
    d = k.get("/api/skan/luki", params={"po": "2025-10-14"}).json()
    ids = [l["id"] for l in d["luki"]]
    assert ids == ["CVE-2026-96951"]   # starsza (2025-09) odfiltrowana


def test_luki_gdy_katalog_pada_mowimy_wprost_ze_brak_listy(k, monkeypatch):
    """Bez katalogu CISA nie pokazujemy zadnych numerow CVE wpisanych z reki."""
    monkeypatch.setattr(skan, "TRANSPORT", httpx.MockTransport(lambda z: httpx.Response(503)))
    d = k.get("/api/skan/luki").json()
    assert d == {"zrodlo": "niedostepne", "luki": []}


def test_luki_zostaje_ostatnia_udana_kopia(k, monkeypatch):
    monkeypatch.setattr(skan, "TRANSPORT", httpx.MockTransport(lambda z: httpx.Response(200, json=KEV_PROBKA)))
    assert k.get("/api/skan/luki").json()["zrodlo"] == "CISA KEV"
    skan._kev_cache["ts"] = 0.0  # wymus odswiezenie
    monkeypatch.setattr(skan, "TRANSPORT", httpx.MockTransport(lambda z: httpx.Response(503)))
    d = k.get("/api/skan/luki").json()
    assert d["zrodlo"] == "CISA KEV" and len(d["luki"]) == 2
