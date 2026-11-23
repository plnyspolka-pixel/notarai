# Główny czat NotarAI: polecenia tekstowe, głos i narzędzia

Status: implementacja w osobnej gałęzi; przed udostępnieniem produkcyjnym wymagane testy CI, test mikrofonu Android + Safari oraz sprawdzenie działania na testowej kancelarii.

## Zachowanie po logowaniu

Domyślnie otwiera się widok czatu (etap 13) z polem wpisywania poleceń, mikrofonem i skrótami. Tradycyjny kokpit pozostaje dostępny przyciskiem i pozycją menu. Profil kancelarii może wybrać inny widok startowy; dotychczas zapisane preferencje są respektowane.

## Zasada dostępu do narzędzi

`pulpit_ai.KATALOG` opisuje 18 istniejących obszarów aplikacji. Nawigacja odbywa się po stałych identyfikatorach, nie przez arbitralny adres URL. Narzędzia wykonywalne w pierwszym etapie:
- `otworz_modul`: nawigacja do istniejącego widoku (bez zapisu).
- `wyszukaj_sprawy`: podgląd metadanych maksymalnie 10 spraw kancelarii.
- `lista_komputerow`: stan wyłącznie sparowanych komputerów kancelarii.
- `przygotuj_polecenie_windows`: przygotowanie potwierdzanego polecenia dla aktywnego PC, bez wysyłki przez sam model.

**To nie jest jeszcze wykonawczy dostęp do wszystkich operacji API NotarAI.** Wysyłka pism/e-maili, płatności, usuwanie i podpisy nie są dostępne z czatu bez odrębnych, dedykowanych i audytowanych mechanizmów zgody. Narzędzia do kalendarza, ksiąg, GIIF, dokumentów i poczty mają na razie nawigację do istniejących ekranów. Kolejne adaptery należy budować jako osobne funkcje z typowanymi argumentami, walidacją, kontrolą stanowiska i idempotencją.

## Samonaprawa w jednym głównym czacie

Czat główny ma dwa dodatkowe narzędzia Bedrock:
- `przygotuj_zgloszenie_samonaprawy` zbiera opis objawu, anonimizuje go istniejącym `samonaprawa.anonimizuj` i zwraca tylko **propozycję** do zatwierdzenia.
- `sprawdz_postep_samonaprawy` pobiera etapy, numery i postęp procentowy wyłącznie zgłoszeń zalogowanej kancelarii z istniejącego `asystent_kancelarii.prosby_z_postepem`.

Bezpośrednie API jest dostępne wyłącznie w sesji zalogowanego członka kancelarii:
- `POST /api/pulpit-ai/samonaprawa/zglos` — uruchamia istniejące `asystent_kancelarii.wykonaj("zglos_zmiane_programu", ...)` dopiero **po osobnym kliknięciu** przycisku „Potwierdź zgłoszenie”. Ten sam limit 5 zgłoszeń/dobę i deduplikacja powtórzeń. Brak wykonania narzędzia z samego tekstu modelu.
- `GET /api/pulpit-ai/samonaprawa` — statusy (nie zawierają treści zgłoszeń). Mechanizm statusów może automatycznie włączać dopuszczone ustawienie kancelarii po wdrożeniu naprawy — to obecne działanie istniejącego modułu.

Zmian logowania, uwierzytelniania, uprawnień i płatności nie kierujemy do samonaprawy — człowiek z zespołu NotarAI musi je rozpatrzyć. Wstępna reguła opisowa nie zastępuje bramek GitHub Actions. Wyłącznie istniejący workflow `.github/workflows/samonaprawa.yml` decyduje, czy korekta może zostać automatycznie scalona i wdrożona. Główny Chat AI nie ma dostępu do swobodnego zapisu plików repozytorium, tokenów CI, arbitralnego REST API ani mechanizmu ręcznego pomijania bramek.

Przykłady: „Kalendarz nie zapisuje zmian, napraw to” (propozycja + akceptacja) i „Na jakim etapie jest moja naprawa?” (status). Dyktowanie korzysta z tego samego przycisku mikrofonu głównego czatu.

## Polecenia głosowe

- Przycisk mikrofonu uruchamia `getUserMedia` i `MediaRecorder` wyłącznie po dotknięciu przez użytkownika. Dźwięk max. 60 sekund / 15 MB, wybór `webm`/`mp4`.
- W instalacji lokalnej: istniejący `faster-whisper`, jeśli został zainstalowany.
- W SaaS: istniejący bucket kancelarii i AWS Transcribe w `eu-central-1`. Start zadania `POST /api/pulpit-ai/glos`, odczyt `GET /api/pulpit-ai/glos/{id}`. Warunek: `PIECZAPP_TRANSCRIBE_OPTOUT=1` oraz region `eu-central-1`.
- Nazwa zadania zawiera skrót identyfikatora kancelarii i losowy identyfikator. Audio oraz nieanonimizowany wynik trafiają na krótko pod prefiks danej kancelarii; po odebraniu tekstu usuwane są wszystkie wersje obu obiektów S3 i zadanie AWS Transcribe.
- Jeśli użytkownik zamknie kartę przed pobraniem wyniku, następna próba głosowa z tej kancelarii usuwa porzucone nagrania starsze niż 24 godziny. Potrzebny osobny harmonogram sprzątający, aby zagwarantować usunięcie także przy braku późniejszych sesji.
- Rozpoznany tekst zostaje pokazany w edytowalnym polu. **Głos nie wysyła polecenia automatycznie.** Klient może poprawić rozpoznanie przed zatwierdzeniem.

## Potwierdzanie czynności

Polecenie Windows jest tylko propozycją narzędzia Bedrock. Frontend tworzy kartę z celem i komputerem, a przycisk **Sprawdź i zatwierdź** otwiera dodatkowe okno. Dopiero **Zatwierdź i przekaż** wykonuje POST do istniejącego przepływu mobilnego.

**Zależność od PR #124:** endpoint `/api/urzadzenia/polecenia` pozostaje w otwartym PR #124. Do czasu scalenia klient otrzyma informację o braku możliwości przekazania zadania. PR #124 wymaga testu na prawdziwym Windows i Android; nie należy automatycznie wdrażać tego funkcjonalnie zależnego PR bez weryfikacji.

## Bezpieczeństwo i testy akceptacyjne

- Sesja członka zespołu, bez dostępu tokenu pomocnika i serwisu.
- Lista narzędzi i prawo wykonania kontrolowane na serwerze przez istniejące `stanowiska`.
- Zakaz niejawnego wykonywania arbitralnego endpointu, kodu lub URL przez model.
- Nowe reguły `stanowiska` dla POST /api/urzadzenia/polecenia.
- Wczytane treści spraw są danymi, a nie instrukcjami wyższego priorytetu.
- Po wylogowaniu historia czatu i rozpoczęte nagranie są czyszczone; wyniki poprzedniej sesji są ignorowane.
- Brak tekstów poleceń, danych osobowych, tokenów i audio w logach.
- Przed produkcją: zielone `pytest`, kontrola JS, test rozpoznawania polskiego na Android/Chrome i Safari/iOS, sprawdzenie uprawnień pracownika, potwierdzeń i czyszczenia S3.
- Osobny audyt zgodności z modelem zero operator access / zero knowledge: przesyłanie audio do Transcribe i tekstu do Bedrock oznacza przetwarzanie w chmurze, nie jest samo w sobie rozwiązaniem zero-knowledge.
