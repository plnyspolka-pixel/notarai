---
id: crbr-wspolne-czyszczenie
tor: koder
zakres:
  - crbr.py
sprawdzenie: python -m pytest -q test_crbr.py
---
# crbr.py: wspólna funkcja czyszczenia numeru

## Stan teraz
W `crbr.py` funkcje `normalizuj_nip` i `normalizuj_krs` zaczynają się tym samym wierszem z `re.sub(...)` usuwającym spacje, myślniki, podkreślenia i kropki.

## Stan docelowy
Jedna prywatna funkcja `_cyfry(tekst: str | None) -> str` z tym wyrażeniem i krótkim docstringiem; obie funkcje ją wywołują. Zachowanie obu funkcji nie zmienia się w żadnym przypadku (None, pusty napis, spacje, myślniki, kropki, podkreślenia).

Zmieniasz tylko `crbr.py`; pliku testów nie ruszaj - wszystkie testy w `test_crbr.py` muszą przechodzić.
