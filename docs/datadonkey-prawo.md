# DataDonkey — prawo w NotarAI

Kod integracji, bez wdrożenia. Źródło: https://github.com/plnyspolka-pixel/DataDonkey/pull/147 ; eksport `research/world-law/notarai_snapshot.py`.

## Co działa w kodzie
- `prawo_datadonkey.szukaj` czyta lokalny indeks JSON; nie wykonuje połączeń sieciowych. Sprawdza schemat, przypięty SHA-256 całego pliku, skróty tekstów, źródło, commit korpusu, status review, daty i jednoznaczność wersji. Nie loguje zapytań.
- `bedrock.sporzadz_projekt`, `bedrock.rozmawiaj` i `pulpit_ai.rozmowa`: automatyczny, ograniczony kontekst publicznych przepisów PL na dziś (maks. 6 wyników, 16 tys. znaków). W czacie głównym narzędzie `wyszukaj_prawo` pozwala jawnie wybrać datę i państwo. Nie automatyzuje rozstrzygnięcia prawa właściwego. Przy historycznych aktach notariusz musi sprawdzić właściwy dzień; automatyczny kontekst PL na dziś nie zastępuje tego ustalenia.
- Teksty są materiałem źródłowym, nie instrukcjami dla modelu. Projekt nie jest gotowy do podpisu. Nie umieszczamy metadanych technicznych w treści aktu. Brak wyniku nie dowodzi braku regulacji. Nie ma mechanicznej walidacji wszystkich cytowań wyjściowych modelu ani automatycznego doboru wszystkich właściwych przepisów.
- Do DataDonkey nie trafia treść aktu, skany, dane stron, zapytania ani historia rozmów. Dane spraw w istniejącym przepływie Bedrock podlegają dotychczasowej polityce NotarAI; nie zmieniono konfiguracji modeli, retencji ani regionu.

## Konfiguracja pilota
1. DataDonkey: pozyskać urzędowy dokument i sprawdzić jego skrót, prawa do ponownego użycia, dokładny tekst, wszystkie zmiany i przedział obowiązywania przepisu. Przygotować zatwierdzony manifest. Eksporter obsługuje XML/HTML i PDF z jawnym numerem strony (dla PDF wymaga pypdf w środowisku eksportu). Nie poświadcza sam prawidłowości interpretacji prawnej ani commita.
2. W DataDonkey uruchomić `python research/world-law/notarai_snapshot.py --review <review.json> --raw <katalog obiektów SHA256> --out <law.json>`. Otrzymany SHA-256 przekazać zaufanym kanałem konfiguracji.
3. Dostarczyć wyłącznie publiczny plik prawa do odczytu przez NotarAI. Ustawić `PIECZAPP_PRAWO_SNAPSHOT` (ścieżka pliku) i `PIECZAPP_PRAWO_SHA256` (64 małe znaki hex). Bez ścieżki funkcja jest wyłączona, bez poprawnego skrótu nie używa treści. Nie pobierać pliku na podstawie URL podanego przez klienta. Nie przechowywać akt klientów w tym katalogu.
4. Indeks i przegląd prawa muszą być aktualne (limit 48 h dla indeksu, dwa dni kalendarzowe dla daty kontroli przepisów). Aktualizacja wymaga atomowej wymiany pliku i konfiguracji przypiętego skrótu, przy niespójności integracja odmawia użycia zbioru. Automatyczna dystrybucja i podpisywanie kolejnych wersji nie są jeszcze wdrożone.
5. Testy `pytest test_prawo_datadonkey.py test_bedrock.py test_rozmowa.py test_pulpit_ai.py test_zgodnosc_sdk.py`. Następnie test na fikcyjnej sprawie w Bedrock EU i porównanie projektu ze źródłem, wersją i datą. Zbadać brak źródła, nowelizację, przepis przyszły, źródło nieaktualne i sprzeczne wersje.

## Zakres danych
Pilotażowy JSON do 16 MiB, nie globalna baza produkcyjna. Dla większego korpusu potrzebny lokalny indeks pełnotekstowy, przyrostowe publikacje i podpisany manifest. W pierwszej kolejności polskie akty: Kodeks cywilny, Prawo o notariacie, ustawa o księgach wieczystych i hipotece, KPC, PCC, podatki od spadków i darowizn oraz rozporządzenie o taksie. Nie utożsamiać listy priorytetów z gotowym korpusem ani z pełną aktualnością. Zmiany infrastruktury, IAM lub umowy powierzenia wymagają osobnej oceny i akceptacji zgodnie z AGENTS.md.

Brak danych źródłowych nie może być maskowany przez przykładowe przepisy. W repozytorium testy zawierają wyłącznie fikcyjne dane. Nie włączono produkcji ani harmonogramu.
