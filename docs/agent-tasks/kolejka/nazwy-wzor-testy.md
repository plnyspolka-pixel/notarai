---
id: nazwy-wzor-testy
tor: koder
zakres:
  - test_nazwy.py
sprawdzenie: python -m pytest -q test_nazwy.py
---
# Testy dla nazwy.wypelnij_wzor_nazwy

Funkcja `wypelnij_wzor_nazwy(wzor, wartosci)` w `nazwy.py` nie ma bezpośrednich testów. Dopisz je na końcu `test_nazwy.py`. Nie zmieniaj `nazwy.py`.

Przeczytaj funkcję i stałe, z których korzysta (`_POLE_WZORU`, `_SEPARATOR`, `_PUSTE`, `DOMYSLNY_WZOR_NAZWY`). Sprawdź testami:
- wszystkie pola wypełnione: wynik zawiera wartości w kolejności wzoru;
- puste pole w środku znika razem z separatorem przed sobą ("A - <puste> - B" daje "A - B");
- puste pole na początku znika razem z separatorem za sobą;
- pole spoza słownika `wartosci` zachowuje się jak puste;
- pusty `wzor` oznacza użycie `DOMYSLNY_WZOR_NAZWY`;
- znaki niedozwolone w nazwie pliku w wartości pola (np. `/` i `:`) nie trafiają do wyniku.

Istniejące testy w pliku mają dalej przechodzić.
