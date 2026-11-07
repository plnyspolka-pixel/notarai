"""Silnik taksy notarialnej - liczby sprawdzone recznie wg rozporzadzenia
(t.j. Dz.U. 2024 poz. 1566 i zmiana Dz.U. 2026 poz. 1370)."""
from datetime import date
from decimal import Decimal

import pytest

import taksa

NOWE = date(2026, 11, 7)    # po zmianie z 5.11.2026
STARE = date(2026, 11, 4)   # dzien przed


class TestStawkaPodstawowa:
    @pytest.mark.parametrize("wartosc, oczekiwana", [
        (1, "100"), (3000, "100"),
        (3001, "100.03"), (10000, "310"),
        (20000, "510"), (30000, "710"),
        (45000, "860"), (60000, "1010"),
        (450000, "2570"), (1000000, "4770"),
        (1500000, "5770"), (2000000, "6770"),
        (3000000, "9270"), (5000000, "14270"),
        (6000000, "15770"), (12000000, "24770"),
    ])
    def test_progi_nowej_tabeli(self, wartosc, oczekiwana):
        assert taksa.stawka_podstawowa(wartosc, NOWE) == (Decimal(oczekiwana), False)

    def test_limit_nowy_25000(self):
        assert taksa.stawka_podstawowa(20_000_000, NOWE) == (Decimal("25000"), True)

    def test_limit_nowy_grupa1_15000(self):
        assert taksa.stawka_podstawowa(6_000_000, NOWE, grupa1=True) == (Decimal("15000"), True)
        assert taksa.stawka_podstawowa(5_000_000, NOWE, grupa1=True) == (Decimal("14270"), False)

    def test_stara_tabela_powyzej_2_mln(self):
        assert taksa.stawka_podstawowa(3_000_000, STARE) == (Decimal("9270"), False)
        assert taksa.stawka_podstawowa(5_000_000, STARE) == (Decimal("10000"), True)
        assert taksa.stawka_podstawowa(3_000_000, STARE, grupa1=True) == (Decimal("7500"), True)

    def test_zero_i_smieci(self):
        assert taksa.stawka_podstawowa(0, NOWE) == (Decimal("0"), False)
        assert taksa.stawka_podstawowa("abc", NOWE) == (Decimal("0"), False)
        assert taksa.stawka_podstawowa(-5, NOWE) == (Decimal("0"), False)

    def test_napis_z_polskim_formatem(self):
        assert taksa.stawka_podstawowa("450 000,00 zł", NOWE)[0] == Decimal("2570")


class TestWypisy:
    def test_nowe_progi_12_10_8(self):
        assert taksa.koszt_wypisu(1, NOWE) == 12
        assert taksa.koszt_wypisu(10, NOWE) == 120
        assert taksa.koszt_wypisu(11, NOWE) == 130
        assert taksa.koszt_wypisu(20, NOWE) == 220
        assert taksa.koszt_wypisu(21, NOWE) == 228
        assert taksa.koszt_wypisu(25, NOWE) == 260

    def test_stara_stawka_6_zl(self):
        assert taksa.koszt_wypisu(25, STARE) == 150

    def test_zero_stron(self):
        assert taksa.koszt_wypisu(0, NOWE) == 0


class TestTabela:
    def test_data_zmiany(self):
        assert taksa.tabela(date(2026, 11, 5))["id"] == "2026"
        assert taksa.tabela(date(2026, 11, 4))["id"] == "2004"
        assert taksa.tabela(date(2030, 1, 1))["id"] == "2026"

    def test_placa_minimalna(self):
        assert taksa.placa_minimalna(date(2026, 3, 1)) == 4806
        assert taksa.placa_minimalna(date(2040, 3, 1)) == 4806   # ostatnia znana


class TestObliczSprzedaz:
    def test_sprzedaz_mieszkania_jak_w_car(self):
        """450 000 zl, 1/2 stawki, 6 wypisow po 6 stron, PCC 2 %, wpis wlasnosci."""
        w = taksa.oblicz({"data": "2026-11-07", "czynnosci": [{"rodzaj": "sprzedaz_lokalu", "wartosc": 450000}]})
        etykiety = {p["etykieta"]: p for p in w["pozycje"]}
        t = [p for p in w["pozycje"] if p["rodzaj"] == "taksa"]
        assert t[0]["netto"] == 1285.0 and t[0]["brutto"] == 1580.55 and t[0]["podstawa"] == "§ 6 pkt 19"
        assert etykiety["wypisy aktu (6 × 6 str.)"]["brutto"] == 531.36
        assert etykiety["podatek od czynności cywilnoprawnych (PCC 2 %)"]["brutto"] == 9000.0
        assert etykiety["opłata sądowa: wpis prawa własności (użytkowania wieczystego, spółdzielczego prawa)"]["brutto"] == 200.0
        assert etykiety["wniosek o wpis w księdze wieczystej"]["brutto"] == 369.0
        assert etykiety["opłata rejestracyjna"]["brutto"] == 5.0
        assert w["razem"] == pytest.approx(1580.55 + 531.36 + 9000 + 200 + 369 + 5)
        assert w["sumy"]["taksa_netto"] == 1285.0 + 300.0
        assert "RAZEM" in w["tekst"] and "szacunkowe" in w["tekst"]
        assert w["tabela"]["id"] == "2026"

    def test_kredyt_dodaje_hipoteke_pcc_i_oplate(self):
        w = taksa.oblicz({"data": "2026-11-07",
                          "czynnosci": [{"rodzaj": "sprzedaz_lokalu", "wartosc": 450000}],
                          "hipoteka": {"kwota": 400000}})
        etykiety = {p["etykieta"]: p for p in w["pozycje"]}
        hip = etykiety["taksa notarialna: ustanowienie hipoteki 400 000,00 zł (1/4 stawki)"]
        assert hip["netto"] == 592.5 and hip["podstawa"] == "§ 7 ust. 1 pkt 1"
        assert etykiety["PCC od ustanowienia hipoteki"]["brutto"] == 19.0
        assert etykiety["opłata sądowa: wpis hipoteki"]["brutto"] == 200.0
        assert w["razem"] == pytest.approx(12633.69)

    def test_hipoteka_inna_niz_kredyt_mieszkaniowy_to_polowa(self):
        w = taksa.oblicz({"data": "2026-11-07", "czynnosci": [{"rodzaj": "sprzedaz_domu", "wartosc": 100000}],
                          "hipoteka": {"kwota": 100000, "kredyt_mieszkaniowy": False}})
        hip = [p for p in w["pozycje"] if "hipoteki" in p["etykieta"] and p["rodzaj"] == "taksa"][0]
        assert hip["netto"] == 585.0 and hip["podstawa"] == "§ 6 pkt 11"

    def test_grupa1_niski_limit(self):
        w = taksa.oblicz({"data": "2026-11-07", "grupa1": True,
                          "czynnosci": [{"rodzaj": "darowizna_inna", "wartosc": 6_000_000}]})
        t = [p for p in w["pozycje"] if p["rodzaj"] == "taksa"][0]
        assert t["netto"] == 15000.0
        assert any("limit taksy 15" in u for u in w["uwagi"])
        assert not any(p["rodzaj"] == "pcc" for p in w["pozycje"])   # darowizna bez PCC

    def test_darowizna_bez_pcc_i_bez_uwagi_o_pcc(self):
        w = taksa.oblicz({"data": "2026-11-07", "czynnosci": [{"rodzaj": "darowizna_lokalu_grupa1", "wartosc": 300000}], "grupa1": True})
        assert w["sumy"]["pcc"] == 0 and w["uwagi"] == []

    def test_pcc_wylaczone_recznie_daje_uwage(self):
        w = taksa.oblicz({"data": "2026-11-07", "pcc": False,
                          "czynnosci": [{"rodzaj": "sprzedaz_lokalu", "wartosc": 300000}]})
        assert w["sumy"]["pcc"] == 0 and any("Nie doliczono PCC" in u for u in w["uwagi"])

    def test_deweloper_bez_pcc_z_zalozeniem_kw(self):
        w = taksa.oblicz({"data": "2026-11-07", "czynnosci": [{"rodzaj": "przeniesienie_od_dewelopera", "wartosc": 600000}]})
        assert w["sumy"]["pcc"] == 0 and w["sumy"]["sad"] == 300.0

    def test_umowa_spolki_pcc_pol_procent(self):
        w = taksa.oblicz({"data": "2026-11-07", "czynnosci": [{"rodzaj": "umowa_spolki", "wartosc": 100000}]})
        pcc = [p for p in w["pozycje"] if p["rodzaj"] == "pcc"][0]
        assert pcc["brutto"] == 500.0 and "0,5" in pcc["etykieta"]
        assert w["sumy"]["sad"] == 0 and not any("wniosek" in p["etykieta"] for p in w["pozycje"])

    def test_rabat_zastepuje_stawke_maksymalna(self):
        w = taksa.oblicz({"data": "2026-11-07", "czynnosci": [{"rodzaj": "sprzedaz_inna", "wartosc": 100000, "rabat_netto": 500}]})
        t = [p for p in w["pozycje"] if p["rodzaj"] == "taksa"][0]
        assert t["netto"] == 500.0 and "po rabacie" in t["uwaga"]

    def test_rabat_wyzszy_niz_maksimum_jest_ignorowany(self):
        w = taksa.oblicz({"data": "2026-11-07", "czynnosci": [{"rodzaj": "sprzedaz_inna", "wartosc": 100000, "rabat_netto": 5000}]})
        assert [p for p in w["pozycje"] if p["rodzaj"] == "taksa"][0]["netto"] == 1170.0

    def test_dwie_czynnosci_sumuja_pcc(self):
        w = taksa.oblicz({"data": "2026-11-07", "czynnosci": [
            {"rodzaj": "sprzedaz_lokalu", "wartosc": 100000}, {"rodzaj": "sprzedaz_inna", "wartosc": 50000, "opis": "garaż"}]})
        assert w["wartosc"] == 150000.0
        assert [p for p in w["pozycje"] if p["rodzaj"] == "pcc"][0]["brutto"] == 3000.0
        assert sum(1 for p in w["pozycje"] if "wpis prawa własności" in p["etykieta"]) == 1

    def test_stara_tabela_wniosek_kw_200_i_wypisy_6(self):
        w = taksa.oblicz({"data": "2026-10-01", "czynnosci": [{"rodzaj": "sprzedaz_lokalu", "wartosc": 450000}]})
        etykiety = {p["etykieta"]: p for p in w["pozycje"]}
        assert etykiety["wniosek o wpis w księdze wieczystej"]["netto"] == 200.0
        assert etykiety["wypisy aktu (6 × 6 str.)"]["netto"] == 216.0
        assert w["tabela"]["id"] == "2004"

    def test_poswiadczenie_podpisu_z_suma_limit_500(self):
        w = taksa.oblicz({"data": "2026-11-07", "czynnosci": [{"rodzaj": "poswiadczenie_podpisu_z_suma", "wartosc": 3_000_000}]})
        t = [p for p in w["pozycje"] if p["rodzaj"] == "taksa"][0]
        assert t["netto"] == 500.0 and not any(p["rodzaj"] == "wypisy" for p in w["pozycje"])

    def test_nieznany_rodzaj_to_pelna_stawka(self):
        w = taksa.oblicz({"data": "2026-11-07", "czynnosci": [{"rodzaj": "cos_dziwnego", "wartosc": 10000}]})
        assert [p for p in w["pozycje"] if p["rodzaj"] == "taksa"][0]["netto"] == 310.0

    def test_wypisy_i_strony_z_parametrow(self):
        w = taksa.oblicz({"data": "2026-11-07", "wypisy": 3, "strony": 12,
                          "czynnosci": [{"rodzaj": "sprzedaz_lokalu", "wartosc": 10000}]})
        wyp = [p for p in w["pozycje"] if p["rodzaj"] == "wypisy"][0]
        assert wyp["netto"] == 3 * 140.0

    def test_dokumenty_pogrupowane(self):
        w = taksa.oblicz({"data": "2026-11-07", "czynnosci": [{"rodzaj": "sprzedaz_domu", "wartosc": 10000}]})
        grupy = {d["grupa"]: d["pozycje"] for d in w["dokumenty"]}
        assert "Wypis z rejestru gruntów" in grupy["Starostwo powiatowe (w mieście na prawach powiatu: urząd miasta)"]
        assert "Świadectwo charakterystyki energetycznej" in grupy["Dodatkowo"]

    def test_pusto(self):
        w = taksa.oblicz({})
        assert w["pozycje"] == [] and w["razem"] == 0 and w["tekst"] == "" and w["uwagi"]


class TestObliczStale:
    def test_testament_z_wyborem_prawa(self):
        w = taksa.oblicz({"data": "2026-11-07", "stale": [{"id": "testament", "opcje": ["wybor_prawa"]}]})
        brutto = [p["brutto"] for p in w["pozycje"]]
        assert brutto == [246.0, 492.0, 29.52]      # 200, 400 (§ 16), 1 wypis x 2 str. x 12 zl
        assert w["razem"] == 767.52

    def test_testament_przed_zmiana_50_zl(self):
        w = taksa.oblicz({"data": "2026-11-04", "stale": [{"id": "testament", "wypisy": 0}]})
        assert w["pozycje"][0]["netto"] == 50.0 and w["razem"] == 61.5

    def test_przechowanie_ilosc_miesiecy_bez_wypisow(self):
        w = taksa.oblicz({"data": "2026-11-07", "stale": [{"id": "przechowanie_miesiac", "ilosc": 3}]})
        assert len(w["pozycje"]) == 1 and w["pozycje"][0]["netto"] == 150.0

    def test_poswiadczenie_odpisu_od_stron(self):
        w = taksa.oblicz({"data": "2026-11-07", "stale": [{"id": "poswiadczenie_odpisu", "dokumentow": 2, "stron_dokumentu": 12}]})
        assert w["pozycje"][0]["netto"] == 2 * 140.0 and len(w["pozycje"]) == 1

    def test_spoldzielcze_cwierc_placy_z_wnioskiem_i_hipoteka(self):
        w = taksa.oblicz({"data": "2026-11-07", "stale": [{"id": "przeniesienie_spoldzielcze", "hipoteka": 200000}]})
        etykiety = {p["etykieta"]: p for p in w["pozycje"]}
        assert [p for p in w["pozycje"] if "1/4 płacy" in p["etykieta"]][0]["netto"] == 1201.5
        assert etykiety["opłata sądowa: założenie księgi wieczystej"]["brutto"] == 100.0
        assert etykiety["opłata sądowa: wpis hipoteki"]["brutto"] == 200.0
        assert etykiety["wniosek o wpis w księdze wieczystej"]["netto"] == 300.0
        assert etykiety["PCC od ustanowienia hipoteki"]["brutto"] == 19.0
        assert [p for p in w["pozycje"] if "hipoteki 200" in p["etykieta"]][0]["netto"] == 392.5   # (1010 + 140 000 x 0,4 %) / 4

    def test_najem_okazjonalny_dziesiata_placy(self):
        w = taksa.oblicz({"data": "2026-11-07", "stale": [{"id": "najem_okazjonalny", "wypisy": 0}]})
        assert w["pozycje"][0]["netto"] == 480.6

    def test_nieznana_opcja_i_id_pomijane(self):
        w = taksa.oblicz({"data": "2026-11-07", "stale": [{"id": "testament", "opcje": ["cos"], "wypisy": 0}, {"id": "nie_ma"}]})
        assert len(w["pozycje"]) == 1

    def test_wniosek_kw_mozna_wylaczyc(self):
        w = taksa.oblicz({"data": "2026-11-07", "stale": [{"id": "zrzeczenie_wlasnosci", "wniosek_kw": False, "wypisy": 0}]})
        assert len(w["pozycje"]) == 1


class TestPrezentacja:
    def test_format_zl(self):
        assert taksa.zl(1234.5) == "1 234,50 zł"
        assert taksa.zl(0) == "0,00 zł"
        assert taksa.zl(12633690.126) == "12 633 690,13 zł"

    def test_tekst_z_podpisem(self):
        w = taksa.oblicz({"data": "2026-11-07", "stale": [{"id": "testament"}]})
        tekst = taksa.tekst_kalkulacji(w, "Kancelaria X, tel. 123")
        assert tekst.endswith("Kancelaria X, tel. 123") and "RAZEM: 275,52" in tekst.replace(" ", " ")

    def test_katalog_i_opis_spojne(self):
        kat = taksa.katalog()
        assert {r["id"] for r in kat["rodzaje"]} == set(taksa.RODZAJE_WG_ID)
        assert kat["wniosek_kw"] == 300.0 and kat["limit"] == 25000.0
        opis = taksa.opis_dla_modelu(NOWE)
        for ident in list(taksa.RODZAJE_WG_ID) + list(taksa.STALE_WG_ID):
            assert ident in opis
        assert "PESEL" not in opis
