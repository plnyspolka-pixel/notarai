---
id: nazwy-max-dlugosc
tor: koder
zakres:
  - nazwy.py
  - test_nazwy.py
sprawdzenie: python -m pytest -q test_nazwy.py
---
# nazwy.bezpieczna_nazwa_pliku: limit długości jako parametr

## Stan teraz
`bezpieczna_nazwa_pliku(tekst)` w `nazwy.py` przycina wynik do stałej `MAX_DLUGOSC_NAZWY`.

## Stan docelowy
Nowy parametr: `bezpieczna_nazwa_pliku(tekst, max_dlugosc: int = MAX_DLUGOSC_NAZWY)`. Przycięcie używa parametru; po przycięciu z końca dalej usuwane są spacje, kropki, myślniki i podkreślenia (jak dotąd). Wywołania bez parametru działają bez zmian.

## Testy
Dopisz do `test_nazwy.py`: tekst z 50 liter "a" przy `max_dlugosc=10` daje 10 znaków; "Kowalski - Nowak" przy `max_dlugosc=11` daje "Kowalski" (końcowe " -" znika); wynik bez parametru równa się wynikowi z `max_dlugosc=nazwy.MAX_DLUGOSC_NAZWY`. Istniejące testy mają przechodzić.
