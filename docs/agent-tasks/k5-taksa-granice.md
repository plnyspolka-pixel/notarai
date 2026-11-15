# K5 - taksa: testy na granicach progów

Zakres: tylko test_taksa.py (dopisz testy na końcu pliku). Nie zmieniaj taksa.py.

Przeczytaj funkcję stawka_podstawowa w taksa.py i tabelę stawek, z której korzysta. Dopisz test
parametryzowany, który dla każdego progu wartości sprawdza trzy punkty: dokładnie na progu, o 1 grosz
poniżej i o 1 grosz powyżej, i potwierdza, że stawka jest niemalejąca oraz ciągła na progu
(różnica między progiem a progiem + 1 grosz nie przekracza 1 grosza). Progi odczytaj z danych modułu,
nie przepisuj ich na sztywno. Jeżeli któryś warunek nie zachodzi, NIE poprawiaj taksa.py - oznacz
przypadek jako xfail z opisem i zgłoś to w raporcie.

Sprawdzenie: python -m pytest -q test_taksa.py

Zasady: tylko dane syntetyczne; nie czytaj dane/, .env ani żadnych kluczy; bez sieci i bez instalowania paczek. Zmieniaj wyłącznie wymienione pliki. Na koniec podaj: zmienione pliki, wynik testów, ograniczenia.
