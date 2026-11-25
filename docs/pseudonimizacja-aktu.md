# PR 143 — pseudonimizacja i tożsamość uczestników (beta)

**Nie aktywować produkcyjnie przed odbiorem.** Domyślnie istniejący tryb pozostaje bez zmian. `PIECZAPP_BEDROCK_CHRONIONY=1` uruchamia tryb blokujący niezatwierdzone żądania we wspólnym kliencie Bedrock. To nie jest jeszcze pełne pokrycie całego produktu ani certyfikacja 3×Zero.

## Przepływ
1. PDF/skan: lokalny Tesseract (pol), warstwa tekstowa PDF i OCR zapisywane w istniejącej sprawie. Niska pewność wymaga sprawdzenia. Brak OCR zatrzymuje operację, nie wysyła obrazu.
2. GET/POST `/api/sprawy/{id}/pseudonimizacja/rejestr`: uprawniony notariusz/właściciel potwierdza uczestnika na podstawie wskazanych zakresów źródeł, nadaje aliasy i role; stabilne UUID, kontrola PESEL i wersji, historia decyzji.
3. POST `.../przeglad` z celem (rozmowa, projekt, ekstrakcja) i poleceniem: zwraca dokładny tekst, odcisk, wersję rejestru, propozycje identyfikatorów. Zakresy liczone jako punkty kodowe Unicode, nie bajty ani jednostki UTF-16.
4. POST `.../wykonaj`: identyczny cel i polecenie, odcisk, wersja, zakresy, potwierdzam=true. Serwer ponownie buduje tekst, sprawdza źródła, maskuje znane aliasy i PESEL oraz zatwierdzone inne dane. Niejednoznaczne osoby i sprzeczne zakresy zatrzymują operację.
5. Jednorazowa mapa w pamięci procesu; do modelu idą tokeny, nie mapa. Odpowiedź kompletna i tekstowa, dokładne tokeny są odtwarzane. Wynik jest propozycją do weryfikacji, nie automatycznie zapisanym aktem.

## Macierz ścieżek
| Ścieżka | Stan trybu chronionego |
|---|---|
| Główne wgrywanie sprawy, skany i PDF | Lokalny OCR, bez modelu |
| Wzór, pola, źródła, historia, polecenia, personalizacja | W nowym przepływie API, po zatwierdzeniu tekstu |
| Ekstrakcja, rozmowa, generowanie | Tekstowa propozycja przez nowe API, nie zastępuje jeszcze dotychczasowego zapisu wyników |
| Wspólny klient Bedrock / Converse | Kontrola odcisku payloadu, tenant, wątek i metoda |
| Stary streaming, tool use, obrazy, poprawki AI | Blokada, nie działający odpowiednik chroniony |
| Asysta odczytu, Word, pulpit, teczka, pozostałe moduły używające wspólnego klienta | Dotychczasowe niezatwierdzone wywołania blokowane; integracja funkcjonalna do wykonania |
| Skrypty kampanii i samonaprawa (własny klient/CLI) | Poza zweryfikowaną granicą aplikacji; osobny audyt egress/IAM konieczny |

## Kandydaci open source
- Tesseract + pol: użyty lokalnie; https://github.com/tesseract-ocr/tesseract i https://github.com/tesseract-ocr/tessdata
- Morfeusz 2 (BSD-2-Clause): https://morfeusz.sgjp.pl/doc/license/ — generowanie i analiza fleksji; kandydat do propozycji aliasów, nie do samodzielnego łączenia ludzi.
- PolDeepNer2: https://github.com/CLARIN-PL/PolDeepNer2 i https://huggingface.co/CodeNLP/pdn2_v08_kpwr_ner_n82 — lokalny NER do wykrywania osób i miejsc, wymaga testu na aktach oraz przeglądu licencji artefaktów.
- IPIPAN pl_nask: https://huggingface.co/ipipan/pl_nask — alternatywa NER/fleksja; osobna weryfikacja licencji modeli.
- Presidio: https://github.com/microsoft/presidio — konfigurowalne detektory PII; polskie identyfikatory potrzebują własnych reguł.
- Splink: https://github.com/moj-analytical-services/splink — probabilistyczne dopasowania jedynie jako sugestie; brak automatycznego scalania uczestników.

## Ograniczenia i bramka odbioru
- Ręczny przegląd całego tekstu jest konieczny; reguły PII nie rozpoznają każdej osoby, adresu lub danych kontekstowych. Opcjonalny interfejs NER nie oznacza wbudowanego modelu. Odmiany nieznane wymagają potwierdzonych aliasów. Maska nie jest anonimizacją w rozumieniu RODO.
- Model może pominąć token, użyć prawidłowego tokenu przy niewłaściwej roli lub wygenerować nową informację. Odtwarzanie nie jest walidacją semantyczną aktu.
- Brak jeszcze pełnego interfejsu zatwierdzania, automatycznej ekstrakcji strukturalnej i wpięcia propozycji do istniejącego edytora/generatora, narzędzi i streamingu. Nie używać produkcyjnie.
- Rejestr przechowywany jak istniejące dane sprawy, S3 z warunkowym zapisem i szyfrowaniem kancelarii, jeśli aktywne. Nie jest niezależnym sejfem kryptograficznym.
- Testy syntetyczne w test_pseudonimizacja_aktu.py obejmują roundtrip, homonimy, odmiany, role, błędne zakresy, PESEL, OCR, izolację tenantów, mock Bedrock, zgodność SDK i API. Wykonanie całego pytest, rzeczywistego OCR w obrazie kontenera, testów współbieżności S3, regresji interfejsu oraz niezależnego audytu egress jest obowiązkowe przed merge.
- Nie przesyłać realnych danych notarialnych do testów. Wyniki CI i testy wdrożeniowe muszą być faktycznie odczytane przed dopuszczeniem.
