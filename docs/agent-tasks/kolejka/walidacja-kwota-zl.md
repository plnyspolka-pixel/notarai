---
id: walidacja-kwota-zl
tor: koder
zakres:
  - walidacja.py
  - test_walidacja.py
sprawdzenie: python -m pytest -q test_walidacja.py
---
# walidacja.kwota: akceptuj "zł" na końcu kwoty

## Stan teraz
`walidacja.kwota("1 234,56 zł")` zwraca `(False, "Nie udalo sie odczytac kwoty")`, bo funkcja usuwa z końca tylko "zl" i "PLN", a nie "zł".

## Stan docelowy
Funkcja `kwota` w `walidacja.py` usuwa z końca "zł", "zl" i "PLN" (bez względu na wielkość liter), także z kropką na końcu. Przykłady:
- "1 234,56 zł" -> (True, "1234.56 zl")
- "1234,56 ZŁ." -> (True, "1234.56 zl")
- "500 PLN" -> (True, "500.00 zl")
- "abc zł" -> (False, "Nie udalo sie odczytac kwoty")
- "-5 zł" -> (False, "Kwota ujemna")

## Testy
Dopisz te przypadki do `test_walidacja.py`. Istniejące testy mają przechodzić. Nie zmieniaj komunikatów ani innych funkcji.
