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
        klient.converse_stream.side_effect = lambda **kw: {"stream": iter([
            {"contentBlockDelta": {"delta": {"text": "ok"}}},
            {"messageStop": {"stopReason": "end_turn"}},
        ])}
        monkeypatch.setattr(bedrock, "_klient", lambda: klient)

        # bez myslenia (np. klikanie) - temperatura 0 tam, gdzie model ja przyjmuje
        monkeypatch.setattr(bedrock.config, "MODEL", "eu.anthropic.claude-opus-4-6-v1")
        bedrock._rozmowa("s", [{"text": "x"}], max_tokenow=10, myslenie=False)
        assert klient.converse_stream.call_args.kwargs["inferenceConfig"]["temperature"] == 0

        monkeypatch.setattr(bedrock.config, "MODEL", "eu.anthropic.claude-opus-5")
        bedrock._rozmowa("s", [{"text": "x"}], max_tokenow=10, myslenie=False)
        assert "temperature" not in klient.converse_stream.call_args.kwargs["inferenceConfig"]

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
        klient.converse_stream.side_effect = self._atrapa_bledu(kod)
        monkeypatch.setattr(bedrock, "_klient", lambda: klient)
        with pytest.raises(bedrock.Przeciazenie) as blad:
            bedrock._rozmowa("s", [{"text": "x"}], max_tokenow=10)
        assert "przeciazony" in str(blad.value).lower()

    def test_inne_bledy_przechodza_dalej(self, monkeypatch):
        from unittest.mock import MagicMock
        from botocore.exceptions import ClientError
        import bedrock
        klient = MagicMock()
        klient.converse_stream.side_effect = self._atrapa_bledu("AccessDeniedException")
        monkeypatch.setattr(bedrock, "_klient", lambda: klient)
        with pytest.raises(ClientError):
            bedrock._rozmowa("s", [{"text": "x"}], max_tokenow=10)


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


def test_projekt_docx_ma_oznaczenie_ai_w_metadanych(tmp_path):
    """Plik niesie maszynowo czytelna informacje, ze powstal z udzialem AI."""
    from docx import Document
    import dokumenty
    cel = dokumenty.tekst_na_docx("AKT NOTARIALNY\n\nTreść projektu.", tmp_path / "projekt.docx")
    wl = Document(cel).core_properties
    assert "sztucznej inteligencji" in wl.comments
    assert "AI-generated" in wl.keywords
    assert wl.author == "notarai"


class TestZnacznikiWWordzie:
    """Znaczniki <<BRAK>> i <<WYBOR>> zostaja w pliku bez zmian, wyroznione
    zakreslaczem - notariusz nie przeoczy ich ani w Wordzie, ani na wydruku."""

    def test_znaczniki_zakreslone_i_tresc_bez_zmian(self, tmp_path):
        from docx import Document
        from docx.enum.text import WD_COLOR_INDEX
        from dokumenty import tekst_na_docx

        tekst = ("§ 1. Irena Nowak oświadcza, że lokal ma powierzchnię <<BRAK: powierzchnia lokalu>> m².\n"
                 "§ 2. Cena zostanie zapłacona <<WYBOR: przelewem przed aktem / gotówką przy akcie>>.")
        cel = tekst_na_docx(tekst, tmp_path / "projekt.docx")
        akapity = [a for a in Document(cel).paragraphs if a.text]
        assert [a.text for a in akapity] == tekst.split("\n")
        przebiegi = {p.text: p for a in akapity for p in a.runs}
        brak = przebiegi["<<BRAK: powierzchnia lokalu>>"]
        wybor = przebiegi["<<WYBOR: przelewem przed aktem / gotówką przy akcie>>"]
        assert brak.font.highlight_color == WD_COLOR_INDEX.YELLOW and brak.bold
        assert wybor.font.highlight_color == WD_COLOR_INDEX.TURQUOISE and wybor.bold
        zwykly = przebiegi["§ 1. Irena Nowak oświadcza, że lokal ma powierzchnię "]
        assert zwykly.font.highlight_color is None and not zwykly.bold


class TestDocxNaWzorze:
    """Projekt w Wordzie powstaje na pliku wzoru: czcionka, kapitaliki, odstepy,
    marginesy i stopka sa kancelarii, a nie domyslne Times New Roman 12."""

    @staticmethod
    def _wzor(tmp_path):
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX
        from docx.shared import Cm, Pt
        d = Document()
        sekcja = d.sections[0]
        sekcja.left_margin = Cm(3)
        sekcja.footer.paragraphs[0].text = "Kancelaria Notarialna - stopka wzoru"
        d.styles["Normal"].font.name = "Garamond"
        d.styles["Normal"].font.size = Pt(13)

        def akapit(tekst, **o):
            p = d.add_paragraph()
            r = p.add_run(tekst)
            r.font.name = "Garamond"
            r.bold = o.get("bold")
            r.italic = o.get("italic")
            r.font.small_caps = o.get("caps")
            if o.get("size"):
                r.font.size = Pt(o["size"])
            if o.get("hl"):
                r.font.highlight_color = WD_COLOR_INDEX.YELLOW
            if o.get("center"):
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if o.get("indent"):
                p.paragraph_format.first_line_indent = Cm(o["indent"])
            return p
        akapit("aaa - zbywca (Jan Kowalski)")
        akapit("")
        akapit("AKT NOTARIALNY", bold=True, caps=True, center=True, size=16)
        akapit("Dnia ?? roku przed notariuszem ?? stawili się:", indent=1.25)
        akapit("§ 1.", bold=True, center=True)
        akapit("aaa oświadcza, że jest właścicielem // współwłaścicielem nieruchomości położonej w ??.", indent=1.25)
        akapit("??", hl=True)
        akapit("Koszty aktu ponosi aaa.", italic=True)
        sciezka = tmp_path / "wzor.docx"
        d.save(sciezka)
        return sciezka

    PROJEKT = ("AKT NOTARIALNY\n"
               "Dnia 13.11.2026 roku przed notariuszem Ewą Przykładową stawili się:\n"
               "§ 1.\n"
               "Jan Kowalski oświadcza, że jest <<WYBOR: właścicielem / współwłaścicielem>> nieruchomości położonej w Zalesiu.\n"
               "§ 2.\n"
               "Cena wynosi <<BRAK: cena>> zł.\n"
               "NOWY NAGŁÓWEK BEZ PARY WE WZORZE\n"
               "Koszty aktu ponosi Jan Kowalski.")

    def test_formatowanie_akapitow_ze_wzoru(self, tmp_path):
        from docx import Document
        from docx.enum.text import WD_COLOR_INDEX
        cel = tekst_na_docx(self.PROJEKT, tmp_path / "projekt.docx", wzor=self._wzor(tmp_path))
        d = Document(cel)
        a = {p.text: p for p in d.paragraphs if p.text.strip()}
        naglowek = a["AKT NOTARIALNY"].runs[0]
        assert naglowek.font.name == "Garamond" and naglowek.font.size.pt == 16
        assert naglowek.bold and naglowek.font.small_caps and a["AKT NOTARIALNY"].alignment == 1
        dnia = a["Dnia 13.11.2026 roku przed notariuszem Ewą Przykładową stawili się:"]
        assert round(dnia.paragraph_format.first_line_indent.cm, 2) == 1.25
        assert a["§ 1."].alignment == 1 and a["§ 1."].runs[0].bold
        assert a["§ 2."].alignment == 1 and a["§ 2."].runs[0].bold, "podobny akapit dostaje te same formatowanie"
        assert a["Koszty aktu ponosi Jan Kowalski."].runs[0].italic
        # znaczniki projektu zakreslone, zakreslenia wzoru nie przeciekaja
        wybor = next(r for r in a["Jan Kowalski oświadcza, że jest <<WYBOR: właścicielem / współwłaścicielem>> nieruchomości położonej w Zalesiu."].runs if "<<WYBOR" in r.text)
        assert wybor.font.highlight_color == WD_COLOR_INDEX.TURQUOISE and wybor.bold
        brak = next(r for r in a["Cena wynosi <<BRAK: cena>> zł."].runs if "<<BRAK" in r.text)
        assert brak.font.highlight_color == WD_COLOR_INDEX.YELLOW
        for p in d.paragraphs:
            for r in p.runs:
                if "<<" not in r.text:
                    assert r.font.highlight_color is None, p.text
        # akapit bez pary: wielkie litery -> naglowek, czcionka dalej wzoru
        nowy = a["NOWY NAGŁÓWEK BEZ PARY WE WZORZE"]
        assert nowy.alignment == 1 and nowy.runs[0].bold and nowy.runs[0].font.name == "Garamond"

    def test_strona_stopka_i_metadane_ai(self, tmp_path):
        from docx import Document
        cel = tekst_na_docx(self.PROJEKT, tmp_path / "projekt.docx", wzor=self._wzor(tmp_path))
        d = Document(cel)
        assert round(d.sections[0].left_margin.cm, 1) == 3.0
        assert d.sections[0].footer.paragraphs[0].text == "Kancelaria Notarialna - stopka wzoru"
        assert "sztucznej inteligencji" in d.core_properties.comments
        assert "aaa - zbywca" not in "\n".join(p.text for p in d.paragraphs), "legenda wzoru nie trafia do projektu"
        assert "??" not in "\n".join(p.text for p in d.paragraphs)

    def test_tresc_projektu_bez_zmian(self, tmp_path):
        cel = tekst_na_docx(self.PROJEKT, tmp_path / "projekt.docx", wzor=self._wzor(tmp_path))
        assert wzor_na_tekst(cel).strip() == self.PROJEKT.strip()

    def test_bez_wzoru_word_zapis_domyslny(self, tmp_path):
        from docx import Document
        (tmp_path / "wzor.txt").write_text("Dnia ?? stawil sie ??", "utf-8")
        for wzor in (None, tmp_path / "wzor.txt", tmp_path / "nie-ma.docx"):
            cel = tekst_na_docx("AKT NOTARIALNY\nTreść.", tmp_path / "p.docx", wzor=wzor)
            d = Document(cel)
            assert d.styles["Normal"].font.name == "Times New Roman"
            assert d.paragraphs[0].runs[0].bold

    def test_uszkodzony_wzor_nie_blokuje_projektu(self, tmp_path):
        zly = tmp_path / "wzor.docx"
        zly.write_bytes(b"to nie jest docx")
        cel = tekst_na_docx("AKT NOTARIALNY\nTreść.", tmp_path / "p.docx", wzor=zly)
        assert "Treść." in wzor_na_tekst(cel)

    def test_numeracja_worda_nie_dubluje_numeru_z_tresci(self, tmp_path):
        from docx import Document
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
        d = Document()
        p = d.add_paragraph("Strona zbywa nieruchomość.")
        numpr = OxmlElement("w:numPr")
        for nazwa, wartosc in (("w:ilvl", "0"), ("w:numId", "1")):
            el = OxmlElement(nazwa)
            el.set(qn("w:val"), wartosc)
            numpr.append(el)
        p._p.get_or_add_pPr().append(numpr)
        assert p._p.find(qn("w:pPr")).find(qn("w:numPr")) is not None
        wzor = tmp_path / "wzor.docx"
        d.save(wzor)
        cel = tekst_na_docx("1. Strona zbywa nieruchomość w Zalesiu.", tmp_path / "p.docx", wzor=wzor)
        akapit = Document(cel).paragraphs[0]
        assert akapit.text.startswith("1. ")
        assert akapit._p.find(qn("w:pPr")).find(qn("w:numPr")) is None
