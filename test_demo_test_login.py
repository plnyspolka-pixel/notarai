"""Izolacja konta test/test w dedykowanym serwerze demo NotarAI."""
import pytest

from scripts.demo_odcinek01 import KANCELARIA, ZESPOL, LogowanieDemo, serwer
from logowanie import BladLogowania


def test_test_test_wchodzi_do_fikcyjnej_kancelarii():
    auth = LogowanieDemo("MocneHasloDoPozostalychKont!")
    sesja = auth.zaloguj("test", "test")
    assert auth.sprawdz(sesja["token"]) == {
        "email": ZESPOL[0][0],
        "kancelaria": KANCELARIA,
    }
    odnowiona = auth.odnow(sesja["odnowienie"])
    assert auth.sprawdz(odnowiona["token"])["kancelaria"] == KANCELARIA


@pytest.mark.parametrize("login,haslo", [
    ("test", "inne"),
    ("test", ""),
    ("obcy", "test"),
    ("helena@kancelaria-demo.test", "test"),
])
def test_test_haslo_nie_otwiera_innych_kont(login, haslo):
    auth = LogowanieDemo("MocneHasloDoPozostalychKont!")
    with pytest.raises(BladLogowania):
        auth.zaloguj(login, haslo)


def test_inne_konta_demo_wymagaja_osobnego_hasla():
    auth = LogowanieDemo("MocneHasloDoPozostalychKont!")
    sesja = auth.zaloguj(ZESPOL[1][0], "MocneHasloDoPozostalychKont!")
    assert auth.sprawdz(sesja["token"])["email"] == ZESPOL[1][0]


def test_serwer_demo_odmawia_dostepu_do_chmurowego_magazynu(monkeypatch, tmp_path):
    monkeypatch.setenv("PIECZAPP_MAGAZYN", "s3")
    monkeypatch.delenv("PIECZAPP_COGNITO_POOL", raising=False)
    with pytest.raises(SystemExit, match="tylko lokalnie"):
        serwer(str(tmp_path), "MocneHaslo!", "127.0.0.1", 8000, 0, 0, str(tmp_path))


def test_serwer_demo_odmawia_produkcyjnego_cognito(monkeypatch, tmp_path):
    monkeypatch.setenv("PIECZAPP_MAGAZYN", "lokalny")
    monkeypatch.setenv("PIECZAPP_COGNITO_POOL", "eu-central-1_REAL")
    with pytest.raises(SystemExit, match="bez puli Cognito"):
        serwer(str(tmp_path), "MocneHaslo!", "127.0.0.1", 8000, 0, 0, str(tmp_path))


def test_publiczny_serwer_demo_bez_atrap_odmawia_startu(monkeypatch, tmp_path):
    monkeypatch.setenv("PIECZAPP_MAGAZYN", "lokalny")
    monkeypatch.delenv("PIECZAPP_COGNITO_POOL", raising=False)
    with pytest.raises(SystemExit, match="wymaga --atrapa-modelu"):
        serwer(str(tmp_path), "MocneHaslo!", "0.0.0.0", 8000, None, None, None)
