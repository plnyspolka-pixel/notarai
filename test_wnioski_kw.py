"""Wnioski wieczystoksiegowe: numer REP.C i oplata sadowa (kwoty wg taksa.OPLATY_SADOWE)."""
from decimal import Decimal

import pytest

import taksa
import wnioski_kw


class TestNormalizujRepC:
    def test_kreski_jak_w_zapisie_kancelarii(self):
        assert wnioski_kw.normalizuj_rep_c("rep.c/nota/1234/26") == "REP.C/NOTA/1234/26"

    def test_odzelnosci_kreski_i_zera_wiodace(self):
        assert wnioski_kw.normalizuj_rep_c("rep.c nota 001234 26") == "REP.C/NOTA/1234/26"

    def test_wielka_literami_od_poczatku(self):
        assert wnioski_kw.normalizuj_rep_c("REP.C/NOTA/1234/26") == "REP.C/NOTA/1234/26"

    @pytest.mark.parametrize("kod", ["KANCEL", "ADWO", "SAD"])
    def test_kod_podmiotu_inny_niz_nota(self, kod):
        with pytest.raises(ValueError):
            wnioski_kw.normalizuj_rep_c(f"REP.C/{kod}/1/26")

    def test_napis_bez_roku(self):
        with pytest.raises(ValueError):
            wnioski_kw.normalizuj_rep_c("REP.C/NOTA")

    def test_pusty_napis(self):
        with pytest.raises(ValueError):
            wnioski_kw.normalizuj_rep_c("")

    def test_none(self):
        with pytest.raises(ValueError):
            wnioski_kw.normalizuj_rep_c(None)


class TestOplata:
    def test_suma_dwuzadan(self):
        a, b = "wpis_wlasnosci", "wpis_roszczenia"
        wynik = wnioski_kw.oplata([{"oplata": a, "opis": "A"}, {"oplata": b, "opis": "B"}])
        nazwy, kwoty = taksa.OPLATY_SADOWE[a], taksa.OPLATY_SADOWE[b]
        assert wynik["pozycje"] == [
            {"zadanie": "A", "podstawa": nazwy[0], "kwota": str(nazwy[1])},
            {"zadanie": "B", "podstawa": kwoty[0], "kwota": str(kwoty[1])},
        ]
        assert wynik["razem"] == str((nazwy[1] + kwoty[1]).quantize(Decimal("0.01")))

    def test_zadanie_bez_opłaty(self):
        a = "wpis_wlasnosci"
        wynik = wnioski_kw.oplata([{"oplata": None, "opis": "Bez opłaty"},
                                    {"oplata": a, "opis": "Z oplata"}])
        assert wynik["pozycje"] == [{"zadanie": "Z oplata", "podstawa": taksa.OPLATY_SADOWE[a][0],
                                     "kwota": str(taksa.OPLATY_SADOWE[a][1])}]

    def test_pusta_lista(self):
        wynik = wnioski_kw.oplata([])
        assert wynik["pozycje"] == []
        assert wynik["razem"] == "0.00"

    def test_razem_jest_napisem_z_dwiema_miejscami_po_przecinku(self):
        wynik = wnioski_kw.oplata([{"oplata": "zalozenie_kw", "opis": "X"}])
        razem = wynik["razem"]
        assert isinstance(razem, str)
        cała, _, części = razem.partition(".")
        assert cała.isdigit() and części == "00"
        assert razem == str(taksa.OPLATY_SADOWE["zalozenie_kw"][1].quantize(Decimal("0.01")))
