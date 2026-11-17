"""Bramka nowych zależności kodera (W3/K5): diff z nieznanym importem jest odrzucany."""
import io
from pathlib import Path

from tools.agent_factory.koder import bramka_zaleznosci as bz


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "taksa.py").write_text("import re\nfrom decimal import Decimal\n", encoding="utf-8")
    (tmp_path / "tools").mkdir()
    (tmp_path / "requirements.txt").write_text(
        "fastapi==0.115.6\nuvicorn[standard]==0.34.0\nPillow>=11\n# komentarz\nPyJWT[crypto]>=2.10\n"
        "beautifulsoup4\npython-docx==1.1.2\n", encoding="utf-8")
    return tmp_path


def _diff(plik: str, *dodane: str, nowy: bool = False) -> str:
    glowa = f"--- {'/dev/null' if nowy else 'a/' + plik}\n+++ b/{plik}\n@@ -1,2 +1,3 @@\n"
    return glowa + "".join(f"+{w}\n" for w in dodane) + " import re\n"


def test_nieznany_import_odrzucony(tmp_path):
    n = bz.sprawdz_diff(_diff("taksa.py", "import requests_magic", "from zmyslona.pod import x"), _repo(tmp_path))
    assert [(x.plik, x.modul, x.powod) for x in n] == [
        ("taksa.py", "requests_magic", "nowa_zaleznosc"), ("taksa.py", "zmyslona", "nowa_zaleznosc")]


def test_stdlib_lokalne_i_wymagania_przechodza(tmp_path):
    diff = _diff("taksa.py", "import json, os.path as p", "from collections import OrderedDict",
                 "import fastapi", "from PIL import Image", "import jwt", "import bs4", "import docx",
                 "import uvicorn", "from tools.agent_factory import runner", "import taksa",
                 "from . import cos", "    import typing  # wcięty")
    assert bz.sprawdz_diff(diff, _repo(tmp_path)) == []


def test_nowy_plik_z_tego_samego_diffu_jest_lokalny(tmp_path):
    diff = _diff("pomocnik_nowy.py", "X = 1", nowy=True) + _diff("taksa.py", "import pomocnik_nowy")
    assert bz.sprawdz_diff(diff, _repo(tmp_path)) == []


def test_import_juz_obecny_w_bazie_nie_jest_nowy(tmp_path):
    repo = _repo(tmp_path)
    (repo / "stary.py").write_text("import numpy_dawne\n", encoding="utf-8")
    assert bz.sprawdz_diff(_diff("stary.py", "import numpy_dawne"), repo) == []


def test_pliki_inne_niz_py_i_wiersze_usuniete_pomijane(tmp_path):
    diff = ("--- a/README.md\n+++ b/README.md\n+import nieistniejacy\n"
            "--- a/taksa.py\n+++ b/taksa.py\n-import kasowany_modul\n")
    assert bz.sprawdz_diff(diff, _repo(tmp_path)) == []


def test_cli_kod_1_przy_naruszeniu(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(_diff("taksa.py", "import halucynacja")))
    assert bz.main([str(_repo(tmp_path))]) == 1
    assert '"modul": "halucynacja"' in capsys.readouterr().out
