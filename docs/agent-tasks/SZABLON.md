---
id: nazwa-z-myslnikami
tor: koder
zakres:
  - modul.py
  - test_modul.py
sprawdzenie: python -m pytest -q test_modul.py
kroki: 40
rodzaj: zmiana  # zmiana | refaktor | testy; ukryte testy w docs/agent-tasks/ukryte/<id>/ (docs/koder.md)
---
# Jedno zdanie: co ma być zrobione

## Stan teraz
Plik `modul.py`, funkcja `nazwa()` (ok. wiersza N): co robi dziś, na przykładzie wejście -> wynik.

## Stan docelowy
Co ma robić po zmianie, na tym samym przykładzie. Każdy przypadek brzegowy wypisany osobno.

## Kryteria akceptacji
- 1-3 punkty, każdy sprawdzalny z zewnątrz: wejście -> wynik albo nazwa testu, który przechodzi.

## Testy
Co dopisać w `test_modul.py` (nazwy przypadków). Istniejące testy mają dalej przechodzić.

## Nie ruszaj
Sygnatur publicznych funkcji, innych modułów, komunikatów widocznych dla użytkownika.
Jeżeli stan docelowy już jest spełniony, dozwolony wynik to „ZMIANA NIEPOTRZEBNA: <uzasadnienie>”.
