---
id: slownie-testy
tor: koder
zakres:
  - test_slownie.py
sprawdzenie: python -m pytest -q test_slownie.py
---
# Testy dla slownie.py (liczba słownie i odczyt kwoty)

Moduł `slownie.py` nie ma żadnych testów. Utwórz `test_slownie.py`. Nie zmieniaj `slownie.py`.

Przeczytaj `slownie.py` i pokryj testami:
- `liczba_slownie(n)`: 0 -> "zero"; 1000 -> "tysiąc" (nie "jeden tysiąc"); 2000, 5000, 21, 115, 1000000; liczba ujemna zaczyna się od "minus "; liczba >= 10**12 podnosi ValueError.
- `parsuj_kwote(tekst)`: "250.000,00 zł" -> (250000, 0); "250 000,5" -> (250000, 50); "1000" -> (1000, 0); "1,5" -> (1, 50).
- `slownie_kwoty(tekst)`: poprawna odmiana złoty/złote/złotych i grosz/grosze/groszy dla 1, 2, 5, 22 oraz brak groszy, gdy jest ich 0.

Oczekiwane napisy ustal uruchamiając funkcje i sprawdź z regułami polszczyzny. Jeżeli wynik funkcji wygląda na błąd, nie poprawiaj modułu, tylko oznacz przypadek `pytest.mark.xfail` z opisem.
