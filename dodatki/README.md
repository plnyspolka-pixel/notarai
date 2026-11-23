# NotarAI — dodatki do edytorów i przeglądarek

Publiczny dział pobierania: strona/do-pobrania/index.html.

- Chrome/Edge: ten sam produkowany z istniejącego źródła \`rozszerzenie/\` pakiet ZIP (do testów przez „Załaduj rozpakowane”).
- Word: manifest XML wskazuje na hostowany panel, który potrafi **tylko lokalnie odczytać zaznaczony tekst** i otworzyć aplikację. Nie przesyła tekstu automatycznie i nie edytuje dokumentu. Wersja beta.
- Apache OpenOffice: pakiet OXT dodaje skrót do otwarcia NotarAI. Nie czyta ani nie edytuje dokumentu. Wersja beta. Instalacja i działanie toolbaru wymagają testu na AOO 4.x na Windows.

Budowa: \`python scripts/buduj_pobieranie.py\`. Paczki powstają w \`strona/do-pobrania/pliki/\` podczas wdrożenia serwisu publicznego; nie są przechowywane w Git. Sumy SHA-256 są tworzone automatycznie.

Nie nazywać żadnego z tych dodatków pełną integracją edycji aktów, nie deklarować zgodności z 3×ZERO bez odrębnej weryfikacji, nie zalecać wyłączania antywirusa. Publikacja w Chrome Web Store i Microsoft Edge Add-ons wymaga osobnych formalności i akceptacji sklepów.

Produkcyjne dodatki będą potrzebowały testów na rzeczywistych programach, dopracowania uprawnień, sesji i zaakceptowanych zmian.