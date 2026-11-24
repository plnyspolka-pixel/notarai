# NotarAI Word — aktywna edycja projektów przez AI

Host: https://app.notarai.pl/static/word/panel.html (ta sama domena co API).
Manifest: dodatki/word/manifest.xml (Office TaskPane, ReadWriteDocument).

## Flow
1. Notariusz loguje się swoim kontem Cognito (JWT tylko w pamięci WebView).
2. Potwierdza, że pracuje na projekcie lub kopii roboczej.
3. Wybiera zakres i wydaje polecenie językiem naturalnym.
4. Dodatek pobiera tekst bieżącego Worda i wysyła go do POST /api/word/propozycja.
5. Główny backend NotarAI weryfikuje członkostwo kancelarii, rolę projekt oraz wywołuje Bedrock.
6. Model zwraca JSON z małymi, jednoznacznymi operacjami find/replace/insert/delete/format/append.
7. Python waliduje kotwice i typy. Panel wyświetla każde proponowane działanie (brak HTML z modelu).
8. Notariusz wybiera zmiany i potwierdza zastosowanie.
9. Dodatek porównuje aktualny dokument z migawką, włącza Track Changes, weryfikuje dopasowania w Wordzie i wykonuje operacje.

## Ograniczenia / bezpieczeństwo
- Dotyczy edycji tekstu, podstawowego formatowania, wstawiania sformatowanych bloków HTML oraz tabel w treści głównej dokumentu, w tym tekstu w tabelach, gdy Word.search odnajdzie unikatową kotwicę.
- Nie obsługuje pełnej bezstratnej rekonstrukcji złożonych OOXML, nagłówków/stopki i automatycznego generowania tabel z dowolnym układem. „Pełna edycja” wymaga jeszcze poszerzenia adaptera i testów w Wordzie.
- Dokument przesyłany jest jawnie (po działaniu użytkownika) do istniejącej ścieżki Bedrock — nie deklarować z tego powodu 3×ZERO.
- Nie wysyła, nie podpisuje i nie zapisuje automatycznie dokumentów; działa wyłącznie na kopiach roboczych.
- Rozmiar dokumentu w jednym żądaniu: 100 tys. znaków, max 30 operacji. Dla dłuższych zaznaczaj fragmenty.
- WordApi >=1.4 wymagany do śledzenia zmian. Jeśli host go nie oferuje, dodatek blokuje edycję.
- Brak gwarancji transakcyjnego rollbacku przy częściowym błędzie Word.run. Po błędzie sprawdź dokument.
- Wymagana walidacja na prawdziwym Microsoft Word (desktop + Web) i testy regresji z dokumentami DOCX przed udostępnieniem klientom.

## Testy
- python -m pytest -q test_word_addin.py
- node --test static/word/test-edits.cjs
- testy end-to-end na Word desktop/web pozostają konieczne.
