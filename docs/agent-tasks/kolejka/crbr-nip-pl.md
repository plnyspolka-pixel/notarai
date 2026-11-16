---
id: crbr-nip-pl
tor: koder
zakres:
  - crbr.py
  - test_crbr.py
sprawdzenie: python -m pytest -q test_crbr.py
---
# crbr.normalizuj_nip: przedrostek kraju PL

## Stan teraz
`crbr.normalizuj_nip("PL 526-025-09-95")` zwraca None.

## Stan docelowy
Funkcja `normalizuj_nip` w `crbr.py` pomija opcjonalny przedrostek "PL" (dowolna wielkość liter, ze spacją lub bez):
- "PL 526-025-09-95" -> "5260250995"
- "pl5260250995" -> "5260250995"
- "526-025-09-95" -> "5260250995" (jak dotąd)
- "DE5260250995" -> None; "PL" -> None; None -> None; "PL 123" -> None

`normalizuj_krs` zostaje bez zmian.

## Testy
Dopisz te przypadki do `test_crbr.py`. Istniejące testy mają przechodzić.
