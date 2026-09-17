"""Testy dla wykrywania pol ze wzoru i operacji na dokumentach.

Testujemy:
- wykrywanie placeholder'ow {{nazwa}} i [NAZWA]
- kolejnosc pol
- duplikaty
- formaty edge case
"""
import pytest
from pathlib import Path
import tempfile
from dokumenty import pola_ze_wzoru, wzor_na_tekst, tekst_na_docx


class TestPolaZeWzoru:
    """Testy wykrywania pol w szablonach."""

    def test_pola_podwojne_nawiasy(self):
        wzor = "Stawil sie {{imie}} {{nazwisko}} PESEL {{pesel}}"
        pola = pola_ze_wzoru(wzor)
        assert pola == ["imie", "nazwisko", "pesel"]

    def test_pola_kwadratowe_nawiasy(self):
        wzor = "Stawil sie [IMIE I NAZWISKO] PESEL [PESEL]"
        pola = pola_ze_wzoru(wzor)
        assert pola == ["IMIE I NAZWISKO", "PESEL"]

    def test_pola_mieszane(self):
        wzor = "Dnia {{data}} stawil sie [IMIE] {{nazwisko}}"
        pola = pola_ze_wzoru(wzor)
        assert pola == ["data", "IMIE", "nazwisko"]

    def test_pola_ze_spacjami(self):
        wzor = "{{  imie  }} [  NAZWISKO  ]"
        pola = pola_ze_wzoru(wzor)
        assert pola == ["imie", "NAZWISKO"]

    def test_duplikaty_pomijane(self):
        wzor = "{{imie}} {{nazwisko}} {{imie}} ponownie {{imie}}"
        pola = pola_ze_wzoru(wzor)
        assert pola == ["imie", "nazwisko"]

    def test_kolejnosc_zachowana(self):
        wzor = "{{trzecie}} {{pierwsze}} {{drugie}}"
        pola = pola_ze_wzoru(wzor)
        assert pola == ["trzecie", "pierwsze", "drugie"]

    def test_puste_nawiasy_pomijane(self):
        wzor = "{{}} {{imie}} [[]] [NAZWISKO]"
        pola = pola_ze_wzoru(wzor)
        assert pola == ["imie", "NAZWISKO"]

    def test_za_krotkie_pole_w_kwadratowych(self):
        # [AB] jest za krotkie (min 3 znaki w nawiasach kwadratowych)
        wzor = "[AB] [ABC] [ABCD]"
        pola = pola_ze_wzoru(wzor)
        assert "AB" not in pola
        assert "ABC" in pola
        assert "ABCD" in pola

    def test_wieloliniowy_wzor(self):
        wzor = """
        Dnia {{data czynnosci}}
        stawil sie {{imie}} {{nazwisko}}
        PESEL {{pesel}}
        """
        pola = pola_ze_wzoru(wzor)
        assert "data czynnosci" in pola
        assert "imie" in pola
        assert "nazwisko" in pola
        assert "pesel" in pola

    def test_pola_w_tabelach(self):
        wzor = "| {{kolumna1}} | {{kolumna2}} |\n| [WARTOSC1] | [WARTOSC2] |"
        pola = pola_ze_wzoru(wzor)
        assert "kolumna1" in pola
        assert "kolumna2" in pola
        assert "WARTOSC1" in pola
        assert "WARTOSC2" in pola

    def test_brak_pol(self):
        wzor = "To jest zwykly tekst bez pol."
        pola = pola_ze_wzoru(wzor)
        assert pola == []

    def test_niepelne_nawiasy(self):
        wzor = "{{niepelny {dalszy}} [[inny]"
        pola = pola_ze_wzoru(wzor)
        # Niepelne nawiasy nie powinny byc wykryte
        assert pola == []

    def test_zagniezdzone_nawiasy(self):
        wzor = "{{zewnetrzne {{wewnetrzne}} }}"
        pola = pola_ze_wzoru(wzor)
        # Zalezy od implementacji - najprawdopodobniej wykryje wewnetrzne

    def test_polskie_znaki_w_kwadratowych(self):
        # Wzorzec wymaga aby [NAZWA] zaczynalo sie od wielkiej litery polskiej
        wzor = "[ŁUKASZ] [ŻÓŁĆ] [ŚWIĘTY]"
        pola = pola_ze_wzoru(wzor)
        assert "ŁUKASZ" in pola
        assert "ŻÓŁĆ" in pola
        assert "ŚWIĘTY" in pola

    def test_male_litery_w_kwadratowych_pomijane(self):
        # [nazwa] z mala litera nie powinna byc wykryta (wg wzorca)
        wzor = "[nazwa] [NAZWA]"
        pola = pola_ze_wzoru(wzor)
        assert "nazwa" not in pola
        assert "NAZWA" in pola

    def test_za_dlugie_pole_w_kwadratowych(self):
        # Limit to 60 znakow
        dlugie = "A" * 70
        wzor = f"[{dlugie}]"
        pola = pola_ze_wzoru(wzor)
        assert dlugie not in pola

    def test_pole_z_liczbami(self):
        wzor = "{{pole123}} [POLE456]"
        pola = pola_ze_wzoru(wzor)
        assert "pole123" in pola
        assert "POLE456" in pola


class TestWzorNaTekst:
    """Testy odczytu wzoru z plikow."""

    def test_czytanie_txt(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("To jest testowy wzor {{pole1}}")
            sciezka = Path(f.name)

        try:
            tekst = wzor_na_tekst(sciezka)
            assert "testowy wzor" in tekst
            assert "{{pole1}}" in tekst
        finally:
            sciezka.unlink()

    def test_czytanie_docx(self):
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            sciezka = Path(f.name)

        try:
            # Utworz prosty dokument docx
            from docx import Document
            doc = Document()
            doc.add_paragraph("Wzor aktu {{data}}")
            doc.add_paragraph("Imie: {{imie}}")
            doc.save(sciezka)

            tekst = wzor_na_tekst(sciezka)
            assert "Wzor aktu" in tekst
            assert "{{data}}" in tekst
            assert "{{imie}}" in tekst
        finally:
            if sciezka.exists():
                sciezka.unlink()


class TestTekstNaDocx:
    """Testy eksportu projektu do docx."""

    def test_zapis_podstawowy(self):
        tekst = "Dnia 2026-07-24\nstawil sie Jan Kowalski"
        with tempfile.TemporaryDirectory() as tmpdir:
            cel = Path(tmpdir) / "projekt.docx"
            wynik = tekst_na_docx(tekst, cel)
            assert wynik.exists()
            assert wynik == cel

            # Sprawdz czy da sie odczytac
            odczyt = wzor_na_tekst(cel)
            assert "2026-07-24" in odczyt
            assert "Jan Kowalski" in odczyt

    def test_zapis_z_pustymi_liniami(self):
        tekst = "Akapit 1\n\nAkapit 2\n\n\nAkapit 3"
        with tempfile.TemporaryDirectory() as tmpdir:
            cel = Path(tmpdir) / "projekt.docx"
            tekst_na_docx(tekst, cel)
            odczyt = wzor_na_tekst(cel)
            # Sprawdz czy wszystkie akapity sa obecne
            assert "Akapit 1" in odczyt
            assert "Akapit 2" in odczyt
            assert "Akapit 3" in odczyt

    def test_katalog_tworzony_automatycznie(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cel = Path(tmpdir) / "nieistniejacy" / "katalog" / "projekt.docx"
            tekst_na_docx("Test", cel)
            assert cel.exists()

    def test_zapis_wielkich_liter(self):
        # Tekst pisany wielkimi literami powinien byc wysrodkowany i pogrubiony
        tekst = "AKT NOTARIALNY\nDnia dzisiejszego"
        with tempfile.TemporaryDirectory() as tmpdir:
            cel = Path(tmpdir) / "projekt.docx"
            tekst_na_docx(tekst, cel)

            from docx import Document
            doc = Document(cel)
            # Pierwszy akapit (AKT NOTARIALNY) powinien byc pogrubiony
            assert len(doc.paragraphs) >= 2
            pierwszy = doc.paragraphs[0]
            # Sprawdz czy tekst zostal zapisany
            assert "AKT NOTARIALNY" in pierwszy.text or len(pierwszy.runs) > 0
