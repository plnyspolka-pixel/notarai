"""Korespondencja e-mail w sprawie: skrzynka -> propozycja -> zatwierdzenie
-> pliki sprawy -> ustalenia ze zrodlem (korespondencja.py).

Dane zmyslone (zestaw Nowak / Kaczmarek z odcinka 01, domena .test).
Model zastapiony atrapa - zaden test nie wola Bedrock.
"""
import json
import logging
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import format_datetime

import pytest
from fastapi.testclient import TestClient

import bedrock
import config
import korespondencja
import stanowiska

SPRAWA = "kor041demo01"
INNA = "inna00000001"
SYGNATURA = "S-041-2026"
KW = "WA4M/00077777/1"
TZ = timezone(timedelta(hours=1))
D = "poczta-demo.test"
OSOBY = [
    {"imie": "Irena Nowak", "email": f"irena.nowak@{D}", "rola": "strona", "opis": "sprzedająca"},
    {"imie": "Joanna Kaczmarek", "email": f"joanna.kaczmarek@{D}", "rola": "kupujacy", "opis": "kupująca"},
    {"imie": "Robert Kaczmarek", "email": f"robert.kaczmarek@{D}", "rola": "kupujacy", "opis": "kupujący"},
    {"imie": "Paweł Nowak", "email": f"pawel.nowak@{D}", "rola": "kontakt", "opis": "syn sprzedającej"},
]
POLA = [
    {"nazwa": "aaa: sprzedająca", "wartosc": "Irena Nowak", "zrodlo": "skan-1"},
    {"nazwa": "ggg: nr kw", "wartosc": KW, "zrodlo": "skan-1"},
    {"nazwa": "ccc: cena", "wartosc": "640 000,00", "zrodlo": "skan-3"},
    {"nazwa": "www: termin wydania lokalu", "wartosc": None, "zrodlo": "",
     "uwaga": "Brak potwierdzenia terminu przez sprzedającą."},
]
WWW = "www: termin wydania lokalu"

# Fragmenty tresci, ktore nie moga trafic do logow.
TAJNE = ["Mama się zgadza", "1 grudnia", "Warunki transakcji", "Kasztanowa", "pawel.nowak", "Paweł",
         "Kaczmarek", "najem kończy", "warunki_przedwstępne", "Robert"]


def mail(od, do, temat, tresc, data, mid, odp=None, zal=None, html=False, dw=()):
    m = EmailMessage()
    m["From"] = f'"{od[0]}" <{od[1]}>'
    m["To"] = ", ".join(f'"{n}" <{a}>' for n, a in do)
    if dw:
        m["Cc"] = ", ".join(f'"{n}" <{a}>' for n, a in dw)
    m["Date"] = format_datetime(data)
    m["Subject"] = temat
    m["Message-ID"] = mid
    if odp:
        m["In-Reply-To"] = odp
        m["References"] = odp
    if html:
        m.set_content("<html><body><p>" + tresc.replace("\n", "<br>") + "</p></body></html>", subtype="html")
    else:
        m.set_content(tresc)
    for nazwa, dane in zal or []:
        m.add_attachment(dane, maintype="application", subtype="pdf", filename=nazwa)
    return bytes(m)


ROBERT = ("Robert Kaczmarek", f"robert.kaczmarek@{D}")
PAWEL = ("Paweł Nowak", f"pawel.nowak@{D}")
JOANNA = ("Joanna Kaczmarek", f"joanna.kaczmarek@{D}")
IRENA = ("Irena Nowak", f"irena.nowak@{D}")
KANC = ("Sekretariat", "sekretariat@kancelaria-demo.test")
OBCY = ("Jan Obcy", "jan@inna-firma.test")
D05 = "<d05@poczta-demo.test>"


def maile_demo():
    return {
        "01_d05.eml": mail(ROBERT, [PAWEL], "Warunki transakcji - ul. Kasztanowa 14 m. 6",
                           "Dzień dobry,\n- cena: 640 000 zł,\n- wydanie lokalu: 1 grudnia 2026 r.\nPozdrawiam, Robert",
                           datetime(2026, 11, 6, 18, 42, tzinfo=TZ), D05, dw=[KANC],
                           zal=[("warunki_przedwstępne.pdf", b"%PDF-1.4 fikcyjny")]),
        "02_d10.eml": mail(PAWEL, [ROBERT], "Re: Warunki transakcji - ul. Kasztanowa 14 m. 6",
                           "Mama się zgadza, 1 grudnia aktualny.", datetime(2026, 11, 9, 7, 58, tzinfo=TZ),
                           "<d10@poczta-demo.test>", odp=D05, dw=[KANC]),
        "03_d09.eml": mail(JOANNA, [KANC], f"{SYGNATURA} - termin wydania",
                           "Prosiliśmy o wydanie 1 grudnia, bo najem kończy się 30 listopada.",
                           datetime(2026, 11, 10, 12, 15, tzinfo=TZ), "<d09@poczta-demo.test>"),
        "04_obcy.eml": mail(OBCY, [KANC], "Oferta szkoleń", "Zapraszamy na szkolenie.",
                            datetime(2026, 11, 11, 9, 0, tzinfo=TZ), "<obcy@inna-firma.test>"),
    }


def _sprawa(baza, identyfikator, nazwa, sygnatura, pola, osoby):
    katalog = baza / identyfikator
    katalog.mkdir(parents=True)
    (katalog / "wzor.txt").write_text("www - termin wydania\n\nAKT\nWydanie nastąpi www.", "utf-8")
    (katalog / "sprawa.json").write_text(json.dumps({
        "id": identyfikator, "nazwa": nazwa, "nazwa_reczna": True, "sygnatura": sygnatura,
        "utworzono": "2026-11-10T14:12:00", "skany": [], "pola_wzoru": [p["nazwa"] for p in pola]}), "utf-8")
    (katalog / "odczyt.json").write_text(json.dumps({"pola": pola, "braki": [], "rozbieznosci": []},
                                                    ensure_ascii=False), "utf-8")
    (katalog / korespondencja.PLIK_SPRAWY).write_text(json.dumps({"osoby": osoby, "wiadomosci": []}), "utf-8")
    return katalog


@pytest.fixture
def srodowisko(tmp_path, monkeypatch):
    import magazyn
    assert magazyn.TRYB == "lokalny"
    monkeypatch.setattr(config, "DANE", tmp_path / "dane")
    if "SPRAWY" in vars(config):
        monkeypatch.delattr(config, "SPRAWY")
    skrzynka = tmp_path / "skrzynka"
    skrzynka.mkdir()
    for nazwa, dane in maile_demo().items():
        (skrzynka / nazwa).write_bytes(dane)
    monkeypatch.setattr(korespondencja, "KATALOG_DEMO", str(skrzynka))
    baza = config.SPRAWY
    katalog = _sprawa(baza, SPRAWA, "NOWAK — KACZMAREK", SYGNATURA, POLA, OSOBY)
    _sprawa(baza, INNA, "ZIELIŃSKA", "S-002-2026", [{"nazwa": "aaa: strona", "wartosc": "Anna Zielińska"}], [])
    import app as aplikacja
    return TestClient(aplikacja.app), katalog, skrzynka


def po_temacie(lista, fragment):
    return next(w for w in lista if w["temat"].startswith(fragment))


def atrapa_ustalen(mapa):
    """Ustalenia jak z modelu: {fragment tresci: [ustalenia]}."""
    def wyciagnij(tekst, temat, pola):
        assert WWW in pola          # model dostaje nazwy pol sprawy
        for fragment, ustalenia in mapa.items():
            if fragment in tekst:
                return ustalenia
        return []
    return wyciagnij


USTALENIA = {
    "wydanie lokalu: 1 grudnia": [{"pole": WWW, "wartosc": "1.12", "cytat": "wydanie lokalu: 1 grudnia 2026 r.",
                                   "pewnosc": "wysoka", "relacja": False, "czyje": ""}],
    "Mama się zgadza": [{"pole": WWW, "wartosc": "1.12", "cytat": "Mama się zgadza, 1 grudnia aktualny.",
                         "pewnosc": "wysoka", "relacja": True, "czyje": "mama autora (sprzedająca)"}],
    "najem": [{"pole": WWW, "wartosc": "1.12", "cytat": "Prosiliśmy o wydanie 1 grudnia",
               "pewnosc": "wysoka", "relacja": False, "czyje": ""},
              {"pole": "inne: koniec najmu kupujących", "wartosc": "30.11", "cytat": "najem kończy się 30 listopada",
               "pewnosc": "wysoka", "relacja": False, "czyje": ""}],
}


def pobierz(k):
    odp = k.post("/api/korespondencja/pobierz")
    assert odp.status_code == 200, odp.text
    return odp.json()


def przypisz(k, wiad, sprawa=SPRAWA, rola=None):
    odp = k.post(f"/api/korespondencja/{wiad['id']}/przypisz", json={"sprawa": sprawa, "rola": rola})
    assert odp.status_code == 200, odp.text
    return odp.json()


# --- parsowanie ------------------------------------------------------------------


class TestParsowanie:
    def test_polskie_znaki_w_naglowkach_tresci_i_nazwie_zalacznika(self):
        p = korespondencja.parsuj(maile_demo()["01_d05.eml"])
        assert p["nadawca"] == {"imie": "Robert Kaczmarek", "email": f"robert.kaczmarek@{D}"}
        assert p["temat"] == "Warunki transakcji - ul. Kasztanowa 14 m. 6"
        assert "wydanie lokalu: 1 grudnia" in p["tekst"] and "Dzień dobry" in p["tekst"]
        assert p["data"] == "2026-11-06T18:42:00+01:00"
        assert p["message_id"] == D05
        assert [a["email"] for a in p["adresaci"]] == [f"pawel.nowak@{D}", "sekretariat@kancelaria-demo.test"]
        (z,) = p["zalaczniki"]
        assert z["nazwa"] == "warunki_przedwstępne.pdf" and z["dane"] == b"%PDF-1.4 fikcyjny"

    def test_nadawca_z_polskim_imieniem_i_watek(self):
        p = korespondencja.parsuj(maile_demo()["02_d10.eml"])
        assert p["nadawca"]["imie"] == "Paweł Nowak"
        assert p["in_reply_to"] == [D05] and p["references"] == [D05]
        assert p["zalaczniki"] == []

    def test_wiadomosc_tylko_html_daje_czysty_tekst(self):
        surowa = mail(IRENA, [KANC], "Zażółć gęślą jaźń", "Proszę o termin &amp; kontakt.\nIrena",
                      datetime(2026, 11, 12, 10, 0, tzinfo=TZ), "<html@poczta-demo.test>", html=True)
        p = korespondencja.parsuj(surowa)
        assert p["temat"] == "Zażółć gęślą jaźń"
        assert "<" not in p["tekst"] and "Proszę o termin & kontakt." in p["tekst"] and "Irena" in p["tekst"]

    def test_naglowki_zakodowane_rfc2047_i_quoted_printable(self):
        surowa = (b"From: =?utf-8?q?Pawe=C5=82_Nowak?= <pawel.nowak@poczta-demo.test>\r\n"
                  b"To: sekretariat@kancelaria-demo.test\r\n"
                  b"Subject: =?utf-8?b?WmHFvMOzxYLEhyBnxJnFm2zEhQ==?=\r\n"
                  b"Date: Mon, 09 Nov 2026 07:58:00 +0100\r\n"
                  b"MIME-Version: 1.0\r\nContent-Type: text/plain; charset=utf-8\r\n"
                  b"Content-Transfer-Encoding: quoted-printable\r\n\r\n"
                  b"Mama si=C4=99 zgadza.\r\n")
        p = korespondencja.parsuj(surowa)
        assert p["nadawca"]["imie"] == "Paweł Nowak" and p["temat"] == "Zażółć gęślą"
        assert p["tekst"] == "Mama się zgadza."


# --- skrzynka i propozycje -----------------------------------------------------------


class TestPropozycje:
    def test_nic_nie_trafia_do_sprawy_bez_zatwierdzenia(self, srodowisko):
        k, katalog, _ = srodowisko
        wynik = pobierz(k)
        assert wynik["pobrano"] == 4 and wynik["nowe"] == 4
        assert len(wynik["wiadomosci"]) == 4
        # Sprawa nietknieta: brak plikow, brak wiadomosci w korespondencji.
        assert not (katalog / "zalaczniki").exists()
        assert k.get(f"/api/sprawy/{SPRAWA}/korespondencja").json()["wiadomosci"] == []
        assert k.get(f"/api/sprawy/{SPRAWA}/pliki").json() == []
        # Drugie sprawdzenie nie dubluje wiadomosci.
        assert pobierz(k)["nowe"] == 0
        assert len(k.get("/api/korespondencja").json()["wiadomosci"]) == 4

    def test_propozycja_po_sygnaturze_z_wysoka_pewnoscia(self, srodowisko):
        k, _, _ = srodowisko
        w = po_temacie(pobierz(k)["wiadomosci"], SYGNATURA)
        top = w["propozycje"][0]
        assert top["sprawa"] == SPRAWA and top["pewnosc"] == "wysoka"
        assert any(SYGNATURA in u for u in top["uzasadnienie"])
        assert any("nadawca jest w sprawie: Joanna Kaczmarek (kupujący)" == u for u in top["uzasadnienie"])
        assert all(p["sprawa"] != INNA for p in w["propozycje"])

    def test_propozycja_po_adresie_nadawcy(self, srodowisko):
        k, _, _ = srodowisko
        w = po_temacie(pobierz(k)["wiadomosci"], "Warunki transakcji - ul.")
        top = w["propozycje"][0]
        assert top["sprawa"] == SPRAWA
        assert "nadawca jest w sprawie: Robert Kaczmarek (kupujący)" in top["uzasadnienie"]
        assert any(u.startswith("adresat jest w sprawie: Paweł Nowak") for u in top["uzasadnienie"])

    def test_propozycja_po_watku_po_przypisaniu_pierwszej_wiadomosci(self, srodowisko):
        k, katalog, _ = srodowisko
        lista = pobierz(k)["wiadomosci"]
        # Odpowiedz od nieznanego adresu w tym samym watku - tylko watek wskazuje sprawe.
        (katalog / korespondencja.PLIK_SPRAWY).write_text(json.dumps({"osoby": OSOBY[:3], "wiadomosci": []}), "utf-8")
        odp = po_temacie(k.get("/api/korespondencja").json()["wiadomosci"], "Re: Warunki")
        assert all("wątku" not in " ".join(p["uzasadnienie"]) for p in odp["propozycje"])
        przypisz(k, po_temacie(lista, "Warunki transakcji - ul."))
        odp = po_temacie(k.get("/api/korespondencja").json()["wiadomosci"], "Re: Warunki")
        top = odp["propozycje"][0]
        assert top["sprawa"] == SPRAWA and top["pewnosc"] == "wysoka"
        assert "odpowiedź w wątku już przypisanym do tej sprawy" in top["uzasadnienie"]

    def test_propozycja_po_numerze_ksiegi(self, srodowisko):
        k, _, skrzynka = srodowisko
        (skrzynka / "05_kw.eml").write_bytes(mail(OBCY, [KANC], "Zapytanie", f"Dotyczy księgi {KW}, proszę o kontakt.",
                                                 datetime(2026, 11, 12, 9, 0, tzinfo=TZ), "<kw@inna-firma.test>"))
        w = po_temacie(pobierz(k)["wiadomosci"], "Zapytanie")
        assert w["propozycje"][0]["sprawa"] == SPRAWA
        assert f"numer księgi wieczystej {KW}" in w["propozycje"][0]["uzasadnienie"]

    def test_obca_wiadomosc_bez_propozycji_i_pominiecie(self, srodowisko):
        k, _, _ = srodowisko
        w = po_temacie(pobierz(k)["wiadomosci"], "Oferta")
        assert w["propozycje"] == []
        assert k.post(f"/api/korespondencja/{w['id']}/pomin").status_code == 200
        assert all(x["id"] != w["id"] for x in k.get("/api/korespondencja").json()["wiadomosci"])
        assert pobierz(k)["nowe"] == 0       # pominieta nie wraca przy kolejnym sprawdzeniu

    def test_lista_nie_zwraca_identyfikatora_u_dostawcy(self, srodowisko):
        k, _, _ = srodowisko
        assert all("ident" not in w for w in pobierz(k)["wiadomosci"])


# --- przypisanie ----------------------------------------------------------------------


class TestPrzypisanie:
    def test_eml_i_zalaczniki_w_plikach_sprawy_z_metadanymi(self, srodowisko):
        k, katalog, skrzynka = srodowisko
        w = po_temacie(pobierz(k)["wiadomosci"], "Warunki transakcji - ul.")
        wynik = przypisz(k, w)
        assert wynik["rola"] == "kupujacy" and wynik["nadawca"]["imie"] == "Robert Kaczmarek"
        pliki = {p["nazwa"]: p for p in k.get(f"/api/sprawy/{SPRAWA}/pliki").json()}
        eml = wynik["plik"]
        assert eml.endswith(".eml") and eml.startswith("2026-11-06 e-mail Robert Kaczmarek")
        assert (katalog / "zalaczniki" / eml).read_bytes() == (skrzynka / "01_d05.eml").read_bytes()
        (zal,) = wynik["zalaczniki"]
        assert "warunki_przedwstępne.pdf" in zal
        assert (katalog / "zalaczniki" / zal).read_bytes() == b"%PDF-1.4 fikcyjny"
        for nazwa in (eml, zal):
            assert pliki[nazwa]["email"] == {"nadawca": "Robert Kaczmarek", "rola": "kupujący",
                                             "data": "2026-11-06T18:42:00+01:00", "temat": w["temat"]}
        # Z listy „Do przypisania” znika, w korespondencji sprawy jest.
        assert all(x["id"] != w["id"] for x in k.get("/api/korespondencja").json()["wiadomosci"])
        stan = k.get(f"/api/sprawy/{SPRAWA}/korespondencja").json()
        assert [x["id"] for x in stan["wiadomosci"]] == [w["id"]]
        assert stan["wiadomosci"][0]["ustalenia_stan"] == "czeka"

    def test_rola_wskazana_przy_zatwierdzeniu_i_nowa_osoba(self, srodowisko):
        k, _, _ = srodowisko
        w = po_temacie(pobierz(k)["wiadomosci"], "Oferta")
        przypisz(k, w, sprawa=INNA, rola="bank")
        osoby = k.get(f"/api/sprawy/{INNA}/korespondencja").json()["osoby"]
        assert osoby == [{"imie": "Jan Obcy", "email": "jan@inna-firma.test", "rola": "bank", "opis": ""}]

    def test_nieznana_rola_i_nieznana_wiadomosc(self, srodowisko):
        k, _, _ = srodowisko
        w = pobierz(k)["wiadomosci"][0]
        assert k.post(f"/api/korespondencja/{w['id']}/przypisz", json={"sprawa": SPRAWA, "rola": "szef"}).status_code == 400
        assert k.post("/api/korespondencja/nieznana1/przypisz", json={"sprawa": SPRAWA}).status_code == 404
        assert k.post(f"/api/korespondencja/{w['id']}/przypisz", json={"sprawa": "brak00000000"}).status_code == 404

    def test_wiadomosc_zniknela_ze_skrzynki(self, srodowisko):
        k, _, skrzynka = srodowisko
        w = po_temacie(pobierz(k)["wiadomosci"], SYGNATURA)
        (skrzynka / "03_d09.eml").unlink()
        odp = k.post(f"/api/korespondencja/{w['id']}/przypisz", json={"sprawa": SPRAWA})
        assert odp.status_code == 502 and "nie ma już" in odp.json()["detail"]


# --- ustalenia ze zrodlem ---------------------------------------------------------------


class TestUstalenia:
    def _wszystkie(self, k, monkeypatch, mapa=USTALENIA):
        monkeypatch.setattr(bedrock, "wyciagnij_ustalenia", atrapa_ustalen(mapa))
        lista = pobierz(k)["wiadomosci"]
        for fragment in ("Warunki transakcji - ul.", "Re: Warunki", f"{SYGNATURA} - termin"):
            w = przypisz(k, po_temacie(lista, fragment))
            odp = k.post(f"/api/sprawy/{SPRAWA}/korespondencja/{w['id']}/ustalenia")
            assert odp.status_code == 200, odp.text
        return odp.json()

    def test_zrodla_i_brak_potwierdzenia_sprzedajacej(self, srodowisko, monkeypatch):
        k, _, _ = srodowisko
        stan = self._wszystkie(k, monkeypatch)
        (grupa,) = stan["ustalenia_pol"][WWW]
        assert grupa["wartosc"] == "1.12"
        assert [(z["imie"], z["rola_opis"], z["data"][:10]) for z in grupa["zrodla"]] == [
            ("Robert Kaczmarek", "kupujący", "2026-11-06"),
            ("Paweł Nowak", "osoba kontaktowa", "2026-11-09"),
            ("Joanna Kaczmarek", "kupujący", "2026-11-10")]
        pawel = grupa["zrodla"][1]
        assert pawel["relacja"] and "sprzedająca" in pawel["czyje"]
        assert grupa["brak_potwierdzenia"] == [{"imie": "Irena Nowak", "opis": "sprzedająca", "rola_opis": "strona"}]
        assert grupa["potwierdzone"] is False
        assert sorted(grupa["strony_potwierdzajace"]) == ["Joanna Kaczmarek", "Robert Kaczmarek"]
        assert stan["ustalenia_pol"]["inne: koniec najmu kupujących"][0]["wartosc"] == "30.11"

    def test_ustalenia_nie_zmieniaja_pol_ani_projektu(self, srodowisko, monkeypatch):
        k, katalog, _ = srodowisko
        odczyt_przed = (katalog / "odczyt.json").read_bytes()
        pola_przed = k.get(f"/api/sprawy/{SPRAWA}").json()["pola"]
        self._wszystkie(k, monkeypatch)
        assert (katalog / "odczyt.json").read_bytes() == odczyt_przed
        sprawa = k.get(f"/api/sprawy/{SPRAWA}").json()
        assert sprawa["pola"] == pola_przed
        assert next(p for p in sprawa["pola"] if p["nazwa"] == WWW)["wartosc"] is None

        # Projekt z pol, ktore wysyla interfejs: termin wydania zostaje <<BRAK>>.
        widziane = {}

        def model(wzor, dane, opis, legenda=None, rozmowa=None, personalizacja=""):
            widziane["dane"] = json.dumps(dane, ensure_ascii=False)
            widziane["rozmowa"] = rozmowa
            www = next(p for p in dane if p["nazwa"] == WWW)["wartosc"]
            return "AKT\nWydanie nastąpi " + (www or "<<BRAK: termin wydania lokalu>>") + "."
        monkeypatch.setattr(bedrock, "sporzadz_projekt", model)
        odp = k.post(f"/api/sprawy/{SPRAWA}/projekt", json={"pola": sprawa["pola"], "polecenie": ""})
        assert odp.status_code == 200, odp.text
        assert "<<BRAK: termin wydania lokalu>>" in odp.json()["tekst"] and odp.json()["brakujace"] == 1
        assert "1.12" not in widziane["dane"] and "grudnia" not in widziane["dane"]
        assert not widziane["rozmowa"]

    def test_potwierdzenie_przez_wszystkie_strony_nadal_nie_wypelnia_pola(self, srodowisko, monkeypatch):
        k, katalog, skrzynka = srodowisko
        (skrzynka / "06_irena.eml").write_bytes(mail(IRENA, [KANC], f"{SYGNATURA} wydanie",
                                                     "Potwierdzam wydanie 1 grudnia.",
                                                     datetime(2026, 11, 12, 8, 0, tzinfo=TZ), "<irena@poczta-demo.test>"))
        mapa = {**USTALENIA, "Potwierdzam": [{"pole": WWW, "wartosc": "1.12", "cytat": "Potwierdzam wydanie 1 grudnia.",
                                               "pewnosc": "wysoka", "relacja": False, "czyje": ""}]}
        self._wszystkie(k, monkeypatch, mapa)
        w = przypisz(k, po_temacie(k.get("/api/korespondencja").json()["wiadomosci"], f"{SYGNATURA} wydanie"))
        stan = k.post(f"/api/sprawy/{SPRAWA}/korespondencja/{w['id']}/ustalenia").json()
        (grupa,) = stan["ustalenia_pol"][WWW]
        assert grupa["potwierdzone"] is True and grupa["brak_potwierdzenia"] == []
        assert json.loads((katalog / "odczyt.json").read_text("utf-8"))["pola"] == POLA

    def test_relacja_strony_nie_jest_potwierdzeniem(self):
        dane = {"osoby": OSOBY[:1], "wiadomosci": [{"id": "a", "nadawca": {"email": OSOBY[0]["email"]}, "data": "2026-11-09",
                                                    "ustalenia": [{"pole": WWW, "wartosc": "1.12", "relacja": True}]}]}
        (grupa,) = korespondencja.ustalenia_pol(dane)[WWW]
        assert grupa["potwierdzone"] is False and grupa["brak_potwierdzenia"][0]["imie"] == "Irena Nowak"

    def test_blad_modelu_zostawia_stan_blad(self, srodowisko, monkeypatch):
        k, _, _ = srodowisko
        w = przypisz(k, po_temacie(pobierz(k)["wiadomosci"], SYGNATURA))
        odp = k.post(f"/api/sprawy/{SPRAWA}/korespondencja/{w['id']}/ustalenia")   # conftest: brak modelu
        assert odp.status_code == 502
        assert k.get(f"/api/sprawy/{SPRAWA}/korespondencja").json()["wiadomosci"][0]["ustalenia_stan"] == "blad"

    def test_model_filtruje_pola_spoza_listy(self, monkeypatch):
        odpowiedz = json.dumps({"ustalenia": [
            {"pole": WWW, "wartosc": "1.12", "cytat": "1 grudnia", "pewnosc": "wysoka", "relacja": True, "czyje": "mama"},
            {"pole": "zmyślone pole", "wartosc": "x", "cytat": ""},
            {"pole": "inne: koniec najmu", "wartosc": "30.11", "cytat": "najem"},
            {"pole": "ccc: cena", "wartosc": "", "cytat": ""}]})
        wywolania = []
        monkeypatch.setattr(bedrock, "_rozmowa", lambda system, tresc, **kw: wywolania.append((system, tresc, kw)) or odpowiedz)
        wynik = bedrock._wyciagnij_ustalenia("Mama się zgadza, 1 grudnia.", "Re: warunki", [WWW, "ccc: cena"])
        assert [(u["pole"], u["wartosc"], u["relacja"]) for u in wynik] == [(WWW, "1.12", True), ("inne: koniec najmu", "30.11", False)]
        (system, tresc, kw), = wywolania
        assert kw["myslenie"] is False and WWW in tresc[0]["text"]
        assert bedrock._wyciagnij_ustalenia("  ", "", [WWW]) == []


# --- logi, uprawnienia, ustawienia, IMAP -------------------------------------------------


def test_brak_tresci_maili_w_logach(srodowisko, monkeypatch, caplog):
    k, _, _ = srodowisko
    monkeypatch.setattr(bedrock, "wyciagnij_ustalenia", atrapa_ustalen(USTALENIA))
    caplog.set_level(logging.DEBUG)
    lista = pobierz(k)["wiadomosci"]
    k.get("/api/korespondencja")
    for w in lista[:3]:
        w = przypisz(k, w)
        k.post(f"/api/sprawy/{SPRAWA}/korespondencja/{w['id']}/ustalenia")
    k.get(f"/api/sprawy/{SPRAWA}/korespondencja")
    assert "przypisano wiadomosc" in caplog.text     # logi sa - tylko bez tresci
    for tajne in TAJNE + [SYGNATURA, KW]:
        assert tajne not in caplog.text, tajne


def test_uprawnienia_stanowisk():
    assert stanowiska.wymagane("POST", f"/api/sprawy/{SPRAWA}/korespondencja/abc123/ustalenia") == "sprawy_ai"
    assert stanowiska.wymagane("PUT", "/api/korespondencja/ustawienia") == "kancelaria"
    # Przypisanie i sprawdzenie skrzynki moze zrobic sekretariat.
    assert stanowiska.wymagane("POST", "/api/korespondencja/abc123/przypisz") is None
    assert stanowiska.wymagane("POST", "/api/korespondencja/pobierz") is None


class TestUstawienia:
    def test_lokalnie_haslo_tylko_ze_zmiennej_srodowiskowej(self, srodowisko, monkeypatch):
        k, _, _ = srodowisko
        monkeypatch.setattr(korespondencja, "KATALOG_DEMO", "")
        odp = k.put("/api/korespondencja/ustawienia", json={"host": "imap.kancelaria.test", "uzytkownik": "sekretariat",
                                                            "haslo": "tajne-haslo-123"})
        assert odp.status_code == 400 and "PIECZAPP_SKRZYNKA_HASLO" in odp.json()["detail"]
        odp = k.put("/api/korespondencja/ustawienia", json={"host": "imap.kancelaria.test", "uzytkownik": "sekretariat"})
        assert odp.status_code == 200 and odp.json()["host"] == "imap.kancelaria.test"
        for plik in config.DANE.rglob("*.json"):
            assert "tajne-haslo-123" not in plik.read_text("utf-8")
        monkeypatch.setenv("PIECZAPP_SKRZYNKA_HASLO", "z-env")
        dost = korespondencja.dostawca()
        assert isinstance(dost, korespondencja.DostawcaImap) and dost.haslo == "z-env" and dost.port == 993

    def test_w_chmurze_haslo_w_secrets_manager_i_nie_wraca(self, srodowisko, monkeypatch):
        k, _, _ = srodowisko
        zapisane = {}

        class Sejf:
            def zapisz(self, kancelaria, haslo):
                zapisane[kancelaria] = haslo

            def wczytaj(self, kancelaria):
                return zapisane.get(kancelaria, "")
        monkeypatch.setattr(korespondencja, "sejf", Sejf())
        monkeypatch.setattr(korespondencja, "_w_chmurze", lambda: True)
        monkeypatch.setenv("PIECZAPP_SKRZYNKA_HASLO", "nie-uzywane-w-chmurze")
        odp = k.put("/api/korespondencja/ustawienia", json={"host": "imap.kancelaria.test", "uzytkownik": "s",
                                                            "haslo": "tajne-haslo-123"})
        assert odp.status_code == 200 and odp.json()["haslo_zapisane"] is True
        assert "tajne-haslo-123" not in odp.text and "tajne-haslo-123" not in k.get("/api/korespondencja/ustawienia").text
        assert zapisane == {"lokalna": "tajne-haslo-123"}
        assert korespondencja.haslo() == "tajne-haslo-123"
        assert korespondencja.dostawca().haslo == "tajne-haslo-123"   # katalog demo nie dziala w chmurze

    def test_nazwa_sekretu_z_prefiksem_notarai(self):
        assert korespondencja.sejf.nazwa("kancelaria pod/siódemką") .startswith("notarai-skrzynka-kancelaria-pod-")


class AtrapaImap:
    def __init__(self, host, port, ssl_context=None, timeout=None):
        assert isinstance(ssl_context, ssl.SSLContext) and ssl_context.verify_mode == ssl.CERT_REQUIRED
        self.polecenia = []
        self.maile = {b"7": maile_demo()["02_d10.eml"], b"9": maile_demo()["03_d09.eml"]}

    def login(self, uzytkownik, haslo):
        self.polecenia.append(("login", uzytkownik))
        return "OK", [b""]

    def select(self, folder, readonly=False):
        assert readonly is True and folder == '"INBOX"'
        return "OK", [b"2"]

    def response(self, kod):
        return kod, [b"4242"]

    def uid(self, polecenie, *argumenty):
        self.polecenia.append((polecenie,) + argumenty)
        if polecenie == "SEARCH":
            return "OK", [b"7 9"]
        assert argumenty[1] == "(BODY.PEEK[])"        # bez oznaczania jako przeczytane
        tresc = self.maile.get(argumenty[0].encode())
        return ("OK", [(b"1 (UID x BODY[] {1}", tresc), b")"]) if tresc else ("OK", [None])

    def logout(self):
        return "BYE", [b""]


def test_imap_tls_tylko_odczyt_i_nowe_wiadomosci(monkeypatch):
    monkeypatch.setattr(korespondencja.DostawcaImap, "polacz", staticmethod(AtrapaImap))
    dost = korespondencja.DostawcaImap("imap.kancelaria.test", 993, "sekretariat", "x")
    nowe = dost.nowe({"4242:7"})
    assert [i for i, _ in nowe] == ["4242:9"]
    assert korespondencja.parsuj(nowe[0][1])["temat"] == f"{SYGNATURA} - termin wydania"
    assert korespondencja.parsuj(dost.pobierz("4242:7"))["nadawca"]["imie"] == "Paweł Nowak"
    with pytest.raises(korespondencja.BladSkrzynki):
        dost.pobierz("1111:7")          # inna numeracja skrzynki
    with pytest.raises(korespondencja.BladSkrzynki):
        dost.pobierz("4242:8")


def test_imap_bez_konfiguracji():
    with pytest.raises(korespondencja.BladSkrzynki):
        korespondencja.DostawcaImap("", 993, "", "")


def test_dane_demo_odcinka_01():
    """3 maile demo: fikcyjne adresy .test, D05 z zalacznikiem, D10 w watku D05, D09 z sygnatura."""
    from pathlib import Path
    katalog = Path(__file__).parent / "scripts" / "demo_odcinek01_skrzynka"
    maile = {p.name: korespondencja.parsuj(p.read_bytes()) for p in sorted(katalog.glob("*.eml"))}
    assert len(maile) == 3
    for m in maile.values():
        assert all(a["email"].endswith(".test") for a in [m["nadawca"], *m["adresaci"]])
    d05, d10, d09 = maile.values()
    assert d05["nadawca"]["imie"] == "Robert Kaczmarek" and "1 grudnia" in d05["tekst"] and d05["zalaczniki"]
    assert d10["in_reply_to"] == [d05["message_id"]] and "Mama się zgadza, 1 grudnia aktualny" in d10["tekst"]
    assert d09["nadawca"]["imie"] == "Joanna Kaczmarek" and "30 listopada" in d09["tekst"] and SYGNATURA in d09["temat"]
