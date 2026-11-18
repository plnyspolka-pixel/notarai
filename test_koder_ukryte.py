"""Ukryte testy karty (W6): kontrola przed pracą agenta i ocena po niej - bez Dockera."""
import difflib
from pathlib import Path

import pytest

from tools.agent_factory.koder import karta, ukryte

DOBRY = "def podwoj(x):\n    return 2 * x\n"
ZLY = "def podwoj(x):\n    return x + 2\n"  # przypadkiem dobre dla x == 2
UKRYTY_TEST = "from modul import podwoj\n\n\ndef test_podwoj():\n    assert podwoj(3) == 6\n    assert podwoj(-1) == -2\n"
SLABY_UKRYTY = "from modul import podwoj\n\n\ndef test_podwoj():\n    assert podwoj(2) == 4\n"


@pytest.fixture(autouse=True)
def lokalnie(monkeypatch):
    monkeypatch.setenv("KODER_OCENA", "lokalnie")


def _latka(stary: str, nowy: str) -> str:
    return "".join(difflib.unified_diff(stary.splitlines(True), nowy.splitlines(True),
                                        fromfile="a/modul.py", tofile="b/modul.py"))


def _uklad(tmp_path: Path, rodzaj: str, testy: dict | None = None, latki: dict | None = None,
           sprawdzenie: str = "test_modul.py") -> dict:
    kolejka = tmp_path / "docs" / "agent-tasks" / "kolejka"
    kat = kolejka.parent / "ukryte" / "probna"
    kolejka.mkdir(parents=True)
    kat.mkdir(parents=True)
    for nazwa, tresc in (testy or {}).items():
        (kat / nazwa).write_text(tresc, encoding="utf-8")
    for nazwa, tresc in (latki or {}).items():
        (kat / nazwa).write_text(tresc, encoding="utf-8")
    (kolejka / "probna.md").write_text(
        f"---\nid: probna\ntor: koder\nrodzaj: {rodzaj}\nzakres:\n  - modul.py\n  - test_modul.py\n"
        f"sprawdzenie: python -m pytest -q {sprawdzenie}\n---\n# Próba\n\nTreść.\n", encoding="utf-8")
    return karta.wczytaj(kolejka / "probna.md")


def _repo(tmp_path: Path, nazwa: str, modul: str, testy_agenta: str | None = None) -> Path:
    r = tmp_path / nazwa
    r.mkdir()
    (r / "modul.py").write_text(modul, encoding="utf-8")
    if testy_agenta is not None:
        (r / "test_modul.py").write_text(testy_agenta, encoding="utf-8")
    return r


@pytest.fixture
def robocze(tmp_path):
    r = tmp_path / "ocena"
    r.mkdir()
    return r


def test_zmiana_dobra_karta_i_ocena_pracy(tmp_path, robocze):
    k = _uklad(tmp_path, "zmiana", {"test_ukryty.py": UKRYTY_TEST})
    assert karta.bledy(k) == []
    baza = _repo(tmp_path, "baza", ZLY)
    assert ukryte.przed(k, baza, robocze)["ok"] is True
    assert ukryte.po(k, _repo(tmp_path, "dobra", DOBRY), robocze)["ukryte_zaliczone"] is True
    # agent "dopasował się" do widocznego przypadku - ukryte testy to łapią
    assert ukryte.po(k, _repo(tmp_path, "dopasowana", ZLY), robocze)["ukryte_zaliczone"] is False


def test_zmiana_ukryty_test_przechodzacy_na_bazie_to_karta_wadliwa(tmp_path, robocze):
    k = _uklad(tmp_path, "zmiana", {"test_ukryty.py": SLABY_UKRYTY})
    wynik = ukryte.przed(k, _repo(tmp_path, "baza", ZLY), robocze)
    assert wynik["ok"] is False and "niczego nie sprawdzają" in wynik["powod"]


def test_zmiana_latka_sabotazu_ktora_przechodzi_ukryte_to_karta_wadliwa(tmp_path, robocze):
    # baza bez funkcji: ukryte testy oblewają; łatka-sabotaż „x + 2” przechodzi słaby test
    k = _uklad(tmp_path, "zmiana", {"test_ukryty.py": SLABY_UKRYTY}, {"zly.patch": _latka("", ZLY)})
    wynik = ukryte.przed(k, _repo(tmp_path, "baza", ""), robocze)
    assert wynik["ok"] is False and "zly.patch" in wynik["powod"]


def test_refaktor_ukryte_przechodza_na_bazie_a_sabotaz_je_oblewa(tmp_path, robocze):
    k = _uklad(tmp_path, "refaktor", {"test_ukryty.py": UKRYTY_TEST}, {"zly.patch": _latka(DOBRY, ZLY)})
    assert karta.bledy(k) == []
    assert ukryte.przed(k, _repo(tmp_path, "baza", DOBRY), robocze)["ok"] is True
    assert ukryte.po(k, _repo(tmp_path, "praca", DOBRY), robocze)["ukryte_zaliczone"] is True


def test_refaktor_sabotaz_niewykryty_to_karta_wadliwa(tmp_path, robocze):
    k = _uklad(tmp_path, "refaktor", {"test_ukryty.py": SLABY_UKRYTY}, {"zly.patch": _latka(DOBRY, ZLY)})
    assert ukryte.przed(k, _repo(tmp_path, "baza", DOBRY), robocze)["ok"] is False


def test_karta_testy_mutacje_wykryte_przez_testy_agenta(tmp_path, robocze):
    k = _uklad(tmp_path, "testy", latki={"zly.patch": _latka(DOBRY, ZLY)})
    assert karta.bledy(k) == []
    assert ukryte.przed(k, _repo(tmp_path, "baza", DOBRY), robocze)["ok"] is True
    mocne = _repo(tmp_path, "mocne", DOBRY, "from modul import podwoj\n\n\ndef test_a():\n    assert podwoj(5) == 10\n")
    wynik = ukryte.po(k, mocne, robocze)
    assert wynik["ukryte_zaliczone"] is True and wynik["wykryte"] == "1/1"
    slabe = _repo(tmp_path, "slabe", DOBRY, "from modul import podwoj\n\n\ndef test_a():\n    assert podwoj(2) == 4\n")
    wynik = ukryte.po(k, slabe, robocze)
    assert wynik["ukryte_zaliczone"] is False and wynik["wykryte"] == "0/1"


def test_latka_niepasujaca_do_bazy_to_karta_wadliwa(tmp_path, robocze):
    k = _uklad(tmp_path, "testy", latki={"zly.patch": _latka("def inna():\n    pass\n", ZLY)})
    wynik = ukryte.przed(k, _repo(tmp_path, "baza", DOBRY), robocze)
    assert wynik["ok"] is False and "nie pasuje" in wynik["powod"]


def test_ocena_nie_zmienia_katalogu_pracy_agenta(tmp_path, robocze):
    k = _uklad(tmp_path, "zmiana", {"test_ukryty.py": UKRYTY_TEST})
    praca = _repo(tmp_path, "praca", DOBRY)
    przed_plikami = sorted(p.name for p in praca.iterdir())
    ukryte.po(k, praca, robocze)
    assert sorted(p.name for p in praca.iterdir()) == przed_plikami  # ukryte testy nie trafiają do commita
