---
id: rekomendacje-okno-dni
tor: koder
zakres:
  - rekomendacje.py
  - test_rekomendacje.py
sprawdzenie: python -m pytest -q test_rekomendacje.py
---
# rekomendacje.przydziel: okno dni jako parametr

## Stan teraz
`przydziel(kandydaci, wczesniejsze, kontekst, teraz=None)` w `rekomendacje.py` liczy wcześniejsze przydziały z ostatnich `OKNO_DNI` dni - stała wpisana na sztywno w treści funkcji.

## Stan docelowy
Nowy parametr na końcu: `okno_dni: int = OKNO_DNI`, użyty zamiast stałej przy liczeniu `granica`. Wywołania bez parametru działają dokładnie jak dotąd.

## Testy
Dopisz do `test_rekomendacje.py` test ze stałym `teraz`: dwie kancelarie, pierwsza ma przydział sprzed 10 dni (`"przydzial": {"sposob": "kolejka"}`). Przy `okno_dni=30` ten przydział się liczy i wybierana jest druga kancelaria. Przy `okno_dni=5` przydział jest poza oknem i wynik równa się `min(kandydaci, key=lambda k: los(teraz.date(), kontekst, k))`. Istniejące testy mają przechodzić.
