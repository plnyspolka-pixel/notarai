---
id: kategorie-nazwy-testy
tor: koder
zakres:
  - test_kategorie.py
sprawdzenie: python -m pytest -q test_kategorie.py
---
# Testy dla kategorie.py: bez_ogonkow i nazwy słownikowe

Moduł `kategorie.py` nie ma własnego pliku testów. Utwórz `test_kategorie.py`. Nie zmieniaj `kategorie.py`.

- `bez_ogonkow(tekst)`: "Stawający ŁĄKA" -> "stawajacy laka"; "Żółć" -> "zolc"; None -> ""; "" -> ""; tekst bez polskich znaków wraca małymi literami.
- `nazwa_rodzaju`, `nazwa_czesci`, `nazwa_obszaru`: dla klucza istniejącego w `RODZAJE` / `CZESCI` / `OBSZARY` zwracają nazwę ze słownika (weź pierwszy klucz ze słownika, nie wpisuj nazw na sztywno); dla nieznanego klucza zwracają odpowiednio `NAZWA_INNEGO`, `NAZWA_INNEJ` i nazwę obszaru "inne".
- każda pozycja `RODZAJE` ma niepuste pole "nazwa".
