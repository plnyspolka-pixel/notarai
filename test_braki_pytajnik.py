"""Ustawienie kancelarii: brakujace dane w pliku Word jako "?" zamiast <<BRAK: ...>>.

Zgloszenie kancelarii 23.11.2026: "tylko zeby zostawial znak zapytania".
"""
from docx import Document
from docx.enum.text import WD_COLOR_INDEX
import pytest

import dokumenty
import ustawienia_kancelarii

PROJEKT = ("1. Adam Testowy (dowód osobisty nr <<BRAK: numer dowodu osobistego>>, ważny do dnia "
           "<<BRAK: data ważności dowodu>>), zamieszkały <<BRAK: adres>>.\n"
           "Strony wybierają <<WYBOR: sąd właściwy>>.")


def _przebiegi(sciezka):
    return [r for p in Document(str(sciezka)).paragraphs for r in p.runs]


def test_pytajnik_zamiast_opisu_braku(tmp_path):
    cel = dokumenty.tekst_na_docx(PROJEKT, tmp_path / "p.docx", braki="pytajnik")
    tekst = "".join(r.text for r in _przebiegi(cel))
    assert "<<BRAK" not in tekst
    assert "dowód osobisty nr ?, ważny do dnia ?)" in tekst
    pytajniki = [r for r in _przebiegi(cel) if r.text == "?"]
    assert len(pytajniki) == 3
    assert all(r.font.highlight_color == WD_COLOR_INDEX.YELLOW and r.bold for r in pytajniki)
    # wybor wariantu to nie brak danych - zostaje z opisem
    assert "<<WYBOR: sąd właściwy>>" in tekst


def test_domyslnie_opis_braku_jak_dotad(tmp_path):
    cel = dokumenty.tekst_na_docx(PROJEKT, tmp_path / "p.docx")
    assert "<<BRAK: numer dowodu osobistego>>" in "".join(r.text for r in _przebiegi(cel))


def test_ustawienie_kancelarii(monkeypatch):
    zapisane = {}
    monkeypatch.setattr(ustawienia_kancelarii.magazyn, "zmien_plik_kancelarii",
                        lambda plik, f, d: zapisane.setdefault("w", f(dict(d))))
    assert ustawienia_kancelarii.domyslne()["braki"] == "opis"
    assert ustawienia_kancelarii.zapisz({"braki": "pytajnik"})["braki"] == "pytajnik"
    with pytest.raises(ValueError):
        ustawienia_kancelarii.zapisz({"braki": "cokolwiek"})
    assert ustawienia_kancelarii._oczysc({"braki": "zle"})["braki"] == "opis"
