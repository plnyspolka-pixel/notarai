"""KRZ - testy na atrapie strony. Zero polaczen z portalem."""
from pathlib import Path

import pytest

import config
import krz
import rejestry


class Atrapa:
    def __init__(self, teksty):
        self.teksty, self.kroki, self.i = teksty, [], 0
    def otworz(self): self.kroki.append("otworz")
    def wybierz_zakladke(self, n): self.kroki.append("zakladka:" + n[:20])
    def wpisz_identyfikator(self, w): self.kroki.append("wpisz")
    def wyszukaj(self): self.kroki.append("wyszukaj")
    def wyczysc(self): self.kroki.append("wyczysc")
    def tekst_wyniku(self):
        t = self.teksty[self.i]; self.i += 1; return t
    def zrzut(self, cel: Path): cel.write_bytes(b"png"); self.kroki.append("zrzut")


@pytest.fixture(autouse=True)
def szybko(monkeypatch, tmp_path):
    monkeypatch.setattr(krz, "ODSTEP_S", 0)
    monkeypatch.setattr(config, "SPRAWY", tmp_path)
    (tmp_path / "abc123").mkdir()


STRONA_BRAK = ("[1/1]Przejdź do kryteriów wyszukiwania Podmiot niebędący osobą fizyczną Osoba fizyczna prowadząca "
    "działalność gospodarczą Osoba fizyczna nieprowadząca działalności gospodarczej Sygnatura Poprzednia zakładka 2 / 4 "
    "Następna zakładka INFORMACJA O KRYTERIACH WYSZUKIWANIA W polach wyszukiwania podaj jedno z kryteriów. System "
    "wyszukuje podmioty wg danych, które zostały ujawnione w rejestrze w trakcie postępowania. Identyfikator Wyczyść "
    "Wyszukaj Nie zostały znalezione żadne pozycje dla podanych kryteriów wyszukiwania.")
STRONA_BEZ_KOMUNIKATU = STRONA_BRAK.replace("Nie zostały znalezione żadne pozycje dla podanych kryteriów wyszukiwania.", "")


class TestRozpoznajPrawdziwaStrona:
    """Tekst z prawdziwej strony KRZ (17.09.2026), zapytanie testowe bez wynikow."""
    def test_komunikat_portalu_to_brak(self):
        assert krz.rozpoznaj(STRONA_BRAK)[0] == "brak_wpisu"
    def test_nazwy_zakladek_nie_daja_falszywego_wpisu(self):
        assert krz.rozpoznaj(STRONA_BEZ_KOMUNIKATU)[0] == "blad"


class TestRozpoznaj:
    def test_brak(self):
        assert krz.rozpoznaj("Wyniki wyszukiwania: Brak wyników")[0] == "brak_wpisu"
    def test_wpis(self):
        assert krz.rozpoznaj("Sygnatura KR1K/GU/12/2025 upadłość konsumencka")[0] == "wpis"
    def test_nieznane(self):
        assert krz.rozpoznaj("Proszę czekać...")[0] == "blad"


class TestSprawdzOsobe:
    def test_dwa_zapytania_i_zrzuty(self, tmp_path):
        s = Atrapa(["Brak wyników", "Brak wyników"])
        w = krz.sprawdz_osobe(s, "440-514-01359", "abc123", "zbywca")
        assert w.rejestr == "KRZ" and w.status == "brak_wpisu" and w.zapytanie == "*******1359"
        assert s.kroki.count("wyszukaj") == 2 and s.kroki.count("zrzut") == 2
        assert [k for k in s.kroki if k.startswith("zakladka")] == ["zakladka:Osoba fizyczna prowa", "zakladka:Osoba fizyczna niepr"]
        pliki = list((tmp_path / "abc123" / "sprawdzenia").glob("krz_*.png"))
        assert len(pliki) == 2 and all("1359" in p.name and "44051401359" not in p.name for p in pliki)
        assert "44051401359" not in w.szczegoly and w.szczegoly.startswith("zbywca - ")

    def test_wpis_w_jednej_zakladce_daje_wpis(self):
        w = krz.sprawdz_osobe(Atrapa(["Brak wyników", "Sygnatura X upadłość"]), "44051401359", "abc123")
        assert w.status == "wpis"

    def test_nierozpoznany_daje_blad(self):
        w = krz.sprawdz_osobe(Atrapa(["Brak wyników", "???"]), "44051401359", "abc123")
        assert w.status == "blad"

    def test_zly_pesel(self):
        with pytest.raises(ValueError):
            krz.sprawdz_osobe(Atrapa([]), "123", "abc123")

    def test_wpis_audytowy_zapisuje_sie(self):
        w = krz.sprawdz_osobe(Atrapa(["Brak wyników", "Brak wyników"]), "44051401359", "abc123")
        rejestry.zapisz_sprawdzenie("abc123", w)
        assert rejestry.wczytaj_sprawdzenia("abc123")[0]["rejestr"] == "KRZ"


class TestApi:
    @pytest.fixture
    def klient(self):
        from fastapi.testclient import TestClient
        import app as aplikacja
        return TestClient(aplikacja.app)

    def test_wymaga_potwierdzenia(self, klient):
        assert klient.post("/api/sprawy/abc123/krz", json={"osoby": [{"pesel": "44051401359"}]}).status_code == 400

    def test_brak_przegladarki_409(self, klient, monkeypatch):
        import formularze.silnik as silnik
        def brak(): raise RuntimeError("Nie mozna polaczyc sie z przegladarka")
        monkeypatch.setattr(silnik, "aktywna_strona", brak)
        odp = klient.post("/api/sprawy/abc123/krz", json={"osoby": [{"pesel": "44051401359"}], "potwierdzam": True})
        assert odp.status_code == 409

    def test_wiele_osob_jeden_przebieg(self, klient, monkeypatch):
        import formularze.silnik as silnik
        class PW:
            def stop(self): pass
        class S:
            _p = object()
        monkeypatch.setattr(silnik, "aktywna_strona", lambda: (PW(), S()))
        wyniki = iter(["Brak wyników"] * 4)
        monkeypatch.setattr(krz, "StronaPlaywright", lambda p: Atrapa([next(wyniki) for _ in range(2)]))
        odp = klient.post("/api/sprawy/abc123/krz", json={
            "osoby": [{"pesel": "44051401359", "etykieta": "zbywca"}, {"pesel": "02070803628", "etykieta": "nabywca"}],
            "potwierdzam": True})
        assert odp.status_code == 200
        assert [w["status"] for w in odp.json()] == ["brak_wpisu", "brak_wpisu"]
        assert odp.json()[1]["szczegoly"].startswith("nabywca - ")

    def test_plik_zrzutu_nazwa_walidowana(self, klient):
        assert klient.get("/api/sprawy/abc123/sprawdzenia/pliki/..%2Fsprawa.json").status_code in (400, 404)
