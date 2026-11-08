"""Ksiegi notarialne i zgloszenia GIIF przez API. Dane zmyslone, zero sieci."""
import pytest
from fastapi.testclient import TestClient

from conftest import z_suma_kontrolna

PESEL = z_suma_kontrolna("8001011234")


@pytest.fixture
def klient(tmp_path, monkeypatch):
    import config
    import magazyn
    monkeypatch.setattr(config, "DANE", tmp_path)
    if "SPRAWY" in vars(config):
        monkeypatch.delattr(config, "SPRAWY")
    assert config.SPRAWY.is_relative_to(tmp_path)
    assert magazyn.TRYB == "lokalny"
    import app as aplikacja
    return TestClient(aplikacja.app)


def rep_a(klient, data="2026-11-03", **pola):
    dane = {"data_czynnosci": data, "tresc": "Umowa sprzedazy lokalu",
            "strony": [{"nazwa": "Jan Sobczak", "rola": "sprzedajacy", "pesel": PESEL},
                       {"nazwa": "Anna Pawlak", "rola": "kupujaca"}],
            "wartosc_przedmiotu": "650000", "wynagrodzenie": "1000", "vat": "230",
            "podatek_pcc": "13000", **pola}
    odp = klient.post("/api/ksiegi-kancelarii/repertorium_a", json=dane)
    assert odp.status_code == 200, odp.text
    return odp.json()


def test_numeracja_roczna_i_oznaczenie(klient):
    assert rep_a(klient)["oznaczenie"] == "Rep. A nr 1/2026"
    assert rep_a(klient, "2026-11-04")["oznaczenie"] == "Rep. A nr 2/2026"
    assert rep_a(klient, "2027-01-02")["oznaczenie"] == "Rep. A nr 1/2027"
    lista = klient.get("/api/ksiegi-kancelarii/repertorium_a", params={"rok": 2026}).json()
    assert [w["numer"] for w in lista] == [1, 2]


def test_repertorium_chronologicznie(klient):
    rep_a(klient, "2026-11-05")
    odp = klient.post("/api/ksiegi-kancelarii/repertorium_a",
                      json={"data_czynnosci": "2026-11-01", "tresc": "x", "strony": "Jan Sobczak"})
    assert odp.status_code == 400 and "chronologicznie" in odp.json()["detail"]


def test_brak_wymaganych_rubryk(klient):
    odp = klient.post("/api/ksiegi-kancelarii/repertorium_a", json={"data_czynnosci": "2026-11-03"})
    assert odp.status_code == 400 and "Brakuje" in odp.json()["detail"]


def test_poprawka_zostawia_historie_i_numer(klient):
    w = rep_a(klient)
    odp = klient.post(f"/api/ksiegi-kancelarii/repertorium_a/{w['id']}/poprawka",
                      json={"zmiany": {"wynagrodzenie": "1200", "numer": 99}, "powod": "blad rachunkowy"})
    assert odp.status_code == 200, odp.text
    po = odp.json()
    assert po["wynagrodzenie"] == "1200.00" and po["numer"] == 1
    assert po["korekty"][0]["bylo"] == {"wynagrodzenie": "1000.00"}
    bez_powodu = klient.post(f"/api/ksiegi-kancelarii/repertorium_a/{w['id']}/poprawka",
                             json={"zmiany": {"vat": "1"}, "powod": " "})
    assert bez_powodu.status_code == 400


def test_uwagi_sumy_i_skorowidz(klient):
    w = rep_a(klient)
    rep_a(klient, "2026-11-03", wynagrodzenie="500", vat="115", podatek_pcc="",
          strony=[{"nazwa": "Anna Pawlak"}])
    klient.post(f"/api/ksiegi-kancelarii/repertorium_a/{w['id']}/uwagi",
                json={"tresc": "Wydano wypis kupujacej"})
    assert klient.get("/api/ksiegi-kancelarii/repertorium_a").json()[0]["uwagi"][0]["tresc"]
    sumy = klient.get("/api/ksiegi-kancelarii/repertorium_a/sumy",
                      params={"rok": 2026, "miesiac": 11}).json()
    assert sumy["razem"]["wynagrodzenie"] == "1500.00"
    assert sumy["dzienne"]["2026-11-03"]["podatek_pcc"] == "13000.00"
    skorowidz = klient.get("/api/ksiegi-kancelarii/repertorium_a/skorowidz", params={"rok": 2026}).json()
    assert [s["nazwa"] for s in skorowidz] == ["Anna Pawlak", "Jan Sobczak"]
    assert skorowidz[0]["numery"] == ["Rep. A nr 1/2026", "Rep. A nr 2/2026"]


def test_depozyt_numeracja_ciagla(klient):
    for dzien in ("2026-12-30", "2027-01-02"):
        odp = klient.post("/api/ksiegi-kancelarii/depozytowa", json={
            "data_zlozenia": dzien, "skladajacy": "Anna Pawlak", "przedmiot": "Gotowka",
            "kwota": "10000", "waluta": "PLN", "odbiorca": "Jan Sobczak"})
        assert odp.status_code == 200, odp.text
    assert [w["oznaczenie"] for w in klient.get("/api/ksiegi-kancelarii/depozytowa").json()] == \
        ["Dep. nr 1", "Dep. nr 2"]


def test_wniosek_kw_trafia_do_dziennika_przesylanych(klient):
    w = rep_a(klient)
    odp = klient.post(f"/api/ksiegi-kancelarii/repertorium_a/{w['id']}/wnioski-kw",
                      json={"numer_kw": "wa4m/00160286/2", "zadanie": "wpis wlasnosci"})
    wniosek = odp.json()["wnioski_kw"][0]
    assert wniosek["status"] == "przygotowany"
    assert klient.get("/api/ksiegi-kancelarii/dziennik_przesylanych").json() == []
    odp = klient.post(f"/api/ksiegi-kancelarii/repertorium_a/{w['id']}/wnioski-kw/{wniosek['id']}",
                      json={"status": "zlozony", "data_zlozenia": "2026-11-03", "identyfikator": "EKW-123"})
    assert odp.status_code == 200, odp.text
    dziennik = klient.get("/api/ksiegi-kancelarii/dziennik_przesylanych").json()
    assert len(dziennik) == 1
    assert dziennik[0]["rep_a"] == "Rep. A nr 1/2026" and dziennik[0]["numer_kw"] == "WA4M/00160286/2"


def test_nieznana_ksiega(klient):
    assert klient.get("/api/ksiegi-kancelarii/repertorium_c").status_code == 400


# --- GIIF ---------------------------------------------------------------------


def test_kwalifikacja_progu_i_podatku(klient):
    w = rep_a(klient)
    wynik = klient.get(f"/api/ksiegi-kancelarii/repertorium_a/{w['id']}/giif",
                       params={"kurs_eur": "4.25"}).json()
    assert wynik["zglosic"] and wynik["rodzaj"] == "czynnosc_giif_kas"
    assert wynik["termin"] == "2026-11-10"
    maly = rep_a(klient, wartosc_przedmiotu="20000", podatek_pcc="")
    assert not klient.get(f"/api/ksiegi-kancelarii/repertorium_a/{maly['id']}/giif",
                          params={"kurs_eur": "4.25"}).json()["zglosic"]


def test_obieg_zgloszenia(klient):
    w = rep_a(klient)
    z = klient.post("/api/giif", json={"rep_a_id": w["id"], "kurs_eur": "4.25"}).json()
    assert z["status"] == "szkic" and z["rep_a"] == "Rep. A nr 1/2026"
    assert any("adres" in b for b in z["braki"])
    assert klient.post(f"/api/giif/{z['id']}/zatwierdz").status_code == 400
    strony = [{**s, "adres": "ul. Lipowa 1, Warszawa"} for s in z["strony"]]
    strony[1].update(dokument="ABC123456", panstwo_dokumentu="PL")
    z = klient.post(f"/api/giif/{z['id']}", json={
        "strony": strony,
        "nieruchomosc": {"adres": "ul. Lipowa 1/2, Warszawa", "numer_kw": "WA4M/00160286/2",
                         "powierzchnia_uzytkowa": "48.5", "liczba_pokoi": "2"}}).json()
    assert z["braki"] == [], z["braki"]
    z = klient.post(f"/api/giif/{z['id']}/zatwierdz").json()
    assert z["status"] == "do_podpisu" and len(z["sha256_tresci"]) == 64
    z = klient.post(f"/api/giif/{z['id']}/wysylka",
                    json={"identyfikator_si_giif": "GIIF-2026-1", "data_wysylki": "2026-11-12"}).json()
    assert z["status"] == "wyslane" and z["po_terminie"] is True
    assert klient.post(f"/api/giif/{z['id']}", json={"przedmiot": "x"}).status_code == 400
    z = klient.post(f"/api/giif/{z['id']}/upo", files={"plik": ("upo.xml", b"<UPO/>")}).json()
    assert z["status"] == "upo" and len(z["sha256_upo"]) == 64
    assert [h["co"] for h in z["historia"]] == ["utworzono", "zmieniono", "zatwierdzono", "wyslano", "upo"]


def test_zalegle_zgloszenia(klient):
    w = rep_a(klient, "2026-01-02")
    klient.post("/api/giif", json={"rep_a_id": w["id"]})
    assert len(klient.get("/api/giif").json()["zalegle"]) == 1


def test_zawiadomienie_wymaga_uzasadnienia(klient):
    z = klient.post("/api/giif", json={"rodzaj": "zawiadomienie_74", "dane": {
        "rep_a": "Rep. A nr 1/2026", "data_czynnosci": "2026-11-03",
        "strony": [{"nazwa": "Jan Sobczak", "pesel": PESEL, "adres": "Warszawa"}]}}).json()
    assert z["braki"] == ["Uzasadnienie podejrzenia"] and z["termin"] == ""


def test_kurs_nbp_cofa_sie_do_dnia_roboczego():
    import giif

    class Odp:
        def __init__(self, kod, dane=None):
            self.status_code, self._dane = kod, dane

        def json(self):
            return self._dane

    class Atrapa:
        def __init__(self):
            self.adresy = []

        def get(self, adres, params=None):
            self.adresy.append(adres)
            if "2026-11-08" in adres or "2026-11-07" in adres:
                return Odp(404)
            return Odp(200, {"rates": [{"mid": 4.2512, "no": "216/A/NBP/2026", "effectiveDate": "2026-11-06"}]})

    atrapa = Atrapa()
    assert giif.kurs_nbp("2026-11-08", atrapa)["data_tabeli"] == "2026-11-06"
    assert len(atrapa.adresy) == 3
    assert str(giif.rownowartosc_eur("650000", "PLN", "4.25")) == "152941.18"
