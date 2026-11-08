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


KW = "WA4M/00160286/2"


def wniosek_kw(klient, w, **pola):
    dane = {"numer_kw": KW.lower(), "sad": "SR dla Warszawy-Mokotowa, XIII Wydzial KW",
            "uczestnicy": [{"nazwa": "Jan Sobczak", "rola": "zbywca", "pesel": PESEL},
                           {"nazwa": "Anna Pawlak", "rola": "nabywca", "pesel": z_suma_kontrolna("9002021234"),
                            "imiona_rodzicow": "Adam, Ewa"}],
            "zadania": [{"rodzaj": "wpis_wlasnosci", "na_rzecz": ["Anna Pawlak"]},
                        {"rodzaj": "wpis_hipoteki", "na_rzecz": ["Anna Pawlak"], "suma": "100000"}],
            "akt": {"notariusz": "Maria Notariuszowa", "siedziba": "Warszawa"}, **pola}
    odp = klient.post(f"/api/ksiegi-kancelarii/repertorium_a/{w['id']}/wnioski-kw", json=dane)
    assert odp.status_code == 200, odp.text
    return odp.json()["wnioski_kw"][-1]


def test_wniosek_kw_przygotowanie_braki_i_oplata(klient):
    w = rep_a(klient)
    wn = wniosek_kw(klient, w)
    assert wn["status"] == "przygotowany" and wn["numer_kw"] == KW
    assert wn["podstawa"]["rep_a"] == "Rep. A nr 1/2026" and wn["podstawa"]["data"] == "2026-11-03"
    assert wn["oplata"]["razem"] == "400.00"
    assert wn["braki"] == [] and wn["gotowy"]
    zly = wniosek_kw(klient, w, uczestnicy=[{"nazwa": "Anna Pawlak", "rola": "nabywca"}],
                     zadania=[{"rodzaj": "wpis_wlasnosci", "na_rzecz": ["Ktos Obcy"]}], numer_kw="WA4M/00160286/3")
    assert not zly["gotowy"]
    tekst = " ".join(zly["braki"])
    assert "Numer KW" in tekst and "PESEL" in tekst and "nie jest uczestnikiem" in tekst
    poprawiony = klient.post(f"/api/ksiegi-kancelarii/repertorium_a/{w['id']}/wnioski-kw/{zly['id']}",
                             json={"numer_kw": KW}).json()["wnioski_kw"][-1]
    assert not any("Numer KW" in b for b in poprawiony["braki"])


def test_pakiet_do_portalu_konczy_sie_przed_podpisem(klient):
    w = rep_a(klient)
    wn = wniosek_kw(klient, w)
    pakiet = klient.get(f"/api/ksiegi-kancelarii/repertorium_a/{w['id']}/wnioski-kw/{wn['id']}/pakiet").json()
    assert pakiet["gotowy"] and pakiet["kroki"][-1]["krok"].startswith("STOP")
    assert [k["krok"] for k in pakiet["kroki"]].count("Zadanie") == 2
    assert pakiet["formularz"]["dane"]["zadanie_1_dzial"] == "II"
    assert pakiet["formularz"]["dane"]["rep_a"] == "Rep. A nr 1/2026"


def test_zlozenie_tworzy_wpis_w_repertorium_c(klient):
    w = rep_a(klient)
    wn = wniosek_kw(klient, w)
    adres = f"/api/ksiegi-kancelarii/repertorium_a/{w['id']}/wnioski-kw/{wn['id']}/status"
    assert klient.post(adres, json={"status": "zlozony", "data_zlozenia": "2026-11-03"}).status_code == 400
    assert klient.post(adres, json={"status": "zlozony", "data_zlozenia": "2026-11-03",
                                    "numer_rep_c": "REP.C/KOMO/1/26"}).status_code == 400
    odp = klient.post(adres, json={"status": "zlozony", "data_zlozenia": "2026-11-03",
                                   "numer_rep_c": "rep.c nota 001234 26"})
    assert odp.status_code == 200, odp.text
    assert odp.json()["wnioski_kw"][0]["numer_rep_c"] == "REP.C/NOTA/1234/26"
    rep_c = klient.get("/api/ksiegi-kancelarii/repertorium_c").json()
    assert len(rep_c) == 1
    assert rep_c[0]["oznaczenie"] == "REP.C/NOTA/1234/26" and rep_c[0]["rep_a"] == "Rep. A nr 1/2026"
    assert rep_c[0]["oplata_sadowa"] == "400.00" and rep_c[0]["status"] == "zlozony"
    # przebieg w sadzie zapisuje sie w repertorium C z historia
    odp = klient.post(adres, json={"status": "wpis_dokonany", "sygnatura_dz_kw": "WA2M/Dz.Kw./12345/26",
                                   "data_wpisu": "2026-11-20"})
    assert odp.status_code == 200, odp.text
    rep_c = klient.get("/api/ksiegi-kancelarii/repertorium_c").json()[0]
    assert rep_c["status"] == "wpis_dokonany" and rep_c["sygnatura_dz_kw"] == "WA2M/Dz.Kw./12345/26"
    assert rep_c["korekty"][0]["powod"] == "przebieg wniosku: wpis_dokonany"
    assert klient.post(adres, json={"status": "zwrot"}).status_code == 400
    # ten sam numer REP.C nie wejdzie drugi raz
    wn2 = wniosek_kw(klient, w)
    adres2 = f"/api/ksiegi-kancelarii/repertorium_a/{w['id']}/wnioski-kw/{wn2['id']}/status"
    assert klient.post(adres2, json={"status": "zlozony", "data_zlozenia": "2026-11-04",
                                     "numer_rep_c": "REP.C/NOTA/1234/26"}).status_code == 400


def test_niekompletnego_wniosku_nie_mozna_zlozyc(klient):
    w = rep_a(klient)
    wn = wniosek_kw(klient, w, sad="")
    odp = klient.post(f"/api/ksiegi-kancelarii/repertorium_a/{w['id']}/wnioski-kw/{wn['id']}/status",
                      json={"status": "zlozony", "data_zlozenia": "2026-11-03", "numer_rep_c": "REP.C/NOTA/1/26"})
    assert odp.status_code == 400 and "braki" in odp.json()["detail"]


def test_mapowanie_portalu_jest_szkicem():
    from formularze import silnik
    m = silnik.wczytaj_mapowanie("wniosek_kw_portal_ms")
    assert m.status == "szkic" and all(p.selektor != m.przycisk_wysylki for p in m.pola)


def test_nieznana_ksiega(klient):
    assert klient.get("/api/ksiegi-kancelarii/repertorium_x").status_code == 400


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
    # karta XML: bez ustawien i kodow ze slownikow GIIF nie da sie zatwierdzic
    odp = klient.post(f"/api/giif/{z['id']}/zatwierdz")
    assert odp.status_code == 400 and "karte" in odp.json()["detail"]
    z = wypelnij_karte(klient, z)
    z = klient.post(f"/api/giif/{z['id']}/zatwierdz").json()
    assert len(z["sha256_xml"]) == 64 and z["schemat"] == "2026/04/28/14250"
    assert z["status"] == "do_podpisu" and len(z["sha256_tresci"]) == 64
    z = klient.post(f"/api/giif/{z['id']}/wysylka",
                    json={"identyfikator_si_giif": "GIIF-2026-1", "data_wysylki": "2026-11-12"}).json()
    assert z["status"] == "wyslane" and z["po_terminie"] is True
    assert klient.post(f"/api/giif/{z['id']}", json={"przedmiot": "x"}).status_code == 400
    z = klient.post(f"/api/giif/{z['id']}/upo", files={"plik": ("upo.xml", b"<UPO/>")}).json()
    assert z["status"] == "upo" and len(z["sha256_upo"]) == 64
    assert [h["co"] for h in z["historia"]] == ["utworzono", "zmieniono", "karta", "zatwierdzono", "wyslano", "upo"]


def wypelnij_karte(klient, z):
    klient.post("/api/giif/ustawienia", json={
        "nip": "5260250274", "nr_sekw_js": "1471", "tytul": "a01", "charakter_zbywcy": "sprz",
        "charakter_nabywcy": "kupu", "rodzaj_dokumentu": "DO", "typ_przedmiotu_lokal": "111"})
    wynik = klient.get(f"/api/giif/{z['id']}/xml").json()
    karta = wynik["karta"]
    assert karta["numer_repertorium"] == "1/2026" and karta["tytul"] == "A01"
    assert [p["strona_transakcji"] for p in karta["przedmioty"][0]["podmioty"]] == ["Z", "N"]
    assert any("CREWAN" in b for b in wynik["bledy"])
    karta["nr_crewan"] = "XX900"
    for s in karta["strony"]:
        s["adres"].update(miejscowosc="Warszawa", kod_pocztowy="00-001", ulica="Lipowa 1")
    karta["strony"][0]["dokument"]["numer"] = "ABC123456"
    karta["strony"][1].update(data_urodzenia="1990-02-02", kraj_urodzenia="PL")  # bez PESEL
    karta["przedmioty"][0]["adres"] = {"kraj": "PL", "kod_pocztowy": "02-001", "woj": "14", "pow": "65",
                                       "gmi": "01", "rodz": "1", "simc": "0918123", "nr_domu": "1", "nr_mieszkania": "2"}
    odp = klient.post(f"/api/giif/{z['id']}/karta", json=karta)
    assert odp.status_code == 200, odp.text
    wynik = klient.get(f"/api/giif/{z['id']}/xml").json()
    assert wynik["bledy"] == [], wynik["bledy"]
    assert "<NrKsiegiWieczystej>WA4M/00160286/2</NrKsiegiWieczystej>" in wynik["xml"].replace("typ:", "")
    plik = klient.get(f"/api/giif/{z['id']}/xml", params={"pobierz": 1})
    assert plik.status_code == 200 and plik.headers["content-type"].startswith("application/xml")
    return odp.json()


def test_xml_regul_udzialow_i_sumy():
    import giif_xml
    karta = {"kwota": "100", "przedmioty": [{"wartosc": "90", "typ": "1", "podmioty": [
        {"strona": 0, "charakter": "X", "strona_transakcji": "N", "udzial_licznik": 1, "udzial_mianownik": 2}]}],
        "strony": [{"imie": "A", "nazwisko": "B", "pesel": "12345678901"}]}
    bledy = " | ".join(giif_xml.bledy_regul(karta, {"nip": "1", "nr_sekw_js": ""}))
    for fragment in ("NIP notariusza", "nrSekwJs", "INF.3", "INF.2", "PESEL niepoprawny", "CREWAN", "Tytul"):
        assert fragment in bledy, fragment


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
