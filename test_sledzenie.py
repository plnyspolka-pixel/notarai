"""Sledzenie przesylek: statusy z uslugi Poczty Polskiej trafiaja do ksiag.

Usluge udaje httpx.MockTransport. Odpowiedzi zbudowane jak prawdziwe
(sprawdzone 08.11.2026 na tt.poczta-polska.pl: przestrzenie nazw ns/ax21,
status -1 dla nieznanego numeru). Kody zdarzen z listy Poczty
(PPSA_events_lists 20250205). Dane zmyslone.
"""
import xml.etree.ElementTree as ET
from datetime import date, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

DZIS = date.today().isoformat()
WCZORAJ = (date.today() - timedelta(days=1)).isoformat()
SAD = {"adresat": "Sąd Rejonowy w Zalesiu", "ulica": "ul. Sądowa 1", "kod": "05-500", "miejscowosc": "Zalesie"}

# numer -> lista (czas, kod, nazwa)
HISTORIE = {
    "00659007734000000001": [(f"{WCZORAJ} 15:02", "P_NAD", "Nadanie przesyłki"),
                             (f"{DZIS} 06:10", "P_PZL", "Przyjęta w centrum logistycznym"),
                             (f"{DZIS} 11:45", "P_D", "Doręczona")],
    "00659007734000000002": [(f"{WCZORAJ} 15:02", "P_NAD", "Nadanie przesyłki"),
                             (f"{DZIS} 09:00", "P_A", "Awizo - przesyłka do odbioru w placówce")],
    "00659007734000000003": [(f"{WCZORAJ} 15:02", "P_NAD", "Nadanie przesyłki"),
                             (f"{DZIS} 10:00", "P_ZDUN", "Zwrot do nadawcy")],
}


def _przesylka(numer: str) -> str:
    ax = 'xmlns:ax21="http://ws.sledzenie.pocztapolska.pl/xsd"'
    if numer not in HISTORIE:
        return f'<ax21:danePrzesylki {ax} xsi:nil="true"/><ax21:numer {ax}>{numer}</ax21:numer><ax21:status {ax}>-1</ax21:status>'
    zdarzenia = "".join(
        f"<ax21:zdarzenie><ax21:czas>{c}</ax21:czas><ax21:jednostka><ax21:nazwa>UP Zalesie</ax21:nazwa></ax21:jednostka>"
        f"<ax21:kod>{k}</ax21:kod><ax21:konczace>{'true' if k in ('P_D', 'P_ZDUN') else 'false'}</ax21:konczace>"
        f"<ax21:nazwa>{n}</ax21:nazwa></ax21:zdarzenie>" for c, k, n in HISTORIE[numer])
    return (f'<ax21:danePrzesylki {ax}><ax21:numer>{numer}</ax21:numer><ax21:zdarzenia>{zdarzenia}</ax21:zdarzenia>'
            f'</ax21:danePrzesylki><ax21:numer {ax}>{numer}</ax21:numer><ax21:status {ax}>0</ax21:status>')


class UdawaneSledzenie:
    def __init__(self):
        self.zapytania = []
        self.awarie = 0

    def __call__(self, zadanie: httpx.Request) -> httpx.Response:
        if self.awarie:
            self.awarie -= 1
            raise httpx.ConnectError("Connection reset by peer")
        tresc = zadanie.content.decode()
        assert "<wsse:Username>sledzeniepp</wsse:Username>" in tresc and "PasswordText" in tresc
        cialo = ET.fromstring(zadanie.content).find("{http://schemas.xmlsoap.org/soap/envelope/}Body")[0]
        metoda = cialo.tag.split("}")[1]
        assert zadanie.headers["soapaction"] == f'"urn:{metoda}"'
        numery = [e.text for e in cialo]
        self.zapytania.append((metoda, numery))
        assert metoda == "sprawdzPrzesylke" and len(numery) == 1
        return httpx.Response(200, text=(
            '<?xml version="1.0" encoding="utf-8"?><soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">'
            '<soapenv:Body><ns:sprawdzPrzesylkeResponse xmlns:ns="http://sledzenie.pocztapolska.pl">'
            '<ns:return xmlns:ns1="http://ws.sledzenie.pocztapolska.pl/xsd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            f'xsi:type="ns1:Przesylka">{_przesylka(numery[0])}</ns:return></ns:sprawdzPrzesylkeResponse></soapenv:Body></soapenv:Envelope>'))


@pytest.fixture
def poczta(monkeypatch):
    import sledzenie
    usluga = UdawaneSledzenie()
    monkeypatch.setattr(sledzenie, "TRANSPORT", httpx.MockTransport(usluga))
    return usluga


@pytest.fixture
def klient(tmp_path, monkeypatch, poczta):
    import config
    import magazyn
    monkeypatch.setattr(config, "DANE", tmp_path)
    if "SPRAWY" in vars(config):
        monkeypatch.delattr(config, "SPRAWY")
    assert magazyn.TRYB == "lokalny"
    import app as aplikacja
    return TestClient(aplikacja.app)


def wypis(klient, numer, **pola):
    odp = klient.post("/api/przesylki/przeslane", json={"data": WCZORAJ, "repertorium": "A 1/2026", **SAD,
                                                        "numer_nadania": numer, **pola})
    assert odp.status_code == 200, odp.text
    return odp.json()


def test_statusy_trafiaja_do_ksiegi(klient, poczta):
    for n in ("00659007734000000001", "00659007734000000002", "00659007734000000003", "00659007734000000099"):
        wypis(klient, n)
    wynik = klient.post("/api/sledzenie").json()
    assert wynik["sprawdzono"] == 4 and wynik["doreczone"] == 1 and wynik["zwrocone"] == 1
    wpisy = {w["numer_nadania"]: w for w in klient.get("/api/przesylki/przeslane").json()}
    d = wpisy["00659007734000000001"]
    assert d["sledzenie"]["stan"] == "doreczona" and d["data_doreczenia"] == DZIS
    assert d["poprawki"][-1]["uzupelnienie"] and d["poprawki"][-1]["kto"] == "Poczta Polska (śledzenie)"
    assert wpisy["00659007734000000002"]["sledzenie"]["stan"] == "awizo"
    assert wpisy["00659007734000000002"]["sledzenie"]["ostatnie"]["kod"] == "P_A"
    assert wpisy["00659007734000000003"]["sledzenie"]["stan"] == "zwrocona"
    assert not wpisy["00659007734000000003"]["data_doreczenia"]
    assert wpisy["00659007734000000099"]["sledzenie"]["stan"] == "brak"
    # Doreczonych i zwroconych juz nie pytamy.
    poczta.zapytania.clear()
    klient.post("/api/sledzenie")
    assert sorted(n for _, (n,) in poczta.zapytania) == ["00659007734000000002", "00659007734000000099"]


def test_odswiezanie_samoczynne_najwyzej_co_kilka_godzin(klient, poczta):
    wypis(klient, "00659007734000000002")
    assert klient.post("/api/sledzenie?wymus=false").json()["pominieto"] is False
    assert klient.post("/api/sledzenie?wymus=false").json()["pominieto"] is True
    assert len(poczta.zapytania) == 1
    assert klient.post("/api/sledzenie").json()["pominieto"] is False  # przycisk - zawsze


def test_pomija_anulowane_bez_numeru_i_stare(klient, poczta):
    a = wypis(klient, "00659007734000000002")
    klient.post(f"/api/przesylki/przeslane/{a['id']}/anuluj", json={"powod": "pomyłka"})
    wypis(klient, "")
    wypis(klient, "00659007734000000001", data=(date.today() - timedelta(days=90)).isoformat())
    assert klient.post("/api/sledzenie").json()["sprawdzono"] == 0
    assert poczta.zapytania == []


def test_ponawia_po_zerwanym_polaczeniu(klient, poczta):
    poczta.awarie = 2
    wypis(klient, "00659007734000000001")
    assert klient.post("/api/sledzenie").json()["doreczone"] == 1


def test_niedostepna_usluga(klient, poczta):
    poczta.awarie = 10
    wypis(klient, "00659007734000000001")
    odp = klient.post("/api/sledzenie")
    assert odp.status_code == 502 and "nie odpowiada" in odp.json()["detail"]


def test_historia_jednej_przesylki(klient):
    h = klient.get("/api/sledzenie/0065 9007 7340 0000 0001").json()
    assert h["stan"] == "doreczona" and [z["kod"] for z in h["zdarzenia"]] == ["P_NAD", "P_PZL", "P_D"]
    assert h["zdarzenia"][0]["jednostka"] == "UP Zalesie" and h["opisy_stanow"]["doreczona"] == "doręczona"
    assert klient.get("/api/sledzenie/zly!").status_code == 400


def test_do_poczty_ida_tylko_numery(klient, poczta, monkeypatch):
    wysylane = []
    import sledzenie
    oryginal = sledzenie._koperta
    monkeypatch.setattr(sledzenie, "_koperta", lambda m, n: wysylane.append(oryginal(m, n)) or wysylane[-1])
    wypis(klient, "00659007734000000001")
    klient.post("/api/sledzenie")
    assert wysylane and all(b"Zalesie" not in k and "Sąd".encode() not in k for k in wysylane)
