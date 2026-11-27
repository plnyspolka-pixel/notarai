"""The AWS function for land registers runs V1's ekw.py unchanged, behind a thin shim."""
import importlib
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1] / "rejestry"
REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def function(monkeypatch, tmp_path):
    # The packaged layout: handler, shims and V1 modules side by side.
    for name in ("config", "rejestry", "ekw", "walidacja", "handler"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.syspath_prepend(str(REPO))
    monkeypatch.syspath_prepend(str(HERE / "shim"))
    monkeypatch.syspath_prepend(str(HERE))
    handler = importlib.import_module("handler")
    monkeypatch.setattr(handler, "_ready", True)
    yield handler
    for name in ("config", "rejestry", "ekw", "walidacja", "handler"):
        sys.modules.pop(name, None)


def test_a_book_comes_back_as_sections_and_text(function, monkeypatch):
    import ekw
    assert Path(ekw.__file__).parent == REPO                        # V1's own module, not a copy
    book = {"numer_kw": "WA4M/00160286/2", "dzialy": [{"oznaczenie": "II", "tytul": "Dział II", "pusty": False,
                                                       "tekst": "JAN TESTOWY"}], "zrodlo": "test"}
    monkeypatch.setattr(ekw, "pobierz", lambda numer: book)
    monkeypatch.setattr(ekw, "do_tekstu", lambda ksiega: "DZIAŁ II\nJAN TESTOWY")
    answer = function.handler({"rejestr": "kw", "numer": "WA4M/00160286/2"}, None)
    assert answer == {"ok": True, "ksiega": book, "tekst": "DZIAŁ II\nJAN TESTOWY", "zrodlo": "test"}


def test_errors_are_plain_and_carry_no_data(function, monkeypatch):
    import ekw

    def missing(numer):
        raise ekw.BladEKW("nie_znaleziono", "Ksiegi o tym numerze nie ma w rejestrze")
    monkeypatch.setattr(ekw, "pobierz", missing)
    assert function.handler({"rejestr": "kw", "numer": "WA4M/00160286/2"}, None)["kod"] == "nie_znaleziono"
    assert function.handler({"rejestr": "kw", "numer": "zly"}, None)["kod"] in {"zly_numer", "nie_znaleziono"}
    assert function.handler({"numer": 5}, None)["kod"] == "zle_zadanie"

    def crash(numer):
        raise RuntimeError("JAN TESTOWY 44051401359")
    monkeypatch.setattr(ekw, "pobierz", crash)
    answer = function.handler({"rejestr": "kw", "numer": "WA4M/00160286/2"}, None)
    assert answer["kod"] == "niedostepny" and "TESTOWY" not in json.dumps(answer)


def test_a_wrong_number_is_refused_by_v1_validation(function):
    answer = function.handler({"rejestr": "kw", "numer": "WA4M/00160286/9"}, None)
    assert answer["ok"] is False and answer["kod"] == "zly_numer"
