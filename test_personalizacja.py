"""Personalizacja: silnik klauzul, zasady kancelarii, styl z aktow, API.

Dane zmyslone (Kowalski/Nowak/Zielinski, PESEL-e z poprawna suma kontrolna
niepotrzebne - silnik nie waliduje, tylko usuwa).
"""
import io
import json
from unittest.mock import patch

import pytest
from docx import Document
from fastapi.testclient import TestClient

import kategorie
import klauzule
import slownie
import styl
import zasady

AKT = """Repertorium A nr 1234/2026
AKT NOTARIALNY
Dnia 03.12.2025r. przed notariuszem Anną Wiśniewską w Kancelarii Notarialnej w Zalesiu stawili się:
1. Jan KOWALSKI, syn Piotra i Marii, PESEL 80010112345, legitymujący się dowodem osobistym ABC123456, zamieszkały w Zalesiu, ul. Lipowa 2 m. 4, 05-500 Zalesie,
2. Anna Nowak, córka Józefa, PESEL 85020254321, zamieszkała w Kobyłce.
Tożsamość stawających notariusz ustaliła na podstawie dowodów osobistych.
UMOWA SPRZEDAŻY
§ 1. Jan Kowalski oświadcza, że jest właścicielem działki nr 12/3 o powierzchni 0,1234 ha, położonej w obrębie Zalesie, dla której Sąd Rejonowy w Zalesiu prowadzi księgę wieczystą KW nr WA1L/00012345/6.
§ 2. 1. Jan Kowalski sprzedaje Annie Nowak działkę opisaną w § 1 za cenę 250.000,00 zł (dwieście pięćdziesiąt tysięcy złotych), a Anna Nowak kupuje.
2. Cena zostanie zapłacona przelewem, o czym mowa w ust. 3.
§ 4. Wydanie przedmiotu umowy nastąpi z dniem dzisiejszym.
§ 5. Notariusz pouczyła strony o treści art. 158 kodeksu cywilnego oraz § 3 rozporządzenia Ministra Sprawiedliwości.
§ 6. Taksę notarialną pobrano w kwocie 2.000,00 zł na podstawie § 3 rozporządzenia.
Akt ten został odczytany, przyjęty i podpisany.
"""
DANE_OSOBOWE = ["KOWALSKI", "Kowalski", "Nowak", "80010112345", "85020254321", "ABC123456",
                "WA1L/00012345/6", "Lipowa", "Kobyłce", "Piotra", "Józefa", "Wiśniewską"]


def ustawienia(*teksty):
    lista = []
    for i, t in enumerate(teksty):
        z = zasady.interpretuj(t)
        z["id"] = f"z{i}"
        lista.append(z)
    return {"zasady": lista, "wbudowane_wylaczone": []}


# ---------------------------------------------------------------------------
class TestKategorie:
    def test_rodzaj_dokumentu(self):
        assert kategorie.klasyfikuj_dokument(AKT)[0]["rodzaj"] == "sprzedaz"
        assert kategorie.klasyfikuj_dokument("Testament. Powołuję do całego spadku córkę.")[0]["rodzaj"] == "testament"
        assert kategorie.klasyfikuj_dokument("Lorem ipsum")[0]["rodzaj"] == kategorie.RODZAJ_INNY

    def test_czesc_aktu(self):
        assert kategorie.klasyfikuj_czesc("Notariusz pouczył strony o treści art. 158 k.c.")[0] == "pouczenia"
        assert kategorie.klasyfikuj_czesc("Taksę notarialną pobrano w kwocie 100 zł")[0] == "koszty"
        assert kategorie.klasyfikuj_czesc("Stawający wnoszą do Sądu Rejonowego Wydział Ksiąg Wieczystych o wpis")[0] == "wnioski_kw"

    def test_slownik_ui_ma_wszystko(self):
        s = kategorie.slownik_dla_ui()
        assert set(kategorie.RODZAJE) <= set(s["rodzaje"]) and "inne" in s["obszary"]


# ---------------------------------------------------------------------------
class TestSilnikKlauzul:
    def test_drzewo_i_czesci(self):
        r = klauzule.rozbij(AKT)
        typy = [(k.typ, k.numer) for k in r.klauzule]
        assert ("paragraf", "2") in typy and ("ustep", "1") in typy  # "§ 2. 1." rozdzielone
        czesci = {k.czesc for k in r.klauzule}
        assert {"komparycja", "stan_prawny", "pouczenia", "koszty", "zamkniecie"} <= czesci

    def test_odeslania_wewnetrzne_i_zewnetrzne(self):
        assert [o["paragraf"] for o in klauzule.odeslania_w_tekscie("opisaną w § 1 ust. 2")] == ["1"]
        assert klauzule.odeslania_w_tekscie("art. 5 § 2 kodeksu cywilnego") == []
        assert klauzule.odeslania_w_tekscie("na podstawie § 3 rozporządzenia Ministra") == []

    def test_kontrola_konstrukcji(self):
        kody = {p["kod"] for p in klauzule.sprawdz_konstrukcje(klauzule.rozbij(AKT))}
        assert kody == {"numeracja_paragrafow", "odeslania"}   # brak § 3, "ust. 3" nie istnieje

    def test_luki_i_warianty(self):
        kody = {p["kod"] for p in klauzule.sprawdz_konstrukcje(klauzule.rozbij(
            "§ 1. Cena ?? zł\n// albo gotówką\n§ 2. Strony <<BRAK: data>> podpisują."))}
        assert kody == {"luki", "warianty"}   # <<BRAK>> to celowy znacznik, nie luka

    def test_przenumerowanie_z_odeslaniami(self):
        tekst, zmiany = klauzule.przenumeruj("§ 1. A\n§ 3. B, o którym mowa w § 4.\n§ 4. C zgodnie z § 3 rozporządzenia.")
        assert zmiany == {"3": "2", "4": "3"}
        assert tekst == "§ 1. A\n§ 2. B, o którym mowa w § 3.\n§ 3. C zgodnie z § 3 rozporządzenia."

    def test_pseudonimizacja_usuwa_dane(self):
        szkielety = " ".join(klauzule.pseudonimizuj(k.tekst) for k in klauzule.rozbij(AKT).klauzule)
        for dana in DANE_OSOBOWE:
            assert dana not in szkielety, dana
        assert "art. 158 kodeksu cywilnego" in szkielety and "{PESEL}" in szkielety

    def test_ta_sama_klauzula_ten_sam_identyfikator(self):
        a = "Jan KOWALSKI, PESEL 80010112345, zamieszkały w Zalesiu"
        b = "Ewa LIS, PESEL 70010112345, zamieszkały w Kobyłce"
        assert klauzule.identyfikator(a) == klauzule.identyfikator(b)


# ---------------------------------------------------------------------------
class TestSlownie:
    @pytest.mark.parametrize("kwota,tekst", [
        ("250.000,00", "dwieście pięćdziesiąt tysięcy złotych"),
        ("1 001,50", "tysiąc jeden złotych pięćdziesiąt groszy"),
        ("22", "dwadzieścia dwa złote"),
        ("12", "dwanaście złotych"),
        ("1", "jeden złoty"),
        ("2,01", "dwa złote jeden grosz"),
    ])
    def test_kwoty(self, kwota, tekst):
        assert slownie.slownie_kwoty(kwota) == tekst


# ---------------------------------------------------------------------------
class TestInterpretacja:
    @pytest.mark.parametrize("tekst,typ", [
        ("Zamiast „w/w” pisz „wyżej wymieniony”", "zamiana"),
        ("Nie piszemy „niniejszy”, tylko „ten”", "zamiana"),
        ("Pisz „Stawający” zamiast „Stawiający”", "zamiana"),
        ("w/w -> wyżej wymieniony", "zamiana"),
        ("Nigdy nie używaj słowa „niniejszy”", "zakaz_frazy"),
        ("Bez skrótu „tzw.”", "zakaz_frazy"),
        ("Kwoty zawsze cyframi i słownie", "kwoty_slownie"),
        ("Kwoty z kropką co trzy cyfry, np. 250.000,00 zł", "separator_tysiecy"),
        ("Daty zapisuj jak 03.12.2025 r.", "format_daty"),
        ("Po § zawsze spacja", "spacja_paragraf"),
        ("Cudzysłowy tylko polskie", "cudzyslowy"),
        ("Zawsze pouczenie o RODO", "wymagana_czesc"),
        ("PESEL zawsze w komparycji", "wymagana_fraza"),
        ("Nazwiska stawających w komparycji wielkimi literami", "wytyczna"),
    ])
    def test_typ(self, tekst, typ):
        assert zasady.interpretuj(tekst)["typ"] == typ

    def test_zakres_i_kierunek_zamiany(self):
        z = zasady.interpretuj("Pisz „Stawający” zamiast „Stawiający”")
        assert z["parametry"] == {"zakazane": ["Stawiający"], "zamiennik": "Stawający"}
        z = zasady.interpretuj("W umowach sprzedaży zawsze wnioski wieczystoksięgowe")
        assert z["zakres"]["rodzaje"] == ["sprzedaz"] and z["parametry"]["czesc"] == "wnioski_kw"

    def test_nazwa_ustawy_nie_zaweza_zakresu(self):
        z = zasady.interpretuj("W darowiznach zawsze pouczenie o art. 9 ust. 1 ustawy o podatku od spadków i darowizn")
        assert z["typ"] == "wymagana_fraza" and z["parametry"]["frazy"] == ["art. 9 ust. 1"]
        assert z["zakres"]["rodzaje"] == ["darowizna"]
        z = zasady.interpretuj("Zawsze pouczenie o art. 2 ustawy o kształtowaniu ustroju rolnego")
        assert z["zakres"]["rodzaje"] == []

    def test_poziom(self):
        assert zasady.interpretuj("Staraj się unikać słowa „przedmiotowy”")["poziom"] == "ostrzega"
        assert zasady.interpretuj("Nigdy nie używaj „przedmiotowy”")["poziom"] == "blokuje"

    def test_opis_dla_notariusza(self):
        assert "dopisuję sam" in zasady.interpretuj("Kwoty zawsze cyframi i słownie")["opis"]
        assert "poprawiam sam" in zasady.interpretuj("Po § zawsze spacja")["opis"]

    def test_pusta_zasada(self):
        with pytest.raises(ValueError):
            zasady.interpretuj("   ")


# ---------------------------------------------------------------------------
class TestSprawdzanieIAutonaprawa:
    def test_zamiana_z_zachowaniem_wielkosci_liter(self):
        u = ustawienia("Zamiast „w/w” pisz „wyżej wymieniony”")
        tekst, poprawki = zasady.napraw("W/w lokal i w/w działka.", u, [])
        assert tekst == "Wyżej wymieniony lokal i wyżej wymieniony działka."
        assert poprawki[0]["ile"] == 2

    def test_zakaz_lapie_odmiany(self):
        r = zasady.sprawdz("Przedmiotem niniejszego aktu jest lokal.", ustawienia("Nigdy nie używaj słowa „niniejszy”"))
        assert r["blokujacych"] == 1 and r["naruszenia"][0]["trafienie"] == "niniejszego"

    def test_kwoty_slownie_dopisane(self):
        u = ustawienia("Kwoty zawsze cyframi i słownie")
        tekst, _ = zasady.napraw("Cena 1.500,00 zł. Zadatek 200 zł (dwieście złotych).", u, [])
        assert "1.500,00 zł (tysiąc pięćset złotych)" in tekst
        assert tekst.count("(dwieście złotych)") == 1
        assert zasady.sprawdz(tekst, u, [])["zgodny"]

    def test_format_daty_pomija_tytuly_ustaw(self):
        u = ustawienia("Daty zapisuj jak 03.12.2025 r.")
        tekst, _ = zasady.napraw("Wypis z dnia 3 grudnia 2025 r., ustawy z dnia 14 lutego 1991 r. Prawo o notariacie, "
                                 "postanowienie z 05.01.2026r.", u, [])
        assert "Wypis z dnia 03.12.2025 r." in tekst
        assert "ustawy z dnia 14 lutego 1991 r." in tekst
        assert "05.01.2026 r." in tekst

    def test_zakres_rodzaju(self):
        u = ustawienia("W umowach sprzedaży zawsze wnioski wieczystoksięgowe")
        assert zasady.sprawdz(AKT, u)["blokujacych"] >= 1
        r = zasady.sprawdz("Testament. Powołuję do całego spadku córkę.", u)
        assert not any(n["zasada"] == "z0" for n in r["naruszenia"])

    def test_wylaczona_zasada_nie_obowiazuje(self):
        u = ustawienia("Nigdy nie używaj słowa „niniejszy”")
        u["zasady"][0]["wlaczona"] = False
        assert zasady.sprawdz("niniejszy akt", u, [])["zgodny"]

    def test_wbudowana_mozna_wylaczyc(self):
        u = {"zasady": [], "wbudowane_wylaczone": ["luki"]}
        assert zasady.sprawdz("§ 1. Cena ?? zł", u, [])["zgodny"]


class TestEgzekwowanie:
    def test_autonaprawa_numeracji(self):
        tekst, raport = zasady.egzekwuj("§ 1. A.\n§ 3. B, o którym mowa w § 1.", {"zasady": []}, rodzaje=[])
        assert tekst.startswith("§ 1. A.\n§ 2.") and raport["zgodny"]
        assert raport["poprawki"][0]["zasada"] == "wbudowana:numeracja_paragrafow"

    def test_poprawka_modelu_przyjeta_gdy_usuwa_naruszenia(self):
        u = ustawienia("Każdy akt musi zawierać „Akt ten został odczytany”")
        model = lambda t, n: t + "\nAkt ten został odczytany."  # noqa: E731
        tekst, raport = zasady.egzekwuj("§ 1. Strony zawierają umowę.", u, popraw_modelem=model, rodzaje=[])
        assert raport["zgodny"] and raport["poprawka_modelu"]["przyjeta"]
        assert tekst.endswith("Akt ten został odczytany.")

    def test_poprawka_modelu_odrzucona_gdy_skraca_akt(self):
        u = ustawienia("Każdy akt musi zawierać „Akt ten został odczytany”")
        dlugi = "§ 1. " + "Strony zawierają umowę. " * 40
        tekst, raport = zasady.egzekwuj(dlugi, u, popraw_modelem=lambda t, n: "Akt ten został odczytany.", rodzaje=[])
        assert tekst == dlugi and not raport["zgodny"] and not raport["poprawka_modelu"]["przyjeta"]

    def test_wytyczne_sprawdza_model(self):
        u = ustawienia("Nazwiska stawających w komparycji wielkimi literami")
        uwagi = lambda t, w: [{"zasada": "z0", "fragment": "Jan Kowalski", "uwaga": "małe litery"},  # noqa: E731
                              {"zasada": "obca", "uwaga": "x"}]
        _, raport = zasady.egzekwuj("Stawił się Jan Kowalski.", u, sprawdz_modelem=uwagi, rodzaje=[])
        assert raport["blokujacych"] == 1 and raport["naruszenia"][0]["ai"]

    def test_blad_modelu_nie_blokuje_projektu(self):
        u = ustawienia("Nazwiska stawających w komparycji wielkimi literami")

        def awaria(*_):
            raise RuntimeError("bedrock")
        tekst, raport = zasady.egzekwuj("Tekst.", u, sprawdz_modelem=awaria, rodzaje=[])
        assert tekst == "Tekst." and "wytyczne_ai_blad" in raport

    def test_blok_dla_modelu(self):
        u = ustawienia("Kwoty zawsze cyframi i słownie", "W testamentach zawsze pouczenia notariusza")
        blok = zasady.blok_do_polecenia(u, ["sprzedaz"])
        assert "Kwoty zawsze" in blok and "testament" not in blok and "NIEPRZEKRACZALNA" in blok


# ---------------------------------------------------------------------------
@pytest.fixture
def dane(tmp_path, monkeypatch):
    import config
    import magazyn
    monkeypatch.setattr(config, "DANE", tmp_path)
    if "SPRAWY" in vars(config):
        monkeypatch.delattr(config, "SPRAWY")
    assert magazyn.TRYB == "lokalny"
    return tmp_path


@pytest.fixture
def klient(dane):
    import app as aplikacja
    return TestClient(aplikacja.app)


def docx(tekst: str) -> bytes:
    d = Document()
    for linia in tekst.split("\n"):
        d.add_paragraph(linia)
    bufor = io.BytesIO()
    d.save(bufor)
    return bufor.getvalue()


def akty(n=5):
    osoby = ["Piotr ZIELIŃSKI", "Adam MAJ", "Ewa LIS", "Olga BIAŁA", "Jan KOWALSKI"]
    return [("pliki", (f"akt{i}.docx", docx(AKT.replace("Jan KOWALSKI", osoby[i % 5])), "application/octet-stream"))
            for i in range(n)]


class TestStyl:
    def test_nauka_bez_danych_osobowych(self, dane):
        styl.naucz([styl.analizuj(AKT) for _ in range(3)])
        zapis = (dane / "styl.json").read_text("utf-8")
        for dana in DANE_OSOBOWE:
            assert dana not in zapis, dana
        profil = styl.wczytaj()
        assert len(profil["akty"]) == 3
        assert all(s["wystapien"] == 3 for s in profil["sformulowania"])   # te same klauzule polaczone

    def test_sugestie_z_nawykow(self, dane):
        styl.naucz([styl.analizuj(AKT) for _ in range(5)])
        teksty = [s["tekst"] for s in styl.sugestie(styl.wczytaj(), zasady.domyslne())]
        assert "Po § zawsze spacja" in teksty
        assert "W umowach sprzedaży zawsze pouczenia notariusza" in teksty

    def test_blok_stylu_dla_modelu(self, dane):
        styl.naucz([styl.analizuj(AKT) for _ in range(2)])
        blok = styl.blok_do_polecenia(styl.wczytaj(), ["sprzedaz"])
        assert "STYL KANCELARII" in blok and "{OSOBA}" in blok and "KOWALSKI" not in blok

    def test_zaznaczony_fragment_jako_wzorcowy(self, dane):
        wpis = styl.zapamietaj_sformulowanie("Notariusz pouczył Jana KOWALSKIEGO o treści art. 158 kodeksu cywilnego.")
        assert wpis["przypiete"] and wpis["czesc"] == "pouczenia"
        assert "KOWALSK" not in json.dumps(styl.wczytaj())


class TestApi:
    def test_zasada_od_zdania_do_listy(self, klient):
        podglad = klient.post("/api/personalizacja/zasady/interpretuj", json={"tekst": "Kwoty zawsze cyframi i słownie"})
        assert podglad.status_code == 200 and podglad.json()["typ"] == "kwoty_slownie"
        odp = klient.post("/api/personalizacja/zasady", json={"tekst": "Kwoty zawsze cyframi i słownie"})
        assert odp.status_code == 201
        id_ = odp.json()["zasada"]["id"]
        assert klient.post("/api/personalizacja/zasady", json={"tekst": "Kwoty zawsze cyframi i słownie"}).json()["juz_byla"]
        assert klient.put(f"/api/personalizacja/zasady/{id_}", json={"wlaczona": False}).json()["wlaczona"] is False
        stan = klient.get("/api/personalizacja").json()
        assert stan["liczby"] == {"zasad": 1, "wlaczonych": 0, "automatycznie": 0, "naprawianych": 0}
        assert klient.delete(f"/api/personalizacja/zasady/{id_}").status_code == 200
        assert klient.delete(f"/api/personalizacja/zasady/{id_}").status_code == 404

    def test_zasada_formatu_zastepuje_poprzednia(self, klient):
        klient.post("/api/personalizacja/zasady", json={"tekst": "Daty zapisuj jak 03.12.2025 r."})
        odp = klient.post("/api/personalizacja/zasady", json={"tekst": "Daty słownie, np. 3 grudnia 2025 r."}).json()
        assert odp["zastapiona"]["tekst"] == "Daty zapisuj jak 03.12.2025 r."
        assert len(klient.get("/api/personalizacja").json()["zasady"]) == 1

    def test_nauka_z_plikow_i_przyjecie_sugestii(self, klient, dane):
        odp = klient.post("/api/personalizacja/akty", files=akty(5) + [
            ("pliki", ("stary.doc", b"x", "application/msword"))])
        wynik = odp.json()
        assert odp.status_code == 200 and len(wynik["dodane"]) == 5
        assert "docx" in wynik["pominiete"][0]["powod"]
        assert not list(dane.glob("**/*.docx"))   # plikow nie przechowujemy
        stan = klient.get("/api/personalizacja").json()
        sugestia = next(s for s in stan["sugestie"] if s["tekst"] == "Po § zawsze spacja")
        przyjeta = klient.post(f"/api/personalizacja/sugestie/{sugestia['klucz']}/przyjmij")
        assert przyjeta.status_code == 201 and przyjeta.json()["zasada"]["zrodlo"] == "z_aktow"
        assert all(s["klucz"] != sugestia["klucz"] for s in klient.get("/api/personalizacja").json()["sugestie"])

    def test_sprawdz_tekst(self, klient):
        klient.post("/api/personalizacja/zasady", json={"tekst": "Zamiast „w/w” pisz „wyżej wymieniony”"})
        r = klient.post("/api/personalizacja/sprawdz", json={"tekst": "§ 1. Sprzedaje w/w lokal."}).json()
        assert r["blokujacych"] == 1 and r["poprawiony"] == "§ 1. Sprzedaje wyżej wymieniony lokal."

    def test_projekt_przechodzi_przez_zasady(self, klient, dane):
        klient.post("/api/personalizacja/zasady", json={"tekst": "Zamiast „w/w” pisz „wyżej wymieniony”"})
        klient.post("/api/personalizacja/zasady", json={"tekst": "Kwoty zawsze cyframi i słownie"})
        (dane / "sprawy" / "abc123").mkdir(parents=True)
        (dane / "sprawy" / "abc123" / "sprawa.json").write_text('{"id": "abc123", "nazwa_reczna": true}', encoding="utf-8")
        (dane / "sprawy" / "abc123" / "wzor.txt").write_text("UMOWA SPRZEDAŻY\n§ 1. Cena {{cena}}", encoding="utf-8")
        with patch("bedrock.sporzadz_projekt", return_value="UMOWA SPRZEDAŻY\n§ 1. Sprzedaje w/w lokal za 100 zł.") as sp:
            odp = klient.post("/api/sprawy/abc123/projekt", json={"pola": [], "polecenie": ""})
        assert odp.status_code == 200, odp.text
        wynik = odp.json()
        assert "Zamiast „w/w”" in sp.call_args.kwargs["personalizacja"]
        assert wynik["tekst"] == "UMOWA SPRZEDAŻY\n§ 1. Sprzedaje wyżej wymieniony lokal za 100 zł (sto złotych)."
        assert wynik["zgodnosc"]["zgodny"] and len(wynik["zgodnosc"]["poprawki"]) == 2
        assert (dane / "sprawy" / "abc123" / "projekt.txt").read_text("utf-8") == wynik["tekst"]
        assert klient.get("/api/sprawy/abc123").json()["zgodnosc"]["zgodny"]


@pytest.fixture
def u_siebie():
    import magazyn
    znacznik = magazyn.przechowywanie_var.set("u-klienta")
    yield
    magazyn.przechowywanie_var.reset(znacznik)


class TestUSiebie:
    """Kancelaria trzymajaca pliki u siebie: zasady i styl leza w jej folderze,
    przegladarka przysyla je z kazdym zadaniem, serwer niczego nie zapisuje."""

    def test_bez_plikow_czytelna_odmowa(self, klient, u_siebie):
        odp = klient.post("/api/personalizacja/zasady", json={"tekst": "Po § zawsze spacja"})
        assert odp.status_code == 409 and "folder" in odp.json()["detail"]

    def test_zasady_wracaja_do_przegladarki_a_serwer_nic_nie_zapisuje(self, klient, dane, u_siebie):
        pliki = {"zasady": None, "styl": None}
        odp = klient.post("/api/personalizacja/zasady", json={"tekst": "Po § zawsze spacja", "pliki_kancelarii": pliki})
        assert odp.status_code == 201
        pliki = odp.json()["pliki_kancelarii"]
        assert [z["tekst"] for z in pliki["zasady"]["zasady"]] == ["Po § zawsze spacja"]
        id_ = pliki["zasady"]["zasady"][0]["id"]

        odp = klient.put(f"/api/personalizacja/zasady/{id_}", json={"wlaczona": False, "pliki_kancelarii": pliki})
        pliki = odp.json()["pliki_kancelarii"]
        assert pliki["zasady"]["zasady"][0]["wlaczona"] is False

        stan = klient.post("/api/personalizacja/stan", json={"pliki_kancelarii": pliki}).json()
        assert stan["u_klienta"] and stan["liczby"]["zasad"] == 1

        odp = klient.request("DELETE", f"/api/personalizacja/zasady/{id_}", json={"pliki_kancelarii": pliki})
        assert odp.json()["pliki_kancelarii"]["zasady"]["zasady"] == []
        assert not list(dane.glob("**/*.json"))           # na serwerze nic

    def test_nauka_stylu_u_siebie(self, klient, dane, u_siebie):
        odp = klient.post("/api/personalizacja/akty", files=akty(3),
                          data={"pliki_kancelarii": json.dumps({"zasady": None, "styl": None})})
        assert odp.status_code == 200, odp.text
        styl_u_siebie = odp.json()["pliki_kancelarii"]["styl"]
        assert len(styl_u_siebie["akty"]) == 3
        for dana in DANE_OSOBOWE:
            assert dana not in json.dumps(styl_u_siebie, ensure_ascii=False), dana
        assert not list(dane.glob("**/*.json")) and not list(dane.glob("**/*.docx"))

    def test_uszkodzony_plik_z_dysku_nie_wywraca(self, klient, u_siebie):
        pliki = {"zasady": {"zasady": [{"tekst": "Kwoty zawsze cyframi i słownie", "id": "z1", "poziom": "ostrzega"},
                                       {"smieci": 1}, "x"]},
                 "styl": {"sformulowania": [{"id": 5}], "nawyki": {"daty": {"a": "b"}}}}
        stan = klient.post("/api/personalizacja/stan", json={"pliki_kancelarii": pliki}).json()
        assert [(z["typ"], z["poziom"]) for z in stan["zasady"]] == [("kwoty_slownie", "ostrzega")]

    def test_projekt_sprawdzony_zasadami_z_folderu(self, klient, dane, u_siebie):
        pliki = klient.post("/api/personalizacja/zasady", json={
            "tekst": "Zamiast „w/w” pisz „wyżej wymieniony”", "pliki_kancelarii": {}}).json()["pliki_kancelarii"]
        with patch("bedrock.sporzadz_projekt", return_value="§ 1. Sprzedaje w/w lokal.") as sp:
            odp = klient.post("/api/projekt", files={"wzor": ("wzor.txt", "§ 1. {{x}}".encode(), "text/plain")},
                              data={"pliki_kancelarii": json.dumps(pliki)})
        assert odp.status_code == 200, odp.text
        assert odp.json()["tekst"] == "§ 1. Sprzedaje wyżej wymieniony lokal."
        assert "Zamiast „w/w”" in sp.call_args.kwargs["personalizacja"]
        assert not list(dane.glob("**/*.json"))

    def test_chmura_pomija_pliki_z_przegladarki(self, klient):
        obce = {"zasady": {"zasady": [{"tekst": "Po § zawsze spacja"}]}}
        stan = klient.post("/api/personalizacja/stan", json={"pliki_kancelarii": obce}).json()
        assert stan["zasady"] == [] and "pliki_kancelarii" not in stan
