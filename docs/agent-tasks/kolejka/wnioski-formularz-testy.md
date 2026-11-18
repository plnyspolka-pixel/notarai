---
id: wnioski-formularz-testy
tor: koder
zakres:
  - test_wnioski_kw_formularz.py
sprawdzenie: python -m pytest -q test_wnioski_kw_formularz.py
---
# Testy dla wnioski_kw: dane formularza i kroki portalu

Utwórz `test_wnioski_kw_formularz.py`. Nie zmieniaj `wnioski_kw.py`.

Przeczytaj w `wnioski_kw.py` funkcje `przygotuj()`, `dane_formularza(wniosek)` i `pakiet_portalu(wniosek)`. Zbuduj poprawny wniosek przez `przygotuj()` na danych zmyślonych (żadnych prawdziwych osób ani numerów) i sprawdź:
- `dane_formularza`: dla dwóch uczestników i dwóch żądań istnieją klucze `uczestnik_1_*`, `uczestnik_2_*`, `zadanie_1_*`, `zadanie_2_*`, a wartości odpowiadają danym wejściowym;
- `pakiet_portalu`: zwraca listę kroków w stałej kolejności, a ostatni krok to zatrzymanie przed podpisem i wysłaniem (porównaj z tekstem w kodzie);
- wniosek z brakami (np. bez uczestników) ma `gotowy == False` i niepustą listę `braki`.
