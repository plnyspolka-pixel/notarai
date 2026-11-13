"""Nazwa sprawy z nazwisk stron. Dane zmyslone albo z nazw plikow testowych."""
from nazwy import (DOMYSLNY_WZOR_NAZWY, MAX_DLUGOSC_NAZWY, bezpieczna_nazwa_pliku, czynnosc_z_rodzajow,
                   miejscowosc_z_pol, nazwa_pliku, nazwa_sprawy, nazwiska_stron, nazwiska_z_plikow,
                   nazwiska_z_wartosci, nieznane_pola_wzoru, przyklad_nazwy)


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


class TestNazwiskaStron:
    def test_pole_stale_pierwszy_zbywa(self):
        pola = [{"nazwa": "STALE: nazwiska stron czynnosci", "wartosc": "Sobczak - Pawlak - Nowak"}]
        assert nazwiska_stron(pola) == {"zbywcy": ["Sobczak"], "nabywcy": ["Pawlak", "Nowak"], "inni": []}

    def test_z_pol_rol(self):
        pola = [{"nazwa": "bbb: nabywcy", "wartosc": "Marian i Anna małżonkowie Nowak"},
                {"nazwa": "aaa: zbywca", "wartosc": "TOMASZ PIOTR SOBCZAK, STANISŁAW, HALINA, 85031512337"}]
        assert nazwiska_stron(pola) == {"zbywcy": ["Sobczak"], "nabywcy": ["Nowak"], "inni": []}

    def test_z_plikow_gdy_brak_pol(self):
        assert nazwiska_stron([], ["Sobczak Tomasz - Pawlak Grzegorz - sprzedaż RI - Zalesie.pdf"]) == \
            {"zbywcy": ["Sobczak"], "nabywcy": ["Pawlak"], "inni": []}


class TestNazwaPliku:
    POLA = [{"nazwa": "STALE: nazwiska stron czynnosci - SAME nazwiska", "wartosc": "Sobczak - Pawlak"},
            {"nazwa": "STALE: miejscowosc polozenia nieruchomosci - obreb", "wartosc": "Zalesie: dz. 12/3, 14\nBorki: 5"}]

    def test_domyslny_wzor_jak_w_kancelarii(self):
        assert nazwa_pliku(DOMYSLNY_WZOR_NAZWY, self.POLA, rodzaje=["sprzedaz_rolna"]) == "Sobczak - Pawlak - sprzedaż - Zalesie"

    def test_puste_pole_znika_z_myslnikiem(self):
        assert nazwa_pliku(DOMYSLNY_WZOR_NAZWY, self.POLA, rodzaje=["inny"]) == "Sobczak - Pawlak - Zalesie"
        tylko_zbywca = [{"nazwa": "aaa: zbywca", "wartosc": "Jan Kowalski"}]
        assert nazwa_pliku(DOMYSLNY_WZOR_NAZWY, tylko_zbywca) == "Kowalski"

    def test_bez_danych_numer_sprawy(self):
        assert nazwa_pliku(DOMYSLNY_WZOR_NAZWY, [], identyfikator="abc123") == "projekt-abc123"
        assert nazwa_pliku(DOMYSLNY_WZOR_NAZWY, []) == "projekt"

    def test_inne_pola_i_wlasny_separator(self):
        wynik = nazwa_pliku("{sygnatura}_{data}_{nazwa}", self.POLA, sygnatura="A 123/2026",
                            utworzono="2026-11-13T10:00:00", nazwa="Sobczak – Pawlak")
        assert wynik == "A 123-2026_2026-11-13_Sobczak – Pawlak"

    def test_kilku_nabywcow(self):
        pola = [{"nazwa": "STALE: nazwiska stron czynnosci", "wartosc": "Sobczak - Pawlak - Nowak"}]
        assert nazwa_pliku("{zbywca} - {nabywca}", pola) == "Sobczak - Pawlak i Nowak"
        assert nazwa_pliku("{strony}", pola) == "Sobczak - Pawlak - Nowak"

    def test_znaki_niedozwolone_w_nazwie_pliku(self):
        pola = [{"nazwa": "STALE: miejscowosc polozenia nieruchomosci", "wartosc": 'Zalesie "Dolne"?'}]
        assert "?" not in nazwa_pliku("{miejscowosc}", pola) and '"' not in nazwa_pliku("{miejscowosc}", pola)
        assert bezpieczna_nazwa_pliku(" a/b\\c:d*e ") == "a-b-c-de"
        assert len(bezpieczna_nazwa_pliku("x" * 500)) == MAX_DLUGOSC_NAZWY

    def test_nieznane_pole_wykryte_i_pomijane(self):
        assert nieznane_pola_wzoru("{zbywca} - {klient}") == ["klient"]
        assert nazwa_pliku("{zbywca} - {klient}", self.POLA) == "Sobczak"

    def test_czynnosc_z_rodzajow(self):
        assert czynnosc_z_rodzajow(["darowizna", "sprzedaz"]) == "darowizna"
        assert czynnosc_z_rodzajow(["inny"]) == ""
        assert czynnosc_z_rodzajow(None) == ""

    def test_miejscowosc_z_pola_legendy_bez_adresu_strony(self):
        pola = [{"nazwa": "adres zamieszkania zbywcy - miejscowość", "wartosc": "Warszawa"},
                {"nazwa": "ccc: miejscowość położenia nieruchomości", "wartosc": "Zalesie Górne (gmina Piaseczno)"}]
        assert miejscowosc_z_pol(pola) == "Zalesie Górne"
        assert miejscowosc_z_pol([]) == ""

    def test_przyklad_dla_okna_ustawien(self):
        assert przyklad_nazwy(DOMYSLNY_WZOR_NAZWY) == "Sobczak - Pawlak - sprzedaż - Zalesie.docx"
        assert przyklad_nazwy("") == "Sobczak - Pawlak - sprzedaż - Zalesie.docx"
