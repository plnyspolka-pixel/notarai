"""Kontrola zwięzłej karty kodera (W7): karty otwarte, kryteria, „zmiana niepotrzebna”."""
import pytest

from tools.agent_factory.koder import lint_karty as lk


def _k(tytul: str, tresc: str = "") -> dict:
    return {"tytul": tytul, "tresc": f"# {tytul}\n\n{tresc}"}


@pytest.mark.parametrize("tytul, tresc", [
    ("Popraw moduł taksa", ""),
    ("taksa.py: zrefaktoruj kwota", ""),
    ("Dzielenie kwot", "## Stan docelowy\n- ulepsz komunikaty\n"),
    ("Moduł nazwy", "1. Uporządkuj importy\n"),
])
def test_karta_otwarta_bez_kryteriow_odrzucona(tytul, tresc):
    assert any("karta otwarta" in b for b in lk.bledy(_k(tytul, tresc)))


def test_karta_otwarta_z_kryteriami_przechodzi():
    k = _k("Popraw taksa.kwota", '## Kryteria akceptacji\n- "250.000,00 zł" -> Decimal("250000.00")\n')
    assert lk.bledy(k) == []


def test_zamknieta_karta_i_slowa_podobne_przechodza():
    k = _k("taksa.kwota: kropki jako separator tysięcy",
           '- poprawny: `(True, "REGON poprawny")`\n- poprawka wiersza 3\n')
    assert lk.bledy(k) == []


def test_za_duzo_albo_zero_kryteriow():
    za_duzo = _k("A", "## Kryteria akceptacji\n- a\n- b\n- c\n- d\n## Nie ruszaj\n- e\n")
    puste = _k("A", "## Kryteria akceptacji\ntekst bez punktów\n")
    assert any("1-3" in b for b in lk.bledy(za_duzo))
    assert any("1-3" in b for b in lk.bledy(puste))
    assert lk.kryteria(za_duzo["tresc"]) == ["a", "b", "c", "d"]


@pytest.mark.parametrize("tekst, oczekiwane", [
    ("ZMIANA NIEPOTRZEBNA: funkcja już obsługuje kropki", True),
    ("zmiana niepotrzebna:  test już przechodzi", True),
    ("ZMIANA NIEPOTRZEBNA", False),  # bez uzasadnienia nie liczy się
    ("Gotowe, zmieniłem taksa.py", False),
    (None, False),
])
def test_deklaracja_niepotrzebnej(tekst, oczekiwane):
    assert lk.deklaruje_niepotrzebna(tekst) is oczekiwane


def test_wynik_niepotrzebnej():
    assert lk.wynik_niepotrzebnej([], True) == ("niepotrzebna", [])
    assert lk.wynik_niepotrzebnej([], False) == ("odrzucone", ["niepotrzebna_niepotwierdzona"])
    assert lk.wynik_niepotrzebnej(["taksa.py"], True)[0] == "odrzucone"


def test_istniejace_karty_kolejki_nie_sa_otwarte():
    from pathlib import Path
    from tools.agent_factory.koder import karta
    for p in sorted(Path("docs/agent-tasks/kolejka").glob("*.md")):
        assert lk.bledy(karta.wczytaj(p)) == [], p.name
