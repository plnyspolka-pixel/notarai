---
id: klauzule-zapora-testy
tor: koder
zakres:
  - test_klauzule.py
sprawdzenie: python -m pytest -q test_klauzule.py
---
# Testy dla klauzule.py: zapora danych osobowych, podobieństwo, pola szkieletu

Utwórz `test_klauzule.py`. Nie zmieniaj `klauzule.py`. Wszystkie dane w testach mają być zmyślone.

- `ma_dane_osobowe(tekst)`: True dla 11 cyfr pod rząd, numeru księgi w postaci "KR1K/00012345/7", numeru dowodu "ABC123456" i "ABC 123456", adresu e-mail; False dla szkieletu z samymi polami w klamrach, dla 10 i 12 cyfr, dla pustego napisu i None.
- `podobienstwo(a, b)`: 1.0 dla identycznych zdań, także różniących się tylko polskimi znakami i wielkością liter; 0.0, gdy którakolwiek strona jest pusta; wartość między 0 a 1 dla zdań częściowo wspólnych; funkcja jest symetryczna.
- `pola_szkieletu(s)`: zwraca posortowane, niepowtarzające się nazwy pól w klamrach; pusta lista dla tekstu bez pól i dla None. Format pola sprawdź w wyrażeniu `_KLAMRY`.
