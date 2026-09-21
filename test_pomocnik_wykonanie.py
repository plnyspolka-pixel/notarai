"""Testy wykonania zlecenia po stronie pomocnika.

Pomocnik siedzi przy zalogowanej sesji notariusza, wiec nie moze wierzyc
serwerowi na slowo. Te testy pilnuja przede wszystkim tego, czego pomocnik
ma ODMOWIC.
"""
import pytest

from pomocnik import wykonanie
from pomocnik.wykonanie import OdmowaWykonania, wykonaj


class AtrapaStrony:
    def __init__(self, url="https://rejestry.krn.org.pl/pesel/formularz",
                 elementy=("#pesel", "#rodzaj", "#zgoda", "#wyslij", "#haslo"),
                 typy=None):
        self.url = url
        self.elementy = set(elementy)
        self.typy = typy or {"#haslo": "password", "#pesel": "text",
                             "#rodzaj": "select-one", "#zgoda": "checkbox"}
        self.wpisane = {}
        self.klikniete = []

    def istnieje(self, selektor): return selektor in self.elementy
    def poczekaj_na(self, selektor, sekundy=0): return selektor in self.elementy
    def typ_pola(self, selektor): return self.typy.get(selektor, "text")
    def wpisz(self, selektor, wartosc): self.wpisane[selektor] = wartosc
    def wybierz(self, selektor, wartosc): self.wpisane[selektor] = wartosc
    def zaznacz(self, selektor, tak): self.wpisane[selektor] = tak


def zlecenie(**zmiany):
    podstawa = {
        "system": "rejestry_notarialne_pesel",
        "tryb": "faktyczny",
        "status_mapowania": "gotowe",
        "adres": "https://rejestry.krn.org.pl/pesel",
        "gotowosc": "#pesel",
        "przycisk_wysylki": "#wyslij",
        "kroki": [{"pole": "Numer PESEL", "selektor": "#pesel", "typ": "tekst",
                   "wartosc": "44051401359"}],
    }
    podstawa.update(zmiany)
    return podstawa


class TestCzegoPomocnikOdmawia:
    def test_nie_dziala_na_przycisku_wysylki(self):
        """Najwazniejsza kontrola: zlecenie celujace w przycisk wysylki
        przepada w calosci, a nie tylko w tym jednym kroku."""
        zle = zlecenie(kroki=[
            {"pole": "Numer PESEL", "selektor": "#pesel", "typ": "tekst", "wartosc": "44051401359"},
            {"pole": "Sprawdz", "selektor": "#wyslij", "typ": "tekst", "wartosc": "x"},
        ])
        strona = AtrapaStrony()
        with pytest.raises(OdmowaWykonania, match="przycisku wysylki"):
            wykonaj(zle, strona)
        assert strona.wpisane == {}, "po odmowie nie wolno wpisac nawet poprawnego pola"

    def test_nie_wpisuje_do_pola_hasla(self):
        zle = zlecenie(kroki=[{"pole": "Haslo", "selektor": "#haslo", "typ": "tekst",
                               "wartosc": "cokolwiek"}])
        raport = wykonaj(zle, strona := AtrapaStrony())
        assert strona.wpisane == {}
        assert raport["kroki"][0]["wykonano"] is False
        assert "haslo" in raport["bledy"][0].lower()

    def test_szkic_mapowania_nie_wpisuje_niczego(self):
        raport = wykonaj(zlecenie(status_mapowania="szkic"), strona := AtrapaStrony())
        assert strona.wpisane == {}
        assert raport["tryb"] == "podglad"
        assert "szkic" in raport["bledy"][0]

    def test_inna_strona_to_odmowa(self):
        strona = AtrapaStrony(url="https://zupelnie.inny.portal/formularz")
        with pytest.raises(OdmowaWykonania, match="nie jest formularzem"):
            wykonaj(zlecenie(), strona)
        assert strona.wpisane == {}

    def test_formularz_jeszcze_niegotowy_to_odmowa(self):
        strona = AtrapaStrony(elementy=("#wyslij",))
        with pytest.raises(OdmowaWykonania, match="nie jest gotowy"):
            wykonaj(zlecenie(), strona)

    def test_niekompletne_zlecenie_to_odmowa(self):
        with pytest.raises(OdmowaWykonania, match="niekompletne"):
            wykonaj(zlecenie(gotowosc=""), AtrapaStrony())


class TestPodgladu:
    def test_podglad_nie_dotyka_strony(self):
        raport = wykonaj(zlecenie(tryb="podglad"), strona := AtrapaStrony())
        assert strona.wpisane == {}
        assert raport["tryb"] == "podglad"
        assert raport["kroki"][0]["ma_wartosc"] is True

    def test_podglad_jest_domyslny(self):
        """Zlecenie bez pola 'tryb' nie moze niczego wpisac."""
        zle = zlecenie()
        del zle["tryb"]
        wykonaj(zle, strona := AtrapaStrony())
        assert strona.wpisane == {}


class TestWypelniania:
    def test_wpisuje_tekst_liste_i_pole_wyboru(self):
        zle = zlecenie(kroki=[
            {"pole": "Numer PESEL", "selektor": "#pesel", "typ": "tekst", "wartosc": "44051401359"},
            {"pole": "Rodzaj", "selektor": "#rodzaj", "typ": "lista", "wartosc": "Sprzedaz"},
            {"pole": "Zgoda", "selektor": "#zgoda", "typ": "pole_wyboru", "wartosc": "tak"},
        ])
        raport = wykonaj(zle, strona := AtrapaStrony())
        assert strona.wpisane == {"#pesel": "44051401359", "#rodzaj": "Sprzedaz", "#zgoda": True}
        assert all(k["wykonano"] for k in raport["kroki"])
        assert raport["bledy"] == []

    def test_puste_pole_jest_pomijane_a_nie_kasuje_rubryki(self):
        zle = zlecenie(kroki=[{"pole": "Numer PESEL", "selektor": "#pesel",
                               "typ": "tekst", "wartosc": ""}])
        raport = wykonaj(zle, strona := AtrapaStrony())
        assert strona.wpisane == {}
        assert raport["kroki"][0]["uwaga"] == "brak wartosci"

    def test_blad_jednego_pola_nie_przerywa_reszty(self):
        class Kapryszna(AtrapaStrony):
            def wpisz(self, selektor, wartosc):
                if selektor == "#pesel":
                    raise RuntimeError("pole zablokowane")
                super().wpisz(selektor, wartosc)

        zle = zlecenie(kroki=[
            {"pole": "Numer PESEL", "selektor": "#pesel", "typ": "tekst", "wartosc": "44051401359"},
            {"pole": "Rodzaj", "selektor": "#rodzaj", "typ": "lista", "wartosc": "Sprzedaz"},
        ])
        raport = wykonaj(zle, strona := Kapryszna())
        assert strona.wpisane == {"#rodzaj": "Sprzedaz"}
        assert raport["kroki"][0]["wykonano"] is False
        assert raport["kroki"][1]["wykonano"] is True
        assert len(raport["bledy"]) == 1

    def test_nieznany_typ_pola_to_blad_kroku(self):
        zle = zlecenie(kroki=[{"pole": "Cos", "selektor": "#pesel",
                               "typ": "suwak", "wartosc": "5"}])
        raport = wykonaj(zle, AtrapaStrony())
        assert "Nieznany typ pola" in raport["bledy"][0]


class TestRaportu:
    def test_raport_nie_niesie_wartosci_pol(self):
        """Raport trafia do logow. Dane osobowe nie maja tam czego szukac."""
        raport = wykonaj(zlecenie(), AtrapaStrony())
        assert "44051401359" not in str(raport)

    def test_raport_zawsze_mowi_ze_nie_wyslano(self):
        raport = wykonaj(zlecenie(), AtrapaStrony())
        assert "wysyla czlowiek" in raport["zatrzymano_przed"]

    def test_pomocnik_nie_ma_czym_kliknac_wysylki(self):
        """Nie chodzi o to, ze nie klika - chodzi o to, ze nie potrafi."""
        assert not hasattr(wykonanie, "kliknij")
        assert "kliknij" not in dir(AtrapaStrony())
