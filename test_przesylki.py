"""Dziennik przesylanych dokumentow, dziennik korespondencyjny, wydruki.

Dane zmyslone (zestaw Sobczak/Pawlak); adresy urzedow przykladowe.
"""
import fitz
import pytest
from fastapi.testclient import TestClient

DZIEN = "2026-11-09"
SAD = {"adresat": "Sąd Rejonowy w Zalesiu, Wydział Ksiąg Wieczystych", "ulica": "ul. Sądowa 1",
       "kod": "05-500", "miejscowosc": "Zalesie"}


@pytest.fixture
def klient(tmp_path, monkeypatch):
    import config
    import magazyn
    monkeypatch.setattr(config, "DANE", tmp_path)
    if "SPRAWY" in vars(config):
        monkeypatch.delattr(config, "SPRAWY")
    assert magazyn.TRYB == "lokalny"
    import app as aplikacja
    return TestClient(aplikacja.app)


def wypis(klient, repertorium="A 1234/2026", **pola):
    odp = klient.post("/api/przesylki/przeslane", json={"data": DZIEN, "repertorium": repertorium, **SAD, **pola})
    assert odp.status_code == 200, odp.text
    return odp.json()


def pismo(klient, **pola):
    dane = {"data": DZIEN, "kierunek": "wychodzące", "adresat": "Pawlak Grzegorz", "ulica": "ul. Lipowa 2",
            "kod": "05-501", "miejscowosc": "Zalesie", "tresc": "zawiadomienie o terminie", **pola}
    odp = klient.post("/api/przesylki/korespondencja", json=dane)
    assert odp.status_code == 200, odp.text
    return odp.json()


def tekst_pdf(tresc: bytes) -> str:
    with fitz.open("pdf", tresc) as d:
        return " ".join(" ".join(s.get_text() for s in d).split())


class TestKsiegi:
    def test_dwie_osobne_ksiegi_z_wlasna_numeracja(self, klient):
        assert wypis(klient)["lp"] == 1
        assert wypis(klient, "A 1235/2026")["lp"] == 2
        assert pismo(klient)["lp"] == 1
        assert [w["lp"] for w in klient.get("/api/przesylki/przeslane").json()] == [1, 2]
        assert len(klient.get("/api/przesylki/korespondencja").json()) == 1

    def test_numeracja_nie_zaczyna_sie_od_nowa_w_nowym_roku(self, klient):
        wypis(klient, data="2026-12-30")
        assert wypis(klient, "A 1/2027", data="2027-01-02")["lp"] == 2

    def test_wymagane_pola(self, klient):
        odp = klient.post("/api/przesylki/przeslane", json={"data": DZIEN, **SAD})
        assert odp.status_code == 400 and "repertorium" in odp.json()["detail"]
        odp = klient.post("/api/przesylki/przeslane", json={"data": DZIEN, "repertorium": "A 1/2026",
                                                            "adresat": "Urząd Skarbowy", "sposob": "list polecony"})
        assert odp.status_code == 400 and "adresu" in odp.json()["detail"]
        odp = klient.post("/api/przesylki/przeslane", json={**SAD, "data": DZIEN, "repertorium": "A 1/2026", "kod": "05500"})
        assert odp.status_code == 400
        assert klient.post("/api/przesylki/nieznana", json={"data": DZIEN}).status_code == 400

    def test_pismo_przychodzace_bez_adresu(self, klient):
        w = pismo(klient, kierunek="przychodzące", adresat="Urząd Gminy Zalesie", ulica="", kod="", miejscowosc="",
                  znak_pisma="GN.6840.1.2026", data_pisma="2026-11-05")
        assert w["kierunek"] == "przychodzące"

    def test_poprawka_zostawia_slad_a_uzupelnienie_numeru_nie(self, klient):
        w = wypis(klient)
        odp = klient.put(f"/api/przesylki/przeslane/{w['id']}", json={**w, "numer_nadania": "00659007734210012345"})
        assert odp.status_code == 200
        odp = klient.put(f"/api/przesylki/przeslane/{w['id']}", json={**odp.json(), "repertorium": "A 1243/2026"})
        poprawki = odp.json()["poprawki"]
        assert poprawki[0]["uzupelnienie"] is True
        assert poprawki[1]["pola"]["repertorium"] == ["A 1234/2026", "A 1243/2026"]
        tekst = tekst_pdf(klient.get("/api/przesylki/przeslane/ksiega.pdf?podglad=1").content)
        assert "A 1243/2026" in tekst and "A 1234/2026" in tekst  # tresc pierwotna czytelna

    def test_anulowanie_zostawia_pozycje(self, klient):
        w = wypis(klient)
        assert klient.post(f"/api/przesylki/przeslane/{w['id']}/anuluj", json={"powod": ""}).status_code == 400
        odp = klient.post(f"/api/przesylki/przeslane/{w['id']}/anuluj", json={"powod": "pomyłka adresata"})
        assert odp.json()["status"] == "anulowany"
        assert wypis(klient)["lp"] == 2
        assert klient.put(f"/api/przesylki/przeslane/{w['id']}", json=w).status_code == 400

    def test_numery_z_naklejek(self, klient):
        a, b = wypis(klient), wypis(klient, "A 1240/2026", sposob="list polecony za potwierdzeniem odbioru")
        odp = klient.put("/api/przesylki/przeslane/numery", json={"numery": {a["id"]: "00659007734210012345",
                                                                             b["id"]: " 0065 9007 7342 1001 2346 "}})
        assert odp.json() == {"zmieniono": 2}
        numery = [w["numer_nadania"] for w in klient.get("/api/przesylki/przeslane").json()]
        assert numery == ["00659007734210012345", "00659007734210012346"]
        assert klient.put("/api/przesylki/przeslane/numery", json={"numery": {a["id"]: "zły numer!"}}).status_code == 400


class TestWydruki:
    def test_ksiega_pdf_ma_naglowek_na_kazdej_stronie_i_ciagla_numeracje(self, klient):
        for i in range(60):
            wypis(klient, f"A {1000 + i}/2026")
        pdf = klient.get("/api/przesylki/przeslane/ksiega.pdf")
        assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
        with fitz.open("pdf", pdf.content) as d:
            strony = d.page_count
            assert strony > 1
            for s in d:
                assert "Nr repertorium" in " ".join(s.get_text().split())
            assert "strona 1" in d[0].get_text()
        tekst = tekst_pdf(pdf.content)
        assert all(f"A {1000 + i}/2026" in tekst for i in range(60))
        assert "Sąd Rejonowy w Zalesiu" in tekst  # polskie znaki
        # Nastepny wydruk zaczyna od kolejnej strony; podglad niczego nie zapamietuje.
        drugi = klient.get("/api/przesylki/przeslane/ksiega.pdf?od_lp=60")
        assert f"strona {strony + 1}" in tekst_pdf(drugi.content)
        podglad = klient.get("/api/przesylki/przeslane/ksiega.pdf?od_lp=60&podglad=1")
        assert f"strona {strony + 2}" in tekst_pdf(podglad.content)
        assert f"strona {strony + 2}" in tekst_pdf(klient.get("/api/przesylki/przeslane/ksiega.pdf?od_lp=60").content)

    def test_pusta_ksiega_drukuje_sie(self, klient):
        assert klient.get("/api/przesylki/korespondencja/ksiega.pdf").status_code == 200

    def test_ksiazka_nadawcza_z_obu_ksiag_tylko_polecone(self, klient):
        wypis(klient)
        wypis(klient, "A 1300/2026", sposob="elektronicznie (ePUAP, e-mail, portal)")
        pismo(klient, sposob="list polecony za potwierdzeniem odbioru")
        pismo(klient, kierunek="przychodzące", adresat="Urząd Gminy", sposob="list polecony")
        tekst = tekst_pdf(klient.get(f"/api/przesylki/ksiazka-nadawcza.pdf?dzien={DZIEN}").content)
        assert "przesyłek: 2" in tekst
        assert "Pawlak Grzegorz" in tekst and "polecony ZPO" in tekst and "DPD 1" in tekst and "DK 1" in tekst
        assert len(klient.get(f"/api/przesylki/do-wysylki?dzien={DZIEN}").json()) == 2

    def test_koperty_i_eksport(self, klient):
        klient.put("/api/przesylki/ustawienia", json={"nadawca": "Kancelaria Notarialna Notariusz Ewa Sobczak",
                                                      "adres_nadawcy": "ul. Rynek 5\n05-500 Zalesie"})
        a = wypis(klient, sposob="list polecony za potwierdzeniem odbioru")
        odp = klient.post("/api/przesylki/przeslane/koperty.pdf", json={"pozycje": [a["id"]], "format": "C5"})
        with fitz.open("pdf", odp.content) as d:
            assert d.page_count == 1 and round(d[0].rect.width / 72 * 25.4) == 229
            tekst = d[0].get_text()
        assert "05-500 Zalesie" in tekst and "ZA POTWIERDZENIEM ODBIORU" in tekst and "Ewa Sobczak" in tekst
        assert klient.post("/api/przesylki/przeslane/koperty.pdf", json={"pozycje": []}).status_code == 400
        csv = klient.post("/api/przesylki/przeslane/e-nadawca.csv", json={"pozycje": [a["id"]]})
        linie = csv.content.decode("utf-8-sig").splitlines()
        assert linie[0].startswith("nazwa_adresata;ulica")
        assert linie[1].split(";")[6] == "TAK" and linie[1].endswith("DPD 1")
