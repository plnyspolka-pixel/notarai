---
id: taksa-kwota-kropki
tor: koder
zakres:
  - taksa.py
  - test_taksa.py
sprawdzenie: python -m pytest -q test_taksa.py
---
# taksa.kwota: kropki jako separator tysięcy

## Stan teraz
`taksa.kwota("250.000,00 zł")` zwraca `Decimal("0")`: po zamianie przecinka na kropkę powstaje "250.000.00", którego Decimal nie przyjmuje, a błąd jest połykany.

## Stan docelowy
W funkcji `kwota` w `taksa.py` (tylko gałąź dla napisów):
- jeżeli napis zawiera i kropkę, i przecinek, kropki są separatorem tysięcy i znikają: "250.000,00 zł" -> Decimal("250000.00");
- jeżeli napis ma więcej niż jedną kropkę i żadnego przecinka, wszystkie kropki znikają: "1.250.000" -> Decimal("1250000");
- bez zmian: "1234.56" -> Decimal("1234.56"); "450 000,50" -> Decimal("450000.50"); "abc" -> Decimal("0"); wartości ujemne -> Decimal("0").

## Testy
Dopisz te przypadki do `test_taksa.py` jako test parametryzowany. Wszystkie istniejące testy w pliku mają przechodzić. Nie zmieniaj innych funkcji.
