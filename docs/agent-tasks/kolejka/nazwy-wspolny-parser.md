---
id: nazwy-wspolny-parser
tor: koder
zakres:
  - nazwy.py
sprawdzenie: python -m pytest -q test_nazwy.py
---
# nazwy.py: wspólna funkcja dla powtórzonego odczytu "STALE: nazwiska stron"

## Stan teraz
W `nazwy.py` ten sam fragment występuje dwa razy - w `nazwa_sprawy` i w `nazwiska_stron`: dzielenie wartości pola "STALE: nazwiska stron" tym samym wyrażeniem regularnym, odfiltrowanie przez `SLOWO.match` i `NIE_NAZWISKA`, przepuszczenie przez `_ladnie`.

## Stan docelowy
Jedna prywatna funkcja `_nazwiska_ze_stalego(wartosc) -> list[str]`, która zwraca listę po filtrze i `_ladnie`, BEZ usuwania powtórzeń i BEZ przycinania. Oba miejsca wywołują ją i dalej robią to, co dotąd, w tej samej kolejności:
- `nazwa_sprawy`: najpierw przycięcie do `MAX_NAZWISK`, potem `dict.fromkeys`;
- `nazwiska_stron`: najpierw `dict.fromkeys`, potem podział na zbywców i nabywców.

Zachowanie nie może się zmienić w żadnym przypadku. Zmieniasz tylko `nazwy.py`; pliku testów nie ruszaj - wszystkie istniejące testy w `test_nazwy.py` muszą przechodzić.
