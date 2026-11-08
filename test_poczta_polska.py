"""Poczta Polska: wniosek o umowe, polaczenie z e-Nadawca, nadawanie z dziennika.

Prawdziwego e-Nadawcy nie wolamy - udaje go httpx.MockTransport, ktory
sprawdza koperty SOAP (metoda, HTTP Basic, pola przesylki) i odpowiada jak
WebAPI. Sejf (Secrets Manager) to slownik w pamieci. Dane zmyslone.
"""
import base64
import re
import xml.etree.ElementTree as ET
from datetime import date

import fitz
import httpx
import pytest
from fastapi.testclient import TestClient

LOGIN, HASLO = "kancelaria_sobczak", "Tajne-Haslo-1"
DZIS = date.today().isoformat()
SAD = {"adresat": "Sąd Rejonowy w Zalesiu, Wydział Ksiąg Wieczystych", "ulica": "ul. Sądowa 12/4",
       "kod": "05-500", "miejscowosc": "Zalesie"}


def pdf_z_tekstem(tekst: str) -> bytes:
    d = fitz.open()
    d.new_page().insert_text((50, 50), tekst)
    return d.tobytes()


class Sejf:
    def __init__(self):
        self.dane = {}

    def wczytaj(self, k):
        return self.dane.get(k)

    def zapisz(self, k, d):
        self.dane[k] = dict(d)

    def usun(self, k):
        self.dane.pop(k, None)


class UdawanyNadawca:
    """Odpowiada na metody WebAPI, ktorych uzywa poczta_polska.py."""

    def __init__(self):
        self.haslo = HASLO
        self.wywolania = []
        self.przesylki = {}
        self.bufor = []
        self.zbiory = {}
        self.blad_przesylki = set()   # opisy (np. "DPD 2"), ktore e-Nadawca odrzuci

    def __call__(self, zadanie: httpx.Request) -> httpx.Response:
        assert zadanie.url.host == "e-nadawca.api.poczta-polska.pl"
        login, _, haslo = base64.b64decode(zadanie.headers["authorization"].split()[1]).decode().partition(":")
        if (login, haslo) != (LOGIN, self.haslo):
            return httpx.Response(401, text="Unauthorized")
        cialo = ET.fromstring(zadanie.content).find("{http://schemas.xmlsoap.org/soap/envelope/}Body")[0]
        metoda = cialo.tag.split("}")[1]
        assert zadanie.headers["soapaction"] == f'"http://e-nadawca.poczta-polska.pl/{metoda}"'
        self.wywolania.append(metoda)
        return httpx.Response(200, content=self.koperta(metoda, getattr(self, metoda)(cialo)))

    @staticmethod
    def koperta(metoda, tresc):
        return (f'<?xml version="1.0"?><SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" '
                f'xmlns:ns1="http://e-nadawca.poczta-polska.pl"><SOAP-ENV:Body><ns1:{metoda}Response>{tresc}'
                f'</ns1:{metoda}Response></SOAP-ENV:Body></SOAP-ENV:Envelope>').encode()

    @staticmethod
    def _dzieci(cialo, nazwa):
        return [e for e in cialo.iter() if e.tag.endswith("}" + nazwa) or e.tag == nazwa]

    def hello(self, c):
        return "<out>notarai</out>"

    def getUrzedyNadania(self, c):
        return '<urzedyNadania urzadNadania="263867" opis="UP Zalesie 1"/>'

    def getKarty(self, c):
        return '<karta idKarta="101" opis="Umowa kancelarii" aktywna="true"/>'

    def getPasswordExpiredDate(self, c):
        return "<dataWygasniecia>2026-12-31</dataWygasniecia>"

    def changePassword(self, c):
        self.haslo = self._dzieci(c, "newPassword")[0].text
        return ""

    def getGuid(self, c):
        ile = int(self._dzieci(c, "ilosc")[0].text)
        return "".join(f"<guid>{(len(self.przesylki) + i + 1):032X}</guid>" for i in range(ile))

    def addShipment(self, c):
        wynik = []
        for p in self._dzieci(c, "przesylki"):
            guid = p.get("guid")
            assert re.fullmatch(r"[0-9A-F]{32}", guid)
            assert p.get("{http://www.w3.org/2001/XMLSchema-instance}type") == "e:przesylkaPoleconaKrajowaType"
            adres = self._dzieci(p, "adres")[0]
            self.przesylki[guid] = {**p.attrib, "adres": dict(adres.attrib),
                                    "epo": bool(self._dzieci(p, "epo"))}
            if p.get("opis") in self.blad_przesylki:
                wynik.append(f'<retval guid="{guid}"><error errorNumber="12345" errorDesc="Nieprawidłowy adres"/></retval>')
                continue
            numer = f"00659007734{len(self.przesylki):09d}"
            self.przesylki[guid]["numer"] = numer
            self.bufor.append(guid)
            wynik.append(f'<retval guid="{guid}" numerNadania="{numer}"/>')
        return "".join(wynik)

    def clearEnvelopeByGuids(self, c):
        for g in self._dzieci(c, "guid"):
            self.bufor.remove(g.text)
        return ""

    def getPrintForParcel(self, c):
        guidy = [g.text for g in self._dzieci(c, "guid")]
        assert self._dzieci(c, "kind")[0].text == "ADDRESS_LABEL"
        pdf = pdf_z_tekstem("ETYKIETY " + " ".join(self.przesylki[g]["numer"] for g in guidy))
        return f"<printResult><print>{base64.b64encode(pdf).decode()}</print></printResult>"

    def sendEnvelope(self, c):
        assert self._dzieci(c, "urzadNadania")[0].text == "263867"
        ident = str(900 + len(self.zbiory))
        self.zbiory[ident], self.bufor = list(self.bufor), []
        return f"<idEnvelope>{ident}</idEnvelope><envelopeStatus>PRZYJETY</envelopeStatus>"

    def getOutboxBook(self, c):
        ident = self._dzieci(c, "idEnvelope")[0].text
        pdf = pdf_z_tekstem(f"KSIAZKA NADAWCZA {ident} " + " ".join(self.przesylki[g]["numer"] for g in self.zbiory[ident]))
        return f"<pdfContent>{base64.b64encode(pdf).decode()}</pdfContent>"

    def getEPOStatus(self, c):
        guid = self._dzieci(c, "guid")[0].text
        return (f'<epo guid="{guid}" statusEPO="ZAKONCZONY"><EPOInfo>'
                f'<doreczeniePrzesylki data="2026-11-12T10:15:00" osobaOdbierajaca="Pawlak"/></EPOInfo></epo>')


@pytest.fixture
def poczta(monkeypatch):
    import poczta_polska
    nadawca, sejf = UdawanyNadawca(), Sejf()
    monkeypatch.setattr(poczta_polska, "TRANSPORT", httpx.MockTransport(nadawca))
    monkeypatch.setattr(poczta_polska, "sejf", sejf)
    nadawca.sejf = sejf
    return nadawca


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


WNIOSEK = {"firma": "Kancelaria Notarialna Ewa Sobczak", "nip": "526-000-12-46", "imie": "Ewa", "nazwisko": "Sobczak",
           "email": "kancelaria@example.com", "telefon": "600100200", "ulica": "Rynek", "numer": "5", "kod": "05-500",
           "miejscowosc": "Zalesie", "wolumen": "do 200", "epo": True}


def polacz(klient):
    odp = klient.post("/api/poczta/polacz", json={"login": LOGIN, "haslo": HASLO})
    assert odp.status_code == 200, odp.text
    return odp.json()


def wypis(klient, repertorium="A 1234/2026", **pola):
    odp = klient.post("/api/przesylki/przeslane", json={"data": DZIS, "repertorium": repertorium,
                                                        "sposob": "list polecony za potwierdzeniem odbioru", **SAD, **pola})
    assert odp.status_code == 200, odp.text
    return odp.json()


def tekst(pdf: bytes) -> str:
    with fitz.open("pdf", pdf) as d:
        return " ".join(" ".join(s.get_text() for s in d).split())


class TestWniosek:
    def test_wniosek_wypelniony_i_pdf(self, klient):
        stan = klient.get("/api/poczta").json()
        assert stan["etap"] == "start" and stan["formularz_poczty"].startswith("https://www.poczta-polska.pl/")
        assert klient.put("/api/poczta/wniosek", json={**WNIOSEK, "nip": "123"}).status_code == 400
        stan = klient.put("/api/poczta/wniosek", json=WNIOSEK).json()
        assert stan["wniosek"]["nip"] == "5260001246"
        assert "WebAPI" in stan["prosba"] and "EPO" in stan["prosba"] and "do 200" in stan["prosba"]
        pdf = klient.get("/api/poczta/wniosek.pdf")
        assert pdf.status_code == 200
        t = tekst(pdf.content)
        assert "Wniosek o zawarcie umowy" in t and "Ewa Sobczak" in t and "podpis i pieczęć notariusza" in t

    def test_etapy(self, klient):
        assert klient.post("/api/poczta/etap", json={"etap": "wniosek"}).status_code == 400  # bez wniosku
        klient.put("/api/poczta/wniosek", json=WNIOSEK)
        stan = klient.post("/api/poczta/etap", json={"etap": "wniosek"}).json()
        assert stan["etap"] == "wniosek" and stan["wniosek"]["wyslano"] == DZIS
        assert klient.post("/api/poczta/etap", json={"etap": "umowa"}).json()["etap"] == "umowa"


class TestPolaczenie:
    def test_polaczenie_zapisuje_haslo_tylko_w_sejfie(self, klient, poczta):
        stan = polacz(klient)
        assert stan["etap"] == "polaczona"
        assert stan["polaczenie"]["urzad"] == "263867" and stan["polaczenie"]["karta"] == "101"
        assert stan["polaczenie"]["haslo_wygasa"] == "2026-12-31"
        assert poczta.sejf.dane["lokalna"]["haslo"] == HASLO
        assert HASLO not in klient.get("/api/poczta").text
        assert HASLO not in str(klient.get("/api/poczta").json())

    def test_bledne_haslo_bez_ponawiania(self, klient, poczta):
        odp = klient.post("/api/poczta/polacz", json={"login": LOGIN, "haslo": "zle"})
        assert odp.status_code == 400 and "blokuje konto" in odp.json()["detail"]
        assert poczta.wywolania == []  # 401 przed metoda; tylko jedna proba
        assert poczta.sejf.dane == {}

    def test_automatyczna_zmiana_hasla(self, klient, poczta):
        polacz(klient)
        klient.post("/api/poczta/haslo")
        nowe = poczta.sejf.dane["lokalna"]["haslo"]
        assert nowe != HASLO and poczta.haslo == nowe and "haslo_oczekujace" not in poczta.sejf.dane["lokalna"]
        assert klient.post("/api/poczta/nadaj", json={"pozycje": [{"ksiega": "przeslane", "id": wypis(klient)["id"]}]}).status_code == 200

    def test_odlaczenie(self, klient, poczta):
        polacz(klient)
        assert klient.delete("/api/poczta/polaczenie").json()["etap"] == "umowa"
        assert poczta.sejf.dane == {}


class TestNadawanie:
    def test_od_wpisu_do_ksiazki_nadawczej_i_doreczenia(self, klient, poczta):
        polacz(klient)
        a = wypis(klient)
        b = wypis(klient, "A 1235/2026", sposob="list polecony")
        wybor = {"pozycje": [{"ksiega": "przeslane", "id": a["id"]}, {"ksiega": "przeslane", "id": b["id"]}]}
        odp = klient.post("/api/poczta/nadaj", json=wybor).json()
        assert odp == {"nadano": 2, "bledy": []}
        wpisy = klient.get("/api/przesylki/przeslane").json()
        assert [w["numer_nadania"] for w in wpisy] == ["00659007734000000001", "00659007734000000002"]
        p1, p2 = poczta.przesylki.values()
        assert p1["adres"] == {"nazwa": SAD["adresat"], "ulica": "ul. Sądowa",
                               "numerDomu": "12", "numerLokalu": "4", "miejscowosc": "Zalesie", "kodPocztowy": "05500"}
        assert p1["iloscPotwierdzenOdbioru"] == "1" and "iloscPotwierdzenOdbioru" not in p2
        assert p1["opis"] == "DPD 1" and p1["kategoria"] == "EKONOMICZNA"
        # Ponowne nadanie tych samych pozycji niczego nie dubluje.
        assert klient.post("/api/poczta/nadaj", json=wybor).status_code == 400

        assert "00659007734000000002" in tekst(klient.post("/api/poczta/etykiety.pdf", json=wybor).content)
        zbior = klient.post("/api/poczta/zbior").json()
        assert zbior == {"id": "900", "status": "PRZYJETY", "przesylek": 2}
        assert klient.post("/api/poczta/zbior").status_code == 400  # bufor pusty
        ksiazka = klient.get("/api/poczta/zbior/900/ksiazka.pdf")
        assert "KSIAZKA NADAWCZA 900" in tekst(ksiazka.content)
        assert klient.get("/api/poczta/zbior/1/ksiazka.pdf").status_code == 400

        assert klient.post("/api/poczta/doreczenia").json() == {"sprawdzono": 2, "zmieniono": 2}
        wpisy = klient.get("/api/przesylki/przeslane").json()
        assert {w["data_doreczenia"] for w in wpisy} == {"2026-11-12"}
        # Wpisanie numeru i daty doreczenia przez e-Nadawce to uzupelnienie, nie poprawka.
        druk = tekst(klient.get("/api/przesylki/przeslane/ksiega.pdf?podglad=1").content)
        assert "popr." not in druk and "00659007734000000001" in druk

    def test_odrzucona_przesylka_i_wycofanie(self, klient, poczta):
        polacz(klient)
        a, b = wypis(klient), wypis(klient, "A 1300/2026")
        poczta.blad_przesylki.add("DPD 2")
        wybor = {"pozycje": [{"ksiega": "przeslane", "id": a["id"]}, {"ksiega": "przeslane", "id": b["id"]}]}
        odp = klient.post("/api/poczta/nadaj", json=wybor).json()
        assert odp["nadano"] == 1 and "poz. 2" in odp["bledy"][0] and "Nieprawidłowy adres" in odp["bledy"][0]
        assert klient.get("/api/poczta").json()["w_buforze"] == 1
        assert klient.post("/api/poczta/wycofaj", json=wybor).json() == {"wycofano": 1}
        assert poczta.bufor == [] and klient.get("/api/przesylki/przeslane").json()[0]["numer_nadania"] == ""

    def test_tylko_polecone_i_tylko_po_polaczeniu(self, klient, poczta):
        a = wypis(klient)
        wybor = {"pozycje": [{"ksiega": "przeslane", "id": a["id"]}]}
        assert "połącz" in klient.post("/api/poczta/nadaj", json=wybor).json()["detail"]
        polacz(klient)
        e = wypis(klient, "A 1/2026", sposob="elektronicznie (ePUAP, e-mail, portal)")
        odp = klient.post("/api/poczta/nadaj", json={"pozycje": [{"ksiega": "przeslane", "id": e["id"]}]})
        assert odp.status_code == 400 and "nie jest listem poleconym" in odp.json()["detail"]

    def test_epo_zamiast_papierowej_zwrotki(self, klient, poczta):
        polacz(klient)
        klient.put("/api/poczta/ustawienia", json={"urzad": "263867", "kategoria": "PRIORYTETOWA", "epo": True})
        klient.post("/api/poczta/nadaj", json={"pozycje": [{"ksiega": "przeslane", "id": wypis(klient)["id"]}]})
        p = next(iter(poczta.przesylki.values()))
        assert p["epo"] and "iloscPotwierdzenOdbioru" not in p and p["kategoria"] == "PRIORYTETOWA"


def test_podziel_nazwe():
    import poczta_polska
    dluga = "Sąd Rejonowy dla Krakowa-Podgórza w Krakowie, IV Wydział Ksiąg Wieczystych"
    nazwa, nazwa2 = poczta_polska.podziel_nazwe(dluga)
    assert len(nazwa) <= 60 and f"{nazwa} {nazwa2}" == dluga.replace(", ", ", ") and not nazwa.endswith(" ")


def test_rozbij_ulice():
    import poczta_polska
    assert poczta_polska.rozbij_ulice("ul. Sądowa 12/4") == ("ul. Sądowa", "12", "4")
    assert poczta_polska.rozbij_ulice("Aleje Jerozolimskie 100A") == ("Aleje Jerozolimskie", "100A", "")
    assert poczta_polska.rozbij_ulice("ul. 3 Maja 7 m. 2") == ("ul. 3 Maja", "7", "2")
    assert poczta_polska.rozbij_ulice("Zalesie Dolne") == ("Zalesie Dolne", "", "")
