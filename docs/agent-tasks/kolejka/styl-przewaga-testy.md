---
id: styl-przewaga-testy
tor: koder
zakres:
  - test_styl.py
sprawdzenie: python -m pytest -q test_styl.py
---
# Testy dla styl._przewaga

Utwórz `test_styl.py`. Nie zmieniaj `styl.py`.

Funkcja `_przewaga(licznik, minimum, udzial)` w `styl.py` zwraca `(zwyciezca, ile, wszystkich)`, gdy jeden wariant dominuje, a inaczej None. Sprawdź testami parametryzowanymi:
- suma poniżej `minimum` -> None;
- suma równa `minimum` i udział zwycięzcy dokładnie równy `udzial` -> krotka (granica włączona);
- udział tuż poniżej progu -> None;
- jeden wariant w liczniku -> krotka z ile == wszystkich;
- pusty licznik przy minimum 1 -> None (bez wyjątku).

Jeżeli pusty licznik przy minimum 0 podnosi wyjątek, opisz to w teście jako `xfail`, nie poprawiaj modułu.
