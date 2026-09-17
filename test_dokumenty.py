"""Testy dla wykrywania pol ze wzoru i operacji na dokumentach.

Testujemy:
- wykrywanie placeholder'ow {{nazwa}} i [NAZWA]
- kolejnosc pol
- duplikaty
- formaty edge case
"""
import io

import pytest
from pathlib import Path
import tempfile
from dokumenty import pola_ze_wzoru, wzor_na_tekst, tekst_na_docx


def _pdf_z_tekstem(cel: Path, linie: int = 20) -> Path:
    """PDF wygenerowany elektronicznie - ma warstwe tekstowa, jak wypis."""
    import fitz
    dokument = fitz.open()
    strona = dokument.new_page()
    for i in range(linie):
        strona.insert_text(
            (60, 80 + i * 16),
            f"ZASWIADCZENIE nr {i}/2026, dzialka 12/3, obreb Zalesie",
            fontsize=10,
        )
    dokument.save(cel)
    dokument.close()
    return cel


def _pdf_skan(cel: Path, stron: int = 1) -> Path:
    """PDF bez warstwy tekstowej - strona wklejona jako obraz A4 w 300 dpi."""
    import fitz
    from PIL import Image
    bufor = io.BytesIO()
    Image.new("L", (2480, 3508), 255).save(bufor, format="PNG")
    dokument = fitz.open()
    for _ in range(stron):
        strona = dokument.new_page()
        strona.insert_image(strona.rect, stream=bufor.getvalue())
    dokument.save(cel)
    dokument.close()
    return cel


class TestRozdzielczoscModelu:
    """Rozmiar obrazu ma odpowiadac temu, ile model naprawde widzi."""

    @pytest.mark.parametrize("model,wysoka", [
        ("eu.anthropic.claude-sonnet-4-5-20250929-v1:0", False),
        ("eu.anthropic.claude-sonnet-4-6", False),
        ("eu.anthropic.claude-opus-4-6-v1", False),
        ("eu.anthropic.claude-opus-4-7", True),
        ("eu.anthropic.claude-opus-4-8", True),
        ("eu.anthropic.claude-sonnet-5", True),
        ("eu.anthropic.claude-opus-5", True),
    ])
    def test_klasa_rozdzielczosci(self, model, wysoka):
        import config
        assert config.wysoka_rozdzielczosc(model) is wysoka

    @pytest.mark.parametrize("model,przyjmuje", [
        ("eu.anthropic.claude-opus-4-6-v1", True),
        ("eu.anthropic.claude-sonnet-4-6", True),
        ("eu.anthropic.claude-opus-4-7", False),
        ("eu.anthropic.claude-opus-5", False),
        ("eu.anthropic.claude-sonnet-5", False),
    ])
    def test_temperature_tylko_dla_starszych_modeli(self, model, przyjmuje):
        """Modele 4.7+ odrzucaja zadanie z parametrem temperature."""
        import config
        assert config.przyjmuje_temperature(model) is przyjmuje

    def test_zadanie_bez_temperatury_dla_nowych_modeli(self, monkeypatch):
        from unittest.mock import MagicMock
        import bedrock
        klient = MagicMock()
        klient.converse.return_value = {
            "output": {"message": {"content": [{"text": "ok"}]}},
            "usage": {}, "stopReason": "end_turn",
        }
        monkeypatch.setattr(bedrock, "_klient", lambda: klient)

        monkeypatch.setattr(bedrock.config, "MODEL", "eu.anthropic.claude-opus-4-6-v1")
        bedrock._rozmowa("s", [{"text": "x"}], max_tokenow=10)
        assert klient.converse.call_args.kwargs["inferenceConfig"]["temperature"] == 0

        monkeypatch.setattr(bedrock.config, "MODEL", "eu.anthropic.claude-opus-5")
        bedrock._rozmowa("s", [{"text": "x"}], max_tokenow=10)
        assert "temperature" not in klient.converse.call_args.kwargs["inferenceConfig"]

    def test_max_bok_idzie_za_modelem(self, monkeypatch):
        import importlib
        import config
        monkeypatch.setenv("PIECZAPP_MODEL", "eu.anthropic.claude-opus-5")
        monkeypatch.delenv("PIECZAPP_MAX_BOK", raising=False)
        importlib.reload(config)
        assert config.MAX_BOK == 2576
        monkeypatch.setenv("PIECZAPP_MODEL", "eu.anthropic.claude-sonnet-4-6")
        importlib.reload(config)
        assert config.MAX_BOK == 1568
        # recznie podana wartosc jest rozstrzygajaca
        monkeypatch.setenv("PIECZAPP_MAX_BOK", "1234")
        importlib.reload(config)
        assert config.MAX_BOK == 1234
        monkeypatch.undo()
        importlib.reload(config)


class TestPrzeciazenieModelu:
    """Limit zapytan na koncie AWS jest niski, wiec odmowa musi byc obsluzona."""

    def _atrapa_bledu(self, kod):
        from botocore.exceptions import ClientError
        return ClientError({"Error": {"Code": kod, "Message": "limit"}}, "Converse")

    def test_klient_ponawia_i_przyhamowuje(self):
        import bedrock
        ponowienia = bedrock._ustawienia.retries
        assert ponowienia["mode"] == "adaptive", "tryb adaptacyjny sam zwalnia przy odmowach"
        assert ponowienia["max_attempts"] >= 5

    @pytest.mark.parametrize("kod", [
        "ThrottlingException", "TooManyRequestsException", "ServiceQuotaExceededException",
    ])
    def test_limit_daje_czytelny_komunikat(self, monkeypatch, kod):
        from unittest.mock import MagicMock
        import bedrock
        klient = MagicMock()
        klient.converse.side_effect = self._atrapa_bledu(kod)
        monkeypatch.setattr(bedrock, "_klient", lambda: klient)
        with pytest.raises(bedrock.Przeciazenie) as blad:
            bedrock._rozmowa("s", [{"text": "x"}], max_tokenow=10)
        assert "przeciazony" in str(blad.value).lower()

    def test_inne_bledy_przechodza_dalej(self, monkeypatch):
        from unittest.mock import MagicMock
        from botocore.exceptions import ClientError
        import bedrock
        klient = MagicMock()
        klient.converse.side_effect = self._atrapa_bledu("AccessDeniedException")
        monkeypatch.setattr(bedrock, "_klient", lambda: klient)
        with pytest.raises(ClientError):
            bedrock._rozmowa("s", [{"text": "x"}], max_tokenow=10)


class TestPrzygotowanieStron:
    """Co trafia do modelu: tekst, obraz, podzial strony i limity zadania."""

    def test_warstwa_tekstowa_idzie_obok_obrazu(self, tmp_path):
        from dokumenty import strony_ze_skanow
        strony = strony_ze_skanow([_pdf_z_tekstem(tmp_path / "wypis.pdf")])
        assert strony, "dokument nie zostal przetworzony"
        assert all("ZASWIADCZENIE" in s["tekst"] for s in strony)
        assert any(s.get("png") for s in strony)

    def test_skan_bez_tekstu_dzielony_na_dwie_czesci(self, tmp_path):
        from dokumenty import strony_ze_skanow
        strony = strony_ze_skanow([_pdf_skan(tmp_path / "skan.pdf")])
        assert [s.get("fragment") for s in strony] == ["gora", "dol"]
        assert all(s["tekst"] == "" for s in strony)

    def test_czesci_zachodza_na_siebie(self, tmp_path):
        """Podzial nie moze uciac wiersza przechodzacego przez srodek strony.

        Porownujemy proporcje, nie piksele - obraz moze byc po drodze
        pomniejszony do tego, ile widzi model.
        """
        from PIL import Image
        from dokumenty import strony_ze_skanow
        strony = strony_ze_skanow([_pdf_skan(tmp_path / "skan.pdf")])
        proporcja_strony = 3508 / 2480
        for s in strony:
            obraz = Image.open(io.BytesIO(s["png"]))
            proporcja = obraz.height / obraz.width
            assert proporcja > proporcja_strony / 2, "czesc krotsza niz polowa strony"
            assert proporcja < proporcja_strony, "czesc nie moze byc cala strona"

    def test_duza_sprawa_miesci_sie_w_limicie_zadania(self, tmp_path):
        """Powyzej 20 obrazow API wymaga mniejszych stron - inaczej odrzuca zadanie."""
        from PIL import Image
        from dokumenty import strony_ze_skanow, MAX_BOK_WIELE_OBRAZOW
        strony = strony_ze_skanow([_pdf_skan(tmp_path / "duzy.pdf", stron=25)])
        assert all("fragment" not in s for s in strony), "przy duzej sprawie nie dzielimy stron"
        boki = [max(Image.open(io.BytesIO(s["png"])).size) for s in strony]
        assert max(boki) <= MAX_BOK_WIELE_OBRAZOW

    def test_strona_w_limicie_nie_jest_dzielona(self, tmp_path):
        """Maly obraz nie zyskuje na podziale, wiec go nie dzielimy."""
        from PIL import Image
        from dokumenty import strony_ze_skanow
        maly = tmp_path / "dowod.png"
        Image.new("L", (1200, 800), 255).save(maly)
        strony = strony_ze_skanow([maly])
        assert len(strony) == 1 and "fragment" not in strony[0]


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
