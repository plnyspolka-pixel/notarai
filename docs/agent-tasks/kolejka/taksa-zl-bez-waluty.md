---
id: taksa-zl-bez-waluty
tor: koder
zakres:
  - taksa.py
  - test_taksa.py
sprawdzenie: python -m pytest -q test_taksa.py
---
# taksa.zl: opcja bez dopisku waluty

## Stan teraz
`taksa.zl(1234.5)` zwraca "1 234,50 zł" z twardymi spacjami (U+00A0) jako separatorem tysięcy i przed "zł".

## Stan docelowy
Nowy parametr: `zl(x, waluta: bool = True)`. Z `waluta=False` wynik to sama liczba bez końcowej twardej spacji i "zł". Wywołania bez parametru zwracają dokładnie to, co dotąd.

## Testy
Dopisz do `test_taksa.py`: `zl(0, waluta=False) == "0,00"`, wynik dla 1234.5 i 1000000 z `waluta=False`, oraz że `zl(x) == zl(x, waluta=False) + "\u00a0zł"` dla tych trzech wartości. Istniejące testy mają przechodzić; nie zmieniaj innych funkcji.
