"""Baza osob i kalendarz. Dane zmyslone (zestaw Sobczak/Pawlak)."""
import importlib
import json

import pytest

import kalendarz
import osoby
from conftest import z_suma_kontrolna
from test_magazyn import AtrapaS3

PESEL_SOBCZAK = "85031512337"
PESEL_PAWLAK = z_suma_kontrolna("9007120145")
PESEL_PAWLAK_EWA = z_suma_kontrolna("9211030286")


@pytest.fixture
def dane(tmp_path, monkeypatch):
    # Kancelaria "lokalna": sprawy w DANE/sprawy, telefony w DANE/osoby.json.
    # Inne testy przeladowuja config, wiec osoby moze trzymac stary modul.
    import config
    monkeypatch.setattr(osoby, "config", config)
    monkeypatch.setattr(config, "DANE", tmp_path)
    # monkeypatch.setattr(config, "SPRAWY", ...) w innych testach zostawia po
    # sobie zwykly atrybut SPRAWY = prawdziwe dane/sprawy; bez niego wraca
    # wyliczanie z DANE.
    if "SPRAWY" in vars(config):
        monkeypatch.delattr(config, "SPRAWY")
    sprawy = config.SPRAWY
    assert sprawy.is_relative_to(tmp_path)
    osoby._PAMIEC.clear()

    def sprawa(identyfikator, pola):
        (sprawy / identyfikator).mkdir()
        (sprawy / identyfikator / "odczyt.json").write_text(json.dumps({"pola": pola}), "utf-8")
        return {"id": identyfikator, "nazwa": "sprawa " + identyfikator}
    return sprawa


class TestOsobyZeSprawy:
    def test_legenda_i_pesele(self):
        pola = [{"nazwa": "aaa: zbywca", "wartosc": "TOMASZ PIOTR SOBCZAK"},
                {"nazwa": "aa2: zbywcy", "wartosc": "Tomasza Piotra Sobczaka"},
                {"nazwa": "bbb: nabywcy", "wartosc": "Grzegorz Pawlak"},
                {"nazwa": "+ PESEL zbywcy", "wartosc": PESEL_SOBCZAK},
                {"nazwa": "+ PESEL nabywcy", "wartosc": PESEL_PAWLAK}]
        assert osoby.osoby_ze_sprawy(pola) == [
            {"imie_nazwisko": "Tomasz Piotr Sobczak", "pesel": PESEL_SOBCZAK, "rola": "zbywca"},
            {"imie_nazwisko": "Grzegorz Pawlak", "pesel": PESEL_PAWLAK, "rola": "nabywca"},
        ]

    def test_malzonkowie(self):
        pola = [{"nazwa": "bbb: nabywcy", "wartosc": "Grzegorz i Ewa małżonkowie Pawlak"}]
        assert [o["imie_nazwisko"] for o in osoby.osoby_ze_sprawy(pola)] == ["Grzegorz Pawlak", "Ewa Pawlak"]

    def test_bledny_pesel_pominiety(self):
        pola = [{"nazwa": "aaa: zbywca", "wartosc": "Tomasz Sobczak"},
                {"nazwa": "+ PESEL zbywcy", "wartosc": "85031512338"}]
        assert osoby.osoby_ze_sprawy(pola)[0]["pesel"] == ""

    def test_pola_bez_osob(self):
        pola = [{"nazwa": "ccc: numer działki", "wartosc": "12/3"},
                {"nazwa": "+ imiona rodzicow zbywcy", "wartosc": "Stanisław, Halina"},
                {"nazwa": "??110: na rzecz …, syna…, PESEL __", "wartosc": PESEL_SOBCZAK}]
        assert osoby.osoby_ze_sprawy(pola) == []


class TestTelefon:
    @pytest.mark.parametrize("wejscie,wynik", [
        ("600100200", "+48 600 100 200"),
        ("600-100-200", "+48 600 100 200"),
        ("+48 600 100 200", "+48 600 100 200"),
        ("0049301234567", "+49301234567"),
        ("", ""),
    ])
    def test_poprawne(self, wejscie, wynik):
        assert osoby.telefon(wejscie) == wynik

    @pytest.mark.parametrize("wejscie", ["12345", "telefon", "60010020"])
    def test_bledne(self, wejscie):
        with pytest.raises(ValueError):
            osoby.telefon(wejscie)


class TestBaza:
    def test_ta_sama_osoba_w_dwoch_sprawach(self, dane):
        a = dane("aaa111", [{"nazwa": "aaa: zbywca", "wartosc": "Tomasz Sobczak"},
                            {"nazwa": "+ PESEL zbywcy", "wartosc": PESEL_SOBCZAK}])
        b = dane("bbb222", [{"nazwa": "bbb: nabywcy", "wartosc": "Tomasz Sobczak"},
                            {"nazwa": "+ PESEL nabywcy", "wartosc": PESEL_SOBCZAK},
                            {"nazwa": "aaa: zbywca", "wartosc": "Grzegorz Pawlak"}])
        wynik = osoby.wszystkie([a, b])
        sobczak = next(o for o in wynik if o["imie_nazwisko"] == "Tomasz Sobczak")
        assert [(s["id"], s["rola"]) for s in sobczak["sprawy"]] == [("aaa111", "zbywca"), ("bbb222", "nabywca")]
        assert len(wynik) == 2

    def test_bez_pelnego_peselu_w_wyniku_i_pliku(self, dane):
        a = dane("aaa111", [{"nazwa": "aaa: zbywca", "wartosc": "Tomasz Sobczak"},
                            {"nazwa": "+ PESEL zbywcy", "wartosc": PESEL_SOBCZAK}])
        osoba = osoby.wszystkie([a])[0]
        osoby.ustaw_telefon(osoba["id"], "600100200")
        assert PESEL_SOBCZAK not in json.dumps(osoby.wszystkie([a]))
        assert PESEL_SOBCZAK not in (osoby.config.DANE / "osoby.json").read_text("utf-8")
        assert osoby.wszystkie([a])[0]["telefon"] == "+48 600 100 200"

    def test_telefon_zostaje_po_odczytaniu_peselu(self, dane):
        a = dane("aaa111", [{"nazwa": "aaa: zbywca", "wartosc": "Tomasz Sobczak"}])
        osoby.ustaw_telefon(osoby.wszystkie([a])[0]["id"], "600100200")
        b = dane("bbb222", [{"nazwa": "aaa: zbywca", "wartosc": "Tomasz Sobczak"},
                            {"nazwa": "+ PESEL zbywcy", "wartosc": PESEL_SOBCZAK}])
        wynik = osoby.wszystkie([a, b])
        assert len(wynik) == 1
        assert wynik[0]["telefon"] == "+48 600 100 200"
        assert len(wynik[0]["sprawy"]) == 2

    def test_drugie_imie_tylko_w_jednej_sprawie(self, dane):
        a = dane("aaa111", [{"nazwa": "aaa: zbywca", "wartosc": "Tomasz Sobczak"}])
        b = dane("bbb222", [{"nazwa": "bbb: nabywcy", "wartosc": "Tomasz Piotr Sobczak"},
                            {"nazwa": "+ PESEL nabywcy", "wartosc": PESEL_SOBCZAK}])
        c = dane("ccc333", [{"nazwa": "aaa: zbywca", "wartosc": "Tomasz Piotr Sobczak"}])
        wynik = osoby.wszystkie([a, b, c])
        assert len(wynik) == 1
        assert wynik[0]["imie_nazwisko"] == "Tomasz Piotr Sobczak"
        assert wynik[0]["pesel"] == PESEL_SOBCZAK[:4] + "*******"
        assert len(wynik[0]["sprawy"]) == 3

    def test_bez_peselu_laczy_sie_z_pelniejszym_imieniem(self, dane):
        a = dane("aaa111", [{"nazwa": "aaa: zbywca", "wartosc": "Grzegorz Pawlak"}])
        b = dane("bbb222", [{"nazwa": "bbb: nabywcy", "wartosc": "Grzegorz Adam Pawlak"},
                            {"nazwa": "aaa: zbywca", "wartosc": "Ewa Pawlak"}])
        assert sorted(o["imie_nazwisko"] for o in osoby.wszystkie([a, b])) == ["Ewa Pawlak", "Grzegorz Adam Pawlak"]

    def test_dwie_osoby_z_peselem_nie_zgadujemy(self, dane):
        a = dane("aaa111", [{"nazwa": "aaa: zbywca", "wartosc": "Grzegorz Pawlak"},
                            {"nazwa": "+ PESEL zbywcy", "wartosc": PESEL_PAWLAK}])
        b = dane("bbb222", [{"nazwa": "aaa: zbywca", "wartosc": "Grzegorz Pawlak"},
                            {"nazwa": "+ PESEL zbywcy", "wartosc": PESEL_PAWLAK_EWA}])
        c = dane("ccc333", [{"nazwa": "aaa: zbywca", "wartosc": "Grzegorz Pawlak"}])
        assert len(osoby.wszystkie([a, b, c])) == 3

    def test_osoba_reczna(self, dane):
        identyfikator = osoby.dodaj_reczna("Ewa Pawlak", "")
        assert osoby.wszystkie([])[0] == {"id": identyfikator, "imie_nazwisko": "Ewa Pawlak", "pesel": "",
                                          "telefon": "", "sprawy": [], "reczna": True}
        assert osoby.usun_reczna(identyfikator)
        assert osoby.wszystkie([]) == []


class TestKalendarz:
    def test_dodaj_zmien_usun(self, dane):
        wpis = kalendarz.dodaj({"data": "2026-11-03", "godzina": "10:30", "sprawa": "aaa111"})
        kalendarz.dodaj({"data": "2026-11-03", "godzina": "09:00", "tytul": "Spotkanie"})
        assert [w["godzina"] for w in kalendarz.lista()] == ["09:00", "10:30"]
        with pytest.raises(ValueError, match="zajęte"):
            kalendarz.dodaj({"data": "2026-11-03", "godzina": "08:30", "koniec": "09:30", "tytul": "x"})
        kalendarz.zmien(wpis["id"], {"data": "2026-11-04", "godzina": "", "tytul": "Akt", "sprawa": "aaa111"})
        assert kalendarz.lista()[-1]["data"] == "2026-11-04"
        assert kalendarz.usun(wpis["id"])
        assert len(kalendarz.lista()) == 1

    def test_rezerwacja_godzin(self, dane):
        wpis = kalendarz.dodaj({"data": "2026-11-03", "godzina": "08:30", "koniec": "09:30",
                                "rodzaj": "sprzedaż", "uczestnicy": "Sobczak, Pawlak", "telefon": "600 100 200"})
        assert wpis["rodzaj"] == "sprzedaż" and wpis["uczestnicy"] == "Sobczak, Pawlak"
        kalendarz.dodaj({"data": "2026-11-03", "godzina": "09:30", "koniec": "10:00", "rodzaj": "testament"})
        kalendarz.dodaj({"data": "2026-11-04", "godzina": "09:00", "koniec": "10:00", "rodzaj": "testament"})
        with pytest.raises(ValueError, match="zajęte"):
            kalendarz.dodaj({"data": "2026-11-03", "godzina": "09:00", "koniec": "09:30", "rodzaj": "darowizna"})
        with pytest.raises(ValueError, match="zajęte"):
            kalendarz.zmien(wpis["id"], {**wpis, "koniec": "10:00"})
        kalendarz.zmien(wpis["id"], {**wpis, "godzina": "08:00"})
        assert len(kalendarz.lista()) == 3

    def test_rodzaj_inne_wymaga_opisu(self, dane):
        with pytest.raises(ValueError, match="jaka to czynność"):
            kalendarz.dodaj({"data": "2026-11-03", "rodzaj": "inne"})
        wpis = kalendarz.dodaj({"data": "2026-11-03", "rodzaj": "inne", "rodzaj_inny": "umowa dożywocia"})
        assert wpis["rodzaj_inny"] == "umowa dożywocia"
        assert kalendarz.dodaj({"data": "2026-11-03", "rodzaj": "sprzedaż", "rodzaj_inny": "x"})["rodzaj_inny"] == ""

    @pytest.mark.parametrize("dane_wpisu", [
        {"data": "3.11.2026", "tytul": "x"},
        {"data": "2026-11-03", "godzina": "09:00", "koniec": "08:30", "tytul": "x"},
        {"data": "2026-11-03", "koniec": "09:00", "tytul": "x"},
        {"data": "2026-11-03", "rodzaj": "kupno"},
        {"data": "2026-11-03", "godzina": "25:00", "tytul": "x"},
        {"data": "2026-11-03"},
        {"data": "2026-11-03", "sprawa": "../etc"},
    ])
    def test_bledne(self, dane, dane_wpisu):
        with pytest.raises(ValueError):
            kalendarz.dodaj(dane_wpisu)

    def test_usunieta_sprawa_znika_z_terminu(self, dane):
        wpis = kalendarz.dodaj({"data": "2026-11-03", "tytul": "Akt", "sprawa": "aaa111"})
        kalendarz.usun_sprawe("aaa111")
        assert next(w for w in kalendarz.lista() if w["id"] == wpis["id"])["sprawa"] == ""


# --- notarai: S3, kilka kopii aplikacji, kilka kancelarii ---------------------


class _Warunek(Exception):
    """Jak botocore ClientError przy niespelnionym If-Match / If-None-Match."""

    def __init__(self):
        super().__init__("PreconditionFailed")
        self.response = {"Error": {"Code": "PreconditionFailed"}}


class AtrapaWarunkowa(AtrapaS3):
    """S3 z zapisem warunkowym i ETagiem w get_object."""

    def __init__(self):
        super().__init__()
        self.przed_zapisem = None   # wstrzykniecie "drugiej kopii aplikacji"

    def get_object(self, Bucket, Key):
        odp = super().get_object(Bucket, Key)
        odp["ETag"] = self.head_object(Bucket, Key)["ETag"]
        return odp

    def put_object(self, Bucket, Key, Body, **kw):
        if self.przed_zapisem:
            akcja, self.przed_zapisem = self.przed_zapisem, None
            akcja()
        if "IfNoneMatch" in kw and Key in self.obiekty:
            raise _Warunek()
        if "IfMatch" in kw and (Key not in self.obiekty
                                or self.head_object(Bucket, Key)["ETag"] != kw["IfMatch"]):
            raise _Warunek()
        return super().put_object(Bucket, Key, Body, **kw)


@pytest.fixture
def s3(tmp_path, monkeypatch):
    monkeypatch.setenv("PIECZAPP_MAGAZYN", "s3")
    monkeypatch.setenv("PIECZAPP_S3_BUCKET", "testowy-bucket")
    import magazyn
    importlib.reload(magazyn)
    atrapa = AtrapaWarunkowa()
    monkeypatch.setattr(magazyn, "_s3", atrapa)
    import config
    monkeypatch.setattr(osoby, "config", config)
    monkeypatch.setattr(config, "DANE", tmp_path)
    # monkeypatch.setattr(config, "SPRAWY", ...) w innych testach zostawia po
    # sobie zwykly atrybut SPRAWY = prawdziwe dane/sprawy; bez niego wraca
    # wyliczanie z DANE.
    if "SPRAWY" in vars(config):
        monkeypatch.delattr(config, "SPRAWY")
    znacznik = magazyn.kancelaria_var.set("kancelaria-a")
    yield magazyn, atrapa
    magazyn.kancelaria_var.reset(znacznik)
    monkeypatch.setenv("PIECZAPP_MAGAZYN", "lokalny")
    importlib.reload(magazyn)


class TestS3:
    def test_plik_pod_prefiksem_kancelarii_i_szyfrowany(self, s3):
        magazyn, atrapa = s3
        kalendarz.dodaj({"data": "2026-11-03", "tytul": "Akt"})
        osoby.dodaj_reczna("Ewa Pawlak", "600100200")
        assert set(atrapa.obiekty) == {"kancelarie/kancelaria-a/kalendarz.json",
                                       "kancelarie/kancelaria-a/osoby.json"}
        assert all(atrapa.szyfrowanie.values())

    def test_druga_kancelaria_nie_widzi_terminow(self, s3):
        magazyn, _ = s3
        kalendarz.dodaj({"data": "2026-11-03", "tytul": "Akt"})
        znacznik = magazyn.kancelaria_var.set("kancelaria-b")
        try:
            assert kalendarz.lista() == []
            assert osoby.wszystkie([]) == []
        finally:
            magazyn.kancelaria_var.reset(znacznik)

    def test_rownoczesny_zapis_drugiej_kopii_nie_ginie(self, s3):
        """Druga kopia aplikacji zapisuje miedzy naszym odczytem a zapisem."""
        _, atrapa = s3
        kalendarz.dodaj({"data": "2026-11-03", "tytul": "Pierwszy"})
        atrapa.przed_zapisem = lambda: kalendarz.dodaj({"data": "2026-11-04", "tytul": "Z drugiej kopii"})
        kalendarz.dodaj({"data": "2026-11-05", "tytul": "Nasz"})
        assert [w["tytul"] for w in kalendarz.lista()] == ["Pierwszy", "Z drugiej kopii", "Nasz"]

    def test_pierwszy_zapis_nie_nadpisuje_cudzego(self, s3):
        _, atrapa = s3
        atrapa.przed_zapisem = lambda: osoby.dodaj_reczna("Ewa Pawlak")
        osoby.dodaj_reczna("Grzegorz Pawlak")
        assert sorted(o["imie_nazwisko"] for o in osoby.wszystkie([])) == ["Ewa Pawlak", "Grzegorz Pawlak"]

    def test_usuniecie_kancelarii_kasuje_kalendarz_i_telefony(self, s3, tmp_path):
        magazyn, atrapa = s3
        kalendarz.dodaj({"data": "2026-11-03", "tytul": "Akt"})
        osoby.dodaj_reczna("Ewa Pawlak", "600100200")
        magazyn.usun_kancelarie("kancelaria-a", tmp_path)
        assert atrapa.obiekty == {}

    def test_u_klienta_nic_nie_zapisuje(self, s3):
        magazyn, atrapa = s3
        znacznik = magazyn.przechowywanie_var.set("u-klienta")
        try:
            with pytest.raises(RuntimeError, match="u siebie"):
                kalendarz.dodaj({"data": "2026-11-03", "tytul": "Akt"})
        finally:
            magazyn.przechowywanie_var.reset(znacznik)
        assert atrapa.obiekty == {}


def test_api_odmawia_kancelarii_u_klienta(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import app as aplikacja
    import config
    import magazyn
    monkeypatch.setattr(config, "DANE", tmp_path)
    znacznik = magazyn.przechowywanie_var.set("u-klienta")
    try:
        klient = TestClient(aplikacja.app)
        assert klient.get("/api/kalendarz").status_code == 409
        assert klient.post("/api/osoby", json={"imie_nazwisko": "Ewa Pawlak"}).status_code == 409
    finally:
        magazyn.przechowywanie_var.reset(znacznik)
