---
id: wnioski-repc-testy
tor: koder
zakres:
  - test_wnioski_kw.py
sprawdzenie: python -m pytest -q test_wnioski_kw.py
---
# Testy dla wnioski_kw: numer REP.C i opłata sądowa

Moduł `wnioski_kw.py` nie ma testów. Utwórz `test_wnioski_kw.py`. Nie zmieniaj `wnioski_kw.py`.

- `normalizuj_rep_c(tekst)`: "rep.c/nota/1234/26" -> "REP.C/NOTA/1234/26"; "rep.c nota 001234 26" -> "REP.C/NOTA/1234/26" (zera wiodące znikają); inny kod podmiotu niż NOTA podnosi ValueError; napis bez roku, pusty napis i None podnoszą ValueError.
- `oplata(zadania)`: lista słowników z kluczami "oplata" i "opis". Klucze opłat weź z `taksa.OPLATY_SADOWE` i porównuj z kwotami z tego słownika, nie wpisuj kwot na sztywno. Sprawdź: suma dwóch żądań, pominięcie żądania z `"oplata": None`, pusta lista daje "0.00" i brak pozycji, pole "razem" jest napisem z dwoma miejscami po przecinku.
