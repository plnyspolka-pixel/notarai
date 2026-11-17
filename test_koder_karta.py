"""Kontrola kart zadań kodera: format i reguła przydziału toru."""
from pathlib import Path

import pytest

from tools.agent_factory.koder import karta

DOBRA = """---
id: przyklad-ok
tor: koder
zakres:
  - taksa.py
  - test_taksa.py
sprawdzenie: python -m pytest -q test_taksa.py
---
# Tytuł zadania

Treść.
"""


def _karta(tmp_path: Path, tekst: str, nazwa: str = "przyklad-ok.md", ukryte: bool = True) -> dict:
    kolejka = tmp_path / "docs" / "agent-tasks" / "kolejka"
    kolejka.mkdir(parents=True, exist_ok=True)
    if ukryte:
        kat = kolejka.parent / "ukryte" / Path(nazwa).stem
        kat.mkdir(parents=True, exist_ok=True)
        (kat / "test_ukryty.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")
    p = kolejka / nazwa
    p.write_text(tekst, encoding="utf-8")
    return karta.wczytaj(p)


def test_dobra_karta_przechodzi_i_buduje_polecenie(tmp_path):
    k = _karta(tmp_path, DOBRA)
    assert karta.bledy(k) == []
    tekst = karta.polecenie(k)
    assert "- taksa.py" in tekst and "python -m pytest -q test_taksa.py" in tekst
    assert "Zasady pracy" in tekst


@pytest.mark.parametrize("zamiana, fragment", [
    (("  - taksa.py", "  - autoryzacja.py"), "zastrzeżony"),
    (("  - taksa.py", "  - infra/notarai-aplikacja.yaml"), "zastrzeżony"),
    (("  - taksa.py", "  - *.py"), "bez gwiazdek"),
    (("  - taksa.py", "  - ../poza.py"), "bez gwiazdek"),
    (("sprawdzenie: python -m pytest -q test_taksa.py", "sprawdzenie: bash skrypt.sh"), "sprawdzenie"),
    (("id: przyklad-ok", "id: Inna Nazwa"), "id:"),
    (("tor: koder", "tor: gpu"), "tor:"),
])
def test_karta_lamiaca_regule_jest_odrzucana(tmp_path, zamiana, fragment):
    k = _karta(tmp_path, DOBRA.replace(*zamiana))
    assert any(fragment in b for b in karta.bledy(k))


def test_za_duzo_plikow_to_zadanie_dla_claude(tmp_path):
    wiecej = DOBRA.replace("  - test_taksa.py", "  - test_taksa.py\n  - a.py\n  - b.py\n  - c.py")
    assert any("ponad" in b for b in karta.bledy(_karta(tmp_path, wiecej)))


def test_tor_claude_nie_wymaga_zakresu_ani_testu(tmp_path):
    tekst = "---\nid: przyklad-ok\ntor: claude\n---\n# Projekt zmiany w logowaniu\n\nOpis.\n"
    assert karta.bledy(_karta(tmp_path, tekst)) == []


def test_pliki_poza_zakresem(tmp_path):
    k = _karta(tmp_path, DOBRA)
    assert karta.poza_zakresem(k, ["taksa.py", "app.py", "test_taksa.py"]) == ["app.py"]


def test_brak_naglowka(tmp_path):
    with pytest.raises(karta.BladKarty):
        _karta(tmp_path, "# Samo zadanie\n")


def test_karta_koder_bez_ukrytych_testow_jest_odrzucana(tmp_path):
    k = _karta(tmp_path, DOBRA, ukryte=False)
    assert any("ukrytych testów" in b for b in karta.bledy(k))


def test_karta_testy_wymaga_latki_sabotazu(tmp_path):
    k = _karta(tmp_path, DOBRA.replace("---\n# Tytuł", "rodzaj: testy\n---\n# Tytuł"))
    assert any("łatek sabotażu" in b for b in karta.bledy(k))


def test_agent_nie_dostaje_katalogu_zadan_w_zakresie(tmp_path):
    k = _karta(tmp_path, DOBRA.replace("  - taksa.py", "  - docs/agent-tasks/ukryte/x.py"))
    assert any("zastrzeżony" in b for b in karta.bledy(k))
