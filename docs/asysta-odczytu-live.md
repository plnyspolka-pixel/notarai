# NotarAI — Asysta odczytu aktu na żywo (MVP)

## Funkcje

- Polski ASR **Amazon Transcribe Streaming** (pl-PL), wyłącznie Frankfurt (eu-central-1).
- Naciśnięcie "Włącz mikrofon" i odrębna zgoda użytkownika rozpoczynają sesję.
- Przeglądarka przekształca dźwięk z mikrofonu do 16 kHz mono PCM s16le w AudioWorklet.
- Backend wymaga ważnego tokenu kancelarii także dla WebSocket — middleware HTTP go nie obejmuje.
- Fragmenty częściowe i zatwierdzone wyniki Transcribe są widoczne w przeglądarce. Audio i transkrypcji **nie zapisujemy** w tym module.
- Użytkownik może skopiować rozpoznaną wypowiedź do instrukcji dla Bedrock, zaznaczyć fragment dokumentu, wygenerować propozycję.
- Model nie edytuje dokumentu: tylko proponuje "before" i "after"; stary fragment musi występować dokładnie raz, musi pasować hash wersji.
- Po zatwierdzeniu przez notariusza powstaje osobna wersja robocza DOCX albo (w trybie sporządzonego oryginału) wyłącznie notatka.
- Źródłowy projekt.txt/projekt.docx oraz oryginał aktu **nigdy nie są zmieniane**.
- Odsłuch Polly z PR #126 pozostaje osobną funkcją.

## Zabezpieczenia i ograniczenia

- Amazon Transcribe / Bedrock to zarządzane usługi AWS, więc nie jest to Zero Operator Access.
- Włączenie streaming STT wymaga ustawionego PIECZAPP_TRANSCRIBE_OPTOUT=1.
- Propozycja AI wymaga ponownej weryfikacji prawnej, językowej i liczbowej przez człowieka.
- Nie potwierdzamy formalnego odczytania, nie zapisujemy dowodu odczytania, nie rozpoznajemy automatycznie, który mówca jest notariuszem, ani nie oceniamy zgody stron.
- Przełącznik "oryginał" generuje wyłącznie notatkę; poprawki na oryginale wymagają czynności według art. 94 §2 PrNot.
- Asysta dla kancelarii z przechowywaniem "u-klienta" jest wyłączona, bo projekty nie mogą być automatycznie przesyłane z ich dysków do serwera.
- Limity żądań i sesji są procesowe (per replika ECS); globalny limit wymaga AWS Budgets/centralnego limitera.
- Backend nie chroni przed symultanicznymi zatwierdzeniami z dwóch replik atomowym CAS S3; każda rewizja jest osobnym nieusuwalnym plikiem, ale przy równoległej pracy należy zsynchronizować wybór aktualnej gałęzi przed udostępnieniem produkcyjnym na wielu stanowiskach. MVP: jedna aktywna sesja redakcyjna na sprawę.
- Przechowywanie notatek z oryginału jako historii decyzji nie oznacza naniesienia poprawek na oryginale.

## Uruchomienie

1. Wdrożyć zmiany w app.py, requirements.txt i szablonie infra/notarai-aplikacja.yaml z AsystaOdczytu=false.
2. Kontener ECS dostaje uprawnienie transcribe:StartStreamTranscription z warunkiem aws:RequestedRegion = eu-central-1, a PIECZAPP_ASYSTA_ODCZYTU uruchamia się po celowym ustawieniu parametru AsystaOdczytu=true (domyślnie false).
3. Upewnić się, że polityka AI-services opt-out jest aktywna w AWS Organizations. Uruchomić pilotaż na osobnym środowisku po ustawieniu AsystaOdczytu=true.
4. Testować TYLKO na fikcyjnym projekcie i wypowiedziach testowych. Sprawdzić JWT, brak przechowywania, różnice wersji, DOCX oraz zapis notatki.
5. W aplikacji kliknąć "Asysta odczytu" lub otworzyć /asysta-odczytu.

Testy: pytest -q test_asysta_odczytu.py, node --check static/asysta-odczytu.js i static/asysta-worklet.js.

Źródła:
- https://docs.aws.amazon.com/transcribe/latest/dg/streaming.html
- https://docs.aws.amazon.com/transcribe/latest/dg/supported-languages.html
- https://github.com/awslabs/amazon-transcribe-streaming-sdk
