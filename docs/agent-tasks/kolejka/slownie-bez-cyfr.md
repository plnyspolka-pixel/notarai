---
id: slownie-bez-cyfr
tor: koder
zakres:
  - slownie.py
  - test_slownie_bledy.py
sprawdzenie: python -m pytest -q test_slownie_bledy.py
---
# slownie.parsuj_kwote: tekst bez cyfr to błąd, nie zero

## Stan teraz
`slownie.parsuj_kwote("abc")` i `parsuj_kwote("")` zwracają `(0, 0)`, więc `slownie_kwoty("abc")` daje "zero złotych" - pomyłka w danych wygląda jak poprawna kwota.

## Stan docelowy
`parsuj_kwote` podnosi `ValueError("Brak kwoty w tekście")`, gdy tekst nie zawiera żadnej cyfry ("abc", "", "zł", ","). Bez zmian: "0" -> (0, 0); "0,00 zł" -> (0, 0); "250.000,00 zł" -> (250000, 0); ",50" -> (0, 50).

## Testy
Utwórz `test_slownie_bledy.py` z powyższymi przypadkami oraz testem, że `slownie_kwoty("abc")` podnosi ValueError. Nie zmieniaj `liczba_slownie` ani innych modułów.
