"""Nazwa sprawy z nazwisk stron. Dane zmyslone albo z nazw plikow testowych."""
from nazwy import nazwa_sprawy, nazwiska_z_plikow, nazwiska_z_wartosci


class TestWartosci:
    def test_dzial_ii_z_rodzicami_i_peselem(self):
        assert nazwiska_z_wartosci("JAN ADAM KOWALSKI, STANISŁAW, HALINA, 44051401359") == ["Kowalski"]

    def test_malzonkowie(self):
        assert nazwiska_z_wartosci("Marian i Anna małżonkowie Nowak") == ["Nowak"]

    def test_dwie_osoby(self):
        assert nazwiska_z_wartosci("Jan Kowalski i Anna Nowak-Wiśniewska") == ["Kowalski", "Nowak-Wiśniewska"]

    def test_samo_nazwisko(self):
        assert nazwiska_z_wartosci("PAWLAK", tylko_nazwisko=True) == ["Pawlak"]


class TestPliki:
    def test_konwencja_kancelarii(self):
        assert nazwiska_z_plikow(["kw 2.pdf", "Sobczak Tomasz - Pawlak Grzegorz - sprzedaż RI - Zalesie.pdf"]) == ["Sobczak", "Pawlak"]

    def test_brak_konwencji(self):
        assert nazwiska_z_plikow(["skan001.pdf", "kw 3.pdf"]) == []


class TestNazwaSprawy:
    def test_pole_stale_ma_pierwszenstwo(self):
        pola = [{"nazwa": "aaa: zbywca", "wartosc": "Jan Kowalski"},
                {"nazwa": "STALE: nazwiska stron czynnosci", "wartosc": "Sobczak - Pawlak"}]
        assert nazwa_sprawy(pola) == "Sobczak – Pawlak"

    def test_zbywca_przed_nabywca_niezaleznie_od_kolejnosci(self):
        pola = [{"nazwa": "+ Nazwisko nabywcy", "wartosc": "PAWLAK"},
                {"nazwa": "aaa: zbywca", "wartosc": "TOMASZ PIOTR SOBCZAK"}]
        assert nazwa_sprawy(pola) == "Sobczak – Pawlak"

    def test_pomija_imiona_rodzicow_i_pesel(self):
        pola = [{"nazwa": "aaa: zbywca", "wartosc": "Jan Kowalski"},
                {"nazwa": "+ Imię ojca nabywcy", "wartosc": "Bogdan"},
                {"nazwa": "+ PESEL nabywcy", "wartosc": "44051401359"},
                {"nazwa": "+ Nazwisko nabywcy", "wartosc": "Nowak"}]
        assert nazwa_sprawy(pola) == "Kowalski – Nowak"

    def test_luki_wzoru_ignorowane(self):
        pola = [{"nazwa": "??3: zbywca __", "wartosc": "Coś Innego"}]
        assert nazwa_sprawy(pola, ["Sobczak Tomasz - Pawlak Grzegorz - sprzedaż.pdf"]) == "Sobczak – Pawlak"

    def test_bez_danych(self):
        assert nazwa_sprawy([], ["skan.pdf"]) is None

    def test_duplikaty_i_limit(self):
        pola = [{"nazwa": "aaa: zbywca", "wartosc": "Jan Kowalski"}, {"nazwa": "aa2: zbywcy", "wartosc": "Jana Kowalski"},
                {"nazwa": "bbb: nabywcy", "wartosc": "A Nowak i B Lis i C Kot i D Sowa"}]
        assert nazwa_sprawy(pola) == "Kowalski – Nowak – Lis"


class TestPrawdziweKsztaltyPol:
    """Ksztalt pol z prawdziwego odczytu (wartosci zmienione)."""
    POLA = [
        {"nazwa": "aaa: zbywca", "wartosc": "JAN ADAM KOWALSKI"},
        {"nazwa": "bbb: nabywcy", "wartosc": "PIOTR NOWAK"},
        {"nazwa": "bb2: nabywcom", "wartosc": "Piotrowi Nowakowi"},
        {"nazwa": "aa2: zbywcy", "wartosc": "Jana Kowalskiego"},
        {"nazwa": "STALE: KW gospodarstwa nabywcy (z oswiadczenia)", "wartosc": "KW 12345"},
        {"nazwa": "STALE: dokument o wykszt. rolniczym nabywcy", "wartosc": "Duplikat swiadectwa Szkoly Zawodowej w Zalesiu"},
        {"nazwa": "STALE: imiona rodzicow nabywcy", "wartosc": "Bogdan, Leontyna"},
        {"nazwa": "+ numer dowodu osobistego zbywcy", "wartosc": "ABC123456"},
        {"nazwa": "+ podstawa wpisu wlasnosci zbywcy w KW", "wartosc": "UMOWA DAROWIZNY, 1234/2001"},
    ]

    def test_tylko_nazwiska_stron(self):
        assert nazwa_sprawy(self.POLA) == "Kowalski – Nowak"


class TestRdzen:
    def test_odmiany(self):
        from nazwy import _ten_sam_rdzen
        assert _ten_sam_rdzen("Sobczak", "Sobczaka") and _ten_sam_rdzen("Pawlak", "Pawlakowi")
        assert _ten_sam_rdzen("Kowalska", "Kowalskiej") and not _ten_sam_rdzen("Nowak", "Nowicki")
