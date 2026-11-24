"""Walidacja zmian Word bez dostępu do AWS i rzeczywistych dokumentów."""
import pytest
from fastapi import HTTPException

from word_addin import PropozycjaWejscie, zweryfikuj_propozycje

TEXT = "Pierwszy paragraf ma błąd.\nDrugi paragraf jest poprawny."

def test_change_types_and_stale_anchor():
    r=zweryfikuj_propozycje({
        "summary":"Korekta",
        "operations":[
            {"type":"replace","find":"ma błąd","text":"jest poprawny"},
            {"type":"insert_after","find":"Drugi paragraf","text":" (zmieniony)"},
            {"type":"format","find":"Drugi paragraf","format":{"bold":True}},
            {"type":"append","text":"Nowy paragraf"}
        ]}, TEXT, "", "document")
    assert len(r["operations"])==4

def test_duplicate_and_missing_anchor_rejected():
    with pytest.raises(ValueError):
        zweryfikuj_propozycje({"summary":"","operations":[{"type":"delete","find":"paragraf"}]},TEXT,"","document")
    with pytest.raises(ValueError):
        zweryfikuj_propozycje({"summary":"","operations":[{"type":"delete","find":"PESEL"}]},TEXT,"","document")

def test_selection_scope_must_include_find():
    with pytest.raises(ValueError):
        zweryfikuj_propozycje({"summary":"","operations":[{"type":"delete","find":"Drugi paragraf"}]},
                              TEXT,"Pierwszy paragraf","selection")

def test_scope_does_not_allow_append_to_selection():
    with pytest.raises(ValueError):
        zweryfikuj_propozycje({"summary":"","operations":[{"type":"append","text":"x"}]},
                              TEXT,"Pierwszy paragraf","selection")

def test_untrusted_format_and_long_anchor_rejected():
    with pytest.raises(ValueError):
        zweryfikuj_propozycje({"summary":"","operations":[{"type":"format","find":"Pierwszy","format":{"script":"eval"}}]},
                              TEXT,"","document")
    with pytest.raises(ValueError):
        zweryfikuj_propozycje({"summary":"","operations":[{"type":"replace","find":"Pierwszy","text":"x", "format":{}}]},
                              TEXT,"","selection")

def test_unchanged_read_only_and_no_auto_write():
    from pathlib import Path
    file=Path(__file__).parent/"word_addin.py"
    s=file.read_text("utf-8")
    assert "insertText" not in s
    assert "document_text" in s
    assert '"projekt"' in (Path(__file__).parent/"stanowiska.py").read_text("utf-8")
    assert "word" in (Path(__file__).parent/"app.py").read_text("utf-8")

def test_draft_flag_required_server_side():
    from word_addin import propozycja
    class R: pass
    request=R();request.state=R();request.state.email="notariusz@example.test";request.state.serwis=False
    data=PropozycjaWejscie(document_text=TEXT,scope="document",instruction="Popraw tekst")
    with pytest.raises(HTTPException) as ex:
        propozycja(data,request)
    assert ex.value.status_code==400
