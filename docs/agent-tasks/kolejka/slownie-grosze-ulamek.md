---
id: slownie-grosze-ulamek
tor: koder
zakres:
  - slownie.py
  - test_slownie_grosze.py
sprawdzenie: python -m pytest -q test_slownie_grosze.py
---
# slownie.slownie_kwoty: grosze jako ułamek "50/100"

## Stan teraz
`slownie_kwoty("1000,50")` zawsze zapisuje grosze słownie.

## Stan docelowy
Nowy parametr: `slownie_kwoty(tekst, grosze_slownie: bool = True)`.
- Z wartością domyślną wynik jest identyczny jak dotąd.
- Z `grosze_slownie=False` grosze są zapisane jako ułamek z dwiema cyframi: `slownie_kwoty("1000,50", grosze_slownie=False)` kończy się na " 50/100", a `slownie_kwoty("1000,05", grosze_slownie=False)` na " 05/100". Gdy groszy jest 0, ułamek też jest dopisany: " 00/100".

## Testy
Utwórz `test_slownie_grosze.py`: oba tryby dla "1000,50", "1000,05" i "1000" oraz sprawdzenie, że wywołanie bez parametru daje to samo co `slownie_kwoty(tekst, True)`. Nie zmieniaj `parsuj_kwote` ani `liczba_slownie`.
