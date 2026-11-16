"""Zakres w zdaniu zasady: wzorce sprzedaz_rolna i spolka nie trafia
w srodek slowa (np. "kontrolna", "wspolkupujacy")."""
from kategorie import rodzaje_w_zdaniu


class TestBrakFalszywychTrafien:
    def test_kontrolna_nie_jest_sprzedazia_rolna(self):
        assert rodzaje_w_zdaniu("cyfra kontrolna KW") == []

    def test_wspolkupujacy_nie_jest_spolka(self):
        assert rodzaje_w_zdaniu("współkupujący") == []


class TestSluszneTrafienia:
    def test_sprzedaz_nieruchomosci_rolnej(self):
        znalezione = rodzaje_w_zdaniu("sprzedaż nieruchomości rolnej")
        assert "sprzedaz_rolna" in znalezione
        assert "sprzedaz" in znalezione

    def test_umowa_spolki(self):
        assert rodzaje_w_zdaniu("umowa spółki z o.o.") == ["spolka"]

    def test_spolki_mnogie(self):
        assert "spolka" in rodzaje_w_zdaniu("udziały w spółkach")
