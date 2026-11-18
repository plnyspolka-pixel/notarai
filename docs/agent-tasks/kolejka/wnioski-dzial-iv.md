---
id: wnioski-dzial-iv
tor: koder
zakres:
  - wnioski_kw.py
  - test_wnioski_kw_dzialy.py
sprawdzenie: python -m pytest -q test_wnioski_kw_dzialy.py
---
# wnioski_kw.DZIALY: literówka w nazwie działu IV

## Stan teraz
W `wnioski_kw.py` słownik `DZIALY` ma wpis `"IV": "Dzial IV - hipoteka"` - bez "ł", inaczej niż pozostałe wpisy ("Dział ...").

## Stan docelowy
`DZIALY["IV"] == "Dział IV - hipoteka"`.

## Testy
Utwórz `test_wnioski_kw_dzialy.py` z testem, że każda wartość `DZIALY` zaczyna się od "Dział " + klucz, oraz że kluczami są dokładnie "I-O", "I-Sp", "II", "III", "IV". Nie zmieniaj niczego poza tym jednym napisem.
