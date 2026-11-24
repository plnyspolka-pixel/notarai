"""Pilot telefonu -> istniejacy pomocnik Windows, bez drugiej instalacji.

Testy wykorzystuja lokalna atrape S3 i prawdziwy middleware izolacji kancelarii.
Nie otwieraja przegladarki ani nie lacza sie z internetem.
"""
from pathlib import Path

from test_urzadzenia import _polacz, srodowisko  # noqa: F401


def _aktywny(klient, notariusz, nazwa="KOMPUTER"):
    pomocnik, identyfikator = _polacz(klient, notariusz, nazwa)
    assert klient.get("/api/pomocnik/zlecenia", headers=pomocnik).status_code == 200
    return pomocnik, identyfikator


class TestPilotMobilny:
    def test_zadanie_trafia_tylko_do_wybranego_komputera(self, srodowisko):
        klient, kancelaria, _, _ = srodowisko
        _, osoba = kancelaria("Kancelaria Mobilna")
        pc1, id1 = _aktywny(klient, osoba, "PC-1")
        pc2, id2 = _aktywny(klient, osoba, "PC-2")
        odp = klient.post("/api/urzadzenia/polecenia", headers=osoba,
                          json={"komputer": id2, "cel": "znajdz dzialke",
                                "dozwolone_hosty": [" GEOportal.gov.pl "]})
        assert odp.status_code == 202
        zadanie = odp.json()["zlecenie"]
        assert klient.get("/api/pomocnik/zlecenia", headers=pc1).json() == []
        lista = klient.get("/api/pomocnik/zlecenia", headers=pc2).json()
        assert len(lista) == 1 and lista[0]["id"] == zadanie
        assert lista[0]["tresc"]["dozwolone_hosty"] == ["geoportal.gov.pl"]
        assert lista[0]["tresc"]["docelowy_komputer"] == id2
        assert id1 != id2

    def test_wynik_wraca_na_telefon_bez_sprawy(self, srodowisko):
        klient, kancelaria, _, _ = srodowisko
        _, osoba = kancelaria("Kancelaria Mobilna")
        pomocnik, pc = _aktywny(klient, osoba)
        z = klient.post("/api/urzadzenia/polecenia", headers=osoba,
                        json={"komputer": pc, "cel": "sprawdz rejestr"}).json()["zlecenie"]
        adres = f"/api/urzadzenia/polecenia/{z}"
        assert klient.get(adres, headers=osoba).json() == {"stan": "czeka", "raport": None, "zgoda": None}
        wynik = klient.post(f"/api/pomocnik/zlecenia/{z}/wynik", headers=pomocnik,
                            json={"kroki": [{"nr": 1, "akcja": "czytaj", "cel": "portal"}],
                                  "podsumowanie": "Otworzono portal",
                                  "pytanie": "", "bledy": []})
        assert wynik.status_code == 200
        odp = klient.get(adres, headers=osoba)
        assert odp.status_code == 200
        assert odp.json()["stan"] == "wykonane"
        assert odp.json()["raport"]["podsumowanie"] == "Otworzono portal"
        assert odp.json()["raport"]["kroki"][0]["akcja"] == "czytaj"

    def test_inny_komputer_nie_moze_zglaszac_wyniku_ani_kroku(self, srodowisko):
        klient, kancelaria, _, _ = srodowisko
        _, osoba = kancelaria("Kancelaria Mobilna")
        pc1, id1 = _aktywny(klient, osoba, "PC-1")
        pc2, _ = _aktywny(klient, osoba, "PC-2")
        zadanie = klient.post("/api/urzadzenia/polecenia", headers=osoba,
                              json={"komputer": id1, "cel": "otworz rejestr"}).json()["zlecenie"]
        krok = {"cel": "otworz rejestr", "stan": {"adres": "https://example.gov.pl",
                "tekst": "", "elementy": []}, "kroki": []}
        assert klient.post(f"/api/pomocnik/klikamy/{zadanie}/krok",
                           headers=pc2, json=krok).status_code == 403
        assert klient.post(f"/api/pomocnik/zlecenia/{zadanie}/wynik",
                           headers=pc2, json={}).status_code == 403
        assert klient.get("/api/pomocnik/zlecenia", headers=pc1).json()[0]["id"] == zadanie

    def test_kancelarie_nie_widza_swoich_komputerow_i_zadan_nawzajem(self, srodowisko):
        klient, kancelaria, _, _ = srodowisko
        _, a = kancelaria("Kancelaria A")
        _, b = kancelaria("Kancelaria B")
        _, pc = _aktywny(klient, a)
        obcy = klient.post("/api/urzadzenia/polecenia", headers=b,
                           json={"komputer": pc, "cel": "dzialka"})
        assert obcy.status_code == 404
        zadanie = klient.post("/api/urzadzenia/polecenia", headers=a,
                              json={"komputer": pc, "cel": "dzialka"}).json()["zlecenie"]
        assert klient.get(f"/api/urzadzenia/polecenia/{zadanie}",
                          headers=b).status_code == 404

    def test_offline_nie_przyjmuje_polecen(self, srodowisko):
        klient, kancelaria, _, _ = srodowisko
        _, osoba = kancelaria("Kancelaria Offline")
        _, pc = _polacz(klient, osoba)
        odp = klient.post("/api/urzadzenia/polecenia", headers=osoba,
                          json={"komputer": pc, "cel": "sprawdz"})
        assert odp.status_code == 409

    def test_puste_polecenie_i_lokalne_hosty_odrzucone(self, srodowisko):
        klient, kancelaria, _, _ = srodowisko
        _, osoba = kancelaria("Kancelaria Mobilna")
        _, pc = _aktywny(klient, osoba)
        for cel, hosty in [("  ", []), ("dzialaj", ["localhost"]),
                            ("dzialaj", ["127.0.0.1"]), ("dzialaj", ["intranet.local"])]:
            odp = klient.post("/api/urzadzenia/polecenia", headers=osoba,
                              json={"komputer": pc, "cel": cel,
                                    "dozwolone_hosty": hosty})
            assert odp.status_code == 400

    def test_telefon_musi_byc_zalogowany_i_helper_nie_dostaje_api_pilota(self, srodowisko):
        klient, kancelaria, _, _ = srodowisko
        _, osoba = kancelaria("Kancelaria Mobilna")
        pomocnik, pc = _aktywny(klient, osoba)
        payload = {"komputer": pc, "cel": "sprawdz"}
        assert klient.post("/api/urzadzenia/polecenia", json=payload).status_code == 401
        assert klient.post("/api/urzadzenia/polecenia",
                           headers=pomocnik, json=payload).status_code == 403


def test_mobile_ui_ma_pilota_i_nie_wymusza_pobierania_exe():
    tekst = (Path(__file__).parent / "static" / "index.html").read_text("utf-8")
    assert 'id="okno-pilot"' in tekst
    assert 'id="pilot-cel"' in tekst
    assert 'if (!naWindows)' in tekst
    assert '$("btn-instaluj-pomocnika").hidden = !naWindows;' in tekst
    assert 'if (!((ostatniStanPomocnika || {}).urzadzenia || []).length && naWindows)' in tekst


class TestZgodaNaWyslanie:
    def test_telefon_potwierdza_jeden_konkretny_krok(self, srodowisko):
        klient, kancelaria, _, _ = srodowisko
        _, osoba = kancelaria("Kancelaria Zgody")
        pomocnik, pc = _aktywny(klient, osoba)
        zadanie = klient.post("/api/urzadzenia/polecenia", headers=osoba,
                              json={"komputer": pc, "cel": "wypelnij i wyslij"}).json()["zlecenie"]
        prosba = klient.post(f"/api/pomocnik/polecenia/{zadanie}/zgoda",
                             headers=pomocnik,
                             json={"host": "geoportal.gov.pl", "etykieta": "Wyślij wniosek"})
        assert prosba.status_code == 201
        id_zgody = prosba.json()["id"]
        oczekujaca = klient.get(f"/api/urzadzenia/polecenia/{zadanie}",
                               headers=osoba).json()["zgoda"]
        assert oczekujaca["id"] == id_zgody
        assert oczekujaca["host"] == "geoportal.gov.pl"
        assert oczekujaca["etykieta"] == "Wyślij wniosek"
        url = f"/api/pomocnik/polecenia/{zadanie}/zgoda/{id_zgody}"
        assert klient.get(url, headers=pomocnik).json()["stan"] == "czeka"
        decyzja = klient.post(f"/api/urzadzenia/polecenia/{zadanie}/zgoda",
                              headers=osoba, json={"id": id_zgody, "zgoda": True})
        assert decyzja.status_code == 200 and decyzja.json()["stan"] == "zgoda"
        assert klient.get(url, headers=pomocnik).json()["stan"] == "zgoda"
        assert klient.get(url, headers=pomocnik).json()["stan"] == "odebrana"
        ponownie = klient.post(f"/api/urzadzenia/polecenia/{zadanie}/zgoda",
                               headers=osoba, json={"id": id_zgody, "zgoda": True})
        assert ponownie.status_code == 409

    def test_odmowa_zatrzymuje_wyslanie(self, srodowisko):
        klient, kancelaria, _, _ = srodowisko
        _, osoba = kancelaria("Kancelaria Zgody")
        pomocnik, pc = _aktywny(klient, osoba)
        zadanie = klient.post("/api/urzadzenia/polecenia", headers=osoba,
                              json={"komputer": pc, "cel": "wyslij"}).json()["zlecenie"]
        id_zgody = klient.post(f"/api/pomocnik/polecenia/{zadanie}/zgoda",
                              headers=pomocnik, json={"host": "krz.ms.gov.pl",
                                                     "etykieta": "Wyślij"}).json()["id"]
        klient.post(f"/api/urzadzenia/polecenia/{zadanie}/zgoda", headers=osoba,
                    json={"id": id_zgody, "zgoda": False})
        assert klient.get(f"/api/pomocnik/polecenia/{zadanie}/zgoda/{id_zgody}",
                          headers=pomocnik).json()["stan"] == "odmowa"

    def test_drugi_pc_nie_moze_prosic_ani_odebrac_zgody(self, srodowisko):
        klient, kancelaria, _, _ = srodowisko
        _, osoba = kancelaria("Kancelaria Zgody")
        pc1, id1 = _aktywny(klient, osoba, "PC1")
        pc2, _ = _aktywny(klient, osoba, "PC2")
        zadanie = klient.post("/api/urzadzenia/polecenia", headers=osoba,
                              json={"komputer": id1, "cel": "wyslij"}).json()["zlecenie"]
        path = f"/api/pomocnik/polecenia/{zadanie}/zgoda"
        args = {"host": "krz.ms.gov.pl", "etykieta": "Wyślij"}
        assert klient.post(path, headers=pc2, json=args).status_code == 403
        id_zgody = klient.post(path, headers=pc1, json=args).json()["id"]
        assert klient.get(f"{path}/{id_zgody}", headers=pc2).status_code == 403
        assert klient.post(path, headers=pc1, json=args).status_code == 409

    def test_nie_da_sie_potwierdzic_podpisu_ani_platnosci(self, srodowisko):
        klient, kancelaria, _, _ = srodowisko
        _, osoba = kancelaria("Kancelaria Zgody")
        pomocnik, pc = _aktywny(klient, osoba)
        zadanie = klient.post("/api/urzadzenia/polecenia", headers=osoba,
                              json={"komputer": pc, "cel": "wyslij"}).json()["zlecenie"]
        for etykieta in ("Podpisz kwalifikowanym", "Sign document", "Zapłać",
                          "Usuń sprawę", "Autoryzuj przelew"):
            odp = klient.post(f"/api/pomocnik/polecenia/{zadanie}/zgoda",
                              headers=pomocnik,
                              json={"host": "krz.ms.gov.pl", "etykieta": etykieta})
            assert odp.status_code == 403, etykieta

    def test_inna_kancelaria_nie_moze_zatwierdzic(self, srodowisko):
        klient, kancelaria, _, _ = srodowisko
        _, osoba = kancelaria("Kancelaria Zgody")
        _, obca = kancelaria("Kancelaria Obca")
        pomocnik, pc = _aktywny(klient, osoba)
        zadanie = klient.post("/api/urzadzenia/polecenia", headers=osoba,
                              json={"komputer": pc, "cel": "wyslij"}).json()["zlecenie"]
        id_zgody = klient.post(f"/api/pomocnik/polecenia/{zadanie}/zgoda",
                              headers=pomocnik,
                              json={"host": "krz.ms.gov.pl", "etykieta": "Wyślij"}).json()["id"]
        odp = klient.post(f"/api/urzadzenia/polecenia/{zadanie}/zgoda", headers=obca,
                          json={"id": id_zgody, "zgoda": True})
        assert odp.status_code == 404

    def test_wygasla_zgoda_nie_moze_byc_wykorzystana(self, srodowisko, monkeypatch):
        from datetime import datetime, timedelta, timezone
        import zgody_pilota
        klient, kancelaria, _, _ = srodowisko
        _, osoba = kancelaria("Kancelaria Zgody")
        pomocnik, pc = _aktywny(klient, osoba)
        zadanie = klient.post("/api/urzadzenia/polecenia", headers=osoba,
                              json={"komputer": pc, "cel": "wyslij"}).json()["zlecenie"]
        id_zgody = klient.post(f"/api/pomocnik/polecenia/{zadanie}/zgoda",
                              headers=pomocnik,
                              json={"host": "krz.ms.gov.pl", "etykieta": "Wyślij"}).json()["id"]
        daleko = datetime.now(timezone.utc) + timedelta(seconds=130)
        monkeypatch.setattr(zgody_pilota, "_teraz", lambda: daleko)
        assert klient.post(f"/api/urzadzenia/polecenia/{zadanie}/zgoda", headers=osoba,
                           json={"id": id_zgody, "zgoda": True}).status_code == 409
        assert klient.get(f"/api/pomocnik/polecenia/{zadanie}/zgoda/{id_zgody}",
                          headers=pomocnik).json()["stan"] == "wygasla"

    def test_wysylka_wymaga_roli_notariusza(self, srodowisko):
        klient, kancelaria, _, _ = srodowisko
        _, osoba = kancelaria("Kancelaria Zgody")
        pomocnik, pc = _aktywny(klient, osoba)
        zadanie = klient.post("/api/urzadzenia/polecenia", headers=osoba,
                              json={"komputer": pc, "cel": "wyslij"}).json()["zlecenie"]
        # Sciezki sa egzekwowane przez middleware, nie przycisk.
        import stanowiska
        assert stanowiska.wymagane("POST", f"/api/urzadzenia/polecenia/{zadanie}/zgoda") == "kancelaria"
        assert stanowiska.wymagane("POST", "/api/urzadzenia/polecenia") == "rejestry"


def test_approval_dialog_present():
    tekst = (Path(__file__).parent / "static" / "index.html").read_text("utf-8")
    assert 'id="okno-zgoda-pilota"' in tekst
    assert 'id="pilot-zgoda-tak"' in tekst
    assert 'id="pilot-zgoda-nie"' in tekst
    assert 'Pozwól tylko tym razem' in tekst


class TestKartyPrzezTelefon:
    def test_komenda_otwiera_nowa_karte_na_wskazanym_pc(self, srodowisko):
        klient, kancelaria, _, _ = srodowisko
        _, osoba = kancelaria("Kancelaria Karty")
        pc1, id1 = _aktywny(klient, osoba, "PC1")
        pc2, _ = _aktywny(klient, osoba, "PC2")
        odp = klient.post("/api/urzadzenia/polecenia", headers=osoba,
                          json={"komputer": id1,
                                "cel": "Otwórz nową kartę https://geoportal.gov.pl/mapa"})
        assert odp.status_code == 202
        assert klient.get("/api/pomocnik/zlecenia", headers=pc2).json() == []
        zadanie = klient.get("/api/pomocnik/zlecenia", headers=pc1).json()[0]
        assert zadanie["rodzaj"] == "karty"
        assert zadanie["tresc"]["adres"] == "https://geoportal.gov.pl/mapa"
        assert zadanie["tresc"]["nowa_karta"] is True

    def test_jawny_adres_i_zwykla_nawigacja(self, srodowisko):
        klient, kancelaria, _, _ = srodowisko
        _, osoba = kancelaria("Kancelaria Karty")
        pc, id_komputera = _aktywny(klient, osoba)
        odp = klient.post("/api/urzadzenia/polecenia", headers=osoba,
                          json={"komputer": id_komputera, "cel": "wejdź na stronę",
                                "adres": "https://krz.ms.gov.pl/", "nowa_karta": False})
        assert odp.status_code == 202
        zadanie = klient.get("/api/pomocnik/zlecenia", headers=pc).json()[0]
        assert zadanie["rodzaj"] == "karty"
        assert zadanie["tresc"]["nowa_karta"] is False

    def test_nie_akceptuje_prywatnych_adresow_i_niebezpiecznych_schematow(self, srodowisko):
        klient, kancelaria, _, _ = srodowisko
        _, osoba = kancelaria("Kancelaria Karty")
        _, id_komputera = _aktywny(klient, osoba)
        for adres in ("http://geoportal.gov.pl/", "https://127.0.0.1/",
                      "https://intranet.local/", "file:///c:/users/",
                      "https://uzytkownik:haslo@geoportal.gov.pl/",
                      "https://geoportal.gov.pl:444/", "https://geoportal.gov.pl:abc/"):
            odp = klient.post("/api/urzadzenia/polecenia", headers=osoba,
                              json={"komputer": id_komputera, "cel": "otworz",
                                    "adres": adres, "nowa_karta": True})
            assert odp.status_code == 400, adres

    def test_zadanie_karty_zwraca_raport(self, srodowisko):
        klient, kancelaria, _, _ = srodowisko
        _, osoba = kancelaria("Kancelaria Karty")
        pc, id_komputera = _aktywny(klient, osoba)
        identyfikator = klient.post("/api/urzadzenia/polecenia", headers=osoba,
                                    json={"komputer": id_komputera, "cel": "otworz",
                                          "adres": "https://geoportal.gov.pl/",
                                          "nowa_karta": True}).json()["zlecenie"]
        odp = klient.post(f"/api/pomocnik/zlecenia/{identyfikator}/wynik",
                          headers=pc, json={"podsumowanie": "Nowa karta", "bledy": []})
        assert odp.status_code == 200
        raport = klient.get(f"/api/urzadzenia/polecenia/{identyfikator}",
                            headers=osoba).json()["raport"]
        assert raport["podsumowanie"] == "Nowa karta"


KLUCZ_TELEFONU = {"kty": "EC", "crv": "P-256", "x": "AAAA", "y": "BBBB"}
KLUCZ_ROZSZERZENIA = {"kty": "EC", "crv": "P-256", "x": "CCCC", "y": "DDDD"}


class TestZaszyfrowanegoPodgladu:
    def test_klatka_jest_szyfrowana_i_nalezy_do_kancelarii(self, srodowisko):
        klient, kancelaria, _, _ = srodowisko
        _, osoba = kancelaria("Kancelaria Wideo")
        _, obca = kancelaria("Kancelaria Obca")
        pc, id1 = _aktywny(klient, osoba)
        pc2, _ = _aktywny(klient, osoba, "DRUGI-PC")
        zadanie = klient.post("/api/urzadzenia/polecenia", headers=osoba,
                              json={"komputer": id1, "cel": "czytaj stronę",
                                    "podglad_pubkey": KLUCZ_TELEFONU}).json()["zlecenie"]
        paczka = {"numer": 1, "klucz": KLUCZ_ROZSZERZENIA,
                  "iv": "abcdefghijklmnop", "dane": "Y2lwaGVydGV4dA=="}
        wysylka = f"/api/pomocnik/podglad/{zadanie}"
        odczyt = f"/api/urzadzenia/polecenia/{zadanie}/podglad"
        assert klient.post(wysylka, headers=pc2, json=paczka).status_code == 403
        assert klient.post(wysylka, headers=osoba, json=paczka).status_code == 403
        assert klient.post(wysylka, headers=pc, json=paczka).status_code == 202
        assert klient.get(odczyt, headers=obca).json()["stan"] == "brak"
        aktualny = klient.get(odczyt, headers=osoba).json()
        assert aktualny["stan"] == "kadr"
        assert aktualny["kadr"]["numer"] == 1
        assert aktualny["kadr"]["dane"] == paczka["dane"]
        assert "obraz" not in str(aktualny).lower()
        assert klient.get(odczyt).status_code == 401

    def test_kadr_wygasa_automatycznie(self, srodowisko, monkeypatch):
        import podglad_pilota
        from datetime import datetime, timedelta, timezone
        klient, kancelaria, _, _ = srodowisko
        _, osoba = kancelaria("Kancelaria Wideo")
        pc, id1 = _aktywny(klient, osoba)
        zadanie = klient.post("/api/urzadzenia/polecenia", headers=osoba,
                              json={"komputer": id1, "cel": "czytaj",
                                    "podglad_pubkey": KLUCZ_TELEFONU}).json()["zlecenie"]
        klient.post(f"/api/pomocnik/podglad/{zadanie}", headers=pc,
                    json={"numer": 1, "klucz": KLUCZ_ROZSZERZENIA,
                          "iv": "abcdefghijklmnop", "dane": "YQ=="})
        daleko = datetime.now(timezone.utc) + timedelta(seconds=18)
        monkeypatch.setattr(podglad_pilota, "_teraz", lambda: daleko)
        assert klient.get(f"/api/urzadzenia/polecenia/{zadanie}/podglad",
                          headers=osoba).json()["stan"] == "brak"

    def test_bez_klucza_telefonu_nie_wolno_przesylac_obrazu(self, srodowisko):
        klient, kancelaria, _, _ = srodowisko
        _, osoba = kancelaria("Kancelaria Wideo")
        pc, id1 = _aktywny(klient, osoba)
        zadanie = klient.post("/api/urzadzenia/polecenia", headers=osoba,
                              json={"komputer": id1, "cel": "czytaj"}).json()["zlecenie"]
        odp = klient.post(f"/api/pomocnik/podglad/{zadanie}", headers=pc,
                          json={"numer": 1, "klucz": KLUCZ_ROZSZERZENIA,
                                "iv": "abcdefghijklmnop", "dane": "YQ=="})
        assert odp.status_code == 403


def test_preview_ui_and_extension_code_have_encryption():
    root = Path(__file__).parent
    html = (root / "static" / "index.html").read_text("utf-8")
    js = (root / "rozszerzenie" / "podglad.js").read_text("utf-8")
    assert 'id="pilot-kadr"' in html
    assert 'id="pilot-nowa-karta"' in html
    assert "AES-GCM" in js and "ECDH" in js
    assert "captureVisibleTab" in js
    assert "podglad_pubkey" in (root / "rozszerzenie" / "panel.js").read_text("utf-8")
