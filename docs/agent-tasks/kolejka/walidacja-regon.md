---
id: walidacja-regon
tor: koder
zakres:
  - walidacja.py
  - test_walidacja.py
sprawdzenie: python -m pytest -q test_walidacja.py
---
# walidacja.py: walidator numeru REGON

## Stan docelowy
Nowa funkcja `regon(wartosc: str) -> tuple[bool, str]` w `walidacja.py`, w stylu istniejących `pesel` i `nip` (przeczytaj je najpierw):
- usuwa spacje i myślniki; przyjmuje 9 albo 14 cyfr, inaczej `(False, "REGON musi miec 9 albo 14 cyfr")`;
- 9 cyfr: wagi 8,9,2,3,4,5,6,7 dla pierwszych ośmiu cyfr; cyfra kontrolna = suma mod 11, a wynik 10 oznacza 0;
- 14 cyfr: najpierw pierwsze 9 cyfr sprawdzane jak wyżej, potem wagi 2,4,8,5,0,9,7,3,6,1,2,4,8 dla pierwszych trzynastu; kontrolna = suma mod 11, 10 oznacza 0;
- błędna cyfra kontrolna: `(False, "Bledna cyfra kontrolna REGON")`; poprawny: `(True, "REGON poprawny")`.

Zarejestruj ją w słowniku `REGULY` pod kluczem `"regon"`.

Przykłady: "123456785" poprawny; "123456786" błędna kontrolna; "12345678512347" poprawny; "12345678512348" błędna kontrolna; "12345" zła długość.

## Testy
Dopisz do `test_walidacja.py` powyższe przypadki oraz test, że `sprawdz_pole("REGON", "123456785")` zwraca `(True, "REGON poprawny")`. Istniejące testy mają przechodzić.
