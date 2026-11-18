---
id: kategorie-granice-slow
tor: koder
zakres:
  - kategorie.py
  - test_kategorie_zakres.py
sprawdzenie: python -m pytest -q test_kategorie_zakres.py
---
# kategorie.rodzaje_w_zdaniu: fałszywe trafienia w środku słowa

## Stan teraz
W `kategorie.py`, lista `_ZAKRES_RODZAJOW`: wzorzec dla "sprzedaz_rolna" (`roln`) trafia w słowo "kontrolna", a wzorzec dla "spolka" (`spolk|spolek`) w "wspolkupujacy".
- `rodzaje_w_zdaniu("cyfra kontrolna KW")` zwraca `["sprzedaz_rolna"]`
- `rodzaje_w_zdaniu("współkupujący")` zwraca `["spolka"]`

## Stan docelowy
Oba wywołania zwracają `[]`. Te dwa wzorce mają trafiać tylko na początku słowa (granica słowa `\b` przed wzorcem). Dalej muszą działać:
- `rodzaje_w_zdaniu("sprzedaż nieruchomości rolnej")` zawiera "sprzedaz_rolna" i "sprzedaz"
- `rodzaje_w_zdaniu("umowa spółki z o.o.")` zwraca `["spolka"]`
- `rodzaje_w_zdaniu("udziały w spółkach")` zawiera "spolka"

## Testy
Utwórz `test_kategorie_zakres.py` z powyższymi pięcioma przypadkami. Zmień tylko te dwa wzorce; pozostałych pozycji listy nie ruszaj.
