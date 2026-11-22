# SEC-10 — [SEC-10] Zero Knowledge: cykl życia plaintext, retencja, logi, kopie i usuwanie

**Status: PLANNED (NOT IMPLEMENTED).** P0; zależności: SEC-03, SEC-04, SEC-08

## Zakres
1. Zmapuj w jakich procesach dokument występuje jawnie: browser RAM, model context, PDF preview, exception, crashdump, screenshot, metrics, tmpfs, stdout/stderr, support, cache i backup.
2. Wymuś minimalny lifetime DEK/plaintext wewnątrz zatwierdzonego Nitro; brak core dump, persisted browser cache i metadanych ujawniających PII; na ile technicznie możliwe: bezpieczna likwidacja sesji i zera po zakończeniu.
3. Przetestuj retencję i usuwanie ciphertext, kluczy/wersji, backupów, danych z LLM i audytu zgodnie z wymaganiami notarialnymi/RODO; NIE obiecuj kasowania historii w S3 Retain/PITR bez osobnej procedury.
4. Przygotuj model recovery i legal hold: operator nie może mieć ukrytego klucza awaryjnego, a notariusz/kustosz muszą znać ograniczenia odtwarzania.

## Kryteria odbioru
- [ ] Audyt artefaktów po crash/retry: brak plaintext w miejscach dostępnych operatorowi.
- [ ] Testy wyjątków, pamięci tymczasowej, logów, zrzutów, historycznych wersji i odmowy plaintext backup.
- [ ] Precyzyjne retencje i ograniczenia Zero Knowledge potwierdzone dowodami, nie obietnicą.

## Instrukcja dla osobnej konwersacji
To **wyłącznie PR planistyczny**. Zrealizuj zadanie na istniejącej gałęzi tego PR, uzupełnij kod, testy, instrukcje i dowody w tym samym PR. Czytaj poprzednie #57, #60, #61, #62, #65 i odpowiednie SEC-nn; sprawdź aktualne SHA. Wszystkie SEC-nn bazują na #65 i nie wymagają edycji gałęzi pozostałych zadań. Jeśli potrzebna zmiana w pliku współdzielonym, udokumentuj integracyjne uzgodnienie i konflikt.
Zakres danych: wyłącznie syntetyczne pilot01/pilot02, EU eu-central-1, produkcja OFF, no-submit/no-sign. Nie dotykaj prawdziwych spraw, nie wynoś plaintext ani sekretów do CloudWatch/GitHub/proxy. Nie wykonuj AWS write bez autoryzowanych tożsamości i zgody kustosza. Wyniki CI != real hardware evidence. Kryteria: kod + testy odmowy + dokumentacja, niezależny dowód i jawne FAIL/BLOCKED. Bez automatycznej deklaracji 'Verified Zero Knowledge/Zero Operator Access'.
